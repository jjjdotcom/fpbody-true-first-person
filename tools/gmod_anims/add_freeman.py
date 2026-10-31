"""Add the Half-Life 2: Freeman mod's player animations to an fpbody player model.

  python3 -I add_freeman.py <Freeman models folder> <in.mdl> <out.mdl> [classic|gmod]

The Freeman mod (Source) plays kicks, vaults, wall climbing, prone, falls,
hard landings, rolls, a lowered ("at ease") weapon, empty hands, weapon draws
and a slide from several Garry's Mod Workshop animation packs. This retargets
them (ValveBiped -> Bip01, see retarget.py) and appends them as fm_<name>
sequences, which the client plays by name (cl_dll/fpbody_anim.cpp), plus the
"unarmed" weapon hold (ref_/crouch_ aim/shoot_unarmed) the server picks with
the holster-all command.

Packs (the files are in Freeman/models, keep the result local - it contains
third-party animation data):
  akick/kick_anim_m.mdl                     kicks and stomps
  mixamomovement/mixamomovementanims.mdl    mantle, vault, pull-up, climb, hard landing, roll
  player/wiltos/anim_extension_prone.mdl    prone
  ram/fall.mdl                              falling
  xdreanims/m_anm_slot_042.mdl              weapon draws
  blackops_iii_special_anims/bo3_pb_male_enh_anims.mdl   slide
  m_anm_gmod.mdl + m_anm.ani                Garry's Mod passive and unarmed sets

"classic" models (Half-Life's own skeleton heights) put the feet 18 units
below the origin for anything played while ducked (Half-Life moves the origin
to the duck hull's centre); "gmod" (fpbody/models/player.mdl) keeps its own
convention of 36 for everything.
"""
import struct
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from srcmdl import SourceModel                    # noqa: E402
from goldsrc import GoldSrcModel                  # noqa: E402
import retarget                                   # noqa: E402
from retarget import Retargeter                   # noqa: E402
from add_cz import existing_sequences, textures_last   # noqa: E402

STAND, DUCK = -36.0, -18.0

# out label: (pack, source sequence or animation (@name / a_name), ducked, loop, upper body only)
SEQS = {
    # kicks (the plain sequences are an empty pose with the motion in a layer; *_base is the motion)
    'fm_kick':        ('kick', 'kick_pistol_base', False, False),
    'fm_kick_45':     ('kick', 'kick_pistol_45_base', False, False),
    'fm_kick_25':     ('kick', 'kick_pistol_25_base', False, False),
    'fm_kick_crouch': ('kick', 'kick_pistol_base_crouch', True, False),
    'fm_stomp':       ('kick', 'curbstomp_base', False, False),
    'fm_stomp_crouch': ('kick', 'curbstomp_crouch_base', True, False),
    'fm_kick_air':    ('kick', 'kick_midair_base', False, False),
    'fm_kick_air_45': ('kick', 'kick_midair_45_base', False, False),
    'fm_kick_air_25': ('kick', 'kick_midair_25_base', False, False),
    'fm_stomp_air':   ('kick', 'curbstomp_midair_base', False, False),
    # vault / climb
    'fm_mantle':      ('mixamo', 'wos_mma_mantle', False, False),
    'fm_vault':       ('mixamo', 'wos_mma_vault', False, False),
    'fm_pullup':      ('mixamo', 'wos_mma_bracedhang_to_crouch', False, False),
    'fm_climb':       ('mixamo', 'wos_mma_climbladder_up', False, True),
    # falls and landings
    'fm_fall':        ('fall', 'fall', False, True),
    'fm_hardland':    ('mixamo', 'wos_mma_hardlanding', False, False),
    'fm_standup_front': ('mixamo', 'wos_mma_standup_front01', False, False),
    'fm_standup_back': ('mixamo', 'wos_mma_standup_back01', False, False),
    'fm_roll':        ('mixamo', 'wos_mma_roll', False, False),
    # slide
    'fm_slide':       ('bo3', 'pb_rifle_fem_run_slide', True, False),
    # weapon draws (the motion is in the *_base_layer sequences)
    'fm_draw_pistol': ('draw', 'draw_pistol_base_layer', False, False),
    'fm_draw_rifle':  ('draw', 'draw_rifle_base_layer', False, False),
    'fm_draw_rpg':    ('draw', 'draw_rpg_base_layer', False, False),
    'fm_draw_melee':  ('draw', 'draw_melee_base_layer', False, False),
    'fm_draw_physgun': ('draw', 'draw_physgun_base_layer', False, False),
    # at ease (lowered weapon)
    'fm_passive_idle':  ('gmod', '@idle_passive', False, True),
    'fm_passive_walk':  ('gmod', 'a_walking_walk_passive_N', False, True),
    'fm_passive_run':   ('gmod', 'a_running_run_passive_N', False, True),
    # prone transitions (Half-Life keeps the duck hull while prone)
    'fm_pronedown_stand':  ('prone', 'pronedown_stand', True, False),
    'fm_pronedown_crouch': ('prone', 'pronedown_crouch', True, False),
    'fm_proneup_stand':    ('prone', 'proneup_stand', True, False),
    'fm_proneup_crouch':   ('prone', 'proneup_crouch', True, False),
}
for hold in ('passive', 'pistol', 'revolver', 'smg1', 'ar2', 'shotgun', 'rpg', 'crossbow', 'physgun', 'melee',
             'grenade', 'slam'):
    SEQS['fm_prone_' + hold] = ('prone', 'prone_' + hold, True, True)
for walk in ('passive', 'onehand', 'twohand', 'rpg', 'crossbow', 'physgun'):
    SEQS['fm_pronewalk_' + walk] = ('prone', 'prone_walk' + walk, True, True)

# the empty-hands weapon hold, looked up by the server as <stance>_<part>_unarmed
UNARMED = {'ref_aim_unarmed': ('gmod', '@idle_all_01', False), 'ref_shoot_unarmed': ('gmod', '@idle_all_01', False),
           'crouch_aim_unarmed': ('gmod', '@cidle_all', True), 'crouch_shoot_unarmed': ('gmod', '@cidle_all', True)}

PACKS = {
    'kick': ('akick/kick_anim_m.mdl', None),
    'mixamo': ('mixamomovement/mixamomovementanims.mdl', None),
    'prone': ('player/wiltos/anim_extension_prone.mdl', None),
    'fall': ('ram/fall.mdl', None),
    'draw': ('xdreanims/m_anm_slot_042.mdl', None),
    'bo3': ('blackops_iii_special_anims/bo3_pb_male_enh_anims.mdl', None),
    'gmod': ('m_anm_gmod.mdl', 'm_anm.ani'),
}


class PackRetargeter(Retargeter):
    """Retargeter for an animation pack: the rest pose the animations were made
    for is the Garry's Mod player's (some packs were compiled on a skeleton in
    another bind pose), and the origin height depends on the stance."""

    def __init__(self, src, tgt, ref):
        super().__init__(src, tgt)
        rpos = np.array([b['pos'] for b in ref.bones]); rquat = np.array([b['quat'] for b in ref.bones])
        Rr, Tr = ref.world(rpos, rquat)
        for i, b in enumerate(src.bones):
            j = ref.bone_by_name.get(b['name'])
            if j is not None:
                self.Rs0[i] = Rr[j]; self.Ts0[i] = Tr[j]
        # direction corrections and height scale against the reference rest pose
        for tn, sn in retarget.MAP:
            ti = tgt.bone_by_name[tn]
            ch = retarget.DIR_CHILD.get(tn)
            if ch is None:
                continue
            ci = tgt.bone_by_name[ch]
            dt = self.Tt0[ci] - self.Tt0[ti]
            dv = self.Ts0[self.src_of[ci]] - self.Ts0[self.src_of[ti]]
            self.C[ti] = retarget.rot_between(dt, dv)
        for tn, sn in retarget.MAP:              # bones without a direction child follow the parent
            ti = tgt.bone_by_name[tn]
            if retarget.DIR_CHILD.get(tn) is None:
                self.C[ti] = self.C.get(tgt.bones[ti]['parent'], np.eye(3))
        tp = self.Tt0[tgt.bone_by_name['Bip01 Pelvis']][2] - self.Tt0[tgt.bone_by_name['Bip01 L Toe0']][2]
        sp = Tr[ref.bone_by_name[retarget.VB + 'Pelvis']][2] - Tr[ref.bone_by_name[retarget.VB + 'L_Toe0']][2]
        self.scale = tp / sp

    def frames(self, poses, zoff):
        retarget.ZOFFSET = zoff
        try:
            return np.array([self.pose(p, q) for p, q in poses])
        finally:
            retarget.ZOFFSET = STAND


def source_anim(g, name):
    if name.lower() in g.seq_by_name and not name.startswith(('@', 'a_')):
        s = g.seq_by_name[name.lower()]
        return g.anims[s['anims'][len(s['anims']) // 2] if len(s['anims']) > 1 else s['anims'][0]]
    return g.anim_by_name[name]


def make_seq(label, frames, fps, loop, template):
    d = dict(label=label[:31], fps=float(fps), flags=1 if loop else 0, activity=0, actweight=0,
             motiontype=0, motionbone=0, linearmovement=[0, 0, 0],
             blendtype=[0, 0], blendstart=[0, 0], blendend=[1.0, 0], frames=[frames])
    raw = bytearray(template['raw'])          # bbox etc. from a Half-Life sequence, no events
    struct.pack_into('<2i', raw, 48, 0, 0)
    struct.pack_into('<2i', raw, 60, 0, 0)
    struct.pack_into('<6i', raw, 152, 0, 0, 0, 0, 0, 0)
    d['raw'] = bytes(raw)
    return d


def main(folder, in_path, out_path, kind='classic'):
    folder = folder.rstrip('/') + '/'
    M = GoldSrcModel(in_path)
    seqs = [s for s in existing_sequences(M) if not s['label'].startswith('fm_') and not s['label'].endswith('_unarmed')]
    by = {s['label']: s for s in seqs}
    template = by.get('look_idle') or seqs[0]
    ref = SourceModel(folder + PACKS['gmod'][0], folder + PACKS['gmod'][1])
    packs, rts = {}, {}
    duck = STAND if kind == 'gmod' else DUCK
    added = []

    def build(label, pack, name, ducked, loop):
        if pack not in packs:
            m, a = PACKS[pack]
            packs[pack] = ref if pack == 'gmod' else SourceModel(folder + m, folder + a if a else None)
            rts[pack] = PackRetargeter(packs[pack], M, ref)
        g = packs[pack]
        a = source_anim(g, name)
        fr = rts[pack].frames(g.frames(a), duck if ducked else STAND)
        added.append(make_seq(label, fr, a['fps'], loop, template))

    for label, (pack, name, ducked, loop) in SEQS.items():
        build(label, pack, name, ducked, loop)
    for label, (pack, name, ducked) in UNARMED.items():
        build(label, pack, name, ducked, True)
    seqs += added
    M.write(out_path, seqs)
    textures_last(out_path)
    return len(seqs), len(added), M.downsampled


if __name__ == '__main__':
    print(main(*sys.argv[1:5]))
