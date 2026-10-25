import sys, struct, math; sys.path.insert(0,'/home/claude/gmodconv')
import numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from goldsrc import GoldSrcModel
from viz import draw

GUNS = {}
import re
for line in open('out/gun_table.inc'):
    if line.strip().startswith('{ "'):
        name = line.split('"')[1]
        nums = [float(x) for x in re.findall(r'-?\d+\.\d+', line)]
        GUNS[name] = (np.array(nums[0:3]), np.array(nums[3:6]), nums[6])

def axis_angle(axis, ang):
    x,y,z = axis; c,s=math.cos(ang),math.sin(ang); t=1-c
    return np.array([[t*x*x+c,t*x*y-s*z,t*x*z+s*y],[t*x*y+s*z,t*y*y+c,t*y*z-s*x],[t*x*z-s*y,t*y*z+s*x,t*z*z+c]])

class Pose:
    def __init__(s, m, loc):
        s.m=m; s.R, s.T = m.world(loc)
        s.par=[b['parent'] for b in m.bones]
    def sub(s, root):
        mask={root}
        for i,p in enumerate(s.par):
            if p in mask: mask.add(i)
        return mask
    def rot(s, mask, W, pivot):
        for i in mask:
            s.R[i]=W@s.R[i]; s.T[i]=W@(s.T[i]-pivot)+pivot
    def turn(s, mask, pivot, a, b, w=1.0):
        a=a/np.linalg.norm(a); b=b/np.linalg.norm(b); ax=np.cross(a,b); sn=np.linalg.norm(ax)
        if sn<1e-6: return
        s.rot(mask, axis_angle(ax/sn, math.atan2(sn, np.dot(a,b))*w), pivot)

def angle_at(a,c,b):
    u=(a-c)/np.linalg.norm(a-c); v=(b-c)/np.linalg.norm(b-c); return math.acos(np.clip(np.dot(u,v),-1,1))

def reach(P, target):
    b=P.m.bone_by_name
    up,fo,ha=b['Bip01 L Arm1'],b['Bip01 L Arm2'],b['Bip01 L Hand']
    S,E,H=P.T[up].copy(),P.T[fo].copy(),P.T[ha].copy()
    a=np.linalg.norm(E-S); bb=np.linalg.norm(H-E); d=np.clip(np.linalg.norm(target-S),abs(a-bb)+.1,a+bb-.1)
    cur=angle_at(S,E,H); des=math.acos(np.clip((a*a+bb*bb-d*d)/(2*a*bb),-1,1))
    n=np.cross(E-S,H-E); n/=np.linalg.norm(n)
    W=axis_angle(n,des-cur); h1=W@(H-E)+E
    if abs(angle_at(S,E,h1)-des)>abs(cur-des): W=axis_angle(n,-(des-cur))
    P.rot(P.sub(fo),W,E)
    P.turn(P.sub(up),S,P.T[ha]-S,target-S)

def gun_pose(P, gun, fwd, aim):
    b=P.m.bone_by_name; rh,ru=b['Bip01 R Hand'],b['Bip01 R Arm1']
    axis,grip,down=GUNS[gun]
    if aim: P.turn(P.sub(ru),P.T[ru].copy(),P.R[rh]@axis,fwd)
    target=P.T[rh]+P.R[rh]@grip; target[2]-=down
    reach(P,target)
    return target

def gun_points(m_path, P):
    """p_ mesh vertices placed on the body's right hand"""
    g=GoldSrcModel(m_path); d=bytes(g.d); R,T=g.world(g.decode(0)[0][0])
    hi=g.bone_by_name['Bip01 R Hand']; sub={hi}
    for i,bn in enumerate(g.bones):
        if bn['parent'] in sub: sub.add(i)
    numbp,bpi=struct.unpack_from('<2i',d,204); pts=[]
    for p in range(numbp):
        nm,base,mi=struct.unpack_from('<3i',d,bpi+p*76+64)
        for k in range(nm):
            mo=mi+k*112; nv,vinfo,vidx=struct.unpack_from('<3i',d,mo+80)
            for v in range(nv):
                if d[vinfo+v] in sub:
                    pv=np.array(struct.unpack_from('<3f',d,vidx+v*12)); w=R[d[vinfo+v]]@pv+T[d[vinfo+v]]
                    pts.append(R[hi].T@(w-T[hi]))
    rh=P.m.bone_by_name['Bip01 R Hand']
    return np.array([P.R[rh]@p+P.T[rh] for p in pts])

def reach_side(P, side, target):
    b=P.m.bone_by_name
    up,fo,ha=b['Bip01 %s Arm1'%side],b['Bip01 %s Arm2'%side],b['Bip01 %s Hand'%side]
    S,E,H=P.T[up].copy(),P.T[fo].copy(),P.T[ha].copy()
    a=np.linalg.norm(E-S); bb=np.linalg.norm(H-E); d=np.clip(np.linalg.norm(target-S),abs(a-bb)+.1,a+bb-.1)
    cur=angle_at(S,E,H); des=math.acos(np.clip((a*a+bb*bb-d*d)/(2*a*bb),-1,1))
    n=np.cross(E-S,H-E); n/=np.linalg.norm(n)
    W=axis_angle(n,des-cur); h1=W@(H-E)+E
    if abs(angle_at(S,E,h1)-des)>abs(cur-des): W=axis_angle(n,-(des-cur))
    P.rot(P.sub(fo),W,E)
    P.turn(P.sub(up),S,P.T[ha]-S,target-S)

def pistol_pose(P, gun, f, fwd_dist=15.0, drop=4.0, right=1.5):
    b=P.m.bone_by_name; rh=b['Bip01 R Hand']
    mid=(P.T[b['Bip01 R Arm1']]+P.T[b['Bip01 L Arm1']])/2
    r=np.cross(f,[0,0,1.0]); r/=np.linalg.norm(r)       # right
    u=np.cross(r,f)
    reach_side(P,'R',mid+f*fwd_dist-u*drop+r*right)
    axis,grip,down=GUNS[gun]
    P.turn(P.sub(rh),P.T[rh].copy(),P.R[rh]@axis,f)       # wrist points the gun
    target=P.T[rh]+P.R[rh]@grip; target[2]-=down
    reach_side(P,'L',target)
    return target
