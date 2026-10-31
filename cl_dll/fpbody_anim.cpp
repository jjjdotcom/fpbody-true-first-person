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
//   cl_fpbody_offhand   1    keep the off hand on two-handed guns (arm IK; in classic mode,
//                            the left hand on the Tau Cannon, Gluon gun and Displacer handles)
//   cl_fpbody_grip_fwd  0    move the off-hand grip forward/back along the gun (units)
//   cl_fpbody_grip_down 0    move the off-hand grip down/up (units)
//
// Console commands (GMod animations, need fpbody/models/player.mdl)
//   fp_act <name>     play a gesture/taunt, e.g. "fp_act dance", "fp_act wave"
//   fp_act_stop       stop it
//   fp_actlist        list every available animation

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

#include <string.h>
#include <math.h>

#include "fpbody.h"
#include "fpbody_anim.h"
#include "fpbody_game.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

extern engine_studio_api_t IEngineStudio;
extern kbutton_t in_use;
extern kbutton_t in_attack;
extern kbutton_t in_attack2;
extern kbutton_t in_jump;
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
static float g_speed2D;

static void StopOverlay( void ) { g_ovSeq = -1; g_ovRequest[ 0 ] = 0; }
static void FP_ActCmd( void );
static void FP_ActList( void );
static bool StartOverlay( const char *name, bool user, float wantDur );

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
static int g_lastFlash = -1;
static float g_flashStart = -10.0f;
static float g_landStart = -10.0f;
static float g_landStrength;
static int g_wasOnGround = 1;
static float g_maxFallSpeed;
static float g_ladderW;
static float g_ladderPhase;
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
	cl_fpbody_grip_fwd  = gEngfuncs.pfnRegisterVariable( "cl_fpbody_grip_fwd", "0", FCVAR_ARCHIVE );
	cl_fpbody_grip_down = gEngfuncs.pfnRegisterVariable( "cl_fpbody_grip_down", "0", FCVAR_ARCHIVE );

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

	if ( type == CLIP_NONE )
		return;

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
	if ( ( type == CLIP_DRAW || type == CLIP_HOLSTER ) && g_ovSeq >= 0 && !g_ovUser )
		StopOverlay();

	// Use GMod's reload animation for this weapon when the model has one
	if ( type == CLIP_RELOAD && g_bGmodModel && cl_fpbody_gmod->value != 0.0f )
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

	if ( type == CLIP_RECOIL || type == CLIP_CHARGE || type == CLIP_BEAM )
		g_lastShot = gEngfuncs.GetClientTime();

	StartClip( type, variant, strength, seqDur );
}

void FPAnim_OnWeaponAnim( int iAnim, int viewmodelIndex )
{
	g_bHookSeen = true;

	if ( !AnimsOn() )
		return;

	model_t *model = NULL;
	if ( viewmodelIndex > 0 )
		model = IEngineStudio.GetModelByIndex( viewmodelIndex );

	if ( !model )
	{
		cl_entity_t *view = gEngfuncs.GetViewModel();
		if ( view )
			model = view->model;
	}

	HandleWeaponAnim( model, iAnim );
}

// Fallback when client weapon prediction is off (cl_lw 0): watch the view
// model entity for animation changes sent by the server.
static void PollViewModel( void )
{
	if ( g_bHookSeen )
		return;

	cl_entity_t *view = gEngfuncs.GetViewModel();
	if ( !view || !view->model )
		return;

	if ( view->curstate.sequence != g_lastPollSeq || view->curstate.animtime != g_lastPollAnimTime )
	{
		bool first = ( g_lastPollSeq < 0 );
		g_lastPollSeq = view->curstate.sequence;
		g_lastPollAnimTime = view->curstate.animtime;
		if ( !first )
			HandleWeaponAnim( view->model, view->curstate.sequence );
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
		p.lBack     += 4.5f * Bump( t, 0.05f, 0.7f ) * weight;
		p.armsPitch -= 3.0f * Bump( t, 0.0f, 0.5f ) * weight;
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

void FPAnim_Frame( struct ref_params_s *pparams )
{
	g_now = gEngfuncs.GetClientTime();
	g_frameTime = Clamp( pparams->frametime, 0.0f, 0.1f );

	PollViewModel();

	g_speed2D = (float)sqrt( pparams->simvel[ 0 ] * pparams->simvel[ 0 ] + pparams->simvel[ 1 ] * pparams->simvel[ 1 ] );

	// full-body acts end when you move, shoot or jump
	if ( g_ovSeq >= 0 && g_ovFull && g_now - g_ovStart > 0.3f )
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
}

static void EvalActions( float now, pose_t &p, const float *f, const float *r, const float *u )
{
	float dir[ 3 ];

	// +use: off hand reaches out; holding it keeps the hand out (pushing)
	float tap = Bump( ( now - g_useStart ) / 0.6f, 0.0f, 1.0f );
	float useW = tap > g_useHoldW ? tap : g_useHoldW;
	if ( useW > 0.0f )
	{
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
	bool rightArm = false )
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
	d = Clamp( d, (float)fabs( a - b ) + 0.1f, a + b - 0.1f );

	// 1. elbow bend
	float cur = AngleAt( S, E, H );
	float des = (float)acos( Clamp( ( a * a + b * b - d * d ) / ( 2.0f * a * b ), -1.0f, 1.0f ) );
	float n[ 3 ];
	Cross( se, eh, n );
	if ( Normalize3( n ) < 1e-3f )
	{
		float down[ 3 ] = { 0, 0, -1 };
		Cross( se, down, n );
		if ( Normalize3( n ) < 1e-3f )
			return;
	}
	float delta = ( des - cur ) * (float)( 180.0 / M_PI ) * Clamp01( weight );
	if ( fabs( delta ) > 0.01f )
	{
		// pick the rotation direction that opens/closes the elbow the right way
		mat3_t W;
		AxisAngle( n, delta, W );
		float h1[ 3 ];
		for ( int r = 0; r < 3; r++ )
			h1[ r ] = W[ r ][ 0 ] * eh[ 0 ] + W[ r ][ 1 ] * eh[ 1 ] + W[ r ][ 2 ] * eh[ 2 ] + E[ r ];
		if ( fabs( AngleAt( S, E, h1 ) - des ) > fabs( cur - des ) )
			AxisAngle( n, -delta, W );
		TransformBones( bone, light, foreMask, W, E, NULL );
		BoneOrigin( light, hand, H );
	}

	// 2. swing the arm at the shoulder
	float sh[ 3 ];
	VectorSubtract( H, S, sh );
	TurnToward( bone, light, upperMask, S, sh, st, weight );
}

static void ApplyGunPose( float ( *bone )[ 3 ][ 4 ], float ( *light )[ 3 ][ 4 ], int weaponmodel,
	const float *f, const float *r, const float *u, float now )
{
	const gun_t *gun = GunForModel( weaponmodel );
	bool overlay = ( g_ovSeq >= 0 );	// GMod reload: hands leave the gun

	// smooth weights
	float aimTarget = ( gun && !overlay && cl_fpbody_aimfire->value != 0.0f &&
						( now - g_lastShot < 0.6f || g_attackHeld ) ) ? 1.0f : 0.0f;
	float aimRate = aimTarget > g_aimW ? 14.0f : 5.0f;
	g_aimW += ( aimTarget - g_aimW ) * Clamp01( g_frameTime * aimRate );

	float offTarget = ( gun && gun->down >= 0.0f && !overlay ) ? Clamp01( cl_fpbody_offhand->value ) : 0.0f;
	g_offW += ( offTarget - g_offW ) * Clamp01( g_frameTime * 8.0f );

	if ( !gun || g_skel.rUpper < 0 || g_skel.rHand < 0 )
		return;

	// 1a. pistols: two-handed hold, shooting hand in front of the chest and
	//     the pistol pointed down the view by the wrist
	if ( gun->pistol && g_offW > 0.001f && g_skel.lClav >= 0 && g_skel.rClav >= 0 )
	{
		float ls[ 3 ], rs[ 3 ], target[ 3 ];
		BoneOrigin( light, g_skel.lUpper >= 0 ? g_skel.lUpper : g_skel.lClav, ls );
		BoneOrigin( light, g_skel.rUpper, rs );
		for ( int i = 0; i < 3; i++ )
			target[ i ] = ( ls[ i ] + rs[ i ] ) * 0.5f + f[ i ] * 15.0f - u[ i ] * 4.0f + r[ i ] * 1.5f;
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

	// 2. off hand onto the gun
	if ( g_offW > 0.001f && gun->down >= 0.0f )
	{
		float grip[ 3 ], barrel[ 3 ], target[ 3 ];
		HandToWorldDir( light, g_skel.rHand, gun->grip, grip );
		HandToWorldDir( light, g_skel.rHand, gun->axis, barrel );
		Normalize3( barrel );
		float drop = gun->down + cl_fpbody_grip_down->value;
		for ( int i = 0; i < 3; i++ )
			target[ i ] = light[ g_skel.rHand ][ i ][ 3 ] + grip[ i ] + barrel[ i ] * cl_fpbody_grip_fwd->value;
		target[ 2 ] -= drop;
		ReachArm( bone, light, target, g_offW );
	}
}

// Classic mode keeps Half-Life's own holds, except the big guns whose world
// model has a handle for the left hand: the left wrist is put on it by arm IK.
// The wrist point is in the space of the bone the gun's mesh hangs from,
// measured on the models the mods ship (tools/gmod_anims/lefthand_sim.py).
struct gunhandle_t
{
	const char *model;
	const char *bone;		// player bone the gun mesh is attached to
	float wrist[ 3 ];		// left wrist target in that bone's space
};

static const gunhandle_t g_handles[] =
{
	{ "p_gauss", "Bip01 R Hand", { 16.3f, 8.0f, 2.5f } },		// Half-Life MMod Tau Cannon: side handle
	{ "p_egon", "Bip01 R Arm2", { 20.8f, -4.7f, 8.5f } },		// VAPW Gluon gun: front grip
	{ "p_displacer", "Bip01 R Hand", { 11.0f, 10.5f, 4.2f } },	// Displacer: side bar
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
			cached = &g_handles[ i ];
			break;
		}
	}
	return cached;
}

static void ApplyClassicHandle( float ( *bone )[ 3 ][ 4 ], float ( *light )[ 3 ][ 4 ], int weaponmodel )
{
	const gunhandle_t *h = HandleForModel( weaponmodel );
	bool overlay = ( g_ovSeq >= 0 );
	float want = ( h && !overlay ) ? Clamp01( cl_fpbody_offhand->value ) : 0.0f;
	g_handleW += ( want - g_handleW ) * Clamp01( g_frameTime * 8.0f );
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
		EvalClip( g_cur, now, fade, p, f, r, u );
		EvalClip( g_prev, now, 1.0f - fade, p, f, r, u );
		EvalActions( now, p, f, r, u );

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
		}
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

static bool IsUpperBodyAct( const char *label )
{
	return !strnicmp( label, "gm_gesture_", 11 ) || !strnicmp( label, "gm_reload_", 10 ) ||
		   !strnicmp( label, "gm_shove_", 9 ) || !strnicmp( label, "gm_zombie_attack_", 17 );
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

	if ( !FPBody_Active() || cl_fpbody_gmod->value == 0.0f )
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

int FPAnim_ActCamActive( void )
{
	return g_ovSeq >= 0 && g_ovFull && cl_fpbody_actcam && cl_fpbody_actcam->value != 0.0f;
}
