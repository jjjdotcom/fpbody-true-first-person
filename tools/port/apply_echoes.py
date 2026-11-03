r"""Apply the True First Person (fpbody) code to Half-Life: Echoes - the FWGS
hlsdk-portable "echoes" branch (Spirit of Half-Life based):

  git clone -b echoes --recursive https://github.com/FWGS/hlsdk-portable fpbody_echoes_sdk
  python3 tools/port/apply_echoes.py fpbody_echoes_sdk
  copy tools\port\BUILD_FPBODY_ECHOES.bat fpbody_echoes_sdk\

Copies the fpbody sources from this repository and adds the hooks (the same
ones as in Half-Life's own files here). Run it once on a fresh checkout; it
stops with an error if an anchor it looks for isn't there.
"""
import os, shutil, sys
SDK = sys.argv[1]
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def rep(rel, pairs):
    p = os.path.join(SDK, rel); s = open(p, encoding='latin-1', newline='').read()
    nl = '\r\n' if '\r\n' in s else '\n'; s = s.replace('\r\n', '\n')
    for old, new, *cnt in pairs:
        c = cnt[0] if cnt else 1
        n = s.count(old)
        if n != c: sys.exit('%s: expected %d of %r, found %d' % (rel, c, old[:70], n))
        s = s.replace(old, new)
    open(p, 'w', encoding='latin-1', newline='').write(s.replace('\n', nl)); print('patched', rel)

# new files
for f in ('cl_dll/fpbody.cpp', 'cl_dll/fpbody.h', 'cl_dll/fpbody_anim.cpp', 'cl_dll/fpbody_anim.h', 'cl_dll/fpbody_holsters.h',
          'cl_dll/fpbody_game.h', 'dlls/fpbody_moves.inl', 'pm_shared/fpbody_pm.h', 'pm_shared/fpbody_pm_move.h'):
    shutil.copy(os.path.join(REPO, f), os.path.join(SDK, f))

# Echoes: the lab coat until the chapter RUIN (echoes06), though the HUD suit
# is picked up in the first chapter; then the suit outfit
rep('cl_dll/fpbody_game.h', [('#define FPBODY_SUIT_FROM_ARMOR 0\t// 1 = "suited" while the player has armor (Blue Shift)\n', '#define FPBODY_SUIT_FROM_ARMOR 0\t// 1 = "suited" while the player has armor (Blue Shift)\n#define FPBODY_SUIT_MAP_PREFIX "echoes"\t// the suit outfit only from map echoes<FIRST> on\n#define FPBODY_SUIT_MAP_FIRST 6\t\t\t// echoes06 = chapter RUIN\n#define FPBODY_SUIT_NO_HLS 1\t\t\t// suited: the damaged classic-mesh suit (fpbody_suit / fpbody_classic_suit)\n')])

# ---------------- client
SMR = open(os.path.join(REPO, 'cl_dll/StudioModelRenderer.cpp'), encoding='latin-1').read().replace('\r\n', '\n')
structs = SMR[SMR.index('#include "fpbody.h"\n'):SMR.index('\nextern cvar_t *tfc_newmodels;')]
holster = SMR[SMR.index('\t\t// fpbody: the weapons we carry, on the body (holsters)'):]
holster = holster[:holster.index('\t\t\t\t*m_pCurrentEntity = saveent;\n\t\t\t}\n\t\t}\n') + len('\t\t\t\t*m_pCurrentEntity = saveent;\n\t\t\t}\n\t\t}\n')]
remap = SMR[SMR.index('\t// fpbody: the server numbers our sequences'):SMR.index('\tif (pplayer->gaitsequence)\n')]
gaitcopy = '''		for( i = 0; i < m_pStudioHeader->numbones; i++ )
		{
			for( j = 0; j < LEGS_BONES_COUNT; j++ )
			{
				if( !strcmp( pbones[i].name, legs_bones[j] ) )
					break;
			}

			if( j == LEGS_BONES_COUNT )
				continue;	// not used for legs

			memcpy( pos[i], pos2[i], sizeof(pos[i]) );
			memcpy( q[i], q2[i], sizeof(q[i]) );
		}
	}
'''
gaitnew = '''		// fpbody: Half-Life's rule - everything below "Bip01 Spine" (the pelvis, legs,
		// toes) follows the gait - instead of a fixed list of leg bones, which
		// misses the toes of the Garry's Mod skeleton
		int copy = 1;
		for( i = 0; i < m_pStudioHeader->numbones; i++ )
		{
			if( !strcmp( pbones[i].name, "Bip01 Spine" ) )
				copy = 0;
			else if( pbones[i].parent >= 0 && !strcmp( pbones[pbones[i].parent].name, "Bip01 Pelvis" ) )
				copy = 1;

			if( copy || FPBody_WholeBodyGait() )	// fpbody: unarmed, arms swing with the gait
			{
				memcpy( pos[i], pos2[i], sizeof(pos[i]) );
				memcpy( q[i], q2[i], sizeof(q[i]) );
			}
		}
	}

	// fpbody: an additive gesture layer on the local player (ExtendedER fidgets, flinches)
	{
		int addSeq;
		float addFrame, addWeight;
		if( m_pPlayerInfo && FPAnim_GetAdditive( m_pCurrentEntity->index, m_pStudioHeader, &addSeq, &addFrame, &addWeight ) )
		{
			mstudioseqdesc_t *pad = (mstudioseqdesc_t *)( (byte *)m_pStudioHeader + m_pStudioHeader->seqindex ) + addSeq;
			unsigned char ctl[4], prev[4], neutral[4];
			memcpy( ctl, m_pCurrentEntity->curstate.controller, 4 );
			memcpy( prev, m_pCurrentEntity->latched.prevcontroller, 4 );
			FPAnim_NeutralControllers( m_pStudioHeader, neutral );	// the layer must not turn the controller bones again
			memcpy( m_pCurrentEntity->curstate.controller, neutral, 4 );
			memcpy( m_pCurrentEntity->latched.prevcontroller, neutral, 4 );
			StudioCalcRotations( pos3, q3, pad, StudioGetAnim( m_pRenderModel, pad ), addFrame );
			memcpy( m_pCurrentEntity->curstate.controller, ctl, 4 );
			memcpy( m_pCurrentEntity->latched.prevcontroller, prev, 4 );
			FPAnim_AddLayer( q, q3, m_pStudioHeader->numbones, addWeight );
		}
	}
'''
rep('cl_dll/StudioModelRenderer.cpp', [
    ('#include "GameStudioModelRenderer.h"\n', '#include "GameStudioModelRenderer.h"\n' + structs + '\n'),
    (gaitcopy, gaitnew),
    ('		m_pPlayerInfo->gaitframe += ( m_flGaitMovement / pseqdesc->linearmovement[0] ) * pseqdesc->numframes;',
     '		m_pPlayerInfo->gaitframe += ( m_flGaitMovement / pseqdesc->linearmovement[0] ) * pseqdesc->numframes * FPAnim_GaitScale();	// fpbody'),
    ('''	m_pRenderModel = IEngineStudio.SetupPlayerModel( m_nPlayerIndex );
	if( m_pRenderModel == NULL )
		return 0;

	m_pStudioHeader = (studiohdr_t *)IEngineStudio.Mod_Extradata( m_pRenderModel );
	IEngineStudio.StudioSetHeader( m_pStudioHeader );
	IEngineStudio.SetRenderModel( m_pRenderModel );

	if( pplayer->gaitsequence )
''', '''	m_pRenderModel = IEngineStudio.SetupPlayerModel( m_nPlayerIndex );

	// fpbody: the outfit (before / after the HEV suit)
	bool fpOutfit = false;
	{
		model_t *outfit = FPBody_GetOutfitModel( pplayer->number );
		if( outfit )
		{
			m_pRenderModel = outfit;
			fpOutfit = true;
		}
	}

	if( m_pRenderModel == NULL )
		return 0;

	m_pStudioHeader = (studiohdr_t *)IEngineStudio.Mod_Extradata( m_pRenderModel );
	IEngineStudio.StudioSetHeader( m_pStudioHeader );
	IEngineStudio.SetRenderModel( m_pRenderModel );

''' + remap + '''	if( pplayer->gaitsequence )
'''),
    ('''		StudioProcessGait( pplayer );

		m_pPlayerInfo->gaitsequence = pplayer->gaitsequence;
		m_pPlayerInfo = NULL;

		StudioSetUpTransform( 0 );''', '''		FPBody_PrePlayerBlend( pplayer->number, m_pCurrentEntity );	// fpbody
		StudioProcessGait( pplayer );

		m_pPlayerInfo->gaitsequence = pplayer->gaitsequence;
		m_pPlayerInfo = NULL;

		FPBody_LevelBody( pplayer->number, m_pCurrentEntity );	// fpbody
		StudioSetUpTransform( 0 );'''),
    ('''		m_pPlayerInfo->gaitsequence = 0;

		StudioSetUpTransform( 0 );''', '''		m_pPlayerInfo->gaitsequence = 0;

		FPBody_LevelBody( pplayer->number, m_pCurrentEntity );	// fpbody
		StudioSetUpTransform( 0 );'''),
    ('''	m_pPlayerInfo = IEngineStudio.PlayerInfo( m_nPlayerIndex );
	StudioSetupBones();
	StudioSaveBones();
	m_pPlayerInfo->renderframe = m_nFrameCount;''', '''	m_pPlayerInfo = IEngineStudio.PlayerInfo( m_nPlayerIndex );
	FPBody_SetWholeBodyGait( pplayer->number, pplayer->weaponmodel, fpRestore.saved );	// fpbody
	StudioSetupBones();
	FPBody_SetWholeBodyGait( -1, 0, 1 );

	// fpbody: animate the arms, remember where our head is and collapse it so
	// it's not in the way. Done before StudioSaveBones so the weapon model in
	// the hands is merged onto the animated bones.
	if( flags & STUDIO_RENDER )
	{
		FPBody_ProcessPlayerBones( pplayer->number, m_pCurrentEntity, m_pStudioHeader,
			*m_pbonetransform, *m_plighttransform, pplayer->weaponmodel );
	}

	StudioSaveBones();
	m_pPlayerInfo->renderframe = m_nFrameCount;'''),
    ('''			m_pStudioHeader = (studiohdr_t *)IEngineStudio.Mod_Extradata( pweaponmodel );
			IEngineStudio.StudioSetHeader( m_pStudioHeader );

			StudioMergeBones( pweaponmodel );

			IEngineStudio.StudioSetupLighting( &lighting );

			StudioRenderModel();

			StudioCalcAttachments();

			*m_pCurrentEntity = saveent;
		}
''', '''			m_pStudioHeader = (studiohdr_t *)IEngineStudio.Mod_Extradata( pweaponmodel );
			IEngineStudio.StudioSetHeader( m_pStudioHeader );
			IEngineStudio.SetRenderModel( pweaponmodel );	// fpbody: its own textures

			StudioMergeBones( pweaponmodel );
			FPAnim_AdjustWeapon( m_pStudioHeader, *m_pbonetransform, *m_plighttransform, pweaponmodel, m_pCurrentEntity->index );	// fpbody: fp_gun

			IEngineStudio.StudioSetupLighting( &lighting );

			StudioRenderModel();

			StudioCalcAttachments();

			*m_pCurrentEntity = saveent;
			IEngineStudio.SetRenderModel( m_pRenderModel );	// fpbody: back to the body
		}

''' + holster),
])

rep('cl_dll/ammo.cpp', [
    ('#include "vgui_TeamFortressViewport.h"\n', '#include "vgui_TeamFortressViewport.h"\n\nvoid FPAnim_OnPickup( void );	// fpbody (cl_dll/fpbody_anim.cpp)\n'),
    ('''int CHudAmmo::MsgFunc_AmmoPickup( const char *pszName, int iSize, void *pbuf )
{
	BEGIN_READ( pbuf, iSize );
''', '''int CHudAmmo::MsgFunc_AmmoPickup( const char *pszName, int iSize, void *pbuf )
{
	BEGIN_READ( pbuf, iSize );
	FPAnim_OnPickup();	// fpbody: bend down and grab it
'''),
    ('''int CHudAmmo::MsgFunc_WeapPickup( const char *pszName, int iSize, void *pbuf )
{
	BEGIN_READ( pbuf, iSize );
''', '''int CHudAmmo::MsgFunc_WeapPickup( const char *pszName, int iSize, void *pbuf )
{
	BEGIN_READ( pbuf, iSize );
	FPAnim_OnPickup();	// fpbody: bend down and grab it
'''),
    ('''int CHudAmmo::MsgFunc_ItemPickup( const char *pszName, int iSize, void *pbuf )
{
	BEGIN_READ( pbuf, iSize );
''', '''int CHudAmmo::MsgFunc_ItemPickup( const char *pszName, int iSize, void *pbuf )
{
	BEGIN_READ( pbuf, iSize );
	FPAnim_OnPickup();	// fpbody: bend down and grab it
'''),
])

rep('cl_dll/com_weapons.cpp', [
    ('''void HUD_SendWeaponAnim( int iAnim, int body, int force )
{''', '''void FPAnim_OnWeaponAnim( int iAnim, int viewmodelIndex );
int HUD_GetViewModelIndex( void );

void HUD_SendWeaponAnim( int iAnim, int body, int force )
{'''),
    ('''	g_currentanim = iAnim;

	// Tell animation system new info''', '''	g_currentanim = iAnim;

	// fpbody: body animations follow the weapon's actions
	FPAnim_OnWeaponAnim( iAnim, HUD_GetViewModelIndex() );

	// Tell animation system new info'''),
])

rep('cl_dll/hl/hl_weapons.cpp', [
    ('static globalvars_t Globals; \n', '''static globalvars_t Globals; 

// fpbody: current view model index, used to name weapon animations
int HUD_GetViewModelIndex( void )
{
	return player.pev ? player.pev->viewmodel : 0;
}
'''),
])

rep('cl_dll/health.cpp', [
    ('#include "hud.h"\n', '#include "hud.h"\n#include "fpbody_anim.h"\n'),
    ('''	long bitsDamage = READ_LONG(); // damage bits
''', '''	long bitsDamage = READ_LONG(); // damage bits
	FPAnim_OnDamage( damageTaken + armor, bitsDamage );	// fpbody: ExtendedER flinches
	bitsDamage &= ~( DMG_BULLET | DMG_BLAST | DMG_CLUB | DMG_SLASH | DMG_CRUSH | DMG_FALL | DMG_SONIC | DMG_ENERGYBEAM );	// fpbody: those have no HUD icon
'''),
])

rep('cl_dll/hud.h', [
    ('class CHudBattery : public CHudBase\n{\npublic:\n', 'class CHudBattery : public CHudBase\n{\npublic:\n\tint GetArmor( void ) { return m_iBat; }	// fpbody: outfit with armor (Blue Shift)\n'),
    ('class CHudFlashlight: public CHudBase\n{\npublic:\n', 'class CHudFlashlight: public CHudBase\n{\npublic:\n\tint IsOn( void ) { return m_fOn; }	// fpbody: flashlight toggle animation\n'),
])

rep('cl_dll/in_camera.cpp', [
    ('#include "in_defs.h"\n', '#include "in_defs.h"\n#include "fpbody.h"\n'),
    ('''int DLLEXPORT CL_IsThirdPerson( void )
{
	return ( cam_thirdperson ? 1 : 0 ) || ( g_iUser1 && ( g_iUser2 == gEngfuncs.GetLocalPlayer()->index ) );
}''', '''// True only for the real chase camera ("thirdperson" command / spectating yourself).
int CAM_IsRealThirdPerson( void )
{
	return ( cam_thirdperson ? 1 : 0 ) || ( g_iUser1 && ( g_iUser2 == gEngfuncs.GetLocalPlayer()->index ) );
}

int DLLEXPORT CL_IsThirdPerson( void )
{
	// fpbody: tell the engine to draw our own body while the camera sits in its head
	return CAM_IsRealThirdPerson() || FPBody_Active();
}'''),
])

rep('cl_dll/input.cpp', [
    ('void IN_DuckDown( void )\n{\n\tKeyDown( &in_duck );', 'void IN_DuckDown( void )\n{\n\tFPBody_DuckPressed( !( in_duck.state & 1 ) );	// fpbody\n\tKeyDown( &in_duck );'),
    ('void IN_ReloadDown( void )\n{\n\tKeyDown( &in_reload );', 'void IN_ReloadDown( void )\n{\n\tFPBody_ReloadPressed( !( in_reload.state & 1 ) );	// fpbody\n\tKeyDown( &in_reload );'),
    ('	if( in_alt1.state & 3 )\n	{\n		bits |= IN_ALT1;\n	}', '	if( ( in_alt1.state & 3 ) && FPBody_SprintAllowed( bits ) )	// fpbody: sprint\n	{\n		bits |= IN_ALT1;\n	}'),
])
rep('cl_dll/input.cpp', [
    ('int CL_ButtonBits( int );\n', 'int CL_ButtonBits( int );\nint FPBody_SprintAllowed( int bits );	// fpbody: sprint (cl_dll/fpbody_anim.cpp)\nvoid FPBody_DuckPressed( int fresh );	// fpbody: double-tap duck = prone\nvoid FPBody_ReloadPressed( int fresh );	// fpbody: double-tap reload = holster all\n'),
])

rep('cl_dll/view.cpp', [
    ('#include "view.h"\n', '#include "view.h"\n#include "fpbody.h"\n#include "fpbody_anim.h"\n\nint CAM_IsRealThirdPerson( void );	// fpbody: in_camera.cpp (C++ linkage, like fpbody.cpp)\n'),
    ('''	pparams->vieworg[2] += bob ;
	VectorAdd( pparams->vieworg, pparams->viewheight, pparams->vieworg );
''', '''	pparams->vieworg[2] += bob ;
	VectorAdd( pparams->vieworg, pparams->viewheight, pparams->vieworg );

	// fpbody: put the camera in the head of the player model. The head's own
	// animation replaces the artificial view bob.
	{
		vec3_t headorg;
		if( FPBody_GetViewOrigin( pparams, headorg ) )
			VectorCopy( headorg, pparams->vieworg );
	}
'''),
    ('	if( CL_IsThirdPerson() )', '	if( CAM_IsRealThirdPerson() )', 2),
    ('''	V_DropPunchAngle( pparams->frametime, (float *)&g_ev_punchangle );
''', '''	V_DropPunchAngle( pparams->frametime, (float *)&g_ev_punchangle );

	// fpbody: the view tilts and bobs with the body's head
	{
		vec3_t headofs;
		FPAnim_GetViewAngleOffset( headofs );
		VectorAdd( pparams->viewangles, headofs, pparams->viewangles );
	}
'''),
    ('''void DLLEXPORT V_CalcRefdef( struct ref_params_s *pparams )
{
''', '''void DLLEXPORT V_CalcRefdef( struct ref_params_s *pparams )
{
	FPBody_BeginFrame( pparams );

'''),
    ('''	cl_chasedist = gEngfuncs.pfnRegisterVariable( "cl_chasedist","112", 0 );
}''', '''	cl_chasedist = gEngfuncs.pfnRegisterVariable( "cl_chasedist","112", 0 );

	FPBody_Init();
}'''),
])

# ev_hldm: firing animations through the wrapper
p = os.path.join(SDK, 'cl_dll/ev_hldm.cpp'); s = open(p, encoding='latin-1', newline='').read()
n = s.count('gEngfuncs.pEventAPI->EV_WeaponAnimation')
s = s.replace('gEngfuncs.pEventAPI->EV_WeaponAnimation', 'FP_EV_WeaponAnimation')
anchor = '#include "r_studioint.h"'
assert s.count(anchor) == 1, 'ev_hldm anchor'
s = s.replace(anchor, anchor + '''

// fpbody: firing animations are played here (events), not through HUD_SendWeaponAnim:
// tell the body about them too
extern "C++" void FPAnim_OnWeaponAnim( int iAnim, int viewmodelIndex );	// C++ linkage, whatever block this sits in
static void FP_EV_WeaponAnimation( int sequence, int body )
{
	FPAnim_OnWeaponAnim( sequence, 0 );
	gEngfuncs.pEventAPI->EV_WeaponAnimation( sequence, body );
}''')
open(p, 'w', encoding='latin-1', newline='').write(s); print('patched cl_dll/ev_hldm.cpp', n, 'calls')

# ---------------- pm_shared
rep('pm_shared/pm_shared.c', [
    ('#include "pm_shared.h"\n', '#include "pm_shared.h"\n#include "fpbody_pm.h"	// fpbody: Freeman moves\n'),
    ('		friction *= pmove->friction;  // player friction?\n', '		friction *= pmove->friction;  // player friction?\n		friction *= FPM_FRICTION_SCALE( pmove );	// fpbody: sliding\n'),
])
rep('pm_shared/pm_shared.c', [
    ('''/*
=============
PlayerMove

Returns with origin''', '''#include "fpbody_pm_move.h"	// fpbody: Freeman moves

/*
=============
PlayerMove

Returns with origin'''),
    ('''	PM_UpdateStepSound();

	PM_Duck();
	
''', '''	PM_UpdateStepSound();

	// fpbody: slide, vault and wall climb (a vault moves the player itself)
	if( FPM_PreDuck( pLadder != NULL ) )
		return;

	PM_Duck();
	FPM_PostDuck();
	
'''),
])

# ---------------- server
rep('dlls/client.cpp', [
    ('	else if ( FStrEq(pcmd, "hud_color") ) //LRC', '''	else if( FStrEq( pcmd, "buddha" ) )	// fpbody: buddha mode
	{
		if( gpGlobals->maxClients == 1 || CVAR_GET_FLOAT( "sv_cheats" ) != 0 )
		{
			const bool on = CMD_ARGC() > 1 ? atoi( CMD_ARGV( 1 ) ) != 0 : sv_buddha.value == 0;
			CVAR_SET_FLOAT( "sv_buddha", on ? 1 : 0 );
			ClientPrint( pev, HUD_PRINTCONSOLE, on ? "buddha ON\\n" : "buddha OFF\\n" );
		}
		else
			ClientPrint( pev, HUD_PRINTCONSOLE, "buddha needs sv_cheats 1 in multiplayer\\n" );
	}
	else if ( FStrEq(pcmd, "hud_color") ) //LRC'''),
    ('''	cd->flags		= pev->flags;
	cd->health		= pev->health;
''', '''	cd->flags		= pev->flags;
	cd->health		= pev->health;
	cd->fuser1 = pev->fuser1;	// fpbody: Freeman move timer
	cd->fuser4 = pev->fuser4;	// fpbody: Freeman move state
'''),
])

rep('dlls/game.cpp', [
    ('cvar_t chargerfix	= { "chargerfix", "0", FCVAR_SERVER };\n', '''cvar_t chargerfix	= { "chargerfix", "0", FCVAR_SERVER };
cvar_t sv_buddha = { "sv_buddha", "1", FCVAR_ARCHIVE };	// fpbody: buddha mode (on by default; "buddha" toggles)
cvar_t sv_fpbody_anims = { "sv_fpbody_anims", "cz", FCVAR_ARCHIVE };	// fpbody: cz / cs player weapon animations
cvar_t sv_fpbody_regen = { "sv_fpbody_regen", "1", FCVAR_ARCHIVE };			// fpbody: health comes back by itself
cvar_t sv_fpbody_regen_delay = { "sv_fpbody_regen_delay", "5", FCVAR_ARCHIVE };	// seconds without getting hurt first
cvar_t sv_fpbody_regen_rate = { "sv_fpbody_regen_rate", "5", FCVAR_ARCHIVE };		// health per second
cvar_t sv_fpbody_regen_max = { "sv_fpbody_regen_max", "100", FCVAR_ARCHIVE };		// up to this much health
'''),
    ('	CVAR_REGISTER( &chargerfix );\n', '''	CVAR_REGISTER( &chargerfix );
	CVAR_REGISTER( &sv_buddha );
	CVAR_REGISTER( &sv_fpbody_anims );
	CVAR_REGISTER( &sv_fpbody_regen );
	CVAR_REGISTER( &sv_fpbody_regen_delay );
	CVAR_REGISTER( &sv_fpbody_regen_rate );
	CVAR_REGISTER( &sv_fpbody_regen_max );
'''),
])
rep('dlls/game.h', [
    ('extern cvar_t chargerfix;\n', '''extern cvar_t chargerfix;
extern cvar_t sv_buddha;	// fpbody: buddha mode
extern cvar_t sv_fpbody_anims;	// fpbody: cz / cs player weapon animations
extern cvar_t sv_fpbody_regen;			// fpbody: health regeneration
extern cvar_t sv_fpbody_regen_delay;
extern cvar_t sv_fpbody_regen_rate;
extern cvar_t sv_fpbody_regen_max;
'''),
])

# hold types (animation extensions) the fpbody player model has
for rel, old, new in [
    ('dlls/crossbow.cpp', '"bow" )', '"rifle" )'),
    ('dlls/crowbar.cpp', 'CROWBAR_DRAW, "crowbar" )', 'CROWBAR_DRAW, "knife" )'),
    ('dlls/gauss.cpp', 'GAUSS_DRAW, "gauss" )', 'GAUSS_DRAW, "tau" )'),
    ('dlls/handgrenade.cpp', 'HANDGRENADE_DRAW, "crowbar" )', 'HANDGRENADE_DRAW, "grenade" )'),
    ('dlls/mp5.cpp', 'MP5_DEPLOY, "mp5" )', 'MP5_DEPLOY, "rifle" )'),
    ('dlls/python.cpp', 'PYTHON_DRAW, "python"', 'PYTHON_DRAW, "onehanded"'),
    ('dlls/satchel.cpp', 'SATCHEL_DRAW, "trip" )', 'SATCHEL_DRAW, "c4" )'),
    ('dlls/tripmine.cpp', 'TRIPMINE_DRAW, "trip" )', 'TRIPMINE_DRAW, "c4" )'),
    ('dlls/squeakgrenade.cpp', 'SQUEAK_UP, "squeak" )', 'SQUEAK_UP, "grenade" )'),
]:
    p = os.path.join(SDK, rel); s = open(p, encoding='latin-1', newline='').read()
    n = s.count(old)
    if n == 0: sys.exit('%s: no %r' % (rel, old))
    open(p, 'w', encoding='latin-1', newline='').write(s.replace(old, new)); print('hold', rel, n)
p = os.path.join(SDK, 'dlls/satchel.cpp'); s = open(p, encoding='latin-1', newline='').read()
s = s.replace('strcpy( m_pPlayer->m_szAnimExtention, "trip" );', 'strcpy( m_pPlayer->m_szAnimExtention, "c4" );')
open(p, 'w', encoding='latin-1', newline='').write(s)
_pc = open(os.path.join(REPO, 'dlls/player.cpp'), encoding='latin-1').read().replace('\r\n', '\n')
_a = _pc.index('// fpbody: sv_fpbody_anims "cs"'); LOOKUP = _pc[_a:_pc.index('\n}\n', _a) + 3] + '\n'
_ph = open(os.path.join(REPO, 'dlls/player.h'), encoding='latin-1').read().replace('\r\n', '\n')
PLAYERH = _ph[_ph.index('\t// fpbody: Freeman moves (dlls/fpbody_moves.inl)'):_ph.index('\tint m_iFPUseKind;') + len('\tint m_iFPUseKind;\n')]
rep('dlls/player.h', [
    ('	char m_szAnimExtention[32];\n', '	char m_szAnimExtention[32];\n\n' + PLAYERH),
])
rep('dlls/player.cpp', [
    ('	DEFINE_FIELD( CBasePlayer, m_bitsHUDDamage, FIELD_INTEGER ),\n',
     '	DEFINE_FIELD( CBasePlayer, m_bitsHUDDamage, FIELD_INTEGER ),\n	DEFINE_ARRAY( CBasePlayer, m_szAnimExtention, FIELD_CHARACTER, 32 ),	// fpbody: the hold type (ref_aim_<ext>) survives saved games\n'),
    ('''	// as an int (zero) and think the player is dead! (this will incite a clientside screentilt, etc)
	fTookDamage = CBaseMonster::TakeDamage(''', '''	// as an int (zero) and think the player is dead! (this will incite a clientside screentilt, etc)
	// fpbody: buddha mode - take the hit, but never drop below 1 health
	if( sv_buddha.value != 0 && pev->health - (int)flDamage < 1 )
	{
		flDamage = (int)pev->health - 1;
		if( flDamage < 0 )
			flDamage = 0;
	}

	fTookDamage = CBaseMonster::TakeDamage('''),
    ('// Set the activity based on an event or current state\nvoid CBasePlayer::SetAnimation', LOOKUP + '// Set the activity based on an event or current state\nvoid CBasePlayer::SetAnimation'),
    ('		animDesired = LookupSequence( szAnim );\n		if( animDesired == -1 )', '		animDesired = FPBody_LookupAnim( this, szAnim );\n		if( animDesired == -1 )'),
    ('			animDesired = LookupSequence( szAnim );\n', '			animDesired = FPBody_LookupAnim( this, szAnim );\n'),
    ('''				m_afPhysicsFlags |= PFLAG_USING;

			pObject->Use( this, this, USE_SET, 1 );''', '''				m_afPhysicsFlags |= PFLAG_USING;

			FPMoves_OnUse( pObject );	// fpbody: Contextual Player Animations
			pObject->Use( this, this, USE_SET, 1 );'''),
    ('void CBasePlayer::PostThink()\n{\n', 'void CBasePlayer::PostThink()\n{\n	FPMoves_Think();	// fpbody: kick, redeploy after holster-all\n'),
    ('	int iImpulse = (int)pev->impulse;\n	switch( iImpulse )\n', '	int iImpulse = (int)pev->impulse;\n	FPMoves_Impulse( iImpulse );	// fpbody: kick, holster all\n	switch( iImpulse )\n'),
    ('		int visibleDamageBits = m_bitsDamageType & DMG_SHOWNHUD;', '		int visibleDamageBits = m_bitsDamageType & ( DMG_SHOWNHUD | DMG_FPBODY_REACT );	// fpbody: the body reacts to blasts, bullets and hits too'),
])
p = os.path.join(SDK, 'dlls/player.cpp'); s = open(p, encoding='latin-1', newline='').read()
nl = '\r\n' if '\r\n' in s else '\n'
s = s.replace('void CBasePlayer::UpdateClientData( void )', '#define DMG_FPBODY_REACT ( DMG_BULLET | DMG_BLAST | DMG_CLUB | DMG_SLASH | DMG_CRUSH | DMG_FALL | DMG_SONIC | DMG_ENERGYBEAM )	// fpbody: damage the client body flinches at' + nl + nl + 'void CBasePlayer::UpdateClientData( void )', 1)
s = s.rstrip() + nl + nl + '#include "fpbody_moves.inl"	// fpbody: Freeman moves (kick, holster all)' + nl
open(p, 'w', encoding='latin-1', newline='').write(s); print('player.cpp tail')
rep('cl_dll/CMakeLists.txt', [('	view.cpp\n', '	view.cpp\n	fpbody.cpp\n	fpbody_anim.cpp\n')])
rep('mod_options.txt', [('GAMEDIR=echoes # Gamedir path', 'GAMEDIR=fpbody_echoes # Gamedir path (fpbody: the True First Person mod folder)')])

# ladders: Spirit hides func_ladder with EF_NODRAW, which keeps it off the client
# entirely - the client's movement prediction (and the body's climbing
# animations, which go by it) never sees the ladder. Half-Life's way instead:
# drawn fully transparent, still sent.
rep('dlls/triggers.cpp', [('''		pev->effects |= EF_NODRAW;
		//LRC- NODRAW is a better-performance way to stop things being drawn.
		// (unless... would it prevent client-side movement algorithms from working?)
//		pev->rendermode = kRenderTransTexture;
//		pev->renderamt = 0;
	}''', '''		// fpbody: invisible but still sent to the client (Half-Life's way): with
		// EF_NODRAW the client never gets the ladder, so its movement prediction
		// and the body's climbing animations don't know we're on it
		pev->effects &= ~EF_NODRAW;
		pev->rendermode = kRenderTransTexture;
		pev->renderamt = 0;
	}''')])
