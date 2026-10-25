"""Minimal Source engine MDL (v44-49) reader for skeletons and animations.

Follows the layouts and decoding in the Source SDK 2013 (studio.h,
studio.cpp, bone_setup.cpp, compressed_vector.h).
"""
import math
import struct

import numpy as np


def cstr(d, o):
    e = d.index(b'\0', o)
    return d[o:e].decode('latin-1')


def half(h):
    return float(np.frombuffer(struct.pack('<H', h), dtype=np.float16)[0])


# ---------------------------------------------------------------- math

def euler_to_quat(x, y, z):
    """RadianEuler -> Quaternion (x, y, z, w), as mathlib AngleQuaternion."""
    sr, cr = math.sin(x * 0.5), math.cos(x * 0.5)
    sp, cp = math.sin(y * 0.5), math.cos(y * 0.5)
    sy, cy = math.sin(z * 0.5), math.cos(z * 0.5)
    srXcp, crXcp = sr * cp, cr * cp
    return np.array([
        srXcp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        crXcp * sy - sr * sp * cy,
        crXcp * cy + sr * sp * sy,
    ])


def quat_mul(p, q):
    """Hamilton product p*q (x, y, z, w)."""
    px, py, pz, pw = p
    qx, qy, qz, qw = q
    return np.array([
        pw * qx + px * qw + py * qz - pz * qy,
        pw * qy - px * qz + py * qw + pz * qx,
        pw * qz + px * qy - py * qx + pz * qw,
        pw * qw - px * qx - py * qy - pz * qz,
    ])


def quat_to_mat(q):
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


def quat_slerp(a, b, t):
    if np.dot(a, b) < 0:
        b = -b
    d = np.clip(np.dot(a, b), -1, 1)
    if d > 0.9995:
        r = a + (b - a) * t
        return r / np.linalg.norm(r)
    th = math.acos(d)
    return (math.sin((1 - t) * th) * a + math.sin(t * th) * b) / math.sin(th)


# ---------------------------------------------------------------- reader

class SourceModel:
    def __init__(self, mdl_path, ani_path=None):
        self.d = open(mdl_path, 'rb').read()
        self.ani = open(ani_path, 'rb').read() if ani_path else None
        d = self.d
        self.id, self.version = struct.unpack_from('<4si', d, 0)
        assert self.id == b'IDST', self.id
        self.name = cstr(d, 12)
        (self.numbones, self.boneindex) = struct.unpack_from('<ii', d, 156)
        (self.numanim, self.animindex) = struct.unpack_from('<ii', d, 180)
        (self.numseq, self.seqindex) = struct.unpack_from('<ii', d, 188)
        (self.numpose, self.poseindex) = struct.unpack_from('<ii', d, 300)
        (self.numincl, self.inclindex) = struct.unpack_from('<ii', d, 336)
        (self.animblocknameindex, self.numanimblocks, self.animblockindex) = struct.unpack_from('<iii', d, 348)
        self._read_bones()
        self._read_animdescs()
        self._read_poseparams()
        self._read_seqs()

    # bones -------------------------------------------------------------
    def _read_bones(self):
        d = self.d
        self.bones = []
        for i in range(self.numbones):
            o = self.boneindex + i * 216
            nameoff, parent = struct.unpack_from('<ii', d, o)
            pos = np.array(struct.unpack_from('<3f', d, o + 32))
            quat = np.array(struct.unpack_from('<4f', d, o + 44))
            rot = np.array(struct.unpack_from('<3f', d, o + 60))
            posscale = np.array(struct.unpack_from('<3f', d, o + 72))
            rotscale = np.array(struct.unpack_from('<3f', d, o + 84))
            flags = struct.unpack_from('<i', d, o + 160)[0]
            self.bones.append(dict(name=cstr(d, o + nameoff), parent=parent, pos=pos, quat=quat,
                                   rot=rot, posscale=posscale, rotscale=rotscale, flags=flags))
        self.bone_by_name = {b['name']: i for i, b in enumerate(self.bones)}

    def _read_poseparams(self):
        d = self.d
        self.poseparams = []
        for i in range(self.numpose):
            o = self.poseindex + i * 20
            nameoff, flags, start, end, loop = struct.unpack_from('<iifff', d, o)
            self.poseparams.append(dict(name=cstr(d, o + nameoff), start=start, end=end, loop=loop))

    # animations ----------------------------------------------------------
    def _read_animdescs(self):
        d = self.d
        self.anims = []
        for i in range(self.numanim):
            o = self.animindex + i * 100
            (baseptr, nameoff, fps, flags, numframes, nummov, movidx) = struct.unpack_from('<iifiiii', d, o)
            animblock, animidx, numik, ikidx, ablkikidx, numlh, lhidx, sectidx, sectframes = \
                struct.unpack_from('<9i', d, o + 52)
            self.anims.append(dict(index=i, off=o, name=cstr(d, o + nameoff), fps=fps, flags=flags,
                                   numframes=numframes, animblock=animblock, animindex=animidx,
                                   sectionindex=sectidx, sectionframes=sectframes,
                                   nummovements=nummov, movementindex=movidx))
        self.anim_by_name = {a['name']: a for a in self.anims}

    def _block_data(self, block, index, desc_off):
        """Returns (buffer, offset) of the first mstudioanim_t, or None."""
        if block == -1:
            return None
        if block == 0:
            return self.d, desc_off + index
        o = self.animblockindex + block * 8
        start, end = struct.unpack_from('<ii', self.d, o)
        return self.ani, start + index

    def _anim_ptr(self, a, frame):
        block, index, section = a['animblock'], a['animindex'], 0
        sf = a['sectionframes']
        if sf:
            if a['numframes'] > sf and frame == a['numframes'] - 1:
                frame = 0
                section = a['numframes'] // sf + 1
            else:
                section = frame // sf
                frame -= section * sf
            so = a['off'] + a['sectionindex'] + section * 8
            block, index = struct.unpack_from('<ii', self.d, so)
        r = self._block_data(block, index, a['off'])
        return r, frame

    @staticmethod
    def _extract(buf, o, frame, scale):
        """ExtractAnimValue (single value) at mstudioanimvalue_t* buf[o]."""
        k = frame
        while True:
            valid, total = buf[o], buf[o + 1]
            if total <= k:
                k -= total
                o += (valid + 1) * 2
                if buf[o + 1] == 0:
                    return 0.0
                continue
            break
        if valid > k:
            return struct.unpack_from('<h', buf, o + (k + 1) * 2)[0] * scale
        return struct.unpack_from('<h', buf, o + valid * 2)[0] * scale

    def frame_pose(self, a, frame):
        """Local (pos[n,3], quat[n,4]) for one integer frame of animdesc a.

        For delta animations the result is the delta (identity where absent).
        """
        n = self.numbones
        delta = bool(a['flags'] & 0x0004)
        pos = np.zeros((n, 3))
        quat = np.zeros((n, 4)); quat[:, 3] = 1
        if not delta:
            for i, b in enumerate(self.bones):
                pos[i] = b['pos']; quat[i] = b['quat']

        r, lf = self._anim_ptr(a, frame)
        if r is None or r[0] is None:
            return pos, quat
        buf, o = r
        while True:
            bone, flags, nextoff = struct.unpack_from('<BBh', buf, o)
            if bone >= self.numbones:      # 255 = empty animation (all identity)
                break
            data = o + 4
            b = self.bones[bone]
            adelta = bool(flags & 0x10)
            # rotation
            if flags & 0x02:      # RAWROT Quaternion48
                x, y, zw = struct.unpack_from('<HHH', buf, data)
                z = zw & 0x7fff; wneg = zw >> 15
                qx = (x - 32768) / 32768.0; qy = (y - 32768) / 32768.0; qz = (z - 16384) / 16384.0
                qw = math.sqrt(max(0.0, 1 - qx * qx - qy * qy - qz * qz))
                quat[bone] = [qx, qy, qz, -qw if wneg else qw]
            elif flags & 0x20:    # RAWROT2 Quaternion64
                v = struct.unpack_from('<Q', buf, data)[0]
                x = v & 0x1fffff; y = (v >> 21) & 0x1fffff; z = (v >> 42) & 0x1fffff; wneg = v >> 63
                qx = (x - 1048576) / 1048576.5; qy = (y - 1048576) / 1048576.5; qz = (z - 1048576) / 1048576.5
                qw = math.sqrt(max(0.0, 1 - qx * qx - qy * qy - qz * qz))
                quat[bone] = [qx, qy, qz, -qw if wneg else qw]
            elif flags & 0x08:    # ANIMROT
                offs = struct.unpack_from('<3h', buf, data)
                ang = [0.0, 0.0, 0.0]
                for j in range(3):
                    if offs[j] > 0:
                        ang[j] = self._extract(buf, data + offs[j], lf, b['rotscale'][j])
                if not adelta:
                    ang = [ang[j] + b['rot'][j] for j in range(3)]
                quat[bone] = euler_to_quat(*ang)
            else:
                quat[bone] = [0, 0, 0, 1] if adelta else b['quat']
            # position
            if flags & 0x01:      # RAWPOS Vector48
                po = data + (6 if flags & 0x02 else 0) + (8 if flags & 0x20 else 0)
                hx, hy, hz = struct.unpack_from('<3H', buf, po)
                pos[bone] = [half(hx), half(hy), half(hz)]
            elif flags & 0x04:    # ANIMPOS
                vo = data + (6 if flags & 0x08 else 0)
                offs = struct.unpack_from('<3h', buf, vo)
                p = [0.0, 0.0, 0.0]
                for j in range(3):
                    if offs[j] > 0:
                        p[j] = self._extract(buf, vo + offs[j], lf, b['posscale'][j])
                if not adelta:
                    p = [p[j] + b['pos'][j] for j in range(3)]
                pos[bone] = p
            else:
                pos[bone] = [0, 0, 0] if adelta else b['pos']
            if nextoff == 0:
                break
            o += nextoff
        return pos, quat

    def frames(self, a):
        return [self.frame_pose(a, f) for f in range(a['numframes'])]

    # sequences ---------------------------------------------------------
    def _read_seqs(self):
        d = self.d
        self.seqs = []
        for i in range(self.numseq):
            o = self.seqindex + i * 212
            (baseptr, labeloff, actoff, flags, activity, actweight, numevents, eventindex) = \
                struct.unpack_from('<8i', d, o)
            numblends, animindexindex, movementindex = struct.unpack_from('<3i', d, o + 56)
            groupsize = struct.unpack_from('<2i', d, o + 68)
            paramindex = struct.unpack_from('<2i', d, o + 76)
            paramstart = struct.unpack_from('<2f', d, o + 84)
            paramend = struct.unpack_from('<2f', d, o + 92)
            fadein, fadeout = struct.unpack_from('<2f', d, o + 104)
            numautolayers, autolayerindex, weightlistindex, posekeyindex = struct.unpack_from('<4i', d, o + 148)
            count = groupsize[0] * groupsize[1]
            anims = list(struct.unpack_from('<%dh' % count, d, o + animindexindex)) if count else []
            weights = list(struct.unpack_from('<%df' % self.numbones, d, o + weightlistindex))
            self.seqs.append(dict(index=i, name=cstr(d, o + labeloff), activity=cstr(d, o + actoff),
                                  flags=flags, groupsize=groupsize, paramindex=paramindex,
                                  paramstart=paramstart, paramend=paramend, anims=anims,
                                  weights=weights, fadein=fadein, fadeout=fadeout,
                                  numautolayers=numautolayers, autolayerindex=autolayerindex,
                                  off=o))
        self.seq_by_name = {s['name'].lower(): s for s in self.seqs}

    # world space ---------------------------------------------------------
    def world(self, pos, quat):
        n = self.numbones
        R = np.zeros((n, 3, 3)); T = np.zeros((n, 3))
        for i, b in enumerate(self.bones):
            r = quat_to_mat(quat[i])
            if b['parent'] < 0:
                R[i] = r; T[i] = pos[i]
            else:
                p = b['parent']
                R[i] = R[p] @ r; T[i] = R[p] @ pos[i] + T[p]
        return R, T
