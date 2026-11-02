// fpbody_anim.cpp - procedural body animations for the "True First Person" mod.
//
// Everything here moves the third-person body's bones directly, after the
// engine has posed the skeleton from player.mdl's own sequences:
//
//   Weapon actions   (detected from the view model's animation names, so it
//                     works for every weapon, including ones added by mods)
//     draw / deploy      arms come up from low
//     holster            arms go down
//     shoot / fire       recoil kick, scaled per weapon
//     reload             gun tilts in, off hand drops to the belt and back
//     shotgun shells     gun stays tilted, off hand feeds each shell, pump
//     crowbar attacks    big right-arm swings (three swing styles)
//     grenade / snark    wind-up and throw; pin pull with the off hand
//     tripmine / satchel reach down to place it; radio button press
//     gauss / egon       charging tremble and beam vibration
//   Action buttons
//     +use               off hand reaches forward (held = keeps pushing)
//     flashlight         off hand taps the helmet
//     ladders            off hand climbs, gun lowered
//     landing            body crouches into the impact
//     turning / strafing weapon sway and lag
//   Camera
//     the view follows the head bone's tilt and bob (not only its position)
//
// Console variables
//   cl_fpbody_anims     1    procedural animations on/off
//   cl_fpbody_animscale 1    strength of all procedural animations
//   cl_fpbody_sway      1    strength of weapon sway / lag
//   cl_fpbody_headrot   0.6  how much the camera follows the head's rotation
//   cl_fpbody_runbob    1    arms bob with the steps while moving with a weapon
//   cl_fpbody_actcam    1    show full-body acts from behind (0 = stay in the head)
//   cl_fpbody_gmod      1    use the GMod animations in the player model when present
//   cl_fpbody_aimfire   1    turn the gun straight down the view while firing
//   cl_fpbody_gunlower  20   classic mode: degrees the shouldered Condition Zero holds are
//                            tilted down in our own view (0 = as in Condition Zero)
//   cl_fpbody_glreload  1    reload the 9mmAR grenade launcher after every shot (body animation)
//   cl_fpbody_pickup    1    bend down and grab anything you pick up (ammo, weapons, health, batteries, items)
//   cl_fpbody_l4dreload 1    Left 4 Dead reloads for pistols, rifles and the shotgun (GMod mode)
//   cl_fpbody_reloads   cz   classic mode third-person reloads: cz = Condition Zero first,
//                            cs = Counter-Strike 1.6 first, sven = Sven Co-op first
//                            (the others fill gaps), 0 = off
//   (server) sv_fpbody_anims cz  classic mode weapon holds: cz = Condition Zero,
//                            cs = Counter-Strike 1.6 (falls back to Condition Zero).
//                            The 9mmAR (an M16) always uses Counter-Strike 1.6's rifle set.
//   cl_fpbody_holdlower 10   GMod mode: degrees two-handed guns are held lower than the sights
//                            until you fire (per gun: fp_hold <down> <right> <back>)
//   cl_fpbody_usepalm   1    pressing use: the left palm flat (down, or on a charger's panel)
//   cl_fpbody_offhand_release 1  the off hand lets go of the gun for use, the flashlight,
//                            ladders, barnacles, hard landings and the relaxed holds
//   cl_fpbody_offhand   1    keep the off hand on two-handed guns (arm IK; in classic mode,
//                            the left hand on the Tau Cannon's side bar)
//   cl_fpbody_grip_fwd  0    move the off-hand grip forward/back along the gun (units)
//   cl_fpbody_grip_down 0    move the off-hand grip down/up (units)
//   cl_fpbody_moves     1    play the Freeman moves' animations (kick, vault, climb, prone,
//                            falls, landings, slide, draws)
//   cl_fpbody_atease    1    lower the gun after a few quiet seconds (at ease)
//   cl_fpbody_atease_delay 4 seconds without shooting, reloading or getting hurt
//   cl_fpbody_doubletap 1    double-tap duck = prone, double-tap reload = holster all
//   cl_fpbody_epa       1    ExtendedER Player Animations: fidgets, pickups, panic, flinches,
//                            climbing off ladders, raising the gun when a hostile is in view
//   cl_fpbody_epa_fidget_idle 3    seconds standing around before fidgets can start
//   cl_fpbody_epa_fidget_min / _max 3 / 10     wait between fidget checks (seconds)
//   cl_fpbody_epa_fidget_chance 1              chance a check plays one
//   cl_fpbody_epa_fidget_speed 1               playback speed of the fidgets (2 = twice as fast)
//   cl_fpbody_gaitspeed 0.7  with the GMod animations: how fast the walk / run cycles play
//                            for your speed (1 = feet match the ground, lower = slower legs)
//   cl_fpbody_sprint    1    sprinting (+alt1, bound to shift in autoexec.cfg): faster, with stamina
//   cl_fpbody_sprint_time 6  seconds of sprinting on a full stamina bar
//   cl_fpbody_sprint_recover 4  seconds to refill it (starts a second after you stop)
//   cl_fpbody_contextual 1   Contextual Player Animations: a push for doors, a press for
//                            buttons, a reach for chargers and other things you +use,
//                            flinching where a bullet hit, going under / coming up for air
//
// Console commands (the Freeman mod's moves; bound in fpbody's autoexec.cfg)
//   pm_kick           kick (look down to stomp, jump first for a drop kick)
//   pm_prone          lie down / get up (or double-tap duck)
//   pm_atease         lower / raise the gun
//   pm_holster        put the gun away (empty hands); again, or fire, takes it out
//   Vaulting: jump at a ledge or low wall holding forward. Wall climbing: jump at
//   a wall and keep holding jump. Slide: duck while running.
//
// Console commands (GMod animations, need fpbody/models/player.mdl)
//   fp_act <name>     play a gesture/taunt, e.g. "fp_act dance", "fp_act wave"
//   fp_act_stop       stop it
//   fp_actlist        list every available animation

#include <stdarg.h>
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include "hud.h"
#include "cl_util.h"
#include "cvardef.h"
#include "const.h"
#include "com_model.h"
#include "studio.h"
#include "entity_state.h"
#include "cl_entity.h"
#include "ref_params.h"
#include "r_studioint.h"
#include "kbutton.h"
#include "in_defs.h"	// PITCH YAW ROLL
#include "in_buttons.h"

#include <string.h>
#include <math.h>

#include "fpbody.h"
#include "fpbody_anim.h"
#include "fpbody_pm.h"
#include "ammohistory.h"
#include "fpbody_game.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

extern engine_studio_api_t IEngineStudio;
extern kbutton_t in_use;
extern kbutton_t in_attack;
extern kbutton_t in_attack2;
extern kbutton_t in_jump;
extern kbutton_t in_duck;
extern kbutton_t in_reload;
extern kbutton_t in_alt1;
FPBODY_DECLARE_ONLADDER	// pm_shared, set by client movement prediction (fpbody_game.h)

static cvar_t *cl_fpbody_anims;
static cvar_t *cl_fpbody_animscale;
static cvar_t *cl_fpbody_sway;
static cvar_t *cl_fpbody_headrot;
static cvar_t *cl_fpbody_runbob;
static float g_runW, g_runPhase;
static cvar_t *cl_fpbody_actcam;
static cvar_t *cl_fpbody_gmod;
static cvar_t *cl_fpbody_aimfire;
static cvar_t *cl_fpbody_offhand;
static cvar_t *cl_fpbody_offhand_release;
static cvar_t *cl_fpbody_usepalm;
static cvar_t *cl_fpbody_holdlower;
static cvar_t *cl_fpbody_reloads;
static cvar_t *cl_fpbody_glreload;
static cvar_t *cl_fpbody_l4dreload;
static cvar_t *cl_fpbody_pickup;
static bool g_pickupPending;			// the HUD got a pickup message
static float g_pickupUntil;			// the pickup reach is playing
static float g_l4dShellAt = -10.0f;	// last Left 4 Dead shotgun shell
static float g_glOpenW;				// grenade launcher reload: left hand at the launcher's opening
static float g_glReloadAt;			// when to reload the 9mmAR grenade launcher (0 = no)
static cvar_t *cl_fpbody_gunlower;
static float g_gunLowerW;
static cvar_t *cl_fpbody_grip_fwd;
static cvar_t *cl_fpbody_grip_down;

// ---------------------------------------------------------------------------
// Weapon geometry for aiming and the off hand, measured from the p_ models in
// the right hand's bone space (see tools/gmod_anims/weapons.py)
// ---------------------------------------------------------------------------

struct gun_t
{
	const char *model;
	float axis[ 3 ];	// barrel direction
	float grip[ 3 ];	// where the off hand holds it
	float down;			// how far below the barrel line the off-hand wrist sits; < 0 = no off-hand IK
	int pistol;			// two-handed pistol hold: shooting hand comes in front of the chest
};

static const gun_t g_guns[] =
{
	// measured on the HD weapon models (valve_hd / bshift_hd), which the mods use
	{ "p_9mmhandgun", { 0.9195f, 0.0769f, 0.3855f }, { 1.35f, 0.42f, 0.59f }, 2.5f, 1 },
	{ "p_glock", { 0.9195f, 0.0769f, 0.3855f }, { 1.35f, 0.42f, 0.59f }, 2.5f, 1 },
	{ "p_357", { 0.9702f, 0.1144f, 0.2138f }, { 1.09f, 0.38f, 1.91f }, 2.5f, 1 },
	{ "p_9mmar", { 0.9923f, 0.0941f, 0.0799f }, { 13.43f, 1.17f, 3.95f }, 1.5f, 0 },
	{ "p_shotgun", { 0.9912f, 0.0928f, 0.0946f }, { 13.79f, 1.18f, 3.44f }, 1.5f, 0 },
	{ "p_crossbow", { 0.9954f, 0.0888f, 0.0347f }, { 12.06f, 1.58f, 2.80f }, 1.5f, 0 },
	{ "p_gauss", { 0.9912f, 0.1289f, 0.0308f }, { 12.69f, 1.84f, 4.70f }, 2.0f, 0 },
	{ "p_rpg", { 0.9932f, 0.1006f, -0.0581f }, { 9.78f, 2.00f, 4.58f }, 2.0f, 0 },
	{ "p_hgun", { 0.9892f, 0.0215f, -0.1453f }, { 8.58f, 0.45f, -0.07f }, 2.0f, 0 },
	{ "p_egon", { 0.9889f, 0.0000f, 0.1483f }, { 16.00f, 0.50f, 3.00f }, 2.0f, 0 },
	// Opposing Force weapons (only exist in SD)
	{ "p_saw", { 0.9943f, 0.0521f, 0.0931f }, { 10.38f, 0.76f, 3.18f }, 1.5f, 0 },
	{ "p_m40a1", { 0.9891f, 0.1037f, 0.1044f }, { 13.53f, 1.06f, 2.77f }, 1.5f, 0 },
	{ "p_shock", { 0.9867f, 0.1473f, -0.0681f }, { 9.92f, 0.48f, 4.68f }, 1.5f, 0 },
	{ "p_spore_launcher", { 0.9999f, 0.0105f, -0.0087f }, { 9.17f, 0.30f, 1.65f }, 2.0f, 0 },
	{ "p_displacer", { 0.9901f, 0.1404f, 0.0014f }, { 10.21f, 0.98f, 6.22f }, 2.0f, 0 },
	{ "p_bgrap", { 0.9996f, -0.0220f, -0.0173f }, { 8.34f, -0.50f, -0.58f }, 2.0f, 0 },
	{ "p_desert_eagle", { 0.9947f, 0.0902f, 0.0499f }, { 1.33f, 0.45f, 2.65f }, 2.5f, 1 },
};

static float g_lastShot = -10.0f;	// last time a firing animation started
static bool g_attackHeld;
static float g_aimW;				// 0..1 how much the gun is turned down the view
static float g_offW;				// 0..1 off-hand IK weight

// ---------------------------------------------------------------------------
// GMod animation overlays (gm_* sequences in the player model)
// ---------------------------------------------------------------------------

static const studiohdr_t *g_playerHdr;		// the local player's model, seen while drawing
static bool g_bGmodModel;					// it contains converted GMod animations
static char g_ovRequest[ 64 ];				// pending fp_act request (resolved when drawing)
static int g_ovSeq = -1;
static float g_ovStart;
static float g_ovDur;
static float g_ovRate = 1.0f;
static bool g_ovFull;
static bool g_ovLoop;
static bool g_ovUser;						// started by fp_act (vs. automatic reload)
// what started the overlay: fp_act, a reload / gesture, a Freeman move (one-off or
// looping: prone, falling, climbing) or the at-ease lowered gun
enum { OVK_USER = 1, OVK_RELOAD, OVK_MOVE, OVK_LOOP, OVK_EASE };
static int g_ovKind;
static bool MoveBusy( void ) { return g_ovSeq >= 0 && ( g_ovKind == OVK_MOVE || g_ovKind == OVK_LOOP ); }
static bool StartOverlayKind( const char *name, int kind, float wantDur );
static bool OverlayIs( const char *name );
static const char *OverlayName( void );
static cvar_t *cl_fpbody_debug;
static cvar_t *cl_fpbody_elbowdown;
static cvar_t *cl_fpbody_wristtwist;
static cvar_t *cl_fpbody_pump;
static cvar_t *cl_fpbody_grip_side;
static cvar_t *cl_fpbody_swimhold;
static cvar_t *cl_fpbody_fingers;
static float g_relaxW;			// how far the at-ease hold is in (0..1), for fp_gun_relax
static void FP_GripCmd( void );
static void FP_GripSetCmd( void );
static void FP_GunCmd( void );
static void FP_GunRelaxCmd( void );
static void FP_GunSetCmd( void );
static void FP_GunRelaxSetCmd( void );
static void FP_HoldCmd( void );
static void FP_HoldSetCmd( void );
static void FP_RelaxHandCmd( void );
static void FP_RelaxLHandCmd( void );
static void FP_RelaxHandSetCmd( void );
static void FP_RelaxLHandSetCmd( void );
static void FP_FingersCmd( void );
static void FP_FingersSetCmd( void );
static cvar_t *cl_fpbody_reloadset;
// cl_fpbody_debug 1: print what the body starts playing (overlays, gun clips) to the console
static void FPDbg( const char *fmt, ... )
{
	if ( !cl_fpbody_debug || cl_fpbody_debug->value == 0.0f )
		return;
	char buf[ 256 ];
	va_list ap;
	va_start( ap, fmt );
	vsnprintf( buf, sizeof( buf ), fmt, ap );
	va_end( ap );
	gEngfuncs.Con_Printf( "[fpanim %.2f] %s", gEngfuncs.GetClientTime(), buf );
}
static cvar_t *cl_fpbody_moves;
static cvar_t *cl_fpbody_atease;
static cvar_t *cl_fpbody_atease_delay;
static cvar_t *cl_fpbody_doubletap;
static cvar_t *cl_fpbody_epa;
static cvar_t *cl_fpbody_epa_fidget_idle;
static cvar_t *cl_fpbody_epa_fidget_min;
static cvar_t *cl_fpbody_epa_fidget_max;
static cvar_t *cl_fpbody_epa_fidget_chance;
static cvar_t *cl_fpbody_epa_fidget_speed;
static cvar_t *cl_fpbody_contextual;
static cvar_t *cl_fpbody_sprint;
static cvar_t *cl_fpbody_gaitspeed;
static cvar_t *cl_fpbody_sprint_time;
static cvar_t *cl_fpbody_sprint_recover;
static float g_mvActivity = -100.0f;		// last time the gun was used (at ease timer)
static void PM_KickCmd( void );
static void PM_ProneCmd( void );
static void FP_InvNextCmd( void );
static void FP_InvPrevCmd( void );
static void PM_AtEaseCmd( void );
static void PM_HolsterCmd( void );
static float g_speed2D;

static void StopOverlay( void )
{
	if ( g_ovSeq >= 0 )
		FPDbg( "stop %s\n", OverlayName() );
	g_ovSeq = -1;
	g_ovRequest[ 0 ] = 0;
}
static void FP_ActCmd( void );
static void FP_ActList( void );
static bool StartOverlay( const char *name, bool user, float wantDur );
static int FindSeq( const studiohdr_t *hdr, const char *name );
static int LocalSeq( cl_entity_t *local );

// ---------------------------------------------------------------------------
// Small math helpers
// ---------------------------------------------------------------------------

typedef float mat3_t[ 3 ][ 3 ];

static float Clamp( float x, float lo, float hi ) { return x < lo ? lo : ( x > hi ? hi : x ); }
static float Clamp01( float x ) { return Clamp( x, 0.0f, 1.0f ); }

static float Smooth( float x )
{
	x = Clamp01( x );
	return x * x * ( 3.0f - 2.0f * x );
}

// 0 -> 1 over the first `in` of t, 1 -> 0 over the last `out` of t (t in 0..1)
static float Env( float t, float in, float out )
{
	float a = in > 0.0f ? Smooth( t / in ) : 1.0f;
	float b = out > 0.0f ? 1.0f - Smooth( ( t - ( 1.0f - out ) ) / out ) : 1.0f;
	if ( t >= 1.0f ) b = 0.0f;
	return a * b;
}

// A single smooth hump between a and b
static float Bump( float t, float a, float b )
{
	if ( t <= a || t >= b )
		return 0.0f;
	return (float)sin( M_PI * ( t - a ) / ( b - a ) );
}

// Piecewise smooth interpolation through (t, value) pairs
static float Keys( const float *k, int count, float t )
{
	if ( t <= k[ 0 ] )
		return k[ 1 ];
	for ( int i = 0; i < count - 1; i++ )
	{
		float t0 = k[ i * 2 ], v0 = k[ i * 2 + 1 ];
		float t1 = k[ i * 2 + 2 ], v1 = k[ i * 2 + 3 ];
		if ( t <= t1 )
		{
			float f = Smooth( ( t - t0 ) / ( t1 - t0 ) );
			return v0 + ( v1 - v0 ) * f;
		}
	}
	return k[ ( count - 1 ) * 2 + 1 ];
}

static void Cross( const float *a, const float *b, float *out )
{
	out[ 0 ] = a[ 1 ] * b[ 2 ] - a[ 2 ] * b[ 1 ];
	out[ 1 ] = a[ 2 ] * b[ 0 ] - a[ 0 ] * b[ 2 ];
	out[ 2 ] = a[ 0 ] * b[ 1 ] - a[ 1 ] * b[ 0 ];
}

static float Dot3( const float *a, const float *b )
{
	return a[ 0 ] * b[ 0 ] + a[ 1 ] * b[ 1 ] + a[ 2 ] * b[ 2 ];
}

static float Normalize3( float *v )
{
	float len = (float)sqrt( Dot3( v, v ) );
	if ( len > 1e-6f )
	{
		v[ 0 ] /= len; v[ 1 ] /= len; v[ 2 ] /= len;
	}
	return len;
}

// Rotation of `deg` degrees around unit `axis` (right-hand rule)
static void AxisAngle( const float *axis, float deg, mat3_t m )
{
	float rad = deg * (float)( M_PI / 180.0 );
	float c = (float)cos( rad ), s = (float)sin( rad ), t = 1.0f - c;
	float x = axis[ 0 ], y = axis[ 1 ], z = axis[ 2 ];

	m[ 0 ][ 0 ] = t * x * x + c;     m[ 0 ][ 1 ] = t * x * y - s * z; m[ 0 ][ 2 ] = t * x * z + s * y;
	m[ 1 ][ 0 ] = t * x * y + s * z; m[ 1 ][ 1 ] = t * y * y + c;     m[ 1 ][ 2 ] = t * y * z - s * x;
	m[ 2 ][ 0 ] = t * x * z - s * y; m[ 2 ][ 1 ] = t * y * z + s * x; m[ 2 ][ 2 ] = t * z * z + c;
}

static void MatMul3( const mat3_t a, const mat3_t b, mat3_t out )
{
	mat3_t r;
	for ( int i = 0; i < 3; i++ )
		for ( int j = 0; j < 3; j++ )
			r[ i ][ j ] = a[ i ][ 0 ] * b[ 0 ][ j ] + a[ i ][ 1 ] * b[ 1 ][ j ] + a[ i ][ 2 ] * b[ 2 ][ j ];
	memcpy( out, r, sizeof( r ) );
}

static void Identity3( mat3_t m )
{
	memset( m, 0, sizeof( mat3_t ) );
	m[ 0 ][ 0 ] = m[ 1 ][ 1 ] = m[ 2 ][ 2 ] = 1.0f;
}

// ---------------------------------------------------------------------------
// Animation clips
// ---------------------------------------------------------------------------

enum
{
	CLIP_NONE = 0,
	CLIP_DRAW,
	CLIP_HOLSTER,
	CLIP_RECOIL,
	CLIP_RELOAD,
	CLIP_SHELL_START,
	CLIP_SHELL,
	CLIP_PUMP,
	CLIP_FIDDLE,
	CLIP_MELEE,
	CLIP_THROW,
	CLIP_PINPULL,
	CLIP_PLACE,
	CLIP_PRESS,
	CLIP_CHARGE,	// looping until the next weapon animation
	CLIP_BEAM,		// looping until the next weapon animation
	CLIP_IDLE		// pseudo-clip: ends loops, otherwise ignored
};

struct clip_t
{
	int type;
	int variant;
	float start;
	float dur;
	float strength;
};

// Everything a frame's animations add up to
struct pose_t
{
	float armsPitch;	// both arms (and the gun), degrees, + = down
	float armsYaw;		// + = toward the left
	float armsRoll;		// + = right side down
	float armsBack;		// units pulled back toward the body
	float rPitch;		// right arm only, + = down
	float rYaw;			// right arm only, + = left
	float lPitch;		// left arm only, + = down
	float lBack;		// left arm pulled back (units)
	float lAimDir[ 3 ];	// accumulated (weighted) direction for the left arm
	float lAimW;		// total weight of that direction
	float spinePitch;	// upper body bend forward, degrees
};

static clip_t g_cur;		// current weapon clip
static clip_t g_prev;		// previous one, fading out
static float g_prevFadeStart;
static bool g_bHookSeen;	// weapon anims arrive through the prediction hook
static int g_lastPollSeq = -1;
static float g_lastPollAnimTime = -1.0f;
static int g_lastWeaponModel = -1;

// action-button state
static bool g_useDown;
static float g_useStart = -10.0f;
static float g_useHoldW;
static float g_usePalmW;			// this frame's +use reach (0..1): the left palm turns down / onto the panel
static int g_lastFlash = -1;
static float g_flashStart = -10.0f;
static float g_landStart = -10.0f;
static float g_landStrength;
static int g_wasOnGround = 1;
static float g_maxFallSpeed;
static float g_ladderW;
static float g_ladderPhase;
static float g_ropeVz;			// Opposing Force ropes: how fast we climb (from the height we move)
static float g_lastZ;

// sway state
static float g_lastYaw, g_lastPitch;
static bool g_haveLastAngles;
static float g_swayYaw, g_swayPitch, g_swayRoll;

// camera / head rotation state
static mat3_t g_headSmooth;
static bool g_haveHeadSmooth;
static float g_headAngOfs[ 3 ];
static float g_headOfsTime = -10.0f;
static float g_lastHeadTime = -10.0f;

// per-frame values captured in FPAnim_Frame for use while posing bones
static float g_frameTime;
static float g_now;

void FPAnim_Init( void )
{
	cl_fpbody_anims     = gEngfuncs.pfnRegisterVariable( "cl_fpbody_anims", "1", FCVAR_ARCHIVE );
	cl_fpbody_animscale = gEngfuncs.pfnRegisterVariable( "cl_fpbody_animscale", "1", FCVAR_ARCHIVE );
	cl_fpbody_sway      = gEngfuncs.pfnRegisterVariable( "cl_fpbody_sway", "1", FCVAR_ARCHIVE );
	cl_fpbody_headrot   = gEngfuncs.pfnRegisterVariable( "cl_fpbody_headrot", "0.6", FCVAR_ARCHIVE );
	cl_fpbody_runbob    = gEngfuncs.pfnRegisterVariable( "cl_fpbody_runbob", "1", FCVAR_ARCHIVE );
	cl_fpbody_actcam    = gEngfuncs.pfnRegisterVariable( "cl_fpbody_actcam", "1", FCVAR_ARCHIVE );
	cl_fpbody_gmod      = gEngfuncs.pfnRegisterVariable( "cl_fpbody_gmod", "1", FCVAR_ARCHIVE );
	cl_fpbody_aimfire   = gEngfuncs.pfnRegisterVariable( "cl_fpbody_aimfire", "1", FCVAR_ARCHIVE );
	cl_fpbody_offhand   = gEngfuncs.pfnRegisterVariable( "cl_fpbody_offhand", "1", FCVAR_ARCHIVE );
	cl_fpbody_offhand_release = gEngfuncs.pfnRegisterVariable( "cl_fpbody_offhand_release", "1", FCVAR_ARCHIVE );
	cl_fpbody_usepalm = gEngfuncs.pfnRegisterVariable( "cl_fpbody_usepalm", "1", FCVAR_ARCHIVE );
	cl_fpbody_holdlower = gEngfuncs.pfnRegisterVariable( "cl_fpbody_holdlower", "10", FCVAR_ARCHIVE );
	cl_fpbody_reloads   = gEngfuncs.pfnRegisterVariable( "cl_fpbody_reloads", "cz", FCVAR_ARCHIVE );
	cl_fpbody_glreload  = gEngfuncs.pfnRegisterVariable( "cl_fpbody_glreload", "1", FCVAR_ARCHIVE );
	cl_fpbody_debug     = gEngfuncs.pfnRegisterVariable( "cl_fpbody_debug", "0", 0 );
	cl_fpbody_elbowdown = gEngfuncs.pfnRegisterVariable( "cl_fpbody_elbowdown", "0.7", FCVAR_ARCHIVE );
	cl_fpbody_wristtwist = gEngfuncs.pfnRegisterVariable( "cl_fpbody_wristtwist", "0.65", FCVAR_ARCHIVE );
	cl_fpbody_pump = gEngfuncs.pfnRegisterVariable( "cl_fpbody_pump", "4", FCVAR_ARCHIVE );
	cl_fpbody_reloadset = gEngfuncs.pfnRegisterVariable( "cl_fpbody_reloadset", "css", FCVAR_ARCHIVE );
	cl_fpbody_l4dreload = gEngfuncs.pfnRegisterVariable( "cl_fpbody_l4dreload", "1", FCVAR_ARCHIVE );
	cl_fpbody_pickup    = gEngfuncs.pfnRegisterVariable( "cl_fpbody_pickup", "1", FCVAR_ARCHIVE );
	cl_fpbody_gunlower  = gEngfuncs.pfnRegisterVariable( "cl_fpbody_gunlower", "20", FCVAR_ARCHIVE );
	cl_fpbody_grip_fwd  = gEngfuncs.pfnRegisterVariable( "cl_fpbody_grip_fwd", "0", FCVAR_ARCHIVE );
	cl_fpbody_grip_down = gEngfuncs.pfnRegisterVariable( "cl_fpbody_grip_down", "0", FCVAR_ARCHIVE );
	cl_fpbody_grip_side = gEngfuncs.pfnRegisterVariable( "cl_fpbody_grip_side", "0", FCVAR_ARCHIVE );
	cl_fpbody_swimhold  = gEngfuncs.pfnRegisterVariable( "cl_fpbody_swimhold", "1", FCVAR_ARCHIVE );
	cl_fpbody_fingers   = gEngfuncs.pfnRegisterVariable( "cl_fpbody_fingers", "1", FCVAR_ARCHIVE );

	cl_fpbody_moves     = gEngfuncs.pfnRegisterVariable( "cl_fpbody_moves", "1", FCVAR_ARCHIVE );
	cl_fpbody_atease    = gEngfuncs.pfnRegisterVariable( "cl_fpbody_atease", "1", FCVAR_ARCHIVE );
	cl_fpbody_atease_delay = gEngfuncs.pfnRegisterVariable( "cl_fpbody_atease_delay", "4", FCVAR_ARCHIVE );
	cl_fpbody_doubletap = gEngfuncs.pfnRegisterVariable( "cl_fpbody_doubletap", "1", FCVAR_ARCHIVE );
	cl_fpbody_epa       = gEngfuncs.pfnRegisterVariable( "cl_fpbody_epa", "1", FCVAR_ARCHIVE );
	cl_fpbody_contextual = gEngfuncs.pfnRegisterVariable( "cl_fpbody_contextual", "1", FCVAR_ARCHIVE );
	cl_fpbody_sprint    = gEngfuncs.pfnRegisterVariable( "cl_fpbody_sprint", "1", FCVAR_ARCHIVE );
	cl_fpbody_gaitspeed = gEngfuncs.pfnRegisterVariable( "cl_fpbody_gaitspeed", "0.7", FCVAR_ARCHIVE );
	cl_fpbody_sprint_time = gEngfuncs.pfnRegisterVariable( "cl_fpbody_sprint_time", "6", FCVAR_ARCHIVE );
	cl_fpbody_sprint_recover = gEngfuncs.pfnRegisterVariable( "cl_fpbody_sprint_recover", "4", FCVAR_ARCHIVE );
	cl_fpbody_epa_fidget_idle   = gEngfuncs.pfnRegisterVariable( "cl_fpbody_epa_fidget_idle", "3", FCVAR_ARCHIVE );
	cl_fpbody_epa_fidget_min    = gEngfuncs.pfnRegisterVariable( "cl_fpbody_epa_fidget_min", "3", FCVAR_ARCHIVE );
	cl_fpbody_epa_fidget_max    = gEngfuncs.pfnRegisterVariable( "cl_fpbody_epa_fidget_max", "10", FCVAR_ARCHIVE );
	cl_fpbody_epa_fidget_chance = gEngfuncs.pfnRegisterVariable( "cl_fpbody_epa_fidget_chance", "1", FCVAR_ARCHIVE );
	cl_fpbody_epa_fidget_speed  = gEngfuncs.pfnRegisterVariable( "cl_fpbody_epa_fidget_speed", "1", FCVAR_ARCHIVE );
	gEngfuncs.pfnAddCommand( "pm_kick", PM_KickCmd );
	gEngfuncs.pfnAddCommand( "fp_invnext", FP_InvNextCmd );
	gEngfuncs.pfnAddCommand( "fp_invprev", FP_InvPrevCmd );
	if ( FPM_ENABLE_PRONE )
		gEngfuncs.pfnAddCommand( "pm_prone", PM_ProneCmd );
	gEngfuncs.pfnAddCommand( "pm_atease", PM_AtEaseCmd );
	gEngfuncs.pfnAddCommand( "fp_grip", FP_GripCmd );
	gEngfuncs.pfnAddCommand( "fp_grip_set", FP_GripSetCmd );
	gEngfuncs.pfnAddCommand( "fp_gun", FP_GunCmd );
	gEngfuncs.pfnAddCommand( "fp_gun_relax", FP_GunRelaxCmd );
	gEngfuncs.pfnAddCommand( "fp_gun_set", FP_GunSetCmd );
	gEngfuncs.pfnAddCommand( "fp_gun_relax_set", FP_GunRelaxSetCmd );
	gEngfuncs.pfnAddCommand( "fp_hold", FP_HoldCmd );
	gEngfuncs.pfnAddCommand( "fp_hold_set", FP_HoldSetCmd );
	gEngfuncs.pfnAddCommand( "fp_relax_hand", FP_RelaxHandCmd );
	gEngfuncs.pfnAddCommand( "fp_relax_lhand", FP_RelaxLHandCmd );
	gEngfuncs.pfnAddCommand( "fp_relax_hand_set", FP_RelaxHandSetCmd );
	gEngfuncs.pfnAddCommand( "fp_relax_lhand_set", FP_RelaxLHandSetCmd );
	gEngfuncs.pfnAddCommand( "fp_fingers", FP_FingersCmd );
	gEngfuncs.pfnAddCommand( "fp_fingers_set", FP_FingersSetCmd );
	gEngfuncs.pfnAddCommand( "pm_holster", PM_HolsterCmd );

	gEngfuncs.pfnAddCommand( "fp_act", FP_ActCmd );
	gEngfuncs.pfnAddCommand( "fp_act_stop", StopOverlay );
	gEngfuncs.pfnAddCommand( "fp_actlist", FP_ActList );
}

static bool AnimsOn( void )
{
	return cl_fpbody_anims && cl_fpbody_anims->value != 0.0f;
}

// ---------------------------------------------------------------------------
// Weapon animation classification
// ---------------------------------------------------------------------------

static void Lower( const char *in, char *out, int size )
{
	int i;
	for ( i = 0; in[ i ] && i < size - 1; i++ )
	{
		char c = in[ i ];
		if ( c >= 'A' && c <= 'Z' ) c += 'a' - 'A';
		out[ i ] = c;
	}
	out[ i ] = 0;
}

static bool Has( const char *s, const char *sub ) { return strstr( s, sub ) != NULL; }
static bool Starts( const char *s, const char *pre ) { return !strncmp( s, pre, strlen( pre ) ); }

static float RecoilStrength( const char *model, const char *seq )
{
	if ( Has( model, "v_shotgun" ) )     return Has( seq, "big" ) ? 2.4f : 1.8f;
	if ( Has( model, "v_357" ) )         return 1.7f;
	if ( Has( model, "v_rpg" ) )         return 2.0f;
	if ( Has( model, "v_gauss" ) )       return 1.5f;
	if ( Has( model, "v_crossbow" ) )    return 1.2f;
	if ( Has( model, "v_9mmar" ) )       return Has( seq, "grenade" ) ? 1.8f : 0.6f;
	if ( Has( model, "v_9mmhandgun" ) )  return 0.8f;
	if ( Has( model, "v_hgun" ) )        return 0.5f;
	return 1.0f;
}

static int Classify( const char *model, const char *seq, int *variant, float *strength )
{
	*variant = 0;
	*strength = 1.0f;

	if ( Starts( seq, "idle" ) || Has( seq, "fidget" ) || Has( seq, "longidle" ) ||
		 Has( seq, "deepidle" ) || Has( seq, "sm_idle" ) || Has( seq, "altfireoff" ) )
		return CLIP_IDLE;

	if ( Has( seq, "draw" ) || Has( seq, "deploy" ) || !strcmp( seq, "up" ) )
		return CLIP_DRAW;

	if ( Has( seq, "holster" ) || !strcmp( seq, "down" ) )
		return CLIP_HOLSTER;

	if ( Has( seq, "start_reload" ) )
		return CLIP_SHELL_START;

	if ( Has( seq, "reload" ) )
		return Has( model, "v_shotgun" ) ? CLIP_SHELL : CLIP_RELOAD;

	if ( Has( seq, "pump" ) )
		return CLIP_PUMP;

	if ( Has( seq, "silencer" ) )
		return CLIP_FIDDLE;

	if ( Has( seq, "attack" ) )
	{
		if ( Has( seq, "2" ) ) *variant = 1;
		else if ( Has( seq, "3" ) ) *variant = 2;
		return CLIP_MELEE;
	}

	if ( Has( seq, "pinpull" ) )
		return CLIP_PINPULL;

	if ( Has( seq, "throw" ) )
		return CLIP_THROW;

	if ( Has( seq, "place" ) || Has( seq, "drop" ) )
		return CLIP_PLACE;

	if ( Has( model, "v_satchel_radio" ) && Has( seq, "fire" ) )
		return CLIP_PRESS;

	if ( Has( seq, "spin" ) )
		return CLIP_CHARGE;

	if ( Has( model, "v_egon" ) && ( Starts( seq, "fire" ) || Has( seq, "altfire" ) ) )
		return CLIP_BEAM;

	if ( Has( seq, "shoot" ) || Has( seq, "fire" ) || Has( seq, "grenade" ) )
	{
		*strength = RecoilStrength( model, seq );
		return CLIP_RECOIL;
	}

	return CLIP_NONE;
}

static void StartClip( int type, int variant, float strength, float seqDur )
{
	float now = gEngfuncs.GetClientTime();
	if ( type != CLIP_NONE )
		FPDbg( "gun clip %d variant %d\n", type, variant );
	clip_t c;
	c.type = type;
	c.variant = variant;
	c.strength = strength;
	c.start = now;

	switch ( type )
	{
	case CLIP_DRAW:        c.dur = Clamp( seqDur * 0.9f, 0.35f, 1.0f ); break;
	case CLIP_HOLSTER:     c.dur = Clamp( seqDur, 0.3f, 1.0f ) + 0.4f; break;
	case CLIP_RECOIL:      c.dur = 0.5f; break;
	case CLIP_RELOAD:      c.dur = Clamp( seqDur, 0.8f, 5.0f ); break;
	case CLIP_SHELL_START: c.dur = Clamp( seqDur, 0.4f, 1.5f ) + 0.6f; break;
	case CLIP_SHELL:       c.dur = Clamp( seqDur, 0.3f, 1.5f ) + 0.5f; break;
	case CLIP_PUMP:        c.dur = Clamp( seqDur, 0.3f, 1.2f ); break;
	case CLIP_FIDDLE:      c.dur = Clamp( seqDur, 0.8f, 4.0f ); break;
	case CLIP_MELEE:       c.dur = Clamp( seqDur, 0.3f, 1.0f ); break;
	case CLIP_THROW:       c.dur = Clamp( seqDur, 0.4f, 1.5f ); break;
	case CLIP_PINPULL:     c.dur = Clamp( seqDur, 0.3f, 1.0f ); break;
	case CLIP_PLACE:       c.dur = Clamp( seqDur, 0.3f, 1.0f ) + 0.2f; break;
	case CLIP_PRESS:       c.dur = 0.5f; break;
	case CLIP_CHARGE:
	case CLIP_BEAM:        c.dur = 30.0f; break;
	default:               c.dur = 0.5f; break;
	}

	// A shell inserted while the gun is already tilted keeps it tilted
	if ( ( type == CLIP_SHELL || type == CLIP_SHELL_START ) &&
		 ( g_cur.type == CLIP_SHELL || g_cur.type == CLIP_SHELL_START ) &&
		 now < g_cur.start + g_cur.dur )
	{
		c.variant = 1;
	}

	g_prev = g_cur;
	g_prevFadeStart = now;
	g_cur = c;
}

static void HandleWeaponAnim( model_t *model, int iAnim )
{
	if ( !model || model->type != mod_studio )
		return;

	studiohdr_t *hdr = (studiohdr_t *)IEngineStudio.Mod_Extradata( model );
	if ( !hdr || iAnim < 0 || iAnim >= hdr->numseq )
		return;

	mstudioseqdesc_t *seq = (mstudioseqdesc_t *)( (byte *)hdr + hdr->seqindex ) + iAnim;

	char seqName[ 32 ], modelName[ 64 ];
	Lower( seq->label, seqName, sizeof( seqName ) );
	Lower( model->name, modelName, sizeof( modelName ) );

	float seqDur = ( seq->fps > 0.0f && seq->numframes > 1 ) ? ( seq->numframes - 1 ) / seq->fps : 0.5f;

	int variant;
	float strength;
	int type = Classify( modelName, seqName, &variant, &strength );

	// 9mmAR grenade launcher: the kick, then a reload of the launcher after every
	// shot (the view model has no reload for it)
	if ( Has( modelName, "v_9mmar" ) && ( Has( seqName, "launch" ) || Has( seqName, "grenade" ) ) )
	{
		g_lastShot = gEngfuncs.GetClientTime();
		g_mvActivity = g_now;
		StartClip( CLIP_RECOIL, 0, 1.6f, seqDur );
		if ( cl_fpbody_glreload->value != 0.0f )
			g_glReloadAt = g_lastShot + 0.35f;
		return;
	}

	if ( type == CLIP_NONE )
		return;

	if ( type == CLIP_DRAW || type == CLIP_HOLSTER )
		g_glReloadAt = 0.0f;							// switched away: no launcher reload

	if ( type == CLIP_IDLE )
	{
		// idles only stop looping effects; everything else plays out
		if ( g_cur.type == CLIP_CHARGE || g_cur.type == CLIP_BEAM )
			StartClip( CLIP_NONE, 0, 0.0f, 0.0f );
		return;
	}

	// The egon re-sends its looping fire animation constantly; don't restart
	if ( type == CLIP_BEAM && g_cur.type == CLIP_BEAM )
		return;

	// switching weapons cancels a GMod reload in progress
	if ( ( type == CLIP_DRAW || type == CLIP_HOLSTER ) && g_ovSeq >= 0 && ( g_ovKind == OVK_RELOAD || g_ovKind == OVK_EASE ) )
		StopOverlay();

	// the gun is in use: no lowered gun for a while
	if ( type != CLIP_IDLE )
		g_mvActivity = g_now;

	// shooting ends a pickup reach, a blast reaction or gagging: the gun comes back up
	if ( type != CLIP_DRAW && type != CLIP_HOLSTER && g_ovSeq >= 0 && g_ovKind == OVK_EASE &&
		 ( OverlayIs( "fm_pickup" ) || OverlayIs( "fm_blast" ) || OverlayIs( "fm_strangle" ) ) )
	{
		FPDbg( "shot ends %s\n", OverlayName() );
		StopOverlay();
		g_pickupUntil = 0.0f;
	}

	// Freeman: draw animations (upper body) when a gun comes out
	if ( type == CLIP_DRAW && g_playerHdr && cl_fpbody_moves->value != 0.0f && !MoveBusy() &&
		 ( g_ovSeq < 0 || g_ovKind == OVK_EASE ) && !( g_now < g_pickupUntil && g_now >= g_pickupUntil - 1.0f ) )
	{
		const char *draw = NULL;
		if ( Has( modelName, "v_9mmhandgun" ) || Has( modelName, "v_357" ) || Has( modelName, "v_desert_eagle" ) ||
			 Has( modelName, "v_hgun" ) )
			draw = "fm_draw_pistol";
		else if ( Has( modelName, "v_rpg" ) || Has( modelName, "v_gauss" ) || Has( modelName, "v_egon" ) )
			draw = "fm_draw_rpg";
		else if ( Has( modelName, "v_crowbar" ) || Has( modelName, "v_knife" ) || Has( modelName, "v_pipe_wrench" ) ||
				  Has( modelName, "v_bgrap" ) )
			draw = "fm_draw_melee";
		else if ( Has( modelName, "v_9mmar" ) || Has( modelName, "v_shotgun" ) || Has( modelName, "v_crossbow" ) ||
				  Has( modelName, "v_m40a1" ) || Has( modelName, "v_saw" ) || Has( modelName, "v_shock" ) ||
				  Has( modelName, "v_spore_launcher" ) || Has( modelName, "v_displacer" ) )
			draw = "fm_draw_rifle";
		if ( draw && StartOverlayKind( draw, OVK_EASE, Clamp( seqDur, 0.5f, 1.0f ) ) )
		{
			StartClip( CLIP_NONE, 0, 0.0f, 0.0f );
			return;
		}
	}

	// Left 4 Dead's reloads where a gun has one: pistols, rifles, and the pump
	// shotgun's start / shell / end (the shotgun pump after the shells)
	if ( ( type == CLIP_RELOAD || type == CLIP_SHELL_START || type == CLIP_SHELL || type == CLIP_PUMP ) && g_bGmodModel &&
		 cl_fpbody_gmod->value != 0.0f && cl_fpbody_l4dreload->value != 0.0f && !MoveBusy() )
	{
		// cl_fpbody_reloadset: "css" Counter-Strike: Source's reloads (css_reload_*),
		// "l4d" Left 4 Dead's (l4d_reload_*); a model without the set falls back to the other
		const char *l4 = NULL, *css = NULL;
		if ( Has( modelName, "v_shotgun" ) )
		{
			if ( type == CLIP_SHELL_START )
				l4 = "l4d_reload_shotgun_start", css = "css_reload_shotgun_start";
			else if ( type == CLIP_SHELL )
				l4 = "l4d_reload_shotgun_loop", css = "css_reload_shotgun_loop";
			// the pump after the last shell: Garry's Mod's own pump instead (the left
			// hand racks the pump back along the barrel and forward: ApplyGunPose)
		}
		else if ( type == CLIP_RELOAD )
		{
			// (the .357 has none: it gets Garry's Mod's revolver reload below, the cylinder
			// swung out and reloaded, instead of a magazine)
			if ( Has( modelName, "v_9mmhandgun" ) || Has( modelName, "v_desert_eagle" ) )
				l4 = "l4d_reload_pistol", css = "css_reload_pistol";
			else if ( Has( modelName, "v_9mmar" ) )
				l4 = "l4d_reload_rifle", css = "css_reload_smg";
			else if ( Has( modelName, "v_saw" ) )
				l4 = "l4d_reload_rifle", css = "css_reload_m249";
			else if ( Has( modelName, "v_m40a1" ) || Has( modelName, "v_crossbow" ) )
				l4 = Has( modelName, "v_m40a1" ) ? "l4d_reload_rifle" : NULL, css = "css_reload_sniper";
		}
		bool useCss = cl_fpbody_reloadset && !stricmp( cl_fpbody_reloadset->string, "css" );
		const char *first = useCss ? css : l4, *second = useCss ? l4 : css;
		if ( first && FindSeq( g_playerHdr, first ) < 0 )
			first = NULL;
		if ( !first )
			first = second;
		l4 = first;
		if ( l4 && StartOverlay( l4, false, seqDur ) )
		{
			g_ovLoop = false;							// one shell per insert
			if ( type == CLIP_SHELL_START || type == CLIP_SHELL )
				g_l4dShellAt = g_now;
			else
				g_l4dShellAt = -10.0f;
			StartClip( CLIP_NONE, 0, 0.0f, 0.0f );
			return;
		}
	}

	// Use GMod's reload animation for this weapon when the model has one
	if ( type == CLIP_RELOAD && g_bGmodModel && cl_fpbody_gmod->value != 0.0f && !MoveBusy() )
	{
		const char *gm = NULL;
		if ( Has( modelName, "v_9mmhandgun" ) )     gm = "gm_reload_pistol";
		else if ( Has( modelName, "v_357" ) )       gm = "gm_reload_revolver";
		else if ( Has( modelName, "v_9mmar" ) )     gm = "gm_reload_smg1";
		else if ( Has( modelName, "v_crossbow" ) )  gm = "gm_reload_ar2";
		else if ( Has( modelName, "v_rpg" ) )       gm = "gm_reload_smg1_alt";

		if ( gm && StartOverlay( gm, false, seqDur ) )
		{
			StartClip( CLIP_NONE, 0, 0.0f, 0.0f );
			return;
		}
	}

	// Third-person reloads: the classic player models carry Condition Zero's
	// (<stance>_reload_<set>), Counter-Strike 1.6's (cs_<stance>_reload_<set>)
	// and Sven Co-op's (sv_<stance>_reload_<set>). cl_fpbody_reloads picks which
	// is tried first; the others are the backup for weapons the first has no
	// reload for. Played on the upper body.
	if ( ( type == CLIP_RELOAD || type == CLIP_SHELL_START || type == CLIP_SHELL ) && g_playerHdr && FPBody_Classic() &&
		 !MoveBusy() )
	{
		const char *pref = cl_fpbody_reloads->string;
		bool off = !pref[ 0 ] || !strcmp( pref, "0" );
		// 0 = Condition Zero, 1 = Counter-Strike 1.6, 2 = Sven Co-op
		int order[ 3 ] = { 0, 1, 2 };
		if ( !strnicmp( pref, "sv", 2 ) )
			order[ 0 ] = 2, order[ 1 ] = 0, order[ 2 ] = 1;
		else if ( !strnicmp( pref, "cs", 2 ) )
			order[ 0 ] = 1, order[ 1 ] = 0, order[ 2 ] = 2;

		// cs: 1 = Counter-Strike 1.6's reload first whatever cl_fpbody_reloads says
		struct reloadset_t { const char *view, *cz, *sv; int cs; };
		static const reloadset_t sets[] =
		{
			{ "v_9mmar", "rifle", "mp5", 1 },     { "v_shotgun", "shotgun", "shotgun", 0 },
			{ "v_9mmhandgun", "onehanded", "onehanded", 0 }, { "v_357", "onehanded", "python", 0 },
			{ "v_desert_eagle", "onehanded", "onehanded", 0 }, { "v_crossbow", "rifle", "bow", 0 },
			{ "v_m40a1", "rifle", "sniper", 0 },  { "v_saw", "m249", "saw", 0 },
			{ "v_rpg", NULL, "rpg", 0 },
		};
		const reloadset_t *rs = NULL;
		for ( int i = 0; !off && i < (int)( sizeof( sets ) / sizeof( sets[ 0 ] ) ); i++ )
			if ( Has( modelName, sets[ i ].view ) )
			{
				rs = &sets[ i ];
				break;
			}
		// the 9mmAR is an M16: Counter-Strike 1.6's M4A1 reload
		if ( rs && rs->cs )
			order[ 0 ] = 1, order[ 1 ] = 0, order[ 2 ] = 2;

		if ( rs )
		{
			bool crouch = false;
			cl_entity_t *local = gEngfuncs.GetLocalPlayer();
			int curSeq = LocalSeq( local );
			if ( curSeq >= 0 && curSeq < g_playerHdr->numseq )
			{
				const mstudioseqdesc_t *cur = (const mstudioseqdesc_t *)( (const byte *)g_playerHdr + g_playerHdr->seqindex ) +
											  curSeq;
				const char *lab = cur->label;
				if ( !strnicmp( lab, "cs_", 3 ) || !strnicmp( lab, "sv_", 3 ) )
					lab += 3;
				crouch = !strnicmp( lab, "crouch", 6 );
			}
			const char *st = crouch ? "crouch" : "ref";
			bool shotgun = !strcmp( rs->view, "v_shotgun" );

			for ( int pass = 0; pass < 3; pass++ )
			{
				bool sven = order[ pass ] == 2;
				const char *prefix = order[ pass ] == 2 ? "sv_" : order[ pass ] == 1 ? "cs_" : "";
				const char *set = sven ? rs->sv : rs->cz;
				if ( !set )
					continue;
				// shotgun: Condition Zero's / Counter-Strike's play once when the reload starts, Sven
				// Co-op's once per shell; every other gun on its reload
				if ( shotgun ? ( sven ? type != CLIP_SHELL : type != CLIP_SHELL_START ) : type != CLIP_RELOAD )
					continue;
				char name[ 48 ];
				snprintf( name, sizeof( name ), "%s%s_reload_%s", prefix, st, set );
				int seq = FindSeq( g_playerHdr, name );
				if ( seq < 0 )
					continue;
				float now = gEngfuncs.GetClientTime();
				// a reload in two viewmodel parts (M249 start / end) keeps the one already playing
				if ( seq == g_ovSeq && now - g_ovStart < g_ovDur )
				{
					StartClip( CLIP_NONE, 0, 0.0f, 0.0f );
					return;
				}
				if ( StartOverlay( name, false, type == CLIP_RELOAD ? seqDur : 0.0f ) )
				{
					StartClip( CLIP_NONE, 0, 0.0f, 0.0f );
					return;
				}
			}
		}
	}

	if ( type == CLIP_RECOIL || type == CLIP_CHARGE || type == CLIP_BEAM )
		g_lastShot = gEngfuncs.GetClientTime();

	StartClip( type, variant, strength, seqDur );
}

static float g_hookTime = -10.0f;	// last weapon anim from the prediction hook
static int g_hookSeq = -1;

void FPAnim_OnWeaponAnim( int iAnim, int viewmodelIndex )
{
	g_bHookSeen = true;
	g_hookTime = gEngfuncs.GetClientTime();
	g_hookSeq = iAnim;

	if ( !AnimsOn() )
		return;

	// The predicted player's viewmodel field isn't always a model index (a
	// weapon's client-side Deploy stores the model's name string there), so the
	// index can point at any loaded model. Use it only if it really is a view
	// model with that animation, otherwise the view model being drawn.
	model_t *model = NULL;
	if ( viewmodelIndex > 0 )
	{
		model_t *m = IEngineStudio.GetModelByIndex( viewmodelIndex );
		if ( m && m->type == mod_studio && strstr( m->name, "/v_" ) )
		{
			studiohdr_t *h = (studiohdr_t *)IEngineStudio.Mod_Extradata( m );
			if ( h && iAnim >= 0 && iAnim < h->numseq )
				model = m;
		}
	}

	if ( !model )
	{
		cl_entity_t *view = gEngfuncs.GetViewModel();
		if ( view )
			model = view->model;
	}
	FPDbg( "weapon anim %d on %s\n", iAnim, model ? model->name : "(no model)" );

	HandleWeaponAnim( model, iAnim );
}

// Fallback when client weapon prediction is off (cl_lw 0): watch the view
// model entity for animation changes sent by the server.
// The view model's animation, watched every frame. Weapon anims usually come
// through the prediction hook above; the ones that don't (weapons the client
// doesn't predict, Blue Shift / Opposing Force builds, cl_lw 0) still change
// the view model, so they're caught here. One the hook just reported is skipped.
static void PollViewModel( void )
{
	cl_entity_t *view = gEngfuncs.GetViewModel();
	if ( !view || !view->model )
		return;

	float now = gEngfuncs.GetClientTime();
	if ( view->curstate.animtime < g_lastPollAnimTime - 0.5f )
		g_lastPollSeq = -1;								// new map / saved game: start again
	if ( view->curstate.sequence != g_lastPollSeq || view->curstate.animtime != g_lastPollAnimTime )
	{
		bool first = ( g_lastPollSeq < 0 );
		g_lastPollSeq = view->curstate.sequence;
		g_lastPollAnimTime = view->curstate.animtime;
		bool hooked = g_bHookSeen && g_hookSeq == view->curstate.sequence && now - g_hookTime >= 0.0f && now - g_hookTime < 0.25f;
		if ( !first && !hooked && AnimsOn() )
		{
			FPDbg( "view model anim %d (not from the hook)\n", view->curstate.sequence );
			HandleWeaponAnim( view->model, view->curstate.sequence );
		}
	}
}

// ---------------------------------------------------------------------------
// Clip evaluation
// ---------------------------------------------------------------------------

static void AddLeftAim( pose_t &p, const float *dir, float w )
{
	if ( w <= 0.0f )
		return;
	for ( int i = 0; i < 3; i++ )
		p.lAimDir[ i ] += dir[ i ] * w;
	p.lAimW += w;
}

static void MakeDir( const float *f, const float *r, const float *u, float df, float dr, float du, float *out )
{
	for ( int i = 0; i < 3; i++ )
		out[ i ] = f[ i ] * df + r[ i ] * dr + u[ i ] * du;
	Normalize3( out );
}

static void EvalClip( const clip_t &c, float now, float weight, pose_t &p,
	const float *f, const float *r, const float *u )
{
	if ( c.type == CLIP_NONE || weight <= 0.0f )
		return;

	float tau = now - c.start;
	if ( tau < 0.0f || tau > c.dur )
		return;

	float t = tau / c.dur;
	float s = c.strength * weight;
	float dir[ 3 ];

	// With GMod animations in the model, ref_shoot_* already carries the
	// swing / throw / placing motion and most of the recoil
	if ( g_bGmodModel && cl_fpbody_gmod->value != 0.0f )
	{
		if ( c.type == CLIP_MELEE || c.type == CLIP_THROW || c.type == CLIP_PLACE )
			return;
		if ( c.type == CLIP_RECOIL )
			s *= 0.35f;
	}

	switch ( c.type )
	{
	case CLIP_DRAW:
	{
		float e = 1.0f - Smooth( t );
		p.armsPitch += 60.0f * e * weight;
		p.armsRoll  += 15.0f * e * weight;
		p.armsYaw   += 10.0f * e * weight;
		break;
	}
	case CLIP_HOLSTER:
	{
		float e = Env( t, 0.55f, 0.25f );
		p.armsPitch += 60.0f * e * weight;
		p.armsRoll  += 15.0f * e * weight;
		break;
	}
	case CLIP_RECOIL:
	{
		float k = tau < 0.04f ? tau / 0.04f : (float)exp( -( tau - 0.04f ) * 11.0f );
		p.armsPitch -= 7.0f * s * k;
		p.armsBack  += 2.5f * s * k;
		p.armsYaw   += ( ( (int)( c.start * 100.0f ) & 1 ) ? 1.0f : -1.0f ) * 1.2f * s * k;
		break;
	}
	case CLIP_RELOAD:
	{
		if ( c.variant == 1 )
		{
			// grenade launcher: the gun tips up a little, the off hand takes a
			// grenade from the belt, pushes it into the tube under the barrel and
			// snaps the breech shut
			float e = Env( t, 0.12f, 0.2f );
			p.armsPitch -= 22.0f * e * weight;						// muzzle up, launcher toward you
			p.armsRoll  += 10.0f * e * weight;
			p.armsYaw   += 8.0f * e * weight;
			MakeDir( f, r, u, 0.3f, 0.2f, -1.0f, dir );				// to the belt for a grenade
			AddLeftAim( p, dir, 0.85f * Bump( t, 0.06f, 0.42f ) * weight );
			// then the hand goes to the launcher's opening (ApplyGunPose) and pushes it in
			float open = Bump( t, 0.36f, 0.92f ) * weight;
			if ( open > g_glOpenW )
				g_glOpenW = open;
			p.armsPitch += 5.0f * Bump( t, 0.74f, 0.88f ) * weight;	// breech snaps shut
			break;
		}
		float e = Env( t, 0.15f, 0.2f );
		p.armsPitch += 20.0f * e * weight;
		p.armsRoll  += 22.0f * e * weight;
		p.armsYaw   += 10.0f * e * weight;
		// slap the new magazine home
		p.armsPitch -= 5.0f * Bump( t, 0.62f, 0.78f ) * weight;
		// off hand drops to the belt for a new magazine, then comes back
		MakeDir( f, r, u, 0.3f, 0.15f, -1.0f, dir );
		AddLeftAim( p, dir, 0.85f * Bump( t, 0.16f, 0.7f ) * weight );
		break;
	}
	case CLIP_SHELL_START:
	case CLIP_SHELL:
	{
		float in = c.variant ? 0.0f : 0.3f;
		float e = Env( t, in, 0.3f );
		p.armsPitch += 14.0f * e * weight;
		p.armsRoll  += 20.0f * e * weight;
		p.armsYaw   += 6.0f * e * weight;
		if ( c.type == CLIP_SHELL )
		{
			// off hand takes a shell from the belt and pushes it in
			float shellT = tau / ( c.dur - 0.5f );
			MakeDir( f, r, u, 0.45f, 0.25f, -0.8f, dir );
			AddLeftAim( p, dir, 0.7f * Bump( shellT, 0.0f, 1.0f ) * weight );
		}
		break;
	}
	case CLIP_PUMP:
		if ( FPBody_Classic() )		// GMod mode racks the pump with the hand on it (ApplyGunPose)
		{
			p.lBack     += 4.5f * Bump( t, 0.05f, 0.7f ) * weight;
			p.armsPitch -= 3.0f * Bump( t, 0.0f, 0.5f ) * weight;
		}
		break;
	case CLIP_FIDDLE:
	{
		float e = Env( t, 0.15f, 0.2f );
		p.armsPitch += 15.0f * e * weight;
		p.armsYaw   += 10.0f * e * weight;
		MakeDir( f, r, u, 1.0f, 0.35f, -0.1f, dir );
		AddLeftAim( p, dir, 0.6f * e * weight );
		break;
	}
	case CLIP_MELEE:
	{
		static const float pitch0[] = { 0, 0,  0.3f, -40,  0.55f, 30,  1, 0 };
		static const float yaw0[]   = { 0, 0,  0.3f, -30,  0.55f, 35,  1, 0 };
		static const float pitch1[] = { 0, 0,  0.3f, -55,  0.55f, 38,  1, 0 };
		static const float yaw1[]   = { 0, 0,  0.3f, 10,   0.55f, -10, 1, 0 };
		static const float pitch2[] = { 0, 0,  0.3f, -20,  0.55f, 15,  1, 0 };
		static const float yaw2[]   = { 0, 0,  0.3f, -45,  0.55f, 42,  1, 0 };
		const float *kp = c.variant == 1 ? pitch1 : ( c.variant == 2 ? pitch2 : pitch0 );
		const float *ky = c.variant == 1 ? yaw1 : ( c.variant == 2 ? yaw2 : yaw0 );
		p.rPitch += Keys( kp, 4, t ) * weight;
		p.rYaw   += Keys( ky, 4, t ) * weight;
		break;
	}
	case CLIP_THROW:
	{
		static const float kp[] = { 0, 0,  0.3f, -55,  0.5f, 25,  1, 0 };
		static const float ky[] = { 0, 0,  0.3f, -15,  0.5f, 10,  1, 0 };
		p.rPitch += Keys( kp, 4, t ) * weight;
		p.rYaw   += Keys( ky, 4, t ) * weight;
		break;
	}
	case CLIP_PINPULL:
		MakeDir( f, r, u, 1.0f, 0.5f, -0.2f, dir );
		AddLeftAim( p, dir, 0.8f * Bump( t, 0.0f, 1.0f ) * weight );
		break;
	case CLIP_PLACE:
	{
		float b = Bump( t, 0.0f, 1.0f );
		p.armsPitch += 40.0f * b * weight;
		p.armsBack  -= 3.0f * b * weight;
		break;
	}
	case CLIP_PRESS:
		p.armsPitch -= 6.0f * Bump( t, 0.0f, 0.5f ) * weight;
		break;
	case CLIP_CHARGE:
	{
		float amp = Smooth( tau / 1.0f ) * weight;
		p.armsYaw   += amp * 1.2f * (float)sin( tau * 55.0f );
		p.armsPitch += amp * 1.2f * (float)sin( tau * 41.0f + 1.0f );
		p.armsBack  += amp * 0.8f;
		break;
	}
	case CLIP_BEAM:
	{
		float amp = Smooth( tau / 0.3f ) * weight;
		p.armsYaw   += amp * 0.8f * (float)sin( tau * 60.0f );
		p.armsPitch += amp * 0.8f * (float)sin( tau * 47.0f );
		p.armsBack  += amp * 1.0f;
		break;
	}
	}
}

// ---------------------------------------------------------------------------
// Per-frame action-button state
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// The Freeman mod's moves (pm_shared/fpbody_pm.h does the movement, the
// server the kick and holster-all): animations for them, the at-ease lowered
// gun, and the commands / double-taps that start them. The fm_ sequences are
// added to the player models by tools/gmod_anims/add_freeman.py.
// ---------------------------------------------------------------------------

static int g_mvPrevState;
static int g_mvPrevOnGround = 1;
static float g_mvFallStart = -1.0f;
static float g_mvMaxFall;
static float g_mvLastDuck = -10.0f, g_mvLastReload = -10.0f;
static bool g_mvEaseForced;
static int g_mvLastHealth = -1;
static bool g_mvDucked;
static bool g_mvOnGround = true;

static const char *HoldType( void )
{
	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	model_t *m = ( local && local->curstate.weaponmodel > 0 ) ? IEngineStudio.GetModelByIndex( local->curstate.weaponmodel ) : NULL;
	if ( !m )
		return "passive";
	char n[ 64 ];
	Lower( m->name, n, sizeof( n ) );
	if ( Has( n, "p_9mmhandgun" ) || Has( n, "p_glock" ) || Has( n, "p_desert_eagle" ) || Has( n, "p_hgun" ) ) return "pistol";
	if ( Has( n, "p_357" ) ) return "revolver";
	if ( Has( n, "p_9mmar" ) || Has( n, "p_mp5" ) ) return "smg1";
	if ( Has( n, "p_shotgun" ) ) return "shotgun";
	if ( Has( n, "p_crossbow" ) || Has( n, "p_m40a1" ) ) return "crossbow";
	if ( Has( n, "p_rpg" ) ) return "rpg";
	if ( Has( n, "p_gauss" ) || Has( n, "p_egon" ) || Has( n, "p_displacer" ) || Has( n, "p_spore" ) ) return "physgun";
	if ( Has( n, "p_saw" ) || Has( n, "p_shock" ) ) return "ar2";
	if ( Has( n, "p_crowbar" ) || Has( n, "p_knife" ) || Has( n, "p_pipe_wrench" ) || Has( n, "p_bgrap" ) ) return "melee";
	if ( Has( n, "p_grenade" ) || Has( n, "p_squeak" ) || Has( n, "p_penguin" ) ) return "grenade";
	if ( Has( n, "p_satchel" ) || Has( n, "p_tripmine" ) ) return "slam";
	return "passive";
}

static const char *ProneWalk( const char *hold )
{
	if ( !strcmp( hold, "passive" ) ) return "passive";
	if ( !strcmp( hold, "smg1" ) || !strcmp( hold, "ar2" ) || !strcmp( hold, "shotgun" ) ) return "twohand";
	if ( !strcmp( hold, "rpg" ) || !strcmp( hold, "crossbow" ) || !strcmp( hold, "physgun" ) ) return hold;
	return "onehand";
}

static const char *OverlayName( void )
{
	if ( g_ovSeq < 0 || !g_playerHdr || g_ovSeq >= g_playerHdr->numseq )
		return "(none)";
	const mstudioseqdesc_t *sd = (const mstudioseqdesc_t *)( (const byte *)g_playerHdr + g_playerHdr->seqindex ) + g_ovSeq;
	return sd->label;
}

static bool OverlayIs( const char *name )
{
	if ( g_ovSeq < 0 || !g_playerHdr || g_ovSeq >= g_playerHdr->numseq )
		return false;
	const mstudioseqdesc_t *sd = (const mstudioseqdesc_t *)( (const byte *)g_playerHdr + g_playerHdr->seqindex ) + g_ovSeq;
	return !stricmp( sd->label, name );
}

// keep a looping move animation going (prone, falling, climbing); rate 0 = leave it
static void WantLoop( const char *name, float rate )
{
	if ( OverlayIs( name ) )
	{
		if ( rate > 0.0f && fabs( rate - g_ovRate ) > 0.01f )
		{
			float phase = ( g_now - g_ovStart ) * g_ovRate;		// keep the cycle where it is
			g_ovRate = rate;
			g_ovStart = g_now - phase / rate;
		}
		g_ovKind = OVK_LOOP;
		return;
	}
	if ( StartOverlayKind( name, OVK_LOOP, 0.0f ) && rate > 0.0f )
		g_ovRate = rate;
}

static void PM_KickCmd( void )
{
	gEngfuncs.pfnClientCmd( "impulse 211\n" );
	if ( !FPBody_Active() || !g_playerHdr || cl_fpbody_moves->value == 0.0f || ( g_fpmState & ( FPM_VAULT | FPM_PRONE ) ) )
		return;
	if ( MoveBusy() && g_ovKind == OVK_MOVE && g_now - g_ovStart < g_ovDur * 0.85f )
		return;									// still in the last kick / landing
	Vector ang;
	gEngfuncs.GetViewAngles( (float *)ang );
	float pitch = ang[ PITCH ];					// + = looking down
	const char *name;
	if ( !g_mvOnGround )
		name = pitch > 50.0f ? "fm_stomp_air" : pitch > 30.0f ? "fm_kick_air_25" : pitch > 12.0f ? "fm_kick_air_45" : "fm_kick_air";
	else if ( g_mvDucked )
		name = pitch > 45.0f ? "fm_stomp_crouch" : "fm_kick_crouch";
	else
		name = pitch > 50.0f ? "fm_stomp" : pitch > 30.0f ? "fm_kick_25" : pitch > 12.0f ? "fm_kick_45" : "fm_kick";
	StartOverlayKind( name, OVK_MOVE, !strncmp( name, "fm_stomp", 8 ) ? 0.8f : 1.0f );
	g_mvActivity = g_now;
}

static void PM_ProneCmd( void ) { gEngfuncs.pfnClientCmd( "impulse 210\n" ); }

// fp_invnext / fp_invprev: next / previous weapon, taken out straight away (no
// confirm press) - for a controller's D-pad (Steam Input sends the mouse wheel).
// Presses in quick succession keep going from the one just picked, since the
// server hasn't switched yet.
extern WEAPON *gpActiveSel;
extern WEAPON *gpLastSel;
extern int g_weaponselect;
static WEAPON *g_quickSel;
static float g_quickTime = -100.0f;

static void QuickSwitch( bool next )
{
	float now = gEngfuncs.GetClientTime();
	if ( g_quickSel && now - g_quickTime < 0.6f && ( !gpActiveSel || gpActiveSel == (WEAPON *)1 ) )
		gpActiveSel = g_quickSel;
	if ( next )
		gHUD.m_Ammo.UserCmd_NextWeapon();
	else
		gHUD.m_Ammo.UserCmd_PrevWeapon();
	if ( !gpActiveSel || gpActiveSel == (WEAPON *)1 )
		return;
	ServerCmd( gpActiveSel->szName );
	g_weaponselect = gpActiveSel->iId;
	g_quickSel = gpActiveSel;
	g_quickTime = now;
	gpLastSel = gpActiveSel;
	gpActiveSel = NULL;
	PlaySound( "common/wpn_select.wav", 1 );
}
static void FP_InvNextCmd( void ) { QuickSwitch( true ); }
static void FP_InvPrevCmd( void ) { QuickSwitch( false ); }
static void PM_HolsterCmd( void ) { gEngfuncs.pfnClientCmd( "impulse 212\n" ); }

static void PM_AtEaseCmd( void )
{
	if ( g_ovSeq >= 0 && g_ovKind == OVK_EASE )
	{
		g_mvEaseForced = false;
		g_mvActivity = g_now;					// raise it
		StopOverlay();
	}
	else
		g_mvEaseForced = true;
}


// ---------------------------------------------------------------------------
// ExtendedER Player Animations (Concon's Garry's Mod addon, as ported to
// Half-Life 2 by the Freeman mod): fidgets after standing around, a bend-down
// when you pick things up, cowering / panicked running when empty-handed in a
// fight, flinches by damage type, a reach at the top of a ladder, and the gun
// coming up when a hostile is in view. The server finds the fights and the
// hostiles (FPM_PANIC / FPM_HOSTILE in the move state). Fidgets and flinches
// are additive layers (fa_ sequences), added on top of whatever the body does.
// ---------------------------------------------------------------------------

static int g_adSeq = -1;
static float g_adStart, g_adDur, g_adRate = 1.0f;
static float g_epaIdleSince, g_epaNextFidget = -1.0f;
static int g_epaSpasms;
static float g_epaNextSpasm, g_epaNextFlinch, g_epaNextStrangle;
static int g_epaLastAmmo = -1, g_epaLastWeapons = -1, g_epaLastArmor = -1, g_epaLastHealth = -1;
static float g_epaNextPickup;
static int g_epaPrevLadder;
static float g_epaLadderVz;
static int g_epaCower;				// 0 not cowering, 1 intro playing, 2 cowering
static int g_epaDmgPending, g_epaDmgBits;
static float g_epaDmgAt;
static int g_ctxLastWater = -1, g_ctxLastUse;
static float g_epaLastHurt = -100.0f;
static int g_epaLastWeaponModel;

static float RandF( float a, float b ) { return a + ( b - a ) * ( rand() / (float)RAND_MAX ); }

static float g_adHoldUntil, g_adHoldFrac = 0.45f;		// hold the gesture at its reach while a charger is used
static float g_useChargeUntil;							// the server says we are using a charger
void FPAnim_OnPickup( void ) { g_pickupPending = true; FPDbg( "pickup message\n" ); }

static bool StartAdditive( const char *name, float rate )
{
	g_adHoldUntil = 0.0f;
	if ( !g_playerHdr )
		return false;
	int seq = FindSeq( g_playerHdr, name );
	if ( seq < 0 )
		return false;
	const mstudioseqdesc_t *sd = (const mstudioseqdesc_t *)( (const byte *)g_playerHdr + g_playerHdr->seqindex ) + seq;
	g_adSeq = seq;
	g_adStart = g_now;
	g_adRate = rate;
	g_adDur = ( sd->fps > 0.0f && sd->numframes > 1 ) ? ( sd->numframes - 1 ) / sd->fps / rate : 0.1f;
	return true;
}

int FPAnim_GetAdditive( int entindex, void *studiohdr, int *seq, float *frame, float *weight )
{
	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	if ( g_adSeq < 0 || !local || entindex != local->index || studiohdr != (void *)g_playerHdr || !FPBody_Active() ||
		 g_adSeq >= g_playerHdr->numseq )
		return 0;
	float t = gEngfuncs.GetClientTime() - g_adStart;
	if ( g_adHoldUntil > 0.0f && gEngfuncs.GetClientTime() < g_adHoldUntil && t > g_adHoldFrac * g_adDur )
	{
		g_adStart = gEngfuncs.GetClientTime() - g_adHoldFrac * g_adDur;	// keep the arm out (charger)
		t = g_adHoldFrac * g_adDur;
	}
	if ( t < 0.0f || t > g_adDur )
	{
		g_adSeq = -1;
		return 0;
	}
	const mstudioseqdesc_t *sd = (const mstudioseqdesc_t *)( (const byte *)g_playerHdr + g_playerHdr->seqindex ) + g_adSeq;
	*seq = g_adSeq;
	*frame = Clamp( t * sd->fps * g_adRate, 0.0f, (float)( sd->numframes - 1 ) );
	*weight = Clamp01( t / 0.1f ) * Clamp01( ( g_adDur - t ) / 0.15f );
	return 1;
}

void FPAnim_AddLayer( float ( *q )[ 4 ], float ( *dq )[ 4 ], int numbones, float weight )
{
	for ( int i = 0; i < numbones; i++ )
	{
		// the delta, scaled by the weight (slerp from no rotation)
		float d[ 4 ] = { dq[ i ][ 0 ], dq[ i ][ 1 ], dq[ i ][ 2 ], dq[ i ][ 3 ] };
		if ( d[ 3 ] < 0.0f )
			d[ 0 ] = -d[ 0 ], d[ 1 ] = -d[ 1 ], d[ 2 ] = -d[ 2 ], d[ 3 ] = -d[ 3 ];
		if ( d[ 3 ] > 0.99999f )
			continue;
		if ( weight < 0.999f )
		{
			float ang = acosf( Clamp( d[ 3 ], -1.0f, 1.0f ) );
			float s = sinf( ang );
			float k = s > 1e-5f ? sinf( ang * weight ) / s : weight;
			d[ 0 ] *= k; d[ 1 ] *= k; d[ 2 ] *= k;
			d[ 3 ] = cosf( ang * weight );
		}
		// q = q * d (the delta in the bone's own space)
		float *a = q[ i ];
		float r[ 4 ];
		r[ 0 ] = a[ 3 ] * d[ 0 ] + a[ 0 ] * d[ 3 ] + a[ 1 ] * d[ 2 ] - a[ 2 ] * d[ 1 ];
		r[ 1 ] = a[ 3 ] * d[ 1 ] - a[ 0 ] * d[ 2 ] + a[ 1 ] * d[ 3 ] + a[ 2 ] * d[ 0 ];
		r[ 2 ] = a[ 3 ] * d[ 2 ] + a[ 0 ] * d[ 1 ] - a[ 1 ] * d[ 0 ] + a[ 2 ] * d[ 3 ];
		r[ 3 ] = a[ 3 ] * d[ 3 ] - a[ 0 ] * d[ 0 ] - a[ 1 ] * d[ 1 ] - a[ 2 ] * d[ 2 ];
		a[ 0 ] = r[ 0 ]; a[ 1 ] = r[ 1 ]; a[ 2 ] = r[ 2 ]; a[ 3 ] = r[ 3 ];
	}
}

void FPAnim_NeutralControllers( void *studiohdr, unsigned char *out4 )
{
	const studiohdr_t *hdr = (const studiohdr_t *)studiohdr;
	for ( int i = 0; i < 4; i++ )
		out4[ i ] = 127;
	const mstudiobonecontroller_t *bc = (const mstudiobonecontroller_t *)( (const byte *)hdr + hdr->bonecontrollerindex );
	for ( int i = 0; i < hdr->numbonecontrollers; i++ )
	{
		int idx = bc[ i ].index;
		if ( idx < 0 || idx > 3 || bc[ i ].end == bc[ i ].start )
			continue;
		float v = 255.0f * ( 0.0f - bc[ i ].start ) / ( bc[ i ].end - bc[ i ].start );
		out4[ idx ] = (unsigned char)Clamp( v + 0.5f, 0.0f, 255.0f );
	}
}

void FPAnim_OnDamage( int amount, int bits )
{
	if ( amount <= 0 )
		return;
	FPDbg( "damage %d bits %x\n", amount, bits );
	if ( g_epaDmgPending == 0 )
		g_epaDmgAt = g_now;
	g_epaDmgPending += amount;
	g_epaDmgBits |= bits;
}

static void EPA_Fidget( const char *hold, bool atEase )
{
	static const char *both[] = { "fa_head_fwd", "fa_head_fwd2", "fa_accent_fwd", "fa_head_back", "fa_head_shake",
		"fa_chin_out", "fa_nod" };
	static const char *standard[] = { "fa_point", "fa_wave", "fa_pump", "fa_arms_up", "fa_arc_chin", "fa_arc_straight" };
	static const char *unarmed[] = { "fa_stretch_chin", "fa_stretch" };
	const char *pool[ 24 ];
	int n = 0;
	bool handgun = !strcmp( hold, "pistol" ) || !strcmp( hold, "revolver" );
	bool longGun = !strcmp( hold, "smg1" ) || !strcmp( hold, "ar2" ) || !strcmp( hold, "shotgun" ) ||
				   !strcmp( hold, "rpg" ) || !strcmp( hold, "crossbow" );
	for ( int i = 0; i < 7; i++ ) pool[ n++ ] = both[ i ];
	if ( !strcmp( hold, "passive" ) || ( atEase && handgun ) )
	{
		for ( int i = 0; i < 2; i++ ) pool[ n++ ] = unarmed[ i ];
	}
	else
	{
		bool restricted = !strcmp( hold, "grenade" ) || !strcmp( hold, "slam" ) || !strcmp( hold, "melee" ) || ( atEase && longGun );
		for ( int i = 0; i < 6; i++ )
			if ( !restricted || i >= 4 )			// the first four wave the arms
				pool[ n++ ] = standard[ i ];
	}
	// only the ones the model has
	int have = 0;
	for ( int i = 0; i < n; i++ )
		if ( FindSeq( g_playerHdr, pool[ i ] ) >= 0 )
			pool[ have++ ] = pool[ i ];
	if ( have )
		StartAdditive( pool[ rand() % have ], Clamp( cl_fpbody_epa_fidget_speed->value, 0.25f, 4.0f ) );
}

static void EPA_Frame( struct ref_params_s *pparams, int st, bool onground, bool ducked )
{
	bool on = cl_fpbody_epa->value != 0.0f;
	const char *hold = HoldType();
	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	int weaponModel = local ? local->curstate.weaponmodel : 0;

	// --- a hostile in view raises the gun (server: FPM_HOSTILE)
	if ( on && ( st & FPM_HOSTILE ) )
		g_mvActivity = g_now;

	// --- flinches by damage type (the Damage message); the hit group (bullets)
	// comes with the move state, so give it a moment to arrive
	bool ctx = cl_fpbody_contextual->value != 0.0f;
	if ( g_epaDmgPending > 0 && ( g_now - g_epaDmgAt >= 0.05f || g_now < g_epaDmgAt ) )
	{
		int bits = g_epaDmgBits;
		g_epaDmgPending = 0;
		g_epaDmgBits = 0;
		g_epaLastHurt = g_now;
		bool ready = g_now >= g_epaNextFlinch;
		if ( on && ready && !( st & ( FPM_VAULT | FPM_PRONE ) ) )
		{
			g_epaNextFlinch = g_now + 0.2f;
			if ( bits & DMG_SHOCK )
			{
				g_epaSpasms = 1 + rand() % 8;			// a burst of twitches
				g_epaNextSpasm = g_now;
			}
			else if ( bits & ( DMG_ACID | DMG_POISON | DMG_NERVEGAS ) )
			{
				StartAdditive( "fa_flinch_phys", 1.0f );
				if ( ( bits & ( DMG_ACID | DMG_NERVEGAS ) ) && g_now >= g_epaNextStrangle && ( g_ovSeq < 0 || g_ovKind == OVK_EASE ) )
				{
					g_epaNextStrangle = g_now + 15.0f;	// gagging on it
					StartOverlayKind( "fm_strangle", OVK_EASE, 0.0f );
				}
			}
			else if ( bits & DMG_BLAST )
			{
				if ( g_ovSeq < 0 || g_ovKind == OVK_EASE )
					StartOverlayKind( "fm_blast", OVK_EASE, 1.4f );
				else
					StartAdditive( "fa_flinch_phys2", 1.0f );
			}
			else if ( bits & DMG_BULLET )
			{
				static const char *hit[] = { "fa_flinch2", "fa_flinch_stomach", "fa_flinch_stomach2", "fa_flinch_shoulder_l",
					"fa_flinch_shoulder_r", "fa_flinch_head" };
				// Contextual: flinch where we were hit (server: the hit group in the move state)
				int hg = ( st >> FPM_HITGROUP_SHIFT ) & 7;
				const char *where = NULL;
				switch ( ctx ? hg : -1 )
				{
				case 0: where = rand() & 1 ? "fa_flinch_phys" : "fa_flinch_phys2"; break;		// generic
				case 1: where = rand() & 1 ? "fa_flinch_head" : "fa_flinch_head2"; break;		// head
				case 2: where = "fa_flinch_phys"; break;										// chest
				case 3: where = rand() & 1 ? "fa_flinch_stomach" : "fa_flinch_stomach2"; break;	// stomach
				case 4: where = "fa_flinch_shoulder_l"; break;									// left arm
				case 5: where = "fa_flinch_shoulder_r"; break;									// right arm
				case 6: where = "fa_flinch"; break;												// left leg
				case 7: where = "fa_flinch2"; break;											// right leg
				}
				StartAdditive( where ? where : hit[ rand() % 6 ], 1.0f );
			}
			else if ( bits & DMG_FALL )
				;											// the landing animation covers it
			else if ( bits & ( DMG_CRUSH | DMG_CLUB | DMG_SLASH | DMG_SONIC | DMG_ENERGYBEAM | DMG_PARALYZE ) )
				StartAdditive( rand() & 1 ? "fa_flinch_phys" : "fa_flinch_phys2", 1.0f );
			else
				StartAdditive( rand() & 1 ? "fa_flinch" : "fa_flinch_back", 1.0f );	// burns, drowning, anything else
		}
	}
	if ( g_epaSpasms > 0 && g_now >= g_epaNextSpasm )
	{
		static const char *spasm[] = { "fa_flinch", "fa_flinch_back", "fa_flinch_head", "fa_flinch_phys",
			"fa_flinch_shoulder_l", "fa_flinch_shoulder_r", "fa_flinch_stomach" };
		if ( on )
			StartAdditive( spasm[ rand() % 7 ], 1.4f );
		g_epaSpasms--;
		g_epaNextSpasm = g_now + RandF( 0.1f, 0.4f );
	}

	// --- Contextual: going under, coming up
	int wl = pparams->waterlevel;
	if ( on && ctx && g_ctxLastWater >= 0 && wl != g_ctxLastWater && !( st & ( FPM_VAULT | FPM_PRONE ) ) )
	{
		if ( wl < 3 && g_ctxLastWater >= 3 )
			StartAdditive( "fa_flinch_phys", 1.0f );
		else if ( wl == 3 )
			StartAdditive( "fa_flinch_stomach", 1.0f );
	}
	g_ctxLastWater = wl;

	// --- Contextual: doors get a push, buttons a press, chargers a reach that repeats
	// while you hold use, anything else you +use a reach (server: what we used)
	// (the off hand does the reaching, see EvalActions; the right-arm gestures
	// from the GMod set were made for empty fists and bent the arm over a gun)
	int use = ( st >> FPM_USE_SHIFT ) & 7;
	if ( on && ctx && use && use != g_ctxLastUse && !( st & ( FPM_PRONE | FPM_VAULT | FPM_CLIMB ) ) )
		g_mvActivity = g_now;
	if ( use == FPM_USE_CHARGER )
		g_useChargeUntil = g_now + 0.3f;			// charging: the hand stays on the charger
	g_ctxLastUse = use;

	// --- picked something up: bend down and grab
	int ammo = 0, weapons = 0;
	for ( int i = 0; i < MAX_AMMO_TYPES; i++ )
		ammo += gWR.CountAmmo( i );
	for ( int s = 0; s < MAX_WEAPON_SLOTS; s++ )
		for ( int p = 0; p < MAX_WEAPON_POSITIONS; p++ )
			if ( gWR.GetWeaponSlot( s, p ) )
				weapons++;
	int armor = gHUD.m_Battery.GetArmor(), health = gHUD.m_Health.m_iHealth;
	// only the server's pickup messages (ammo, weapons, health kits, batteries,
	// any item): the counts also go up and down while shooting and reloading
	// (client prediction against the server), which isn't a pickup
	bool got = g_pickupPending;
	g_pickupPending = false;
	g_epaLastAmmo = ammo; g_epaLastWeapons = weapons; g_epaLastArmor = armor; g_epaLastHealth = health;
	if ( got && on && cl_fpbody_pickup->value != 0.0f && g_now >= g_epaNextPickup && !( st & ( FPM_PRONE | FPM_VAULT | FPM_CLIMB ) ) &&
		 ( g_ovSeq < 0 || g_ovKind == OVK_EASE ) )
	{
		g_epaNextPickup = g_now + 0.5f;					// a crate of items is one reach
		if ( StartOverlayKind( "fm_pickup", OVK_EASE, 0.8f ) )
			g_pickupUntil = g_now + 0.8f;				// a new gun's draw waits for it
	}

	// --- ladders: hands on the ledge when climbing off the top
	if ( g_onladder )
		g_epaLadderVz = pparams->simvel[ 2 ];
	else if ( g_epaPrevLadder && on && g_epaLadderVz > 10.0f && ( g_ovSeq < 0 || g_ovKind == OVK_EASE ) )
		StartOverlayKind( "fm_pickup", OVK_EASE, 0.7f );
	g_epaPrevLadder = g_onladder;

	// --- empty-handed in a fight: cower, crouch-walk, run in a panic (server: FPM_PANIC)
	bool panic = on && ( st & FPM_PANIC ) && weaponModel == 0 && onground && !ducked && !( st & ( FPM_PRONE | FPM_SLIDE | FPM_VAULT ) ) &&
				 pparams->waterlevel < 2 && !g_onladder;
	if ( panic && ( g_ovSeq < 0 || g_ovKind >= OVK_LOOP || ( g_epaCower == 1 && OverlayIs( "fm_cower_intro" ) ) ) )
	{
		if ( g_speed2D < 20.0f )
		{
			if ( g_epaCower == 0 )
			{
				g_epaCower = StartOverlayKind( "fm_cower_intro", OVK_LOOP, 0.0f ) ? 1 : 2;
				if ( g_epaCower == 1 ) g_ovLoop = false;
			}
			else if ( g_epaCower == 1 && !OverlayIs( "fm_cower_intro" ) )
				g_epaCower = 2;
			if ( g_epaCower == 2 )
				WantLoop( "fm_cower", 0.0f );
		}
		else
		{
			g_epaCower = 0;
			if ( g_speed2D < 160.0f )
				WantLoop( "fm_panic_walk", Clamp( g_speed2D / 70.0f, 0.5f, 1.6f ) );
			else
				WantLoop( "fm_panic_run", Clamp( g_speed2D / 220.0f, 0.6f, 1.5f ) );
		}
	}
	else
	{
		g_epaCower = 0;
		if ( g_ovSeq >= 0 && ( OverlayIs( "fm_cower" ) || OverlayIs( "fm_cower_intro" ) || OverlayIs( "fm_panic_walk" ) ||
							   OverlayIs( "fm_panic_run" ) ) )
			StopOverlay();
	}

	// --- fidgets after standing around
	bool active = !onground || g_speed2D > 200.0f || ( in_attack.state & 1 ) || ( in_attack2.state & 1 ) ||
				  ( st & ( FPM_PRONE | FPM_SLIDE | FPM_VAULT | FPM_CLIMB | FPM_PANIC ) ) || g_now - g_epaLastHurt < 2.0f ||
				  weaponModel != g_epaLastWeaponModel || g_onladder || pparams->waterlevel >= 2 ||
				  ( g_ovSeq >= 0 && g_ovKind != OVK_EASE );
	g_epaLastWeaponModel = weaponModel;
	float idle = cl_fpbody_epa_fidget_idle->value;
	float fmin = cl_fpbody_epa_fidget_min->value, fmax = cl_fpbody_epa_fidget_max->value > fmin ? cl_fpbody_epa_fidget_max->value : fmin;
	if ( active || g_epaNextFidget < 0.0f )
	{
		g_epaIdleSince = g_now;
		if ( g_epaNextFidget < g_now + idle )
			g_epaNextFidget = g_now + idle + RandF( fmin, fmax );
	}
	else if ( on && g_now - g_epaIdleSince >= idle && g_now >= g_epaNextFidget && g_adSeq < 0 )
	{
		g_epaNextFidget = g_now + RandF( fmin, fmax );
		if ( RandF( 0.0f, 1.0f ) < cl_fpbody_epa_fidget_chance->value )
			EPA_Fidget( hold, g_ovSeq >= 0 && g_ovKind == OVK_EASE );
	}
}

// --- sprint stamina (the movement is in pm_shared/fpbody_pm_move.h)
static float g_spStamina = 1.0f, g_spLast = -1.0f, g_spUsedAt = -100.0f;
static bool g_spLocked;					// ran dry: no sprinting until a third is back and the key is let go

float FPAnim_GaitScale( void )
{
	if ( !cl_fpbody_gaitspeed || FPBody_Classic() )
		return 1.0f;					// Half-Life's own gaits were made for its speeds
	return Clamp( cl_fpbody_gaitspeed->value, 0.2f, 2.0f );
}

// input.cpp: whether the sprint button (IN_ALT1) goes out this frame
int FPBody_SprintAllowed( int bits )
{
	if ( !FPM_ENABLE_SPRINT || !cl_fpbody_sprint || cl_fpbody_sprint->value == 0.0f || g_spLocked )
		return 0;
	return ( bits & ( IN_ATTACK | IN_ATTACK2 | IN_RELOAD ) ) ? 0 : 1;		// shooting stops it
}

static void Sprint_Frame( int st )
{
	float dt = g_spLast >= 0.0f ? Clamp( g_now - g_spLast, 0.0f, 0.1f ) : 0.0f;
	g_spLast = g_now;
	if ( ( st & FPM_SPRINT ) && g_speed2D > 150.0f )
	{
		g_spStamina -= dt / ( cl_fpbody_sprint_time->value > 0.5f ? cl_fpbody_sprint_time->value : 0.5f );
		g_spUsedAt = g_now;
		if ( g_spStamina <= 0.0f )
		{
			g_spStamina = 0.0f;
			g_spLocked = true;
		}
	}
	else if ( g_now - g_spUsedAt > 1.0f )
		g_spStamina += dt / ( cl_fpbody_sprint_recover->value > 0.5f ? cl_fpbody_sprint_recover->value : 0.5f );
	if ( g_spStamina > 1.0f )
		g_spStamina = 1.0f;
	if ( g_spLocked && g_spStamina >= 0.33f && !( in_alt1.state & 1 ) )
		g_spLocked = false;
}

static const char *SprintAnim( const char *hold )
{
	if ( !strcmp( hold, "pistol" ) || !strcmp( hold, "revolver" ) ) return "fm_sprint_pistol";
	if ( !strcmp( hold, "smg1" ) ) return "fm_sprint_smg";
	if ( !strcmp( hold, "ar2" ) || !strcmp( hold, "shotgun" ) || !strcmp( hold, "crossbow" ) ) return "fm_sprint_rifle";
	if ( !strcmp( hold, "rpg" ) ) return "fm_sprint_launcher";
	if ( !strcmp( hold, "physgun" ) ) return "fm_sprint_lmg";
	if ( !strcmp( hold, "melee" ) ) return "fm_sprint_melee";
	if ( !strcmp( hold, "grenade" ) || !strcmp( hold, "slam" ) ) return "fm_sprint_grenade";
	return FindSeq( g_playerHdr, "fm_sprint_unarmed" ) >= 0 ? "fm_sprint_unarmed" : "fm_sprint_hold";	// empty hands
}

// Double-taps, caught when the key goes down (input.cpp calls these before
// KeyDown), so quick presses from a controller through Steam Input count
// even when both fall between two frames. fresh = the button wasn't held.
static bool DoubleTap( float &last )
{
	float t = gEngfuncs.GetClientTime();
	if ( t - last < 0.4f && t >= last )
	{
		last = -10.0f;
		return true;
	}
	last = t;
	return false;
}

void FPBody_DuckPressed( int fresh )
{
	if ( FPM_ENABLE_PRONE && fresh && cl_fpbody_doubletap && cl_fpbody_doubletap->value != 0.0f && FPBody_Active() &&
		 DoubleTap( g_mvLastDuck ) )
		PM_ProneCmd();
}

void FPBody_ReloadPressed( int fresh )
{
	if ( fresh && cl_fpbody_doubletap && cl_fpbody_doubletap->value != 0.0f && FPBody_Active() && DoubleTap( g_mvLastReload ) )
		PM_HolsterCmd();
}

static void FPMoves_Frame( struct ref_params_s *pparams )
{
	int st = g_fpmState;
	bool onground = pparams->onground != 0;
	bool ducked = pparams->viewheight[ 2 ] < 20.0f;
	bool on = FPBody_Active() && g_playerHdr && cl_fpbody_moves->value != 0.0f;
	g_mvDucked = ducked;
	g_mvOnGround = onground;
	Sprint_Frame( st );

	// double-taps (duck = prone, reload = holster all) are caught as the keys go
	// down, in FPBody_DuckPressed / FPBody_ReloadPressed (input.cpp)
	bool reloadDown = ( in_reload.state & 1 ) != 0;

	// anything that brings the gun up
	int health = gHUD.m_Health.m_iHealth;
	if ( ( in_attack.state & 1 ) || ( in_attack2.state & 1 ) || reloadDown || ( g_mvLastHealth >= 0 && health < g_mvLastHealth ) )
	{
		g_mvActivity = g_now;
		g_mvEaseForced = false;
	}
	g_mvLastHealth = health;

	// falling
	float vz = pparams->simvel[ 2 ];
	if ( !onground )
	{
		if ( -vz > g_mvMaxFall )
			g_mvMaxFall = -vz;
		if ( vz < -300.0f && g_mvFallStart < 0.0f )
			g_mvFallStart = g_now;
		else if ( vz >= -300.0f )
			g_mvFallStart = -1.0f;
	}

	if ( !on )
	{
		if ( g_ovSeq >= 0 && g_ovKind >= OVK_MOVE )
			StopOverlay();
		g_mvPrevState = st;
		g_mvPrevOnGround = onground;
		if ( onground ) g_mvMaxFall = 0.0f;
		return;
	}

	int started = st & ~g_mvPrevState;
	int ended = g_mvPrevState & ~st;
	bool oneShot = g_ovSeq >= 0 && g_ovKind == OVK_MOVE;

	// Opposing Force jobs the server runs (dlls/fpbody_jobs.inl): pull the
	// torch, cut, kick the door in; kneel and give a shot. Each phase plays as
	// long as the server holds it.
	int job = FPM_JOB( st ), prevJob = FPM_JOB( g_mvPrevState );
	if ( job != prevJob )
	{
		static const char *names[ 8 ] = { NULL, "fm_job_pull_torch", "fm_job_cut_door", "fm_job_kick", "fm_job_heal",
			"fm_job_cut_grate", "fm_job_open_grate", "fm_job_store_torch" };
		static const float durs[ 8 ] = { 0.0f, FPM_JOB_DUR_PULL, FPM_JOB_DUR_CUT, FPM_JOB_DUR_KICK, FPM_JOB_DUR_HEAL,
			FPM_JOB_DUR_CUTGRATE, FPM_JOB_DUR_OPENGRATE, FPM_JOB_DUR_STORE };
		if ( job )
			StartOverlayKind( names[ job ], OVK_MOVE, durs[ job ] );
		else if ( g_ovSeq >= 0 && g_ovKind == OVK_MOVE && !strncmp( OverlayName(), "fm_job_", 7 ) )
			StopOverlay();
		oneShot = g_ovSeq >= 0 && g_ovKind == OVK_MOVE;
	}

	// one-off moves, in order of importance
	if ( job )
		;
	else if ( started & FPM_VAULT )
	{
		int type = FPM_VTYPE( st );
		const char *name = type == FPM_VAULT_HOP ? "fm_vault" : type == FPM_VAULT_PULLUP ? "fm_pullup" : "fm_mantle";
		StartOverlayKind( name, OVK_MOVE, g_fpmTimer > 0.1f ? g_fpmTimer + 0.15f : 0.9f );
	}
	else if ( started & FPM_SLIDE )
		StartOverlayKind( "fm_slide", OVK_MOVE, 0.95f );
	else if ( onground && !g_mvPrevOnGround && g_mvMaxFall > 500.0f && !( st & FPM_VAULT ) && pparams->waterlevel < 2 )
	{
		bool roll = g_speed2D > 150.0f && !ducked;
		StartOverlayKind( roll ? "fm_roll" : "fm_hardland", OVK_MOVE, roll ? 1.1f : 1.0f );
	}
	else if ( started & FPM_PRONE )
		StartOverlayKind( ducked ? "fm_pronedown_crouch" : "fm_pronedown_stand", OVK_MOVE, 0.9f );
	else if ( ended & FPM_PRONE )
		StartOverlayKind( ( in_duck.state & 1 ) ? "fm_proneup_crouch" : "fm_proneup_stand", OVK_MOVE, 0.9f );
	oneShot = g_ovSeq >= 0 && g_ovKind == OVK_MOVE;

	// a one-off move that no longer fits: getting up, moving off, or a vault cut short
	if ( oneShot && g_now - g_ovStart > 0.2f )
	{
		if ( ( OverlayIs( "fm_slide" ) && !( st & FPM_SLIDE ) && g_now - g_ovStart > 0.5f ) ||
			 ( ( OverlayIs( "fm_mantle" ) || OverlayIs( "fm_vault" ) || OverlayIs( "fm_pullup" ) ) && !( st & FPM_VAULT ) &&
			   onground && g_speed2D > 60.0f ) )
		{
			StopOverlay();
			oneShot = false;
		}
	}

	// looping states
	const char *loop = NULL;
	float rate = 0.0f;
	if ( st & FPM_BARNACLE )
	{
		// caught by a barnacle (Extended Player Animations' barnacle_unarmed /
		// _armed): legs kicking, hands at the tongue or the gun held ready; while
		// you shoot at it the arms are yours (the gun aims up at it)
		bool shooting = ( in_attack.state & 1 ) || ( in_attack2.state & 1 ) || g_now - g_lastShot < 0.5f;
		cl_entity_t *me = gEngfuncs.GetLocalPlayer();
		bool armed = me && me->curstate.weaponmodel > 0;
		if ( !( shooting && armed ) )
		{
			// armed: the left hand pulls at the tongue, the right holds the gun
			loop = armed ? "fm_barnacle_mixed" : "fm_barnacle_unarmed";
			if ( FindSeq( g_playerHdr, loop ) < 0 )
				loop = armed ? "fm_barnacle_armed" : "fm_strangle";		// older models
			if ( FindSeq( g_playerHdr, loop ) < 0 )
				loop = "fm_strangle";
		}
	}
	else if ( st & FPM_PRONE )
	{
		const char *hold = HoldType();
		static char name[ 48 ];
		if ( g_speed2D > 8.0f )
		{
			snprintf( name, sizeof( name ), "fm_pronewalk_%s", ProneWalk( hold ) );
			rate = Clamp( g_speed2D / 50.0f, 0.3f, 1.6f );
		}
		else
			snprintf( name, sizeof( name ), "fm_prone_%s", hold );
		loop = name;
	}
	else if ( ( st & FPM_CLIMB ) && !onground && vz > -150.0f && !( st & FPM_VAULT ) )
		loop = "fm_climb";
	else if ( !onground && g_mvFallStart >= 0.0f && g_now - g_mvFallStart > 0.35f && !( st & ( FPM_VAULT | FPM_ROPE ) ) &&
			  pparams->waterlevel < 2 && !g_onladder )
		loop = "fm_fall";
	else if ( ( g_onladder || ( st & FPM_ROPE ) ) && !( st & ( FPM_PRONE | FPM_VAULT ) ) && FindSeq( g_playerHdr, "fm_ladder_idle" ) >= 0 )
	{
		// ladders (Freeman): climb up / down at the climbing speed, hang still;
		// Opposing Force's ropes the same, hand over hand
		if ( st & FPM_ROPE )
			vz = g_ropeVz;
		if ( vz > 5.0f )
			loop = "fm_ladder_up";
		else if ( vz < -5.0f )
			loop = "fm_ladder_down";
		else
			loop = "fm_ladder_idle";
		rate = ( vz > 5.0f || vz < -5.0f ) ? Clamp( (float)fabs( vz ) / 120.0f, 0.4f, 2.0f ) : 1.0f;
	}
	else if ( ( st & FPM_SPRINT ) && onground && !ducked && g_speed2D > 200.0f && FindSeq( g_playerHdr, SprintAnim( HoldType() ) ) >= 0 )
	{
		loop = SprintAnim( HoldType() );
		rate = Clamp( g_speed2D / 380.0f, 0.7f, 1.4f );
	}

	if ( loop && !oneShot )
		WantLoop( loop, rate );
	else if ( !loop && g_ovSeq >= 0 && g_ovKind == OVK_LOOP )
		StopOverlay();

	// at ease: lower the gun after a few quiet seconds
	bool easeOk = cl_fpbody_atease->value != 0.0f && onground && !ducked && !( st & ( FPM_PRONE | FPM_SLIDE | FPM_VAULT | FPM_SPRINT ) ) &&
				  !gHUD.m_Flash.IsOn() && pparams->waterlevel < 2 && !g_onladder;
	if ( easeOk )
	{
		const char *hold = HoldType();
		easeOk = strcmp( hold, "passive" ) && strcmp( hold, "melee" ) && strcmp( hold, "grenade" ) && strcmp( hold, "slam" );
	}
	bool easeWant = easeOk && ( g_mvEaseForced || g_now - g_mvActivity > cl_fpbody_atease_delay->value );
	// one-shot moves that share the at-ease slot play out: weapon draws, the
	// pickup reach, the blast reaction, gagging on gas
	bool drawing = g_ovSeq >= 0 && g_ovKind == OVK_EASE &&
				   ( OverlayIs( "fm_draw_pistol" ) || OverlayIs( "fm_draw_rifle" ) || OverlayIs( "fm_draw_rpg" ) ||
					 OverlayIs( "fm_draw_melee" ) || OverlayIs( "fm_pickup" ) || OverlayIs( "fm_blast" ) ||
					 OverlayIs( "fm_strangle" ) );
	if ( easeWant && !drawing && ( g_ovSeq < 0 || g_ovKind == OVK_EASE ) )
	{
		// Freeman: pistols and the .357 hang at the side (relaxed hands), long guns go to the passive hold
		const char *hold = HoldType();
		bool relaxed = ( !strcmp( hold, "pistol" ) || !strcmp( hold, "revolver" ) ) && FindSeq( g_playerHdr, "fm_relax_idle" ) >= 0;
		const char *name = relaxed ? ( g_speed2D < 20.0f ? "fm_relax_idle" : g_speed2D < 160.0f ? "fm_relax_walk" : "fm_relax_run" )
								   : ( g_speed2D < 20.0f ? "fm_passive_idle" : g_speed2D < 160.0f ? "fm_passive_walk" : "fm_passive_run" );
		if ( !OverlayIs( name ) )
			StartOverlayKind( name, OVK_EASE, 0.0f );
	}
	else if ( !easeWant && !drawing && g_ovSeq >= 0 && g_ovKind == OVK_EASE )
		StopOverlay();

	// how far the lowered hold is in, for fp_gun_relax
	{
		bool relaxed = g_ovSeq >= 0 && g_ovKind == OVK_EASE &&
					   ( OverlayIs( "fm_relax_idle" ) || OverlayIs( "fm_relax_walk" ) || OverlayIs( "fm_relax_run" ) ||
						 OverlayIs( "fm_passive_idle" ) || OverlayIs( "fm_passive_walk" ) || OverlayIs( "fm_passive_run" ) );
		g_relaxW += ( ( relaxed ? 1.0f : 0.0f ) - g_relaxW ) * Clamp01( g_frameTime * 6.0f );
	}

	EPA_Frame( pparams, st, onground, ducked );

	g_mvPrevState = st;
	g_mvPrevOnGround = onground;
	if ( onground )
	{
		g_mvMaxFall = 0.0f;
		g_mvFallStart = -1.0f;
	}
}

void FPAnim_Frame( struct ref_params_s *pparams )
{
	static float s_lastNow = -1.0f;
	g_now = gEngfuncs.GetClientTime();
	// the client clock starts again at every map change and saved game: timers
	// set on the last map would block pickups, flinches and draws (or fire late)
	if ( g_now < s_lastNow - 0.5f )
	{
		FPDbg( "clock reset %.1f -> %.1f: timers cleared\n", s_lastNow, g_now );
		g_pickupUntil = 0.0f; g_epaNextPickup = 0.0f; g_glReloadAt = 0.0f; g_useChargeUntil = 0.0f;
		g_epaNextFlinch = 0.0f; g_epaNextStrangle = 0.0f; g_epaNextSpasm = 0.0f; g_epaSpasms = 0;
		g_epaNextFidget = -1.0f; g_epaIdleSince = g_now; g_epaDmgPending = 0; g_epaDmgBits = 0;
		g_mvActivity = g_now; g_adHoldUntil = 0.0f; g_l4dShellAt = -10.0f; g_pickupPending = false;
		g_mvLastDuck = g_mvLastReload = -10.0f; g_epaLastHurt = -100.0f;
		g_cur.type = CLIP_NONE; g_prev.type = CLIP_NONE;
		// and the ones that let the off hand go / pose the arms for a moment
		// (use, flashlight, landing, firing): from the last map they lie in the
		// future and would hold it off the gun until the clock caught up
		g_useStart = g_flashStart = g_landStart = g_lastShot = -10.0f;
		g_useHoldW = 0.0f; g_usePalmW = 0.0f; g_aimW = 0.0f; g_quickTime = -100.0f;
		g_mvFallStart = -1.0f; g_prevFadeStart = -10.0f;
		g_lastHeadTime = g_headOfsTime = -10.0f; g_hookTime = -10.0f;
		StopOverlay();
	}
	s_lastNow = g_now;
	g_frameTime = Clamp( pparams->frametime, 0.0f, 0.1f );

	PollViewModel();

	g_speed2D = (float)sqrt( pparams->simvel[ 0 ] * pparams->simvel[ 0 ] + pparams->simvel[ 1 ] * pparams->simvel[ 1 ] );

	// full-body acts end when you move, shoot or jump
	if ( g_ovSeq >= 0 && g_ovFull && g_ovKind == OVK_USER && g_now - g_ovStart > 0.3f )
	{
		if ( g_speed2D > 40.0f || ( in_attack.state & 1 ) || ( in_attack2.state & 1 ) || ( in_jump.state & 1 ) )
			StopOverlay();
	}

	// +use
	bool useDown = ( in_use.state & 1 ) != 0;
	if ( useDown && !g_useDown )
		g_useStart = g_now;
	g_useDown = useDown;

	float holdTarget = ( useDown && g_now - g_useStart > 0.3f ) ? 0.7f : 0.0f;
	if ( useDown && g_now < g_useChargeUntil )
		holdTarget = 0.9f;								// hand flat on the charger while it charges
	g_useHoldW += ( holdTarget - g_useHoldW ) * Clamp01( g_frameTime * 10.0f );

	// flashlight (the server tells the HUD when it toggles)
	int flash = gHUD.m_Flash.IsOn() ? 1 : 0;
	if ( g_lastFlash >= 0 && flash != g_lastFlash )
		g_flashStart = g_now;
	g_lastFlash = flash;

	// landing
	int onGround = pparams->onground ? 1 : 0;
	if ( !onGround )
	{
		float fall = -pparams->simvel[ 2 ];
		if ( fall > g_maxFallSpeed )
			g_maxFallSpeed = fall;
	}
	else if ( !g_wasOnGround )
	{
		if ( g_maxFallSpeed > 180.0f )
		{
			g_landStart = g_now;
			g_landStrength = Clamp( ( g_maxFallSpeed - 180.0f ) / 420.0f, 0.15f, 1.0f );
		}
		g_maxFallSpeed = 0.0f;
	}
	if ( onGround )
		g_maxFallSpeed = 0.0f;
	g_wasOnGround = onGround;

	// ladders: climb cycle follows height travelled
	float ladderTarget = g_onladder ? 1.0f : 0.0f;
	g_ladderW += ( ladderTarget - g_ladderW ) * Clamp01( g_frameTime * 6.0f );
	float dz = pparams->simorg[ 2 ] - g_lastZ;
	if ( fabs( dz ) < 64.0f && g_onladder )
		g_ladderPhase += dz * (float)( 2.0 * M_PI / 40.0 );
	// a rope holds our velocity at zero and moves us along it: the speed is the height travelled
	if ( ( g_mvPrevState & FPM_ROPE ) && g_frameTime > 0.0f && fabs( dz ) < 64.0f )
	{
		g_ropeVz += ( dz / g_frameTime - g_ropeVz ) * Clamp01( g_frameTime * 8.0f );
		g_ladderPhase += dz * (float)( 2.0 * M_PI / 40.0 );
	}
	else
		g_ropeVz = 0.0f;
	g_lastZ = pparams->simorg[ 2 ];

	// weapon sway: the gun lags behind turning and leans when strafing
	float yaw = pparams->cl_viewangles[ YAW ];
	float pitch = pparams->cl_viewangles[ PITCH ];
	if ( g_haveLastAngles && g_frameTime > 0.0f )
	{
		float dyaw = yaw - g_lastYaw;
		while ( dyaw > 180.0f ) dyaw -= 360.0f;
		while ( dyaw < -180.0f ) dyaw += 360.0f;
		float dpitch = pitch - g_lastPitch;

		float yawVel = dyaw / g_frameTime;
		float pitchVel = dpitch / g_frameTime;

		Vector f, r, u;
		AngleVectors( pparams->cl_viewangles, f, r, u );
		float side = Dot3( pparams->simvel, r );

		float k = cl_fpbody_sway->value;
		float ty = Clamp( -yawVel * 0.012f, -6.0f, 6.0f ) * k;
		float tp = Clamp( -pitchVel * 0.010f, -5.0f, 5.0f ) * k;	// gun lags behind looking up/down
		float tr = Clamp( side / 320.0f * 4.0f, -4.0f, 4.0f ) * k;
		float a = Clamp01( g_frameTime * 8.0f );
		g_swayYaw   += ( ty - g_swayYaw ) * a;
		g_swayPitch += ( tp - g_swayPitch ) * a;
		g_swayRoll  += ( tr - g_swayRoll ) * a;
	}
	// step rhythm for the arm bob while moving with a weapon
	{
		float speed = (float)sqrt( pparams->simvel[ 0 ] * pparams->simvel[ 0 ] + pparams->simvel[ 1 ] * pparams->simvel[ 1 ] );
		float target = pparams->onground ? Clamp01( speed / 250.0f ) : 0.0f;
		g_runW += ( target - g_runW ) * Clamp01( g_frameTime * 6.0f );
		g_runPhase += speed * g_frameTime * (float)( 2.0 * M_PI / 128.0 );	// one cycle = two steps
		if ( g_runPhase > 2.0 * M_PI * 64 ) g_runPhase -= (float)( 2.0 * M_PI * 64 );
	}
	g_attackHeld = ( in_attack.state & 1 ) != 0;
	g_lastYaw = yaw;
	g_lastPitch = pitch;
	g_haveLastAngles = true;

	// grenade launcher reload, a moment after the shot
	if ( g_glReloadAt > 0.0f && ( g_now >= g_glReloadAt || g_now < g_glReloadAt - 2.0f ) )
	{
		g_glReloadAt = 0.0f;
		if ( g_ovSeq < 0 )
		{
			StartClip( CLIP_RELOAD, 1, 1.0f, 1.3f );
			g_mvActivity = g_now;
		}
	}

	FPMoves_Frame( pparams );
}

static void EvalActions( float now, pose_t &p, const float *f, const float *r, const float *u )
{
	float dir[ 3 ];

	// +use: off hand reaches out; holding it keeps the hand out (pushing)
	float tap = Bump( ( now - g_useStart ) / 0.6f, 0.0f, 1.0f );
	float useW = tap > g_useHoldW ? tap : g_useHoldW;
	g_usePalmW = useW;
	if ( useW > 0.0f )
	{
		if ( now < g_useChargeUntil )
			MakeDir( f, r, u, 1.0f, -0.1f, -0.05f, dir );	// charger: palm on the panel
		else
			MakeDir( f, r, u, 1.0f, -0.05f, 0.1f, dir );
		AddLeftAim( p, dir, useW );
		p.lBack     -= 3.0f * useW;
		p.armsPitch += 8.0f * useW;
	}

	// flashlight: tap the helmet
	float fl = Bump( ( now - g_flashStart ) / 0.55f, 0.0f, 1.0f );
	if ( fl > 0.0f )
	{
		MakeDir( f, r, u, 0.45f, 0.15f, 1.0f, dir );
		AddLeftAim( p, dir, 0.9f * fl );
	}

	// landing: crouch into the impact
	float lt = now - g_landStart;
	if ( lt >= 0.0f && lt < 0.8f )
	{
		float k = lt < 0.08f ? lt / 0.08f : (float)exp( -( lt - 0.08f ) * 6.0f );
		p.spinePitch += 12.0f * g_landStrength * k;
		p.armsPitch  += 10.0f * g_landStrength * k;
	}

	// ladder: gun lowered, off hand climbs
	if ( g_ladderW > 0.01f )
	{
		p.armsPitch += 30.0f * g_ladderW;
		p.rPitch    += 10.0f * g_ladderW * (float)sin( g_ladderPhase + M_PI );
		MakeDir( f, r, u, 0.55f, 0.0f, 1.0f, dir );
		AddLeftAim( p, dir, 0.75f * g_ladderW * ( 0.5f + 0.5f * (float)sin( g_ladderPhase ) ) );
	}

	// arms bob with the steps while moving (the gun bounces a little)
	if ( g_runW > 0.01f && cl_fpbody_runbob && cl_fpbody_runbob->value != 0.0f )
	{
		float amp = cl_fpbody_runbob->value * g_runW;
		p.armsPitch += 2.5f * amp * (float)sin( 2.0f * g_runPhase );
		p.armsYaw   += 1.5f * amp * (float)sin( g_runPhase );
		p.armsRoll  += 1.0f * amp * (float)sin( g_runPhase );
	}

	// sway
	p.armsYaw   += g_swayYaw;
	p.armsPitch += g_swayPitch;
	p.armsRoll  += g_swayRoll;
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

struct skel_t
{
	const studiohdr_t *hdr;
	int numbones;
	int lClav, lUpper, lHand;
	int rClav, rUpper, rHand;
	int spine;
	int lFore;
	bool lForeMask[ MAXSTUDIOBONES ];
	int rFore;
	bool rForeMask[ MAXSTUDIOBONES ];
	bool rHandMask[ MAXSTUDIOBONES ];
	bool lHandMask[ MAXSTUDIOBONES ];
	int lThumb, lFinger;	// Bip01 L Finger0 / Finger1 (the hand's palm frame)
	bool armsMask[ MAXSTUDIOBONES ];
	bool lUpperMask[ MAXSTUDIOBONES ];
	bool rUpperMask[ MAXSTUDIOBONES ];
	bool spineMask[ MAXSTUDIOBONES ];
};

static skel_t g_skel;

static int FindBone( const mstudiobone_t *bones, int num, const char *a, const char *b )
{
	for ( int i = 0; i < num; i++ )
		if ( !stricmp( bones[ i ].name, a ) || ( b && !stricmp( bones[ i ].name, b ) ) )
			return i;
	return -1;
}

static void MarkSubtree( const mstudiobone_t *bones, int num, int root, bool *mask, bool clear )
{
	if ( clear )
		memset( mask, 0, sizeof( bool ) * MAXSTUDIOBONES );
	if ( root < 0 )
		return;
	mask[ root ] = true;
	for ( int i = root + 1; i < num; i++ )
	{
		int parent = bones[ i ].parent;
		if ( parent >= 0 && mask[ parent ] && parent >= root )
			mask[ i ] = true;
	}
}

static void CacheSkeleton( const studiohdr_t *hdr )
{
	if ( g_skel.hdr == hdr )
		return;

	memset( &g_skel, 0, sizeof( g_skel ) );
	g_skel.hdr = hdr;

	const mstudiobone_t *bones = (const mstudiobone_t *)( (const byte *)hdr + hdr->boneindex );
	int num = hdr->numbones > MAXSTUDIOBONES ? MAXSTUDIOBONES : hdr->numbones;
	g_skel.numbones = num;

	// Valve's skeletons use the old Character Studio names (L Arm = clavicle,
	// L Arm1 = upper arm); newer custom models use Clavicle / UpperArm.
	g_skel.lClav  = FindBone( bones, num, "Bip01 L Arm",  "Bip01 L Clavicle" );
	g_skel.lUpper = FindBone( bones, num, "Bip01 L Arm1", "Bip01 L UpperArm" );
	g_skel.lHand  = FindBone( bones, num, "Bip01 L Hand", NULL );
	g_skel.rClav  = FindBone( bones, num, "Bip01 R Arm",  "Bip01 R Clavicle" );
	g_skel.rUpper = FindBone( bones, num, "Bip01 R Arm1", "Bip01 R UpperArm" );
	g_skel.rHand  = FindBone( bones, num, "Bip01 R Hand", NULL );
	g_skel.spine  = FindBone( bones, num, "Bip01 Spine2", "Bip01 Spine1" );

	MarkSubtree( bones, num, g_skel.lClav, g_skel.armsMask, true );
	MarkSubtree( bones, num, g_skel.rClav, g_skel.armsMask, false );
	MarkSubtree( bones, num, g_skel.lUpper, g_skel.lUpperMask, true );
	MarkSubtree( bones, num, g_skel.rUpper, g_skel.rUpperMask, true );
	MarkSubtree( bones, num, g_skel.spine, g_skel.spineMask, true );

	g_skel.lFore = FindBone( bones, num, "Bip01 L Arm2", "Bip01 L Forearm" );
	MarkSubtree( bones, num, g_skel.lFore, g_skel.lForeMask, true );
	g_skel.rFore = FindBone( bones, num, "Bip01 R Arm2", "Bip01 R Forearm" );
	MarkSubtree( bones, num, g_skel.rFore, g_skel.rForeMask, true );
	MarkSubtree( bones, num, g_skel.rHand, g_skel.rHandMask, true );
	MarkSubtree( bones, num, g_skel.lHand, g_skel.lHandMask, true );
	g_skel.lThumb = FindBone( bones, num, "Bip01 L Finger0", NULL );
	g_skel.lFinger = FindBone( bones, num, "Bip01 L Finger1", NULL );
}

// Rotate (and optionally move) every masked bone around pivot by world rotation W
static void TransformBones( float ( *bone )[ 3 ][ 4 ], float ( *light )[ 3 ][ 4 ], const bool *mask,
	const mat3_t W, const float *pivot, const float *move )
{
	for ( int i = 0; i < g_skel.numbones; i++ )
	{
		if ( !mask[ i ] )
			continue;

		float ( *arrays[ 2 ] )[ 3 ][ 4 ] = { bone, light };
		for ( int a = 0; a < 2; a++ )
		{
			float ( *m )[ 4 ] = arrays[ a ][ i ];
			float rot[ 3 ][ 3 ], t[ 3 ];
			int r, c;

			for ( r = 0; r < 3; r++ )
				for ( c = 0; c < 3; c++ )
					rot[ r ][ c ] = W[ r ][ 0 ] * m[ 0 ][ c ] + W[ r ][ 1 ] * m[ 1 ][ c ] + W[ r ][ 2 ] * m[ 2 ][ c ];

			float d[ 3 ] = { m[ 0 ][ 3 ] - pivot[ 0 ], m[ 1 ][ 3 ] - pivot[ 1 ], m[ 2 ][ 3 ] - pivot[ 2 ] };
			for ( r = 0; r < 3; r++ )
				t[ r ] = W[ r ][ 0 ] * d[ 0 ] + W[ r ][ 1 ] * d[ 1 ] + W[ r ][ 2 ] * d[ 2 ] + pivot[ r ] + ( move ? move[ r ] : 0.0f );

			for ( r = 0; r < 3; r++ )
			{
				for ( c = 0; c < 3; c++ )
					m[ r ][ c ] = rot[ r ][ c ];
				m[ r ][ 3 ] = t[ r ];
			}
		}
	}
}

static void BoneOrigin( float ( *light )[ 3 ][ 4 ], int bone, float *out )
{
	out[ 0 ] = light[ bone ][ 0 ][ 3 ];
	out[ 1 ] = light[ bone ][ 1 ][ 3 ];
	out[ 2 ] = light[ bone ][ 2 ][ 3 ];
}

// Builds yaw * roll * pitch around the view axes (+pitch = down, +yaw = left,
// +roll = right side down)
static void ViewRotation( const float *f, const float *r, const float *u,
	float pitchDown, float yawLeft, float rollRight, mat3_t out )
{
	mat3_t a, b, c;
	AxisAngle( u, yawLeft, a );
	AxisAngle( f, rollRight, b );
	AxisAngle( r, -pitchDown, c );
	MatMul3( a, b, out );
	MatMul3( out, c, out );
}

// Swing the arm starting at upperBone so that the hand points along dir
static void AimArm( float ( *bone )[ 3 ][ 4 ], float ( *light )[ 3 ][ 4 ], int upperBone, int handBone,
	const bool *mask, const float *dir, float weight )
{
	if ( upperBone < 0 || handBone < 0 || weight <= 0.001f )
		return;

	float shoulder[ 3 ], hand[ 3 ], v[ 3 ];
	BoneOrigin( light, upperBone, shoulder );
	BoneOrigin( light, handBone, hand );
	VectorSubtract( hand, shoulder, v );
	if ( Normalize3( v ) < 1.0f )
		return;

	float axis[ 3 ];
	Cross( v, dir, axis );
	float sinA = Normalize3( axis );
	float cosA = Clamp( Dot3( v, dir ), -1.0f, 1.0f );
	if ( sinA < 1e-4f )
		return;

	float angle = (float)( atan2( sinA, cosA ) * 180.0 / M_PI ) * Clamp01( weight );
	mat3_t W;
	AxisAngle( axis, angle, W );
	TransformBones( bone, light, mask, W, shoulder, NULL );
}

// ---------------------------------------------------------------------------
// Gun aiming and off-hand IK
// ---------------------------------------------------------------------------

static const gun_t *GunForModel( int modelindex )
{
	static int cachedIndex = -1;
	static const gun_t *cachedGun = NULL;
	if ( modelindex == cachedIndex )
		return cachedGun;

	cachedIndex = modelindex;
	cachedGun = NULL;
	model_t *m = modelindex > 0 ? IEngineStudio.GetModelByIndex( modelindex ) : NULL;
	if ( !m )
		return NULL;

	char name[ 64 ];
	Lower( m->name, name, sizeof( name ) );
	for ( int i = 0; i < (int)( sizeof( g_guns ) / sizeof( g_guns[ 0 ] ) ); i++ )
	{
		char want[ 40 ];
		snprintf( want, sizeof( want ), "/%s.mdl", g_guns[ i ].model );
		if ( Has( name, want ) )
		{
			cachedGun = &g_guns[ i ];
			break;
		}
	}
	return cachedGun;
}

// Right-hand bone rotation times a vector (bone space -> world)
static void HandToWorldDir( float ( *light )[ 3 ][ 4 ], int hand, const float *v, float *out )
{
	for ( int r = 0; r < 3; r++ )
		out[ r ] = light[ hand ][ r ][ 0 ] * v[ 0 ] + light[ hand ][ r ][ 1 ] * v[ 1 ] + light[ hand ][ r ][ 2 ] * v[ 2 ];
}

// Rotate `mask` bones around pivot so that direction `from` turns toward `to`
static void TurnToward( float ( *bone )[ 3 ][ 4 ], float ( *light )[ 3 ][ 4 ], const bool *mask,
	const float *pivot, const float *from, const float *to, float weight )
{
	float a[ 3 ] = { from[ 0 ], from[ 1 ], from[ 2 ] };
	float b[ 3 ] = { to[ 0 ], to[ 1 ], to[ 2 ] };
	if ( Normalize3( a ) < 1e-4f || Normalize3( b ) < 1e-4f )
		return;
	float axis[ 3 ];
	Cross( a, b, axis );
	float s = Normalize3( axis );
	if ( s < 1e-5f )
		return;
	float ang = (float)( atan2( s, Clamp( Dot3( a, b ), -1.0f, 1.0f ) ) * 180.0 / M_PI ) * Clamp01( weight );
	mat3_t W;
	AxisAngle( axis, ang, W );
	TransformBones( bone, light, mask, W, pivot, NULL );
}

static float AngleAt( const float *a, const float *corner, const float *b )
{
	float u[ 3 ], v[ 3 ];
	VectorSubtract( a, corner, u );
	VectorSubtract( b, corner, v );
	if ( Normalize3( u ) < 1e-4f || Normalize3( v ) < 1e-4f )
		return 0.0f;
	return (float)acos( Clamp( Dot3( u, v ), -1.0f, 1.0f ) );
}

// Two-bone IK: bend the elbow so the shoulder-to-hand distance matches the
// target, then swing the arm so the hand lands on it. The elbow stays in its
// current bend plane, so it keeps pointing the way the animation had it.
static void ReachArm( float ( *bone )[ 3 ][ 4 ], float ( *light )[ 3 ][ 4 ], const float *target, float weight,
	bool rightArm = false, float elbowDown = 0.0f )
{
	int upper = rightArm ? g_skel.rUpper : g_skel.lUpper;
	int fore  = rightArm ? g_skel.rFore  : g_skel.lFore;
	int hand  = rightArm ? g_skel.rHand  : g_skel.lHand;
	const bool *upperMask = rightArm ? g_skel.rUpperMask : g_skel.lUpperMask;
	const bool *foreMask  = rightArm ? g_skel.rForeMask  : g_skel.lForeMask;

	if ( upper < 0 || fore < 0 || hand < 0 || weight <= 0.001f )
		return;

	float S[ 3 ], E[ 3 ], H[ 3 ];
	BoneOrigin( light, upper, S );
	BoneOrigin( light, fore, E );
	BoneOrigin( light, hand, H );

	float se[ 3 ], eh[ 3 ], st[ 3 ];
	VectorSubtract( E, S, se );
	VectorSubtract( H, E, eh );
	VectorSubtract( target, S, st );
	float a = (float)sqrt( Dot3( se, se ) ), b = (float)sqrt( Dot3( eh, eh ) );
	float d = (float)sqrt( Dot3( st, st ) );
	if ( a < 0.5f || b < 0.5f || d < 0.5f )
		return;
	// never all the way straight: at full stretch the bend direction is undefined
	// and the elbow can flip backwards (the hand falls a little short instead)
	d = Clamp( d, (float)fabs( a - b ) + 0.1f, ( a + b ) * 0.96f );

	// 1. elbow bend: the forearm turns in the plane it bends in now, on the side
	// it bends to now, to the angle that puts the hand at the target's distance.
	// (Picking the turn by the resulting angle alone can't tell bending from
	// over-straightening past 180, so the elbow could flip backwards and twist.)
	float des = (float)acos( Clamp( ( a * a + b * b - d * d ) / ( 2.0f * a * b ), -1.0f, 1.0f ) );
	float uu[ 3 ] = { se[ 0 ] / a, se[ 1 ] / a, se[ 2 ] / a };	// along the upper arm
	float vv[ 3 ];													// the side the elbow bends to
	float de = Dot3( eh, uu );
	for ( int i = 0; i < 3; i++ )
		vv[ i ] = eh[ i ] - uu[ i ] * de;
	if ( Normalize3( vv ) < 0.05f * b )
	{
		// arm (nearly) straight: bend toward the body's front-down
		float hint[ 3 ] = { 0.0f, 0.0f, -1.0f };
		float dh = Dot3( hint, uu );
		for ( int i = 0; i < 3; i++ )
			vv[ i ] = hint[ i ] - uu[ i ] * dh;
		if ( Normalize3( vv ) < 1e-3f )
			return;
	}
	// interior angle des between the upper arm (back toward the shoulder) and the forearm
	float want[ 3 ];
	for ( int i = 0; i < 3; i++ )
		want[ i ] = -uu[ i ] * (float)cos( des ) + vv[ i ] * (float)sin( des );
	TurnToward( bone, light, foreMask, E, eh, want, weight );
	BoneOrigin( light, hand, H );

	// 2. swing the arm at the shoulder
	float sh[ 3 ];
	VectorSubtract( H, S, sh );
	TurnToward( bone, light, upperMask, S, sh, st, weight );

	// 3. elbow down: turn the arm about the shoulder-to-hand line (the hand stays
	// put) so the elbow hangs under the gun and a little out from the body,
	// instead of folding in across the chest or up toward the face
	if ( elbowDown > 0.0f )
	{
		BoneOrigin( light, fore, E );
		BoneOrigin( light, hand, H );
		float ax[ 3 ], e[ 3 ], pole[ 3 ] = { 0.0f, 0.0f, -1.0f };
		VectorSubtract( H, S, ax );
		VectorSubtract( E, S, e );
		if ( g_skel.lClav >= 0 && g_skel.rClav >= 0 )
		{
			float lc[ 3 ], rc[ 3 ], out[ 3 ];
			BoneOrigin( light, g_skel.lClav, lc );
			BoneOrigin( light, g_skel.rClav, rc );
			VectorSubtract( rightArm ? rc : lc, rightArm ? lc : rc, out );
			out[ 2 ] = 0.0f;
			if ( Normalize3( out ) > 1e-3f )
				for ( int i = 0; i < 3; i++ )
					pole[ i ] += out[ i ] * 0.45f;
		}
		if ( Normalize3( ax ) > 1e-3f )
		{
			float de = Dot3( e, ax ), dp = Dot3( pole, ax ), pe[ 3 ], pp[ 3 ];
			for ( int i = 0; i < 3; i++ )
			{
				pe[ i ] = e[ i ] - ax[ i ] * de;
				pp[ i ] = pole[ i ] - ax[ i ] * dp;
			}
			if ( Normalize3( pe ) > 1e-3f && Normalize3( pp ) > 1e-3f )
			{
				float ang = (float)( acos( Clamp( Dot3( pe, pp ), -1.0f, 1.0f ) ) * 180.0 / M_PI ) * Clamp01( elbowDown ) * Clamp01( weight );
				if ( ang > 0.5f )
				{
					// try one way; if the elbow ends up further from the pole, the other
					mat3_t W;
					AxisAngle( ax, ang, W );
					float e1[ 3 ];
					for ( int r = 0; r < 3; r++ )
						e1[ r ] = W[ r ][ 0 ] * pe[ 0 ] + W[ r ][ 1 ] * pe[ 1 ] + W[ r ][ 2 ] * pe[ 2 ];
					if ( Dot3( e1, pp ) < Dot3( pe, pp ) )
						AxisAngle( ax, -ang, W );
					TransformBones( bone, light, upperMask, W, S, NULL );
				}
			}
		}
	}
}

// GMod mode: where the left wrist goes on each two-handed gun - on the barrel /
// handguard / front handle, in the space of the bone the gun hangs from. Found by
// posing the body in the gun's hold and reaching the arm to each point
// (tools/gmod_anims/lefthand_gmod.py); a point on the gun, so any hold can use it.
struct gmhandle_t
{
	const char *model;
	const char *bone;
	float wrist[ 3 ];
	int length;				// header length of the model it was measured on (0 = any)
};

static const gmhandle_t g_gmHandles[] =
{
	// VAPW v2 held models (Half-Life\.Mods\vapw_v2\models), told apart by their size:
	{ "p_9mmar", "Bip01 R Hand", { 8.5f, 2.5f, 0.0f }, 72036 },			// MP5: under the grenade launcher
	{ "p_shotgun", "Bip01 R Hand", { 14.5f, 6.0f, -0.5f }, 60840 },		// cupping the pump from below
	{ "p_rpg", "Bip01 R Hand", { 12.0f, 4.5f, 0.5f }, 117012 },			// on the rocket tube
	{ "p_crossbow", "Bip01 R Hand", { 11.5f, 3.0f, -3.0f }, 112276 },		// the front grip under the bow
	{ "p_egon", "Bip01 R Arm2", { 17.0f, -10.5f, 2.0f }, 134264 },	// VAPW Gluon: on the side bar
	{ "p_9mmar", "Bip01 R Hand", { 14.5f, 3.5f, 1.0f }, 0 },			// HD M16 / MP5: under the grenade launcher (within reach looking down)
	{ "p_shotgun", "Bip01 R Hand", { 16.0f, 3.0f, 1.0f }, 0 },		// under the pump
	{ "p_crossbow", "Bip01 R Hand", { 9.5f, 4.0f, 0.5f }, 0 },		// fore-stock
	{ "p_rpg", "Bip01 R Hand", { 19.0f, 7.2f, 1.0f }, 0 },			// under the front of the tube
	{ "p_hgun", "Bip01 R Hand", { 13.0f, 7.2f, -3.5f }, 0 },
	{ "p_gauss", "Bip01 R Hand", { 11.8f, 8.5f, 5.0f }, 37260 },		// MMod Tau Cannon: the side handle
	{ "p_egon", "Bip01 R Arm2", { 19.0f, -1.5f, 3.5f }, 29080 },		// HD Gluon gun (on the forearm): under the nozzle
	{ "p_saw", "Bip01 R Hand", { 19.0f, 4.2f, 2.5f }, 0 },
	{ "p_m40a1", "Bip01 R Hand", { 13.0f, 3.5f, 2.5f }, 0 },
	{ "p_shock", "Bip01 R Hand", { 16.0f, 8.0f, 1.0f }, 0 },
	{ "p_spore_launcher", "Bip01 R Hand", { 11.5f, 6.5f, -6.5f }, 0 },
	{ "p_displacer", "Bip01 R Hand", { 12.0f, 10.0f, 6.0f }, 338732 },	// upscaled Displacer: the side handle
	{ "p_displacer", "Bip01 R Hand", { 23.5f, 6.5f, 4.0f }, 0 },
};

static const gmhandle_t *GmHandleForModel( int modelindex )
{
	static int cachedIndex = -1;
	static const gmhandle_t *cached = NULL;
	if ( modelindex == cachedIndex )
		return cached;
	cachedIndex = modelindex;
	cached = NULL;
	model_t *m = modelindex > 0 ? IEngineStudio.GetModelByIndex( modelindex ) : NULL;
	if ( !m )
		return NULL;
	char name[ 64 ];
	Lower( m->name, name, sizeof( name ) );
	const studiohdr_t *mh = (const studiohdr_t *)IEngineStudio.Mod_Extradata( m );
	for ( int i = 0; i < (int)( sizeof( g_gmHandles ) / sizeof( g_gmHandles[ 0 ] ) ); i++ )
	{
		char want[ 40 ];
		snprintf( want, sizeof( want ), "/%s.mdl", g_gmHandles[ i ].model );
		if ( Has( name, want ) && ( !g_gmHandles[ i ].length || ( mh && mh->length == g_gmHandles[ i ].length ) ) )
		{
			cached = &g_gmHandles[ i ];
			break;
		}
	}
	return cached;
}

// Left-hand tuning per gun (fp_grip): forward along the barrel, left (+) / right (-)
// across it, up (+) / down (-); saved in <game>/fpbody_grips.cfg. The cl_fpbody_grip_*
// cvars add to every gun.
struct gripofs_t { char model[ 32 ]; float ofs[ 3 ]; };
static gripofs_t g_gripOfs[ 48 ];
static int g_numGripOfs;
static bool g_gripCfgRun;

static void GunShortName( int weaponmodel, char *out, int size )
{
	out[ 0 ] = 0;
	model_t *m = weaponmodel > 0 ? IEngineStudio.GetModelByIndex( weaponmodel ) : NULL;
	if ( !m )
		return;
	const char *n = m->name, *sl = strrchr( n, '/' );
	if ( sl )
		n = sl + 1;
	int i = 0;
	for ( ; n[ i ] && n[ i ] != '.' && i < size - 1; i++ )
		out[ i ] = (char)tolower( (unsigned char)n[ i ] );
	out[ i ] = 0;
}

static gripofs_t *GripOfsFor( const char *name, bool create )
{
	for ( int i = 0; i < g_numGripOfs; i++ )
		if ( !stricmp( g_gripOfs[ i ].model, name ) )
			return &g_gripOfs[ i ];
	if ( !create || g_numGripOfs >= 48 || !name[ 0 ] )
		return NULL;
	gripofs_t *g = &g_gripOfs[ g_numGripOfs++ ];
	snprintf( g->model, sizeof( g->model ), "%s", name );
	g->ofs[ 0 ] = g->ofs[ 1 ] = g->ofs[ 2 ] = 0.0f;
	return g;
}

static void GripAdjust( float ( *light )[ 3 ][ 4 ], const gun_t *gun, int weaponmodel, float *target )
{
	char name[ 32 ];
	GunShortName( weaponmodel, name, sizeof( name ) );
	const gripofs_t *g = GripOfsFor( name, false );
	float a = cl_fpbody_grip_fwd->value + ( g ? g->ofs[ 0 ] : 0.0f );
	float b = cl_fpbody_grip_side->value + ( g ? g->ofs[ 1 ] : 0.0f );
	float c = -cl_fpbody_grip_down->value + ( g ? g->ofs[ 2 ] : 0.0f );
	if ( a == 0.0f && b == 0.0f && c == 0.0f )
		return;
	float fw[ 3 ], up[ 3 ] = { 0.0f, 0.0f, 1.0f }, left[ 3 ];
	HandToWorldDir( light, g_skel.rHand, gun->axis, fw );
	if ( Normalize3( fw ) < 1e-3f )
		return;
	float d = Dot3( up, fw );
	for ( int i = 0; i < 3; i++ )
		up[ i ] -= fw[ i ] * d;
	if ( Normalize3( up ) < 1e-3f )
		return;
	Cross( up, fw, left );
	for ( int i = 0; i < 3; i++ )
		target[ i ] += fw[ i ] * a + left[ i ] * b + up[ i ] * c;
}

static void GripSave( void )
{
	char path[ 256 ];
	snprintf( path, sizeof( path ), "%s/fpbody_grips.cfg", gEngfuncs.pfnGetGameDirectory() );
	FILE *fp = fopen( path, "w" );
	if ( !fp )
	{
		gEngfuncs.Con_Printf( "fp_grip: couldn't write %s\n", path );
		return;
	}
	fprintf( fp, "// fpbody left-hand tuning per gun (fp_grip): forward, left, up\n" );
	for ( int i = 0; i < g_numGripOfs; i++ )
		fprintf( fp, "fp_grip_set %s %g %g %g\n", g_gripOfs[ i ].model, g_gripOfs[ i ].ofs[ 0 ],
				 g_gripOfs[ i ].ofs[ 1 ], g_gripOfs[ i ].ofs[ 2 ] );
	fclose( fp );
}

static void FP_GripSetCmd( void )
{
	if ( gEngfuncs.Cmd_Argc() < 5 )
		return;
	gripofs_t *g = GripOfsFor( gEngfuncs.Cmd_Argv( 1 ), true );
	if ( g )
		for ( int i = 0; i < 3; i++ )
			g->ofs[ i ] = (float)atof( gEngfuncs.Cmd_Argv( 2 + i ) );
}

static void FP_GripCmd( void )
{
	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	char name[ 32 ];
	GunShortName( local ? local->curstate.weaponmodel : 0, name, sizeof( name ) );
	if ( !name[ 0 ] )
	{
		gEngfuncs.Con_Printf( "fp_grip: no gun in your hands\n" );
		return;
	}
	int argc = gEngfuncs.Cmd_Argc();
	if ( argc >= 2 && !stricmp( gEngfuncs.Cmd_Argv( 1 ), "reset" ) )
	{
		gripofs_t *g = GripOfsFor( name, false );
		if ( g )
			g->ofs[ 0 ] = g->ofs[ 1 ] = g->ofs[ 2 ] = 0.0f;
		GripSave();
		gEngfuncs.Con_Printf( "fp_grip: %s back to its default\n", name );
		return;
	}
	if ( argc >= 2 )
	{
		gripofs_t *g = GripOfsFor( name, true );
		if ( g )
		{
			for ( int i = 0; i < 3; i++ )
				g->ofs[ i ] = argc > 1 + i ? (float)atof( gEngfuncs.Cmd_Argv( 1 + i ) ) : 0.0f;
			GripSave();
		}
	}
	const gripofs_t *g = GripOfsFor( name, false );
	gEngfuncs.Con_Printf( "fp_grip %s: forward %g  left %g  up %g   (usage: fp_grip <forward> <left> <up>, negatives go back / right / down; fp_grip reset)\n",
		name, g ? g->ofs[ 0 ] : 0.0f, g ? g->ofs[ 1 ] : 0.0f, g ? g->ofs[ 2 ] : 0.0f );
}

// ---------------------------------------------------------------------------
// The gun in the hand (fp_gun / fp_gun_relax): moves and turns the held weapon
// model about the gun hand - forward along the barrel, left, up, then pitch
// (muzzle up +), yaw (muzzle left +), roll (+ = clockwise as you look down the
// barrel). fp_gun_relax is used instead while the gun is lowered (at ease),
// blended in and out with it. Saved per gun in <game>/fpbody_guns.cfg.
// ---------------------------------------------------------------------------
struct gunofs_t { char model[ 32 ]; float ofs[ 6 ]; float rel[ 6 ]; bool hasRel; float hand[ 6 ]; bool hasHand; float lhand[ 3 ]; bool hasLHand; float fingers[ 4 ]; bool hasFingers; float hold[ 3 ]; bool hasHold; };
static gunofs_t g_gunOfs[ 48 ];
static int g_numGunOfs;

static gunofs_t *GunOfsFor( const char *name, bool create )
{
	for ( int i = 0; i < g_numGunOfs; i++ )
		if ( !stricmp( g_gunOfs[ i ].model, name ) )
			return &g_gunOfs[ i ];
	if ( !create || g_numGunOfs >= 48 || !name[ 0 ] )
		return NULL;
	gunofs_t *g = &g_gunOfs[ g_numGunOfs++ ];
	memset( g, 0, sizeof( *g ) );
	snprintf( g->model, sizeof( g->model ), "%s", name );
	return g;
}

static void GunSave( void )
{
	char path[ 256 ];
	snprintf( path, sizeof( path ), "%s/fpbody_guns.cfg", gEngfuncs.pfnGetGameDirectory() );
	FILE *fp = fopen( path, "w" );
	if ( !fp )
	{
		gEngfuncs.Con_Printf( "fp_gun: couldn't write %s\n", path );
		return;
	}
	fprintf( fp, "// fpbody gun-in-hand tuning (fp_gun / fp_gun_relax): forward left up pitch yaw roll\n" );
	for ( int i = 0; i < g_numGunOfs; i++ )
	{
		const float *o = g_gunOfs[ i ].ofs, *r = g_gunOfs[ i ].rel;
		fprintf( fp, "fp_gun_set %s %g %g %g %g %g %g\n", g_gunOfs[ i ].model, o[ 0 ], o[ 1 ], o[ 2 ], o[ 3 ], o[ 4 ], o[ 5 ] );
		if ( g_gunOfs[ i ].hasRel )
			fprintf( fp, "fp_gun_relax_set %s %g %g %g %g %g %g\n", g_gunOfs[ i ].model, r[ 0 ], r[ 1 ], r[ 2 ], r[ 3 ], r[ 4 ], r[ 5 ] );
		const float *h = g_gunOfs[ i ].hand, *l = g_gunOfs[ i ].lhand;
		if ( g_gunOfs[ i ].hasHand )
			fprintf( fp, "fp_relax_hand_set %s %g %g %g %g %g %g\n", g_gunOfs[ i ].model, h[ 0 ], h[ 1 ], h[ 2 ], h[ 3 ], h[ 4 ], h[ 5 ] );
		if ( g_gunOfs[ i ].hasLHand )
			fprintf( fp, "fp_relax_lhand_set %s %g %g %g\n", g_gunOfs[ i ].model, l[ 0 ], l[ 1 ], l[ 2 ] );
		const float *fg = g_gunOfs[ i ].fingers;
		if ( g_gunOfs[ i ].hasFingers )
			fprintf( fp, "fp_fingers_set %s %g %g %g %g\n", g_gunOfs[ i ].model, fg[ 0 ], fg[ 1 ], fg[ 2 ], fg[ 3 ] );
		const float *hd = g_gunOfs[ i ].hold;
		if ( g_gunOfs[ i ].hasHold )
			fprintf( fp, "fp_hold_set %s %g %g %g\n", g_gunOfs[ i ].model, hd[ 0 ], hd[ 1 ], hd[ 2 ] );
	}
	fclose( fp );
}

static void GunSetFrom( float *dst, int first )
{
	int argc = gEngfuncs.Cmd_Argc();
	for ( int i = 0; i < 6; i++ )
		dst[ i ] = argc > first + i ? (float)atof( gEngfuncs.Cmd_Argv( first + i ) ) : 0.0f;
}

static void FP_GunSetCmd( void )
{
	if ( gEngfuncs.Cmd_Argc() < 3 )
		return;
	gunofs_t *g = GunOfsFor( gEngfuncs.Cmd_Argv( 1 ), true );
	if ( g )
		GunSetFrom( g->ofs, 2 );
}

static void FP_GunRelaxSetCmd( void )
{
	if ( gEngfuncs.Cmd_Argc() < 3 )
		return;
	gunofs_t *g = GunOfsFor( gEngfuncs.Cmd_Argv( 1 ), true );
	if ( g )
	{
		GunSetFrom( g->rel, 2 );
		g->hasRel = true;
	}
}

// The ready hold (GMod mode, two-handed guns): both arms and the gun turned
// down / to the right about the shoulders and pulled back, so a gun held up at
// the eyes doesn't fill the view; it comes up to the sights while you fire.
// fp_hold <down degrees> <right degrees> <back units> for the gun in your hands
// (fp_hold reset: back to cl_fpbody_holdlower), saved in fpbody_guns.cfg.
static void FP_HoldSetCmd( void )
{
	if ( gEngfuncs.Cmd_Argc() < 3 )
		return;
	gunofs_t *g = GunOfsFor( gEngfuncs.Cmd_Argv( 1 ), true );
	if ( !g )
		return;
	for ( int i = 0; i < 3; i++ )
		g->hold[ i ] = gEngfuncs.Cmd_Argc() > 2 + i ? (float)atof( gEngfuncs.Cmd_Argv( 2 + i ) ) : 0.0f;
	g->hasHold = true;
}

static void FP_HoldCmd( void )
{
	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	char name[ 32 ];
	GunShortName( local ? local->curstate.weaponmodel : 0, name, sizeof( name ) );
	if ( !name[ 0 ] )
	{
		gEngfuncs.Con_Printf( "fp_hold: nothing in your hands\n" );
		return;
	}
	int argc = gEngfuncs.Cmd_Argc();
	if ( argc >= 2 && !stricmp( gEngfuncs.Cmd_Argv( 1 ), "reset" ) )
	{
		gunofs_t *g = GunOfsFor( name, false );
		if ( g )
			g->hasHold = false;
		GunSave();
	}
	else if ( argc >= 2 )
	{
		gunofs_t *g = GunOfsFor( name, true );
		if ( g )
		{
			for ( int i = 0; i < 3; i++ )
				g->hold[ i ] = argc > 1 + i ? (float)atof( gEngfuncs.Cmd_Argv( 1 + i ) ) : 0.0f;
			g->hasHold = true;
			GunSave();
		}
	}
	const gunofs_t *g = GunOfsFor( name, false );
	if ( g && g->hasHold )
		gEngfuncs.Con_Printf( "fp_hold %s: down %g  right %g  back %g   (usage: fp_hold <down> <right> <back>; fp_hold reset)\n",
			name, g->hold[ 0 ], g->hold[ 1 ], g->hold[ 2 ] );
	else
		gEngfuncs.Con_Printf( "fp_hold %s: default (down %g from cl_fpbody_holdlower)   (usage: fp_hold <down> <right> <back>; fp_hold reset)\n",
			name, cl_fpbody_holdlower ? cl_fpbody_holdlower->value : 0.0f );
}

static void GunCmd( bool relax )
{
	const char *cmd = relax ? "fp_gun_relax" : "fp_gun";
	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	char name[ 32 ];
	GunShortName( local ? local->curstate.weaponmodel : 0, name, sizeof( name ) );
	if ( !name[ 0 ] )
	{
		gEngfuncs.Con_Printf( "%s: nothing in your hands\n", cmd );
		return;
	}
	int argc = gEngfuncs.Cmd_Argc();
	if ( argc >= 2 )
	{
		gunofs_t *g = GunOfsFor( name, true );
		if ( g && !stricmp( gEngfuncs.Cmd_Argv( 1 ), "reset" ) )
		{
			if ( relax )
			{
				memset( g->rel, 0, sizeof( g->rel ) );
				g->hasRel = false;
			}
			else
				memset( g->ofs, 0, sizeof( g->ofs ) );
		}
		else if ( g )
		{
			GunSetFrom( relax ? g->rel : g->ofs, 1 );
			if ( relax )
				g->hasRel = true;
		}
		GunSave();
	}
	const gunofs_t *g = GunOfsFor( name, false );
	const float *o = g ? ( relax ? g->rel : g->ofs ) : NULL;
	gEngfuncs.Con_Printf( "%s %s: forward %g left %g up %g  pitch %g yaw %g roll %g%s\n", cmd, name,
		o ? o[ 0 ] : 0.0f, o ? o[ 1 ] : 0.0f, o ? o[ 2 ] : 0.0f, o ? o[ 3 ] : 0.0f, o ? o[ 4 ] : 0.0f, o ? o[ 5 ] : 0.0f,
		relax && g && !g->hasRel ? " (not set: the normal fp_gun values are used)" : "" );
	gEngfuncs.Con_Printf( "  usage: %s <forward> <left> <up> [pitch yaw roll]   (negatives: back / right / down); %s reset\n", cmd, cmd );
}
static void FP_GunCmd( void ) { GunCmd( false ); }
static void FP_GunRelaxCmd( void ) { GunCmd( true ); }

void FPAnim_AdjustWeapon( void *studiohdr, float ( *bt )[ 3 ][ 4 ], float ( *lt )[ 3 ][ 4 ], struct model_s *weapon, int entindex )
{
	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	if ( !studiohdr || !weapon || !local || entindex != local->index || !FPBody_Active() )
		return;
	char name[ 32 ];
	{
		const char *n = weapon->name, *sl = strrchr( n, '/' );
		if ( sl )
			n = sl + 1;
		int i = 0;
		for ( ; n[ i ] && n[ i ] != '.' && i < 31; i++ )
			name[ i ] = (char)tolower( (unsigned char)n[ i ] );
		name[ i ] = 0;
	}
	const gunofs_t *g = GunOfsFor( name, false );
	if ( !g )
		return;
	float o[ 6 ];
	float w = g->hasRel ? Clamp01( g_relaxW ) : 0.0f;
	bool any = false;
	for ( int i = 0; i < 6; i++ )
	{
		o[ i ] = g->ofs[ i ] * ( 1.0f - w ) + g->rel[ i ] * w;
		if ( o[ i ] != 0.0f )
			any = true;
	}
	if ( !any )
		return;

	// the gun hand, as merged from the body
	const studiohdr_t *hdr = (const studiohdr_t *)studiohdr;
	const mstudiobone_t *bones = (const mstudiobone_t *)( (const byte *)hdr + hdr->boneindex );
	int hand = -1;
	for ( int i = 0; i < hdr->numbones; i++ )
		if ( !stricmp( bones[ i ].name, "Bip01 R Hand" ) )
		{
			hand = i;
			break;
		}
	if ( hand < 0 )
		return;

	// frame: forward = the barrel (or the hand's length for melee), left, up
	float fw[ 3 ], ax[ 3 ] = { 1.0f, 0.0f, 0.0f };
	char want[ 40 ];
	for ( int i = 0; i < (int)( sizeof( g_guns ) / sizeof( g_guns[ 0 ] ) ); i++ )
	{
		snprintf( want, sizeof( want ), "%s", g_guns[ i ].model );
		if ( !stricmp( want, name ) )
		{
			ax[ 0 ] = g_guns[ i ].axis[ 0 ]; ax[ 1 ] = g_guns[ i ].axis[ 1 ]; ax[ 2 ] = g_guns[ i ].axis[ 2 ];
			break;
		}
	}
	for ( int r = 0; r < 3; r++ )
		fw[ r ] = bt[ hand ][ r ][ 0 ] * ax[ 0 ] + bt[ hand ][ r ][ 1 ] * ax[ 1 ] + bt[ hand ][ r ][ 2 ] * ax[ 2 ];
	if ( Normalize3( fw ) < 1e-3f )
		return;
	float up[ 3 ] = { 0.0f, 0.0f, 1.0f }, left[ 3 ];
	float d = Dot3( up, fw );
	for ( int i = 0; i < 3; i++ )
		up[ i ] -= fw[ i ] * d;
	if ( Normalize3( up ) < 1e-3f )
	{
		up[ 0 ] = 1.0f; up[ 1 ] = 0.0f; up[ 2 ] = 0.0f;
		d = Dot3( up, fw );
		for ( int i = 0; i < 3; i++ )
			up[ i ] -= fw[ i ] * d;
		Normalize3( up );
	}
	Cross( up, fw, left );

	// rotation: roll about the barrel, then pitch about left (muzzle up), yaw about up
	mat3_t Rr, Rp, Ry, T1, R;
	AxisAngle( fw, o[ 5 ], Rr );
	AxisAngle( left, -o[ 3 ], Rp );
	AxisAngle( up, o[ 4 ], Ry );
	for ( int a = 0; a < 3; a++ )
		for ( int b = 0; b < 3; b++ )
			T1[ a ][ b ] = Rp[ a ][ 0 ] * Rr[ 0 ][ b ] + Rp[ a ][ 1 ] * Rr[ 1 ][ b ] + Rp[ a ][ 2 ] * Rr[ 2 ][ b ];
	for ( int a = 0; a < 3; a++ )
		for ( int b = 0; b < 3; b++ )
			R[ a ][ b ] = Ry[ a ][ 0 ] * T1[ 0 ][ b ] + Ry[ a ][ 1 ] * T1[ 1 ][ b ] + Ry[ a ][ 2 ] * T1[ 2 ][ b ];
	float pivot[ 3 ] = { bt[ hand ][ 0 ][ 3 ], bt[ hand ][ 1 ][ 3 ], bt[ hand ][ 2 ][ 3 ] };
	float t[ 3 ];
	for ( int i = 0; i < 3; i++ )
		t[ i ] = fw[ i ] * o[ 0 ] + left[ i ] * o[ 1 ] + up[ i ] * o[ 2 ];

	for ( int pass = 0; pass < 2; pass++ )
	{
		float ( *m )[ 3 ][ 4 ] = pass ? lt : bt;
		if ( pass && lt == bt )
			break;
		for ( int bi = 0; bi < hdr->numbones; bi++ )
		{
			float n[ 3 ][ 4 ];
			for ( int a = 0; a < 3; a++ )
			{
				for ( int b = 0; b < 3; b++ )
					n[ a ][ b ] = R[ a ][ 0 ] * m[ bi ][ 0 ][ b ] + R[ a ][ 1 ] * m[ bi ][ 1 ][ b ] + R[ a ][ 2 ] * m[ bi ][ 2 ][ b ];
				float pa = m[ bi ][ 0 ][ 3 ] - pivot[ 0 ], pb = m[ bi ][ 1 ][ 3 ] - pivot[ 1 ], pc = m[ bi ][ 2 ][ 3 ] - pivot[ 2 ];
				n[ a ][ 3 ] = R[ a ][ 0 ] * pa + R[ a ][ 1 ] * pb + R[ a ][ 2 ] * pc + pivot[ a ] + t[ a ];
			}
			memcpy( m[ bi ], n, sizeof( n ) );
		}
	}
}

// fp_relax_hand / fp_relax_lhand: where the gun hand / the other hand go in the
// lowered (at ease) hold, per gun: forward / left / up from where the animation
// puts them (in the body's facing), and for the gun hand a turn of the wrist
// (pitch: fingers up +, yaw: fingers left +, roll). Blended in with the hold.
static void FP_RelaxSetCmd( bool left )
{
	if ( gEngfuncs.Cmd_Argc() < 3 )
		return;
	gunofs_t *g = GunOfsFor( gEngfuncs.Cmd_Argv( 1 ), true );
	if ( !g )
		return;
	if ( left )
	{
		float t[ 6 ];
		GunSetFrom( t, 2 );
		memcpy( g->lhand, t, sizeof( g->lhand ) );
		g->hasLHand = true;
	}
	else
	{
		GunSetFrom( g->hand, 2 );
		g->hasHand = true;
	}
}
static void FP_RelaxHandSetCmd( void ) { FP_RelaxSetCmd( false ); }
static void FP_RelaxLHandSetCmd( void ) { FP_RelaxSetCmd( true ); }

static void RelaxCmd( bool left )
{
	const char *cmd = left ? "fp_relax_lhand" : "fp_relax_hand";
	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	char name[ 32 ];
	GunShortName( local ? local->curstate.weaponmodel : 0, name, sizeof( name ) );
	if ( !name[ 0 ] )
	{
		gEngfuncs.Con_Printf( "%s: nothing in your hands\n", cmd );
		return;
	}
	int argc = gEngfuncs.Cmd_Argc();
	if ( argc >= 2 )
	{
		gunofs_t *g = GunOfsFor( name, true );
		if ( g && !stricmp( gEngfuncs.Cmd_Argv( 1 ), "reset" ) )
		{
			if ( left ) { memset( g->lhand, 0, sizeof( g->lhand ) ); g->hasLHand = false; }
			else { memset( g->hand, 0, sizeof( g->hand ) ); g->hasHand = false; }
		}
		else if ( g )
		{
			float t[ 6 ];
			GunSetFrom( t, 1 );
			if ( left ) { memcpy( g->lhand, t, sizeof( g->lhand ) ); g->hasLHand = true; }
			else { memcpy( g->hand, t, sizeof( g->hand ) ); g->hasHand = true; }
		}
		GunSave();
	}
	const gunofs_t *g = GunOfsFor( name, false );
	if ( left )
		gEngfuncs.Con_Printf( "%s %s: forward %g left %g up %g\n  usage: %s <forward> <left> <up>   (negatives: back / right / down); %s reset\n",
			cmd, name, g ? g->lhand[ 0 ] : 0.0f, g ? g->lhand[ 1 ] : 0.0f, g ? g->lhand[ 2 ] : 0.0f, cmd, cmd );
	else
		gEngfuncs.Con_Printf( "%s %s: forward %g left %g up %g  pitch %g yaw %g roll %g\n  usage: %s <forward> <left> <up> [pitch yaw roll]   (negatives: back / right / down); %s reset\n",
			cmd, name, g ? g->hand[ 0 ] : 0.0f, g ? g->hand[ 1 ] : 0.0f, g ? g->hand[ 2 ] : 0.0f,
			g ? g->hand[ 3 ] : 0.0f, g ? g->hand[ 4 ] : 0.0f, g ? g->hand[ 5 ] : 0.0f, cmd, cmd );
	gEngfuncs.Con_Printf( "  (only while the gun is lowered: press your lower-weapon key to see it)\n" );
}
static void FP_RelaxHandCmd( void ) { RelaxCmd( false ); }
static void FP_RelaxLHandCmd( void ) { RelaxCmd( true ); }

static void ApplyRelaxHands( float ( *bone )[ 3 ][ 4 ], float ( *light )[ 3 ][ 4 ], int weaponmodel, const float *f )
{
	float w = Clamp01( g_relaxW );
	if ( w < 0.01f )
		return;
	char name[ 32 ];
	GunShortName( weaponmodel, name, sizeof( name ) );
	const gunofs_t *g = GunOfsFor( name, false );
	if ( !g || ( !g->hasHand && !g->hasLHand ) )
		return;
	// the body's facing, level
	float fh[ 3 ] = { f[ 0 ], f[ 1 ], 0.0f }, up[ 3 ] = { 0.0f, 0.0f, 1.0f }, lf[ 3 ];
	if ( Normalize3( fh ) < 1e-3f )
		return;
	Cross( up, fh, lf );
	if ( g->hasHand && g_skel.rHand >= 0 )
	{
		float H[ 3 ], target[ 3 ];
		BoneOrigin( light, g_skel.rHand, H );
		for ( int i = 0; i < 3; i++ )
			target[ i ] = H[ i ] + ( fh[ i ] * g->hand[ 0 ] + lf[ i ] * g->hand[ 1 ] + up[ i ] * g->hand[ 2 ] ) * w;
		ReachArm( bone, light, target, 1.0f, true, 0.0f );
		if ( g->hand[ 3 ] != 0.0f || g->hand[ 4 ] != 0.0f || g->hand[ 5 ] != 0.0f )
		{
			mat3_t Rr, Rp, Ry, T1, R;
			AxisAngle( fh, g->hand[ 5 ] * w, Rr );
			AxisAngle( lf, -g->hand[ 3 ] * w, Rp );
			AxisAngle( up, g->hand[ 4 ] * w, Ry );
			for ( int a = 0; a < 3; a++ )
				for ( int b = 0; b < 3; b++ )
					T1[ a ][ b ] = Rp[ a ][ 0 ] * Rr[ 0 ][ b ] + Rp[ a ][ 1 ] * Rr[ 1 ][ b ] + Rp[ a ][ 2 ] * Rr[ 2 ][ b ];
			for ( int a = 0; a < 3; a++ )
				for ( int b = 0; b < 3; b++ )
					R[ a ][ b ] = Ry[ a ][ 0 ] * T1[ 0 ][ b ] + Ry[ a ][ 1 ] * T1[ 1 ][ b ] + Ry[ a ][ 2 ] * T1[ 2 ][ b ];
			BoneOrigin( light, g_skel.rHand, H );
			TransformBones( bone, light, g_skel.rHandMask, R, H, NULL );
		}
	}
	if ( g->hasLHand && g_skel.lHand >= 0 )
	{
		float H[ 3 ], target[ 3 ];
		BoneOrigin( light, g_skel.lHand, H );
		for ( int i = 0; i < 3; i++ )
			target[ i ] = H[ i ] + ( fh[ i ] * g->lhand[ 0 ] + lf[ i ] * g->lhand[ 1 ] + up[ i ] * g->lhand[ 2 ] ) * w;
		ReachArm( bone, light, target, 1.0f, false, 0.0f );
	}
}

// ---------------------------------------------------------------------------
// Fingers round the gun: extra curl of the fingers / thumbs, in degrees per
// joint (+ = closed tighter, - = opened), on top of the hold's own. Built-in
// defaults per gun (the left hand that goes onto barrels and pumps closes round
// them), plus fp_fingers per gun: right fingers, left fingers, right thumb,
// left thumb.
// ---------------------------------------------------------------------------
struct fingerdef_t { const char *model; float curl[ 4 ]; };
static const fingerdef_t g_fingerDefs[] =
{
	// two-handed guns: the left hand wraps the barrel / pump / handle
	{ "p_9mmar",          { 0.0f, 25.0f, 0.0f, 15.0f } },
	{ "p_shotgun",        { 0.0f, 25.0f, 0.0f, 15.0f } },
	{ "p_crossbow",       { 0.0f, 25.0f, 0.0f, 15.0f } },
	{ "p_rpg",            { 0.0f, 25.0f, 0.0f, 15.0f } },
	{ "p_gauss",          { 0.0f, 30.0f, 0.0f, 15.0f } },
	{ "p_egon",           { 0.0f, 30.0f, 0.0f, 15.0f } },
	{ "p_hgun",           { 0.0f, 15.0f, 0.0f, 10.0f } },
	{ "p_saw",            { 0.0f, 25.0f, 0.0f, 15.0f } },
	{ "p_m40a1",          { 0.0f, 25.0f, 0.0f, 15.0f } },
	{ "p_shock",          { 0.0f, 25.0f, 0.0f, 15.0f } },
	{ "p_spore_launcher", { 0.0f, 25.0f, 0.0f, 15.0f } },
	{ "p_displacer",      { 0.0f, 30.0f, 0.0f, 15.0f } },
};
static float g_fingerRW, g_fingerLW;

static void FP_FingersSetCmd( void )
{
	if ( gEngfuncs.Cmd_Argc() < 3 )
		return;
	gunofs_t *g = GunOfsFor( gEngfuncs.Cmd_Argv( 1 ), true );
	if ( !g )
		return;
	float t[ 6 ];
	GunSetFrom( t, 2 );
	memcpy( g->fingers, t, sizeof( g->fingers ) );
	g->hasFingers = true;
}

static void FP_FingersCmd( void )
{
	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	char name[ 32 ];
	GunShortName( local ? local->curstate.weaponmodel : 0, name, sizeof( name ) );
	if ( !name[ 0 ] )
	{
		gEngfuncs.Con_Printf( "fp_fingers: nothing in your hands\n" );
		return;
	}
	if ( gEngfuncs.Cmd_Argc() >= 2 )
	{
		gunofs_t *g = GunOfsFor( name, true );
		if ( g && !stricmp( gEngfuncs.Cmd_Argv( 1 ), "reset" ) )
		{
			memset( g->fingers, 0, sizeof( g->fingers ) );
			g->hasFingers = false;
		}
		else if ( g )
		{
			float t[ 6 ];
			GunSetFrom( t, 1 );
			memcpy( g->fingers, t, sizeof( g->fingers ) );
			g->hasFingers = true;
		}
		GunSave();
	}
	const gunofs_t *g = GunOfsFor( name, false );
	float def[ 4 ] = { 0, 0, 0, 0 };
	for ( int i = 0; i < (int)( sizeof( g_fingerDefs ) / sizeof( g_fingerDefs[ 0 ] ) ); i++ )
		if ( !stricmp( g_fingerDefs[ i ].model, name ) )
			memcpy( def, g_fingerDefs[ i ].curl, sizeof( def ) );
	const float *o = g && g->hasFingers ? g->fingers : NULL;
	gEngfuncs.Con_Printf( "fp_fingers %s: right fingers %g  left fingers %g  right thumb %g  left thumb %g   (built in: %g %g %g %g, yours add to them)\n",
		name, o ? o[ 0 ] : 0.0f, o ? o[ 1 ] : 0.0f, o ? o[ 2 ] : 0.0f, o ? o[ 3 ] : 0.0f, def[ 0 ], def[ 1 ], def[ 2 ], def[ 3 ] );
	gEngfuncs.Con_Printf( "  usage: fp_fingers <right> <left> [right thumb] [left thumb]   (degrees per joint: + closes, - opens); fp_fingers reset\n" );
}

static void CurlChain( float ( *bone )[ 3 ][ 4 ], float ( *light )[ 3 ][ 4 ], const char *const *names, int axisCol, float axisSign, float deg )
{
	if ( deg == 0.0f || !g_skel.hdr )
		return;
	const mstudiobone_t *bones = (const mstudiobone_t *)( (const byte *)g_skel.hdr + g_skel.hdr->boneindex );
	int num = g_skel.numbones;
	for ( int k = 0; k < 3; k++ )
	{
		int b = FindBone( bones, num, names[ k ], NULL );
		if ( b < 0 )
			return;
		static bool mask[ MAXSTUDIOBONES ];
		for ( int i = 0; i < num; i++ )
		{
			int j = i;
			while ( j >= 0 && j != b )
				j = bones[ j ].parent;
			mask[ i ] = ( j == b );
		}
		float axis[ 3 ] = { light[ b ][ 0 ][ axisCol ] * axisSign, light[ b ][ 1 ][ axisCol ] * axisSign, light[ b ][ 2 ][ axisCol ] * axisSign };
		if ( Normalize3( axis ) < 1e-3f )
			return;
		float pivot[ 3 ];
		BoneOrigin( light, b, pivot );
		mat3_t W;
		AxisAngle( axis, deg, W );
		TransformBones( bone, light, mask, W, pivot, NULL );
	}
}

static void ApplyFingers( float ( *bone )[ 3 ][ 4 ], float ( *light )[ 3 ][ 4 ], int weaponmodel )
{
	char name[ 32 ];
	GunShortName( weaponmodel, name, sizeof( name ) );
	float curl[ 4 ] = { 0, 0, 0, 0 };
	if ( name[ 0 ] && ( !cl_fpbody_fingers || cl_fpbody_fingers->value != 0.0f ) )
	{
		for ( int i = 0; i < (int)( sizeof( g_fingerDefs ) / sizeof( g_fingerDefs[ 0 ] ) ); i++ )
			if ( !stricmp( g_fingerDefs[ i ].model, name ) )
				for ( int k = 0; k < 4; k++ )
					curl[ k ] = g_fingerDefs[ i ].curl[ k ];
		const gunofs_t *g = GunOfsFor( name, false );
		if ( g && g->hasFingers )
			for ( int k = 0; k < 4; k++ )
				curl[ k ] += g->fingers[ k ];
	}
	// the gun hand: while holding the gun (not in a move or reload); the other
	// hand: as far as it is on the gun
	float rTarget = ( name[ 0 ] && g_ovSeq < 0 ) ? 1.0f : 0.0f;
	g_fingerRW += ( rTarget - g_fingerRW ) * Clamp01( g_frameTime * 8.0f );
	g_fingerLW = Clamp01( g_offW );
	static const char *rf[] = { "Bip01 R Finger1", "Bip01 R Finger11", "Bip01 R Finger12" };
	static const char *lf[] = { "Bip01 L Finger1", "Bip01 L Finger11", "Bip01 L Finger12" };
	static const char *rt[] = { "Bip01 R Finger0", "Bip01 R Finger01", "Bip01 R Finger02" };
	static const char *lt[] = { "Bip01 L Finger0", "Bip01 L Finger01", "Bip01 L Finger02" };
	// fingers bend about their bone's z axis; the thumbs about y (mirrored)
	CurlChain( bone, light, rf, 2, 1.0f, curl[ 0 ] * g_fingerRW );
	CurlChain( bone, light, lf, 2, 1.0f, curl[ 1 ] * g_fingerLW );
	CurlChain( bone, light, rt, 1, 1.0f, curl[ 2 ] * g_fingerRW );
	CurlChain( bone, light, lt, 1, -1.0f, curl[ 3 ] * g_fingerLW );
}

// The playermodels' animations roll the hand up to ~130 degrees about the
// forearm (gun holds); in Source the forearm's twist bones roll the wrist half
// of the forearm with it. Half-Life binds every vertex to one bone, so the
// forearm stayed put and the wrist looked wrung, flattened to a spike. Roll the
// forearm (that bone alone, about its own length) by a share of the hand's roll:
// the twist is split between the wrist and the elbow.
static void ShareWristTwist( float ( *bone )[ 3 ][ 4 ], float ( *light )[ 3 ][ 4 ], int fore, int hand, float share )
{
	if ( fore < 0 || hand < 0 || share <= 0.0f || !g_skel.hdr )
		return;
	const mstudiobone_t *bones = (const mstudiobone_t *)( (const byte *)g_skel.hdr + g_skel.hdr->boneindex );
	if ( bones[ hand ].parent != fore )
		return;
	// the hand's rest rotation in the forearm's frame (Rz * Ry * Rx of its angles)
	const float *v = bones[ hand ].value;
	float ca = (float)cos( v[ 3 ] ), sa = (float)sin( v[ 3 ] ), cb = (float)cos( v[ 4 ] ), sb = (float)sin( v[ 4 ] );
	float cc = (float)cos( v[ 5 ] ), sc = (float)sin( v[ 5 ] );
	mat3_t rest = {
		{ cc * cb, cc * sb * sa - sc * ca, cc * sb * ca + sc * sa },
		{ sc * cb, sc * sb * sa + cc * ca, sc * sb * ca - cc * sa },
		{ -sb, cb * sa, cb * ca } };
	float ax[ 3 ] = { v[ 0 ], v[ 1 ], v[ 2 ] };	// the forearm's length, in its frame
	if ( Normalize3( ax ) < 1e-3f )
		return;
	// now: the hand in the forearm's frame, against its rest: d = (Rf^T Rh) rest^T
	mat3_t rel, d;
	for ( int i = 0; i < 3; i++ )
		for ( int j = 0; j < 3; j++ )
			rel[ i ][ j ] = light[ fore ][ 0 ][ i ] * light[ hand ][ 0 ][ j ] + light[ fore ][ 1 ][ i ] * light[ hand ][ 1 ][ j ] +
							light[ fore ][ 2 ][ i ] * light[ hand ][ 2 ][ j ];
	for ( int i = 0; i < 3; i++ )
		for ( int j = 0; j < 3; j++ )
			d[ i ][ j ] = rel[ i ][ 0 ] * rest[ j ][ 0 ] + rel[ i ][ 1 ] * rest[ j ][ 1 ] + rel[ i ][ 2 ] * rest[ j ][ 2 ];
	// its roll about the forearm: how far a line across the forearm turns
	float pp[ 3 ] = { 0.0f, 0.0f, 0.0f };
	pp[ fabs( ax[ 0 ] ) < 0.8f ? 0 : 1 ] = 1.0f;
	float k = Dot3( pp, ax );
	for ( int i = 0; i < 3; i++ )
		pp[ i ] -= ax[ i ] * k;
	Normalize3( pp );
	float q[ 3 ];
	for ( int i = 0; i < 3; i++ )
		q[ i ] = d[ i ][ 0 ] * pp[ 0 ] + d[ i ][ 1 ] * pp[ 1 ] + d[ i ][ 2 ] * pp[ 2 ];
	k = Dot3( q, ax );
	for ( int i = 0; i < 3; i++ )
		q[ i ] -= ax[ i ] * k;
	if ( Normalize3( q ) < 1e-3f )
		return;
	float cr[ 3 ];
	Cross( pp, q, cr );
	float twist = (float)( atan2( Dot3( cr, ax ), Dot3( pp, q ) ) * 180.0 / M_PI );
	float wax[ 3 ], pivot[ 3 ];
	for ( int i = 0; i < 3; i++ )
		wax[ i ] = light[ fore ][ i ][ 0 ] * ax[ 0 ] + light[ fore ][ i ][ 1 ] * ax[ 1 ] + light[ fore ][ i ][ 2 ] * ax[ 2 ];
	if ( Normalize3( wax ) < 1e-3f )
		return;
	BoneOrigin( light, fore, pivot );
	static bool mask[ MAXSTUDIOBONES ];
	memset( mask, 0, sizeof( mask ) );
	mask[ fore ] = true;
	mat3_t W;
	AxisAngle( wax, twist * Clamp01( share ), W );
	TransformBones( bone, light, mask, W, pivot, NULL );
}

// Garry's Mod's shotgun pump (its "shotgun_pump" layer: the left hand slides
// back along the barrel and forward again), on the pump after a reload
static void PumpStroke( float ( *light )[ 3 ][ 4 ], const gun_t *gun, float now, float *target )
{
	if ( g_cur.type != CLIP_PUMP || g_cur.dur <= 0.0f || now < g_cur.start || now > g_cur.start + g_cur.dur ||
		 g_skel.rHand < 0 || ( cl_fpbody_pump && cl_fpbody_pump->value <= 0.0f ) )
		return;
	float t = ( now - g_cur.start ) / g_cur.dur;
	// back quickly, a moment at the end of the stroke, forward again
	float k = t < 0.4f ? Smooth( t / 0.4f ) : t < 0.55f ? 1.0f : 1.0f - Smooth( ( t - 0.55f ) / 0.4f );
	if ( k <= 0.0f )
		return;
	float barrel[ 3 ];
	HandToWorldDir( light, g_skel.rHand, gun->axis, barrel );
	if ( Normalize3( barrel ) < 1e-3f )
		return;
	float stroke = ( cl_fpbody_pump ? cl_fpbody_pump->value : 4.0f ) * k;
	for ( int i = 0; i < 3; i++ )
		target[ i ] -= barrel[ i ] * stroke;
}

// The off hand lets go of the gun while it is busy or the body does something
// of its own: any full-body / gesture animation (relaxed and at-ease holds,
// barnacle gagging, hard landings, rolls, draws), pressing use, the
// flashlight, ladders, being held by a barnacle, a hard landing's dip.
// cl_fpbody_offhand_release 0 keeps it on the gun through all of these.
static float MatAxisAngle( const mat3_t m, float *axis );

// +use: the left hand flat - palm down, fingers along the reach, thumb in -
// or flat on the panel of a charger (fingers up), whatever the gun's hold
// had it doing (a grip round a barrel turns the palm sideways)
static void UsePalm( float ( *bone )[ 3 ][ 4 ], float ( *light )[ 3 ][ 4 ], const float *f, const float *r,
	const float *u, float w, bool charger )
{
	int h = g_skel.lHand, th = g_skel.lThumb, fi = g_skel.lFinger;
	if ( h < 0 || th < 0 || fi < 0 || w <= 0.001f )
		return;
	float H[ 3 ], F[ 3 ], T[ 3 ];
	BoneOrigin( light, h, H );
	BoneOrigin( light, fi, F );
	BoneOrigin( light, th, T );
	for ( int i = 0; i < 3; i++ ) { F[ i ] -= H[ i ]; T[ i ] -= H[ i ]; }
	if ( Normalize3( F ) < 1e-3f )
		return;
	float d = Dot3( T, F );
	for ( int i = 0; i < 3; i++ ) T[ i ] -= F[ i ] * d;
	if ( Normalize3( T ) < 1e-3f )
		return;
	// wanted: fingers along the reach (level) or up for a charger, thumb to the right
	float wf[ 3 ], wt[ 3 ] = { r[ 0 ], r[ 1 ], r[ 2 ] };
	if ( charger )
		for ( int i = 0; i < 3; i++ ) wf[ i ] = u[ i ];
	else
	{
		for ( int i = 0; i < 3; i++ ) wf[ i ] = f[ i ];
		wf[ 2 ] *= 0.3f;							// keep it near level when looking up / down
		if ( Normalize3( wf ) < 1e-3f )
			return;
	}
	d = Dot3( wt, wf );
	for ( int i = 0; i < 3; i++ ) wt[ i ] -= wf[ i ] * d;
	if ( Normalize3( wt ) < 1e-3f )
		return;
	float N[ 3 ], wn[ 3 ];
	Cross( F, T, N );
	Cross( wf, wt, wn );
	// W = [wf wt wn] * [F T N]^T
	mat3_t W, R;
	for ( int a = 0; a < 3; a++ )
		for ( int b = 0; b < 3; b++ )
			W[ a ][ b ] = wf[ a ] * F[ b ] + wt[ a ] * T[ b ] + wn[ a ] * N[ b ];
	float axis[ 3 ];
	float ang = MatAxisAngle( W, axis ) * Clamp01( w );
	if ( ang < 0.2f )
		return;
	AxisAngle( axis, ang, R );
	TransformBones( bone, light, g_skel.lHandMask, R, H, NULL );
}

static bool OffHandBusy( float now )
{
	if ( g_ovSeq >= 0 )
		return true;
	if ( cl_fpbody_offhand_release && cl_fpbody_offhand_release->value == 0.0f )
		return false;
	// (a moment ago: never a time still to come, which is a clock that restarted)
	#define FP_RECENT( t, d ) ( now - ( t ) >= 0.0f && now - ( t ) < ( d ) )
	return g_relaxW > 0.02f ||
		   ( in_use.state & 1 ) || FP_RECENT( g_useStart, 0.7f ) || g_useHoldW > 0.02f ||
		   FP_RECENT( g_flashStart, 0.7f ) ||
		   g_ladderW > 0.02f ||
		   ( g_mvPrevState & FPM_BARNACLE ) ||
		   ( FP_RECENT( g_landStart, 0.7f ) && g_landStrength > 0.35f );
	#undef FP_RECENT
}

// rotation matrix -> unit axis and angle (degrees)
static float MatAxisAngle( const mat3_t m, float *axis )
{
	float c = Clamp( ( m[ 0 ][ 0 ] + m[ 1 ][ 1 ] + m[ 2 ][ 2 ] - 1.0f ) * 0.5f, -1.0f, 1.0f );
	float ang = (float)acos( c );
	axis[ 0 ] = m[ 2 ][ 1 ] - m[ 1 ][ 2 ];
	axis[ 1 ] = m[ 0 ][ 2 ] - m[ 2 ][ 0 ];
	axis[ 2 ] = m[ 1 ][ 0 ] - m[ 0 ][ 1 ];
	if ( Normalize3( axis ) < 1e-5f )
		return 0.0f;
	return ang * (float)( 180.0 / M_PI );
}

// Pistols: the left hand is held on the gun at a fixed place and angle in the
// gun hand's space, so it stays on the grip from every view angle. Taken from
// the hold animation while its left hand is on the gun (else from the gun's
// grip point), kept per gun.
static int g_pgModel = -1;
static bool g_pgHavePos, g_pgHaveRot;
static float g_pgPos[ 3 ];
static mat3_t g_pgRot;

static void PistolGripLatch( float ( *light )[ 3 ][ 4 ], const gun_t *gun, int weaponmodel, bool holding )
{
	if ( weaponmodel != g_pgModel )
	{
		g_pgModel = weaponmodel;
		g_pgHavePos = g_pgHaveRot = false;
	}
	int rh = g_skel.rHand, lh = g_skel.lHand;
	float d[ 3 ], rel[ 3 ];
	for ( int i = 0; i < 3; i++ )
		d[ i ] = light[ lh ][ i ][ 3 ] - light[ rh ][ i ][ 3 ];
	for ( int c = 0; c < 3; c++ )
		rel[ c ] = light[ rh ][ 0 ][ c ] * d[ 0 ] + light[ rh ][ 1 ][ c ] * d[ 1 ] + light[ rh ][ 2 ][ c ] * d[ 2 ];
	// the animation's own two-handed grip: follow it while its hand is on the gun
	if ( holding && Dot3( rel, rel ) < 8.0f * 8.0f )
	{
		for ( int i = 0; i < 3; i++ )
			g_pgPos[ i ] = rel[ i ];
		for ( int a = 0; a < 3; a++ )
			for ( int b = 0; b < 3; b++ )
				g_pgRot[ a ][ b ] = light[ rh ][ 0 ][ a ] * light[ lh ][ 0 ][ b ] + light[ rh ][ 1 ][ a ] * light[ lh ][ 1 ][ b ] +
									light[ rh ][ 2 ][ a ] * light[ lh ][ 2 ][ b ];
		g_pgHavePos = g_pgHaveRot = true;
	}
	else if ( !g_pgHavePos )
	{
		// no grip in the animation: the gun's grip point, with the drop below the
		// gun taken once (the world's down, seen from the gun hand now)
		for ( int c = 0; c < 3; c++ )
			g_pgPos[ c ] = gun->grip[ c ] - light[ rh ][ 2 ][ c ] * gun->down;
		g_pgHavePos = true;
	}
}

// after the arm has reached: turn the left hand to its held angle on the gun
static void PistolGripTurn( float ( *bone )[ 3 ][ 4 ], float ( *light )[ 3 ][ 4 ], float w )
{
	int rh = g_skel.rHand, lh = g_skel.lHand;
	if ( !g_pgHaveRot )
	{
		// first frame fully on the gun: keep the angle the reach left it at
		if ( w < 0.95f )
			return;
		for ( int a = 0; a < 3; a++ )
			for ( int b = 0; b < 3; b++ )
				g_pgRot[ a ][ b ] = light[ rh ][ 0 ][ a ] * light[ lh ][ 0 ][ b ] + light[ rh ][ 1 ][ a ] * light[ lh ][ 1 ][ b ] +
									light[ rh ][ 2 ][ a ] * light[ lh ][ 2 ][ b ];
		g_pgHaveRot = true;
		return;
	}
	mat3_t want, W;
	for ( int a = 0; a < 3; a++ )
		for ( int b = 0; b < 3; b++ )
			want[ a ][ b ] = light[ rh ][ a ][ 0 ] * g_pgRot[ 0 ][ b ] + light[ rh ][ a ][ 1 ] * g_pgRot[ 1 ][ b ] +
							 light[ rh ][ a ][ 2 ] * g_pgRot[ 2 ][ b ];
	for ( int a = 0; a < 3; a++ )		// W = want * current^T
		for ( int b = 0; b < 3; b++ )
			W[ a ][ b ] = want[ a ][ 0 ] * light[ lh ][ b ][ 0 ] + want[ a ][ 1 ] * light[ lh ][ b ][ 1 ] +
						  want[ a ][ 2 ] * light[ lh ][ b ][ 2 ];
	float axis[ 3 ];
	float ang = MatAxisAngle( W, axis ) * Clamp01( w );
	if ( ang < 0.2f )
		return;
	mat3_t R;
	AxisAngle( axis, ang, R );
	float pivot[ 3 ];
	BoneOrigin( light, lh, pivot );
	TransformBones( bone, light, g_skel.lHandMask, R, pivot, NULL );
}

// The big energy guns (Gluon, Tau Cannon, Displacer) are held in their firing
// position whenever they're up, not just while firing (at ease still lowers them)
static bool AlwaysAimed( int weaponmodel )
{
	if ( FPBody_Classic() )
		return false;
	char name[ 32 ];
	GunShortName( weaponmodel, name, sizeof( name ) );
	return !stricmp( name, "p_egon" ) || !stricmp( name, "p_gauss" ) || !stricmp( name, "p_displacer" );
}

static void ApplyGunPose( float ( *bone )[ 3 ][ 4 ], float ( *light )[ 3 ][ 4 ], int weaponmodel,
	const float *f, const float *r, const float *u, float now )
{
	if ( !g_gripCfgRun )
	{
		g_gripCfgRun = true;
		gEngfuncs.pfnClientCmd( "exec fpbody_grips.cfg\n" );
		gEngfuncs.pfnClientCmd( "exec fpbody_guns.cfg\n" );
	}
	const gun_t *gun = GunForModel( weaponmodel );
	bool overlay = ( g_ovSeq >= 0 );	// GMod reload: hands leave the gun
	bool letGo = overlay || OffHandBusy( now );	// the left hand is needed elsewhere

	// smooth weights
	float aimTarget = ( gun && !overlay && cl_fpbody_aimfire->value != 0.0f && g_glOpenW <= 0.0f &&
						!( g_cur.type == CLIP_RELOAD && g_cur.variant == 1 && now < g_cur.start + g_cur.dur ) &&
						( ( now - g_lastShot >= 0.0f && now - g_lastShot < 0.6f ) || g_attackHeld || AlwaysAimed( weaponmodel ) ) ) ? 1.0f : 0.0f;
	float aimRate = aimTarget > g_aimW ? 14.0f : 5.0f;
	g_aimW += ( aimTarget - g_aimW ) * Clamp01( g_frameTime * aimRate );

	float offTarget = ( gun && gun->down >= 0.0f && !letGo ) ? Clamp01( cl_fpbody_offhand->value ) : 0.0f;
	g_offW += ( offTarget - g_offW ) * Clamp01( g_frameTime * ( offTarget < g_offW ? 14.0f : 8.0f ) );

	if ( !gun || g_skel.rUpper < 0 || g_skel.rHand < 0 )
		return;

	// pistols: the left hand's place and angle on the gun, in the gun hand's space
	// (two-handed holds like Counter-Strike's wrap it round the grip), held there
	// when the arms are moved below and from every view angle
	float lRel[ 3 ] = { 0, 0, 0 };
	bool haveRel = false;
	if ( gun->pistol && g_skel.lHand >= 0 )
	{
		PistolGripLatch( light, gun, weaponmodel, !letGo );
		for ( int i = 0; i < 3; i++ )
			lRel[ i ] = g_pgPos[ i ];
		haveRel = g_pgHavePos;
	}

	// 1a. pistols: two-handed hold, shooting hand in front of the chest and
	//     the pistol pointed down the view by the wrist
	if ( gun->pistol && g_offW > 0.001f && g_skel.lClav >= 0 && g_skel.rClav >= 0 )
	{
		float ls[ 3 ], rs[ 3 ], target[ 3 ];
		BoneOrigin( light, g_skel.lUpper >= 0 ? g_skel.lUpper : g_skel.lClav, ls );
		BoneOrigin( light, g_skel.rUpper, rs );
		// the hands follow the view up and down, but only so far: looking at your
		// feet they stay out in front of the chest instead of going into it
		float fh[ 3 ] = { f[ 0 ], f[ 1 ], 0.0f };
		if ( Normalize3( fh ) <= 0.0f )
		{
			fh[ 0 ] = u[ 0 ]; fh[ 1 ] = u[ 1 ];			// looking straight up / down: the top of the view is forward
			if ( Normalize3( fh ) <= 0.0f ) { fh[ 0 ] = 1.0f; fh[ 1 ] = 0.0f; }
		}
		float down = Clamp( (float)asin( Clamp( -f[ 2 ], -1.0f, 1.0f ) ), -1.2f, 0.55f );	// radians, + = looking down
		float cd = (float)cos( down ), sd = (float)sin( down );
		float fwd[ 3 ] = { fh[ 0 ] * cd, fh[ 1 ] * cd, -sd };
		float up2[ 3 ] = { fh[ 0 ] * sd, fh[ 1 ] * sd, cd };
		for ( int i = 0; i < 3; i++ )
			target[ i ] = ( ls[ i ] + rs[ i ] ) * 0.5f + fwd[ i ] * 15.0f - up2[ i ] * 4.0f + r[ i ] * 1.5f;
		ReachArm( bone, light, target, g_offW, true );

		float barrel[ 3 ], wrist[ 3 ];
		HandToWorldDir( light, g_skel.rHand, gun->axis, barrel );
		BoneOrigin( light, g_skel.rHand, wrist );
		TurnToward( bone, light, g_skel.rHandMask, wrist, barrel, f, g_offW );
	}
	// 1b. rifles: while firing, turn the right arm so the barrel points down the view
	else if ( g_aimW > 0.001f )
	{
		float barrel[ 3 ], pivot[ 3 ];
		HandToWorldDir( light, g_skel.rHand, gun->axis, barrel );
		BoneOrigin( light, g_skel.rUpper, pivot );
		TurnToward( bone, light, g_skel.rUpperMask, pivot, barrel, f, g_aimW );
	}

	// 2. off hand onto the gun: its measured handle if it has one
	const gmhandle_t *gh = ( g_offW > 0.001f && gun->down >= 0.0f && g_skel.hdr ) ? GmHandleForModel( weaponmodel ) : NULL;
	int ghBone = -1;
	if ( gh )
	{
		const mstudiobone_t *bones = (const mstudiobone_t *)( (const byte *)g_skel.hdr + g_skel.hdr->boneindex );
		ghBone = FindBone( bones, g_skel.numbones, gh->bone, NULL );
	}
	if ( gh && ghBone >= 0 )
	{
		float target[ 3 ], w[ 3 ] = { gh->wrist[ 0 ], gh->wrist[ 1 ], gh->wrist[ 2 ] };
		// grenade launcher reload: the hand moves back to the launcher's opening
		static const float glOpen[ 3 ] = { 10.5f, 3.5f, 1.0f };
		if ( g_glOpenW > 0.0f && !strcmp( gh->model, "p_9mmar" ) )
			for ( int i = 0; i < 3; i++ )
				w[ i ] += ( glOpen[ i ] - w[ i ] ) * Smooth( g_glOpenW );
		for ( int i = 0; i < 3; i++ )
			target[ i ] = light[ ghBone ][ i ][ 0 ] * w[ 0 ] + light[ ghBone ][ i ][ 1 ] * w[ 1 ] +
						  light[ ghBone ][ i ][ 2 ] * w[ 2 ] + light[ ghBone ][ i ][ 3 ];
		GripAdjust( light, gun, weaponmodel, target );
		PumpStroke( light, gun, now, target );
		ReachArm( bone, light, target, g_offW, false, cl_fpbody_elbowdown->value );
	}
	else if ( g_offW > 0.001f && gun->down >= 0.0f && haveRel )
	{
		// pistol in the animation's two-handed grip: the left hand stays where the
		// animation put it on the gun, wherever the gun hand has been moved to
		float target[ 3 ];
		for ( int i = 0; i < 3; i++ )
			target[ i ] = light[ g_skel.rHand ][ i ][ 0 ] * lRel[ 0 ] + light[ g_skel.rHand ][ i ][ 1 ] * lRel[ 1 ] +
						  light[ g_skel.rHand ][ i ][ 2 ] * lRel[ 2 ] + light[ g_skel.rHand ][ i ][ 3 ];
		GripAdjust( light, gun, weaponmodel, target );
		ReachArm( bone, light, target, g_offW, false, cl_fpbody_elbowdown->value );
		PistolGripTurn( bone, light, g_offW );
	}
	else if ( g_offW > 0.001f && gun->down >= 0.0f )
	{
		float grip[ 3 ], barrel[ 3 ], target[ 3 ];
		HandToWorldDir( light, g_skel.rHand, gun->grip, grip );
		HandToWorldDir( light, g_skel.rHand, gun->axis, barrel );
		Normalize3( barrel );
		for ( int i = 0; i < 3; i++ )
			target[ i ] = light[ g_skel.rHand ][ i ][ 3 ] + grip[ i ];
		target[ 2 ] -= gun->down;
		GripAdjust( light, gun, weaponmodel, target );
		ReachArm( bone, light, target, g_offW, false, cl_fpbody_elbowdown->value );
	}
}

// Classic mode keeps Half-Life's own holds, except guns whose world model has
// a handle for the left hand: the left wrist is put on it by arm IK.
// The wrist point is in the space of the bone the gun's mesh hangs from,
// measured on the models the mods ship (tools/gmod_anims/lefthand_sim.py).
struct gunhandle_t
{
	const char *model;
	const char *bone;		// player bone the gun mesh is attached to
	float wrist[ 3 ];		// left wrist target in that bone's space
	int length;				// header length of the model it was measured on (0 = any)
};

static const gunhandle_t g_handles[] =
{
	// Half-Life MMod Tau Cannon: side bar (the gun uses the shotgun hold, see gauss.cpp)
	{ "p_gauss", "Bip01 R Hand", { 16.3f, 8.0f, 2.5f }, 37260 },	// HD only (LD gauss has no side bar)
	// Sven Co-op Tau Cannon: the bar over the left side
	{ "p_gauss", "Bip01 R Hand", { 16.0f, 7.5f, 6.0f }, 125620 },
	// Sven Co-op MP5: under the handguard (the Condition Zero hold was made for a shorter gun)
	{ "p_9mmar", "Bip01 R Hand", { 15.5f, 5.0f, 2.0f }, 182228 },
	// HD pack weapon models (the same in valve_hd, bshift_hd and gearbox_hd), measured
	// in tools/gmod_anims/lefthand_hd.py: the M16's handguard (the gun is held far
	// forward, so as far along it as the arm reaches), the crossbow's fore-stock,
	// and a two-handed grip under the pistols
	{ "p_9mmar", "Bip01 R Hand", { 13.5f, 4.5f, 3.0f }, 32708 },
	{ "p_9mmar", "Bip01 R Hand", { 13.5f, 4.5f, 3.0f }, 29484 },
	{ "p_crossbow", "Bip01 R Hand", { 9.5f, 4.0f, 0.5f }, 38036 },
	{ "p_9mmhandgun", "Bip01 R Hand", { 3.0f, 4.5f, -1.0f }, 12500 },
	{ "p_357", "Bip01 R Hand", { 3.0f, 4.5f, -1.0f }, 28164 },
	// Opposing Force upscaled Displacer: the side handle (tools/gmod_anims/lefthand_gmod.py)
	{ "p_displacer", "Bip01 R Hand", { 12.0f, 10.0f, 6.0f }, 338732 },
};

static float g_handleW;
static const gunhandle_t *g_lastHandle;

static const gunhandle_t *HandleForModel( int modelindex )
{
	static int cachedIndex = -1;
	static const gunhandle_t *cached = NULL;
	if ( modelindex == cachedIndex )
		return cached;
	cachedIndex = modelindex;
	cached = NULL;
	model_t *m = modelindex > 0 ? IEngineStudio.GetModelByIndex( modelindex ) : NULL;
	if ( !m )
		return NULL;
	char name[ 64 ];
	Lower( m->name, name, sizeof( name ) );
	for ( int i = 0; i < (int)( sizeof( g_handles ) / sizeof( g_handles[ 0 ] ) ); i++ )
	{
		char want[ 40 ];
		snprintf( want, sizeof( want ), "/%s.mdl", g_handles[ i ].model );
		if ( Has( name, want ) )
		{
			const studiohdr_t *mh = (const studiohdr_t *)IEngineStudio.Mod_Extradata( m );
			if ( g_handles[ i ].length && ( !mh || mh->length != g_handles[ i ].length ) )
				continue;
			cached = &g_handles[ i ];
			break;
		}
	}
	return cached;
}

static void ApplyClassicHandle( float ( *bone )[ 3 ][ 4 ], float ( *light )[ 3 ][ 4 ], int weaponmodel )
{
	const gunhandle_t *h = HandleForModel( weaponmodel );
	float want = ( h && !OffHandBusy( g_now ) ) ? Clamp01( cl_fpbody_offhand->value ) : 0.0f;
	g_handleW += ( want - g_handleW ) * Clamp01( g_frameTime * ( want < g_handleW ? 14.0f : 8.0f ) );
	if ( h )
		g_lastHandle = h;
	h = g_lastHandle;
	if ( !h || g_handleW <= 0.001f || !g_skel.hdr )
		return;

	const mstudiobone_t *bones = (const mstudiobone_t *)( (const byte *)g_skel.hdr + g_skel.hdr->boneindex );
	int b = FindBone( bones, g_skel.numbones, h->bone, NULL );
	if ( b < 0 )
		return;

	float target[ 3 ];
	for ( int i = 0; i < 3; i++ )
		target[ i ] = light[ b ][ i ][ 0 ] * h->wrist[ 0 ] + light[ b ][ i ][ 1 ] * h->wrist[ 1 ] +
					  light[ b ][ i ][ 2 ] * h->wrist[ 2 ] + light[ b ][ i ][ 3 ];
	ReachArm( bone, light, target, g_handleW );
}

// ---------------------------------------------------------------------------
// Camera follows the head's rotation
// ---------------------------------------------------------------------------

static void Orthonormalize( mat3_t m )
{
	// rows
	Normalize3( m[ 0 ] );
	float d = Dot3( m[ 0 ], m[ 1 ] );
	for ( int i = 0; i < 3; i++ ) m[ 1 ][ i ] -= m[ 0 ][ i ] * d;
	Normalize3( m[ 1 ] );
	Cross( m[ 0 ], m[ 1 ], m[ 2 ] );
}

static void UpdateHeadRotation( float ( *light )[ 3 ][ 4 ], int headBone,
	const float *f, const float *r, const float *u, float now )
{
	if ( headBone < 0 )
		return;

	// view frame with columns forward, left, up
	float l[ 3 ] = { -r[ 0 ], -r[ 1 ], -r[ 2 ] };
	mat3_t V;
	for ( int i = 0; i < 3; i++ )
	{
		V[ i ][ 0 ] = f[ i ];
		V[ i ][ 1 ] = l[ i ];
		V[ i ][ 2 ] = u[ i ];
	}

	// head rotation expressed in the view frame: Rrel = V^T * H
	mat3_t Rrel;
	for ( int i = 0; i < 3; i++ )
		for ( int j = 0; j < 3; j++ )
			Rrel[ i ][ j ] = V[ 0 ][ i ] * light[ headBone ][ 0 ][ j ] +
							 V[ 1 ][ i ] * light[ headBone ][ 1 ][ j ] +
							 V[ 2 ][ i ] * light[ headBone ][ 2 ][ j ];

	float dt = now - g_lastHeadTime;
	g_lastHeadTime = now;

	if ( !g_haveHeadSmooth || dt > 0.3f || dt < 0.0f )
	{
		memcpy( g_headSmooth, Rrel, sizeof( mat3_t ) );
		g_haveHeadSmooth = true;
		g_headAngOfs[ 0 ] = g_headAngOfs[ 1 ] = g_headAngOfs[ 2 ] = 0.0f;
		g_headOfsTime = now;
		return;
	}

	// slow average of the head's orientation; the camera only gets the fast part
	// (walk bob, sway, jolts), so aiming and looking around aren't affected
	float k = 1.0f - (float)exp( -dt / 0.35f );
	for ( int i = 0; i < 3; i++ )
		for ( int j = 0; j < 3; j++ )
			g_headSmooth[ i ][ j ] += ( Rrel[ i ][ j ] - g_headSmooth[ i ][ j ] ) * k;
	Orthonormalize( g_headSmooth );

	// D = Rrel * S^T (rotation from the average to now)
	mat3_t D;
	for ( int i = 0; i < 3; i++ )
		for ( int j = 0; j < 3; j++ )
			D[ i ][ j ] = Rrel[ i ][ 0 ] * g_headSmooth[ j ][ 0 ] +
						  Rrel[ i ][ 1 ] * g_headSmooth[ j ][ 1 ] +
						  Rrel[ i ][ 2 ] * g_headSmooth[ j ][ 2 ];

	float toDeg = (float)( 180.0 / M_PI );
	float wx = ( D[ 2 ][ 1 ] - D[ 1 ][ 2 ] ) * 0.5f * toDeg;	// about forward -> roll
	float wy = ( D[ 0 ][ 2 ] - D[ 2 ][ 0 ] ) * 0.5f * toDeg;	// about left    -> pitch
	float wz = ( D[ 1 ][ 0 ] - D[ 0 ][ 1 ] ) * 0.5f * toDeg;	// about up      -> yaw

	// the stabilizer mostly removes the side to side (yaw / roll) wobble of steps
	float s = cl_fpbody_headrot->value;
	float stab = FPBody_Stabilize();
	if ( stab < 0.0f ) stab = 0.0f;
	if ( stab > 1.0f ) stab = 1.0f;
	float side = 1.0f - stab * 0.9f;
	float nod = 1.0f - stab * 0.5f;
	g_headAngOfs[ PITCH ] = Clamp( wy * s * 0.5f * nod, -6.0f, 6.0f );
	g_headAngOfs[ YAW ]   = Clamp( wz * s * side, -6.0f, 6.0f );
	g_headAngOfs[ ROLL ]  = Clamp( wx * s * side, -6.0f, 6.0f );
	g_headOfsTime = now;
}

void FPAnim_GetViewAngleOffset( float *ofs )
{
	ofs[ 0 ] = ofs[ 1 ] = ofs[ 2 ] = 0.0f;

	if ( !FPBody_Active() || !cl_fpbody_headrot || cl_fpbody_headrot->value == 0.0f )
		return;

	if ( FPAnim_ActCamActive() )
		return;

	if ( gEngfuncs.GetClientTime() - g_headOfsTime > 0.25f )
		return;

	VectorCopy( g_headAngOfs, ofs );
}

// ---------------------------------------------------------------------------
// Main entry from the renderer
// ---------------------------------------------------------------------------

void FPAnim_ApplyBones( void *studiohdr, float ( *bone )[ 3 ][ 4 ], float ( *light )[ 3 ][ 4 ],
	int headBone, int weaponmodel )
{
	// The software renderer stores bones in screen space; only animate in GL/D3D
	if ( !IEngineStudio.IsHardware() )
		return;

	const studiohdr_t *hdr = (const studiohdr_t *)studiohdr;
	if ( !hdr )
		return;

	CacheSkeleton( hdr );

	float now = gEngfuncs.GetClientTime();

	Vector angles, f, r, u;
	gEngfuncs.GetViewAngles( (float *)angles );
	AngleVectors( angles, f, r, u );

	bool fullAct = ( g_ovSeq >= 0 && g_ovFull );

	if ( AnimsOn() && !fullAct )
	{
		// a new gun in the hands without a draw animation still comes up from low
		if ( weaponmodel != g_lastWeaponModel )
		{
			if ( g_lastWeaponModel >= 0 && weaponmodel > 0 &&
				 !( g_cur.type == CLIP_DRAW && now - g_cur.start < 0.3f ) )
			{
				StartClip( CLIP_DRAW, 0, 1.0f, 0.5f );
			}
			g_lastWeaponModel = weaponmodel;
		}

		pose_t p;
		memset( &p, 0, sizeof( p ) );

		float fade = Clamp01( ( now - g_prevFadeStart ) / 0.12f );
		g_glOpenW = 0.0f;
		EvalClip( g_cur, now, fade, p, f, r, u );
		EvalClip( g_prev, now, 1.0f - fade, p, f, r, u );
		EvalActions( now, p, f, r, u );

		// Condition Zero holds put the sights at eye level, which from inside the
		// head fills the view; classic mode tilts those guns down a little (only
		// in our own view - other players see the full hold)
		{
			float want = 0.0f;
			cl_entity_t *local = gEngfuncs.GetLocalPlayer();
			int curSeq = LocalSeq( local );
			if ( FPBody_Classic() && g_ovSeq < 0 && local && g_playerHdr &&
				 curSeq >= 0 && curSeq < g_playerHdr->numseq )
			{
				const char *lab = ( (const mstudioseqdesc_t *)( (const byte *)g_playerHdr + g_playerHdr->seqindex ) +
									curSeq )->label;
				static const char *raised[] = { "_mp5", "_shotgun", "_onehanded", "_rifle", "_m249" };
				if ( !strnicmp( lab, "cs_", 3 ) )		// Counter-Strike 1.6 set: same holds
					lab += 3;
				if ( !strnicmp( lab, "ref_", 4 ) || !strnicmp( lab, "crouch_", 7 ) )
					for ( int i = 0; i < (int)( sizeof( raised ) / sizeof( raised[ 0 ] ) ); i++ )
					{
						size_t n = strlen( lab ), m = strlen( raised[ i ] );
						if ( n > m && !stricmp( lab + n - m, raised[ i ] ) )
						{
							want = ( i == 2 ) ? 0.4f : 1.0f;		// pistols already sit lower
							break;
						}
					}
			}
			g_gunLowerW += ( want - g_gunLowerW ) * Clamp01( g_frameTime * 6.0f );
			p.armsPitch += cl_fpbody_gunlower->value * g_gunLowerW;
		}

		// GMod mode: the ready hold of two-handed guns, a little below the sights
		// (fp_hold per gun); up to the sights while firing, off while at ease or
		// in a full-body move
		if ( !FPBody_Classic() && weaponmodel > 0 )
		{
			const gun_t *gun = GunForModel( weaponmodel );
			if ( gun && !gun->pistol && gun->down >= 0.0f )
			{
				char name[ 32 ];
				GunShortName( weaponmodel, name, sizeof( name ) );
				const gunofs_t *go = GunOfsFor( name, false );
				float hd[ 3 ] = { cl_fpbody_holdlower ? cl_fpbody_holdlower->value : 0.0f, 0.0f, 0.0f };
				// big guns held in front of the chest: out in front instead of lower
				// (the Displacer otherwise sits right under the eye)
				static const struct { const char *model; float hold[ 3 ]; } holdDefs[] = {
					{ "p_displacer", { 0.0f, 3.0f, -9.0f } },
				};
				bool keepAim = false;		// held out there while firing too (no jump back)
				for ( int i = 0; i < (int)( sizeof( holdDefs ) / sizeof( holdDefs[ 0 ] ) ); i++ )
					if ( !stricmp( name, holdDefs[ i ].model ) )
					{
						for ( int k = 0; k < 3; k++ )
							hd[ k ] = holdDefs[ i ].hold[ k ];
						keepAim = true;
					}
				if ( go && go->hasHold )
					for ( int i = 0; i < 3; i++ )
						hd[ i ] = go->hold[ i ];
				float w = ( keepAim ? 1.0f : 1.0f - Clamp01( g_aimW ) ) * ( 1.0f - Clamp01( g_relaxW ) ) * ( g_ovSeq >= 0 ? 0.0f : 1.0f );
				static float s_holdW;
				s_holdW += ( w - s_holdW ) * Clamp01( g_frameTime * 8.0f );
				p.armsPitch += hd[ 0 ] * s_holdW;
				p.armsYaw   -= hd[ 1 ] * s_holdW;
				p.armsBack  += hd[ 2 ] * s_holdW;
			}
		}

		float scale = cl_fpbody_animscale->value;
		p.armsPitch *= scale; p.armsYaw *= scale; p.armsRoll *= scale; p.armsBack *= scale;
		p.rPitch *= scale; p.rYaw *= scale; p.lPitch *= scale; p.lBack *= scale;
		p.spinePitch *= scale;
		p.lAimW = Clamp01( p.lAimW ) * Clamp01( scale );

		mat3_t W;

		// 1. upper body bend (moves arms and head together)
		if ( g_skel.spine >= 0 && fabs( p.spinePitch ) > 0.01f )
		{
			float pivot[ 3 ];
			BoneOrigin( light, g_skel.spine, pivot );
			AxisAngle( r, -p.spinePitch, W );
			TransformBones( bone, light, g_skel.spineMask, W, pivot, NULL );
		}

		// 2. both arms and the gun, around the point between the shoulders
		if ( g_skel.lClav >= 0 && g_skel.rClav >= 0 &&
			 ( fabs( p.armsPitch ) + fabs( p.armsYaw ) + fabs( p.armsRoll ) + fabs( p.armsBack ) ) > 0.01f )
		{
			float a[ 3 ], b[ 3 ], pivot[ 3 ], move[ 3 ];
			BoneOrigin( light, g_skel.lClav, a );
			BoneOrigin( light, g_skel.rClav, b );
			for ( int i = 0; i < 3; i++ )
			{
				pivot[ i ] = ( a[ i ] + b[ i ] ) * 0.5f;
				move[ i ] = -f[ i ] * p.armsBack;
			}
			ViewRotation( f, r, u, p.armsPitch, p.armsYaw, p.armsRoll, W );
			TransformBones( bone, light, g_skel.armsMask, W, pivot, move );
		}

		// 3. right arm alone (melee swings, throws)
		if ( g_skel.rUpper >= 0 && ( fabs( p.rPitch ) + fabs( p.rYaw ) ) > 0.01f )
		{
			float pivot[ 3 ];
			BoneOrigin( light, g_skel.rUpper, pivot );
			ViewRotation( f, r, u, p.rPitch, p.rYaw, 0.0f, W );
			TransformBones( bone, light, g_skel.rUpperMask, W, pivot, NULL );
		}

		// 3b. gun straight down the view while firing, off hand on the gun
		// (classic mode keeps Half-Life's own holds, like the original game)
		if ( !FPBody_Classic() )
			ApplyGunPose( bone, light, weaponmodel, f, r, u, now );
		else
			ApplyClassicHandle( bone, light, weaponmodel );	// left hand onto the handle of a few big guns
		ApplyRelaxHands( bone, light, weaponmodel, f );		// fp_relax_hand / fp_relax_lhand
		if ( !FPBody_Classic() )
			ApplyFingers( bone, light, weaponmodel );			// fingers round the gun (fp_fingers)

		// 4. left arm alone (reloading, use, flashlight, ladders, pump)
		if ( g_skel.lUpper >= 0 )
		{
			if ( fabs( p.lPitch ) + fabs( p.lBack ) > 0.01f )
			{
				float pivot[ 3 ], move[ 3 ];
				BoneOrigin( light, g_skel.lUpper, pivot );
				for ( int i = 0; i < 3; i++ )
					move[ i ] = -f[ i ] * p.lBack;
				ViewRotation( f, r, u, p.lPitch, 0.0f, 0.0f, W );
				TransformBones( bone, light, g_skel.lUpperMask, W, pivot, move );
			}

			if ( p.lAimW > 0.001f && Normalize3( p.lAimDir ) > 0.0f )
				AimArm( bone, light, g_skel.lUpper, g_skel.lHand, g_skel.lUpperMask, p.lAimDir, p.lAimW );
			if ( cl_fpbody_usepalm && cl_fpbody_usepalm->value != 0.0f )
				UsePalm( bone, light, f, r, u, g_usePalmW * Clamp01( scale ), now < g_useChargeUntil );
		}
	}

	// the forearms roll with the hands (one bone per vertex: see ShareWristTwist)
	if ( !FPBody_Classic() && cl_fpbody_wristtwist && cl_fpbody_wristtwist->value > 0.0f )
	{
		ShareWristTwist( bone, light, g_skel.lFore, g_skel.lHand, cl_fpbody_wristtwist->value );
		ShareWristTwist( bone, light, g_skel.rFore, g_skel.rHand, cl_fpbody_wristtwist->value );
	}

	// Camera rotation from the final head pose
	UpdateHeadRotation( light, headBone, f, r, u, now );
}

// ---------------------------------------------------------------------------
// GMod overlays: lookup, fp_act commands, renderer hook
// ---------------------------------------------------------------------------

static int FindSeq( const studiohdr_t *hdr, const char *name )
{
	if ( !hdr )
		return -1;
	const mstudioseqdesc_t *seqs = (const mstudioseqdesc_t *)( (const byte *)hdr + hdr->seqindex );
	for ( int i = 0; i < hdr->numseq; i++ )
		if ( !stricmp( seqs[ i ].label, name ) )
			return i;
	return -1;
}

// The server picks the player's sequences by number in its own player model
// (models/player.mdl); our body may be drawn with another model (the classic /
// outfit ones) whose numbering differs. Translate by sequence name.
// Which weapon holds play from Counter-Strike 1.6's set (cs_<name>) instead of
// Condition Zero's: 1 = all (sv_fpbody_anims cs), 2 = the rifle set only (the
// local player carries the 9mmAR, an M16). The server's player.mdl has only the
// plain names, so the choice is made here, where the name is looked up in the
// drawn classic model.
static int CSPreference( void )
{
	int pref = 0;
	const char *set = gEngfuncs.pfnGetCvarString ? gEngfuncs.pfnGetCvarString( "sv_fpbody_anims" ) : NULL;
	if ( set && !strnicmp( set, "cs", 2 ) )
		pref |= 1;
	static int cachedIndex = -1, cachedM16 = 0;
	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	int wm = local ? local->curstate.weaponmodel : 0;
	if ( wm != cachedIndex )
	{
		cachedIndex = wm;
		cachedM16 = 0;
		model_t *m = wm > 0 ? IEngineStudio.GetModelByIndex( wm ) : NULL;
		if ( m )
		{
			char name[ 64 ];
			Lower( m->name, name, sizeof( name ) );
			cachedM16 = Has( name, "/p_9mmar.mdl" );
		}
	}
	if ( cachedM16 )
		pref |= 2;
	return pref;
}

// cl_fpbody_debug: which sequence the server plays on us and which one the body draws
void FPAnim_DebugSeq( const void *fromHdr, const void *toHdr, int seq, int gait, int mseq, int mgait )
{
	static int ls = -9, lg = -9, lms = -9, lmg = -9;
	if ( !cl_fpbody_debug || cl_fpbody_debug->value == 0.0f || ( seq == ls && gait == lg && mseq == lms && mgait == lmg ) )
		return;
	ls = seq; lg = gait; lms = mseq; lmg = mgait;
	const studiohdr_t *from = (const studiohdr_t *)fromHdr, *to = (const studiohdr_t *)toHdr;
	const mstudioseqdesc_t *fs = (const mstudioseqdesc_t *)( (const byte *)from + from->seqindex );
	const mstudioseqdesc_t *ts = (const mstudioseqdesc_t *)( (const byte *)to + to->seqindex );
	FPDbg( "server seq %s / gait %s -> body %s / %s\n",
		seq >= 0 && seq < from->numseq ? fs[ seq ].label : "?", gait >= 0 && gait < from->numseq ? fs[ gait ].label : "?",
		mseq >= 0 && mseq < to->numseq ? ts[ mseq ].label : "?", mgait >= 0 && mgait < to->numseq ? ts[ mgait ].label : "?" );
}

// Swimming with a gun: the server plays the whole-body swim (arms doing the strokes,
// the gun flailing in the hand). Keep the arms in the gun's hold (the last
// ref_aim_ / ref_shoot_ hold the server played) and let the legs swim: the hold
// as the sequence, the swim as the gait.
static char g_lastHoldExt[ 32 ];
void FPAnim_SwimHold( const void *fromHdr, const void *toHdr, int srvSeq, int weaponmodel, int entindex, int *seq, int *gait )
{
	const studiohdr_t *from = (const studiohdr_t *)fromHdr, *to = (const studiohdr_t *)toHdr;
	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	if ( !from || !to || !local || entindex != local->index || srvSeq < 0 || srvSeq >= from->numseq )
		return;
	const char *label = ( (const mstudioseqdesc_t *)( (const byte *)from + from->seqindex ) )[ srvSeq ].label;
	static const char *holds[] = { "ref_aim_", "ref_shoot_", "crouch_aim_", "crouch_shoot_" };
	for ( int i = 0; i < 4; i++ )
	{
		size_t n = strlen( holds[ i ] );
		if ( !strnicmp( label, holds[ i ], n ) )
		{
			snprintf( g_lastHoldExt, sizeof( g_lastHoldExt ), "%s", label + n );
			return;
		}
	}
	if ( weaponmodel <= 0 || !g_lastHoldExt[ 0 ] || !cl_fpbody_swimhold || cl_fpbody_swimhold->value == 0.0f )
		return;
	if ( stricmp( label, "swim" ) && stricmp( label, "treadwater" ) )
		return;
	char want[ 48 ];
	snprintf( want, sizeof( want ), "ref_aim_%s", g_lastHoldExt );
	int m = FindSeq( to, want );
	if ( m < 0 )
		return;
	*gait = *seq;			// the swim kicks the legs
	*seq = m;				// the arms hold the gun
}

int FPAnim_MapSeq( const void *fromHdr, const void *toHdr, int seq )
{
	const studiohdr_t *from = (const studiohdr_t *)fromHdr, *to = (const studiohdr_t *)toHdr;
	if ( !from || !to || from == to || seq < 0 || seq >= from->numseq )
		return seq;
	int pref = CSPreference();
	static const studiohdr_t *cFrom, *cTo;
	static int cPref = -1;
	static short cache[ 2048 ];
	if ( cFrom != from || cTo != to || cPref != pref )
	{
		cFrom = from;
		cTo = to;
		cPref = pref;
		for ( int i = 0; i < 2048; i++ )
			cache[ i ] = -2;
	}
	if ( seq >= 2048 )
		return seq;
	if ( cache[ seq ] == -2 )
	{
		const mstudioseqdesc_t *seqs = (const mstudioseqdesc_t *)( (const byte *)from + from->seqindex );
		const char *label = seqs[ seq ].label;
		int m = -1;
		size_t n = strlen( label );
		bool hold = !strnicmp( label, "ref_", 4 ) || !strnicmp( label, "crouch_", 7 );
		bool rifle = n > 6 && !stricmp( label + n - 6, "_rifle" );
		if ( hold && ( ( pref & 1 ) || ( ( pref & 2 ) && rifle ) ) )
		{
			char cs[ 48 ];
			snprintf( cs, sizeof( cs ), "cs_%s", label );
			m = FindSeq( to, cs );
		}
		if ( m < 0 )
			m = FindSeq( to, label );
		cache[ seq ] = (short)( m >= 0 ? m : ( seq < to->numseq ? seq : 0 ) );
	}
	return cache[ seq ];
}

// set by the studio renderer while the local entity's sequence is already
// translated into the drawn model (see StudioDrawPlayer)
int g_fpSeqRemapped;

// the local player's current sequence in the model our body is drawn with
static int LocalSeq( cl_entity_t *local )
{
	if ( !local || !g_playerHdr )
		return -1;
	if ( g_fpSeqRemapped )
		return local->curstate.sequence;
	const void *srv = ( local->model && local->model->type == mod_studio ) ? IEngineStudio.Mod_Extradata( local->model ) : NULL;
	return FPAnim_MapSeq( srv, g_playerHdr, local->curstate.sequence );
}

static bool IsUpperBodyAct( const char *label )
{
	return !strnicmp( label, "gm_gesture_", 11 ) || !strnicmp( label, "gm_reload_", 10 ) || !strnicmp( label, "l4d_reload_", 11 ) || !strnicmp( label, "css_reload_", 11 ) ||
		   !strnicmp( label, "ref_reload_", 11 ) || !strnicmp( label, "crouch_reload_", 14 ) ||
		   !strnicmp( label, "sv_ref_reload_", 14 ) || !strnicmp( label, "sv_crouch_reload_", 17 ) ||
		   !strnicmp( label, "cs_ref_reload_", 14 ) || !strnicmp( label, "cs_crouch_reload_", 17 ) ||
		   !strnicmp( label, "gm_shove_", 9 ) || !strnicmp( label, "gm_zombie_attack_", 17 ) ||
		   !strnicmp( label, "fm_draw_", 8 ) || !strnicmp( label, "fm_passive_", 11 ) || !strnicmp( label, "fm_relax_", 9 ) ||
		   !stricmp( label, "fm_pickup" ) || !stricmp( label, "fm_strangle" ) || !stricmp( label, "fm_blast" );
}

// Start a gm_ sequence now. wantDur > 0 stretches it to that many seconds.
static bool StartOverlay( const char *name, bool user, float wantDur )
{
	if ( !g_playerHdr )
		return false;

	static const char *prefixes[] = { "", "gm_", "gm_taunt_", "gm_gesture_", "gm_pose_", "gm_idle_all_", "gm_seq_" };
	int seq = -1;
	char full[ 96 ];
	for ( int i = 0; i < (int)( sizeof( prefixes ) / sizeof( prefixes[ 0 ] ) ) && seq < 0; i++ )
	{
		snprintf( full, sizeof( full ), "%s%s", prefixes[ i ], name );
		seq = FindSeq( g_playerHdr, full );
	}
	if ( seq < 0 )
		return false;

	const mstudioseqdesc_t *sd = (const mstudioseqdesc_t *)( (const byte *)g_playerHdr + g_playerHdr->seqindex ) + seq;
	float dur = ( sd->fps > 0.0f && sd->numframes > 1 ) ? ( sd->numframes - 1 ) / sd->fps : 0.1f;

	g_ovSeq = seq;
	g_ovStart = gEngfuncs.GetClientTime();
	g_ovRate = ( wantDur > 0.05f ) ? Clamp( dur / wantDur, 0.5f, 2.0f ) : 1.0f;
	g_ovDur = dur / g_ovRate;
	g_ovLoop = ( sd->flags & STUDIO_LOOPING ) != 0;
	g_ovFull = !IsUpperBodyAct( sd->label );
	g_ovUser = user;
	g_ovKind = user ? OVK_USER : OVK_RELOAD;
	return true;
}

static bool StartOverlayKind( const char *name, int kind, float wantDur )
{
	if ( !StartOverlay( name, false, wantDur ) )
		return false;
	g_ovKind = kind;
	FPDbg( "overlay %s (kind %d)\n", name, kind );
	return true;
}

static void FP_ActCmd( void )
{
	if ( gEngfuncs.Cmd_Argc() < 2 )
	{
		gEngfuncs.Con_Printf( "usage: fp_act <name>   (fp_actlist shows them all, fp_act_stop stops)\n" );
		return;
	}
	if ( !FPBody_Active() )
	{
		gEngfuncs.Con_Printf( "fp_act: only works in first-person body mode (cl_fpbody 1, alive)\n" );
		return;
	}
	// resolved on the next frame, when the player model is known
	strncpy( g_ovRequest, gEngfuncs.Cmd_Argv( 1 ), sizeof( g_ovRequest ) - 1 );
	g_ovRequest[ sizeof( g_ovRequest ) - 1 ] = 0;
}

static void FP_ActList( void )
{
	if ( !g_playerHdr )
	{
		gEngfuncs.Con_Printf( "fp_actlist: start a map first\n" );
		return;
	}
	const mstudioseqdesc_t *seqs = (const mstudioseqdesc_t *)( (const byte *)g_playerHdr + g_playerHdr->seqindex );
	int n = 0;
	for ( int i = 0; i < g_playerHdr->numseq; i++ )
	{
		if ( strnicmp( seqs[ i ].label, "gm_", 3 ) )
			continue;
		gEngfuncs.Con_Printf( "  %-28s %s%s\n", seqs[ i ].label + 3,
			IsUpperBodyAct( seqs[ i ].label ) ? "upper body" : "full body",
			( seqs[ i ].flags & STUDIO_LOOPING ) ? ", loops" : "" );
		n++;
	}
	if ( !n )
		gEngfuncs.Con_Printf( "No GMod animations in this player model (fpbody/models/player.mdl missing?)\n" );
	else
		gEngfuncs.Con_Printf( "%d animations. Example: fp_act dance  /  bind g \"fp_act wave\"\n", n );
}

int FPAnim_GetOverlay( int playerNumber, void *studiohdr, int *seq, float *animtime,
	float *framerate, int *fullbody )
{
	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	if ( !local || playerNumber != local->index )
		return 0;

	const studiohdr_t *hdr = (const studiohdr_t *)studiohdr;
	if ( hdr != g_playerHdr )
	{
		g_playerHdr = hdr;
		g_bGmodModel = FindSeq( hdr, "gm_taunt_dance" ) >= 0;
		g_ovSeq = -1;
	}

	if ( !FPBody_Active() || ( cl_fpbody_gmod->value == 0.0f && g_ovKind <= OVK_RELOAD ) )
	{
		g_ovSeq = -1;
		g_ovRequest[ 0 ] = 0;
		return 0;
	}

	if ( g_ovRequest[ 0 ] )
	{
		if ( !StartOverlay( g_ovRequest, true, 0.0f ) )
			gEngfuncs.Con_Printf( "fp_act: no animation called \"%s\" (type fp_actlist)\n", g_ovRequest );
		g_ovRequest[ 0 ] = 0;
	}

	if ( g_ovSeq < 0 || g_ovSeq >= hdr->numseq )
		return 0;

	float now = gEngfuncs.GetClientTime();
	if ( now < g_ovStart || ( !g_ovLoop && now > g_ovStart + g_ovDur ) )
	{
		g_ovSeq = -1;
		return 0;
	}

	*seq = g_ovSeq;
	*animtime = g_ovStart;
	*framerate = g_ovRate;
	*fullbody = g_ovFull ? 1 : 0;
	return 1;
}

// A landing / roll / slide is playing: the body folds forward round the
// head, so the camera keeps ahead of the shoulders (see FPBody_GetViewOrigin)
float FPAnim_HunchWeight( void )
{
	static float w = 0.0f, last = -1.0f;
	float now = gEngfuncs.GetClientTime();
	bool on = g_ovSeq >= 0 && g_ovKind == OVK_MOVE &&
			  ( OverlayIs( "fm_hardland" ) || OverlayIs( "fm_roll" ) || OverlayIs( "fm_slide" ) || OverlayIs( "fm_job_heal" ) );
	float dt = ( last < 0.0f || now < last ) ? 0.0f : Clamp( now - last, 0.0f, 0.1f );
	last = now;
	w += ( ( on ? 1.0f : 0.0f ) - w ) * Clamp01( dt * ( on ? 12.0f : 5.0f ) );
	return w;
}

int FPAnim_ActCamActive( void )
{
	return g_ovSeq >= 0 && g_ovFull && g_ovKind == OVK_USER && cl_fpbody_actcam && cl_fpbody_actcam->value != 0.0f;
}
