/***
*
*	fpbody_pm.h - player movement for the "True First Person" mod: prone,
*	slide, vault / mantle / pull-up and wall climbing, ported from the
*	Half-Life 2 "Freeman" mod.
*
*	Shared by the client (prediction) and the server, like the rest of
*	pm_shared. The state lives in two player fields that the engine predicts:
*	  fuser4  state bits (FPM_*), as a whole number
*	  fuser1  timer for the current move (vault / slide time left, climb cooldown)
*	The moves are started with impulses, so client and server see them in the
*	same user command:
*	  impulse 210  prone on / off       (pm_prone, double-tap duck)
*	  impulse 211  kick                 (pm_kick; damage is done by the server)
*	  impulse 212  holster all weapons  (pm_holster, double-tap reload)
*	Sprinting is a button (IN_ALT1, +sprint): forward on the ground, not ducked;
*	the client stops sending it when stamina runs out or you shoot.
*
****/
#ifndef FPBODY_PM_H
#define FPBODY_PM_H

#define FPM_PRONE			1
#define FPM_VAULT			2
#define FPM_VTYPE_SHIFT		2		// 2 bits: 1 mantle, 2 hop over, 3 pull-up
#define FPM_CLIMB			16
#define FPM_CCOUNT_SHIFT	5		// 2 bits: wall-climb pushes used in this jump
#define FPM_SLIDE			128
#define FPM_PANIC			256		// set by the server: a fight nearby (ExtendedER panic)
#define FPM_HOSTILE			512		// set by the server: a hostile in view (raises the gun)
#define FPM_HITGROUP_SHIFT	10		// 3 bits, set by the server: where the last bullet hit us
#define FPM_USE_SHIFT		13		// 3 bits, set by the server: what we just +used (FPM_USE_*)
#define FPM_SPRINT			65536	// sprinting (+sprint = +alt1, IN_ALT1)
#define FPM_BARNACLE		131072	// set by the server: a barnacle has us
#define FPM_SPRINT_SCALE	1.25f	// speed while sprinting (320 -> 400)

#define FPM_USE_DOOR		1		// Contextual Player Animations
#define FPM_USE_BUTTON		2
#define FPM_USE_OTHER		3
#define FPM_USE_CHARGER		4		// held: the reach repeats

#define FPM_VAULT_MANTLE	1
#define FPM_VAULT_HOP		2
#define FPM_VAULT_PULLUP	3

#define FPM_IMP_PRONE		210
#define FPM_IMP_KICK		211
#define FPM_IMP_HOLSTER		212

#define FPM_STATE( pm )		( (int)( pm )->fuser4 )
#define FPM_VTYPE( st )		( ( ( st ) >> FPM_VTYPE_SHIFT ) & 3 )

// friction while sliding (PM_Friction)
#define FPM_FRICTION_SCALE( pm )	( ( FPM_STATE( pm ) & FPM_SLIDE ) ? 0.08f : 1.0f )

#ifdef __cplusplus
extern "C" {
#endif
// the client's latest predicted state, for the animations (cl_dll/fpbody_anim.cpp)
extern int g_fpmState;
extern float g_fpmTimer;
#ifdef __cplusplus
}
#endif

#endif // FPBODY_PM_H
