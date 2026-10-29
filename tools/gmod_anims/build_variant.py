"""Give another Half-Life player model (same skeleton names, a subset of
player.mdl's bones, same sequence order) the animations of an already
converted player.mdl, by copying each matching bone's local channels.

  python3 -I build_variant.py <converted player.mdl> <base model.mdl> <out.mdl>
"""
import sys
import numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel

src_path, base_path, out_path = sys.argv[1:4]
src = GoldSrcModel(src_path)
base = GoldSrcModel(base_path)

# every base bone must exist in the source with the same parent
idx = []
for b in base.bones:
    si = src.bone_by_name[b['name']]
    sp = src.bones[si]['parent']
    bp = b['parent']
    assert (sp < 0 and bp < 0) or src.bones[sp]['name'] == base.bones[bp]['name'], b['name']
    idx.append(si)

n_base = len(base.seqs)
assert [s['label'] for s in src.seqs[:n_base]] == [s['label'] for s in base.seqs], 'sequence order differs'

seqs = []
for i, s in enumerate(src.seqs):
    frames = [arr[:, idx, :] for arr in src.decode(i)]
    d = dict(label=s['label'], fps=s['fps'], frames=frames, flags=s['flags'], activity=s['activity'],
             actweight=s['actweight'], motiontype=s['motiontype'],
             motionbone=base.seqs[i]['motionbone'] if i < n_base else 0,
             linearmovement=s['linearmovement'], blendtype=s['blendtype'], blendstart=s['blendstart'],
             blendend=s['blendend'])
    # the base model's own sequence header (events, bbox) for the original 77
    d['raw'] = base.seqs[i]['raw'] if i < n_base else None
    seqs.append(d)

size = base.write(out_path, seqs)
print('wrote', out_path, size, 'bytes,', len(seqs), 'sequences')
