"""Add Opposing Force's engineer / medic job animations to an fpbody player model.

  python3 -I add_jobs.py <hgrunt_torch.mdl> <hgrunt_medic.mdl> <in.mdl> <out.mdl>

The scripted sequences the engineer (monster_human_torch_ally) and the medic
(monster_human_medic_ally) play to cut doors open, open the floor grate and
heal a wounded soldier are retargeted onto the player skeleton (same Biped
bones: Thigh/Calf/Clavicle/UpperArm/Forearm become Leg/Leg1/Arm/Arm1/Arm2), so
the player can do those jobs himself (fpbody_jobs.inl, client fm_job_*):

  fm_job_pull_torch  <- pull_torch_wgun     fm_job_cut_door   <- cut_door_wgun
  fm_job_store_torch <- store_torch         fm_job_cut_grate  <- cut_floor_grate
  fm_job_kick        <- frontkick           fm_job_heal       <- heal_crouch (medic)
  fm_job_open_grate  <- open_floor_grate (medic)

Each bone takes the source bone's rotation and keeps the player's own length;
the root moves as the source's does from its standing pose, scaled to the
player's leg length. Bones the soldiers don't have (toes, fingers) keep the
player's standing pose. Sequences already in the model are replaced. The
result contains Gearbox's animation data: keep it local.
"""
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel                                  # noqa: E402
from compose import target_name                                   # noqa: E402
from add_cz import existing_sequences, textures_last              # noqa: E402

JOBS = [  # (source model, source sequence, our name, rate)
    ('torch', 'pull_torch_wgun', 'fm_job_pull_torch'),
    ('torch', 'cut_door_wgun', 'fm_job_cut_door'),
    ('torch', 'store_torch', 'fm_job_store_torch'),
    ('torch', 'cut_floor_grate', 'fm_job_cut_grate'),
    ('torch', 'frontkick', 'fm_job_kick'),
    ('medic', 'heal_crouch', 'fm_job_heal'),
    ('medic', 'open_floor_grate', 'fm_job_open_grate'),
]


def leg(G):
    r = G.rest_local()
    names = [('Bip01 L Leg1', 'Bip01 L Foot'), ('Bip01 L Calf', 'Bip01 L Foot')]
    for a, b in names:
        if a in G.bone_by_name and b in G.bone_by_name:
            return np.linalg.norm(r[G.bone_by_name[a], :3]) + np.linalg.norm(r[G.bone_by_name[b], :3])
    raise KeyError('no leg bones')


class Retarget:
    def __init__(self, C, M):
        self.C, self.M = C, M
        self.base = M.decode(M.seq_by_name['look_idle'])[0][0].copy()
        self.map = {}
        for i, b in enumerate(C.bones):
            t = target_name(b['name'])
            if t in M.bone_by_name:
                self.map[M.bone_by_name[t]] = i
        self.root = [i for i, b in enumerate(M.bones) if b['parent'] < 0]
        self.c_root = C.decode(C.seq_by_name['idle1'])[0][0][[self.map[r] for r in self.root], :3]
        self.k = leg(M) / leg(C)

    def frames(self, label):
        C = self.C
        src = C.decode(C.seq_by_name[label])[0]
        f = np.repeat(self.base[None], src.shape[0], axis=0)
        for mi, ci in self.map.items():
            f[:, mi, 3:6] = src[:, ci, 3:6]
        for j, r in enumerate(self.root):
            ci = self.map[r]
            f[:, r, :3] = self.base[r, :3] + (src[:, ci, :3] - self.c_root[j]) * self.k
        return [f]


def job_seq(C, R, label, name, template):
    s = C.seqs[C.seq_by_name[label]]
    import struct
    raw = bytearray(template['raw'])                 # bbox etc. from look_idle, no events
    lab = name.encode()[:31]
    raw[0:32] = lab + bytes(32 - len(lab))
    struct.pack_into('<2i', raw, 48, 0, 0)
    struct.pack_into('<i', raw, 40, 0)
    return dict(label=name, fps=s['fps'], flags=0, activity=0, actweight=0, motiontype=0, motionbone=0,
                linearmovement=[0, 0, 0], blendtype=[0, 0], blendstart=[0, 0], blendend=[1.0, 0],
                frames=R.frames(label), raw=bytes(raw))


def main(torch_path, medic_path, in_path, out_path):
    M = GoldSrcModel(in_path)
    src = {'torch': GoldSrcModel(torch_path), 'medic': GoldSrcModel(medic_path)}
    rt = {k: Retarget(v, M) for k, v in src.items()}
    seqs = existing_sequences(M)
    by = {s['label']: i for i, s in enumerate(seqs)}
    template = seqs[by['look_idle']]
    n = 0
    for who, label, name in JOBS:
        new = job_seq(src[who], rt[who], label, name, template)
        if name in by:
            seqs[by[name]] = new
        else:
            seqs.append(new)
        n += 1
    M.write(out_path, seqs)
    textures_last(out_path)
    return len(seqs), n


if __name__ == '__main__':
    print(main(*sys.argv[1:5]))
