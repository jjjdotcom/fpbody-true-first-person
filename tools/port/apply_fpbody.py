"""Apply the True First Person (fpbody) client code to a Half-Life Updated
based SDK: Blue Shift Updated or Opposing Force Updated (twhl-community).

  python3 tools/port/apply_fpbody.py <path to SDK> bshift|op4

Copies cl_dll/fpbody*.cpp/.h from this repository, writes the per-game
cl_dll/fpbody_game.h and adds the hooks to the SDK's client sources and
Visual Studio project. Safe to run once on a fresh checkout; it stops with an
error if an anchor it looks for isn't there.
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

GAMES = {
    'bshift': dict(moddir='fpbody_bs', fallback='bshift', title='Blue Shift: True First Person',
                   startmap='ba_tram1', trainmap='ba_hazard1', armor=1),
    'op4': dict(moddir='fpbody_op4', fallback='gearbox', title='Opposing Force: True First Person',
                startmap='of0a0', trainmap='ofboot0', armor=0),
}


def patch(path, edits):
    s = open(path, encoding='utf-8', newline='').read()
    nl = '\r\n' if '\r\n' in s else '\n'
    s = s.replace('\r\n', '\n')
    if 'fpbody' in s:
        print('already patched:', path)
        return
    for old, new, count in edits:
        n = s.count(old)
        if n != count:
            sys.exit('%s: expected %d of %r, found %d' % (path, count, old[:60], n))
        s = s.replace(old, new)
    open(path, 'w', encoding='utf-8', newline='').write(s.replace('\n', nl))
    print('patched', path)


def main():
    sdk, game = sys.argv[1], sys.argv[2]
    g = GAMES[game]
    cl = os.path.join(sdk, 'cl_dll')

    for f in ('fpbody.cpp', 'fpbody.h', 'fpbody_anim.cpp', 'fpbody_anim.h'):
        shutil.copy(os.path.join(REPO, 'cl_dll', f), os.path.join(cl, f))
    open(os.path.join(cl, 'fpbody_game.h'), 'w').write(
        '// fpbody_game.h - per-game settings for the True First Person code (%s).\n'
        '#ifndef FPBODY_GAME_H\n#define FPBODY_GAME_H\n\n'
        '#define FPBODY_SUIT_FROM_ARMOR %d\t// 1 = "suited" while the player has armor\n\n'
        '// pm_shared is C++ in the Updated SDKs\n#define FPBODY_DECLARE_ONLADDER extern bool g_onladder;\n\n#endif\n'
        % (g['title'], g['armor']))

    patch(os.path.join(cl, 'StudioModelRenderer.cpp'), [
        ('#include "GameStudioModelRenderer.h"\n',
         '#include "GameStudioModelRenderer.h"\n#include "fpbody.h"\n#include "fpbody_anim.h"\n\n'
         '// fpbody: restores the entity fields an overlay animation changed, on any\n'
         '// return path out of StudioDrawPlayer\n'
         'struct FPOverlayRestore\n{\n'
         '\tcl_entity_t* ent = nullptr;\n\tbool saved = false;\n\tint sequence = 0;\n'
         '\tfloat frame = 0, animtime = 0, framerate = 0, pitch = 0;\n\n'
         '\tvoid Save(cl_entity_t* e)\n\t{\n\t\tent = e;\n\t\tsaved = true;\n'
         '\t\tsequence = e->curstate.sequence;\n\t\tframe = e->curstate.frame;\n'
         '\t\tanimtime = e->curstate.animtime;\n\t\tframerate = e->curstate.framerate;\n'
         '\t\tpitch = e->curstate.angles[0];\n\t}\n'
         '\t~FPOverlayRestore()\n\t{\n\t\tif (!saved)\n\t\t\treturn;\n'
         '\t\tent->curstate.sequence = sequence;\n\t\tent->curstate.frame = frame;\n'
         '\t\tent->curstate.animtime = animtime;\n\t\tent->curstate.framerate = framerate;\n'
         '\t\tent->curstate.angles[0] = pitch;\n\t}\n};\n', 1),
        ('\tm_pRenderModel = IEngineStudio.SetupPlayerModel(m_nPlayerIndex);\n\n\n\tif (m_pRenderModel == NULL)\n',
         '\tm_pRenderModel = IEngineStudio.SetupPlayerModel(m_nPlayerIndex);\n\n'
         '\t// fpbody: the outfit before / after the suit\n\t{\n'
         '\t\tmodel_t* outfit = FPBody_GetOutfitModel(pplayer->number);\n'
         '\t\tif (outfit)\n\t\t\tm_pRenderModel = outfit;\n\t}\n\n'
         '\tif (m_pRenderModel == NULL)\n', 1),
        ('\tIEngineStudio.SetRenderModel(m_pRenderModel);\n\n\tif (0 != pplayer->gaitsequence)\n',
         '\tIEngineStudio.SetRenderModel(m_pRenderModel);\n\n'
         '\t// fpbody: GMod gestures / taunts / reloads on the local player\n'
         '\tentity_state_t fpState;\n\tFPOverlayRestore fpRestore;\n\t{\n'
         '\t\tint ovSeq, ovFull;\n\t\tfloat ovTime, ovRate;\n'
         '\t\tif (FPAnim_GetOverlay(pplayer->number, m_pStudioHeader, &ovSeq, &ovTime, &ovRate, &ovFull))\n\t\t{\n'
         '\t\t\tfpRestore.Save(m_pCurrentEntity);\n\t\t\tfpState = *pplayer;\n\t\t\tfpState.sequence = ovSeq;\n'
         '\t\t\tif (ovFull)\n\t\t\t{\n'
         '\t\t\t\tfpState.gaitsequence = 0;					// whole body plays the act\n'
         '\t\t\t\tm_pCurrentEntity->curstate.angles[0] = 0;	// don\'t tilt it with the view\n\t\t\t}\n'
         '\t\t\tm_pCurrentEntity->curstate.sequence = ovSeq;\n\t\t\tm_pCurrentEntity->curstate.frame = 0;\n'
         '\t\t\tm_pCurrentEntity->curstate.animtime = ovTime;\n'
         '\t\t\tm_pCurrentEntity->curstate.framerate = ovRate;\n\t\t\tpplayer = &fpState;\n\t\t}\n\t}\n\n'
         '\tif (0 != pplayer->gaitsequence)\n', 1),
        ('\tm_pPlayerInfo = IEngineStudio.PlayerInfo(m_nPlayerIndex);\n\tStudioSetupBones();\n\tStudioSaveBones();\n',
         '\tm_pPlayerInfo = IEngineStudio.PlayerInfo(m_nPlayerIndex);\n\tStudioSetupBones();\n\n'
         '\t// fpbody: animate the arms, remember where our head is and collapse it so\n'
         '\t// it\'s not in the way. Done before StudioSaveBones so the weapon model in\n'
         '\t// the hands is merged onto the animated bones.\n'
         '\tif ((flags & STUDIO_RENDER) != 0)\n\t{\n'
         '\t\tFPBody_ProcessPlayerBones(pplayer->number, m_pCurrentEntity, m_pStudioHeader,\n'
         '\t\t\t*m_pbonetransform, *m_plighttransform, pplayer->weaponmodel);\n\t}\n\n'
         '\tStudioSaveBones();\n', 1),
        ('\t\tStudioSetUpTransform(false);\n',
         '\t\tFPBody_LevelBody(pplayer->number, m_pCurrentEntity); // fpbody: keep our body upright\n'
         '\t\tStudioSetUpTransform(false);\n', 2),
    ])

    patch(os.path.join(cl, 'com_weapons.cpp'), [
        ('\tg_currentanim = iAnim;\n',
         '\tg_currentanim = iAnim;\n\n\t// fpbody: body animations follow the weapon\'s actions\n'
         '\tFPAnim_OnWeaponAnim(iAnim, HUD_GetViewModelIndex());\n', 1),
        ('void HUD_SendWeaponAnim(',
         'void FPAnim_OnWeaponAnim(int iAnim, int viewmodelIndex);\nint HUD_GetViewModelIndex();\n\n'
         'void HUD_SendWeaponAnim(', 1),
    ])

    weap = os.path.join(cl, 'hl', 'hl_weapons.cpp')
    patch(weap, [
        ('static CBasePlayer player;\n',
         'static CBasePlayer player;\n\n// fpbody: current view model index, used to name weapon animations\n'
         'int HUD_GetViewModelIndex()\n{\n\treturn player.pev ? player.pev->viewmodel : 0;\n}\n', 1),
    ])

    hud = os.path.join(cl, 'hud.h')
    s = open(hud, encoding='utf-8', newline='').read()
    if 'fpbody' not in s:
        nl = '\r\n' if '\r\n' in s else '\n'
        s = s.replace('\r\n', '\n')
        for cls, line in (('class CHudFlashlight', '\tbool IsOn() const { return m_fOn; } // fpbody: flashlight animation\n'),
                          ('class CHudBattery', '\tint GetArmor() const { return m_iBat; } // fpbody: outfit with armor\n')):
            k = s.index(cls)
            k = s.index('public:\n', k) + len('public:\n')
            s = s[:k] + line + s[k:]
        open(hud, 'w', encoding='utf-8', newline='').write(s.replace('\n', nl))
        print('patched', hud)

    patch(os.path.join(cl, 'in_camera.cpp'), [
        ('#include "Exports.h"\n', '#include "Exports.h"\n#include "fpbody.h"\n', 1),
        ('int DLLEXPORT CL_IsThirdPerson()\n{\n\t//	RecClCL_IsThirdPerson();\n\n'
         '\treturn static_cast<int>(cam_thirdperson || (0 != g_iUser1 && (g_iUser2 == gEngfuncs.GetLocalPlayer()->index)));\n}\n',
         '// True only for the real chase camera ("thirdperson" command / spectating yourself).\n'
         'int CAM_IsRealThirdPerson()\n{\n'
         '\treturn static_cast<int>(cam_thirdperson || (0 != g_iUser1 && (g_iUser2 == gEngfuncs.GetLocalPlayer()->index)));\n}\n\n'
         'int DLLEXPORT CL_IsThirdPerson()\n{\n\t//	RecClCL_IsThirdPerson();\n\n'
         '\t// fpbody: tell the engine to draw our own body while the camera sits in its head\n'
         '\treturn static_cast<int>(0 != CAM_IsRealThirdPerson() || 0 != FPBody_Active());\n}\n', 1),
    ])

    patch(os.path.join(cl, 'view.cpp'), [
        ('#include "Exports.h"\n', '#include "Exports.h"\n#include "fpbody.h"\n#include "fpbody_anim.h"\n', 1),
        ('int CL_IsThirdPerson();\n', 'int CL_IsThirdPerson();\nint CAM_IsRealThirdPerson();\n', 1),
        ('\tVectorAdd(pparams->vieworg, pparams->viewheight, pparams->vieworg);\n',
         '\tVectorAdd(pparams->vieworg, pparams->viewheight, pparams->vieworg);\n\n'
         '\t// fpbody: put the camera in the head of the player model. The head\'s own\n'
         '\t// animation replaces the artificial view bob.\n'
         '\t{\n\t\tVector headorg;\n\t\tif (0 != FPBody_GetViewOrigin(pparams, headorg))\n'
         '\t\t\tVectorCopy(headorg, pparams->vieworg);\n\t}\n', 1),
        ('if (0 != CL_IsThirdPerson())', 'if (0 != CAM_IsRealThirdPerson())', 2),
        ('\tV_DropPunchAngle(pparams->frametime, (float*)&ev_punchangle);\n',
         '\tV_DropPunchAngle(pparams->frametime, (float*)&ev_punchangle);\n\n'
         '\t// fpbody: the view tilts and bobs with the body\'s head\n'
         '\t{\n\t\tVector headofs;\n\t\tFPAnim_GetViewAngleOffset(headofs);\n'
         '\t\tVectorAdd(pparams->viewangles, headofs, pparams->viewangles);\n\t}\n', 1),
        ('\t//	RecClCalcRefdef(pparams);\n\n\t// intermission / finale rendering\n',
         '\t//	RecClCalcRefdef(pparams);\n\n\tFPBody_BeginFrame(pparams);\n\n\t// intermission / finale rendering\n', 1),
        ('\tcl_chasedist = gEngfuncs.pfnRegisterVariable("cl_chasedist", "112", 0);\n',
         '\tcl_chasedist = gEngfuncs.pfnRegisterVariable("cl_chasedist", "112", 0);\n\n\tFPBody_Init();\n', 1),
    ])

    proj = os.path.join(sdk, 'projects', 'vs2019', 'hl_cdll.vcxproj')
    patch(proj, [
        ('    <ClCompile Include="..\\..\\cl_dll\\in_camera.cpp" />\n',
         '    <ClCompile Include="..\\..\\cl_dll\\fpbody.cpp" />\n'
         '    <ClCompile Include="..\\..\\cl_dll\\fpbody_anim.cpp" />\n'
         '    <ClCompile Include="..\\..\\cl_dll\\in_camera.cpp" />\n', 1),
        ('    <ClInclude Include="..\\..\\cl_dll\\in_defs.h" />\n',
         '    <ClInclude Include="..\\..\\cl_dll\\fpbody.h" />\n'
         '    <ClInclude Include="..\\..\\cl_dll\\fpbody_anim.h" />\n'
         '    <ClInclude Include="..\\..\\cl_dll\\fpbody_game.h" />\n'
         '    <ClInclude Include="..\\..\\cl_dll\\in_defs.h" />\n', 1),
    ])

    # build output goes to the mod folder next to the SDK folder
    fc = os.path.join(sdk, 'filecopy.bat')
    s = open(fc, encoding='utf-8', newline='').read()
    s2 = re.sub(r'set mod_directory=.*', lambda m: 'set mod_directory=%~dp0..\\' + g['moddir'] + '\r', s)
    if s2 != s:
        open(fc, 'w', encoding='utf-8', newline='').write(s2)
        print('patched', fc)

    mod = os.path.join(sdk, '..', g['moddir'])
    os.makedirs(os.path.join(mod, 'cl_dlls'), exist_ok=True)
    os.makedirs(os.path.join(mod, 'dlls'), exist_ok=True)
    os.makedirs(os.path.join(mod, 'models'), exist_ok=True)
    open(os.path.join(mod, 'liblist.gam'), 'w', newline='\r\n').write(
        'game "%s"\ngamedir "%s"\nfallback_dir "%s"\nstartmap "%s"\ntrainmap "%s"\n'
        'gamedll "dlls\\hl.dll"\ngamedll_linux "dlls/hl.so"\ncldll "1"\ntype "singleplayer_only"\nversion "1.0"\n'
        % (g['title'], g['moddir'], g['fallback'], g['startmap'], g['trainmap']))
    print('mod folder', os.path.abspath(mod))


if __name__ == '__main__':
    main()
