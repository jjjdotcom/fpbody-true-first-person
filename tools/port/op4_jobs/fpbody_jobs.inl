/***
*
*	fpbody_jobs.inl - Opposing Force: do the engineer's and the medic's jobs
*	yourself (included from player.cpp).
*
*	Where the story needs an engineer to torch a door open or a medic to patch
*	up a wounded soldier, the player can walk up and press use to do it, playing
*	the soldiers' own scripted animations (fm_job_* in the player model, from
*	hgrunt_torch / hgrunt_medic): pull the torch, cut, kick the door in; kneel
*	and give the shot. The map's own events fire as they would have for the
*	NPC (sparks, lights, the door, the "he's dead, game over" relays cleared).
*
*	Whoever starts first does it: the engineer / medic can still be recruited
*	and do it as usual. While one of them is on the way to (or in) the job's
*	scripts, the player can't start it; once the player starts, those scripts
*	are removed so the NPC doesn't walk over and do it again.
*
*	Anywhere else, crouch + use on a hurt friendly soldier / guard / scientist
*	gives him a shot (fm_job_heal) that patches him up to full health.
*
*	The player is held still while it plays; the phase goes to the client in
*	the move state (FPM_JOB in fuser4), which plays the matching animation.
*
****/
#include "scripted.h"

enum { FJE_PHASE, FJE_FIRE, FJE_SOUND, FJE_PROP, FJE_CUT, FJE_HEAL, FJE_END, FJE_HUSH };

struct FPJobEvt
{
	float t;
	int type;
	int arg;
	const char *str;
};

struct FPJobDef
{
	const char *map;
	bool heal;					// heal the soldier named npc (else torch the door)
	const char *npc;			// heal: the wounded soldier
	const char *woundedSeq;		// heal: the script he lies in while he waits for the medic
	Vector stand;				// door: where the engineer stands (the player is moved here)
	Vector cutLo, cutHi;		// door: the face the torch runs over
	float cutFrom, cutTo;		// door: when the torch is cutting
	const char *marker;			// gone = the job's been done
	const char *remove[ 6 ];	// the NPC's scripts for the job, removed when the player takes it
	Vector search;				// ...and the nameless scripted_sequence that sends him there
	const FPJobEvt *evts;
	int nevts;
};

#define FPJ_T_CUT	FPM_JOB_DUR_PULL
#define FPJ_T_KICK	( FPM_JOB_DUR_PULL + FPM_JOB_DUR_CUT )
#define FPJ_T_HIT	( FPJ_T_KICK + 0.4f )
#define FPJ_T_END	( FPJ_T_KICK + FPM_JOB_DUR_KICK )

// of2a3: the elevator door the engineer (dimjose) torches
static const FPJobEvt s_of2a3Door[] = {
	{ 0.0f, FJE_PHASE, FPM_JOB_PULL, NULL },
	{ 1.3f, FJE_PROP, 0, "models/p_torch.mdl" },
	{ 2.6f, FJE_SOUND, 0, "fgrunt/torch_light.wav" },
	{ FPJ_T_CUT, FJE_PHASE, FPM_JOB_CUT, NULL },
	{ FPJ_T_CUT, FJE_FIRE, 0, "weld_door_flicker_light" },
	{ FPJ_T_KICK - 0.1f, FJE_FIRE, 0, "weld_door_flicker_light" },
	{ FPJ_T_KICK - 0.1f, FJE_HUSH, 0, NULL },			// the torch goes off
	{ FPJ_T_KICK, FJE_PHASE, FPM_JOB_KICK, NULL },
	{ FPJ_T_KICK, FJE_PROP, 0, NULL },
	{ FPJ_T_HIT, FJE_FIRE, 0, "kill_falsedoor" },
	{ FPJ_T_HIT, FJE_FIRE, 0, "torched_door" },
	{ FPJ_T_HIT, FJE_FIRE, 0, "kill_dead_torch" },
	{ FPJ_T_HIT, FJE_FIRE, 0, "weld_door_exp_gibs_1" },
	{ FPJ_T_HIT + 0.1f, FJE_FIRE, 0, "weld_door_exp_1" },
	{ FPJ_T_END, FJE_END, 0, NULL },
	{ FPJ_T_END + 0.1f, FJE_FIRE, 0, "enter_elev" },		// the engineer, if he's still with us, heads into the elevator
};

// of2a5: the door the engineer (johnson) torches, once the medic has seen to him
static const FPJobEvt s_of2a5Door[] = {
	{ 0.0f, FJE_PHASE, FPM_JOB_PULL, NULL },
	{ 0.0f, FJE_FIRE, 0, "kill_doorsnd" },
	{ 1.3f, FJE_PROP, 0, "models/p_torch.mdl" },
	{ 2.6f, FJE_SOUND, 0, "fgrunt/torch_light.wav" },
	{ FPJ_T_CUT, FJE_PHASE, FPM_JOB_CUT, NULL },
	{ FPJ_T_CUT, FJE_FIRE, 0, "torch_doorcut_light" },
	{ FPJ_T_KICK - 0.1f, FJE_FIRE, 0, "torch_doorcut_light" },
	{ FPJ_T_KICK - 0.1f, FJE_HUSH, 0, NULL },			// the torch goes off
	{ FPJ_T_KICK, FJE_PHASE, FPM_JOB_KICK, NULL },
	{ FPJ_T_KICK, FJE_PROP, 0, NULL },
	{ FPJ_T_HIT, FJE_FIRE, 0, "killdadoor" },
	{ FPJ_T_HIT, FJE_FIRE, 0, "door_kickin" },
	{ FPJ_T_HIT, FJE_FIRE, 0, "torchchump" },
	{ FPJ_T_HIT, FJE_FIRE, 0, "weld_door_exp_gibs_1" },
	{ FPJ_T_HIT + 0.1f, FJE_FIRE, 0, "weld_door_exp_1" },
	{ FPJ_T_END, FJE_END, 0, NULL },
};

// of2a5: the wounded engineer (johnson) the medic (guido) patches up
static const FPJobEvt s_of2a5Heal[] = {
	{ 0.0f, FJE_PHASE, FPM_JOB_HEAL, NULL },
	{ 0.6f, FJE_PROP, 0, "models/p_needle.mdl" },
	{ 3.5f, FJE_SOUND, 0, "fgrunt/medic_give_shot.wav" },
	{ 7.0f, FJE_PROP, 0, NULL },
	{ 7.4f, FJE_HEAL, 0, NULL },
	{ 7.4f, FJE_FIRE, 0, "medicchump" },		// the medic dying is no longer game over
	{ 7.4f, FJE_FIRE, 0, "wounded1" },			// johnson gets up, thanks you, gets back to work
	{ FPM_JOB_DUR_HEAL, FJE_END, 0, NULL },
};

// crouch + use on any hurt friendly
static const FPJobEvt s_heal[] = {
	{ 0.0f, FJE_PHASE, FPM_JOB_HEAL, NULL },
	{ 0.6f, FJE_PROP, 0, "models/p_needle.mdl" },
	{ 3.5f, FJE_SOUND, 0, "fgrunt/medic_give_shot.wav" },
	{ 7.0f, FJE_PROP, 0, NULL },
	{ 7.4f, FJE_HEAL, 0, NULL },
	{ FPM_JOB_DUR_HEAL, FJE_END, 0, NULL },
};

#define FPJ_N( a ) ( (int)( sizeof( a ) / sizeof( a[ 0 ] ) ) )
static int s_fpJobProps;		// 1 = p_torch, 2 = p_needle precached on this map (FPJobs_Precache)

static const FPJobDef s_fpJobs[] = {
	{ "of2a3", false, NULL, NULL, Vector( -1104, 448, 0 ), Vector( -1150, 418, 2 ), Vector( -1150, 478, 92 ),
	  FPJ_T_CUT + 0.6f, FPJ_T_KICK - 0.3f, "false_door",
	  { "get_torch", "cut_door", "kickdowndoor", NULL }, Vector( -976, 448, 0 ), s_of2a3Door, FPJ_N( s_of2a3Door ) },
	{ "of2a5", false, NULL, NULL, Vector( 554, -478, 1184 ), Vector( 509, -510, 1186 ), Vector( 509, -450, 1276 ),
	  FPJ_T_CUT + 0.6f, FPJ_T_KICK - 0.3f, "killme_door",
	  { "torchdoormm", "torchseq_01", "torchseq_02", "last_torchseq", "torchseq_03", NULL }, Vector( 704, -480, 1176 ),
	  s_of2a5Door, FPJ_N( s_of2a5Door ) },
	{ "of2a5", true, "johnson", "wounded1", g_vecZero, g_vecZero, g_vecZero, 0, 0, "oops_medic",
	  { "medic_heal1", "healed_mm", NULL }, Vector( -598, -996, 1176 ), s_of2a5Heal, FPJ_N( s_of2a5Heal ) },
};
#define FPJOB_HEAL_ANY	100		// m_iFPJob for crouch + use on any hurt friendly

static const FPJobEvt *FPJobs_Evts( int job, int *n )
{
	if ( job == FPJOB_HEAL_ANY )
	{
		*n = FPJ_N( s_heal );
		return s_heal;
	}
	if ( job < 1 || job > FPJ_N( s_fpJobs ) )
	{
		*n = 0;
		return NULL;
	}
	*n = s_fpJobs[ job - 1 ].nevts;
	return s_fpJobs[ job - 1 ].evts;
}

static bool FPJobs_IsSearch( CBaseEntity *pEnt, const Vector &at )
{
	return pEnt && FClassnameIs( pEnt->pev, "scripted_sequence" ) && FStringNull( pEnt->pev->targetname ) &&
		   ( pEnt->pev->origin - at ).Length() < 24.0f;
}

static bool FPJobs_IsJobScript( const FPJobDef &d, CBaseEntity *pCine )
{
	if ( !pCine )
		return false;
	if ( FPJobs_IsSearch( pCine, d.search ) )
		return true;
	if ( FStringNull( pCine->pev->targetname ) )
		return false;
	for ( int i = 0; i < 6 && d.remove[ i ]; i++ )
		if ( FStrEq( STRING( pCine->pev->targetname ), d.remove[ i ] ) )
			return true;
	return false;
}

// an engineer / medic is on his way to the job, or doing it
static bool FPJobs_NpcBusy( const FPJobDef &d )
{
	edict_t *pEdict = g_engfuncs.pfnPEntityOfEntIndex( 1 );
	for ( int i = 1; i < gpGlobals->maxEntities; i++, pEdict++ )
	{
		if ( pEdict->free || !( pEdict->v.flags & FL_MONSTER ) )
			continue;
		CBaseEntity *pE = CBaseEntity::Instance( pEdict );
		CBaseMonster *pMon = pE ? pE->MyMonsterPointer() : NULL;
		if ( pMon && pMon->IsAlive() && pMon->m_pCine && FPJobs_IsJobScript( d, pMon->m_pCine ) )
			return true;
	}
	return false;
}

static CBaseMonster *FPJobs_Npc( const char *name )
{
	CBaseEntity *pEnt = UTIL_FindEntityByTargetname( NULL, name );
	return pEnt ? pEnt->MyMonsterPointer() : NULL;
}

static bool FPJobs_Friendly( CBaseEntity *pEnt )
{
	CBaseMonster *pMon = pEnt ? pEnt->MyMonsterPointer() : NULL;
	if ( !pMon || pEnt->IsPlayer() || !pMon->IsAlive() )
		return false;
	int c = pMon->Classify();
	return c == CLASS_PLAYER_ALLY || c == CLASS_HUMAN_MILITARY_FRIENDLY;
}

// what we're looking at, close up
static CBaseEntity *FPJobs_LookAt( CBasePlayer *pl, float range, TraceResult *ptr )
{
	UTIL_MakeVectors( pl->pev->v_angle );
	Vector eye = pl->pev->origin + pl->pev->view_ofs;
	UTIL_TraceLine( eye, eye + gpGlobals->v_forward * range, dont_ignore_monsters, pl->edict(), ptr );
	if ( ptr->flFraction >= 1.0f || !ptr->pHit )
		return NULL;
	return CBaseEntity::Instance( ptr->pHit );
}

// The use key went down: start a job if we're at one. true = we did.
bool CBasePlayer::FPJobs_TryStart( void )
{
	if ( m_iFPJob > 0 || !IsAlive() || !FBitSet( pev->flags, FL_ONGROUND ) || pev->waterlevel >= 2 ||
		 ( m_afPhysicsFlags & ( PFLAG_ONBARNACLE | PFLAG_ONTRAIN | PFLAG_ONLADDER ) ) || m_pTank != NULL ||
		 ( (int)pev->fuser4 & ( FPM_PRONE | FPM_VAULT | FPM_CLIMB | FPM_SLIDE ) ) )
		return false;

	TraceResult tr;
	CBaseEntity *pLook = FPJobs_LookAt( this, 128.0f, &tr );
	const char *map = STRING( gpGlobals->mapname );
	UTIL_MakeVectors( pev->v_angle );
	Vector eye = pev->origin + pev->view_ofs;

	for ( int j = 0; j < FPJ_N( s_fpJobs ); j++ )
	{
		const FPJobDef &d = s_fpJobs[ j ];
		if ( stricmp( map, d.map ) || UTIL_FindEntityByTargetname( NULL, d.marker ) == NULL )
			continue;		// another map, or done already
		if ( d.heal )
		{
			CBaseMonster *pNpc = FPJobs_Npc( d.npc );
			if ( !pNpc || !pNpc->IsAlive() || pLook != pNpc )
				continue;
			// still lying there waiting for the medic
			if ( !pNpc->m_pCine || FStringNull( pNpc->m_pCine->pev->targetname ) ||
				 !FStrEq( STRING( pNpc->m_pCine->pev->targetname ), d.woundedSeq ) )
				continue;
			if ( FPJobs_NpcBusy( d ) )
				continue;		// the medic's on his way
			FPJobs_Start( j + 1, pNpc );
			return true;
		}

		// a door: close to where the engineer would stand, looking at it, and
		// not at a soldier (use on him recruits him, as usual)
		Vector2D off = ( pev->origin - d.stand ).Make2D();
		if ( off.Length() > 100.0f || fabs( pev->origin.z - d.stand.z ) > 72.0f )
			continue;
		Vector mid = ( d.cutLo + d.cutHi ) * 0.5f;
		Vector to = ( mid - eye ).Normalize();
		if ( DotProduct( to, gpGlobals->v_forward ) < 0.7f )
			continue;
		if ( pLook && pLook->MyMonsterPointer() )
			continue;
		if ( FPJobs_NpcBusy( d ) )
			continue;		// the engineer's on his way, or at it
		FPJobs_Start( j + 1, NULL );
		return true;
	}

	// crouch + use on a hurt friendly: give him a shot
	if ( FBitSet( pev->flags, FL_DUCKING ) && FPJobs_Friendly( pLook ) )
	{
		CBaseMonster *pMon = pLook->MyMonsterPointer();
		if ( pMon->pev->max_health > 0.0f && pMon->pev->health < pMon->pev->max_health && pMon->m_pCine == NULL &&
			 ( tr.vecEndPos - eye ).Length() < 80.0f )
		{
			FPJobs_Start( FPJOB_HEAL_ANY, pMon );
			return true;
		}
	}
	return false;
}

void CBasePlayer::FPJobs_Start( int job, CBaseEntity *pTarget )
{
	m_iFPJob = job;
	m_flFPJobStart = gpGlobals->time;
	m_iFPJobFired = 0;
	m_iFPJobPhase = 0;
	m_flFPJobNextFx = gpGlobals->time;
	m_flFPJobNextSnd = gpGlobals->time;
	m_hFPJobTarget = pTarget;

	Vector face;
	if ( job != FPJOB_HEAL_ANY )
	{
		const FPJobDef &d = s_fpJobs[ job - 1 ];
		// the NPC won't come and do it too
		for ( int i = 0; i < 6 && d.remove[ i ]; i++ )
		{
			CBaseEntity *pEnt = NULL;
			while ( ( pEnt = UTIL_FindEntityByTargetname( pEnt, d.remove[ i ] ) ) != NULL )
				UTIL_Remove( pEnt );
		}
		CBaseEntity *pEnt = NULL;
		while ( ( pEnt = UTIL_FindEntityByClassname( pEnt, "scripted_sequence" ) ) != NULL )
			if ( FPJobs_IsSearch( pEnt, d.search ) )
				UTIL_Remove( pEnt );

		if ( !d.heal )
		{
			// stand where the engineer does, if there's room
			Vector at( d.stand.x, d.stand.y, pev->origin.z );
			TraceResult tr;
			UTIL_TraceHull( at, at, dont_ignore_monsters, FBitSet( pev->flags, FL_DUCKING ) ? head_hull : human_hull, edict(), &tr );
			if ( !tr.fStartSolid && !tr.fAllSolid )
				UTIL_SetOrigin( pev, at );
			face = ( d.cutLo + d.cutHi ) * 0.5f;
		}
		else
			face = pTarget ? pTarget->pev->origin : pev->origin;
	}
	else
		face = pTarget ? pTarget->pev->origin : pev->origin;

	// face the job
	Vector dir = face - pev->origin;
	float yaw = UTIL_VecToYaw( dir );
	float pitch = job != FPJOB_HEAL_ANY && !s_fpJobs[ job - 1 ].heal ? 8.0f : 30.0f;
	pev->angles = Vector( pitch, yaw, 0 );
	pev->v_angle = pev->angles;
	pev->fixangle = 1;
	pev->velocity = g_vecZero;
	pev->flags |= FL_FROZEN;

	// hands free: the gun goes away while we work
	pev->viewmodel = iStringNull;
	pev->weaponmodel = iStringNull;
	m_flNextAttack = UTIL_WeaponTimeBase() + 0.5f;
}

// the torch's sounds stop when it goes away
void CBasePlayer::FPJobs_Hush( void )
{
	STOP_SOUND( ENT( pev ), CHAN_WEAPON, "fgrunt/torch_cut_loop.wav" );
	STOP_SOUND( ENT( pev ), CHAN_ITEM, "fgrunt/torch_light.wav" );
	m_flFPJobNextSnd = gpGlobals->time + 1000.0f;
}

void CBasePlayer::FPJobs_End( void )
{
	FPJobs_Hush();
	m_iFPJob = 0;
	m_iFPJobPhase = 0;
	m_hFPJobTarget = NULL;
	pev->flags &= ~FL_FROZEN;
	if ( m_pActiveItem )
		m_pActiveItem->Deploy();		// the gun comes back out
	else
	{
		pev->viewmodel = iStringNull;
		pev->weaponmodel = iStringNull;
	}
}

// the torch at work: sparks running over the door, an orange glow, the hiss
void CBasePlayer::FPJobs_CutFx( int job, float t )
{
	const FPJobDef &d = s_fpJobs[ job - 1 ];
	if ( gpGlobals->time < m_flFPJobNextFx )
		return;
	m_flFPJobNextFx = gpGlobals->time + 0.1f;

	// round the door: up one side, across the top, down the other
	float u = ( t - d.cutFrom ) / ( d.cutTo - d.cutFrom );
	u = u < 0.0f ? 0.0f : ( u > 1.0f ? 1.0f : u );
	Vector lo = d.cutLo, hi = d.cutHi;
	bool alongY = fabs( hi.y - lo.y ) > fabs( hi.x - lo.x );
	float w = alongY ? hi.y - lo.y : hi.x - lo.x, h = hi.z - lo.z;
	float along = u * ( 2.0f * h + w );
	float side, up;
	if ( along < h )
		side = 0.0f, up = along;
	else if ( along < h + w )
		side = along - h, up = h;
	else
		side = w, up = h - ( along - h - w );
	Vector p = lo;
	if ( alongY )
		p.y += side;
	else
		p.x += side;
	p.z += up;

	// toward us a little, so the sparks aren't inside the door
	Vector out = pev->origin - p;
	out.z = 0;
	p = p + out.Normalize() * 2.0f;

	if ( RANDOM_LONG( 0, 2 ) == 0 )
		UTIL_Sparks( p );

	MESSAGE_BEGIN( MSG_PVS, SVC_TEMPENTITY, p );
		WRITE_BYTE( TE_DLIGHT );
		WRITE_COORD( p.x );
		WRITE_COORD( p.y );
		WRITE_COORD( p.z );
		WRITE_BYTE( RANDOM_LONG( 10, 14 ) );	// radius * 10
		WRITE_BYTE( 255 );
		WRITE_BYTE( 140 );
		WRITE_BYTE( 60 );
		WRITE_BYTE( 2 );						// life * 10
		WRITE_BYTE( 0 );
	MESSAGE_END();

	if ( gpGlobals->time >= m_flFPJobNextSnd )
	{
		EMIT_SOUND( ENT( pev ), CHAN_WEAPON, "fgrunt/torch_cut_loop.wav", 1.0f, ATTN_NORM );
		m_flFPJobNextSnd = gpGlobals->time + 1.6f;
	}
}

// Each frame (from FPMoves_Think): run the job's timeline.
void CBasePlayer::FPJobs_Think( void )
{
	if ( m_iFPJob < 0 )
		FPJobs_After();
	if ( m_iFPJob <= 0 )
		return;
	if ( !IsAlive() )
	{
		FPJobs_End();
		return;
	}
	int n;
	const FPJobEvt *evts = FPJobs_Evts( m_iFPJob, &n );
	if ( !evts )
	{
		FPJobs_End();
		return;
	}
	float t = gpGlobals->time - m_flFPJobStart;
	if ( t < 0.0f )		// the clock went back (a loaded game): carry on from the start
	{
		m_flFPJobStart = gpGlobals->time;
		t = 0.0f;
	}

	pev->flags |= FL_FROZEN;
	pev->velocity.x = pev->velocity.y = 0.0f;
	pev->viewmodel = iStringNull;
	m_flNextAttack = UTIL_WeaponTimeBase() + 0.5f;

	if ( m_iFPJob != FPJOB_HEAL_ANY )
	{
		const FPJobDef &d = s_fpJobs[ m_iFPJob - 1 ];
		if ( !d.heal && t >= d.cutFrom && t < d.cutTo )
			FPJobs_CutFx( m_iFPJob, t );
	}

	for ( int i = 0; i < n && i < 32; i++ )
	{
		if ( ( m_iFPJobFired & ( 1 << i ) ) || t < evts[ i ].t )
			continue;
		m_iFPJobFired |= 1 << i;
		const FPJobEvt &e = evts[ i ];
		switch ( e.type )
		{
		case FJE_PHASE:
			m_iFPJobPhase = e.arg;
			break;
		case FJE_FIRE:
			FireTargets( e.str, this, this, USE_TOGGLE, 0 );
			break;
		case FJE_SOUND:
			EMIT_SOUND( ENT( pev ), CHAN_ITEM, e.str, 1.0f, ATTN_NORM );
			break;
		case FJE_PROP:
			// a prop this map didn't precache: the client draws it
			pev->weaponmodel = e.str && ( s_fpJobProps & ( strstr( e.str, "needle" ) ? 2 : 1 ) ) ? MAKE_STRING( e.str ) : iStringNull;
			break;
		case FJE_HEAL:
			if ( m_hFPJobTarget != NULL && m_hFPJobTarget->IsAlive() )
			{
				CBaseEntity *pT = m_hFPJobTarget;
				float want = pT->pev->max_health > 0.0f ? pT->pev->max_health - pT->pev->health : 0.0f;
				if ( want > 0.0f )
					pT->TakeHealth( want, DMG_GENERIC );
			}
			break;
		case FJE_HUSH:
			FPJobs_Hush();
			break;
		case FJE_END:
			FPJobs_End();
			// later events (after the end) still fire: keep the timeline running
			m_iFPJob = -m_iFPJob;
			return;
		}
	}
}

// After the end: a few events can follow (an NPC sent on his way); m_iFPJob < 0
void CBasePlayer::FPJobs_After( void )
{
	if ( m_iFPJob >= 0 )
		return;
	int job = -m_iFPJob, n;
	const FPJobEvt *evts = FPJobs_Evts( job, &n );
	float t = gpGlobals->time - m_flFPJobStart;
	bool left = false;
	for ( int i = 0; evts && i < n && i < 32; i++ )
	{
		if ( m_iFPJobFired & ( 1 << i ) )
			continue;
		if ( t < evts[ i ].t )
		{
			left = true;
			continue;
		}
		m_iFPJobFired |= 1 << i;
		if ( evts[ i ].type == FJE_FIRE )
			FireTargets( evts[ i ].str, this, this, USE_TOGGLE, 0 );
	}
	if ( !left || t < 0.0f || t > 30.0f )
		m_iFPJob = 0;
}

// The props count against the map's 512 model limit (of4a4 went over it), so
// they're precached only on the maps whose jobs use them; elsewhere the client
// draws them itself (cl_dll/fpbody_anim.cpp, FPAnim_JobProp).
void FPJobs_Precache( void )
{
	s_fpJobProps = 0;
	const char *map = STRING( gpGlobals->mapname );
	for ( int i = 0; i < FPJ_N( s_fpJobs ); i++ )
		if ( map && !stricmp( map, s_fpJobs[ i ].map ) )
			s_fpJobProps |= s_fpJobs[ i ].heal ? 2 : 1;
	if ( s_fpJobProps & 1 )
		PRECACHE_MODEL( "models/p_torch.mdl" );
	if ( s_fpJobProps & 2 )
		PRECACHE_MODEL( "models/p_needle.mdl" );
	PRECACHE_SOUND( "fgrunt/torch_light.wav" );
	PRECACHE_SOUND( "fgrunt/torch_cut_loop.wav" );
	PRECACHE_SOUND( "fgrunt/medic_give_shot.wav" );
}
