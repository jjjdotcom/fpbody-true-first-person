r"""Apply the True First Person (fpbody) code to Half-Life: Field Intensity - the
field_intensity_1.7 branch of FreeSlave's Half-Life Featureful SDK:

  git clone -b field_intensity_1.7 --recursive https://github.com/FreeSlave/halflife-featureful fpbody_fi_sdk
  python3 tools/port/apply_fi.py fpbody_fi_sdk
  copy tools\port\BUILD_FPBODY_FI.bat fpbody_fi_sdk\

Copies the fpbody sources from this repository and adds the hooks (the same
ones as in Half-Life's own files here). Run it once on a fresh checkout; it
stops with an error if an anchor it looks for isn't there.
"""
import os, shutil, sys
SDK = sys.argv[1]; FAILS = []
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def rep(rel, pairs):
    p = os.path.join(SDK, rel); s = open(p, encoding='latin-1', newline='').read()
    nl = '\r\n' if '\r\n' in s else '\n'; s = s.replace('\r\n', '\n')
    for old, new, *cnt in pairs:
        c = cnt[0] if cnt else 1
        n = s.count(old)
        if n != c: FAILS.append('%s: expected %d of %r, found %d' % (rel, c, old[:70], n)); continue
        s = s.replace(old, new)
    open(p, 'w', encoding='latin-1', newline='').write(s.replace('\n', nl)); print('patched', rel)

# new files
for f in ('cl_dll/fpbody.cpp', 'cl_dll/fpbody.h', 'cl_dll/fpbody_anim.cpp', 'cl_dll/fpbody_anim.h', 'cl_dll/fpbody_holsters.h',
          'dlls/fpbody_moves.inl', 'pm_shared/fpbody_pm.h', 'pm_shared/fpbody_pm_move.h'):
    shutil.copy(os.path.join(REPO, f), os.path.join(SDK, f))

open(os.path.join(SDK, 'cl_dll/fpbody_game.h'), 'w').write(
    '// fpbody_game.h - per-game settings for the True First Person code (Field Intensity).\n'
    '#ifndef FPBODY_GAME_H\n#define FPBODY_GAME_H\n\n'
    '#define FPBODY_SUIT_FROM_ARMOR 0	// 1 = "suited" while the player has armor (Blue Shift)\n\n'
    '// pm_shared is C++ in this SDK\n#define FPBODY_DECLARE_ONLADDER extern bool g_onladder;\n\n#endif\n')
# this SDK's armor HUD is part of the health HUD
for f in ('cl_dll/fpbody.cpp', 'cl_dll/fpbody_anim.cpp'):
    p = os.path.join(SDK, f); t = open(p, encoding='latin-1', newline='').read()
    assert 'gHUD.m_Battery.GetArmor()' in t
    t = t.replace('gHUD.m_Battery.GetArmor()', 'gHUD.m_Health.GetArmor()')
    t = t.replace('( gHUD.m_iWeaponBits & ( 1 << WEAPON_SUIT ) ) ? 1 : 0', 'gHUD.HasSuit() ? 1 : 0')	# the suit is an item here
    t = t.replace('#include "in_buttons.h"\n', '')	# IN_* are in const.h here
    t = t.replace('MAX_WEAPON_SLOTS', 'WEAPON_SLOTS_HARDLIMIT')	# the HUD's slot count here
    open(p, 'w', encoding='latin-1', newline='').write(t)

# server moves: this SDK's names for the tank, the weapon list and TraceAttack
rep('dlls/fpbody_moves.inl', [
    ('m_pTank != NULL', '(CBaseEntity *)m_hTankControls != NULL'),
    ('\tCBasePlayerItem *pItem = (CBasePlayerItem *)pEnt;\n\t// still ours?\n\tfor ( int i = 0; i < MAX_ITEM_TYPES; i++ )\n\t{\n\t\tfor ( CBasePlayerItem *p = m_rgpPlayerItems[ i ]; p; p = p->m_pNext )\n\t\t{\n\t\t\tif ( p == pItem )\n\t\t\t{\n\t\t\t\tSwitchWeapon( pItem );\n\t\t\t\treturn;\n\t\t\t}\n\t\t}\n\t}',
     '\tCBasePlayerWeapon *pItem = (CBasePlayerWeapon *)pEnt;\n\t// still ours?\n\tfor ( int i = 0; i < MAX_WEAPONS; i++ )\n\t{\n\t\tif ( m_rgpPlayerWeapons[ i ] == pItem )\n\t\t{\n\t\t\tSwitchWeapon( pItem );\n\t\t\treturn;\n\t\t}\n\t}'),
    ('pHit->TraceAttack( pev, damage, dir, &tr, DMG_CLUB );', 'pHit->TraceAttack( pev, pev, DamageInfo( damage, DMG_CLUB ), dir, &tr );'),
])

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
    ('#include "ammohistory.h"\n', '#include "ammohistory.h"\n\nvoid FPAnim_OnPickup( void );	// fpbody (cl_dll/fpbody_anim.cpp)\n'),
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
    ('static globalvars_t Globals;\n', '''static globalvars_t Globals;

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
    ('class CHudHealth : public CHudBase\n{\npublic:\n', 'class CHudHealth : public CHudBase\n{\npublic:\n\tint GetArmor( void ) { return m_iBat; }	// fpbody: the armor (this HUD shows health and armor)\n'),
    ('class CHudFlashlight: public CHudBase\n{\npublic:\n', 'class CHudFlashlight: public CHudBase\n{\npublic:\n\tint IsOn( void ) { return m_fOn; }	// fpbody: flashlight toggle animation\n'),
])

rep('cl_dll/in_camera.cpp', [
    ('#include "in_defs.h"\n', '#include "in_defs.h"\n#include "fpbody.h"\n'),
    ('''int DLLEXPORT CL_IsThirdPerson()
{
	return ( cam_thirdperson ? 1 : 0 ) || ( g_iUser1 && ( g_iUser2 == gEngfuncs.GetLocalPlayer()->index ) );
}''', '''// True only for the real chase camera ("thirdperson" command / spectating yourself).
int CAM_IsRealThirdPerson( void )
{
	return ( cam_thirdperson ? 1 : 0 ) || ( g_iUser1 && ( g_iUser2 == gEngfuncs.GetLocalPlayer()->index ) );
}

int DLLEXPORT CL_IsThirdPerson()
{
	// fpbody: tell the engine to draw our own body while the camera sits in its head
	return CAM_IsRealThirdPerson() || FPBody_Active();
}'''),
])

rep('cl_dll/input.cpp', [
    ('void IN_DuckDown()\n{\n\tKeyDown( &in_duck );', 'void IN_DuckDown()\n{\n\tFPBody_DuckPressed( !( in_duck.state & 1 ) );	// fpbody\n\tKeyDown( &in_duck );'),
    ('void IN_ReloadDown()\n{\n\tKeyDown( &in_reload );', 'void IN_ReloadDown()\n{\n\tFPBody_ReloadPressed( !( in_reload.state & 1 ) );	// fpbody\n\tKeyDown( &in_reload );'),
    ('	if( in_alt1.state & 3 )\n	{\n		bits |= IN_ALT1;\n	}', '	if( ( in_alt1.state & 3 ) && FPBody_SprintAllowed( bits ) )	// fpbody: sprint\n	{\n		bits |= IN_ALT1;\n	}'),
])
rep('cl_dll/input.cpp', [
    ('int CL_ButtonBits( int );\n', 'int CL_ButtonBits( int );\nint FPBody_SprintAllowed( int bits );	// fpbody: sprint (cl_dll/fpbody_anim.cpp)\nvoid FPBody_DuckPressed( int fresh );	// fpbody: double-tap duck = prone\nvoid FPBody_ReloadPressed( int fresh );	// fpbody: double-tap reload = holster all\n'),
])

rep('cl_dll/view.cpp', [
    ('#include "view.h"\n', '#include "view.h"\n#include "fpbody.h"\n#include "fpbody_anim.h"\n\nint CAM_IsRealThirdPerson( void );	// fpbody: in_camera.cpp (C++ linkage, like fpbody.cpp)\n'),
    ('''	pparams->vieworg[2] += bob ;
	VectorAdd( pparams->vieworg, viewheight, pparams->vieworg );
''', '''	pparams->vieworg[2] += bob ;
	VectorAdd( pparams->vieworg, viewheight, pparams->vieworg );

	// fpbody: put the camera in the head of the player model. The head's own
	// animation replaces the artificial view bob.
	{
		Vector headorg;
		if( FPBody_GetViewOrigin( pparams, headorg ) )
			VectorCopy( headorg, pparams->vieworg );
	}
'''),
    ('	if( CL_IsThirdPerson() )', '	if( CAM_IsRealThirdPerson() )', 2),
    ('''	V_DropPunchAngle( pparams->frametime, (float *)&g_ev_punchangle );
''', '''	V_DropPunchAngle( pparams->frametime, (float *)&g_ev_punchangle );

	// fpbody: the view tilts and bobs with the body's head
	{
		Vector headofs;
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
    ('''	cl_steady_uncrouch = gEngfuncs.pfnRegisterVariable( "cl_steady_uncrouch","1", 0 );
}''', '''	cl_steady_uncrouch = gEngfuncs.pfnRegisterVariable( "cl_steady_uncrouch","1", 0 );

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
rep('pm_shared/pm_shared.cpp', [
    ('#include "pm_shared.h"\n', '#include "pm_shared.h"\n#include "fpbody_pm.h"	// fpbody: Freeman moves\n'),
    ('		friction *= pmove->friction;  // player friction?\n', '		friction *= pmove->friction;  // player friction?\n		friction *= FPM_FRICTION_SCALE( pmove );	// fpbody: sliding\n'),
])
rep('pm_shared/pm_shared.cpp', [
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
    ('	else if( FStrEq( pcmd, "fullupdate" ) )', '''	else if( FStrEq( pcmd, "buddha" ) )	// fpbody: buddha mode
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
	else if( FStrEq( pcmd, "fullupdate" ) )'''),
    ('''	cd->flags		= pev->flags;
	cd->health		= pev->health;
''', '''	cd->flags		= pev->flags;
	cd->health		= pev->health;
	cd->fuser1 = pev->fuser1;	// fpbody: Freeman move timer
	cd->fuser4 = pev->fuser4;	// fpbody: Freeman move state
'''),
])

rep('dlls/game.cpp', [
    ('cvar_t displaysoundlist = {"displaysoundlist","0"};\n', '''cvar_t displaysoundlist = {"displaysoundlist","0"};
cvar_t sv_buddha = { "sv_buddha", "1", FCVAR_ARCHIVE };	// fpbody: buddha mode (on by default; "buddha" toggles)
cvar_t sv_fpbody_anims = { "sv_fpbody_anims", "cz", FCVAR_ARCHIVE };	// fpbody: cz / cs player weapon animations
cvar_t sv_fpbody_regen = { "sv_fpbody_regen", "1", FCVAR_ARCHIVE };			// fpbody: health comes back by itself
cvar_t sv_fpbody_regen_delay = { "sv_fpbody_regen_delay", "5", FCVAR_ARCHIVE };	// seconds without getting hurt first
cvar_t sv_fpbody_regen_rate = { "sv_fpbody_regen_rate", "5", FCVAR_ARCHIVE };		// health per second
cvar_t sv_fpbody_regen_max = { "sv_fpbody_regen_max", "100", FCVAR_ARCHIVE };		// up to this much health
'''),
    ('	CVAR_REGISTER( &displaysoundlist );\n', '''	CVAR_REGISTER( &displaysoundlist );
	CVAR_REGISTER( &sv_buddha );
	CVAR_REGISTER( &sv_fpbody_anims );
	CVAR_REGISTER( &sv_fpbody_regen );
	CVAR_REGISTER( &sv_fpbody_regen_delay );
	CVAR_REGISTER( &sv_fpbody_regen_rate );
	CVAR_REGISTER( &sv_fpbody_regen_max );
'''),
])
rep('dlls/game.h', [
    ('extern cvar_t displaysoundlist;\n', '''extern cvar_t displaysoundlist;
extern cvar_t sv_buddha;	// fpbody: buddha mode
extern cvar_t sv_fpbody_anims;	// fpbody: cz / cs player weapon animations
extern cvar_t sv_fpbody_regen;			// fpbody: health regeneration
extern cvar_t sv_fpbody_regen_delay;
extern cvar_t sv_fpbody_regen_rate;
extern cvar_t sv_fpbody_regen_max;
'''),
])

# hold types: Field Intensity's weapons take their animation extension from
# templates; map them, by the gun's world model, to the holds the fpbody player
# model has (one place: DefaultDeploy)
rep('dlls/weapons.cpp', [
    ('bool CBasePlayerWeapon::DefaultDeploy( const char *szViewModel,', '''// fpbody: the hold (player animation extension) for a gun, by its p_ model
static const char *FPBody_HoldFor( const char *weaponModel, const char *ext )
{
	static const struct { const char *model, *hold; } holds[] = {
		{ "p_crowbar", "knife" }, { "p_knife", "knife" }, { "p_pipe_wrench", "knife" },
		{ "p_9mmhandgun", "onehanded" }, { "p_357", "onehanded" }, { "p_desert_eagle", "onehanded" },
		{ "p_9mmar", "rifle" }, { "p_crossbow", "rifle" }, { "p_m40a1", "rifle" }, { "p_shotgun", "shotgun" },
		{ "p_saw", "m249" }, { "p_shock", "bow" }, { "p_rpg", "rpg" }, { "p_spore_launcher", "rpg" },
		{ "p_gauss", "tau" }, { "p_bgrap", "gauss" }, { "p_egon", "egon" }, { "p_displacer", "egon" },
		{ "p_hgun", "hive" }, { "p_grenade", "grenade" }, { "p_squeak", "grenade" }, { "p_penguin", "grenade" },
		{ "p_satchel_radio", "hive" }, { "p_satchel", "c4" }, { "p_tripmine", "c4" }, { "p_medkit", "grenade" },
	};
	if( weaponModel )
	{
		const char *base = strrchr( weaponModel, '/' );
		base = base ? base + 1 : weaponModel;
		for( size_t i = 0; i < sizeof( holds ) / sizeof( holds[0] ); i++ )
		{
			size_t n = strlen( holds[i].model );
			if( !strnicmp( base, holds[i].model, n ) && ( base[n] == '.' || base[n] == '\\0' ) )
				return holds[i].hold;
		}
	}
	// Half-Life's own names for the ones not listed
	static const struct { const char *ext, *hold; } exts[] = {
		{ "bow", "rifle" }, { "crowbar", "knife" }, { "gauss", "tau" }, { "mp5", "rifle" },
		{ "python", "onehanded" }, { "trip", "c4" }, { "squeak", "grenade" }, { "saw", "m249" },
	};
	for( size_t i = 0; ext && i < sizeof( exts ) / sizeof( exts[0] ); i++ )
		if( !stricmp( ext, exts[i].ext ) )
			return exts[i].hold;
	return ext;
}

bool CBasePlayerWeapon::DefaultDeploy( const char *szViewModel,'''),
    ('	strcpy( m_pPlayer->m_szAnimExtention, szAnimExt );\n	SendWeaponAnim( iAnim, body );',
     '	strcpy( m_pPlayer->m_szAnimExtention, FPBody_HoldFor( szWeaponModel, szAnimExt ) );	// fpbody\n	SendWeaponAnim( iAnim, body );'),
])
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
    ('''	DamageInfo dmgInfo = damageInfo;
	dmgInfo.damage = trunc(flDamage);''', '''	// fpbody: buddha mode - take the hit, but never drop below 1 health
	if( sv_buddha.value != 0 && pev->health - (int)flDamage < 1 )
	{
		flDamage = (int)pev->health - 1;
		if( flDamage < 0 )
			flDamage = 0;
	}

	DamageInfo dmgInfo = damageInfo;
	dmgInfo.damage = trunc(flDamage);'''),
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
s = s.replace('void CBasePlayer::UpdateClientData()', '#define DMG_FPBODY_REACT ( DMG_BULLET | DMG_BLAST | DMG_CLUB | DMG_SLASH | DMG_CRUSH | DMG_FALL | DMG_SONIC | DMG_ENERGYBEAM )	// fpbody: damage the client body flinches at' + nl + nl + 'void CBasePlayer::UpdateClientData()', 1)
s = s.rstrip() + nl + nl + '#include "fpbody_moves.inl"	// fpbody: Freeman moves (kick, holster all)' + nl
open(p, 'w', encoding='latin-1', newline='').write(s); print('player.cpp tail')
rep('cl_dll/CMakeLists.txt', [('	view.cpp\n', '	view.cpp\n	fpbody.cpp\n	fpbody_anim.cpp\n')])
rep('mod_options.txt', [('GAMEDIR=field_intensity # Gamedir path', 'GAMEDIR=fpbody_fi # Gamedir path (fpbody: the True First Person mod folder)')])
rep('dlls/satchel.cpp', [
    ('strcpy( m_pPlayer->m_szAnimExtention, "trip" );', 'strcpy( m_pPlayer->m_szAnimExtention, "c4" );	// fpbody'),
    ('strcpy( m_pPlayer->m_szAnimExtention, params.PlayerAnimExt() );', 'strcpy( m_pPlayer->m_szAnimExtention, "c4" );	// fpbody'),
    ('strcpy( m_pPlayer->m_szAnimExtention, params.DetonatorPlayerAnimExt() );', 'strcpy( m_pPlayer->m_szAnimExtention, "hive" );	// fpbody'),
])
if FAILS:
    sys.exit("\n".join(FAILS))

# the HEV companion
import subprocess
subprocess.check_call([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fpbody_buddy.py'), SDK, 'fi'])
subprocess.check_call([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fpbody_react.py'), SDK, 'fi'])
