// fpbody: the HEV companion (sv_fpbody_buddy 1).
//
// Included at the end of barney.cpp: monster_fpbody_buddy is a security guard
// (CBarney: following, talking, the revolver) in an HEV suit
// (models/fpbody_buddy.mdl) that
//  - goes down instead of dying (sv_fpbody_down): on his back at the end of
//    his health, until you revive him (hold +use: CPR) or for 60 seconds;
//    your bullets don't hurt him, barnacles can't grab him,
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
// FPB_DECAY (Half-Life: Decay, tools/port/fpbody_decay.py): the companion is
// Colette (models/fpbody_colette.mdl), always there in single player, and she
// does her half of the puzzles - Decay's triggers for "player 2" take her
// (FPDecay_Id) and she goes to them herself (DecayGoal).

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

#include "weapons.h"
#include "player.h"

extern cvar_t sv_fpbody_buddy;
extern cvar_t sv_fpbody_buddy_solid;
// iuser4 tag: pm_shared leaves the companion out of the player's collision
// (sv_fpbody_buddy_solid 0), so you walk through him
#define FPB_PASSTHRU	0x46504253
#define FPB_SETSOLID()	( pev->iuser4 = sv_fpbody_buddy_solid.value != 0 ? 0 : FPB_PASSTHRU )

#ifdef FPB_DECAY
#define FPB_MODEL		"models/fpbody_colette.mdl"
#define FPB_ON()		( gpGlobals->maxClients == 1 )	// Colette: always, in single player
#else
#define FPB_MODEL		"models/fpbody_buddy.mdl"
#define FPB_ON()		( sv_fpbody_buddy.value != 0 )
#endif
// the companion's model is a Barney that carries a minigun (the HEV Barney
// Automatic Weapons Pack's Minigunner, tools/gmod_anims/make_minigun_buddy.py):
// body part 1 is its gun, submodel 1 the minigun in his hands; his firing
// stance is the model's own (ACT_RANGE_ATTACK1). Long bursts, one minigun
// sound per burst (sound/fpbody/minigun.wav)
#define FPB_GUN_GROUP	1
#define FPB_GUN_PISTOL	1	// the minigun in his hands
#define FPB_GUN_MP5		1	// (one gun: the minigun)
#define FPB_BURST		12	// rounds per burst
#define FPB_BURST_GAP	0.06f	// seconds between them
#define FPB_GUN_SOUND	"fpbody/minigun.wav"
#define FPB_PISTOL_DIST	640	// targets further than this: the revolver

#include "weapons.h"
#include "player.h"
#ifdef FPB_SDK_UPDATED
#define FPB_TDRET bool
#else
#define FPB_TDRET int
#endif
#define FPB_DOWN_HP		100.0f		// his health before he goes down (sv_fpbody_down)
class CFPBuddy;
static void FPDown_BuddyHealth( CFPBuddy *b );
static bool FPDown_BuddyHelp( CFPBuddy *b, CBaseEntity *pPlayer );
static bool FPDown_BuddyHit( CFPBuddy *b, entvars_t *pevInflictor, entvars_t *pevAttacker, float flDamage );
static void FPDown_PlayerThink( CBasePlayer *pl );

class CFPBuddy : public CBarney
{
public:
	void Spawn( void ) FPB_OVERRIDE;
	void Precache( void ) FPB_OVERRIDE;
	void RunAI( void ) FPB_OVERRIDE;
	void SetActivity( Activity NewActivity ) FPB_OVERRIDE;
	void StartTask( Task_t *pTask ) FPB_OVERRIDE;
	void RunTask( Task_t *pTask ) FPB_OVERRIDE;
	void HandleAnimEvent( MonsterEvent_t *pEvent ) FPB_OVERRIDE;
	FPB_BOOL FBecomeProne( void ) FPB_OVERRIDE { return false; }

	void EXPORT BuddyUse( CBaseEntity *pActivator, CBaseEntity *pCaller, USE_TYPE useType, float value );
	void Check( CBaseEntity *pPlayer );
	bool Teleport( CBaseEntity *pPlayer );
	void FireMP5( void );
	void ChooseWeapon( void );
	// downed / reviving (sv_fpbody_down, the end of this file)
	void GoDown( void );
	void GetUp( void );
	void EXPORT DownThink( void );
	void EXPORT ReviveThink( void );
	bool StartRevive( CBaseEntity *pPlayer );
	void PlaySeq( const char *name, float rate );
	bool HelpPlayer( CBasePlayer *pl );
#if defined( FPB_SDK_FI )
	TakeDamageResult TakeDamage( entvars_t *pevInflictor, entvars_t *pevAttacker, const DamageInfo &info ) override
	{
		if ( FPDown_BuddyHit( this, pevInflictor, pevAttacker, info.damage ) )
			return TakeDamageResult();
		return CBarney::TakeDamage( pevInflictor, pevAttacker, info );
	}
#else
	FPB_TDRET TakeDamage( entvars_t *pevInflictor, entvars_t *pevAttacker, float flDamage, int bitsDamageType ) FPB_OVERRIDE
	{
		if ( FPDown_BuddyHit( this, pevInflictor, pevAttacker, flDamage ) )
			return 0;
		return CBarney::TakeDamage( pevInflictor, pevAttacker, flDamage, bitsDamageType );
	}
#endif
#ifdef FPB_DECAY
	// Colette's own voice (Decay's sound/colette, COL_ sentences) instead of Barney's
	void ColetteTalk( void );
	void AlertSound( void ) FPB_OVERRIDE;
	void PainSound( void ) FPB_OVERRIDE;
	void DeathSound( void ) FPB_OVERRIDE;
	void DeclineFollowing( void ) FPB_OVERRIDE;
	Schedule_t *GetSchedule( void ) FPB_OVERRIDE;
	bool DecayGoal( CBaseEntity *pPlayer );
	EHANDLE m_hGoal;			// the puzzle trigger she's going to / standing in
	float m_flGoalTime, m_flGoalSeen;
#endif

	FPB_SAVE Save( CSave &save ) FPB_OVERRIDE;
	FPB_SAVE Restore( CRestore &restore ) FPB_OVERRIDE;
	static TYPEDESCRIPTION m_SaveData[];

	int m_iWeapon;			// FPB_GUN_MP5 / FPB_GUN_PISTOL
	int m_iStay;			// told to wait with +use
	float m_flLostTime;		// player out of sight since
	float m_flNextTeleport;
	float m_flHP;			// his own health (pev->health is kept high: see RunAI)
	float m_flDownTime;		// downed since (0 = up)
	float m_flHintTime;		// next "Hold USE to revive" (not saved)
	float m_flHitTime;		// last hurt (health comes back after a while; not saved)
	float m_flRegenTime;
	float m_flHelpUntil;		// helping the player up until (not saved)
	float m_flUseSeen;		// CPR can start again from (after it was stopped)
	float m_flUpTime;		// getting up: back to the fight then
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
	DEFINE_FIELD( CFPBuddy, m_flHP, FIELD_FLOAT ),
	DEFINE_FIELD( CFPBuddy, m_flDownTime, FIELD_TIME ),
	DEFINE_FIELD( CFPBuddy, m_flUpTime, FIELD_TIME ),
};

IMPLEMENT_SAVERESTORE( CFPBuddy, CBarney )

static int g_fpBuddyPrecached;

void CFPBuddy::Precache( void )
{
#ifdef FPB_SDK_UPDATED
	// CBarney's own, without models/barney.mdl: every model counts against the
	// map's 512 limit (Opposing Force's of4a4 is right at it)
	static const char *const snd[] = { "barney/ba_attack1.wav", "barney/ba_attack2.wav", "barney/ba_pain1.wav",
		"barney/ba_pain2.wav", "barney/ba_pain3.wav", "barney/ba_die1.wav", "barney/ba_die2.wav", "barney/ba_die3.wav" };
	for ( int i = 0; i < (int)( sizeof( snd ) / sizeof( snd[ 0 ] ) ); i++ )
		PRECACHE_SOUND( (char *)snd[ i ] );
	TalkInit();
	CTalkMonster::Precache();
#else
	CBarney::Precache();
#endif
	PRECACHE_MODEL( (char *)FPB_MODEL );
#ifdef FPB_DECAY
	ColetteTalk();
#endif
	PRECACHE_SOUND( (char *)FPB_GUN_SOUND );
	PRECACHE_SOUND( (char *)"hgrunt/gr_mgun1.wav" );
	PRECACHE_SOUND( (char *)"hgrunt/gr_mgun2.wav" );
	g_fpBuddyPrecached = 1;
}

void CFPBuddy::Spawn( void )
{
#ifdef FPB_SDK_UPDATED
	// CBarney::Spawn with our model (it sets models/barney.mdl, which we don't precache)
	Precache();
	SET_MODEL( ENT( pev ), FPB_MODEL );
	UTIL_SetSize( pev, VEC_HUMAN_HULL_MIN, VEC_HUMAN_HULL_MAX );
	pev->solid = SOLID_SLIDEBOX;
	pev->movetype = MOVETYPE_STEP;
	m_bloodColor = BLOOD_COLOR_RED;
	pev->health = gSkillData.barneyHealth;
	pev->view_ofs = Vector( 0, 0, 50 );
	m_flFieldOfView = VIEW_FIELD_WIDE;
	m_MonsterState = MONSTERSTATE_NONE;
	pev->body = 0;
	m_afCapability = bits_CAP_HEAR | bits_CAP_TURN_HEAD | bits_CAP_DOORS_GROUP;
	MonsterInit();
#else
	CBarney::Spawn();
	SET_MODEL( ENT( pev ), FPB_MODEL );
	UTIL_SetSize( pev, VEC_HUMAN_HULL_MIN, VEC_HUMAN_HULL_MAX );
#endif
	pev->takedamage = DAMAGE_NO;		// invincible (sv_fpbody_down 0)
	FPB_SETSOLID();
	m_flHP = FPB_DOWN_HP;
	m_flDownTime = m_flUpTime = 0;
	m_fGunDrawn = true;					// the gun is always out
	m_iWeapon = FPB_GUN_MP5;
	SetBodygroup( FPB_GUN_GROUP, m_iWeapon );
	SetUse( &CFPBuddy::BuddyUse );
}

void CFPBuddy::BuddyUse( CBaseEntity *pActivator, CBaseEntity *pCaller, USE_TYPE useType, float value )
{
	if ( m_flDownTime )
	{
		if ( pActivator && pActivator->IsPlayer() )
			StartRevive( pActivator );	// down: CPR
		return;
	}
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
	FPB_SETSOLID();
	FPDown_BuddyHealth( this );
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
		m_iBurst = FPB_BURST;
		m_flNextShot = gpGlobals->time;
		EMIT_SOUND_DYN( ENT( pev ), CHAN_WEAPON, FPB_GUN_SOUND, 1, ATTN_NORM, 0, PITCH_NORM );
	}
	CBarney::StartTask( pTask );
}

void CFPBuddy::RunTask( Task_t *pTask )
{
	if ( pTask->iTask == TASK_RANGE_ATTACK1 && m_iBurst > 0 && gpGlobals->time >= m_flNextShot && m_hEnemy != NULL )
	{
		FireMP5();
		m_iBurst--;
		m_flNextShot = gpGlobals->time + FPB_BURST_GAP;
	}
	CBarney::RunTask( pTask );
}

// the model's own firing events (Barney's: a revolver shot and its sound)
// are left out - the bursts above are the minigun
void CFPBuddy::HandleAnimEvent( MonsterEvent_t *pEvent )
{
	if ( pEvent->event == 3 )		// BARNEY_AE_SHOOT
		return;
	CBarney::HandleAnimEvent( pEvent );
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
	if ( m_flDownTime || m_flUpTime )
		return;							// down, or getting up
	if ( FPDown_BuddyHelp( this, pPlayer ) )
		return;							// on his way to revive the player
#ifdef FPB_DECAY
	if ( DecayGoal( pPlayer ) )
		return;		// at (or on her way to) her half of a puzzle
#endif
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
	if ( FPB_ON() )
		UTIL_PrecacheOther( "monster_fpbody_buddy" );
}

// player.cpp, CBasePlayer::PostThink
void FPBuddy_PlayerThink( CBasePlayer *pPlayer )
{
	FPDown_PlayerThink( pPlayer );		// downed / revived (every frame)
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
		if ( !FPB_ON() || keep )
			UTIL_Remove( e );		// switched off, or one too many (a map visited again)
		else
			keep = (CFPBuddy *)e;
	}
	if ( !FPB_ON() )
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
	{
		( (CFPBuddy *)b )->m_flNextTeleport = gpGlobals->time + 2;
#ifdef FPB_DECAY
		// the map's "player 2 has spawned" triggers (trigger_clientspawn)
		CBaseEntity *t = NULL;
		while ( ( t = UTIL_FindEntityByClassname( t, "trigger_clientspawn" ) ) != NULL )
			t->Use( b, b, USE_TOGGLE, 0 );
#endif
	}
}

#ifdef FPB_DECAY
// Decay's puzzles: 1 = Gina (the player), 2 = Colette, 0 = anyone else
int FPDecay_Id( CBaseEntity *pEnt )
{
	if ( !pEnt )
		return 0;
	if ( pEnt->IsPlayer() )
		return ( (CBasePlayer *)pEnt )->m_iDecayId;
	if ( FClassnameIs( pEnt->pev, "monster_fpbody_buddy" ) )
		return 2;
	return 0;
}

#define FPB_SPECIFICPLAYER	256		// Decay's "check the player index" trigger flag

static bool FPDecay_Inside( CBaseEntity *t, const Vector &p, float pad )
{
	return p.x >= t->pev->absmin.x - pad && p.x <= t->pev->absmax.x + pad &&
		   p.y >= t->pev->absmin.y - pad && p.y <= t->pev->absmax.y + pad &&
		   p.z >= t->pev->absmin.z - pad && p.z <= t->pev->absmax.z + pad;
}

// gina_inside -> colette_inside, cross_p1in -> cross_p2in, player1 -> player2
// fpbody_decay solo (sv_fpbody_decay_solo 1, the default): Gina does it all -
// Decay's "both players" triggers fire for her alone and her half of a pair
// fires Colette's half too (triggers.cpp)
bool FPDecay_Solo( void )
{
	return gpGlobals->maxClients == 1 && CVAR_GET_FLOAT( "sv_fpbody_decay_solo" ) != 0.0f;
}

void FPDecay_Partner( const char *in, char *out, int size )
{
	static const char *const from[] = { "gina", "Gina", "p1", "P1", "player1" };
	static const char *const to[] = { "colette", "Colette", "p2", "P2", "player2" };
	out[ 0 ] = 0;
	if ( !in || !in[ 0 ] )
		return;
	for ( int k = 0; k < 5; k++ )
	{
		const char *hit = strstr( in, from[ k ] );
		if ( hit )
		{
			snprintf( out, size, "%.*s%s%s", (int)( hit - in ), in, to[ k ], hit + strlen( from[ k ] ) );
			return;
		}
	}
}

// Colette's voice: her lines from Decay's two-player game (bot Colette) -
// following / waiting, "freeze" at enemies, after a kill - and nothing of
// Barney's chatter (she has no idle talk, questions or answers)
void CFPBuddy::ColetteTalk( void )
{
	for ( int i = 0; i < TLK_CGROUPS; i++ )
		m_szGrp[ i ] = NULL;
	m_szGrp[ TLK_USE ] = "COL_OK";
	m_szGrp[ TLK_UNUSE ] = "COL_WAIT";
	m_szGrp[ TLK_STOP ] = "COL_STOP";
	m_szGrp[ TLK_NOSHOOT ] = "COL_MAD";
	static const char *const snd[] = { "colette/colette_pain0.wav", "colette/colette_pain1.wav",
		"colette/colette_pain2.wav", "colette/colette_pain3.wav", "colette/colette_die0.wav",
		"colette/colette_die1.wav", "colette/colette_die2.wav" };
	for ( int i = 0; i < (int)( sizeof( snd ) / sizeof( snd[ 0 ] ) ); i++ )
		PRECACHE_SOUND( (char *)snd[ i ] );
}

void CFPBuddy::AlertSound( void )
{
	if ( m_hEnemy != 0 && FOkToSpeak() )
		PlaySentence( "COL_ATTACK", RANDOM_FLOAT( 2.8f, 3.2f ), VOL_NORM, ATTN_IDLE );
}

void CFPBuddy::PainSound( void )
{
	if ( gpGlobals->time < m_painTime )
		return;
	m_painTime = gpGlobals->time + RANDOM_FLOAT( 0.5f, 0.75f );
	char snd[ 64 ];
	snprintf( snd, sizeof( snd ), "colette/colette_pain%d.wav", (int)RANDOM_LONG( 0, 3 ) );
	EMIT_SOUND_DYN( ENT( pev ), CHAN_VOICE, snd, 1.0f, ATTN_NORM, 0, GetVoicePitch() );
}

void CFPBuddy::DeathSound( void )
{
	char snd[ 64 ];
	snprintf( snd, sizeof( snd ), "colette/colette_die%d.wav", (int)RANDOM_LONG( 0, 2 ) );
	EMIT_SOUND_DYN( ENT( pev ), CHAN_VOICE, snd, 1.0f, ATTN_NORM, 0, GetVoicePitch() );
}

void CFPBuddy::DeclineFollowing( void )
{
	PlaySentence( "COL_STOP", 2, VOL_NORM, ATTN_NORM );
}

Schedule_t *CFPBuddy::GetSchedule( void )
{
	// her line after a kill, said first so Barney's ("BA_KILL") finds her talking
	if ( HasConditions( bits_COND_ENEMY_DEAD ) && FOkToSpeak() )
		PlaySentence( "COL_KILL", 4, VOL_NORM, ATTN_NORM );
	return CBarney::GetSchedule();
}

// Colette's half of a puzzle: a "both players" trigger Gina stands in, or the
// Colette trigger that pairs (by name) with the Gina trigger she stands in.
// Colette runs there - or appears there if she can't get there in a few
// seconds - and stays until Gina has left hers for a moment.
bool CFPBuddy::DecayGoal( CBaseEntity *pPlayer )
{
	Vector pp = pPlayer->pev->origin;
	CBaseEntity *goal = NULL;
	static const char *const kinds[] = { "trigger_multiple", "trigger_once" };
	for ( int k = 0; k < 2 && !goal; k++ )
	{
		CBaseEntity *t = NULL;
		while ( !goal && ( t = UTIL_FindEntityByClassname( t, kinds[ k ] ) ) != NULL )
		{
			if ( !( t->pev->spawnflags & FPB_SPECIFICPLAYER ) || t->pev->solid == SOLID_NOT || !FPDecay_Inside( t, pp, 0 ) )
				continue;
			int idx = ( (CBaseToggle *)t )->m_iPlayerIndex;
			if ( idx == 0 )
				goal = t;			// both of us, here
			else if ( idx == 1 )
			{
				char want[ 64 ], wantTarget[ 64 ];
				FPDecay_Partner( STRING( t->pev->targetname ), want, sizeof( want ) );
				FPDecay_Partner( STRING( t->pev->target ), wantTarget, sizeof( wantTarget ) );
				for ( int j = 0; j < 2 && !goal; j++ )
				{
					CBaseEntity *u = NULL;
					while ( ( u = UTIL_FindEntityByClassname( u, kinds[ j ] ) ) != NULL )
					{
						if ( !( u->pev->spawnflags & FPB_SPECIFICPLAYER ) || ( (CBaseToggle *)u )->m_iPlayerIndex != 2 || u->pev->solid == SOLID_NOT )
							continue;
						if ( ( want[ 0 ] && FStrEq( want, STRING( u->pev->targetname ) ) ) ||
							 ( wantTarget[ 0 ] && FStrEq( wantTarget, STRING( u->pev->target ) ) ) )
						{
							goal = u;
							break;
						}
					}
				}
			}
		}
	}
	if ( goal )
		m_flGoalSeen = gpGlobals->time;
	else if ( m_hGoal != NULL && gpGlobals->time - m_flGoalSeen < 1.5 )
		goal = m_hGoal;		// Gina stepped out for a moment
	if ( !goal )
	{
		m_hGoal = NULL;
		return false;
	}
	// where to stand: the middle of the trigger, on the floor
	Vector c = ( goal->pev->absmin + goal->pev->absmax ) * 0.5;
	TraceResult tr;
	UTIL_TraceHull( Vector( c.x, c.y, goal->pev->absmax.z - 36 ), Vector( c.x, c.y, goal->pev->absmin.z - 64 ),
		dont_ignore_monsters, human_hull, ENT( pev ), &tr );
	Vector spot = tr.vecEndPos - Vector( 0, 0, 36 );
	if ( (CBaseEntity *)m_hGoal != goal )
	{
		m_hGoal = goal;
		m_flGoalTime = gpGlobals->time;
		m_hTargetEnt = NULL;			// stop following
		ClearSchedule();
		MoveToLocation( ACT_RUN, 2, spot );
	}
	if ( FPDecay_Inside( goal, pev->origin + Vector( 0, 0, 36 ), 0 ) )
	{
		// there. A monster standing still doesn't touch triggers (only moving
		// does), and Decay's "both players inside" triggers need both touches
		// within a tenth of a second: touch it every frame, like Gina does
		goal->Touch( this );
		return true;
	}
	if ( gpGlobals->time - m_flGoalTime > 4 && !tr.fStartSolid && !tr.fAllSolid )
	{
		SET_ORIGIN( ENT( pev ), spot );	// couldn't get there: appear there
		pev->velocity = g_vecZero;
		RouteClear();
		ClearSchedule();
		m_flGoalTime = gpGlobals->time;
	}
	return true;
}
#endif

// ---------------------------------------------------------------------------
// Downed and revived (sv_fpbody_down 1, single player, while the companion is
// on the map).
//
// The player: a hit that would kill him leaves him on his back at 1 health
// instead (not drowning, crushed, under water or a kill zone's 1000). He can
// look round and shoot - his pistol if he has one - but not move, and takes no
// more damage; enemies stop seeing him. The companion comes over and gives him
// CPR (Half-Life's scientist reviving a security guard: cprscientist on the
// companion, cprbarney on the player's body) and after 5 seconds he's up with
// 30 health; nobody comes: he gets up by himself after 60 seconds.
// The companion: the same for him (his own 100 health; the player's shots
// don't hurt him). Hold +use on him: you kneel and give him CPR for 5 seconds
// (let go and you stop); left there he gets up by himself after 60 seconds.
// The client is told with the FPDown message (0 up, 1 down, 2 down and being
// revived, 3 giving the companion CPR): it plays fm_down / fm_down_up / fm_cpr
// on the body (cl_dll/fpbody_anim.cpp, tools/gmod_anims/add_cpr.py).
// ---------------------------------------------------------------------------

extern cvar_t sv_fpbody_down;

#define FPD_MARK		0x4650444E	// player's iuser4 while down ("FPDN"): a saved game remembers it
#define FPD_SELF		60.0f		// up by yourself after this
#define FPD_CPR			8.0f		// CPR this long (the whole of the scientist's CPR: 160 frames at 20 fps)
#define FPD_UP_HP		30.0f		// health after a revive
#define FPD_BIG			10000.0f	// the companion's pev->health (his own is m_flHP)

int gmsgFPDown;
static float s_pDownTime;			// the player is down since (0 = up)
static float s_pCprTime;			// the companion's CPR on him started (0 = none)
static EHANDLE s_hPatient;			// the companion the player gives CPR
static float s_pPatientTime;
static float s_pHelpUntil;			// the player helps the companion up until (0 = not)
static int s_downMsg = -1;
static float s_downMsgTime;

// player.cpp, LinkUserMessages
void FPDown_LinkMessages( void )
{
	if ( !gmsgFPDown )
		gmsgFPDown = REG_USER_MSG( "FPDown", 1 );
}

static void FPDown_Send( CBasePlayer *pl, int st )
{
	if ( !gmsgFPDown )
		return;
	float t = gpGlobals->time;
	if ( st == s_downMsg && t >= s_downMsgTime && t - s_downMsgTime < 1.0f )
		return;							// (again every second, for a loaded game)
	s_downMsg = st;
	s_downMsgTime = t;
	MESSAGE_BEGIN( MSG_ONE, gmsgFPDown, NULL, pl->pev );
		WRITE_BYTE( st );
	MESSAGE_END();
}

static CFPBuddy *FPDown_Buddy( void )
{
	CBaseEntity *e = UTIL_FindEntityByClassname( NULL, "monster_fpbody_buddy" );
	if ( !e || e->pev->deadflag != DEAD_NO )
		return NULL;
	return (CFPBuddy *)e;
}

static CBasePlayer *FPDown_Player( void )
{
	CBaseEntity *p = UTIL_PlayerByIndex( 1 );
	return ( p && p->IsPlayer() ) ? (CBasePlayer *)p : NULL;
}

void CFPBuddy::PlaySeq( const char *name, float rate )
{
	int seq = LookupSequence( name );
	if ( seq < 0 )
		seq = LookupSequence( "lying_on_back" );
	if ( seq < 0 )
		return;
	pev->sequence = seq;
	pev->frame = 0;
	ResetSequenceInfo();
	pev->framerate = rate;
}

// ---- the player ----------------------------------------------------------

static void FPDown_PlayerUp( CBasePlayer *pl )
{
	s_pDownTime = 0;
	s_pCprTime = 0;
	pl->pev->iuser4 = 0;
	pl->pev->flags &= ~( FL_FROZEN | FL_NOTARGET );
	if ( pl->IsAlive() && pl->pev->health < FPD_UP_HP )
		pl->pev->health = FPD_UP_HP;
	FPDown_Send( pl, 0 );
}

static void FPDown_PlayerDown( CBasePlayer *pl )
{
	s_pHelpUntil = 0;
	s_pDownTime = gpGlobals->time;
	s_pCprTime = 0;
	pl->pev->health = 1;
	pl->pev->iuser4 = FPD_MARK;
	pl->pev->flags |= FL_FROZEN | FL_NOTARGET;
	pl->pev->velocity.x = pl->pev->velocity.y = 0;
	// the pistol out, if he has one
	static const char *const pistols[] = { "weapon_9mmhandgun", "weapon_glock", "weapon_eagle", "weapon_357", "weapon_python", NULL };
	for ( int i = 0; pistols[ i ]; i++ )
	{
		if ( pl->m_pActiveItem && FClassnameIs( pl->m_pActiveItem->pev, pistols[ i ] ) )
			break;
		if ( pl->HasNamedPlayerItem( pistols[ i ] ) )
		{
			pl->SelectItem( pistols[ i ] );
			break;
		}
	}
	FPDown_Send( pl, 1 );
}

// player.cpp, CBasePlayer::TakeDamage, first thing: true = no damage
bool FPDown_OnDamage( CBasePlayer *pl, entvars_t *pevInflictor, entvars_t *pevAttacker, float flDamage, int bitsDamageType )
{
	if ( sv_fpbody_down.value == 0.0f || gpGlobals->maxClients > 1 || !pl->IsAlive() || flDamage <= 0.0f )
		return false;
	if ( s_pDownTime )
		return true;						// down: no more damage
	if ( pl->pev->takedamage == DAMAGE_NO || ( pl->pev->flags & FL_GODMODE ) )
		return false;
	// what reaches his health (the suit takes 80% of the rest, two armour per point)
	float h = flDamage;
	if ( pl->pev->armorvalue > 0 && !( bitsDamageType & ( DMG_FALL | DMG_DROWN ) ) )
	{
		float hp = flDamage * 0.2f, armor = ( flDamage - hp ) * 0.5f;
		if ( armor > pl->pev->armorvalue )
			hp = flDamage - pl->pev->armorvalue * 2.0f;
		h = hp;
	}
	if ( pl->pev->health - h >= 1.0f )
		return false;						// not a killing blow
	if ( flDamage >= 1000.0f || ( bitsDamageType & ( DMG_CRUSH | DMG_DROWN ) ) || pl->pev->waterlevel >= 2 )
		return false;						// kill zones, crushers, water: dead
	if ( !FPDown_Buddy() )
		return false;						// nobody to help: dead as ever
	FPDown_PlayerDown( pl );
	return true;
}

// every frame (FPBuddy_PlayerThink)
static void FPDown_PlayerThink( CBasePlayer *pl )
{
	float t = gpGlobals->time;
	if ( !s_pDownTime && pl->pev->iuser4 == FPD_MARK )
	{
		if ( pl->IsAlive() && sv_fpbody_down.value != 0.0f )
			s_pDownTime = t;				// a game saved lying down
		else
			pl->pev->iuser4 = 0;
	}
	if ( s_pDownTime )
	{
		if ( !pl->IsAlive() || sv_fpbody_down.value == 0.0f )
		{
			FPDown_PlayerUp( pl );
			return;
		}
		if ( s_pDownTime > t || t - s_pDownTime > FPD_SELF + 5.0f )
			s_pDownTime = t;				// the clock started again (a new map, a loaded game)
		pl->pev->flags |= FL_FROZEN | FL_NOTARGET;
		pl->pev->velocity.x = pl->pev->velocity.y = 0;
		if ( pl->pev->health > 1 )
			pl->pev->health = 1;
		if ( t - s_pDownTime >= FPD_SELF )
		{
			FPDown_PlayerUp( pl );			// got up by himself
			return;
		}
		FPDown_Send( pl, s_pCprTime ? 2 : 1 );
		return;
	}
	if ( s_pHelpUntil )
	{
		if ( t < s_pHelpUntil && s_pHelpUntil - t < 10.0f && pl->IsAlive() )
		{
			pl->pev->flags |= FL_FROZEN;	// helping him up
			pl->pev->velocity.x = pl->pev->velocity.y = 0;
			FPDown_Send( pl, 4 );
			return;
		}
		s_pHelpUntil = 0;
		pl->pev->flags &= ~FL_FROZEN;
	}
	CBaseEntity *patient = s_hPatient;
	FPDown_Send( pl, patient ? 3 : 0 );
}

// ---- the companion helps the player -------------------------------------

// the spot beside a patient's chest for the reviver: the reviver's feet and
// yaw. The CPR (Half-Life's cprscientist) kneels with the hands 18 units to
// the reviver's right; the patient lies on his back, the head 21 units behind
// his origin, the chest 8 (cprbarney)
static bool FPDown_CprSpot( const Vector &patientFeet, float patientYaw, edict_t *ignore, Vector &feet, float &yaw )
{
	Vector f, r, u;
	UTIL_MakeVectorsPrivate( Vector( 0, patientYaw, 0 ), f, r, u );
	Vector chest = patientFeet - f * 8.4f;
	for ( int side = 0; side < 2; side++ )
	{
		Vector left = side ? r : -r;		// the patient's left, then his right
		Vector spot = chest + left * 18.0f;
		TraceResult tr;
		UTIL_TraceHull( spot + Vector( 0, 0, 37 ), spot + Vector( 0, 0, 37 ), ignore_monsters, human_hull, ignore, &tr );
		if ( tr.fStartSolid || tr.fAllSolid )
			continue;
		feet = spot;
		yaw = side ? patientYaw + 180.0f : patientYaw;
		return true;
	}
	return false;
}

bool CFPBuddy::HelpPlayer( CBasePlayer *pl )
{
	Vector feet;
	float yaw;
	Vector pfeet = pl->pev->origin + Vector( 0, 0, pl->pev->mins.z );
	if ( !FPDown_CprSpot( pfeet, pl->pev->v_angle.y, ENT( pev ), feet, yaw ) )
		return false;
	SET_ORIGIN( ENT( pev ), feet );
	pev->velocity = g_vecZero;
	pev->angles = Vector( 0, yaw, 0 );
	pev->ideal_yaw = yaw;
	RouteClear();
	ClearSchedule();
	m_hEnemy = NULL;
	PlaySeq( "cprscientist", 1.0f );
	s_pCprTime = gpGlobals->time;
	SetThink( &CFPBuddy::ReviveThink );
	pev->nextthink = gpGlobals->time + 0.1f;
	return true;
}

// Check (every half second): the player is down - go and help
static bool FPDown_BuddyHelp( CFPBuddy *b, CBaseEntity *pPlayer )
{
	if ( !s_pDownTime || !pPlayer || !pPlayer->IsPlayer() )
		return false;
	if ( s_pCprTime )
		return true;						// at it
	CBasePlayer *pl = (CBasePlayer *)pPlayer;
	float dist = ( pl->pev->origin - b->pev->origin ).Length2D();
	if ( ( dist < 160 && b->FVisible( pl ) ) || gpGlobals->time - s_pDownTime > 4.0f )
	{
		if ( b->HelpPlayer( pl ) )
			return true;
	}
	return false;							// still on the way (following)
}

void CFPBuddy::ReviveThink( void )
{
	pev->nextthink = gpGlobals->time + 0.1f;
	StudioFrameAdvance();
	float t = gpGlobals->time;
	if ( m_flHelpUntil > 0 )
	{
		// helping him up (the scientist's cprscientistrevive), then back to it
		if ( t >= m_flHelpUntil || m_flHelpUntil - t > 10.0f || m_fSequenceFinished )
		{
			m_flHelpUntil = 0;
			ClearSchedule();
			SetThink( &CBaseMonster::CallMonsterThink );
		}
		return;
	}
	if ( m_fSequenceFinished )
	{
		pev->frame = 0;
		m_fSequenceFinished = false;
	}
	CBasePlayer *pl = FPDown_Player();
	bool done = !s_pDownTime || !pl || !pl->IsAlive();
	if ( !done && t - s_pCprTime >= FPD_CPR )
	{
		FPDown_PlayerUp( pl );				// back on his feet
		s_pCprTime = 0;
		if ( LookupSequence( "cprscientistrevive" ) >= 0 )
		{
			PlaySeq( "cprscientistrevive", 2.0f );
			pev->frame = 64;				// from where the guard starts getting up
			m_flHelpUntil = t + 3.9f;
			return;
		}
		done = true;
	}
	if ( done )
	{
		s_pCprTime = 0;
		ClearSchedule();
		SetThink( &CBaseMonster::CallMonsterThink );
	}
}

// ---- the companion goes down -------------------------------------------------

// RunAI: hurt by others, not killed (his own health is m_flHP)
static void FPDown_BuddyHealth( CFPBuddy *b )
{
	if ( sv_fpbody_down.value == 0.0f || gpGlobals->maxClients > 1 )
	{
		b->pev->takedamage = DAMAGE_NO;		// invincible, as before
		return;
	}
	b->pev->takedamage = DAMAGE_AIM;
	b->pev->health = FPD_BIG;
	if ( b->m_flHP <= 0 || b->m_flHP > FPB_DOWN_HP )
		b->m_flHP = FPB_DOWN_HP;
	// sv_fpbody_buddy_regen: his health comes back (per second), 5 s after the last hit
	static cvar_t regen = { "sv_fpbody_buddy_regen", "5", FCVAR_ARCHIVE };
	static bool registered;
	if ( !registered )
	{
		CVAR_REGISTER( &regen );
		registered = true;
	}
	float t = gpGlobals->time;
	float dt = ( b->m_flRegenTime > 0 && t > b->m_flRegenTime ) ? t - b->m_flRegenTime : 0.0f;
	b->m_flRegenTime = t;
	if ( b->m_flHitTime > t )
		b->m_flHitTime = 0;					// a new map / a loaded game
	if ( regen.value > 0 && dt < 1.0f && t - b->m_flHitTime >= 5.0f && b->m_flHP < FPB_DOWN_HP )
	{
		b->m_flHP += regen.value * dt;
		if ( b->m_flHP > FPB_DOWN_HP )
			b->m_flHP = FPB_DOWN_HP;
	}
}

// TakeDamage: true = none (down, the player's own shots, switched off)
static bool FPDown_BuddyHit( CFPBuddy *b, entvars_t *pevInflictor, entvars_t *pevAttacker, float flDamage )
{
	if ( sv_fpbody_down.value == 0.0f || gpGlobals->maxClients > 1 || b->m_flDownTime || b->m_flUpTime )
		return true;
	if ( pevAttacker && ( pevAttacker->flags & FL_CLIENT ) )
		return true;						// no friendly fire
	if ( pevInflictor && !FNullEnt( pevInflictor->owner ) && ( pevInflictor->owner->v.flags & FL_CLIENT ) )
		return true;						// his grenades, his rockets
	b->pev->health = FPD_BIG;				// never killed by the hit itself
	b->m_flHP -= flDamage;
	b->m_flHitTime = gpGlobals->time;
	if ( b->m_flHP <= 0 )
	{
		b->GoDown();
		return true;
	}
	return false;
}

void CFPBuddy::GoDown( void )
{
	m_flHP = 0;
	m_flDownTime = gpGlobals->time;
	m_flUseSeen = 0;
	m_flHintTime = 0;
	m_flUpTime = 0;
	pev->takedamage = DAMAGE_NO;
	pev->flags |= FL_NOTARGET;
	pev->velocity = g_vecZero;
	m_hEnemy = NULL;
	RouteClear();
	ClearSchedule();
	DeathSound();
	PlaySeq( "cprbarney", 1.0f );
	SetThink( &CFPBuddy::DownThink );
	pev->nextthink = gpGlobals->time + 0.1f;
}

void CFPBuddy::GetUp( void )
{
	m_flDownTime = 0;
	m_flHP = FPB_DOWN_HP;
	PlaySeq( "cprbarneyrevive", 2.0f );
	pev->frame = 64;						// a quarter in: past the lying still (of 256)
	m_flUpTime = gpGlobals->time + 4.1f;	// (the rest, at double speed)
}

// the player kneels beside him and gives him CPR (his +use)
bool CFPBuddy::StartRevive( CBaseEntity *pPlayer )
{
	CBasePlayer *pl = (CBasePlayer *)pPlayer;
	if ( !m_flDownTime || m_flUpTime || s_pDownTime || (CBaseEntity *)s_hPatient )
		return false;
	if ( !pl || !pl->IsPlayer() || !pl->IsAlive() )
		return false;
	Vector feet;
	float yaw;
	if ( FPDown_CprSpot( pev->origin, pev->angles.y, pl->edict(), feet, yaw ) )
	{
		TraceResult tr;
		UTIL_TraceHull( feet + Vector( 0, 0, 36 ), feet + Vector( 0, 0, 36 ), ignore_monsters, human_hull, pl->edict(), &tr );
		if ( !tr.fStartSolid && !tr.fAllSolid )
		{
			SET_ORIGIN( pl->edict(), feet + Vector( 0, 0, 36 ) );	// kneel at his side
			pl->pev->angles = Vector( 0, yaw, 0 );
			pl->pev->v_angle = Vector( 25, yaw, 0 );	// looking down at him
			pl->pev->fixangle = 1;
		}
	}
	// no room at his side: CPR from where you stand
	pl->pev->velocity = g_vecZero;
	pl->pev->flags |= FL_FROZEN;
	s_hPatient = this;
	g_engfuncs.pfnServerPrint( "fpbody CPR started\n" );
	s_pPatientTime = gpGlobals->time;
	m_flHintTime = 0;
	FPDown_Send( pl, 3 );
	return true;
}

static void FPDown_EndPatient( CBasePlayer *pl )
{
	s_hPatient = NULL;
	if ( pl && !s_pDownTime )
	{
		pl->pev->flags &= ~FL_FROZEN;
		FPDown_Send( pl, 0 );
	}
}

void CFPBuddy::DownThink( void )
{
	pev->nextthink = gpGlobals->time + 0.1f;
	StudioFrameAdvance();
	float t = gpGlobals->time;
	CBasePlayer *pl = FPDown_Player();
	if ( m_flUpTime )
	{
		// getting up: back to the fight when he's on his feet
		if ( t >= m_flUpTime || m_flUpTime - t > 10.0f )
		{
			m_flUpTime = 0;
			pev->takedamage = DAMAGE_AIM;
			pev->flags &= ~FL_NOTARGET;
			pev->health = FPD_BIG;
			ClearSchedule();
			m_IdealMonsterState = MONSTERSTATE_ALERT;
			SetThink( &CBaseMonster::CallMonsterThink );
		}
		return;
	}
	if ( m_fSequenceFinished )
	{
		pev->frame = 0;						// lying there, breathing
		m_fSequenceFinished = false;
	}
	if ( m_flDownTime > t || t - m_flDownTime > FPD_SELF + 5.0f )
		m_flDownTime = t;					// the clock started again
	// +use next to him starts CPR (no need to aim at him: he's on the floor);
	// it then runs to the end by itself - jump or crouch to stop
	if ( pl && (CBaseEntity *)s_hPatient == NULL && !s_pDownTime && pl->IsAlive() )
	{
		Vector d = pev->origin - pl->pev->origin;
		d.z = 0;
		float dist = d.Length();
		if ( m_flUseSeen > t + 2.0f )
			m_flUseSeen = 0;				// (a new map)
		if ( ( pl->pev->button & IN_USE ) && dist < 100 && fabs( pev->origin.z - pl->pev->origin.z ) < 72 && t >= m_flUseSeen )
			StartRevive( pl );
		else if ( dist < 200 && t >= m_flHintTime )
		{
			ClientPrint( pl->pev, HUD_PRINTCENTER, "Press USE to revive" );
			m_flHintTime = t + 1.5f;
		}
	}
	if ( (CBaseEntity *)s_hPatient == this )
	{
		const char *why = NULL;
		if ( !pl || !pl->IsAlive() )
			why = "you died";
		else if ( s_pDownTime )
			why = "you went down";
		else if ( ( pl->pev->origin - pev->origin ).Length() > 160 )
			why = "too far from him";
		else if ( pl->pev->button & ( IN_JUMP | IN_DUCK ) )
			why = "jump / crouch";
		bool keep = !why;
		if ( why )
		{
			g_engfuncs.pfnServerPrint( UTIL_VarArgs( (char *)"fpbody CPR stopped: %s\n", why ) );
			m_flUseSeen = t + 1.0f;			// (not straight back in)
		}
		if ( keep && t >= m_flHintTime )
		{
			int left = (int)( FPD_CPR - ( t - s_pPatientTime ) + 0.99f );
			ClientPrint( pl->pev, HUD_PRINTCENTER, UTIL_VarArgs( (char *)"Reviving... %d", left > 0 ? left : 1 ) );
			m_flHintTime = t + 1.0f;
		}
		if ( !keep )
			FPDown_EndPatient( pl );		// stopped
		else
		{
			pl->pev->flags |= FL_FROZEN;
			pl->pev->velocity = g_vecZero;
			if ( t - s_pPatientTime >= FPD_CPR )
			{
				// revived: the player helps him up (fm_cpr_up), still in place
				s_hPatient = NULL;
				s_pHelpUntil = t + 3.9f;
				FPDown_Send( pl, 4 );
				GetUp();					// revived
				return;
			}
		}
	}
	if ( t - m_flDownTime >= FPD_SELF )
		GetUp();							// up by himself
}
