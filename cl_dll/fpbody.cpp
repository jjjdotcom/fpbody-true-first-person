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

#include <string.h>
#include <math.h>

#include "fpbody.h"
#include "fpbody_anim.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

extern int cam_thirdperson;

static cvar_t *cl_fpbody;
static cvar_t *cl_fpbody_forward;
static cvar_t *cl_fpbody_up;
static cvar_t *cl_fpbody_right;
static cvar_t *cl_fpbody_hidehead;
static cvar_t *cl_fpbody_smooth;

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
	if ( cam_thirdperson )
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
	vec3_t viewangles;
	gEngfuncs.GetViewAngles( (float *)viewangles );
	RotateYaw( rel, -viewangles[ YAW ], g_vHeadLocal );
	g_flHeadTime = gEngfuncs.GetClientTime();

	if ( cl_fpbody_hidehead->value != 0.0f )
	{
		float pivotBone[ 3 ], pivotLight[ 3 ];
		int r;

		for ( r = 0; r < 3; r++ )
		{
			pivotBone[ r ] = bonetransform[ g_iHeadBone ][ r ][ 3 ];
			pivotLight[ r ] = lighttransform[ g_iHeadBone ][ r ][ 3 ];
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

int FPBody_GetViewOrigin( struct ref_params_s *pparams, float *outOrigin )
{
	if ( !FPBody_Active() )
		return 0;

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
	g_flLastSmoothTime = now;
	VectorCopy( g_vHeadSmoothed, local );

	// Back to world space using the current predicted origin and view yaw
	float rel[ 3 ];
	RotateYaw( local, pparams->cl_viewangles[ YAW ], rel );

	vec3_t forward, right, up;
	AngleVectors( pparams->cl_viewangles, forward, right, up );

	vec3_t target;
	for ( int i = 0; i < 3; i++ )
	{
		target[ i ] = pparams->simorg[ i ] + rel[ i ]
			+ forward[ i ] * cl_fpbody_forward->value
			+ right[ i ] * cl_fpbody_right->value
			+ up[ i ] * cl_fpbody_up->value;
	}

	// Don't let the camera poke through walls: trace from the normal eye
	// position (which is always inside the player's hull) to the head.
	vec3_t eye;
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
		vec3_t dir;
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
