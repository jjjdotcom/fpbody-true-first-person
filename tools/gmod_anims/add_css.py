"""Counter-Strike: Source player animations on an fpbody GMod-mode player model.

  python3 -I add_css.py <cs_player_shared.mdl> <Freeman models folder> <in.mdl> <out.mdl>

cs_player_shared.mdl (cstrike_pak_dir.vpk, models/player/) holds every CS:S
player animation. They are layered: a whole-body lower animation (Idle_lower,
Crouch_Idle_Lower), an upper-body hold per weapon (Idle_Upper_<W>) with its own
auto-layers - a body offset (delta), the aim matrix (3x3 delta grid on body_yaw /
body_pitch) and the hand positions - plus shoot gestures (deltas) and reload
layers (absolute, upper body) played over the hold.

This evaluates those layers, retargets (ValveBiped -> Bip01, like add_l4d.py)
and replaces, for the weapons Counter-Strike has a hold for:

  ref_aim_ / ref_shoot_ / crouch_aim_ / crouch_shoot_<ext>
                                    the hold, with the aim pitch blends
and adds css_reload_<kind> (pistol, smg, rifle, sniper, m249, shotgun_start /
_loop / _end) for the client to play on reloads (cl_fpbody_reloadset css).

Weapons Counter-Strike has nothing like (Tau, Gluon, RPG, Hivehand, ...) keep
the holds they have. The result contains Valve's animation data: keep it local.
"""
import struct
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from srcmdl import SourceModel                               # noqa: E402
from goldsrc import GoldSrcModel                             # noqa: E402
from add_cz import existing_sequences, textures_last         # noqa: E402
from add_freeman import PackRetargeter, make_seq             # noqa: E402
from add_l4d import Pose, ANIM_DELTA, SEQ_WORLD, SEQ_POST    # noqa: E402
from retarget import apply_delta, blend_pose                 # noqa: E402

# fpbody weapon extension -> Counter-Strike: Source weapon
HOLD = {
    'crowbar':   'KNIFE',
    'knife':     'KNIFE',
    'trip':      'C4',
    'c4':        'C4',
    'onehanded': 'PISTOL',
    'python':    'PISTOL',
    'shotgun':   'M3S90',
    'mp5':       'MP5',
    'rifle':     'MP5',          # Half-Life's MP5 deploys with "rifle"
    'm249':      'M249',
    'bow':       'SCOUT',
    'squeak':    'GREN',
    'penguin':   'GREN',
    'grenade':   'GREN',
}
# shoot gesture per weapon (the grenade's is a throw)
SHOOT = {'GREN': 'Shoot_GREN1', 'PISTOL': 'Shoot_Pistol'}
# css_reload_<kind> -> CS:S reload sequence (standing)
RELOADS = {
    'css_reload_pistol':        ('Idle_Reload_PISTOL', 'PISTOL', False),
    'css_reload_smg':           ('Idle_Reload_MP5', 'MP5', False),
    'css_reload_rifle':         ('Idle_Reload_M4', 'M4', False),
    'css_reload_sniper':        ('Idle_Reload_SCOUT', 'SCOUT', False),
    'css_reload_m249':          ('Idle_Reload_M249', 'M249', False),
    'css_reload_shotgun_start': ('idle_reload_M3S90_start', 'M3S90', False),
    'css_reload_shotgun_loop':  ('idle_reload_M3S90_loop', 'M3S90', True),
    'css_reload_shotgun_end':   ('idle_reload_M3S90_end', 'M3S90', False),
}
IDLE_STEP = 2


class CSSPose(Pose):
    """Pose with Counter-Strike's layering: lower body + upper hold + its layers."""

    def aim_delta(self, sq, pitch, c):
        g = self.g
        gx, gy = sq['groupsize']
        names = [g.poseparams[i]['name'] if i >= 0 else '' for i in sq['paramindex']]
        pi = names.index('body_pitch') if 'body_pitch' in names else 1
        s0, s1 = sq['paramstart'][pi], sq['paramend'][pi]
        t = (min(max(pitch, min(s0, s1)), max(s0, s1)) - s0) / (s1 - s0) if s1 != s0 else 0.5
        if pi == 1:                         # rows: pitch, columns: yaw (middle = 0)
            r = t * (gy - 1); r0 = int(np.floor(r)); r1 = min(gy - 1, r0 + 1); f = r - r0
            col = gx // 2
            a0 = g.anims[sq['anims'][r0 * gx + col]]; a1 = g.anims[sq['anims'][r1 * gx + col]]
        else:
            r = t * (gx - 1); r0 = int(np.floor(r)); r1 = min(gx - 1, r0 + 1); f = r - r0
            row = gy // 2
            a0 = g.anims[sq['anims'][row * gx + r0]]; a1 = g.anims[sq['anims'][row * gx + r1]]
        return blend_pose(self.anim_frame(a0, c), self.anim_frame(a1, c), f)

    def layer(self, pose, name, c, pitch, loop=True):
        """Put sequence `name` (and its auto-layers) over pose."""
        g = self.g
        sq = g.seq_by_name[name.lower()]
        gx, gy = sq['groupsize']
        if sq['anims'] and any(w > 0 for w in sq['weights']):
            a = g.anims[sq['anims'][0]]
            post = bool(sq['flags'] & SEQ_POST)
            if (gx, gy) != (1, 1) and a['flags'] & ANIM_DELTA:
                pose = apply_delta(pose, self.aim_delta(sq, pitch, c), post=post)
            else:
                lp = self.anim_frame(a, c, loop)
                w = sq['weights']
                if a['flags'] & ANIM_DELTA:
                    pose = self.delta_weighted(pose, lp, w, post)
                elif sq['flags'] & SEQ_WORLD:
                    pose = self.weighted_world(pose, lp, w)
                else:
                    pose = self.weighted_local(pose, lp, w)
        for k in range(sq['numautolayers']):
            o = sq['off'] + sq['autolayerindex'] + k * 24
            iseq = struct.unpack_from('<h', g.d, o)[0]
            pose = self.layer(pose, g.seqs[iseq]['name'], c, pitch, loop)
        return pose

    def hold(self, wpn, crouch, c, pitch):
        g = self.g
        lower = 'Crouch_Idle_Lower' if crouch else 'Idle_lower'
        a = g.anims[g.seq_by_name[lower.lower()]['anims'][0]]
        p = self.anim_frame(a, c, True)
        pose = (p[0].copy(), p[1].copy())
        upper = ('Crouch_Idle_Upper_' if crouch else 'Idle_Upper_') + wpn
        return self.layer(pose, upper, c, pitch)


def css(M, ref, path, seqs, by):
    g = SourceModel(path)
    rt = PackRetargeter(g, M, ref)
    P = CSSPose(g)

    def nframes(name):
        sq = g.seq_by_name[name.lower()]
        a = g.anims[sq['anims'][0]]
        return a['numframes'], a['fps']

    for ext, wpn in HOLD.items():
        for crouch in (False, True):
            upper = ('Crouch_Idle_Upper_' if crouch else 'Idle_Upper_') + wpn
            if upper.lower() not in g.seq_by_name:
                continue
            n, fps = nframes(upper)
            n = max(n, nframes('Crouch_Idle_Lower' if crouch else 'Idle_lower')[0])
            nn = (n - 1) // IDLE_STEP + 1
            shoot = ('Crouch_Idle_' if crouch else 'Idle_') + SHOOT.get(wpn, 'Shoot_' + wpn)
            if shoot.lower() not in g.seq_by_name:
                shoot = 'Idle_' + SHOOT.get(wpn, 'Shoot_' + wpn)
            sn, sfps = nframes(shoot)
            for kind in ('aim', 'shoot'):
                label = ('crouch_' if crouch else 'ref_') + kind + '_' + ext
                if label not in by:
                    continue
                s = by[label]
                blends = []
                for v in (s['blendstart'][0], s['blendend'][0]):
                    if kind == 'aim':
                        blends.append(np.array([rt.pose(*P.hold(wpn, crouch, i / max(1, nn - 1), -v))
                                                for i in range(nn)]))
                    else:
                        blends.append(np.array([rt.pose(*P.layer(P.hold(wpn, crouch, 0.0, -v), shoot,
                                                                 i / max(1, sn - 1), -v, loop=False))
                                                for i in range(sn)]))
                s['frames'] = blends
                s['fps'] = fps / IDLE_STEP if kind == 'aim' else sfps
        print('hold', ext, wpn, 'done', flush=True)

    template = by.get('look_idle') or seqs[0]
    seqs[:] = [s for s in seqs if not s['label'].startswith('css_reload_')]
    for label, (name, wpn, loop) in RELOADS.items():
        if name.lower() not in g.seq_by_name:
            continue
        n, fps = nframes(name)
        fr = np.array([rt.pose(*P.layer(P.hold(wpn, False, 0.0, 0.0), name, i / max(1, n - 1), 0.0, loop=loop))
                       for i in range(n)])
        seqs.append(make_seq(label, fr, fps, loop, template))
        by[label] = seqs[-1]
    print('reloads done', flush=True)


def main(path, freeman, in_path, out_path):
    freeman = freeman.rstrip('/') + '/'
    M = GoldSrcModel(in_path)
    ref = SourceModel(freeman + 'm_anm_gmod.mdl', freeman + 'm_anm.ani')
    seqs = existing_sequences(M)
    by = {s['label']: s for s in seqs}
    css(M, ref, path, seqs, by)
    M.write(out_path, seqs)
    textures_last(out_path)
    return len(seqs), M.downsampled


if __name__ == '__main__':
    print(main(*sys.argv[1:5]))
