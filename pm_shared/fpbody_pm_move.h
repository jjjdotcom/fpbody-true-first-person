/***
*
*	fpbody_pm_move.h - the moves themselves (see fpbody_pm.h). Included by
*	pm_shared just before PM_PlayerMove, so it can use its helpers.
*
*	FPM_PreDuck runs every player move before PM_Duck; when it returns 1 it
*	has moved the player itself (vaulting) and the normal movement is skipped.
*	FPM_PostDuck runs after PM_Duck (prone speed and eye height).
*
****/

int g_fpmState;
float g_fpmTimer;

#define FPM_PRONE_SPEED		0.5f	// on top of the duck speed (Half-Life's 1/3)
#define FPM_PRONE_VIEW		-2.0f	// eye height above the origin while prone (duck: 12)
#define FPM_SLIDE_TIME		0.85f
#define FPM_SLIDE_MINSPEED	230.0f
#define FPM_CLIMB_PUSHES	3
#define FPM_CLIMB_SPEED		270.0f

static int FPM_Get( void ) { return (int)pmove->fuser4; }
static void FPM_Set( int st ) { pmove->fuser4 = (float)st; }

static void FPM_Publish( void )
{
	if ( !pmove->server )
	{
		g_fpmState = FPM_Get();
		g_fpmTimer = pmove->fuser1;
	}
}

static void FPM_Forward( float *f )
{
	float yaw = pmove->angles[ 1 ] * (float)( M_PI / 180.0 );
	f[ 0 ] = (float)cos( yaw );
	f[ 1 ] = (float)sin( yaw );
	f[ 2 ] = 0.0f;
}

static void FPM_Along( const float *from, float dist, const float *dir, float *out )
{
	out[ 0 ] = from[ 0 ] + dir[ 0 ] * dist;
	out[ 1 ] = from[ 1 ] + dir[ 1 ] * dist;
	out[ 2 ] = from[ 2 ] + dir[ 2 ] * dist;
}

static float FPM_Speed2D( void )
{
	return (float)sqrt( pmove->velocity[ 0 ] * pmove->velocity[ 0 ] + pmove->velocity[ 1 ] * pmove->velocity[ 1 ] );
}

// A wall in front with a ledge on top that a standing player fits on.
// Returns the vault type (0 = none).
static int FPM_FindLedge( int onground )
{
	float fwd[ 3 ], start[ 3 ], end[ 3 ];
	pmtrace_t tr;
	float feet, wall, standOfs, top, h;
	int oldhull = pmove->usehull, thin = 0;

	FPM_Forward( fwd );
	feet = pmove->origin[ 2 ] + pmove->player_mins[ pmove->usehull ][ 2 ];

	// a wall just ahead
	FPM_Along( pmove->origin, 24.0f, fwd, end );
	tr = pmove->PM_PlayerTrace( pmove->origin, end, PM_NORMAL, -1 );
	if ( tr.startsolid || tr.allsolid || tr.fraction >= 1.0f || tr.plane.normal[ 2 ] > 0.7f )
		return 0;
	wall = 24.0f * tr.fraction;

	// standing room on top of it: drop a standing hull onto the ledge
	pmove->usehull = 0;
	standOfs = -pmove->player_mins[ 0 ][ 2 ];
	FPM_Along( pmove->origin, wall + 20.0f, fwd, start );
	start[ 2 ] = feet + standOfs + 100.0f;
	end[ 0 ] = start[ 0 ]; end[ 1 ] = start[ 1 ];
	end[ 2 ] = feet + standOfs + 14.0f;
	tr = pmove->PM_PlayerTrace( start, end, PM_NORMAL, -1 );
	if ( tr.startsolid || tr.allsolid || tr.fraction >= 1.0f || tr.plane.normal[ 2 ] < 0.7f )
	{
		pmove->usehull = oldhull;
		return 0;
	}
	top = tr.endpos[ 2 ];
	h = top - standOfs - feet;

	// low wall: is the floor behind it lower again?
	if ( h <= 48.0f )
	{
		FPM_Along( pmove->origin, wall + 52.0f, fwd, start );
		start[ 2 ] = top + 2.0f;
		end[ 0 ] = start[ 0 ]; end[ 1 ] = start[ 1 ];
		end[ 2 ] = top - 20.0f;
		tr = pmove->PM_PlayerTrace( start, end, PM_NORMAL, -1 );
		if ( !tr.startsolid && !tr.allsolid && tr.fraction >= 1.0f )
			thin = 1;
	}
	pmove->usehull = oldhull;

	if ( h < 16.0f || h > 100.0f )
		return 0;

	// room to rise straight up to the ledge height
	end[ 0 ] = pmove->origin[ 0 ]; end[ 1 ] = pmove->origin[ 1 ];
	end[ 2 ] = ( top - standOfs ) - pmove->player_mins[ pmove->usehull ][ 2 ] + 2.0f;	// hull bottom just above the ledge
	if ( end[ 2 ] > pmove->origin[ 2 ] )
	{
		tr = pmove->PM_PlayerTrace( pmove->origin, end, PM_NORMAL, -1 );
		if ( tr.startsolid || tr.fraction < 1.0f )
			return 0;
	}

	if ( thin )
		return FPM_VAULT_HOP;
	if ( onground && h <= 34.0f )
		return 0;					// low enough to just jump onto
	return ( h <= 60.0f ) ? FPM_VAULT_MANTLE : FPM_VAULT_PULLUP;
}

static void FPM_EndVault( int st, int type )
{
	float fwd[ 3 ];
	float keep = ( type == FPM_VAULT_HOP ) ? 170.0f : 60.0f;
	FPM_Forward( fwd );
	st &= ~( FPM_VAULT | ( 3 << FPM_VTYPE_SHIFT ) );
	FPM_Set( st );
	pmove->fuser1 = 0.0f;
	pmove->velocity[ 0 ] = fwd[ 0 ] * keep;
	pmove->velocity[ 1 ] = fwd[ 1 ] * keep;
	pmove->velocity[ 2 ] = 0.0f;
}

// One frame of a vault: forward when the way is clear, up while the wall is still in front
static void FPM_VaultMove( int st )
{
	int type = FPM_VTYPE( st );
	float fwd[ 3 ], end[ 3 ];
	pmtrace_t tr;
	float dt = pmove->frametime;
	float up = ( type == FPM_VAULT_PULLUP ) ? 210.0f : ( type == FPM_VAULT_MANTLE ) ? 180.0f : 240.0f;
	float fw = ( type == FPM_VAULT_HOP ) ? 220.0f : 120.0f;

	FPM_Forward( fwd );
	pmove->velocity[ 0 ] = pmove->velocity[ 1 ] = pmove->velocity[ 2 ] = 0.0f;

	FPM_Along( pmove->origin, fw * dt, fwd, end );
	tr = pmove->PM_PlayerTrace( pmove->origin, end, PM_NORMAL, -1 );
	if ( !tr.startsolid && !tr.allsolid && tr.fraction >= 1.0f )
	{
		pmove->origin[ 0 ] = end[ 0 ]; pmove->origin[ 1 ] = end[ 1 ]; pmove->origin[ 2 ] = end[ 2 ];
		pmove->velocity[ 0 ] = fwd[ 0 ] * fw;
		pmove->velocity[ 1 ] = fwd[ 1 ] * fw;
	}
	else
	{
		end[ 0 ] = pmove->origin[ 0 ]; end[ 1 ] = pmove->origin[ 1 ]; end[ 2 ] = pmove->origin[ 2 ] + up * dt;
		tr = pmove->PM_PlayerTrace( pmove->origin, end, PM_NORMAL, -1 );
		if ( tr.startsolid || tr.allsolid || tr.fraction < 1.0f )
		{
			FPM_EndVault( st, type );		// blocked: let go
			return;
		}
		pmove->origin[ 2 ] = end[ 2 ];
		pmove->velocity[ 2 ] = up;
	}

	pmove->fuser1 -= dt;
	if ( pmove->fuser1 <= 0.0f )
		FPM_EndVault( st, type );
}

static int FPM_PreDuck( int onLadder )
{
	int st = FPM_Get();
	int onground = ( pmove->onground != -1 );
	int jumpPressed = ( pmove->cmd.buttons & IN_JUMP ) && !( pmove->oldbuttons & IN_JUMP );
	int duckPressed = ( pmove->cmd.buttons & IN_DUCK ) && !( pmove->oldbuttons & IN_DUCK );
	int usable = !pmove->dead && pmove->movetype == MOVETYPE_WALK && !( pmove->flags & FL_ONTRAIN ) &&
				 pmove->waterlevel < 2 && !onLadder && !pmove->iuser3;

	if ( pmove->fuser1 > 0.0f && !( st & ( FPM_VAULT | FPM_SLIDE ) ) )
	{
		pmove->fuser1 -= pmove->frametime;		// climb cooldown
		if ( pmove->fuser1 < 0.0f )
			pmove->fuser1 = 0.0f;
	}

	// vault in progress: we move the player
	if ( st & FPM_VAULT )
	{
		if ( !usable )
			FPM_EndVault( st, FPM_VTYPE( st ) );
		else
		{
			pmove->oldbuttons |= IN_JUMP;		// holding jump doesn't jump at the end
			FPM_VaultMove( st );
			PM_CatagorizePosition();
			FPM_Publish();
			return 1;
		}
		st = FPM_Get();
	}

	// prone on / off
	if ( pmove->cmd.impulse == FPM_IMP_PRONE )
	{
		if ( st & FPM_PRONE )
			st &= ~FPM_PRONE;
		else if ( usable && onground )
			st = ( st | FPM_PRONE ) & ~FPM_SLIDE;
	}
	if ( st & FPM_PRONE )
	{
		if ( !usable )
			st &= ~FPM_PRONE;
		else if ( jumpPressed )
		{
			st &= ~FPM_PRONE;					// jump gets up instead
			pmove->cmd.buttons &= ~IN_JUMP;
			pmove->oldbuttons |= IN_JUMP;
		}
		else
		{
			pmove->cmd.buttons |= IN_DUCK;
			pmove->cmd.buttons &= ~IN_JUMP;
		}
	}

	// landed: wall climbing starts over
	if ( onground )
		st &= ~( FPM_CLIMB | ( 3 << FPM_CCOUNT_SHIFT ) );

	// slide: duck while running
	if ( st & FPM_SLIDE )
	{
		pmove->fuser1 -= pmove->frametime;
		if ( !usable || !onground || pmove->fuser1 <= 0.0f || FPM_Speed2D() < 110.0f || ( pmove->cmd.buttons & IN_JUMP ) )
		{
			st &= ~FPM_SLIDE;
			pmove->fuser1 = 0.0f;
		}
		else
		{
			pmove->cmd.buttons |= IN_DUCK;
			pmove->cmd.forwardmove = pmove->cmd.sidemove = 0.0f;
		}
	}
	else if ( usable && onground && duckPressed && !( st & FPM_PRONE ) && !( pmove->flags & FL_DUCKING ) &&
			  FPM_Speed2D() > FPM_SLIDE_MINSPEED && pmove->cmd.forwardmove > 0.0f )
	{
		st |= FPM_SLIDE;
		pmove->fuser1 = FPM_SLIDE_TIME;
		pmove->cmd.forwardmove = pmove->cmd.sidemove = 0.0f;
	}

	// vault / mantle / pull-up: jump (or keep holding it in the air) at a ledge, moving forward
	if ( usable && !( st & ( FPM_PRONE | FPM_SLIDE ) ) && ( pmove->cmd.buttons & IN_JUMP ) && pmove->cmd.forwardmove > 0.0f &&
		 ( onground ? jumpPressed : pmove->velocity[ 2 ] > -300.0f ) )
	{
		static const float times[ 4 ] = { 0.0f, 0.8f, 0.65f, 1.0f };	// mantle, hop, pull-up
		int type = FPM_FindLedge( onground );
		if ( type )
		{
			st = ( st & ~( 3 << FPM_VTYPE_SHIFT ) ) | FPM_VAULT | ( type << FPM_VTYPE_SHIFT );
			FPM_Set( st );
			pmove->fuser1 = times[ type ];
			pmove->cmd.buttons &= ~IN_JUMP;
			pmove->oldbuttons |= IN_JUMP;
			FPM_VaultMove( st );
			PM_CatagorizePosition();
			FPM_Publish();
			return 1;
		}
	}

	// wall climb: keep holding jump against a wall in the air
	if ( usable && !onground && !( st & ( FPM_PRONE | FPM_VAULT ) ) && ( pmove->cmd.buttons & IN_JUMP ) &&
		 pmove->cmd.forwardmove > 0.0f && pmove->fuser1 <= 0.0f && pmove->velocity[ 2 ] < 120.0f )
	{
		int used = ( st >> FPM_CCOUNT_SHIFT ) & 3;
		if ( used < FPM_CLIMB_PUSHES )
		{
			float fwd[ 3 ], end[ 3 ];
			pmtrace_t tr;
			FPM_Forward( fwd );
			FPM_Along( pmove->origin, 14.0f, fwd, end );
			tr = pmove->PM_PlayerTrace( pmove->origin, end, PM_NORMAL, -1 );
			if ( !tr.startsolid && !tr.allsolid && tr.fraction < 1.0f && tr.plane.normal[ 2 ] < 0.5f )
			{
				st = ( st & ~( 3 << FPM_CCOUNT_SHIFT ) ) | FPM_CLIMB | ( ( used + 1 ) << FPM_CCOUNT_SHIFT );
				pmove->velocity[ 0 ] *= 0.2f;
				pmove->velocity[ 1 ] *= 0.2f;
				pmove->velocity[ 2 ] = FPM_CLIMB_SPEED;
				pmove->fuser1 = 0.45f;
			}
		}
	}

	FPM_Set( st );
	FPM_Publish();
	return 0;
}

static void FPM_PostDuck( void )
{
	int st = FPM_Get();

	// sprint: forward, on the ground (keeps going through a jump), standing, dry
	int busy = st & ( FPM_PRONE | FPM_SLIDE | FPM_VAULT | FPM_CLIMB );
	int sprint = ( pmove->cmd.buttons & IN_ALT1 ) && pmove->cmd.forwardmove > 0.0f && !busy &&
				 !( pmove->flags & FL_DUCKING ) && pmove->waterlevel < 2 && pmove->movetype == MOVETYPE_WALK &&
				 ( pmove->onground != -1 || ( st & FPM_SPRINT ) );
	if ( sprint != ( ( st & FPM_SPRINT ) != 0 ) )
	{
		st = sprint ? ( st | FPM_SPRINT ) : ( st & ~FPM_SPRINT );
		FPM_Set( st );
		FPM_Publish();
	}
	if ( sprint )
	{
		pmove->maxspeed = pmove->movevars->maxspeed * FPM_SPRINT_SCALE;
		pmove->cmd.forwardmove *= FPM_SPRINT_SCALE;
		pmove->cmd.sidemove *= 0.6f;		// mostly forward
	}

	if ( st & FPM_PRONE )
	{
		pmove->cmd.forwardmove *= FPM_PRONE_SPEED;
		pmove->cmd.sidemove *= FPM_PRONE_SPEED;
		if ( pmove->flags & FL_DUCKING )
			pmove->view_ofs[ 2 ] = FPM_PRONE_VIEW;
	}
	else if ( ( pmove->flags & FL_DUCKING ) && pmove->view_ofs[ 2 ] == FPM_PRONE_VIEW )
		pmove->view_ofs[ 2 ] = 12.0f;		// got up from prone but still ducking (VEC_DUCK_VIEW)
}
