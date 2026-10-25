"""GoldSrc (Half-Life 1) studio model: read skeleton + animations, rewrite
with replaced/added sequences. Layouts follow the HL SDK engine/studio.h."""
import copy
import math
import struct

import numpy as np

from srcmdl import euler_to_quat, quat_to_mat

HDR_FMT = '<4si64si3f3f3f3f3fi' + 'i' * 30  # through transitionindex
SEQ_SIZE = 176
BONE_SIZE = 112


def cstr(b):
    return b.split(b'\0')[0].decode('latin-1')


def mat_to_euler(m):
    """Inverse of AngleQuaternion/AngleMatrix: R = Rz(z) Ry(y) Rx(x)."""
    sy = -m[2][0]
    sy = max(-1.0, min(1.0, sy))
    y = math.asin(sy)
    if abs(sy) < 0.99999:
        x = math.atan2(m[2][1], m[2][2])
        z = math.atan2(m[1][0], m[0][0])
    else:
        x = math.atan2(-m[1][2], m[1][1])
        z = 0.0
    return np.array([x, y, z])


def quat_to_euler(q):
    return mat_to_euler(quat_to_mat(q))


def unwrap_near(a, ref):
    return ref + ((a - ref + math.pi) % (2 * math.pi)) - math.pi


class GoldSrcModel:
    def __init__(self, path):
        self.d = bytearray(open(path, 'rb').read())
        d = self.d
        assert d[:4] == b'IDST'
        self.version = struct.unpack_from('<i', d, 4)[0]
        assert self.version == 10, self.version
        o = 4 + 4 + 64 + 4 + 12 * 5 + 4
        (self.numbones, self.boneindex, self.numbonecontrollers, self.bonecontrollerindex,
         self.numhitboxes, self.hitboxindex, self.numseq, self.seqindex,
         self.numseqgroups, self.seqgroupindex) = struct.unpack_from('<10i', d, o)
        self.ofs_numbones = o
        self.ofs_numseq = o + 24
        self.bones = []
        for i in range(self.numbones):
            bo = self.boneindex + i * BONE_SIZE
            name = cstr(bytes(d[bo:bo + 32]))
            parent, flags = struct.unpack_from('<ii', d, bo + 32)
            ctl = struct.unpack_from('<6i', d, bo + 40)
            value = np.array(struct.unpack_from('<6f', d, bo + 64))
            scale = np.array(struct.unpack_from('<6f', d, bo + 88))
            self.bones.append(dict(name=name, parent=parent, flags=flags, ctl=ctl, value=value, scale=scale))
        self.bone_by_name = {b['name']: i for i, b in enumerate(self.bones)}
        self.seqs = []
        for i in range(self.numseq):
            so = self.seqindex + i * SEQ_SIZE
            raw = bytes(d[so:so + SEQ_SIZE])
            s = dict(raw=raw, label=cstr(raw[:32]))
            (s['fps'], s['flags'], s['activity'], s['actweight'], s['numevents'], s['eventindex'],
             s['numframes'], s['numpivots'], s['pivotindex'], s['motiontype'], s['motionbone']) = \
                struct.unpack_from('<f10i', raw, 32)
            s['linearmovement'] = list(struct.unpack_from('<3f', raw, 76))
            s['numblends'], s['animindex'] = struct.unpack_from('<ii', raw, 120)
            s['blendtype'] = list(struct.unpack_from('<2i', raw, 128))
            s['blendstart'] = list(struct.unpack_from('<2f', raw, 136))
            s['blendend'] = list(struct.unpack_from('<2f', raw, 144))
            s['seqgroup'] = struct.unpack_from('<i', raw, 156)[0]
            self.seqs.append(s)
        self.seq_by_name = {s['label']: i for i, s in enumerate(self.seqs)}

    # ------------------------------------------------------------ decode
    def _value(self, o, frame, scale):
        d = self.d
        k = frame
        while True:
            valid, total = d[o], d[o + 1]
            if total <= k:
                k -= total
                o += (valid + 1) * 2
                if d[o + 1] == 0:
                    return 0.0
                continue
            break
        if valid > k:
            return struct.unpack_from('<h', d, o + (k + 1) * 2)[0] * scale
        return struct.unpack_from('<h', d, o + valid * 2)[0] * scale

    def decode(self, seqi):
        """-> list over blends of array [frames, bones, 6] (pos xyz, euler xyz)."""
        s = self.seqs[seqi]
        assert s['seqgroup'] == 0
        out = []
        for blend in range(s['numblends']):
            base = s['animindex'] + blend * self.numbones * 12
            arr = np.zeros((s['numframes'], self.numbones, 6))
            for b in range(self.numbones):
                ao = base + b * 12
                offs = struct.unpack_from('<6H', self.d, ao)
                bone = self.bones[b]
                for j in range(6):
                    for f in range(s['numframes']):
                        v = bone['value'][j]
                        if offs[j]:
                            v += self._value(ao + offs[j], f, bone['scale'][j])
                        arr[f, b, j] = v
            out.append(arr)
        return out

    def rest_local(self):
        return np.array([b['value'] for b in self.bones])

    def world(self, local6):
        n = self.numbones
        R = np.zeros((n, 3, 3)); T = np.zeros((n, 3))
        for i, b in enumerate(self.bones):
            r = quat_to_mat(euler_to_quat(*local6[i, 3:6]))
            if b['parent'] < 0:
                R[i] = r; T[i] = local6[i, :3]
            else:
                p = b['parent']
                R[i] = R[p] @ r; T[i] = R[p] @ local6[i, :3] + T[p]
        return R, T

    # ------------------------------------------------------------ encode
    @staticmethod
    def _rle(vals):
        """vals: list of int16 -> list of int16 words (RLE as studiomdl)."""
        out = []
        n = len(vals)
        i = 0
        while i < n:
            valid = 0
            total = 0
            block = []
            # take distinct values until a repeat run starts or 255
            while i < n and valid < 255 and total < 255:
                block.append(vals[i]); valid += 1; total += 1; i += 1
                # absorb repeats of the last value into "total"
                run = 0
                while i < n and vals[i] == block[-1] and total < 255:
                    i += 1; total += 1; run += 1
                if run:
                    break
            out.append(('hdr', valid, total))
            out.extend(block)
        return out

    def _encode_seq(self, s, rest, scales):
        nb = self.numbones
        nbl = len(s['frames'])
        nf = s['frames'][0].shape[0]
        header = bytearray(nbl * nb * 12)
        streams = bytearray()
        for bl, arr in enumerate(s['frames']):
            for b in range(nb):
                for j in range(6):
                    q = np.round((arr[:, b, j] - rest[b, j]) / scales[b, j]).astype(int)
                    q = np.clip(q, -32767, 32767)
                    if not q.any():
                        continue
                    words = self._rle([int(v) for v in q])
                    hdr_pos = (bl * nb + b) * 12
                    off = len(header) - hdr_pos + len(streams)
                    if off > 65535:
                        raise OverflowError(s['label'])
                    struct.pack_into('<H', header, hdr_pos + j * 2, off)
                    for w in words:
                        if isinstance(w, tuple):
                            streams += bytes([w[1], w[2]])
                        else:
                            streams += struct.pack('<h', w)
        return bytes(header + streams), nf

    def write(self, path, sequences):
        """sequences: list of dicts with keys
        label, fps, flags, activity, actweight, motiontype, motionbone,
        linearmovement, blendtype, blendstart, blendend, frames (list over
        blends of [F, bones, 6] arrays), raw (optional original 176 bytes),
        events (optional raw bytes, numevents) """
        nb = self.numbones
        # 1. choose new per-channel scales covering every sequence
        maxdev = np.zeros((nb, 6))
        rest = self.rest_local()
        for s in sequences:
            for arr in s['frames']:
                dev = np.abs(arr - rest[None])
                maxdev = np.maximum(maxdev, dev.max(axis=0))
        scales = np.where(maxdev > 1e-6, maxdev / 32000.0, np.array([b['scale'] for b in self.bones]))
        scales = np.maximum(scales, 1e-7)

        d = bytearray(self.d)
        extra = bytearray()
        base_off = len(d)

        def align4():
            while (base_off + len(extra)) % 4:
                extra.append(0)

        # 2. bones with new scales
        align4()
        new_boneindex = base_off + len(extra)
        for i, b in enumerate(self.bones):
            bo = self.boneindex + i * BONE_SIZE
            raw = bytearray(d[bo:bo + BONE_SIZE])
            struct.pack_into('<6f', raw, 88, *scales[i])
            extra += raw

        # 3. animation data per sequence (long clips are halved in frame
        # rate until every channel offset fits GoldSrc's 16-bit offsets)
        seq_raw = []
        self.downsampled = []
        for s in sequences:
            align4()
            animindex = base_off + len(extra)
            while True:
                try:
                    blob, nf = self._encode_seq(s, rest, scales)
                    break
                except OverflowError:
                    s['frames'] = [np.concatenate([a[::2], a[-1:]]) if (len(a) - 1) % 2 else a[::2]
                                   for a in s['frames']]
                    s['fps'] = s['fps'] / 2.0
                    self.downsampled.append(s['label'])
            nbl = len(s['frames'])
            extra += blob

            raw = bytearray(s.get('raw') or bytes(SEQ_SIZE))
            lab = s['label'].encode('latin-1')[:31]
            raw[0:32] = lab + bytes(32 - len(lab))
            struct.pack_into('<f', raw, 32, s['fps'])
            struct.pack_into('<3i', raw, 36, s['flags'], s['activity'], s['actweight'])
            struct.pack_into('<i', raw, 56, nf)
            struct.pack_into('<2i', raw, 68, s.get('motiontype', 0), s.get('motionbone', 0))
            struct.pack_into('<3f', raw, 76, *s.get('linearmovement', [0, 0, 0]))
            struct.pack_into('<2i', raw, 120, nbl, animindex)
            struct.pack_into('<2i', raw, 128, *s.get('blendtype', [0, 0]))
            struct.pack_into('<2f', raw, 136, *s.get('blendstart', [0, 0]))
            struct.pack_into('<2f', raw, 144, *s.get('blendend', [0, 0]))
            struct.pack_into('<i', raw, 156, 0)  # seqgroup
            if not s.get('raw'):
                # no events / pivots for new sequences; bbox from the first old sequence
                struct.pack_into('<2i', raw, 48, 0, 0)          # numevents, eventindex
                struct.pack_into('<2i', raw, 60, 0, 0)          # numpivots, pivotindex
                raw[96:120] = self.seqs[0]['raw'][96:120]
                struct.pack_into('<6i', raw, 152, 0, 0, 0, 0, 0, 0)  # blendparent.. nextseq
            seq_raw.append(bytes(raw))

        # 4. sequence table
        align4()
        new_seqindex = base_off + len(extra)
        for r in seq_raw:
            extra += r

        d += extra
        struct.pack_into('<i', d, self.ofs_numbones + 4, new_boneindex)
        struct.pack_into('<2i', d, self.ofs_numseq, len(seq_raw), new_seqindex)
        struct.pack_into('<i', d, 72, len(d))  # header length
        open(path, 'wb').write(d)
        return len(d)
