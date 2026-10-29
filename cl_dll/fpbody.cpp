// fpbody.cpp - "True first person" / body awareness for Half-Life.
//
// How it works
// ------------
// 1. CL_IsThirdPerson() reports "third person" to the engine while the mod is
//    active, so the engine renders the local player's model (player.mdl plus
//    the p_ weapon model in its hands) instead of skipping it.
// 2. When the studio renderer builds that model's skeleton, we:
//      a) record where the head bone ended up, stored relative to the player
//         origin and view yaw, so it can be re-applied to the *current*
//         predicted origin next frame without lag when moving or turning;
//      b) collapse the head bone (and everything parented to it) to a single
//         point, so the inside of the head doesn't fill the screen.
// 3. V_CalcNormalRefdef() puts the camera at that recorded head position
//    (plus a small eye offset) instead of origin + view_ofs. Weapon recoil
//    punch, screen shake, water handling and stair smoothing still apply.
//
// Console variables
//   cl_fpbody          1   enable / disable the mod
//   cl_fpbody_forward  4   eye offset forward of the head joint (units)
//   cl_fpbody_up       3   eye offset above the head joint (units)
//   cl_fpbody_right    0   eye offset to the right of the head joint (units)
//   cl_fpbody_hidehead 1   collapse the head so it doesn't block the view
//   cl_fpbody_smooth   0   0 = raw head motion, higher = smoother (e.g. 15)
//   cl_fpbody_outfit   1   outfit before / after the suit (see FPBody_GetOutfitModel)
//   cl_fpbody_lookdown 8   how far the camera moves forward when looking straight down
//   cl_fpbody_bodypitch 0.5 how much of the view pitch bends the body (aim poses)
//   cl_fpbody_stabilize 0.85 how much of the head's fast sway the camera ignores (0 = none)
//   cl_fpbody_runarms   1   unarmed: the arms swing with the walk / run animation
//   cl_fpbody_classic   1   Half-Life's original player animations (models/fpbody_classic*.mdl), 0 = GMod
//   cl_fpbody_holster   1   weapons we carry are shown on the body (back, hips, thighs)

#include "hud.h"
#include "cl_util.h"
#include "cvardef.h"
#include "const.h"
#include "com_model.h"
#include "studio.h"
#include "entity_state.h"
#include "cl_entity.h"
#include "ref_params.h"
#include "in_defs.h"	// PITCH YAW ROLL
#include "pm_defs.h"
#include "event_api.h"
#include "pmtrace.h"
#include "r_studioint.h"

#include <string.h>
#include <math.h>

#include "fpbody.h"
#include "fpbody_anim.h"
#include "fpbody_game.h"
#include "fpbody_holsters.h"
#include "ammohistory.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

int CAM_IsRealThirdPerson( void );	// in_camera.cpp
extern engine_studio_api_t IEngineStudio;
static void FPBody_Debug_f( void );

static cvar_t *cl_fpbody;
static cvar_t *cl_fpbody_forward;
static cvar_t *cl_fpbody_up;
static cvar_t *cl_fpbody_right;
static cvar_t *cl_fpbody_hidehead;
static cvar_t *cl_fpbody_smooth;
static cvar_t *cl_fpbody_outfit;
static cvar_t *cl_fpbody_lookdown;
static cvar_t *cl_fpbody_bodypitch;
static cvar_t *cl_fpbody_stabilize;
static cvar_t *cl_fpbody_runarms;
static cvar_t *cl_fpbody_classic;
static cvar_t *cl_fpbody_holster;

// Per-frame state from V_CalcRefdef
static int g_bFrameAllowed;

// Head bone cache (per model)
static const studiohdr_t *g_pCachedHdr;
static int g_iHeadBone = -1;
static bool g_bIsHeadPart[ MAXSTUDIOBONES ];

// Last recorded head position, in a frame relative to the player origin and
// rotated so that +X points along the view yaw at the time it was recorded.
static float g_vHeadLocal[ 3 ];
static float g_vHeadSmoothed[ 3 ];
static float g_flHeadTime = -1.0f;
static float g_flLastSmoothTime = -1.0f;
static bool g_bHaveSmoothed;

// How long a recorded head position may be reused (seconds). If the body
// hasn't been drawn for longer than this, fall back to normal eye height.
#define FPBODY_MAX_SAMPLE_AGE 0.25f

void FPBody_Init( void )
{
	cl_fpbody          = gEngfuncs.pfnRegisterVariable( "cl_fpbody", "1", FCVAR_ARCHIVE );
	cl_fpbody_forward  = gEngfuncs.pfnRegisterVariable( "cl_fpbody_forward", "4", FCVAR_ARCHIVE );
	cl_fpbody_up       = gEngfuncs.pfnRegisterVariable( "cl_fpbody_up", "3", FCVAR_ARCHIVE );
	cl_fpbody_right    = gEngfuncs.pfnRegisterVariable( "cl_fpbody_right", "0", FCVAR_ARCHIVE );
	cl_fpbody_hidehead = gEngfuncs.pfnRegisterVariable( "cl_fpbody_hidehead", "1", FCVAR_ARCHIVE );
	cl_fpbody_smooth   = gEngfuncs.pfnRegisterVariable( "cl_fpbody_smooth", "0", FCVAR_ARCHIVE );
	cl_fpbody_outfit   = gEngfuncs.pfnRegisterVariable( "cl_fpbody_outfit", "1", FCVAR_ARCHIVE );
	cl_fpbody_lookdown = gEngfuncs.pfnRegisterVariable( "cl_fpbody_lookdown", "8", FCVAR_ARCHIVE );
	cl_fpbody_bodypitch = gEngfuncs.pfnRegisterVariable( "cl_fpbody_bodypitch", "0.5", FCVAR_ARCHIVE );
	cl_fpbody_stabilize = gEngfuncs.pfnRegisterVariable( "cl_fpbody_stabilize", "0.85", FCVAR_ARCHIVE );
	cl_fpbody_runarms   = gEngfuncs.pfnRegisterVariable( "cl_fpbody_runarms", "1", FCVAR_ARCHIVE );
	cl_fpbody_classic   = gEngfuncs.pfnRegisterVariable( "cl_fpbody_classic", "1", FCVAR_ARCHIVE );
	cl_fpbody_holster   = gEngfuncs.pfnRegisterVariable( "cl_fpbody_holster", "1", FCVAR_ARCHIVE );

	gEngfuncs.pfnAddCommand( "fp_debug", FPBody_Debug_f );

	FPAnim_Init();
}

void FPBody_BeginFrame( struct ref_params_s *pparams )
{
	g_bFrameAllowed = 1;

	if ( pparams->intermission )
		g_bFrameAllowed = 0;

	// trigger_camera and other "view through another entity" sequences
	if ( pparams->viewentity > pparams->maxclients )
		g_bFrameAllowed = 0;

	if ( pparams->spectator )
		g_bFrameAllowed = 0;

	// The client time restarts on map change; throw away stale samples.
	if ( g_flHeadTime > pparams->time )
	{
		g_flHeadTime = -1.0f;
		g_bHaveSmoothed = false;
	}

	if ( FPBody_Active() )
		FPAnim_Frame( pparams );
}

int FPBody_Active( void )
{
	if ( !cl_fpbody || cl_fpbody->value == 0.0f )
		return 0;

	if ( !g_bFrameAllowed )
		return 0;

	// Real third person (the "thirdperson" command) takes over.
	if ( CAM_IsRealThirdPerson() )
		return 0;

	// Spectator / observer modes
	if ( g_iUser1 )
		return 0;

	// When dead, let the game use its normal death camera.
	if ( gHUD.m_Health.m_iHealth <= 0 )
		return 0;

	return 1;
}

// Rotate a vector in the XY plane by the given yaw (degrees).
static void RotateYaw( const float *in, float yaw, float *out )
{
	float rad = yaw * ( M_PI / 180.0 );
	float c = cos( rad );
	float s = sin( rad );

	out[ 0 ] = in[ 0 ] * c - in[ 1 ] * s;
	out[ 1 ] = in[ 0 ] * s + in[ 1 ] * c;
	out[ 2 ] = in[ 2 ];
}

static int StrContainsNoCase( const char *haystack, const char *needle )
{
	size_t n = strlen( needle );

	for ( ; *haystack; haystack++ )
	{
		size_t i;
		for ( i = 0; i < n; i++ )
		{
			char a = haystack[ i ];
			char b = needle[ i ];
			if ( a >= 'A' && a <= 'Z' ) a += 'a' - 'A';
			if ( b >= 'A' && b <= 'Z' ) b += 'a' - 'A';
			if ( a != b )
				break;
		}
		if ( i == n )
			return 1;
	}
	return 0;
}

// Find the head bone of a model and mark every bone parented under it.
static void CacheHeadBone( const studiohdr_t *hdr )
{
	if ( hdr == g_pCachedHdr )
		return;

	g_pCachedHdr = hdr;
	g_iHeadBone = -1;
	memset( g_bIsHeadPart, 0, sizeof( g_bIsHeadPart ) );

	const mstudiobone_t *pbones = (const mstudiobone_t *)( (const byte *)hdr + hdr->boneindex );
	int numbones = hdr->numbones;
	if ( numbones > MAXSTUDIOBONES )
		numbones = MAXSTUDIOBONES;

	int i;

	// Standard Half-Life skeletons (player.mdl, gordon.mdl, MP models) use
	// "Bip01 Head". Fall back to any bone with "head" in its name.
	for ( i = 0; i < numbones; i++ )
	{
		if ( !stricmp( pbones[ i ].name, "Bip01 Head" ) )
		{
			g_iHeadBone = i;
			break;
		}
	}

	if ( g_iHeadBone < 0 )
	{
		for ( i = 0; i < numbones; i++ )
		{
			if ( StrContainsNoCase( pbones[ i ].name, "head" ) )
			{
				g_iHeadBone = i;
				break;
			}
		}
	}

	if ( g_iHeadBone < 0 )
		return;

	// Bones are stored parent-first, so one pass marks the whole subtree.
	g_bIsHeadPart[ g_iHeadBone ] = true;
	for ( i = g_iHeadBone + 1; i < numbones; i++ )
	{
		int parent = pbones[ i ].parent;
		if ( parent >= 0 && g_bIsHeadPart[ parent ] )
			g_bIsHeadPart[ i ] = true;
	}
}

// Squash a bone to a point at its joint: every vertex weighted to it ends up
// at the same spot, so the geometry vanishes.
static void CollapseBone( float ( *transform )[ 3 ][ 4 ], int bone, const float *pivot )
{
	for ( int r = 0; r < 3; r++ )
	{
		transform[ bone ][ r ][ 0 ] = 0.0f;
		transform[ bone ][ r ][ 1 ] = 0.0f;
		transform[ bone ][ r ][ 2 ] = 0.0f;
		transform[ bone ][ r ][ 3 ] = pivot[ r ];
	}
}

void FPBody_ProcessPlayerBones( int playerNumber, struct cl_entity_s *ent, void *studiohdr,
	float ( *bonetransform )[ 3 ][ 4 ], float ( *lighttransform )[ 3 ][ 4 ], int weaponmodel )
{
	if ( !FPBody_Active() )
		return;

	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	if ( !local || playerNumber != local->index )
		return;

	const studiohdr_t *hdr = (const studiohdr_t *)studiohdr;
	if ( !hdr )
		return;

	CacheHeadBone( hdr );

	// Procedural animations (reload, draw, use, ...) pose the arms and body
	// first, so the camera and the weapon in the hands follow them.
	FPAnim_ApplyBones( studiohdr, bonetransform, lighttransform, g_iHeadBone, weaponmodel );

	// Full-body acts are watched from behind, so keep the head
	if ( FPAnim_ActCamActive() )
		return;

	if ( g_iHeadBone < 0 )
		return;

	// The light transform is the bone-to-world matrix in both the hardware
	// and the software renderer (in software the bone transform is in screen
	// space), so read the world position from it.
	float headWorld[ 3 ];
	headWorld[ 0 ] = lighttransform[ g_iHeadBone ][ 0 ][ 3 ];
	headWorld[ 1 ] = lighttransform[ g_iHeadBone ][ 1 ][ 3 ];
	headWorld[ 2 ] = lighttransform[ g_iHeadBone ][ 2 ][ 3 ];

	float rel[ 3 ];
	rel[ 0 ] = headWorld[ 0 ] - ent->origin[ 0 ];
	rel[ 1 ] = headWorld[ 1 ] - ent->origin[ 1 ];
	rel[ 2 ] = headWorld[ 2 ] - ent->origin[ 2 ];

	// The upper body is twisted toward the view direction by the gait code,
	// so storing it relative to the view yaw keeps the head stable when the
	// view turns between frames.
	Vector viewangles;
	gEngfuncs.GetViewAngles( (float *)viewangles );
	RotateYaw( rel, -viewangles[ YAW ], g_vHeadLocal );
	g_flHeadTime = gEngfuncs.GetClientTime();

	if ( cl_fpbody_hidehead->value != 0.0f )
	{
		float pivotBone[ 3 ], pivotLight[ 3 ];
		int r;

		// Squash the head down to the neck joint, so the triangles joining the
		// head to the collar flatten into the collar instead of fanning up
		// into the view
		const mstudiobone_t *pbones = (const mstudiobone_t *)( (const byte *)hdr + hdr->boneindex );
		int pivot = pbones[ g_iHeadBone ].parent >= 0 ? pbones[ g_iHeadBone ].parent : g_iHeadBone;
		for ( r = 0; r < 3; r++ )
		{
			pivotBone[ r ] = bonetransform[ pivot ][ r ][ 3 ];
			pivotLight[ r ] = lighttransform[ pivot ][ r ][ 3 ];
		}

		int numbones = hdr->numbones;
		if ( numbones > MAXSTUDIOBONES )
			numbones = MAXSTUDIOBONES;

		for ( int i = 0; i < numbones; i++ )
		{
			if ( !g_bIsHeadPart[ i ] )
				continue;

			CollapseBone( bonetransform, i, pivotBone );
			if ( lighttransform != bonetransform )
				CollapseBone( lighttransform, i, pivotLight );
		}
	}
}

// Camera behind the player while a full-body act plays (mouse orbits it)
static int ActCamOrigin( struct ref_params_s *pparams, float *outOrigin )
{
	Vector forward, right, up, eye, target;
	AngleVectors( pparams->cl_viewangles, forward, right, up );
	VectorAdd( pparams->simorg, pparams->viewheight, eye );
	for ( int i = 0; i < 3; i++ )
		target[ i ] = eye[ i ] - forward[ i ] * 90.0f + up[ i ] * 6.0f;

	pmtrace_t tr;
	gEngfuncs.pEventAPI->EV_SetUpPlayerPrediction( false, true );
	gEngfuncs.pEventAPI->EV_PushPMStates();
	gEngfuncs.pEventAPI->EV_SetSolidPlayers( -1 );
	gEngfuncs.pEventAPI->EV_SetTraceHull( 2 );
	gEngfuncs.pEventAPI->EV_PlayerTrace( eye, target, PM_WORLD_ONLY, -1, &tr );
	gEngfuncs.pEventAPI->EV_PopPMStates();

	if ( tr.fraction < 1.0f )
	{
		Vector dir;
		VectorSubtract( target, eye, dir );
		float len = VectorNormalize( dir );
		float dist = len * tr.fraction - 4.0f;
		if ( dist < 0.0f )
			dist = 0.0f;
		VectorMA( eye, dist, dir, target );
	}
	VectorCopy( target, outOrigin );
	return 1;
}

int FPBody_GetViewOrigin( struct ref_params_s *pparams, float *outOrigin )
{
	if ( !FPBody_Active() )
		return 0;

	if ( FPAnim_ActCamActive() )
		return ActCamOrigin( pparams, outOrigin );

	if ( g_flHeadTime < 0.0f )
		return 0;

	float now = gEngfuncs.GetClientTime();
	if ( now - g_flHeadTime > FPBODY_MAX_SAMPLE_AGE || now < g_flHeadTime )
	{
		g_bHaveSmoothed = false;
		return 0;
	}

	// Optional smoothing of the head motion (exponential, frame-rate independent)
	float local[ 3 ];
	float smooth = cl_fpbody_smooth->value;
	if ( smooth > 0.0f && g_bHaveSmoothed )
	{
		float dt = now - g_flLastSmoothTime;
		if ( dt < 0.0f ) dt = 0.0f;
		float k = 1.0f - (float)exp( -smooth * dt );
		for ( int i = 0; i < 3; i++ )
			g_vHeadSmoothed[ i ] += ( g_vHeadLocal[ i ] - g_vHeadSmoothed[ i ] ) * k;
	}
	else
	{
		VectorCopy( g_vHeadLocal, g_vHeadSmoothed );
		g_bHaveSmoothed = true;
	}
	VectorCopy( g_vHeadSmoothed, local );

	// Stabilizer: follow a slow average of the head position and keep only part
	// of the fast motion around it (the side to side sway and forward / back
	// bob of every step). Vertical bob is damped less, it reads as footsteps.
	{
		static float base[ 3 ];
		static bool haveBase = false;
		float stab = cl_fpbody_stabilize ? cl_fpbody_stabilize->value : 0.0f;
		if ( stab < 0.0f ) stab = 0.0f;
		if ( stab > 1.0f ) stab = 1.0f;
		float dt = now - g_flLastSmoothTime;
		if ( !haveBase || dt < 0.0f || dt > 0.3f )
		{
			VectorCopy( local, base );
			haveBase = true;
		}
		else
		{
			float k = 1.0f - (float)exp( -dt / 0.4f );
			for ( int i = 0; i < 3; i++ )
				base[ i ] += ( local[ i ] - base[ i ] ) * k;
		}
		const float keep[ 3 ] = { 1.0f - stab, 1.0f - stab, 1.0f - stab * 0.6f };	// forward, left, up
		for ( int i = 0; i < 3; i++ )
			local[ i ] = base[ i ] + ( local[ i ] - base[ i ] ) * keep[ i ];
	}
	g_flLastSmoothTime = now;

	// Back to world space using the current predicted origin and view yaw
	float rel[ 3 ];
	RotateYaw( local, pparams->cl_viewangles[ YAW ], rel );

	// Offsets in the level (yaw only) frame, so looking down doesn't sink the
	// camera into the chest; looking down moves the eyes forward over the body
	// instead, like a real neck does.
	float yaw = pparams->cl_viewangles[ YAW ] * ( M_PI / 180.0f );
	float pitch = pparams->cl_viewangles[ PITCH ];
	if ( pitch > 180.0f ) pitch -= 360.0f;
	float down = sin( pitch * ( M_PI / 180.0f ) );
	if ( down < 0.0f ) down = 0.0f;
	Vector forward( (float)cos( yaw ), (float)sin( yaw ), 0.0f );
	Vector right( (float)sin( yaw ), (float)-cos( yaw ), 0.0f );
	float fwd = cl_fpbody_forward->value + cl_fpbody_lookdown->value * down;

	Vector target;
	for ( int i = 0; i < 3; i++ )
	{
		target[ i ] = pparams->simorg[ i ] + rel[ i ]
			+ forward[ i ] * fwd
			+ right[ i ] * cl_fpbody_right->value;
	}
	target[ 2 ] += cl_fpbody_up->value;

	// Don't let the camera poke through walls: trace from the normal eye
	// position (which is always inside the player's hull) to the head.
	Vector eye;
	VectorAdd( pparams->simorg, pparams->viewheight, eye );

	pmtrace_t tr;
	gEngfuncs.pEventAPI->EV_SetUpPlayerPrediction( false, true );
	gEngfuncs.pEventAPI->EV_PushPMStates();
	gEngfuncs.pEventAPI->EV_SetSolidPlayers( -1 );
	gEngfuncs.pEventAPI->EV_SetTraceHull( 2 );	// point hull
	gEngfuncs.pEventAPI->EV_PlayerTrace( eye, target, PM_WORLD_ONLY, -1, &tr );
	gEngfuncs.pEventAPI->EV_PopPMStates();

	if ( tr.fraction < 1.0f && !tr.startsolid )
	{
		Vector dir;
		VectorSubtract( target, eye, dir );
		float len = VectorNormalize( dir );
		float dist = len * tr.fraction - 2.0f;	// stay 2 units off the wall
		if ( dist < 0.0f )
			dist = 0.0f;
		VectorMA( eye, dist, dir, target );
	}
	else if ( tr.startsolid )
	{
		VectorCopy( eye, target );
	}

	VectorCopy( target, outOrigin );
	return 1;
}

int FPBody_Classic( void )
{
	return ( cl_fpbody_classic && cl_fpbody_classic->value != 0.0f ) ? 1 : 0;
}

// Unarmed in first person, the walk / run animation drives the whole body
// (arms swinging); with a weapon the arms keep holding it. Set by the studio
// renderer around the local player's bone setup.
static int g_iWholeBodyGait;

void FPBody_SetWholeBodyGait( int playerNumber, int weaponmodel, int overlay )
{
	g_iWholeBodyGait = 0;
	if ( !FPBody_Active() || overlay || weaponmodel != 0 )
		return;
	if ( !cl_fpbody_runarms || cl_fpbody_runarms->value == 0.0f )
		return;
	if ( FPBody_Classic() )
		return;		// Half-Life's own gaits weren't made to be seen above the hips
	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	if ( local && playerNumber == local->index )
		g_iWholeBodyGait = 1;
}

int FPBody_WholeBodyGait( void )
{
	return g_iWholeBodyGait;
}

float FPBody_Stabilize( void )
{
	return cl_fpbody_stabilize ? cl_fpbody_stabilize->value : 0.0f;
}

// In first person the view pitch only partly bends the body (the aim poses
// bow the whole torso, which pushes the hips out behind it). Called before
// the player blend is worked out.
void FPBody_PrePlayerBlend( int playerNumber, struct cl_entity_s *ent )
{
	if ( !ent || !FPBody_Active() )
		return;
	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	if ( !local || playerNumber != local->index )
		return;
	float k = cl_fpbody_bodypitch ? cl_fpbody_bodypitch->value : 1.0f;
	if ( FPBody_Classic() )
		k = 1.0f;		// classic: the aim poses follow the whole view pitch, like the original
	if ( k < 0.0f ) k = 0.0f;
	if ( k > 1.0f ) k = 1.0f;
	ent->angles[ PITCH ] *= k;
}

// Keep our own body upright: for sequences without an aim blend range (no
// weapon, swimming...) the renderer would tilt the whole model with the view
// pitch, which in first person swings the legs up in front of the camera.
void FPBody_LevelBody( int playerNumber, struct cl_entity_s *ent )
{
	if ( !ent || !FPBody_Active() )
		return;
	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	if ( !local || playerNumber != local->index )
		return;
	ent->angles[ PITCH ] = 0;
}

// The local player's outfit (single player only):
//   not suited: models/fpbody_presuit.mdl, or Gordon's lab coat
//               models/fpbody_scientist.mdl (Half-Life)
//   suited:     models/fpbody_suit.mdl if the game has one (the blue / green
//               HEV suits of Blue Shift and Opposing Force), else the normal model
// What "suited" means is set per game in fpbody_game.h.
static struct model_s *FPBody_TryModel( const char *name, int &state )
{
	// state: 0 = not tried, 1 = loaded, -1 = missing
	if ( state < 0 )
		return NULL;
	// Mod_ForName loads any model file (CL_LoadModel only finds models the map precached)
	struct model_s *m = IEngineStudio.Mod_ForName( name, 0 );
	if ( !m )
	{
		if ( state == 0 )
			gEngfuncs.Con_DPrintf( "fpbody: %s not found\n", name );
		state = -1;
		return NULL;
	}
	state = 1;
	return m;
}

int FPBody_IsSuited( void )
{
#if FPBODY_SUIT_FROM_ARMOR
	return gHUD.m_Battery.GetArmor() > 0;
#else
	return ( gHUD.m_iWeaponBits & ( 1 << WEAPON_SUIT ) ) ? 1 : 0;
#endif
}

// what the last call decided, for fp_debug
static const char *g_szOutfitReason = "not called yet";
static struct model_s *g_pOutfitLast;

struct model_s *FPBody_GetOutfitModel( int playerNumber )
{
	// [classic][model]: suit, presuit, scientist (Half-Life's older name), plain body
	static const char *names[ 2 ][ 4 ] =
	{
		{ "models/fpbody_suit.mdl", "models/fpbody_presuit.mdl", "models/fpbody_scientist.mdl", NULL },
		{ "models/fpbody_classic_suit.mdl", "models/fpbody_classic_presuit.mdl", NULL, "models/fpbody_classic.mdl" },
	};
	static int states[ 2 ][ 4 ];

	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	if ( !local || playerNumber != local->index )
		return NULL;

	if ( !FPBody_Active() )
	{
		g_szOutfitReason = "first person body not active";
		return g_pOutfitLast = NULL;
	}

	// cl_fpbody_classic 1: Half-Life's original player animations instead of the GMod ones
	int c = ( cl_fpbody_classic && cl_fpbody_classic->value != 0.0f ) ? 1 : 0;

	struct model_s *m = NULL;
	if ( cl_fpbody_outfit && cl_fpbody_outfit->value != 0.0f )
	{
		if ( FPBody_IsSuited() )
		{
			m = FPBody_TryModel( names[ c ][ 0 ], states[ c ][ 0 ] );
			g_szOutfitReason = m ? "suited: suit outfit" : "suited, no suit outfit model";
		}
		else
		{
			m = FPBody_TryModel( names[ c ][ 1 ], states[ c ][ 1 ] );
			if ( !m && names[ c ][ 2 ] )
				m = FPBody_TryModel( names[ c ][ 2 ], states[ c ][ 2 ] );
			g_szOutfitReason = m ? "not suited: pre-suit outfit" : "not suited, no outfit model";
		}
	}
	else
		g_szOutfitReason = "cl_fpbody_outfit 0";

	if ( !m && names[ c ][ 3 ] )
		m = FPBody_TryModel( names[ c ][ 3 ], states[ c ][ 3 ] );

	// Never let the engine pick a multiplayer model (the "model" setting) for
	// our own body: only the mod's models have the fpbody/GMod animations.
	if ( !m )
		m = local->model;
	return g_pOutfitLast = m;
}

static void FPBody_Debug_f( void )
{
	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	gEngfuncs.Con_Printf( "fpbody: active %d, maxclients %d, suited %d, armor %d, weaponbits %08x\n",
		FPBody_Active(), gEngfuncs.GetMaxClients(), FPBody_IsSuited(), gHUD.m_Battery.GetArmor(),
		(unsigned int)( gHUD.m_iWeaponBits & 0xffffffff ) );
	gEngfuncs.Con_Printf( "fpbody: outfit: %s -> %s\n", g_szOutfitReason,
		g_pOutfitLast ? g_pOutfitLast->name : "(engine's choice)" );
	if ( local )
		gEngfuncs.Con_Printf( "fpbody: local player %d, entity model %s, sequence %d, gait %d\n", local->index,
			local->model ? local->model->name : "none", local->curstate.sequence, local->curstate.gaitsequence );
	if ( g_pOutfitLast )
	{
		studiohdr_t *h = (studiohdr_t *)IEngineStudio.Mod_Extradata( g_pOutfitLast );
		if ( h )
			gEngfuncs.Con_Printf( "fpbody: drawn model %s: %d bones, %d sequences, %d body parts, %d textures\n",
				h->name, h->numbones, h->numseq, h->numbodyparts, h->numtextures );
	}
}

// ---------------------------------------------------------------------------
// Holsters
// ---------------------------------------------------------------------------

#define NUM_HOLSTER_DEFS ( (int)( sizeof( g_holsterDefs ) / sizeof( g_holsterDefs[ 0 ] ) ) )

// does a space separated list of class names contain this one
static bool NameInList( const char *list, const char *name )
{
	size_t len = strlen( name );
	const char *p = list;
	while ( *p )
	{
		while ( *p == ' ' ) p++;
		const char *e = p;
		while ( *e && *e != ' ' ) e++;
		if ( (size_t)( e - p ) == len && !strnicmp( p, name, len ) )
			return true;
		p = e;
	}
	return false;
}

static bool OwnsWeaponNamed( const char *list )
{
	unsigned long long bits = (unsigned long long)gHUD.m_iWeaponBits;
	if ( sizeof( gHUD.m_iWeaponBits ) < 8 )
		bits &= 0xffffffffULL;
	for ( int id = 1; id < MAX_WEAPONS && id < 64; id++ )
	{
		if ( !( ( bits >> id ) & 1ULL ) )
			continue;
		WEAPON *w = gWR.GetWeapon( id );
		if ( w && w->szName[ 0 ] && NameInList( list, w->szName ) )
			return true;
	}
	return false;
}

int FPBody_GetHolsters( int playerNumber, int weaponmodel, void *playerStudioHdr, fpholster_t *out, int max )
{
	static int modelState[ NUM_HOLSTER_DEFS ];
	static int anchorOf[ NUM_HOLSTER_DEFS ];
	static const studiohdr_t *anchorHdr;

	if ( !cl_fpbody_holster || cl_fpbody_holster->value == 0.0f || !FPBody_Active() || !playerStudioHdr )
		return 0;
	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	if ( !local || playerNumber != local->index )
		return 0;

	const studiohdr_t *hdr = (const studiohdr_t *)playerStudioHdr;
	if ( hdr != anchorHdr )
	{
		anchorHdr = hdr;
		const mstudiobone_t *pbones = (const mstudiobone_t *)( (const byte *)hdr + hdr->boneindex );
		for ( int i = 0; i < NUM_HOLSTER_DEFS; i++ )
		{
			anchorOf[ i ] = -1;
			for ( int b = 0; b < hdr->numbones && b < MAXSTUDIOBONES; b++ )
				if ( !stricmp( pbones[ b ].name, g_holsterDefs[ i ].bone ) )
				{
					anchorOf[ i ] = b;
					break;
				}
		}
	}

	const char *held = NULL;
	if ( weaponmodel )
	{
		struct model_s *wm = IEngineStudio.GetModelByIndex( weaponmodel );
		if ( wm )
			held = wm->name;
	}

	int n = 0;
	for ( int i = 0; i < NUM_HOLSTER_DEFS && n < max; i++ )
	{
		const fpholster_def_t *d = &g_holsterDefs[ i ];
		if ( anchorOf[ i ] < 0 )
			continue;
		if ( held && !stricmp( held, d->model ) )
			continue;			// it's in our hands
		if ( !OwnsWeaponNamed( d->weapons ) )
			continue;
		struct model_s *m = FPBody_TryModel( d->model, modelState[ i ] );
		if ( !m )
			continue;
		out[ n ].model = m;
		out[ n ].anchor = anchorOf[ i ];
		out[ n ].local = d->local;
		out[ n ].keep = d->keep;
		n++;
	}
	return n;
}

void FPBody_HolsterMatrix( const fpholster_t *h, const float ( *playerLight )[ 3 ][ 4 ], float ( *out )[ 4 ] )
{
	const float ( *A )[ 4 ] = playerLight[ h->anchor ];
	const float ( *L )[ 4 ] = h->local;
	for ( int r = 0; r < 3; r++ )
	{
		for ( int c = 0; c < 3; c++ )
			out[ r ][ c ] = A[ r ][ 0 ] * L[ 0 ][ c ] + A[ r ][ 1 ] * L[ 1 ][ c ] + A[ r ][ 2 ] * L[ 2 ][ c ];
		out[ r ][ 3 ] = A[ r ][ 0 ] * L[ 0 ][ 3 ] + A[ r ][ 1 ] * L[ 1 ][ 3 ] + A[ r ][ 2 ] * L[ 2 ][ 3 ] + A[ r ][ 3 ];
	}
}

void FPBody_HolsterHideBones( const fpholster_t *h, void *studiohdr, float ( *bonetransform )[ 3 ][ 4 ],
	float ( *lighttransform )[ 3 ][ 4 ] )
{
	if ( !h->keep || !studiohdr )
		return;
	const studiohdr_t *hdr = (const studiohdr_t *)studiohdr;
	for ( int b = 0; b < hdr->numbones && b < 32; b++ )
	{
		if ( h->keep & ( 1u << b ) )
			continue;
		float pivot[ 3 ] = { bonetransform[ b ][ 0 ][ 3 ], bonetransform[ b ][ 1 ][ 3 ], bonetransform[ b ][ 2 ][ 3 ] };
		CollapseBone( bonetransform, b, pivot );
		if ( lighttransform != bonetransform )
		{
			float lp[ 3 ] = { lighttransform[ b ][ 0 ][ 3 ], lighttransform[ b ][ 1 ][ 3 ], lighttransform[ b ][ 2 ][ 3 ] };
			CollapseBone( lighttransform, b, lp );
		}
	}
}
