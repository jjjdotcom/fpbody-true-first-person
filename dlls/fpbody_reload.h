// fpbody: cl_fpbody_reload_speed - reloads take 1 / speed as long (0.5 = twice as long).
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
