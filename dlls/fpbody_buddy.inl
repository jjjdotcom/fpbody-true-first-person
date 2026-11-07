// fpbody: the HEV companion (sv_fpbody_buddy 1).
//
// Included at the end of barney.cpp: monster_fpbody_buddy is a security guard
// (CBarney: following, talking, the revolver) in an HEV suit
// (models/fpbody_buddy.mdl) that
//  - can't be hurt (takedamage off, barnacles can't grab him),
//  - fights with an MP5 (its own sequences mp5_idle / mp5_walk / mp5_run /
//    mp5_shoot, three-round bursts) and switches to the revolver for far
//    targets,
//  - follows the player from the start; +use tells him to wait / follow,
//  - teleports next to the player when far behind, out of sight or stuck
//    for a few seconds (ladders, lifts, trains, closing doors).
// The player's think (FPBuddy_PlayerThink, player.cpp PostThink) keeps exactly
// one buddy on every map while sv_fpbody_buddy is 1 and removes it at 0. The
// model is precached at map load (client.cpp ClientPrecache) only when the
// setting is on: switched on mid-map, he arrives on the next map or load.
//
// SDK flavours, defined before the include: FPB_SDK_UPDATED (Half-Life
// Updated: bool returns), FPB_SDK_FI (Featureful: Field Intensity).

#if defined( FPB_SDK_UPDATED ) || defined( FPB_SDK_FI )
#define FPB_BOOL bool
#define FPB_OVERRIDE override
#else
#define FPB_BOOL BOOL
#define FPB_OVERRIDE
#endif
#ifdef FPB_SDK_UPDATED
#define FPB_SAVE bool
#else
#define FPB_SAVE int
#endif

#ifdef FPB_SDK_FI
#define FPB_FOLLOWING() IsFollowingPlayer()
#else
#define FPB_FOLLOWING() IsFollowing()
#endif

#include "player.h"

extern cvar_t sv_fpbody_buddy;

#define FPB_MODEL		"models/fpbody_buddy.mdl"
#define FPB_GUN_GROUP	1
#define FPB_GUN_PISTOL	1	// the revolver in his hand
#define FPB_GUN_MP5		3	// the MP5 (fpbody_buddy.mdl's own submodel)
#define FPB_PISTOL_DIST	640	// targets further than this: the revolver

class CFPBuddy : public CBarney
{
public:
	void Spawn( void ) FPB_OVERRIDE;
	void Precache( void ) FPB_OVERRIDE;
	void RunAI( void ) FPB_OVERRIDE;
	void SetActivity( Activity NewActivity ) FPB_OVERRIDE;
	void StartTask( Task_t *pTask ) FPB_OVERRIDE;
	void RunTask( Task_t *pTask ) FPB_OVERRIDE;
	FPB_BOOL FBecomeProne( void ) FPB_OVERRIDE { return false; }

	void EXPORT BuddyUse( CBaseEntity *pActivator, CBaseEntity *pCaller, USE_TYPE useType, float value );
	void Check( CBaseEntity *pPlayer );
	bool Teleport( CBaseEntity *pPlayer );
	void FireMP5( void );
	void ChooseWeapon( void );

	FPB_SAVE Save( CSave &save ) FPB_OVERRIDE;
	FPB_SAVE Restore( CRestore &restore ) FPB_OVERRIDE;
	static TYPEDESCRIPTION m_SaveData[];

	int m_iWeapon;			// FPB_GUN_MP5 / FPB_GUN_PISTOL
	int m_iStay;			// told to wait with +use
	float m_flLostTime;		// player out of sight since
	float m_flNextTeleport;
	// not saved
	int m_iBurst;
	float m_flNextShot;
	float m_flStuckTime, m_flStuckDist;
};

LINK_ENTITY_TO_CLASS( monster_fpbody_buddy, CFPBuddy )

TYPEDESCRIPTION CFPBuddy::m_SaveData[] =
{
	DEFINE_FIELD( CFPBuddy, m_iWeapon, FIELD_INTEGER ),
	DEFINE_FIELD( CFPBuddy, m_iStay, FIELD_INTEGER ),
	DEFINE_FIELD( CFPBuddy, m_flLostTime, FIELD_TIME ),
	DEFINE_FIELD( CFPBuddy, m_flNextTeleport, FIELD_TIME ),
};

IMPLEMENT_SAVERESTORE( CFPBuddy, CBarney )

static int g_fpBuddyPrecached;

void CFPBuddy::Precache( void )
{
	CBarney::Precache();
	PRECACHE_MODEL( (char *)FPB_MODEL );
	PRECACHE_SOUND( (char *)"hgrunt/gr_mgun1.wav" );
	PRECACHE_SOUND( (char *)"hgrunt/gr_mgun2.wav" );
	g_fpBuddyPrecached = 1;
}

void CFPBuddy::Spawn( void )
{
	CBarney::Spawn();
	SET_MODEL( ENT( pev ), FPB_MODEL );
	UTIL_SetSize( pev, VEC_HUMAN_HULL_MIN, VEC_HUMAN_HULL_MAX );
	pev->takedamage = DAMAGE_NO;		// invincible
	m_fGunDrawn = true;					// the gun is always out
	m_iWeapon = FPB_GUN_MP5;
	SetBodygroup( FPB_GUN_GROUP, m_iWeapon );
	SetUse( &CFPBuddy::BuddyUse );
}

void CFPBuddy::BuddyUse( CBaseEntity *pActivator, CBaseEntity *pCaller, USE_TYPE useType, float value )
{
	FollowerUse( pActivator, pCaller, useType, value );
	m_iStay = !FPB_FOLLOWING();
}

void CFPBuddy::ChooseWeapon( void )
{
	int want = FPB_GUN_MP5;
	if ( m_hEnemy != NULL && ( m_hEnemy->pev->origin - pev->origin ).Length() > FPB_PISTOL_DIST )
		want = FPB_GUN_PISTOL;
	if ( want != m_iWeapon && m_Activity != ACT_RANGE_ATTACK1 )
	{
		m_iWeapon = want;
		if ( m_Activity == ACT_IDLE || m_Activity == ACT_WALK || m_Activity == ACT_RUN )
			SetActivity( m_Activity );	// the stance for the new gun
	}
	SetBodygroup( FPB_GUN_GROUP, m_iWeapon );
}

void CFPBuddy::RunAI( void )
{
	pev->takedamage = DAMAGE_NO;
	m_fGunDrawn = true;
	ChooseWeapon();
	CBarney::RunAI();
}

// MP5: Half-Life's soldier animations (added to the model as mp5_*)
void CFPBuddy::SetActivity( Activity NewActivity )
{
	int oldSeq = pev->sequence;
	float oldFrame = pev->frame;
	CBarney::SetActivity( NewActivity );
	if ( m_iWeapon != FPB_GUN_MP5 )
		return;
	const char *name = NULL;
	switch ( NewActivity )
	{
	case ACT_RANGE_ATTACK1:	name = "mp5_shoot"; break;
	case ACT_WALK:			name = "mp5_walk"; break;
	case ACT_RUN:			name = "mp5_run"; break;
	case ACT_IDLE:			name = "mp5_idle"; break;
	default: break;
	}
	if ( !name )
		return;
	int seq = LookupSequence( name );
	if ( seq < 0 )
		return;
	pev->sequence = seq;
	pev->frame = ( seq == oldSeq ) ? oldFrame : 0;
	ResetSequenceInfo();
	SetYawSpeed();
}

void CFPBuddy::StartTask( Task_t *pTask )
{
	if ( pTask->iTask == TASK_RANGE_ATTACK1 )
	{
		m_iBurst = ( m_iWeapon == FPB_GUN_MP5 ) ? 3 : 0;
		m_flNextShot = gpGlobals->time;
	}
	CBarney::StartTask( pTask );
}

void CFPBuddy::RunTask( Task_t *pTask )
{
	if ( pTask->iTask == TASK_RANGE_ATTACK1 && m_iBurst > 0 && gpGlobals->time >= m_flNextShot && m_hEnemy != NULL )
	{
		FireMP5();
		m_iBurst--;
		m_flNextShot = gpGlobals->time + 0.1;
	}
	CBarney::RunTask( pTask );
}

void CFPBuddy::FireMP5( void )
{
	UTIL_MakeVectors( pev->angles );
	Vector src = pev->origin + Vector( 0, 0, 55 );
	Vector dir = ShootAtEnemy( src );
	Vector ang = UTIL_VecToAngles( dir );
	SetBlending( 0, ang.x );
	pev->effects |= EF_MUZZLEFLASH;
	Vector cone( 0.05234, 0.05234, 0.05234 );	// 6 degrees
#ifdef FPB_SDK_FI
	FireBullets( 1, src, dir, cone, 2048, GetSkillValue( "9mm_bullet" ) );
#else
	FireBullets( 1, src, dir, cone, 2048, BULLET_MONSTER_MP5 );
#endif
	EMIT_SOUND_DYN( ENT( pev ), CHAN_WEAPON, RANDOM_LONG( 0, 1 ) ? "hgrunt/gr_mgun1.wav" : "hgrunt/gr_mgun2.wav", 1, ATTN_NORM, 0, PITCH_NORM );
	CSoundEnt::InsertSound( bits_SOUND_COMBAT, pev->origin, 384, 0.3 );
}

// a standing spot next to the player (behind first), on the floor at the
// player's height; FALSE if there's no room (vents, ladders, mid-air)
static bool FPBuddy_FindSpot( CBaseEntity *pPlayer, Vector &out )
{
	Vector fwd, right, up;
	UTIL_MakeVectorsPrivate( Vector( 0, pPlayer->pev->v_angle.y, 0 ), fwd, right, up );
	float feet = pPlayer->pev->origin.z + pPlayer->pev->mins.z;
	Vector start( pPlayer->pev->origin.x, pPlayer->pev->origin.y, feet + 37 );	// a standing hull's centre
	Vector dirs[ 6 ] = { -fwd, ( right - fwd ).Normalize(), ( -right - fwd ).Normalize(), right, -right, fwd };
	const float dists[ 2 ] = { 80, 56 };
	for ( int d = 0; d < 6; d++ )
	{
		for ( int k = 0; k < 2; k++ )
		{
			TraceResult tr;
			UTIL_TraceHull( start, start + dirs[ d ] * dists[ k ], dont_ignore_monsters, human_hull, pPlayer->edict(), &tr );
			if ( tr.fStartSolid || tr.fAllSolid )
				return false;
			if ( tr.flFraction < 1.0 )
				continue;
			TraceResult down;
			UTIL_TraceHull( tr.vecEndPos, tr.vecEndPos - Vector( 0, 0, 96 ), dont_ignore_monsters, human_hull, pPlayer->edict(), &down );
			if ( down.fStartSolid || down.fAllSolid || down.flFraction >= 1.0 )
				continue;	// a drop
			Vector f = down.vecEndPos - Vector( 0, 0, 36 );
			if ( fabs( f.z - feet ) > 40 )
				continue;
			if ( UTIL_PointContents( f + Vector( 0, 0, 36 ) ) != CONTENTS_EMPTY )
				continue;	// water, slime, lava
			out = f;
			return true;
		}
	}
	return false;
}

bool CFPBuddy::Teleport( CBaseEntity *pPlayer )
{
	Vector spot;
	if ( !FPBuddy_FindSpot( pPlayer, spot ) )
		return false;
	SET_ORIGIN( ENT( pev ), spot );
	pev->velocity = g_vecZero;
	pev->angles.y = pev->ideal_yaw = pPlayer->pev->v_angle.y;
	RouteClear();
	ClearSchedule();
	m_flLostTime = 0;
	m_flStuckTime = 0;
	m_flNextTeleport = gpGlobals->time + 2;
	return true;
}

// every half second from the player's think
void CFPBuddy::Check( CBaseEntity *pPlayer )
{
	if ( m_MonsterState == MONSTERSTATE_SCRIPT || m_MonsterState == MONSTERSTATE_DEAD || pev->deadflag != DEAD_NO )
		return;
	if ( !m_iStay && !FPB_FOLLOWING() && m_MonsterState != MONSTERSTATE_PRONE )
	{
		// back to following, quietly (a new map, or he gave up on a path)
#ifdef FPB_SDK_FI
		StartFollowing( pPlayer, false );
#else
		m_hTargetEnt = pPlayer;
		ClearConditions( bits_COND_CLIENT_PUSH );
		ClearSchedule();
#endif
	}
	if ( m_iStay || !FPB_FOLLOWING() )
		return;
	if ( !( pPlayer->pev->flags & FL_ONGROUND ) || pPlayer->pev->movetype == MOVETYPE_NOCLIP || pPlayer->pev->waterlevel >= 2 )
		return;	// on a ladder, jumping, swimming: wait for the player to land
	float dist = ( pPlayer->pev->origin - pev->origin ).Length();
	float dz = fabs( ( pPlayer->pev->origin.z + pPlayer->pev->mins.z ) - pev->origin.z );
	if ( FVisible( pPlayer ) && dz < 64 )
		m_flLostTime = 0;
	else if ( !m_flLostTime )
		m_flLostTime = gpGlobals->time;
	// stuck: following but not getting closer
	if ( dist < 220 || !m_flStuckTime || dist < m_flStuckDist - 24 )
	{
		m_flStuckTime = gpGlobals->time;
		m_flStuckDist = dist;
	}
	bool tooFar = dist > 800;
	bool outOfSight = m_flLostTime && gpGlobals->time - m_flLostTime > 3 && dist > 160;
	bool noProgress = gpGlobals->time - m_flStuckTime > 5;
	if ( ( tooFar || outOfSight || noProgress ) && gpGlobals->time >= m_flNextTeleport )
	{
		if ( !Teleport( pPlayer ) )
			m_flNextTeleport = gpGlobals->time + 0.5;
	}
}

// client.cpp, ClientPrecache (map load)
void FPBuddy_Precache( void )
{
	g_fpBuddyPrecached = 0;
	if ( sv_fpbody_buddy.value )
		UTIL_PrecacheOther( "monster_fpbody_buddy" );
}

// player.cpp, CBasePlayer::PostThink
void FPBuddy_PlayerThink( CBasePlayer *pPlayer )
{
	static float next;
	if ( gpGlobals->time < next && next - gpGlobals->time < 1 )
		return;
	next = gpGlobals->time + 0.5;
	if ( !pPlayer->IsAlive() || gpGlobals->time < 1.5 )
		return;
	CFPBuddy *keep = NULL;
	CBaseEntity *e = NULL;
	while ( ( e = UTIL_FindEntityByClassname( e, "monster_fpbody_buddy" ) ) != NULL )
	{
		if ( !sv_fpbody_buddy.value || keep )
			UTIL_Remove( e );		// switched off, or one too many (a map visited again)
		else
			keep = (CFPBuddy *)e;
	}
	if ( !sv_fpbody_buddy.value )
		return;
	if ( keep )
	{
		keep->Check( pPlayer );
		return;
	}
	if ( !g_fpBuddyPrecached || !( pPlayer->pev->flags & FL_ONGROUND ) )
		return;
	Vector spot;
	if ( !FPBuddy_FindSpot( pPlayer, spot ) )
		return;
	CBaseEntity *b = CBaseEntity::Create( (char *)"monster_fpbody_buddy", spot, Vector( 0, pPlayer->pev->v_angle.y, 0 ), NULL );
	if ( b )
		( (CFPBuddy *)b )->m_flNextTeleport = gpGlobals->time + 2;
}
