"""Retarget ValveBiped (GMod/Source) poses onto Half-Life's Bip01 skeleton.

World-space transfer with rest-pose direction correction:
    W_target(b) = D(b) * C(b) * Rrest_target(b)
    D(b)        = W_source(b') * Rrest_source(b')^-1     (source motion)
    C(b)        = minimal rotation taking the target rest bone direction to
                  the source rest bone direction (fixes T-pose vs A-pose etc.)
Bone lengths stay the target's; only the root moves.
"""
import math

import numpy as np

from srcmdl import quat_to_mat, quat_mul, quat_slerp
from goldsrc import mat_to_euler, unwrap_near

VB = 'ValveBiped.Bip01_'

MAP = [
    ('Bip01 Pelvis', 'Pelvis'),
    ('Bip01 Spine', 'Spine'), ('Bip01 Spine1', 'Spine1'), ('Bip01 Spine2', 'Spine2'),
    ('Bip01 Spine3', 'Spine4'), ('Bip01 Neck', 'Neck1'), ('Bip01 Head', 'Head1'),
]
for side in 'LR':
    MAP += [
        ('Bip01 %s Arm' % side, '%s_Clavicle' % side),
        ('Bip01 %s Arm1' % side, '%s_UpperArm' % side),
        ('Bip01 %s Arm2' % side, '%s_Forearm' % side),
        ('Bip01 %s Hand' % side, '%s_Hand' % side),
        ('Bip01 %s Finger0' % side, '%s_Finger0' % side),
        ('Bip01 %s Finger01' % side, '%s_Finger01' % side),
        ('Bip01 %s Finger02' % side, '%s_Finger02' % side),
        ('Bip01 %s Finger1' % side, '%s_Finger2' % side),
        ('Bip01 %s Finger11' % side, '%s_Finger21' % side),
        ('Bip01 %s Finger12' % side, '%s_Finger22' % side),
        ('Bip01 %s Leg' % side, '%s_Thigh' % side),
        ('Bip01 %s Leg1' % side, '%s_Calf' % side),
        ('Bip01 %s Foot' % side, '%s_Foot' % side),
        ('Bip01 %s Toe0' % side, '%s_Toe0' % side),
    ]

# child used to define each bone's direction (target names)
DIR_CHILD = {
    'Bip01 Pelvis': 'Bip01 Spine', 'Bip01 Spine': 'Bip01 Spine1', 'Bip01 Spine1': 'Bip01 Spine2',
    'Bip01 Spine2': 'Bip01 Spine3', 'Bip01 Spine3': 'Bip01 Neck', 'Bip01 Neck': 'Bip01 Head',
}
for side in 'LR':
    s = 'Bip01 %s ' % side
    DIR_CHILD.update({
        s + 'Arm': s + 'Arm1', s + 'Arm1': s + 'Arm2', s + 'Arm2': s + 'Hand', s + 'Hand': s + 'Finger1',
        s + 'Finger0': s + 'Finger01', s + 'Finger01': s + 'Finger02',
        s + 'Finger1': s + 'Finger11', s + 'Finger11': s + 'Finger12',
        s + 'Leg': s + 'Leg1', s + 'Leg1': s + 'Foot', s + 'Foot': s + 'Toe0',
    })

ZOFFSET = -36.0   # GMod origin is at the feet, Half-Life's at the hull centre


def rot_between(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    v = np.cross(a, b); c = float(np.dot(a, b)); s = np.linalg.norm(v)
    if s < 1e-8:
        if c > 0:
            return np.eye(3)
        # 180 degrees: any perpendicular axis
        p = np.cross(a, [1, 0, 0])
        if np.linalg.norm(p) < 1e-3:
            p = np.cross(a, [0, 1, 0])
        p /= np.linalg.norm(p)
        return 2 * np.outer(p, p) - np.eye(3)
    k = v / s
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    ang = math.atan2(s, c)
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * K @ K


class Retargeter:
    def __init__(self, src, tgt):
        self.src, self.tgt = src, tgt
        spos = np.array([b['pos'] for b in src.bones])
        squat = np.array([b['quat'] for b in src.bones])
        self.Rs0, self.Ts0 = src.world(spos, squat)
        self.trest = tgt.rest_local()
        self.Rt0, self.Tt0 = tgt.world(self.trest)

        self.pairs = []        # (target index, source index)
        self.src_of = {}
        for tn, sn in MAP:
            ti = tgt.bone_by_name[tn]; si = src.bone_by_name[VB + sn]
            self.pairs.append((ti, si)); self.src_of[ti] = si

        # direction corrections
        self.C = {}
        for tn, sn in MAP:
            ti = tgt.bone_by_name[tn]
            ch = DIR_CHILD.get(tn)
            if ch is None:
                parent = tgt.bones[ti]['parent']
                self.C[ti] = self.C.get(parent, np.eye(3))
                continue
            ci = tgt.bone_by_name[ch]
            dt = self.Tt0[ci] - self.Tt0[ti]
            dv = self.Ts0[self.src_of[ci]] - self.Ts0[self.src_of[ti]]
            self.C[ti] = rot_between(dt, dv)

        # height scale from pelvis-above-toes
        tp = self.Tt0[tgt.bone_by_name['Bip01 Pelvis']][2] - self.Tt0[tgt.bone_by_name['Bip01 L Toe0']][2]
        sp = self.Ts0[src.bone_by_name[VB + 'Pelvis']][2] - self.Ts0[src.bone_by_name[VB + 'L_Toe0']][2]
        self.scale = tp / sp
        self.root = tgt.bone_by_name['Bip01']
        self.pelvis_t = tgt.bone_by_name['Bip01 Pelvis']
        self.pelvis_s = src.bone_by_name[VB + 'Pelvis']

    def pose(self, spos, squat):
        """Source local pose -> target local [bones, 6] (pos, euler)."""
        Rs, Ts = self.src.world(spos, squat)
        tgt = self.tgt
        n = tgt.numbones
        W = np.zeros((n, 3, 3)); P = np.zeros((n, 3))
        out = np.zeros((n, 6))
        D = {}
        for ti, si in self.pairs:
            D[ti] = Rs[si] @ self.Rs0[si].T
        for i, b in enumerate(tgt.bones):
            p = b['parent']
            rest_local_R = quat_to_mat(_eq(self.trest[i, 3:6]))
            if i == self.root:
                W[i] = D[self.pelvis_t] @ self.Rt0[i]
                P[i] = Ts[self.pelvis_s] * self.scale + np.array([0, 0, ZOFFSET])
                localR = W[i]
                localP = P[i]
            else:
                localP = self.trest[i, :3]
                P[i] = W[p] @ localP + P[p]
                if i in D:
                    W[i] = D[i] @ self.C[i] @ self.Rt0[i]
                    localR = W[p].T @ W[i]
                else:
                    localR = rest_local_R
                    W[i] = W[p] @ localR
            e = mat_to_euler(localR)
            e = np.array([unwrap_near(e[j], self.trest[i, 3 + j]) for j in range(3)])
            out[i, :3] = localP
            out[i, 3:] = e
        return out


def _eq(e):
    from srcmdl import euler_to_quat
    return euler_to_quat(*e)


# ---------------------------------------------------------------- source pose helpers

def apply_delta(base, delta, w=1.0, post=True):
    """Add a delta layer like Source's SlerpBones: STUDIO_POST layers
    (aim layers, attack gestures) post-multiply, base * delta (QuaternionMA);
    other delta layers pre-multiply, delta * base (QuaternionSM)."""
    bpos, bq = base
    dpos, dq = delta
    pos = bpos + dpos * w
    q = np.zeros_like(bq)
    ident = np.array([0, 0, 0, 1.0])
    for i in range(len(bq)):
        d = quat_slerp(ident, dq[i], w) if w != 1.0 else dq[i]
        r = quat_mul(bq[i], d) if post else quat_mul(d, bq[i])
        q[i] = r / np.linalg.norm(r)
    return pos, q


def blend_pose(a, b, t):
    pos = a[0] * (1 - t) + b[0] * t
    q = np.array([quat_slerp(a[1][i], b[1][i], t) for i in range(len(a[1]))])
    return pos, q
