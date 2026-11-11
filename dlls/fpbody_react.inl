/***
*
*	fpbody_react.inl - hit reactions by who hit us (sv_fpbody_knockdown 1).
*	Included at the end of player.cpp, after fpbody_moves.inl.
*
*	A gargantua's stomp knocks the player down too, its flames throw him back.
*
*	Big enemies (every zombie, bullsquids, gargantuas, alien grunts,
*	tentacles ... and anything with a big hull) knock the player flat when
*	they hit him: he falls on his back, lies there a moment and gets back up
*	(fm_knockdown, played by the client while FPM_KNOCK is set in the move
*	state). He can't move or fire meanwhile, the gun is put away and comes
*	back out when he's up. Not in water, on a ladder, in the air or on a
*	train (then the small reaction instead), and at most once every few
*	seconds.
*
*	Small enemies (headcrabs, snarks, penguins, houndeyes, leeches, rats,
*	shock roaches ... and bullsquid spit) make him react as to an explosion
*	(fm_blast: the Damage message carries DMG_BLAST).
*
*	Hooks: CBasePlayer::TakeDamage calls FPReact_OnDamage first thing;
*	PreThink calls FPReact_Think after FPMoves_Think; game.cpp registers
*	sv_fpbody_knockdown (default 1); FPM_KNOCK is in pm_shared/fpbody_pm.h.
*
****/

#define FPR_KNOCK_DUR		FPM_KNOCK_DUR	// fm_knockdown (pm_shared/fpbody_pm.h)
#define FPR_KNOCK_COOLDOWN	4.0f	// after getting up, before the next one

#ifndef FPR_TANK
#define FPR_TANK( pl )		( ( pl )->m_pTank != NULL )	// at a mounted gun
#endif

extern cvar_t sv_fpbody_knockdown;

static float s_fpKnockEnd;			// when the player is back up (0 = not down)
static float s_fpKnockNext;			// no new knockdown before this

static bool FPReact_NameHas( CBaseEntity *pEnt, const char *const *words )
{
	const char *cls = STRING( pEnt->pev->classname );
	for ( int i = 0; words[ i ]; i++ )
		if ( strstr( cls, words[ i ] ) )
			return true;
	return false;
}

// 2 = a big enemy (knocks us down), 1 = a small one (the blast reaction), 0 = neither
static int FPReact_Kind( CBaseEntity *pAttacker, CBaseEntity *pInflictor )
{
	static const char *const small[] = { "headcrab", "babycrab", "snark", "penguin", "leech", "monster_rat",
		"cockroach", "chumtoad", "houndeye", "shockroach", "pitdrone", "babyvoltigore", "stukabat", "squidspit",
		"bullsquid_spit", NULL };
	static const char *const big[] = { "zombie", "gonome", "bullchicken", "bullsquid", "bigmomma", "gargantua",
		"babygarg", "alien_grunt", "agrunt", "tentacle", "ichthyosaur", "pitworm", "geneworm", "voltigore",
		"shocktrooper", "kingpin", NULL };
	if ( pInflictor && pInflictor != pAttacker && FPReact_NameHas( pInflictor, small ) )
		return 1;									// e.g. bullsquid spit
	if ( !pAttacker || !( pAttacker->pev->flags & FL_MONSTER ) || pAttacker->IsPlayer() )
		return 0;
	if ( FPReact_NameHas( pAttacker, small ) )
		return 1;
	if ( FPReact_NameHas( pAttacker, big ) )
		return 2;
	// anything else by its size: wider than a man or much taller is big, knee high is small
	Vector size = pAttacker->pev->maxs - pAttacker->pev->mins;
	if ( size.x >= 60.0f || size.z >= 96.0f )
		return 2;
	if ( size.x > 0.0f && size.x <= 40.0f && size.z <= 40.0f )
		return 1;
	return 0;
}

static void FPReact_GetUp( CBasePlayer *pl )
{
	s_fpKnockEnd = 0.0f;
	pl->pev->flags &= ~FL_FROZEN;
	pl->pev->fuser4 = (float)( (int)pl->pev->fuser4 & ~FPM_KNOCK );
	if ( pl->IsAlive() && pl->m_pActiveItem )
		pl->m_pActiveItem->Deploy();					// the gun comes back out
}

void FPReact_OnDamage( CBasePlayer *pl, entvars_t *pevInflictor, entvars_t *pevAttacker, float flDamage, int bitsDamageType )
{
	if ( sv_fpbody_knockdown.value == 0.0f || flDamage <= 0.0f || !pl->IsAlive() || pl->pev->takedamage == DAMAGE_NO ||
		 gpGlobals->maxClients > 1 )
		return;
	CBaseEntity *pAttacker = pevAttacker ? CBaseEntity::Instance( pevAttacker ) : NULL;
	CBaseEntity *pInflictor = pevInflictor ? CBaseEntity::Instance( pevInflictor ) : NULL;
	int kind = FPReact_Kind( pAttacker, pInflictor );
	// a gargantua: its flames throw us back as an explosion does (not a
	// knockdown on every flame tick); its stomp's energy stream knocks us down
	bool stomp = pInflictor && FStrEq( STRING( pInflictor->pev->classname ), "garg_stomp" );
	if ( kind == 2 && ( bitsDamageType & DMG_BURN ) && pAttacker && strstr( STRING( pAttacker->pev->classname ), "garg" ) )
		kind = 1;
	if ( stomp )
		kind = 2;
	if ( !kind )
		return;
	int st = (int)pl->pev->fuser4;
	if ( kind == 2 )
	{
		// knocked down by the blow itself (not its hornets, rocks, stomps ...),
		// standing on the ground and free to fall
		bool can = ( pAttacker == pInflictor || stomp ) && s_fpKnockEnd <= 0.0f && gpGlobals->time >= s_fpKnockNext &&
				   ( pl->pev->flags & FL_ONGROUND ) && !( pl->pev->flags & ( FL_FROZEN | FL_ONTRAIN ) ) &&
				   pl->pev->waterlevel < 2 && !pl->IsOnLadder() && !FPR_TANK( pl ) &&
				   !( pl->m_afPhysicsFlags & PFLAG_ONBARNACLE ) && !( st & ( FPM_PRONE | FPM_VAULT | FPM_CLIMB ) );
		if ( can )
		{
			s_fpKnockEnd = gpGlobals->time + FPR_KNOCK_DUR;
			s_fpKnockNext = s_fpKnockEnd + FPR_KNOCK_COOLDOWN;
			pl->pev->flags |= FL_FROZEN;
			pl->pev->velocity = g_vecZero;
			pl->pev->viewmodel = iStringNull;			// hands free to break the fall
			pl->pev->weaponmodel = iStringNull;
			pl->m_flNextAttack = UTIL_WeaponTimeBase() + FPR_KNOCK_DUR;
			pl->pev->fuser4 = (float)( st | FPM_KNOCK );
			return;
		}
		if ( s_fpKnockEnd > 0.0f )
			return;										// already down
	}
	if ( s_fpKnockEnd > 0.0f )
		return;										// lying down: no blast on top
	pl->m_bitsDamageType |= DMG_BLAST;					// the client: thrown back as by a blast (fm_blast)
}

void FPReact_Think( CBasePlayer *pl )
{
	int st = (int)pl->pev->fuser4;
	// down until the time's up; a stale time (a new map, a loaded game: the
	// clock starts again) or a knock bit from a saved game gets him up now
	bool down = s_fpKnockEnd > 0.0f && gpGlobals->time < s_fpKnockEnd && s_fpKnockEnd - gpGlobals->time <= FPR_KNOCK_DUR + 0.5f;
	if ( down && pl->IsAlive() )
	{
		pl->pev->flags |= FL_FROZEN;
		pl->pev->viewmodel = iStringNull;
		pl->pev->weaponmodel = iStringNull;
		pl->pev->fuser4 = (float)( st | FPM_KNOCK );
	}
	else if ( s_fpKnockEnd > 0.0f || ( st & FPM_KNOCK ) )
		FPReact_GetUp( pl );
	if ( s_fpKnockNext - gpGlobals->time > FPR_KNOCK_DUR + FPR_KNOCK_COOLDOWN + 1.0f )
		s_fpKnockNext = 0.0f;
}
