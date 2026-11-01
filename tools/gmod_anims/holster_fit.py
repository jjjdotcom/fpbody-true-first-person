import sys, re, os, glob
sys.argv=[sys.argv[0],'/tmp','0']
exec(open('/home/claude/hlsdk/tools/gmod_anims/lefthand_sim.py').read().split("if __name__ == '__main__':")[0])
import numpy as np
from scipy.spatial import cKDTree
src=open('/home/claude/hlsdk/cl_dll/fpbody_holsters.h').read()
rows=[]
for m in re.finditer(r'\{ "([^"]+)", "([^"]+)", "([^"]+)", \{ \{ ([^}]*)\}, \{ ([^}]*)\}, \{ ([^}]*)\} \}, (0x[0-9a-f]+), (\d+) \},\s*// ([^\n]*)',src):
    L=np.array([[float(x.strip().rstrip('f')) for x in m.group(k).split(',')] for k in (4,5,6)])
    rows.append(dict(w=m.group(1),model=m.group(2),bone=m.group(3),L=L,keep=int(m.group(7),16),length=int(m.group(8)),note=m.group(9)))
files={}
for d in ['/mnt/user-data/uploads/Half-Life/.Mods/vapw_v2/models','/home/claude/gmodconv/src/final_p','/home/claude/gmodconv/src/mmod_p','/home/claude/gmodconv/src/sven_p','/home/claude/gmodconv/src/hd_p','/home/claude/gmodconv/src/hdpack_p','/home/claude/gmodconv/src/hdpack_op4_p','/home/claude/gmodconv/src/op4_p','/home/claude/gmodconv/src/sd_p','/home/claude/gmodconv/src/ld_p']:
    for f in glob.glob(d+'/p_*.mdl'):
        files.setdefault((os.path.basename(f),os.path.getsize(f)),f)
M,btris=load_tris('/mnt/user-data/outputs/final_css/fpbody/fpbody_hls_suit.mdl')
a=M.decode(M.seq_by_name['deep_idle'])[0][0]; R,T=M.world(a)
bv=np.concatenate([np.array([R[b[i]]@v[i]+T[b[i]] for i in range(3)]) for b,v,c in btris]); kd=cKDTree(bv)
cache={}
def gunpts(path,keep):
    if (path,keep) not in cache:
        W,tris=load_tris(path); Rg,Tg=W.world(W.decode(0)[0][0])
        P=[Rg[b[k]]@v[k]+Tg[b[k]] for b,v,c in tris for k in range(3) if not keep or all((keep>>x)&1 for x in b)]
        cache[(path,keep)]=np.array(P)
    return cache[(path,keep)]
out=[]
for r in rows:
    f=files.get((os.path.basename(r['model']),r['length']))
    if not f: print('no file',r['model'],r['length']); continue
    j=M.bone_by_name[r['bone']]; Ra,Ta=R[j],T[j]
    P=gunpts(f,r['keep']); Pw=(Ra@(r['L'][:,:3]@P.T+r['L'][:,3:4])).T+Ta
    t=np.zeros(3); d0=kd.query(Pw)[0].min()
    for it in range(30):
        d,idx=kd.query(Pw+t); i=d.argmin()
        if d[i]<=0.4: break
        # pull toward the body along the gun-to-body direction of the closest pair, and toward the body's centre line
        v=bv[idx[i]]-(Pw[i]+t); t+=v/np.linalg.norm(v)*min(d[i]-0.3,1.0)
    d1=kd.query(Pw+t)[0].min()
    tl=Ra.T@t
    out.append((r['length'],r['bone'],tl,d0,d1,r['model'],r['note']))
    print('%-28s %-14s %6d gap %.1f -> %.1f  shift %s'%(r['model'].split('/')[-1],r['bone'],r['length'],d0,d1,np.round(t,1)))
import json; json.dump([(o[0],o[1],[float(x) for x in o[2]],o[5],o[6]) for o in out],open('/tmp/holst_shift.json','w'))
