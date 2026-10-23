# Half-Life: True First Person (fpbody)

A client-side mod for Half-Life that puts the camera inside the head of the
player's own third-person body. You see your body, legs and the weapon in your
hands; the view moves with the model's head; and the body is animated for
reloads, weapon switches, recoil, melee, throws, using things, ladders and more.

This repository is Valve's [Half-Life SDK](https://github.com/ValveSoftware/halflife)
with the mod added on top. The mod's code is in `cl_dll/fpbody*.cpp`, with small
hooks in `view.cpp`, `in_camera.cpp`, `StudioModelRenderer.cpp`,
`com_weapons.cpp`, `hl/hl_weapons.cpp` and `hud.h`.

## Building (Windows)

1. Install Visual Studio 2019, 2022 or 2026 with the **Desktop development with C++** workload.
2. Double-click `BUILD_FPBODY.bat`. It finds your Visual Studio, picks the
   matching toolset and builds `client.dll` (Release | Win32) into `fpbody\cl_dlls`.

You can also open `projects/vs2019/projects.sln`, retarget if asked, and build
**hl_cdll** in *Release | Win32*.

## Installing

1. Copy the `fpbody` folder into your Half-Life install, next to `valve`.
2. Copy `valve\dlls\hl.dll` into `fpbody\dlls\`.
3. Restart Steam and launch **Half-Life: True First Person**, or run `hl.exe -game fpbody`.

## How it works

- `CL_IsThirdPerson()` reports third person while the mod is active, so the
  engine draws the local player model and its `p_` weapon.
- After the skeleton is built, procedural animations move the arm and spine
  bones (before the weapon model is merged onto the hands), the head bone's
  position is recorded, and the head is collapsed so it doesn't block the view.
- The camera is placed at the recorded head position, traced against walls,
  and tilted by the fast part of the head's rotation.
- Weapon actions are recognised from the (hidden) view model's animation
  names, so every weapon gets animations: draw/deploy, holster, shoot/fire,
  reload, shotgun shells and pump, crowbar attacks, grenade and snark throws,
  tripmine/satchel placing, gauss charge and egon beam.
- Action buttons: `+use` reaches out with the off hand, the flashlight taps
  the helmet, ladders make the off hand climb, landings dip the body, and the
  gun sways when turning or strafing.

## Console variables

| Cvar | Default | Meaning |
|---|---|---|
| `cl_fpbody` | `1` | Mod on/off |
| `cl_fpbody_forward` | `4` | Eye offset forward of the head joint |
| `cl_fpbody_up` | `3` | Eye offset above the head joint |
| `cl_fpbody_right` | `0` | Eye offset to the right |
| `cl_fpbody_hidehead` | `1` | Collapse the head so it doesn't block the view |
| `cl_fpbody_smooth` | `0` | Smooth head motion (try `15`) |
| `cl_fpbody_anims` | `1` | Procedural body animations on/off |
| `cl_fpbody_animscale` | `1` | Strength of the procedural animations |
| `cl_fpbody_sway` | `1` | Weapon sway / lag strength |
| `cl_fpbody_headrot` | `0.6` | How much the camera follows the head's tilt |

## Limitations

- The first-person view model isn't drawn (the engine hides it in third
  person); you aim with the gun in the body's hands and the crosshair.
- Arms are moved as rigid pieces, so shoulders can separate slightly during
  strong motions.
- The software renderer gets the body and camera but not the procedural
  animations.
