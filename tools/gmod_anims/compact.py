"""Rewrite a GoldSrc studio model with only the data it uses.

  python3 -I compact.py <in.mdl> <out.mdl>

The tools here (add_freeman.py, add_l4d.py, hls_body.py ...) append new bones,
animations, sequences, meshes and textures and leave the old ones in the file.
The engine keeps everything up to the texture data in memory for as long as
the model is loaded, so the dead data costs real memory (two 13 MB outfits are
enough to run Half-Life out of model memory when the suit is picked up). This
copies each referenced block once, in the standard order, textures last.
"""
import struct
import sys

HDR = 244


def tri_len(d, o):
    s = o
    while True:
        n = struct.unpack_from('<h', d, o)[0]
        o += 2
        if n == 0:
            return o - s
        o += abs(n) * 8


def anim_len(d, ao, numbones, numblends, numframes):
    """Bytes from animindex to the end of the last channel's RLE stream."""
    end = ao + numblends * numbones * 12
    for b in range(numblends * numbones):
        base = ao + b * 12
        offs = struct.unpack_from('<6H', d, base)
        for off in offs:
            if not off:
                continue
            o = base + off
            k = 0
            while k < numframes:
                valid, total = d[o], d[o + 1]
                if total == 0:
                    break
                k += total
                o += (valid + 1) * 2
            end = max(end, o)
    return end - ao


def compact(src, dst):
    d = open(src, 'rb').read()
    h = bytearray(d[:HDR])
    (numbones, boneindex, nbc, bci, nhb, hbi, numseq, seqindex, nsg, sgi,
     ntex, ti, tdi, nsr, nsf, si, nbp, bpi, natt, atti) = struct.unpack_from('<20i', d, 140)
    ntrans, transi = struct.unpack_from('<2i', d, 236)
    out = bytearray(h)

    def align():
        while len(out) % 4:
            out.append(0)

    def put(blob):
        align()
        o = len(out)
        out.extend(blob)
        return o

    new = {}
    new['bone'] = put(d[boneindex:boneindex + numbones * 112]) if numbones else 0
    new['bc'] = put(d[bci:bci + nbc * 24]) if nbc else 0
    new['hb'] = put(d[hbi:hbi + nhb * 32]) if nhb else 0
    new['sg'] = put(d[sgi:sgi + nsg * 104]) if nsg else 0
    new['att'] = put(d[atti:atti + natt * 88]) if natt else 0
    new['trans'] = put(d[transi:transi + ntrans * ntrans]) if ntrans else 0

    # sequences: events, pivots, animation data, then the table
    seqs = []
    for i in range(numseq):
        so = seqindex + i * 176
        raw = bytearray(d[so:so + 176])
        numevents, eventindex = struct.unpack_from('<2i', raw, 48)
        numframes = struct.unpack_from('<i', raw, 56)[0]
        numpivots, pivotindex = struct.unpack_from('<2i', raw, 60)
        numblends, animindex = struct.unpack_from('<2i', raw, 120)
        seqgroup = struct.unpack_from('<i', raw, 156)[0]
        if numevents:
            struct.pack_into('<i', raw, 52, put(d[eventindex:eventindex + numevents * 76]))
        if numpivots:
            struct.pack_into('<i', raw, 64, put(d[pivotindex:pivotindex + numpivots * 20]))
        if seqgroup == 0:
            n = anim_len(d, animindex, numbones, numblends, numframes)
            struct.pack_into('<i', raw, 124, put(d[animindex:animindex + n]))
        seqs.append(bytes(raw))
    new['seq'] = put(b''.join(seqs)) if numseq else 0

    # body parts -> models -> meshes / vertices / normals / triangles
    bps = []
    for b in range(nbp):
        bo = bpi + b * 76
        raw = bytearray(d[bo:bo + 76])
        nm, base, mi = struct.unpack_from('<3i', raw, 64)
        models = []
        for m in range(nm):
            mo = mi + m * 112
            mr = bytearray(d[mo:mo + 112])
            nmesh, meshi, nv, vinfo, vidx, nn, ninfo, nidx, ng, gi = struct.unpack_from('<10i', mr, 72)
            meshes = []
            for k in range(nmesh):
                me = meshi + k * 20
                mer = bytearray(d[me:me + 20])
                ntri, trii = struct.unpack_from('<2i', mer, 0)
                struct.pack_into('<i', mer, 4, put(d[trii:trii + tri_len(d, trii)]) if trii else 0)
                struct.pack_into('<i', mer, 16, 0)
                meshes.append(bytes(mer))
            nvinfo = put(d[vinfo:vinfo + nv]) if nv else 0
            nvidx = put(d[vidx:vidx + nv * 12]) if nv else 0
            nninfo = put(d[ninfo:ninfo + nn]) if nn else 0
            nnidx = put(d[nidx:nidx + nn * 12]) if nn else 0
            nmeshi = put(b''.join(meshes)) if nmesh else 0
            struct.pack_into('<10i', mr, 72, nmesh, nmeshi, nv, nvinfo, nvidx, nn, nninfo, nnidx, 0, 0)
            models.append(bytes(mr))
        struct.pack_into('<i', raw, 72, put(b''.join(models)) if nm else 0)
        bps.append(bytes(raw))
    new['bp'] = put(b''.join(bps)) if nbp else 0

    # textures: headers and skins here, pixel data last
    texh = []
    for t in range(ntex):
        texh.append(bytearray(d[ti + t * 80:ti + t * 80 + 80]))
    new['tex'] = put(b''.join(texh)) if ntex else 0
    new['skin'] = put(d[si:si + nsr * nsf * 2]) if nsr and nsf else 0
    align()
    new['texdata'] = len(out)
    for t in range(ntex):
        flags, w, hh, idx = struct.unpack_from('<4i', texh[t], 64)
        struct.pack_into('<i', out, new['tex'] + t * 80 + 76, len(out))
        out.extend(d[idx:idx + w * hh + 768])
    if not ntex:
        new['texdata'] = 0

    struct.pack_into('<20i', out, 140, numbones, new['bone'], nbc, new['bc'], nhb, new['hb'], numseq, new['seq'],
                     nsg, new['sg'], ntex, new['tex'], new['texdata'], nsr, nsf, new['skin'], nbp, new['bp'],
                     natt, new['att'])
    struct.pack_into('<4i', out, 220, 0, 0, 0, 0)          # sound tables (unused)
    struct.pack_into('<2i', out, 236, ntrans, new['trans'])
    struct.pack_into('<i', out, 72, len(out))
    open(dst, 'wb').write(out)
    return len(d), len(out), new['texdata']


if __name__ == '__main__':
    print(compact(sys.argv[1], sys.argv[2]))
