// fpbody.h - "True first person" / body awareness for Half-Life.
//
// The engine draws the local player's third-person model (player.mdl and the
// p_ weapon in its hands), the head is collapsed so it doesn't block the view,
// and the camera is placed at the head bone of that animated body.

#ifndef FPBODY_H
#define FPBODY_H

struct ref_params_s;
struct cl_entity_s;

// Registers the cl_fpbody* cvars. Called from V_Init().
void FPBody_Init( void );

// Called at the start of every V_CalcRefdef() with the engine's view params,
// so the mod knows whether it should be active this frame (intermission,
// trigger_camera views, death, etc. turn it off).
void FPBody_BeginFrame( struct ref_params_s *pparams );

// True when the body should be drawn and the camera put in its head.
// Exported to the engine through CL_IsThirdPerson().
int FPBody_Active( void );

// Called from the studio renderer right after the local player's bones are
// built. Records where the head is and collapses the head so it's invisible.
void FPBody_ProcessPlayerBones( int playerNumber, struct cl_entity_s *ent, void *studiohdr,
	float ( *bonetransform )[ 3 ][ 4 ], float ( *lighttransform )[ 3 ][ 4 ], int weaponmodel );

// Called by the studio renderer before the player model's transform is set up
void FPBody_LevelBody( int playerNumber, struct cl_entity_s *ent );

// Model to draw for the local player instead of the normal one: the outfit
// before the suit (Gordon's lab coat, Barney's uniform...) and, where the game
// has one, the suit. NULL = use the normal model.
struct model_s *FPBody_GetOutfitModel( int playerNumber );

// Computes the camera origin at the body's head. Returns 0 if no recent head
// position is available, in which case the normal eye position is used.
int FPBody_GetViewOrigin( struct ref_params_s *pparams, float *outOrigin );

#endif // FPBODY_H
