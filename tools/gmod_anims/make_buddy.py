"""The fpbody HEV companion's model (models/fpbody_buddy.mdl, sv_fpbody_buddy):
an HEV security guard NPC model with Half-Life's soldier MP5 added.

  python3 -I make_buddy.py <barney_hev.mdl> <hgrunt.mdl> <out.mdl> [--ref rest|idle]
        [--hue degrees]

<barney_hev.mdl>: a Barney model on 3ds Max Biped bones (Thigh/Calf/
UpperArm/Forearm names), e.g. Echoes' HEV Barney, or on Half-Life's own
(Leg/Arm names, as the soldier), e.g. Azure Sheep's hev_barney.mdl; textures
in a T file and sequence groups are folded into the one output file. <hgrunt.mdl>: Half-Life's
soldier (hgruntT.mdl / hgrunt01.mdl next to it). Added:
  - sequences mp5_idle / mp5_walk / mp5_run / mp5_shoot from the soldier's
    combatidle / walk1 / run / standing_mp5, retargeted by each bone's turn in
    world space from a shared standing reference (--ref: the two models' rest
    poses, default, or their idle1 first frames); fingers (the soldier has
    none) take Barney's grip from "shootgun"; the root moves as the
    soldier's, scaled to the leg length; walk / run speeds scaled the same;
  - the soldier's MP5 (weapons submodel 0, with its texture) as submodel 3 of
    Barney's gun bodypart, put on Barney's right hand so that it follows the
    hand exactly as on the soldier.
--hue turns the HEV textures' palettes (names starting --suit, default
barney_HEV) by that many degrees (with --near: only colours within 50 degrees
of that hue, e.g. a blue suit and not its yellow logo).
The result contains both models' data: keep it local.
"""
import argparse
import colorsys
import struct
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel, mat_to_euler            # noqa: E402
from srcmdl import euler_to_quat, quat_to_mat             # noqa: E402
from add_cz import existing_sequences, textures_last, clone   # noqa: E402
from compact import compact                               # noqa: E402

MAP = {   # Barney bone -> soldier bone
    'Bip01': 'Bip01', 'Bip01 Pelvis': 'Bip01 Pelvis', 'Bip01 Spine': 'Bip01 Spine', 'Bip01 Spine1': 'Bip01 Spine3',
    'Bip01 Neck': 'Bip01 Neck', 'Bip01 Head': 'Bip01 Head',
}
for s in 'LR':
    MAP.update({'Bip01 %s Thigh' % s: 'Bip01 %s Leg' % s, 'Bip01 %s Calf' % s: 'Bip01 %s Leg1' % s,
                'Bip01 %s Foot' % s: 'Bip01 %s Foot' % s, 'Bip01 %s Clavicle' % s: 'Bip01 %s Arm' % s,
                'Bip01 %s UpperArm' % s: 'Bip01 %s Arm1' % s, 'Bip01 %s Forearm' % s: 'Bip01 %s Arm2' % s,
                'Bip01 %s Hand' % s: 'Bip01 %s Hand' % s})
SEQS = (('mp5_idle', 'combatidle'), ('mp5_walk', 'walk1'), ('mp5_run', 'run'), ('mp5_shoot', 'standing_mp5'))
GUN_PART, GUN_SUB = 2, 0      # the soldier's "weapons" bodypart, "gunreference"


def leg(G):
    r = G.rest_local()
    calf = 'Bip01 L Calf' if 'Bip01 L Calf' in G.bone_by_name else 'Bip01 L Leg1'
    return np.linalg.norm(r[G.bone_by_name[calf], :3]) + np.linalg.norm(r[G.bone_by_name['Bip01 L Foot'], :3])


def bone_map(B, S):
    """Barney bone index -> soldier bone index"""
    out = {}
    for i, b in enumerate(B.bones):
        n = b['name']
        t = MAP.get(n, n if n.startswith('Bip01') else None)
        if t in S.bone_by_name:
            out[i] = S.bone_by_name[t]
    return out


def rot(e):
    return quat_to_mat(euler_to_quat(*e))


def retarget(S, B, src_label, ref_s, ref_b, grip, k):
    """the soldier's sequence on Barney's bones: [blends][frames, bones, 6]"""
    Rs0, Ts0 = S.world(ref_s)
    Rb0, _ = B.world(ref_b)
    smap = bone_map(B, S)
    out = []
    for blend in S.decode(S.seq_by_name[src_label]):
        f = np.repeat(grip[None], len(blend), axis=0)
        for n in range(len(blend)):
            Rs, Ts = S.world(blend[n])
            Rb = np.zeros((len(B.bones), 3, 3))
            for i, b in enumerate(B.bones):
                p = b['parent']
                ci = smap.get(i)
                if ci is not None:
                    Rb[i] = (Rs[ci] @ Rs0[ci].T) @ Rb0[i]
                    loc = Rb[i] if p < 0 else Rb[p].T @ Rb[i]
                    f[n, i, 3:6] = mat_to_euler(loc)
                else:
                    r = rot(grip[i, 3:6])
                    Rb[i] = r if p < 0 else Rb[p] @ r
            for i, b in enumerate(B.bones):
                if b['parent'] < 0 and i in smap:
                    f[n, i, :3] = grip[i, :3] + (Ts[smap[i]] - Ts0[smap[i]]) * k
        out.append(f)
    return out


def read_model(d, mi):
    nummesh, meshindex, numverts, vinfo, vindex, numnorms, ninfo, nindex = struct.unpack_from('<8i', d, mi + 72)
    return dict(meshes=[struct.unpack_from('<5i', d, meshindex + m * 20) for m in range(nummesh)],
                vb=d[vinfo:vinfo + numverts], nb=d[ninfo:ninfo + numnorms],
                v=np.frombuffer(d[vindex:vindex + numverts * 12], '<f4').reshape(-1, 3).astype(float),
                n=np.frombuffer(d[nindex:nindex + numnorms * 12], '<f4').reshape(-1, 3).astype(float))


def tricmds(d, o):
    start = o
    while True:
        c = struct.unpack_from('<h', d, o)[0]; o += 2
        if c == 0:
            return d[start:o]
        o += abs(c) * 8


def textures(d):
    ntex, ti = struct.unpack_from('<2i', d, 180)
    out = []
    for t in range(ntex):
        o = ti + t * 80
        flags, w, h, idx = struct.unpack_from('<4i', d, o + 64)
        out.append(dict(hdr=bytearray(d[o:o + 80]), w=w, h=h, data=d[idx:idx + w * h + 768]))
    return out


def add_gun(path, path_t, S, ST, B, ref_s, ref_b, k):
    """append the soldier's MP5 as a new submodel of Barney's gun bodypart"""
    d = bytearray(open(path, 'rb').read())
    sd, td = bytes(S.d), bytes(ST.d)
    nbp, bpi = struct.unpack_from('<2i', sd, 204)
    gmi = struct.unpack_from('<i', sd, bpi + GUN_PART * 76 + 72)[0] + GUN_SUB * 112
    gun = read_model(sd, gmi)
    # the soldier's bones in his rest (= mesh) pose and at the reference
    Rr, Tr = S.world(S.rest_local())
    Rs0, _ = S.world(ref_s)
    Rb0, _ = B.world(ref_b)
    sh, bh = S.bone_by_name['Bip01 R Hand'], B.bone_by_name['Bip01 R Hand']
    V, N = [], []
    for v, b in zip(gun['v'], gun['vb']):
        w = Rr[b] @ v + Tr[b]
        u = Rr[sh].T @ (w - Tr[sh])                 # in the soldier's hand frame
        V.append(Rb0[bh].T @ (Rs0[sh] @ u) * k)    # in Barney's hand frame
    for nrm, b in zip(gun['n'], gun['nb']):
        N.append(Rb0[bh].T @ (Rs0[sh] @ (Rr[sh].T @ (Rr[b] @ nrm))))
    # textures: Barney's + the gun's (from hgruntT's skin table)
    src = bytes(d)
    if not struct.unpack_from('<i', src, 180)[0]:       # textures in a T file
        import os
        if not os.path.exists(path_t):
            path_t = path_t[:-5] + 't.mdl'
        src = open(path_t, 'rb').read()
    btex = textures(src)
    stex = textures(td)
    nsr, nsf, si = struct.unpack_from('<3i', td, 192)
    sskins = struct.unpack_from('<%dh' % nsr, td, si)
    bnsr, bnsf, bsi = struct.unpack_from('<3i', src, 192)
    bskins = list(struct.unpack_from('<%dh' % (bnsr * bnsf), src, bsi))
    newref = {}
    for m in gun['meshes']:
        if m[2] not in newref:
            newref[m[2]] = len(btex); btex.append(stex[sskins[m[2]]])
    tot = len(btex)
    fams = [bskins[f * bnsr:(f + 1) * bnsr] + list(range(bnsr, tot)) for f in range(bnsf)]

    def align():
        while len(d) % 4:
            d.append(0)

    def put(b):
        align(); o = len(d); d.extend(b); return o
    vinfo = put(bytes([bh] * len(V)))
    ninfo = put(bytes([bh] * len(N)))
    vindex = put(np.array(V, '<f4').tobytes())
    nindex = put(np.array(N, '<f4').tobytes())
    meshes = bytearray()
    for numtris, triindex, skinref, numnorms, _ in gun['meshes']:
        to = put(tricmds(sd, triindex))
        meshes += struct.pack('<5i', numtris, to, newref[skinref], numnorms, 0)
    mesh_off = put(bytes(meshes))
    # Barney's gun bodypart: its submodels + the MP5
    bbp, bbpi = struct.unpack_from('<2i', d, 204)
    gp = next(p for p in range(bbp) if struct.unpack_from('<i', d, bbpi + p * 76 + 64)[0] > 1)
    nm, base, mi = struct.unpack_from('<3i', d, bbpi + gp * 76 + 64)
    models = bytearray(d[mi:mi + nm * 112])
    radius = float(np.max(np.linalg.norm(np.array(V), axis=1)))
    models += struct.pack('<64sif8i2i', b'mp5'.ljust(64, b'\0'), 0, radius, len(gun['meshes']), mesh_off,
                          len(V), vinfo, vindex, len(N), ninfo, nindex, 0, 0)
    struct.pack_into('<3i', d, bbpi + gp * 76 + 64, nm + 1, base, put(bytes(models)))
    # textures (headers, then data) and the skin table
    hdr_off = put(bytes(80 * tot))
    data0 = None
    for i, t in enumerate(btex):
        o = put(t['data'])
        data0 = o if data0 is None else data0
        h = bytearray(t['hdr']); struct.pack_into('<i', h, 76, o)
        d[hdr_off + i * 80:hdr_off + i * 80 + 80] = h
    skin_off = put(struct.pack('<%dh' % (tot * bnsf), *[x for f in fams for x in f]))
    struct.pack_into('<3i', d, 180, tot, hdr_off, data0)
    struct.pack_into('<3i', d, 192, tot, bnsf, skin_off)
    struct.pack_into('<i', d, 72, len(d))
    open(path, 'wb').write(d)
    return gp, nm


def tint(path, hue, prefix, near=None):
    d = bytearray(open(path, 'rb').read())
    for t in textures(bytes(d)):
        name = bytes(t['hdr'][:64]).split(b'\0')[0].decode('latin-1').lower()
        if not any(name.startswith(p.lower()) for p in prefix.split(',')):
            continue
        idx = struct.unpack_from('<i', t['hdr'], 76)[0] + t['w'] * t['h']
        for k in range(256):
            r, g, b = (x / 255 for x in d[idx + k * 3:idx + k * 3 + 3])
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            if s > 0.25 and (near is None or abs((h * 360 - near + 180) % 360 - 180) < 50):   # not greys / chrome / other colours
                r, g, b = colorsys.hsv_to_rgb((h + hue / 360.0) % 1.0, s, v)
                d[idx + k * 3:idx + k * 3 + 3] = bytes(int(round(x * 255)) for x in (r, g, b))
    open(path, 'wb').write(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('barney'); ap.add_argument('hgrunt'); ap.add_argument('out')
    ap.add_argument('--ref', default='rest', choices=('rest', 'idle'))
    ap.add_argument('--hue', type=float, default=0.0)
    ap.add_argument('--suit', default='barney_HEV')
    ap.add_argument('--near', type=float, default=None, help='only colours within 50 degrees of this hue')
    a = ap.parse_args()
    B, S = GoldSrcModel(a.barney), GoldSrcModel(a.hgrunt)
    ST = GoldSrcModel(a.hgrunt[:-4] + 'T.mdl')
    if a.ref == 'rest':
        ref_s, ref_b = S.rest_local(), B.rest_local()
    else:
        ref_s, ref_b = S.decode(S.seq_by_name['idle1'])[0][0], B.decode(B.seq_by_name['idle1'])[0][0]
    k = leg(B) / leg(S)
    grip = B.decode(B.seq_by_name['shootgun'])[0][0].copy()
    seqs = existing_sequences(B)
    by = {s['label']: s for s in seqs}
    for new, src in SEQS:
        si = S.seq_by_name[src]
        s = clone(by['idle1'], new)
        s['frames'] = retarget(S, B, src, ref_s, ref_b, grip, k)
        q = S.seqs[si]
        s['fps'], s['flags'] = q['fps'], q['flags']
        s['blendtype'], s['blendstart'], s['blendend'] = list(q['blendtype']), list(q['blendstart']), list(q['blendend'])
        s['linearmovement'] = [x * k for x in q['linearmovement']]
        s['motiontype'] = q.get('motiontype', 0)
        seqs = [x for x in seqs if x['label'] != new] + [s]
    tmp = a.out + '.tmp'
    B.write(tmp, seqs)
    gp, nm = add_gun(tmp, a.barney[:-4] + 'T.mdl', S, ST, B, ref_s, ref_b, k)
    if a.hue:
        tint(tmp, a.hue, a.suit, a.near)
    textures_last(tmp)
    compact(tmp, a.out)
    d = bytearray(open(a.out, 'rb').read())     # every sequence is in this file now
    o = 4 + 4 + 64 + 4 + 12 * 5 + 4 + 32
    if struct.unpack_from('<i', d, o)[0] > 1:
        struct.pack_into('<i', d, o, 1)
        open(a.out, 'wb').write(d)
    import os
    os.remove(tmp)
    print('wrote', a.out, 'leg scale %.3f' % k, 'MP5 = bodypart %d submodel %d' % (gp, nm))


if __name__ == '__main__':
    main()
