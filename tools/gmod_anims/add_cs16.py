"""Counter-Strike 1.6 player animations (wOS "Counter-Strike 1.6: Port Edition",
Workshop 3218751593) as a selectable set on an fpbody GMod-mode player model.

  python3 -I add_cs16.py <m_reanm_cs16.mdl> <Freeman models folder> <in.mdl> <out.mdl>

The pack replaces Garry's Mod's player animations with Counter-Strike 1.6's
(same sequence names: idle_ar2, cidle_pistol, walk_all ...), layered like
Garry's Mod's: a body animation plus an aim matrix and an idle "posebreaker".
They are evaluated (add_l4d.Pose), retargeted (ValveBiped -> Bip01, like
add_freeman.py) and ADDED next to the model's own animations as

  cs16_ref_aim_ / cs16_ref_shoot_ / cs16_crouch_aim_ / cs16_crouch_shoot_<ext>
                                    every weapon hold (aim pitch blends)
  cs16_walk, cs16_walk2handed, cs16_run, cs16_run2, cs16_crawl,
  cs16_crouch_idle, cs16_deep_idle  the gaits

The client draws cs16_<name> in place of <name> when sv_fpbody_anims is
"cs16" (cl_dll/fpbody_anim.cpp, FPAnim_MapSeq); otherwise nothing changes.
Attack gestures the pack doesn't have (the guns) come from Garry's Mod's own
animations (m_anm_gmod.mdl in the Freeman folder).
The result contains third-party animation data: keep it local.
"""
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from srcmdl import SourceModel                               # noqa: E402
from goldsrc import GoldSrcModel                             # noqa: E402
from add_cz import existing_sequences, textures_last, clone  # noqa: E402
from add_freeman import PackRetargeter                       # noqa: E402
from add_l4d import Pose, movement_distance, IDLE_STEP, SEQ_POST, ANIM_DELTA   # noqa: E402
from retarget import apply_delta                             # noqa: E402

PREFIX = 'cs16_'
# fpbody weapon extension -> (CS 1.6 hold, attack gesture); gmod:<hold> =
# Garry's Mod's own. Empty hands keep the model's own (relaxed) hold.
HOLD = {
    'crowbar':   ('melee',    'range_melee'),
    'knife':     ('knife',    'range_knife'),
    'trip':      ('slam',     'range_slam'),
    'c4':        ('slam',     'range_slam'),
    'onehanded': ('pistol',   'range_pistol'),
    'python':    ('revolver', 'range_revolver'),
    'shotgun':   ('shotgun',  'range_shotgun'),
    'mp5':       ('smg1',     'range_smg1'),
    'rifle':     ('ar2',      'range_ar2'),
    'm249':      ('ar2',      'range_ar2'),
    'gauss':     ('physgun',  'range_physgun'),
    'tau':       ('physgun',  'range_physgun'),
    'egon':      ('physgun',  'range_physgun'),
    'hive':      ('ar2',      'range_ar2'),
    'rpg':       ('gmod:rpg', 'range_rpg'),       # the pack's RPG hold is its knife stance
    'bow':       ('crossbow', 'range_crossbow'),
    'squeak':    ('grenade',  'range_grenade'),
    'penguin':   ('grenade',  'range_grenade'),
    'grenade':   ('grenade',  'range_grenade'),
}
# gait label -> (CS 1.6 sequence, move grid cell or None)
GAITS = {
    'walk':        ('walk_all', (1, 0)),
    'walk2handed': ('walk_all', (1, 0)),
    'run':         ('run_all_01', (1, 0)),
    'run2':        ('run_all_01', (1, 0)),
    'crawl':       ('cwalk_all', (1, 0)),
    'crouch_idle': ('cidle_all', None),
    'deep_idle':   ('idle_all_01', None),
}


def cs16(M, ref, pack):
    g = SourceModel(pack, pack[:-4] + '.ani')
    rt = PackRetargeter(g, M, ref)
    rref = PackRetargeter(ref, M, ref)
    P, Pref = Pose(g), Pose(ref)
    seqs = [s for s in existing_sequences(M) if not s['label'].startswith(PREFIX)]
    by = {s['label']: s for s in seqs}
    added = []

    # gaits ------------------------------------------------------------
    for label, (name, cell) in GAITS.items():
        if label not in by:
            continue
        sq = g.seq_by_name[name]
        a = P.grid_anim(sq, cell)
        n = a['numframes']
        fr = np.array([rt.pose(*P(name, i / max(1, n - 1), cell)) for i in range(n)])
        s = clone(by[label], PREFIX + label)
        s['frames'] = [fr]
        s['fps'] = a['fps']
        if cell is not None:
            dist = movement_distance(g, a)
            if dist > 1.0:
                s['linearmovement'] = [dist * rt.scale, 0.0, 0.0]
        s['flags'] |= 1
        added.append(s)
    print('gaits done', flush=True)

    # weapon holds -----------------------------------------------------
    for ext, (hold, rng) in HOLD.items():
        if hold.startswith('gmod:'):
            gg, PP, RR, hold = ref, Pref, rref, hold[5:]
        else:
            gg, PP, RR = g, P, rt
        for crouch in (False, True):
            idle = ('cidle_' if crouch else 'idle_') + hold
            if idle not in gg.seq_by_name:
                idle = ('cidle_' if crouch else 'idle_') + 'ar2'
            a = PP.grid_anim(gg.seq_by_name[idle], None)
            n = a['numframes']
            step = IDLE_STEP if n > 120 else 1
            nn = (n - 1) // step + 1
            # the attack gesture: the pack's if it's a plain delta, else Garry's Mod's
            src, rs = g, g.seq_by_name.get(rng)
            if gg is ref or rs is None or not (g.anims[rs['anims'][0]]['flags'] & ANIM_DELTA) or rs['numautolayers']:
                src, rs = ref, ref.seq_by_name.get(rng) or ref.seq_by_name['range_ar2']
            ra = src.anims[rs['anims'][0]]
            rpost = bool(rs['flags'] & SEQ_POST)
            rframes = src.frames(ra)
            if src is not gg:               # Garry's Mod's bone order -> the pack's
                idx = [src.bone_by_name.get(b['name']) for b in gg.bones]

                def remap(d):
                    pos = np.zeros((len(idx), 3)); q = np.zeros((len(idx), 4)); q[:, 3] = 1
                    for i, j in enumerate(idx):
                        if j is not None:
                            pos[i] = d[0][j]; q[i] = d[1][j]
                    return pos, q
                rframes = [remap(d) for d in rframes]
            for kind in ('aim', 'shoot'):
                label = ('crouch_' if crouch else 'ref_') + kind + '_' + ext
                if label not in by:
                    continue
                s = clone(by[label], PREFIX + label)
                blends = []
                for v in (s['blendstart'][0], s['blendend'][0]):
                    if kind == 'aim':
                        blends.append(np.array([RR.pose(*PP(idle, i * step / max(1, n - 1), pitch=-v)) for i in range(nn)]))
                    else:
                        base = PP(idle, 0.0, pitch=-v)
                        blends.append(np.array([RR.pose(*apply_delta(base, d, post=rpost)) for d in rframes]))
                s['frames'] = blends
                s['fps'] = a['fps'] / step if kind == 'aim' else ra['fps']
                added.append(s)
        print('hold', ext, 'done', flush=True)
    return seqs + added, len(added)


def main(pack, freeman, in_path, out_path):
    freeman = freeman.rstrip('/') + '/'
    M = GoldSrcModel(in_path)
    ref = SourceModel(freeman + 'm_anm_gmod.mdl', freeman + 'm_anm.ani')
    seqs, n = cs16(M, ref, pack)
    M.write(out_path, seqs)
    textures_last(out_path)
    print('wrote', out_path, 'added', n, 'sequences, total', len(seqs))


if __name__ == '__main__':
    main(*sys.argv[1:5])
