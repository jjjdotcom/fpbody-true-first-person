"""Take a prop a soldier holds (a submodel of an NPC model) as a player p_ model.

  python3 -I npc_prop.py <npc.mdl> <bodypart> <submodel> <sequence:frame> <reference p_.mdl> <out p_.mdl>

The submodel's triangles are posed with the NPC's sequence frame, moved into the
space of the NPC's right hand, and written on the reference p_ model's
skeleton (every vertex on "Bip01 R Hand"), so the prop sits in the player's
hand as it does in the soldier's. Used for Opposing Force's blowtorch
(hgrunt_torch.mdl, weapons 1) and the medic's hypodermic (hgrunt_medic.mdl,
weapons 2) the player uses for the engineer / medic jobs. The result contains
Gearbox's model data: keep it local.
"""
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from compose import Source                     # noqa: E402
from goldsrc import GoldSrcModel               # noqa: E402
import vm2p                                    # noqa: E402


def main(npc, bodypart, sub, pose, ref, out):
    S = Source(npc)
    seq, frame = pose.split(':')
    M = S.m
    arr = M.decode(M.seq_by_name[seq])[0]
    R, T = M.world(arr[min(int(frame), len(arr) - 1)])
    h = M.bone_by_name['Bip01 R Hand']
    mdl = S.model(int(bodypart), int(sub))
    hand = {h}                                    # the hand and the bones under it
    for i, b in enumerate(M.bones):
        if b['parent'] in hand:
            hand.add(i)
    tris = []
    for mesh in mdl['meshes']:
        for tri in mesh['tris']:
            if any(mdl['vb'][v[0]] not in hand for v in tri):
                continue                          # parts on the belt etc. (holster, tank)
            P = np.array([R[mdl['vb'][v[0]]] @ mdl['vv'][v[0]] + T[mdl['vb'][v[0]]] for v in tri])
            N = np.array([R[mdl['nb'][v[1]]] @ mdl['nv'][v[1]] for v in tri])
            P = (P - T[h]) @ R[h]                 # into the hand's space
            N = N @ R[h]
            tris.append((P, N, [(v[2], v[3]) for v in tri], mesh['tex']))
    G = GoldSrcModel(ref)
    hi = G.bone_by_name['Bip01 R Hand']
    print(vm2p.write(ref, hi, tris, S, out))


if __name__ == '__main__':
    main(*sys.argv[1:7])
