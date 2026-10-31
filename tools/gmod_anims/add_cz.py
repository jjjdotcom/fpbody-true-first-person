"""Add Counter-Strike: Condition Zero weapon animations to an fpbody player model.

  python3 -I add_cz.py classic <cz player.mdl> <in.mdl> <out.mdl>
  python3 -I add_cz.py gmod    <cz player.mdl> <in.mdl> <out.mdl>

classic: the Condition Zero aim / shoot / reload sequences, retargeted onto the
  model's Half-Life skeleton (same Biped bones, CZ uses the Clavicle/UpperArm/
  Thigh names). Their 9 pitch blends (-90..90) are cut to the two Half-Life
  uses (-45, +45). Sets: mp5, shotgun and onehanded replace Half-Life's; rifle,
  m249, knife, grenade and c4 are new (c4 throws with the grenade throw);
  reloads for mp5, shotgun, onehanded, rifle and m249 are added for the client
  to play. The Half-Life shotgun hold is kept as "tau" for the Tau Cannon.
gmod: no Condition Zero data; the new set names are aliases of the model's own
  sequences, so the GMod-pose mode looks the same as before.

Texture pixel data is moved back to the end of the file (the engine drops
everything after texturedataindex once the textures are uploaded).
"""
import struct
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel     # noqa: E402
from compose import target_name      # noqa: E402

PARTS = ('ref_aim', 'ref_shoot', 'crouch_aim', 'crouch_shoot')
CZ_SETS = {            # our set name -> (aim from, shoot from) Condition Zero set
    'mp5': ('mp5', 'mp5'), 'shotgun': ('shotgun', 'shotgun'), 'onehanded': ('onehanded', 'onehanded'),
    'rifle': ('rifle', 'rifle'), 'm249': ('m249', 'm249'), 'knife': ('knife', 'knife'),
    'grenade': ('grenade', 'grenade'), 'c4': ('c4', 'grenade'),
}
RELOADS = ('mp5', 'shotgun', 'onehanded', 'rifle', 'm249')
GMOD_ALIAS = {'rifle': 'bow', 'm249': 'mp5', 'knife': 'crowbar', 'grenade': 'crowbar', 'c4': 'trip', 'tau': 'shotgun'}


def existing_sequences(M):
    out = []
    for i, s in enumerate(M.seqs):
        out.append(dict(label=s['label'], fps=s['fps'], flags=s['flags'], activity=s['activity'],
                        actweight=struct.unpack_from('<i', s['raw'], 44)[0], motiontype=s['motiontype'],
                        motionbone=s['motionbone'], linearmovement=list(s['linearmovement']),
                        blendtype=s['blendtype'], blendstart=s['blendstart'], blendend=s['blendend'],
                        frames=M.decode(i), raw=bytes(s['raw'])))
    return out


def clone(seq, label):
    c = dict(seq); c['label'] = label; c['frames'] = [a.copy() for a in seq['frames']]
    raw = bytearray(seq['raw']); lab = label.encode()[:31]; raw[0:32] = lab + bytes(32 - len(lab))
    struct.pack_into('<i', raw, 40, 0)     # no activity: only looked up by name
    c['raw'] = bytes(raw); c['activity'] = 0
    return c


class Retarget:
    def __init__(self, C, M):
        self.C, self.M = C, M
        self.base = M.decode(M.seq_by_name['look_idle'])[0][0].copy()
        self.map = {}
        for i, b in enumerate(C.bones):
            t = target_name(b['name'])
            if t in M.bone_by_name:
                self.map[M.bone_by_name[t]] = i
        self.root = [i for i, b in enumerate(M.bones) if b['parent'] < 0]
        # root height: Half-Life's own standing / crouching aim poses
        self.hl_root = {k: M.decode(M.seq_by_name[k + '_aim_mp5'])[0][0][self.root[0], :3] for k in ('ref', 'crouch')}
        cz = {k: C.decode(C.seq_by_name[k + '_aim_mp5']) for k in ('ref', 'crouch')}
        self.cz_root = {k: cz[k][4][0][0, :3] for k in ('ref', 'crouch')}
        legs = lambda G, a, b: np.linalg.norm(G.rest_local()[G.bone_by_name[a], :3]) + np.linalg.norm(G.rest_local()[G.bone_by_name[b], :3])
        self.k = legs(M, 'Bip01 L Leg1', 'Bip01 L Foot') / legs(C, 'Bip01 L Calf', 'Bip01 L Foot')

    def frames(self, cz_label, stance):
        C, M = self.C, self.M
        src = C.decode(C.seq_by_name[cz_label])
        if len(src) == 9:                      # -90..90 in 22.5 steps -> -45, +45
            src = [src[2], src[6]]
        out = []
        for arr in src:
            f = np.repeat(self.base[None], arr.shape[0], axis=0)
            for mi, ci in self.map.items():
                f[:, mi, 3:6] = arr[:, ci, 3:6]
            for r in self.root:
                ci = self.map.get(r)
                if ci is not None:
                    f[:, r, :3] = self.hl_root[stance] + (arr[:, ci, :3] - self.cz_root[stance]) * self.k
            out.append(f)
        return out


def cz_seq(C, R, cz_label, label, template):
    s = C.seqs[C.seq_by_name[cz_label]]
    stance = 'crouch' if label.startswith('crouch') else 'ref'
    frames = R.frames(cz_label, stance)
    two = len(frames) == 2
    d = dict(label=label, fps=s['fps'], flags=s['flags'] & 1, activity=0, actweight=0,
             motiontype=0, motionbone=0, linearmovement=[0, 0, 0],
             blendtype=[8, 0] if two else [0, 0], blendstart=[-45.0, 0] if two else [0, 0],
             blendend=[45.0, 0] if two else [1.0, 0], frames=frames)
    raw = bytearray(template['raw'])            # bbox etc. from a Half-Life sequence, no events
    struct.pack_into('<2i', raw, 48, 0, 0)
    struct.pack_into('<2i', raw, 60, 0, 0)
    struct.pack_into('<6i', raw, 152, 0, 0, 0, 0, 0, 0)
    d['raw'] = bytes(raw)
    return d


def textures_last(path):
    d = bytearray(open(path, 'rb').read())
    ntex, ti, tdi = struct.unpack_from('<3i', d, 180)
    if ntex == 0:
        return
    blocks = []
    for k in range(ntex):
        o = ti + k * 80
        flags, w, h, idx = struct.unpack_from('<4i', d, o + 64)
        blocks.append((o, bytes(d[idx:idx + w * h + 768])))
    while len(d) % 4:
        d.append(0)
    first = len(d)
    for o, blob in blocks:
        struct.pack_into('<i', d, o + 76, len(d))
        d += blob
    struct.pack_into('<i', d, 188, first)
    struct.pack_into('<i', d, 72, len(d))
    open(path, 'wb').write(d)


def main(mode, cz_path, in_path, out_path):
    M = GoldSrcModel(in_path)
    seqs = existing_sequences(M)
    by = {s['label']: s for s in seqs}
    added = []
    if mode == 'gmod':
        for new, old in GMOD_ALIAS.items():
            for p in PARTS:
                if '%s_%s' % (p, new) not in by:
                    added.append(clone(by['%s_%s' % (p, old)], '%s_%s' % (p, new)))
    else:
        C = GoldSrcModel(cz_path)
        R = Retarget(C, M)
        for p in PARTS:                                         # Half-Life shotgun hold -> Tau Cannon
            added.append(clone(by['%s_shotgun' % p], '%s_tau' % p))
        for name, (aim, shoot) in CZ_SETS.items():
            for p in PARTS:
                label = '%s_%s' % (p, name)
                src = '%s_%s' % (p, aim if 'aim' in p else shoot)
                new = cz_seq(C, R, src, label, by['%s_mp5' % p])
                if label in by:                                  # replace in place, keep its slot
                    i = seqs.index(by[label]); new['activity'] = seqs[i]['activity']; seqs[i] = new
                else:
                    added.append(new)
        for name in RELOADS:
            for st in ('ref', 'crouch'):
                added.append(cz_seq(C, R, '%s_reload_%s' % (st, name), '%s_reload_%s' % (st, name), by['ref_aim_mp5']))
    seqs += added
    M.write(out_path, seqs)
    textures_last(out_path)
    return len(seqs), len(added)


if __name__ == '__main__':
    print(main(*sys.argv[1:5]))
