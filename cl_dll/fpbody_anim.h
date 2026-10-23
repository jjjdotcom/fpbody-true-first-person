// fpbody_anim.h - procedural body animations for the "True First Person" mod.
//
// Half-Life's player.mdl has no reload / weapon-switch / use animations, so
// this module animates the body's own bones in code, on top of whatever
// sequence the model is playing. The third-person arms and the p_ weapon in
// their hands are what you see; nothing here uses the hidden view model
// except to learn *which* action just happened (its animation names).

#ifndef FPBODY_ANIM_H
#define FPBODY_ANIM_H

struct ref_params_s;

// Registers cvars. Called from FPBody_Init().
void FPAnim_Init( void );

// Called once per frame (from V_CalcRefdef) while the mod is active.
// Handles input-driven actions (use, flashlight, ladder, landing, sway).
void FPAnim_Frame( struct ref_params_s *pparams );

// Called whenever the client starts a weapon (view model) animation.
// viewmodelIndex is the model index of the current v_ model.
void FPAnim_OnWeaponAnim( int iAnim, int viewmodelIndex );

// Called from the studio renderer after the local player's bones are built
// and BEFORE they are cached for the weapon model merge, so the p_ weapon
// follows the animated hands.
void FPAnim_ApplyBones( void *studiohdr, float ( *bonetransform )[ 3 ][ 4 ],
	float ( *lighttransform )[ 3 ][ 4 ], int headBone, int weaponmodel );

// Extra view angles (pitch, yaw, roll) from the head bone's motion.
void FPAnim_GetViewAngleOffset( float *ofs );

#endif // FPBODY_ANIM_H
