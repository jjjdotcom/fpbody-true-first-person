"""Lets the fpbody renderer draw the right animations on a body model whose
sequence order differs from the server's player.mdl (translates by name).

  python3 seq_remap.py <sdk folder>

Needs fpbody_anim.cpp/.h with FPAnim_MapSeq and g_fpSeqRemapped.
"""
import os
import sys
REMAP_STRUCT = ('// fpbody: marks the local entity\'s sequence as already translated into the\n'
 '// drawn model, and maps its previous sequence for the blend\n'
 'struct FPSeqRemap\n{\n\tbool on = false;\n\tcl_entity_t* ent = nullptr;\n\tint prevsequence = 0;\n\n'
 '\tvoid Begin(cl_entity_t* e, int mappedPrev)\n\t{\n\t\ton = true;\n\t\tent = e;\n'
 '\t\tprevsequence = e->latched.prevsequence;\n\t\te->latched.prevsequence = mappedPrev;\n\t\tg_fpSeqRemapped = 1;\n\t}\n'
 '\t~FPSeqRemap()\n\t{\n\t\tif (!on)\n\t\t\treturn;\n\t\tent->latched.prevsequence = prevsequence;\n\t\tg_fpSeqRemapped = 0;\n\t}\n};\n\n')
EDITS = [
 ('struct FPOverlayRestore\n{\n', REMAP_STRUCT + 'struct FPOverlayRestore\n{\n'),
 ('\t\tmodel_t* outfit = FPBody_GetOutfitModel(pplayer->number);\n\t\tif (outfit)\n\t\t\tm_pRenderModel = outfit;\n\t}\n',
  '\t\tmodel_t* outfit = FPBody_GetOutfitModel(pplayer->number);\n\t\tif (outfit)\n\t\t{\n\t\t\tm_pRenderModel = outfit;\n\t\t\tfpOutfit = true;\n\t\t}\n\t}\n'),
 ('\t// fpbody: the outfit before / after the suit\n\t{\n', '\t// fpbody: the outfit before / after the suit\n\tbool fpOutfit = false;\n\t{\n'),
 ('\t// fpbody: GMod gestures / taunts / reloads on the local player\n\tentity_state_t fpState;\n\tFPOverlayRestore fpRestore;\n\t{\n',
  '\t// fpbody: the server numbers our sequences in its own player model\n'
  '\t// (models/player.mdl); when the body is drawn with another model, play the\n'
  '\t// sequences of the same name in it\n'
  '\tentity_state_t fpState;\n\tFPOverlayRestore fpSeqRestore;\n\tFPSeqRemap fpRemap;\n'
  '\tif (fpOutfit && m_pRenderModel != m_pCurrentEntity->model && m_pCurrentEntity->model && m_pCurrentEntity->model->type == mod_studio)\n\t{\n'
  '\t\tconst void* srvHdr = IEngineStudio.Mod_Extradata(m_pCurrentEntity->model);\n'
  '\t\tint seq = FPAnim_MapSeq(srvHdr, m_pStudioHeader, m_pCurrentEntity->curstate.sequence);\n'
  '\t\tint gait = FPAnim_MapSeq(srvHdr, m_pStudioHeader, pplayer->gaitsequence);\n'
  '\t\tfpSeqRestore.Save(m_pCurrentEntity);\n'
  '\t\tfpRemap.Begin(m_pCurrentEntity, FPAnim_MapSeq(srvHdr, m_pStudioHeader, m_pCurrentEntity->latched.prevsequence));\n'
  '\t\tfpState = *pplayer;\n\t\tfpState.sequence = seq;\n\t\tfpState.gaitsequence = gait;\n'
  '\t\tm_pCurrentEntity->curstate.sequence = seq;\n\t\tpplayer = &fpState;\n\t}\n\n'
  '\t// fpbody: GMod gestures / taunts / reloads on the local player\n\tFPOverlayRestore fpRestore;\n\t{\n'),
]
def apply(path):
    s=open(path,encoding='latin-1',newline='').read()
    if 'FPSeqRemap' in s: print('already',path); return
    nl='\r\n' if '\r\n' in s else '\n'
    for a,b in EDITS:
        a2=a.replace('\n',nl); b2=b.replace('\n',nl)
        assert s.count(a2)==1,(path,a[:60],s.count(a2))
        s=s.replace(a2,b2)
    open(path,'w',encoding='latin-1',newline='').write(s); print('patched',path)


def main(sdk):
    apply(os.path.join(sdk, 'cl_dll', 'StudioModelRenderer.cpp'))


if __name__ == '__main__':
    main(sys.argv[1])
