# Opposing Force jobs (server)

`fpbody_jobs.inl` lets the player do the engineer's and medic's scripted jobs
himself (of2a3 / of2a5 torch doors, patching up the wounded engineer in of2a5,
crouch + use on any hurt friendly). The client side is in `cl_dll/fpbody_anim.cpp`
(FPM_JOB phases in fuser4 play `fm_job_*`); the animations are added to the
player models with `tools/gmod_anims/add_jobs.py`, the torch / needle props
made with `tools/gmod_anims/npc_prop.py` (both from Gearbox's models: keep the
results local).

Hooks in the Opposing Force SDK's `dlls/`:

- `player.h`: `FPJobs_*` methods and `m_iFPJob`, `m_flFPJobStart`, `m_iFPJobFired`,
  `m_iFPJobPhase`, `m_flFPJobNextFx`, `m_flFPJobNextSnd`, `m_hFPJobTarget`.
- `player.cpp`: save fields (job, start as FIELD_TIME, fired, phase, target);
  in `PlayerUse` after the train block: return while `m_iFPJob > 0`, and
  `if ( use pressed && FPJobs_TryStart() ) return;`;
  `#include "fpbody_jobs.inl"` after `fpbody_moves.inl`.
- `fpbody_moves.inl` (`FPMoves_Think`): clear `7 << FPM_JOB_SHIFT`, call
  `FPJobs_Think()`, set the phase bits while a job runs.
- `client.cpp` (`ClientPrecache`): `FPJobs_Precache()`. It precaches `p_torch` / `p_needle` only on the
  maps whose jobs use them (every model counts against the map's 512 limit:
  of4a4 went over); elsewhere the client draws them itself.
- `cl_dll/StudioModelRenderer.cpp` (the player's weapon model): with no
  `weaponmodel`, draw `FPAnim_JobProp( index )` instead (`cl_dll/fpbody_anim.cpp`).
- `items.cpp` (battery): no extra `w_battery.mdl` precache (a restored entity
  precaches its own model).
