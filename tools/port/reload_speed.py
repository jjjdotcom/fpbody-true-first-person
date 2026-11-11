"""The Freeman mod's reloads per gun and cl_fpbody_reload_speed, for every
fpbody SDK:

  python3 reload_speed.py <sdk dir> [...]

cl_dll/fpbody_anim.cpp
  - GMod mode (cl_fpbody_freemanreload 1) plays what Half-Life 2: Freeman
    plays with its default Counter-Strike: Source stance (hl2_pm_stance css):
    pistols Garry's Mod's pistol / revolver reloads (as before), the 9mmAR the
    MP5 reload, the crossbow and sniper rifle the sniper reload, the M249 and
    the RPG the M249 box reload, the shotgun Counter-Strike: Source's shell
    inserts, then the end of Garry's Mod's reload for the pump (from 70%).
  - cl_fpbody_reload_speed (1 = normal, 0.5 = half speed, 0.1 - 4): every
    reload's body animation and the view model's reload animation.
  - FPAnim_ViewModelRate(), called every frame from fpbody.cpp.
dlls/fpbody_reload.h (new) + player.cpp + cl_dll/hl/hl_weapons.cpp
  - the reload itself takes 1 / cl_fpbody_reload_speed as long: the timers a
    weapon sets while it reloads are stretched (server and client prediction
    alike), whatever the weapon (magazine or shell by shell).
Idempotent.
"""
import os
import re
import sys

HDR = r'''// fpbody: cl_fpbody_reload_speed - reloads take 1 / speed as long (0.5 = twice as long).
// The timers a weapon sets while it is reloading are stretched; called round
// the weapon's ItemPostFrame on the server (player.cpp) and in the client's
// prediction (cl_dll/hl/hl_weapons.cpp) alike, so the two stay in step.
#ifndef FPBODY_RELOAD_H
#define FPBODY_RELOAD_H

#ifdef CLIENT_DLL
float FPReloadSpeedCvar( void );		// cl_dll/fpbody_anim.cpp
#endif

inline float FPReloadScale( void )
{
#ifdef CLIENT_DLL
	float s = FPReloadSpeedCvar();
#else
	float s = CVAR_GET_FLOAT( "cl_fpbody_reload_speed" );
#endif
	if ( s <= 0.0f )
		return 1.0f;					// not set (a dedicated server)
	if ( s < 0.1f ) s = 0.1f;
	if ( s > 4.0f ) s = 4.0f;
	return 1.0f / s;
}

struct FPReloadSnap
{
	float nextAttack, idle, nextPrimary, nextSecondary;
	int inReload, inSpecial;
};

inline void FPReloadBefore( CBasePlayerWeapon *w, CBasePlayer *pl, FPReloadSnap &s )
{
	s.nextAttack = pl->m_flNextAttack;
	s.idle = w->m_flTimeWeaponIdle;
	s.nextPrimary = w->m_flNextPrimaryAttack;
	s.nextSecondary = w->m_flNextSecondaryAttack;
	s.inReload = w->m_fInReload;
	s.inSpecial = w->m_fInSpecialReload;
}

inline void FPReloadAfter( CBasePlayerWeapon *w, CBasePlayer *pl, const FPReloadSnap &s )
{
	float k = FPReloadScale();
	if ( k > 0.99f && k < 1.01f )
		return;
	if ( !w->m_fInReload && !w->m_fInSpecialReload )
		return;							// not reloading (or just finished)
	float t = UTIL_WeaponTimeBase();
	// a timer the weapon set this frame, while reloading: stretch what is left of it
#define FPR_STRETCH( v, old ) if ( ( v ) != ( old ) && ( v ) > t ) ( v ) = t + ( ( v ) - t ) * k
	FPR_STRETCH( pl->m_flNextAttack, s.nextAttack );
	FPR_STRETCH( w->m_flTimeWeaponIdle, s.idle );
	FPR_STRETCH( w->m_flNextPrimaryAttack, s.nextPrimary );
	FPR_STRETCH( w->m_flNextSecondaryAttack, s.nextSecondary );
#undef FPR_STRETCH
}

#endif
'''


def rd(p):
    return open(p, encoding='latin-1').read()


def wr(p, s):
    open(p, 'w', encoding='latin-1', newline='').write(s)


def sub1(s, old, new, what):
    if new in s:
        return s
    if old not in s:
        sys.exit('not found: ' + what)
    return s.replace(old, new, 1)


def nl(s):
    return '\r\n' if '\r\n' in s else '\n'


def fix_anim(p):
    s = rd(p)
    n = nl(s)
    s = s.replace('\r\n', '\n')
    s = sub1(s, '//   cl_fpbody_freemanreload 1  GMod mode: the Freeman mod\'s (Garry\'s Mod\'s) reloads for every gun\n',
             '//   cl_fpbody_freemanreload 1  GMod mode: the Freeman mod\'s reloads for every gun\n'
             '//   cl_fpbody_reload_speed 1   reload speed for every gun: 0.5 = half speed (the reload takes\n'
             '//                            twice as long, body and view model slowed to match), 0.1 - 4\n',
             'cvar comment')
    s = sub1(s, 'static cvar_t *cl_fpbody_freemanreload;\n',
             'static cvar_t *cl_fpbody_freemanreload;\nstatic cvar_t *cl_fpbody_reload_speed;\n', 'cvar decl')
    s = sub1(s, '\tcl_fpbody_freemanreload = gEngfuncs.pfnRegisterVariable( "cl_fpbody_freemanreload", "1", FCVAR_ARCHIVE );\n',
             '\tcl_fpbody_freemanreload = gEngfuncs.pfnRegisterVariable( "cl_fpbody_freemanreload", "1", FCVAR_ARCHIVE );\n'
             '\tcl_fpbody_reload_speed = gEngfuncs.pfnRegisterVariable( "cl_fpbody_reload_speed", "1", FCVAR_ARCHIVE );\n',
             'cvar register')

    # how long a reload takes: 1 / speed
    if 'FPReloadSpeedCvar' not in s and 'static bool IsReloadClip' in s:
        s = s.replace('static bool IsReloadClip( int type )\n',
                      '// the same for the client\'s weapon prediction (dlls/fpbody_reload.h)\n'
                      'float FPReloadSpeedCvar( void )\n{\n'
                      '\treturn cl_fpbody_reload_speed ? cl_fpbody_reload_speed->value : 1.0f;\n}\n\n'
                      'static bool IsReloadClip( int type )\n', 1)
    s = sub1(s, 'static void HandleWeaponAnim( model_t *model, int iAnim )\n',
             '// cl_fpbody_reload_speed: how many times longer a reload takes\n'
             'static float ReloadScale( void )\n'
             '{\n'
             '\tfloat s = cl_fpbody_reload_speed ? cl_fpbody_reload_speed->value : 1.0f;\n'
             '\tif ( s <= 0.0f )\n'
             '\t\treturn 1.0f;\n'
             '\treturn 1.0f / Clamp( s, 0.1f, 4.0f );\n'
             '}\n\n'
             '// the same for the client\'s weapon prediction (dlls/fpbody_reload.h)\n'
             'float FPReloadSpeedCvar( void )\n'
             '{\n'
             '\treturn cl_fpbody_reload_speed ? cl_fpbody_reload_speed->value : 1.0f;\n'
             '}\n\n'
             'static bool IsReloadClip( int type )\n'
             '{\n'
             '\treturn type == CLIP_RELOAD || type == CLIP_SHELL_START || type == CLIP_SHELL;\n'
             '}\n\n'
             'static void HandleWeaponAnim( model_t *model, int iAnim )\n', 'ReloadScale')
    s = sub1(s, '\tint type = Classify( modelName, seqName, &variant, &strength );\n\n',
             '\tint type = Classify( modelName, seqName, &variant, &strength );\n'
             '\tif ( IsReloadClip( type ) )\n'
             '\t\tseqDur *= ReloadScale();\t\t\t\t// cl_fpbody_reload_speed: the view model is slowed as much\n\n',
             'seqDur scale')
    # a slowed reload may play the body's animation at a quarter speed
    s = sub1(s, '\tg_ovRate = ( wantDur > 0.05f ) ? Clamp( dur / wantDur, 0.5f, 2.0f ) : 1.0f;\n',
             '\tg_ovRate = ( wantDur > 0.05f ) ? Clamp( dur / wantDur, 0.2f, 2.0f ) : 1.0f;\n', 'ov rate clamp')

    # the Freeman mod's reload per gun
    if 'just the pump at the end' not in s:
        a = s.index('\t// The Freeman mod\'s reloads (Garry\'s Mod\'s reload gestures) first')
        b = s.index('\t// Left 4 Dead\'s reloads where a gun has one', a)
        s = s[:a] + FREEMAN + '\n' + s[b:]
    s = sub1(s, '// Fallback when client weapon prediction is off',
             VMRATE + '\n// Fallback when client weapon prediction is off', 'vm rate')
    wr(p, s.replace('\n', n))


FREEMAN = r'''	// The Freeman mod's reloads first (Half-Life 2: Freeman with its default
	// Counter-Strike: Source stance, hl2_pm_stance css): the Glock and the Desert
	// Eagle Garry's Mod's pistol reload, the .357 its revolver reload, the 9mmAR
	// the MP5's, the crossbow and the sniper rifle the sniper's, the M249 and the
	// RPG the M249 box; the shotgun Counter-Strike: Source's shell inserts, then
	// the end of Garry's Mod's shotgun reload for the pump. A model without one
	// falls back to Garry's Mod's. cl_fpbody_freemanreload 0 = Left 4 Dead /
	// Counter-Strike: Source first.
	if ( ( type == CLIP_RELOAD || type == CLIP_SHELL_START || type == CLIP_SHELL || type == CLIP_PUMP ) && g_bGmodModel &&
		 g_playerHdr && cl_fpbody_gmod->value != 0.0f && cl_fpbody_freemanreload->value != 0.0f && !MoveBusy() )
	{
		const char *fm = NULL, *gm = NULL;
		bool pump = false;
		if ( Has( modelName, "v_shotgun" ) )
		{
			if ( type == CLIP_SHELL_START )
				fm = "css_reload_shotgun_start", gm = "gm_reload_shotgun";
			else if ( type == CLIP_SHELL )
				fm = "css_reload_shotgun_loop", gm = "gm_reload_shotgun";
			else if ( type == CLIP_PUMP && FindSeq( g_playerHdr, "css_reload_shotgun_loop" ) >= 0 )
				gm = "gm_reload_shotgun", pump = true;
		}
		else if ( type == CLIP_RELOAD )
		{
			if ( Has( modelName, "v_9mmhandgun" ) || Has( modelName, "v_desert_eagle" ) )
				gm = "gm_reload_pistol";
			else if ( Has( modelName, "v_357" ) )
				gm = "gm_reload_revolver";
			else if ( Has( modelName, "v_9mmar" ) )
				fm = "css_reload_smg", gm = "gm_reload_smg1";
			else if ( Has( modelName, "v_crossbow" ) || Has( modelName, "v_m40a1" ) )
				fm = "css_reload_sniper", gm = "gm_reload_ar2";
			else if ( Has( modelName, "v_saw" ) || Has( modelName, "v_rpg" ) )
				fm = "css_reload_m249", gm = Has( modelName, "v_rpg" ) ? "gm_reload_smg1_alt" : "gm_reload_ar2";
			else if ( Has( modelName, "v_spore_launcher" ) )
				gm = "gm_reload_smg1_alt";
		}
		const char *name = ( fm && FindSeq( g_playerHdr, fm ) >= 0 ) ? fm : gm;
		if ( name && FindSeq( g_playerHdr, name ) >= 0 && StartOverlay( name, false, pump ? 0.0f : seqDur ) )
		{
			g_ovLoop = false;							// one shell per insert
			if ( pump )
				g_ovStart -= 0.7f * g_ovDur;			// just the pump at the end
			g_l4dShellAt = ( type == CLIP_SHELL_START || type == CLIP_SHELL ) ? g_now : -10.0f;
			StartClip( CLIP_NONE, 0, 0.0f, 0.0f );
			return;
		}
	}
'''

VMRATE = r'''// cl_fpbody_reload_speed: the view model's reload animations play slower (or
// faster) to match the reload's length. Every frame, body mode or not.
void FPAnim_ViewModelRate( void )
{
	cl_entity_t *view = gEngfuncs.GetViewModel();
	if ( !view || !view->model || view->model->type != mod_studio )
		return;
	studiohdr_t *hdr = (studiohdr_t *)IEngineStudio.Mod_Extradata( view->model );
	if ( !hdr || view->curstate.sequence < 0 || view->curstate.sequence >= hdr->numseq )
		return;
	mstudioseqdesc_t *seq = (mstudioseqdesc_t *)( (byte *)hdr + hdr->seqindex ) + view->curstate.sequence;
	char seqName[ 32 ], modelName[ 64 ];
	Lower( seq->label, seqName, sizeof( seqName ) );
	Lower( view->model->name, modelName, sizeof( modelName ) );
	int variant;
	float strength;
	static bool s_slowed;
	float k = ReloadScale();
	if ( IsReloadClip( Classify( modelName, seqName, &variant, &strength ) ) && ( k < 0.99f || k > 1.01f ) )
	{
		view->curstate.framerate = 1.0f / k;
		s_slowed = true;
	}
	else if ( s_slowed )
	{
		view->curstate.framerate = 1.0f;		// back to normal after the reload
		s_slowed = false;
	}
}
'''


def fix_fpbody(p):
    s = rd(p)
    n = nl(s)
    s = s.replace('\r\n', '\n')
    if 'FPAnim_ViewModelRate' not in s:
        s = sub1(s, '\tif ( FPBody_Active() )\n\t\tFPAnim_Frame( pparams );\n',
                 '\tFPAnim_ViewModelRate();\t\t\t\t\t// cl_fpbody_reload_speed\n'
                 '\tif ( FPBody_Active() )\n\t\tFPAnim_Frame( pparams );\n', 'fpbody frame')
        s, k = re.subn(r'\nvoid FPBody_BeginFrame\(', '\nvoid FPAnim_ViewModelRate( void );\n\nvoid FPBody_BeginFrame(', s, count=1)
        if not k:
            sys.exit('FPBody_BeginFrame not found in ' + p)
    wr(p, s.replace('\n', n))


def fix_player(p):
    s = rd(p)
    ph = rd(os.path.join(os.path.dirname(p), 'player.h'))
    # FWGS's newer code holds the active item as a CBasePlayerWeapon already
    getw = 'm_pActiveItem' if re.search(r'CBasePlayerWeapon\s*\*\s*m_pActiveItem;', ph) else \
        '(CBasePlayerWeapon *)m_pActiveItem->GetWeaponPtr()'
    n = nl(s)
    s = s.replace('\r\n', '\n')
    if 'fpbody_reload.h' not in s:
        s, k = re.subn(r'\nvoid CBasePlayer::ItemPostFrame\(', '\n#include "fpbody_reload.h"\t// cl_fpbody_reload_speed\n\nvoid CBasePlayer::ItemPostFrame(', s, count=1)
        if not k:
            sys.exit('player include')
    if 'FPReloadBefore' not in s:
        s, k = re.subn(r'\n(\t+)m_pActiveItem->ItemPostFrame\( ?\);\n',
                       lambda m: ('\n%s{\n%s\tCBasePlayerWeapon *fpw = GETW;\n'
                       '%s\tFPReloadSnap fps;\n%s\tif ( fpw ) FPReloadBefore( fpw, this, fps );\n'
                       '%s\tm_pActiveItem->ItemPostFrame();\n%s\tif ( fpw ) FPReloadAfter( fpw, this, fps );\t// cl_fpbody_reload_speed\n%s}\n'
                       % ((m.group(1),) * 7)).replace('GETW', getw), s, count=1)
        if not k:
            sys.exit('player ItemPostFrame not found in ' + p)
    wr(p, s.replace('\n', n))


def fix_client(p):
    s = rd(p)
    n = nl(s)
    s = s.replace('\r\n', '\n')
    if 'fpbody_reload.h' not in s:
        s = re.sub(r'\n(/\*[^\n]*\n)?void HUD_WeaponsPostThink\(', lambda m: '\n#include "fpbody_reload.h"\t// cl_fpbody_reload_speed\n' + m.group(0), s, count=1)
        if 'fpbody_reload.h' not in s:
            sys.exit('client include')
    if 'FPReloadBefore' not in s:
        s, k = re.subn(r'\n(\t+)pWeapon->ItemPostFrame\(\);\n',
                       lambda m: '\n%s{\n%s\tFPReloadSnap fps;\n%s\tFPReloadBefore( pWeapon, &player, fps );\n'
                       '%s\tpWeapon->ItemPostFrame();\n%s\tFPReloadAfter( pWeapon, &player, fps );\t// cl_fpbody_reload_speed\n%s}\n'
                       % ((m.group(1),) * 6), s, count=1)
        if not k:
            sys.exit('client ItemPostFrame not found in ' + p)
    wr(p, s.replace('\n', n))


def fix_m249(p):
    s = rd(p)
    if 'FPReloadScale' in s:
        return
    s = sub1(s, 'gpGlobals->time >= m_flReloadStart + 1.33)', 'gpGlobals->time >= m_flReloadStart + 1.33 * FPReloadScale())', 'm249')
    last = list(re.finditer(r'#include "[^"]+"(\r?\n)', s))[-1]
    s = s[:last.end()] + '#include "fpbody_reload.h"' + last.group(1) + s[last.end():]
    if 'fpbody_reload.h' not in s:
        sys.exit('m249 include')
    open(p, 'w', encoding='latin-1', newline='').write(s)


def main(sdk):
    open(os.path.join(sdk, 'dlls', 'fpbody_reload.h'), 'w', newline='\r\n').write(HDR)
    fix_anim(os.path.join(sdk, 'cl_dll', 'fpbody_anim.cpp'))
    fix_fpbody(os.path.join(sdk, 'cl_dll', 'fpbody.cpp'))
    fix_player(os.path.join(sdk, 'dlls', 'player.cpp'))
    fix_client(os.path.join(sdk, 'cl_dll', 'hl', 'hl_weapons.cpp'))
    m = os.path.join(sdk, 'dlls', 'weapons', 'CM249.cpp')
    if os.path.exists(m):
        fix_m249(m)
    print('ok', sdk)


if __name__ == '__main__':
    for d in sys.argv[1:]:
        main(d)
