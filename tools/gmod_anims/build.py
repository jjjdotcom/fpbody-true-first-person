"""Build fpbody/models/player.mdl: Half-Life's player model with GMod
animations retargeted onto it.

  python3 -I build.py <hl player.mdl> <m_anm.mdl> <m_anm.ani> <out.mdl>
"""
import json
import sys
import time

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from srcmdl import SourceModel                      # noqa: E402
from goldsrc import GoldSrcModel                    # noqa: E402
from retarget import Retargeter, apply_delta, blend_pose  # noqa: E402

hl_path, mdl_path, ani_path, out_path = sys.argv[1:5]
g = SourceModel(mdl_path, ani_path)
h = GoldSrcModel(hl_path)
rt = Retargeter(g, h)
t0 = time.time()

LEG_BONES = set(range(h.bone_by_name['Bip01 Spine']))   # bones driven by gait sequences


# ------------------------------------------------------------ source helpers
def seq_anim(name, grid=None):
    s = g.seq_by_name[name.lower()]
    if grid is None:
        return g.anims[s['anims'][0]]
    gx, gy = s['groupsize']
    x, y = grid
    return g.anims[s['anims'][y * gx + x]]


def frames_of(a):
    return g.frames(a)


def retarget_frames(poses):
    return np.array([rt.pose(p, q) for p, q in poses])


def aim_delta(aimseq, src_pitch):
    """Delta pose for the aim layer at a Source pitch (+ = down), yaw centre."""
    s = g.seq_by_name[aimseq]
    gx = s['groupsize'][0]
    mid = g.frame_pose(g.anims[s['anims'][1 * gx + 1]], 0)
    if src_pitch >= 0:
        row, lim = 2, s['paramend'][1]
    else:
        row, lim = 0, s['paramstart'][1]
    edge = g.frame_pose(g.anims[s['anims'][row * gx + 1]], 0)
    t = min(1.0, max(0.0, src_pitch / lim)) if lim else 0.0
    return blend_pose(mid, edge, t)


def hl_seq(name):
    return h.seqs[h.seq_by_name[name]]


# ------------------------------------------------------------ sequences
out = []          # list of sequence dicts in final order
replaced = {}     # HL label -> new dict


def base_dict(label, fps, frames, raw=None, **kw):
    d = dict(label=label, fps=float(fps), frames=frames, raw=raw,
             flags=kw.pop('flags', 0), activity=kw.pop('activity', 0), actweight=kw.pop('actweight', 0))
    d.update(kw)
    return d


def replace(label, frames_list, fps, linear=None, loop=None):
    s = hl_seq(label)
    d = base_dict(label, fps, frames_list, raw=s['raw'], flags=s['flags'] if loop is None else (1 if loop else 0),
                  activity=s['activity'], actweight=s['actweight'], motiontype=s['motiontype'],
                  motionbone=s['motionbone'], blendtype=s['blendtype'], blendstart=s['blendstart'],
                  blendend=s['blendend'],
                  linearmovement=[linear, 0, 0] if linear is not None else s['linearmovement'])
    replaced[label] = d


# gaits (legs + pelvis) -------------------------------------------------
def gait(label, anim, distance=None):
    a = g.anim_by_name[anim] if isinstance(anim, str) else anim
    # whole body: the game also plays some of these as the main sequence
    # (deep_idle for ACT_IDLE), not only as the legs under another sequence
    fr = retarget_frames(frames_of(a))
    replace(label, [fr], a['fps'], linear=None if distance is None else distance * rt.scale)


gait('deep_idle', '@idle_all_01')
gait('walk2handed', 'a_WalkN', 80.0)
gait('run2', 'a_RunN', 125.9)
gait('crawl', 'a_CwalkN', 60.0)
gait('crouch_idle', '@cidle_all')
gait('walk', 'a_WalkN', 80.0)
gait('run', 'a_RunN', 125.9)
# upper body with no weapon: "ref_aim_" + "" doesn't exist, so the game falls
# back to sequence 0 (look_idle); ACT_IDLE picks look_idle / idle / deep_idle
gait('look_idle', '@idle_all_01')
gait('idle', '@idle_all_01')

# whole-body movement --------------------------------------------------
for label, src in [('swim', 'a_SwimN'), ('treadwater', '@swim_idle_all'),
                   ('jump', seq_anim('jump_smg1')['name']), ('long_jump', seq_anim('jump_passive')['name'])]:
    a = g.anim_by_name[src]
    replace(label, [retarget_frames(frames_of(a))], a['fps'])

# deaths ------------------------------------------------------------------
for label, src in [('die_simple', 'death_01'), ('die_backwards1', 'death_02'), ('die_backwards', 'death_03'),
                   ('die_forwards', 'death_04'), ('headshot', 'death_03'), ('die_spin', 'death_04'),
                   ('gutshot', 'death_01')]:
    a = seq_anim(src)
    replace(label, [retarget_frames(frames_of(a))], a['fps'])

# weapon poses ------------------------------------------------------------
HOLD = {
    'crowbar':   ('melee',    'range_melee',    'aimlayer_melee',    'aimlayer_melee'),
    'trip':      ('slam',     'range_slam',     'aimlayer_slam',     'aimlayer_slam_crouch'),
    'onehanded': ('revolver', 'range_pistol',   'aimlayer_revolver', 'aimlayer_revolver'),     # two-handed grip
    'python':    ('revolver', 'range_revolver', 'aimlayer_revolver', 'aimlayer_revolver'),
    'shotgun':   ('ar2',      'range_shotgun',  'aimlayer_ar2',      'aimlayer_ar2'),       # GMod's shotgun stance is hip-level
    'gauss':     ('ar2',      'range_ar2',      'aimlayer_ar2',      'aimlayer_ar2'),
    'mp5':       ('smg1',     'range_smg1',     'aimlayer_smg',      'aimlayer_smg'),
    'rpg':       ('rpg',      'range_rpg',      'aimlayer_rpg',      'aimlayer_rpg_crouch'),
    'egon':      ('ar2',      'range_ar2',      'aimlayer_ar2',      'aimlayer_ar2'),
    'squeak':    ('grenade',  'range_grenade',  'aimlayer_melee',    'aimlayer_melee'),
    'hive':      ('ar2',      'range_ar2',      'aimlayer_ar2',      'aimlayer_ar2'),
    'bow':       ('ar2',      'range_crossbow', 'aimlayer_ar2',      'aimlayer_ar2'),       # GMod's crossbow stance is hip-level
}

for ext, (hold, rng, aim, aimc) in HOLD.items():
    for crouch in (False, True):
        idle_a = seq_anim(('cidle_' if crouch else 'idle_') + hold)
        aimseq = aimc if crouch else aim
        idle_fr = frames_of(idle_a)
        range_a = seq_anim(rng)
        range_fr = frames_of(range_a)
        for kind in ('aim', 'shoot'):
            label = ('crouch_' if crouch else 'ref_') + kind + '_' + ext
            if label not in h.seq_by_name:
                continue
            s = hl_seq(label)
            blends = []
            for v in (s['blendstart'][0], s['blendend'][0]):
                delta = aim_delta(aimseq, -v)
                aim_post = bool(g.seq_by_name[aimseq]['flags'] & 0x10)
                rng_post = bool(g.seq_by_name[rng]['flags'] & 0x10)
                if kind == 'aim':
                    poses = [apply_delta(p, delta, post=aim_post) for p in idle_fr]
                else:
                    base = idle_fr[0]
                    poses = [apply_delta(apply_delta(base, rd, post=rng_post), delta, post=aim_post)
                             for rd in range_fr]
                blends.append(retarget_frames(poses))
            fps = idle_a['fps'] if kind == 'aim' else range_a['fps']
            replace(label, blends, fps)
    print('weapon', ext, 'done', round(time.time() - t0), 's', flush=True)

# extra GMod sequences (gestures, taunts, poses ...) ------------------------
UPPER_PREFIX = ('gesture_', 'reload_', 'range_melee_shove', 'zombie_attack_')
added = []


def add_extra(src_seq, label, upper):
    a = seq_anim(src_seq)
    if a['flags'] & 4:
        return
    fr = retarget_frames(frames_of(a))
    loop = bool(g.seq_by_name[src_seq]['flags'] & 1)
    out_label = 'gm_' + label
    added.append(dict(name=label, upper=upper, loop=loop))
    out.append(base_dict(out_label[:31], a['fps'], [fr], flags=1 if loop else 0))


for s in g.seqs:
    n = s['name'].lower()
    gx, gy = s['groupsize']
    if (gx, gy) != (1, 1):
        continue
    if n.endswith('_original'):
        stem = n[:-len('_original')]
        if stem.startswith(UPPER_PREFIX) or stem == 'taunt_zombie':
            add_extra(n, stem.replace('range_melee_shove', 'shove'), stem.startswith(UPPER_PREFIX))
    elif n.startswith('taunt_') and n.endswith('_base'):
        add_extra(n, n[:-len('_base')], False)
    elif n.startswith(('pose_', 'seq_', 'death_', 'drive_', 'menu_gman', 'menu_combine')) or \
            n in ('idle_all_02', 'idle_all_angry', 'idle_all_scared', 'idle_all_cower', 'sit', 'sit_zen',
                  'sit_rollercoaster', 'idle_suitcase', 'idle_melee_angry', 'zombie_idle_01',
                  'zombie_cidle_01', 'zombie_slump_idle_01', 'zombie_slump_rise_01', 'zombie_slump_idle_02',
                  'zombie_climb_start', 'zombie_climb_loop', 'zombie_climb_end', 'zombie_leap_start',
                  'zombie_leap_mid'):
        add_extra(n, n, False)

print('extras', len(added), round(time.time() - t0), 's', flush=True)

# ------------------------------------------------------------ assemble + write
final = []
for i, s in enumerate(h.seqs):
    if s['label'] in replaced:
        final.append(replaced[s['label']])
    else:
        final.append(base_dict(s['label'], s['fps'], h.decode(i), raw=s['raw'], flags=s['flags'],
                               activity=s['activity'], actweight=s['actweight'], motiontype=s['motiontype'],
                               motionbone=s['motionbone'], linearmovement=s['linearmovement'],
                               blendtype=s['blendtype'], blendstart=s['blendstart'], blendend=s['blendend']))
final += out
# Opposing Force's penguin uses the "penguin" animation extension, which the
# Half-Life player model doesn't have: hold it like the snark
import copy as _copy
for kind in ('ref_aim_', 'ref_shoot_', 'crouch_aim_', 'crouch_shoot_'):
    src = next(d for d in final if d['label'] == kind + 'squeak')
    dup = _copy.copy(src)
    dup['label'] = kind + 'penguin'
    if dup.get('raw'):
        raw = bytearray(dup['raw']); lab = dup['label'].encode()
        raw[0:32] = lab + bytes(32 - len(lab)); dup['raw'] = bytes(raw)
    final.append(dup)
size = h.write(out_path, final)
print('wrote', out_path, size, 'bytes,', len(final), 'sequences; replaced', len(replaced),
      'added', len(out), 'downsampled', h.downsampled, round(time.time() - t0), 's')
json.dump(added, open(out_path + '.acts.json', 'w'), indent=1)
