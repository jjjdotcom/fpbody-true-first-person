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
#define FPM_BARNACLE		131072	// set by the server: a barnacle has us (fuser4 needs 24 bits in delta.lst)
#define FPM_ROPE			262144	// set by the server: hanging on a rope (Opposing Force)
#define FPM_JOB_SHIFT		19		// 3 bits, set by the server: an Opposing Force job (FPM_JOB_*)
#define FPM_KNOCK			4194304	// set by the server: knocked down by a big enemy (dlls/fpbody_react.inl; bit 22, the last that fits in fuser4's 24 signed bits)
#define FPM_SPRINT_SCALE	1.25f	// speed while sprinting (320 -> 400)

// Moves that can be switched off (1 = on): prone (pm_prone, double-tap duck) and
// sprinting (+alt1). Shift / LB walks instead (+speed, autoexec.cfg).
#define FPM_ENABLE_PRONE	1
#define FPM_ENABLE_SPRINT	0

#define FPM_USE_DOOR		1		// Contextual Player Animations
#define FPM_USE_BUTTON		2
#define FPM_USE_OTHER		3
#define FPM_USE_CHARGER		4		// held: the reach repeats
#define FPM_USE_SCAN		5		// a retinal scanner: the eye scan (fm_retina)

#define FPM_VAULT_MANTLE	1
#define FPM_VAULT_HOP		2
#define FPM_VAULT_PULLUP	3

#define FPM_IMP_PRONE		210
#define FPM_IMP_KICK		211
#define FPM_IMP_HOLSTER		212

// Opposing Force jobs the player does himself (dlls/fpbody_jobs.inl): the
// phase, and how long the server holds it (the client plays fm_job_* that long)
#define FPM_JOB_PULL		1		// fm_job_pull_torch
#define FPM_JOB_CUT			2		// fm_job_cut_door
#define FPM_JOB_KICK		3		// fm_job_kick
#define FPM_JOB_HEAL		4		// fm_job_heal
#define FPM_JOB_CUTGRATE	5		// fm_job_cut_grate
#define FPM_JOB_OPENGRATE	6		// fm_job_open_grate
#define FPM_JOB_STORE		7		// fm_job_store_torch
#define FPM_JOB_DUR_PULL	3.8f
#define FPM_JOB_DUR_CUT		12.0f
#define FPM_JOB_DUR_KICK	0.9f
#define FPM_JOB_DUR_HEAL	8.0f
#define FPM_JOB_DUR_CUTGRATE	5.7f
#define FPM_JOB_DUR_OPENGRATE	1.6f
#define FPM_JOB_DUR_STORE	3.3f
#define FPM_KNOCK_DUR		3.5f	// fm_knockdown: falling, a moment down, getting up
#define FPM_JOB( st )		( ( ( st ) >> FPM_JOB_SHIFT ) & 7 )

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
