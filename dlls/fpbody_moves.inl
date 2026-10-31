/***
*
*	fpbody_moves.inl - server side of the Freeman moves (see pm_shared/fpbody_pm.h).
*	Included at the end of player.cpp.
*
*	impulse 211  kick: the foot lands a moment later (the animation, played by
*	             the client, is still winding up); kicks hurt and push what they
*	             hit, open doors you could open with +use, and a kick in the air
*	             (drop kick) does double damage. Look down to stomp.
*	impulse 212  holster all: put the gun away (empty hands, the "unarmed" hold);
*	             again, or fire, takes it out.
*
****/

#include "fpbody_pm.h"

#define FPM_KICK_DELAY		0.35f		// until the foot connects (the client plays the kick in 1 s)
#define FPM_STOMP_DELAY		0.2f
#define FPM_KICK_COOLDOWN	0.9f
#define FPM_KICK_RANGE		56.0f
#define FPM_KICK_DAMAGE		25.0f

void CBasePlayer::FPMoves_Impulse( int iImpulse )
{
	if ( iImpulse == FPM_IMP_KICK )
	{
		if ( !IsAlive() || gpGlobals->time < m_flFPNextKick || ( pev->flags & FL_ONTRAIN ) || m_pTank != NULL ||
			 ( (int)pev->fuser4 & ( FPM_PRONE | FPM_VAULT ) ) )
			return;
		m_iFPKickAir = ( pev->flags & FL_ONGROUND ) ? 0 : 1;
		m_flFPKickTime = gpGlobals->time + ( pev->v_angle.x > 50.0f ? FPM_STOMP_DELAY : FPM_KICK_DELAY );
		m_flFPNextKick = gpGlobals->time + FPM_KICK_COOLDOWN;
	}
	else if ( iImpulse == FPM_IMP_HOLSTER )
	{
		if ( !IsAlive() )
			return;
		if ( m_pActiveItem )
		{
			if ( !m_pActiveItem->CanHolster() )
				return;
			m_hFPHolstered = m_pActiveItem;
			m_pActiveItem->Holster();
			m_pActiveItem = NULL;
			pev->viewmodel = 0;
			pev->weaponmodel = 0;
			strcpy( m_szAnimExtention, "unarmed" );
		}
		else
			FPMoves_Redeploy();
	}
}

void CBasePlayer::FPMoves_Redeploy( void )
{
	CBaseEntity *pEnt = m_hFPHolstered;
	m_hFPHolstered = NULL;
	if ( !pEnt || m_pActiveItem )
		return;
	CBasePlayerItem *pItem = (CBasePlayerItem *)pEnt;
	// still ours?
	for ( int i = 0; i < MAX_ITEM_TYPES; i++ )
	{
		for ( CBasePlayerItem *p = m_rgpPlayerItems[ i ]; p; p = p->m_pNext )
		{
			if ( p == pItem )
			{
				SwitchWeapon( pItem );
				return;
			}
		}
	}
}

void CBasePlayer::FPMoves_DoKick( void )
{
	UTIL_MakeVectors( pev->v_angle );
	Vector fwd = gpGlobals->v_forward;
	bool ducked = ( pev->flags & FL_DUCKING ) != 0;
	bool stomp = pev->v_angle.x > 50.0f;		// looking well down

	Vector start, dir;
	if ( stomp )
	{
		start = pev->origin;
		dir = Vector( fwd.x * 0.5f, fwd.y * 0.5f, -1.0f ).Normalize();
	}
	else
	{
		// from the hips, the way the foot goes: level, a little down or up
		start = pev->origin + Vector( 0, 0, ducked ? 0.0f : -4.0f );
		float pitch = pev->v_angle.x;
		if ( pitch < -20.0f ) pitch = -20.0f;
		if ( pitch > 40.0f ) pitch = 40.0f;
		UTIL_MakeVectors( Vector( pitch, pev->v_angle.y, 0 ) );
		dir = gpGlobals->v_forward;
	}

	Vector end = start + dir * FPM_KICK_RANGE;
	TraceResult tr;
	UTIL_TraceLine( start, end, dont_ignore_monsters, ENT( pev ), &tr );
	if ( tr.flFraction >= 1.0f )
		UTIL_TraceHull( start, end, dont_ignore_monsters, head_hull, ENT( pev ), &tr );

	if ( tr.flFraction >= 1.0f || !tr.pHit )
	{
		EMIT_SOUND_DYN( ENT( pev ), CHAN_ITEM, "weapons/cbar_miss1.wav", 1, ATTN_NORM, 0, 90 + RANDOM_LONG( 0, 10 ) );
		return;
	}

	CBaseEntity *pHit = CBaseEntity::Instance( tr.pHit );
	float damage = FPM_KICK_DAMAGE * ( m_iFPKickAir ? 2.0f : 1.0f );
	bool flesh = false;

	if ( pHit && pHit->pev->takedamage != DAMAGE_NO )
	{
		ClearMultiDamage();
		pHit->TraceAttack( pev, damage, dir, &tr, DMG_CLUB );
		ApplyMultiDamage( pev, pev );
		flesh = pHit->Classify() != CLASS_NONE && pHit->Classify() != CLASS_MACHINE;
	}

	if ( pHit && !pHit->IsBSPModel() && pHit->pev->movetype != MOVETYPE_NONE && pHit->pev->movetype != MOVETYPE_PUSH &&
		 pHit->pev->solid != SOLID_BSP && pHit != this )
	{
		pHit->pev->velocity = pHit->pev->velocity + dir * ( m_iFPKickAir ? 380.0f : 240.0f ) + Vector( 0, 0, 60 );
	}
	else if ( pHit && pHit->pev->movetype == MOVETYPE_PUSHSTEP )
	{
		pHit->pev->velocity = pHit->pev->velocity + Vector( dir.x, dir.y, 0 ) * 160.0f;	// pushable crates
	}

	// doors you could open with +use open with a kick (locked ones stay locked)
	if ( pHit && ( pHit->ObjectCaps() & FCAP_IMPULSE_USE ) &&
		 ( FClassnameIs( pHit->pev, "func_door" ) || FClassnameIs( pHit->pev, "func_door_rotating" ) ) )
	{
		pHit->Use( this, this, USE_TOGGLE, 0 );
	}

	if ( flesh )
		EMIT_SOUND_DYN( ENT( pev ), CHAN_ITEM, "weapons/cbar_hitbod1.wav", 1, ATTN_NORM, 0, 90 + RANDOM_LONG( 0, 10 ) );
	else
		EMIT_SOUND_DYN( ENT( pev ), CHAN_ITEM, "weapons/cbar_hit1.wav", 1, ATTN_NORM, 0, 90 + RANDOM_LONG( 0, 10 ) );

	// the kick pushes us back off what we hit
	Vector back = Vector( -dir.x, -dir.y, 0 );
	pev->velocity = pev->velocity + back * ( m_iFPKickAir ? 220.0f : 110.0f );
}

// ExtendedER: a fight near us (FPM_PANIC: empty-handed Gordon cowers / runs in a
// panic) and a hostile in front of us (FPM_HOSTILE: the lowered gun comes up).
// The client plays the animations; the bits ride in the move state (fuser4).
static bool FPMoves_IgnoreMonster( CBaseEntity *pEnt )
{
	static const char *skip[] = { "monster_barnacle", "monster_turret", "monster_miniturret", "monster_sentry",
		"monster_apache", "monster_blkop_apache", "monster_osprey", "monster_blkop_osprey", "monster_cockroach",
		"monster_leech", "monster_flyer", "monster_flyer_flock", "monster_furniture", "monster_generic",
		"monster_tentacle", "monster_nihilanth", "monster_bigmomma", "monster_gargantua", "monster_babygarg" };
	for ( int i = 0; i < (int)( sizeof( skip ) / sizeof( skip[ 0 ] ) ); i++ )
		if ( FClassnameIs( pEnt->pev, skip[ i ] ) )
			return true;
	return false;
}

void CBasePlayer::FPMoves_Scan( void )
{
	if ( gpGlobals->time < m_flFPScanTime )
		return;
	m_flFPScanTime = gpGlobals->time + 0.25f;

	UTIL_MakeVectors( pev->v_angle );
	Vector eye = pev->origin + pev->view_ofs;
	float cone = cos( 25.0f * M_PI / 180.0f );		// a 50 degree view cone
	CBaseEntity *pEnt = NULL;
	while ( ( pEnt = UTIL_FindEntityInSphere( pEnt, pev->origin, 2048.0f ) ) != NULL )
	{
		CBaseMonster *pMon = pEnt->MyMonsterPointer();
		if ( !pMon || pEnt == this || pEnt->IsPlayer() || !pEnt->IsAlive() || FPMoves_IgnoreMonster( pEnt ) )
			continue;
		Vector to = pEnt->Center() - eye;
		float dist = to.Length();

		// a fight nearby
		if ( pMon->m_hEnemy != NULL && dist < 1020.0f )
			m_flFPPanicUntil = gpGlobals->time + 6.0f;

		// out for us, in front of us, in the open
		if ( dist > 1.0f && ( pMon->m_hEnemy == this || pMon->IRelationship( this ) >= R_DL ) &&
			 DotProduct( gpGlobals->v_forward, to / dist ) > cone && FVisible( pEnt ) )
			m_flFPHostileUntil = gpGlobals->time + 0.5f;
	}
}

// Contextual Player Animations: what we just +used, for the client's gesture
// (a push for doors, a press for buttons, a reach for anything else; chargers
// keep reaching while use is held). Called from PlayerUse before the Use.
void CBasePlayer::FPMoves_OnUse( CBaseEntity *pObject )
{
	if ( !pObject || ( (int)pev->fuser4 & ( FPM_PRONE | FPM_VAULT | FPM_CLIMB ) ) )
		return;
	const char *cls = STRING( pObject->pev->classname );
	int kind;
	if ( FClassnameIs( pObject->pev, "func_healthcharger" ) || FClassnameIs( pObject->pev, "func_recharge" ) )
		kind = FPM_USE_CHARGER;
	else if ( FClassnameIs( pObject->pev, "func_door" ) || FClassnameIs( pObject->pev, "func_door_rotating" ) ||
			  FClassnameIs( pObject->pev, "momentary_door" ) )
		kind = FPM_USE_DOOR;
	else if ( strstr( cls, "button" ) )
		kind = FPM_USE_BUTTON;
	else if ( pObject->MyMonsterPointer() || pObject->IsPlayer() || !strncmp( cls, "func_tank", 9 ) ||
			  FClassnameIs( pObject->pev, "func_tracktrain" ) || FClassnameIs( pObject->pev, "func_vehicle" ) ||
			  FClassnameIs( pObject->pev, "func_pushable" ) )
		return;		// following, mounting a gun, driving, dragging: no gesture
	else
		kind = FPM_USE_OTHER;

	if ( kind == FPM_USE_CHARGER )
	{
		m_iFPUseKind = kind;
		m_flFPUseUntil = gpGlobals->time + 0.2f;			// while it's held
		return;
	}
	if ( !( m_afButtonPressed & IN_USE ) || gpGlobals->time < m_flFPNextUse )
		return;
	m_iFPUseKind = kind;
	m_flFPUseUntil = gpGlobals->time + 0.3f;
	m_flFPNextUse = gpGlobals->time + 1.0f;
}

void CBasePlayer::FPMoves_Think( void )
{
	if ( IsAlive() )
		FPMoves_Scan();
	int st = (int)pev->fuser4 & ~( FPM_PANIC | FPM_HOSTILE | ( 7 << FPM_HITGROUP_SHIFT ) | ( 7 << FPM_USE_SHIFT ) );
	st |= ( m_LastHitGroup & 7 ) << FPM_HITGROUP_SHIFT;
	if ( IsAlive() && gpGlobals->time < m_flFPUseUntil )
		st |= ( m_iFPUseKind & 7 ) << FPM_USE_SHIFT;
	if ( IsAlive() && gpGlobals->time < m_flFPPanicUntil )
		st |= FPM_PANIC;
	if ( IsAlive() && gpGlobals->time < m_flFPHostileUntil )
		st |= FPM_HOSTILE;
	pev->fuser4 = (float)st;

	if ( m_flFPKickTime > 0.0f && gpGlobals->time >= m_flFPKickTime )
	{
		m_flFPKickTime = 0.0f;
		if ( IsAlive() )
			FPMoves_DoKick();
	}

	if ( m_hFPHolstered != NULL )
	{
		if ( m_pActiveItem )
			m_hFPHolstered = NULL;							// a gun came out some other way
		else if ( IsAlive() && ( m_afButtonPressed & IN_ATTACK ) )
			FPMoves_Redeploy();								// fire takes the gun out again
	}
}
