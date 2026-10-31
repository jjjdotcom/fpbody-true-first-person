"""Left 4 Dead player animations on an fpbody GMod-mode player model.

  python3 -I add_l4d.py <l4d m_anm_slot_046.mdl | -> <Freeman models folder> <in.mdl> <out.mdl> [bo3animations.mdl]

The [xdR] Left 4 Dead animation pack (Workshop 2411672781) replaces Garry's
Mod's player animations with the survivors' (same sequence names: idle_ar2,
run_smg1, cwalk_pistol ...). Its sequences are layered like Left 4 Dead's: a
body animation, a world-space upper-body layer, an arms layer, the aim matrix
(a 3x4 grid of deltas driven by aim_yaw / aim_pitch) and an idle-noise delta.
This evaluates those layers (see Pose below), retargets the result
(ValveBiped -> Bip01, like add_freeman.py) and replaces, by name:

  walk, walk2handed, run, run2, crawl, crouch_idle, jump, long_jump, swim,
  treadwater                                     the gaits and whole-body moves
  ref_aim_ / ref_shoot_ / crouch_aim_ / crouch_shoot_<ext>
                                                 every weapon hold, with the aim
                                                 pitch blends from the aim matrix

Attack gestures the pack doesn't have as a simple delta come from Garry's
Mod's own animations (m_anm_gmod.mdl in the Freeman folder). Everything else
(fm_ / fa_ moves, deaths, the empty-hands idle) is kept.

With the BO3 sprint pack (Workshop 3807533640, bo3animations.mdl) it also adds
fm_sprint_<type> loops (smg, rifle, pistol, lmg, launcher, grenade, melee,
hold, and unarmed - Garry's Mod's run) for the sprint (cl_dll/fpbody_anim.cpp). With - instead of the L4D
pack only the sprints are added (Half-Life's classic animation models).

The result contains third-party animation data: keep it local.
"""
import math
import struct
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from srcmdl import SourceModel, quat_to_mat, quat_slerp      # noqa: E402
from goldsrc import GoldSrcModel                             # noqa: E402
from add_cz import existing_sequences, textures_last         # noqa: E402
from add_freeman import PackRetargeter, STAND, make_seq      # noqa: E402
from retarget import apply_delta, blend_pose                 # noqa: E402

SEQ_WORLD = 0x4000
SEQ_POST = 0x10
ANIM_DELTA = 0x4

# fpbody weapon extension -> (L4D hold, attack gesture)
HOLD = {
    'crowbar':   ('melee',    'range_melee'),
    'knife':     ('knife',    'range_knife'),
    'trip':      ('slam',     'range_slam'),
    'c4':        ('slam',     'range_slam'),
    'onehanded': ('revolver', 'range_pistol'),
    'python':    ('revolver', 'range_revolver'),
    'shotgun':   ('shotgun',  'range_shotgun'),
    'gauss':     ('ar2',      'range_ar2'),
    'tau':       ('ar2',      'range_ar2'),
    'mp5':       ('smg1',     'range_smg1'),
    'm249':      ('ar2',      'range_ar2'),
    'rpg':       ('rpg',      'range_rpg'),
    'egon':      ('ar2',      'range_ar2'),
    'hive':      ('ar2',      'range_ar2'),
    'bow':       ('crossbow', 'range_crossbow'),
    'rifle':     ('crossbow', 'range_crossbow'),
    'squeak':    ('grenade',  'range_grenade'),
    'penguin':   ('grenade',  'range_grenade'),
    'grenade':   ('grenade',  'range_grenade'),
}
# gait label -> (L4D sequence, move grid cell or None, loop). Left 4 Dead's
# empty-handed ("passive") cycles carry a rifle, and unarmed in first person
# the gaits drive the whole body, so they stay Garry's Mod's (arms swinging):
# set USE_L4D_GAITS to use them anyway.
USE_L4D_GAITS = False
GAITS = {
    'walk':        ('walk_passive', (1, 0), True),
    'walk2handed': ('walk_passive', (1, 0), True),
    'run':         ('run_passive', (1, 0), True),
    'run2':        ('run_passive', (1, 0), True),
    'crawl':       ('cwalk_passive', (1, 0), True),
    'crouch_idle': ('cidle_passive', None, True),
    'jump':        ('jump_smg1', (1, 0), False),
    'long_jump':   ('jump_passive', (1, 0), False),
    'swim':        ('swimming_passive', (1, 0), True),
    'treadwater':  ('swim_idle_passive', None, True),
}
SPRINT = {'smg': 'bo3_sprint_smg', 'rifle': 'bo3_sprint_rifle', 'pistol': 'bo3_sprint_pistol',
          'lmg': 'bo3_sprint_lmg', 'launcher': 'bo3_sprint_launcher', 'grenade': 'bo3_sprint_grenade',
          'melee': 'bo3_sprint_sword', 'hold': 'bo3_sprint_hold'}
IDLE_STEP = 3                        # long idles: every 3rd frame


def mat_to_quat(m):
    t = m[0, 0] + m[1, 1] + m[2, 2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        q = [(m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s, 0.25 * s]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        q = [0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s, (m[2, 1] - m[1, 2]) / s]
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        q = [(m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s, (m[0, 2] - m[2, 0]) / s]
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        q = [(m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s, (m[1, 0] - m[0, 1]) / s]
    q = np.array(q)
    return q / np.linalg.norm(q)


class Pose:
    """Evaluates a layered Source sequence (body + auto-layers) at one cycle."""

    def __init__(self, g):
        self.g = g
        self.cache = {}

    def autolayers(self, sq):
        g = self.g
        out = []
        for k in range(sq['numautolayers']):
            o = sq['off'] + sq['autolayerindex'] + k * 24
            iseq, ipose, flags, st, pk, tl, en = struct.unpack_from('<hhiffff', g.d, o)
            out.append((g.seqs[iseq], flags))
        return out

    def anim_frame(self, a, c, loop=True):
        n = a['numframes']
        f = int(round((c % 1.0 if loop else min(1.0, max(0.0, c))) * (n - 1))) if n > 1 else 0
        key = (a['index'], f)
        if key not in self.cache:
            self.cache[key] = self.g.frame_pose(a, f)
        return self.cache[key]

    def grid_anim(self, sq, cell):
        gx, gy = sq['groupsize']
        if cell is None:
            cell = (gx // 2, gy // 2)
        return self.g.anims[sq['anims'][cell[1] * gx + cell[0]]]

    def aim_delta(self, sq, pitch, c):
        """The aim matrix at yaw 0 and a Source pitch (+ = down)."""
        g = self.g
        gx, gy = sq['groupsize']
        pi = 1 if sq['paramindex'][1] >= 0 and g.poseparams[sq['paramindex'][1]]['name'] == 'aim_pitch' else 0
        s0, s1 = sq['paramstart'][pi], sq['paramend'][pi]
        t = (min(max(pitch, min(s0, s1)), max(s0, s1)) - s0) / (s1 - s0) if s1 != s0 else 0.0
        if pi == 1:
            r = t * (gy - 1)
            r0 = int(math.floor(r)); r1 = min(gy - 1, r0 + 1); f = r - r0
            col = gx // 2
            a0 = g.anims[sq['anims'][r0 * gx + col]]; a1 = g.anims[sq['anims'][r1 * gx + col]]
        else:
            r = t * (gx - 1)
            r0 = int(math.floor(r)); r1 = min(gx - 1, r0 + 1); f = r - r0
            row = gy // 2
            a0 = g.anims[sq['anims'][row * gx + r0]]; a1 = g.anims[sq['anims'][row * gx + r1]]
        return blend_pose(self.anim_frame(a0, c), self.anim_frame(a1, c), f)

    def weighted_local(self, pose, layer, w):
        pos, q = pose
        lpos, lq = layer
        pos = pos.copy(); q = q.copy()
        for i, wi in enumerate(w):
            if wi <= 0:
                continue
            pos[i] = pos[i] * (1 - wi) + lpos[i] * wi
            q[i] = quat_slerp(q[i], lq[i], wi)
        return pos, q

    def weighted_world(self, pose, layer, w):
        """Blend bone world rotations toward the layer's (Source's STUDIO_WORLD)."""
        g = self.g
        pos, q = pose
        Rc, _ = g.world(pos, q)
        Rl, _ = g.world(*layer)
        q = q.copy(); pos = pos.copy()
        Rn = np.zeros_like(Rc)
        for i, b in enumerate(g.bones):
            p = b['parent']
            PR = Rn[p] if p >= 0 else np.eye(3)
            wi = w[i]
            if wi > 0:
                Rt = quat_to_mat(quat_slerp(mat_to_quat(Rc[i]), mat_to_quat(Rl[i]), wi))
                q[i] = mat_to_quat(PR.T @ Rt)
                pos[i] = pos[i] * (1 - wi) + layer[0][i] * wi
            Rn[i] = PR @ quat_to_mat(q[i])
        return pos, q

    def delta_weighted(self, pose, d, w, post):
        if all(x >= 0.999 for x in w) or not any(x > 0 for x in w):
            return apply_delta(pose, d, post=post) if any(x > 0 for x in w) else pose
        out_pos, out_q = pose[0].copy(), pose[1].copy()
        full = apply_delta(pose, d, post=post)
        for i, wi in enumerate(w):
            if wi > 0:
                out_pos[i] = pose[0][i] * (1 - wi) + full[0][i] * wi
                out_q[i] = quat_slerp(pose[1][i], full[1][i], wi)
        return out_pos, out_q

    def __call__(self, name, c, cell=None, pitch=0.0, layers=True):
        g = self.g
        sq = g.seq_by_name[name.lower()]
        loop = bool(sq['flags'] & 1)
        pose = self.anim_frame(self.grid_anim(sq, cell), c, loop)
        pose = (pose[0].copy(), pose[1].copy())
        if not layers:
            return pose
        for ls, flags in self.autolayers(sq):
            if not ls['anims']:
                continue
            post = bool(ls['flags'] & SEQ_POST)
            gx, gy = ls['groupsize']
            a = g.anims[ls['anims'][0]]
            if (gx, gy) != (1, 1) and a['flags'] & ANIM_DELTA and ls['paramindex'][0] >= 0 and \
                    g.poseparams[ls['paramindex'][0]]['name'].startswith('aim'):
                pose = apply_delta(pose, self.aim_delta(ls, pitch, c), post=post)
                continue
            if (gx, gy) != (1, 1):
                a = self.grid_anim(ls, cell)
            lp = self.anim_frame(a, c, bool(ls['flags'] & 1) or loop)
            w = ls['weights']
            if a['flags'] & ANIM_DELTA:
                pose = self.delta_weighted(pose, lp, w, post)
            elif ls['flags'] & SEQ_WORLD:
                pose = self.weighted_world(pose, lp, w)
            else:
                pose = self.weighted_local(pose, lp, w)
        return pose


def movement_distance(g, a):
    """Forward distance one cycle of animation a covers (its movement blocks)."""
    total = np.zeros(3)
    for k in range(a.get('nummovements', 0) or 0):
        o = a['off'] + a['movementindex'] + k * 44
        pos = struct.unpack_from('<3f', g.d, o + 32)
        total += pos
    return float(np.linalg.norm(total[:2]))


def l4d(M, ref, l4d_path, seqs, by):
    """Replace the gaits and weapon holds with the Left 4 Dead ones (in place)."""
    g = SourceModel(l4d_path, l4d_path[:-4] + '.ani')
    rt = PackRetargeter(g, M, ref)
    rref = PackRetargeter(ref, M, ref)
    P = Pose(g)

    def frames(fn, n):
        return np.array([rt.pose(*fn(i / max(1, n - 1) if n > 1 else 0.0)) for i in range(n)])

    # gaits ------------------------------------------------------------
    for label, (name, cell, loop) in (GAITS.items() if USE_L4D_GAITS else ()):
        if label not in by:
            continue
        sq = g.seq_by_name[name]
        a = P.grid_anim(sq, cell)
        n = a['numframes']
        step = IDLE_STEP if n > 120 else 1
        nn = (n - 1) // step + 1
        fr = frames(lambda c: P(name, c, cell), nn)
        s = by[label]
        s['frames'] = [fr]
        s['fps'] = a['fps'] / step
        if label in ('walk', 'walk2handed', 'run', 'run2', 'crawl', 'swim'):
            dist = movement_distance(g, a)
            if dist > 1.0:
                s['linearmovement'] = [dist * rt.scale, 0.0, 0.0]
        s['flags'] = (s['flags'] | 1) if loop else (s['flags'] & ~1)
    print('gaits done', flush=True)

    # weapon holds -----------------------------------------------------
    for ext, (hold, rng) in HOLD.items():
        for crouch in (False, True):
            idle = ('cidle_' if crouch else 'idle_') + hold
            if idle not in g.seq_by_name:
                idle = ('cidle_' if crouch else 'idle_') + 'ar2'
            a = P.grid_anim(g.seq_by_name[idle], None)
            n = a['numframes']
            step = IDLE_STEP if n > 120 else 1
            nn = (n - 1) // step + 1
            # the attack gesture: Left 4 Dead's if it's a plain delta, else Garry's Mod's
            src, rs = g, g.seq_by_name.get(rng)
            if rs is None or not (g.anims[rs['anims'][0]]['flags'] & ANIM_DELTA) or rs['numautolayers']:
                src, rs = ref, ref.seq_by_name.get(rng) or ref.seq_by_name['range_ar2']
            ra = src.anims[rs['anims'][0]]
            rpost = bool(rs['flags'] & SEQ_POST)
            rframes = src.frames(ra)
            if src is not g:                # Garry's Mod's bone order -> the pack's
                idx = [src.bone_by_name.get(b['name']) for b in g.bones]

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
                s = by[label]
                blends = []
                for v in (s['blendstart'][0], s['blendend'][0]):
                    if kind == 'aim':
                        blends.append(frames(lambda c: P(idle, c, pitch=-v), nn))
                    else:
                        base = P(idle, 0.0, pitch=-v)
                        blends.append(np.array([rt.pose(*apply_delta(base, d, post=rpost)) for d in rframes]))
                s['frames'] = blends
                s['fps'] = a['fps'] / step if kind == 'aim' else ra['fps']
        print('hold', ext, 'done', flush=True)



def main(l4d_path, freeman, in_path, out_path, bo3=None):
    freeman = freeman.rstrip('/') + '/'
    M = GoldSrcModel(in_path)
    ref = SourceModel(freeman + 'm_anm_gmod.mdl', freeman + 'm_anm.ani')
    seqs = existing_sequences(M)
    by = {s['label']: s for s in seqs}
    if l4d_path != '-':
        l4d(M, ref, l4d_path, seqs, by)

    # empty hands standing still: unarmed, the gait drives the whole body, so the
    # idle gaits are the empty-hands idle (the COD IW idle, see add_freeman.py)
    if l4d_path != '-' and 'ref_aim_unarmed' in by:
        idle = by['ref_aim_unarmed']
        for label in ('deep_idle', 'idle', 'look_idle'):
            if label in by:
                by[label]['frames'] = [idle['frames'][0].copy()]
                by[label]['fps'] = idle['fps']
                by[label]['flags'] |= 1

    # At Ease with a pistol (the Freeman mod): relaxed hands - the empty-hands idle,
    # walk and run, played on the upper body (fm_relax_*)
    seqs = [s for s in seqs if not s['label'].startswith('fm_relax_')]
    by = {s['label']: s for s in seqs}
    template = by.get('look_idle') or seqs[0]
    for label, src in (('fm_relax_idle', 'ref_aim_unarmed'), ('fm_relax_walk', 'walk'), ('fm_relax_run', 'run2')):
        if src in by:
            seqs.append(make_seq(label, by[src]['frames'][0].copy(), by[src]['fps'], True, template))

    # sprints ----------------------------------------------------------
    out = [s for s in seqs if not s['label'].startswith('fm_sprint_')]
    if bo3 and bo3 != '-':
        b = SourceModel(bo3)
        rb = PackRetargeter(b, M, ref)
        template = by.get('look_idle') or seqs[0]
        for kind, name in SPRINT.items():
            sq = b.seq_by_name[name]
            a = b.anims[sq['anims'][0]]
            fr = np.array([rb.pose(*p) for p in b.frames(a)])
            seq = make_seq('fm_sprint_' + kind, fr, a['fps'], True, template)
            out.append(seq)
        # empty hands: Garry's Mod's run (arms swinging)
        rr = PackRetargeter(ref, M, ref)
        a = ref.anim_by_name['a_RunN']
        fr = np.array([rr.pose(*p) for p in ref.frames(a)])
        out.append(make_seq('fm_sprint_unarmed', fr, a['fps'], True, template))
        print('sprints done', flush=True)
    M.write(out_path, out)
    textures_last(out_path)
    return len(out), M.downsampled


if __name__ == '__main__':
    print(main(*sys.argv[1:6]))
