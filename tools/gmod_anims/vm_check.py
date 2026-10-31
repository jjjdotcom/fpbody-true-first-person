import sys, numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
sys.path.insert(0,'.')
G_={}; exec(open('holster_mock.py').read().split("HD = json.load")[0], G_)
gun_world_tris=G_['gun_world_tris']
names=sys.argv[2:]
fig,axes=plt.subplots(len(names),2,figsize=(10,2.6*len(names)))
def draw(ax,tris,view,ghost=None):
    up=np.array([0,0,1.]); v=view/np.linalg.norm(view); r=np.cross(v,up); r/=np.linalg.norm(r); u=np.cross(r,v)
    for T,alpha in ((ghost,0.25),(tris,1)):
        if T is None: continue
        pl,cl,dp=[],[],[]
        for P,c in T:
            n=np.cross(P[1]-P[0],P[2]-P[0]); nl=np.linalg.norm(n)
            if nl<1e-9: continue
            n/=nl
            if alpha==1 and n@v<0: continue
            pl.append(np.stack([P@r,P@u],1)); cl.append(np.clip(np.array(c)*(0.5+0.5*abs(n@v)),0,1) if alpha==1 else (0.9,0.2,0.2,0.25)); dp.append(-(P@v).mean())
        o=np.argsort(dp); ax.add_collection(PolyCollection([pl[i] for i in o],facecolors=[cl[i] for i in o],edgecolors='none'))
    ax.autoscale_view(); ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
for k,(nm) in enumerate(names):
    ref,new=nm.split('=')
    a=gun_world_tris(ref,lambda P:P); b=gun_world_tris(new,lambda P:P)
    draw(axes[k][0],b,np.array([0,-1.,0.]),a); axes[k][0].set_title(new.split('/')[-1]+' side (red = old model)',fontsize=8)
    draw(axes[k][1],b,np.array([0.2,-0.6,0.8]),a); axes[k][1].set_title('top',fontsize=8)
plt.tight_layout(); plt.savefig(sys.argv[1],dpi=70)
