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
| `cl_fpbody_actcam` | `1` | Watch full-body acts from behind (`0` = stay in the head) |
| `cl_fpbody_gmod` | `1` | Use converted GMod animations (reloads, acts) when present |
| `cl_fpbody_outfit` | `1` | Lab coat (`models/fpbody_scientist.mdl`) until you pick up the HEV suit |
| `cl_fpbody_aimfire` | `1` | Turn the gun straight down the view while firing |
| `cl_fpbody_offhand` | `1` | Keep the off hand on two-handed guns (arm IK) |
| `cl_fpbody_grip_fwd` | `0` | Slide the off-hand grip along the gun (units, + = forward) |
| `cl_fpbody_grip_down` | `0` | Move the off-hand grip down (+) or up (−) |

## GMod animations (optional)

`tools/gmod_anims` converts Garry's Mod's player animations onto Half-Life's
player model (you need both games; the result is for personal use and is not
included here). With `fpbody/models/player.mdl` in place:

- movement, jumping, swimming, deaths and every weapon pose use GMod's
  animations (Half-Life picks them by name, no code needed);
- reloads play GMod's reload animation for the pistol, .357, MP5, crossbow
  and RPG (other procedural animations still run on top);
- `build_variant.py` gives Half-Life's scientist player model the same
  animations (`fpbody/models/fpbody_scientist.mdl`); Gordon wears it until he
  picks up the HEV suit;
- `fp_act <name>` plays a gesture or taunt (`fp_act dance`, `fp_act wave`,
  `fp_act salute`, ...), `fp_act_stop` stops it, `fp_actlist` lists all 75.
  Full-body acts end when you move, shoot or jump.

## Moves from the Half-Life 2 "Freeman" mod

Ported from the Freeman mod (Source): its movement code, re-written for
GoldSrc's player movement, and its animations, converted onto the player
models by `tools/gmod_anims/add_freeman.py` (the packs are Garry's Mod Workshop
animation addons the Freeman mod uses; the converted models stay local).

| Move | How | Code |
|---|---|---|
| Kick | `pm_kick` (V). Look down to stomp, kick in the air for a drop kick (double damage). Opens doors you could open with +use, pushes what it hits and you back. | `dlls/fpbody_moves.inl` (impulse 211) |
| Vault / mantle / pull-up | Jump at a ledge or low wall holding forward: hop over a low wall, climb onto a chest-high ledge, pull up onto a high one. | `pm_shared/fpbody_pm_move.h` |
| Wall climb | Jump at a wall and keep holding jump (3 pushes); forward at the top pulls you up. | same |
| Slide | Duck while running. | same |
| Prone | `pm_prone` (Z) or double-tap duck; jump gets up. Uses the duck hull, half its speed. | same (impulse 210) |
| At ease | The gun lowers after `cl_fpbody_atease_delay` (4) quiet seconds; `pm_atease` (B) lowers / raises it. | `cl_dll/fpbody_anim.cpp` |
| Holster all | `pm_holster` (G) or double-tap reload: empty hands; again, or fire, takes the gun out. | `dlls/fpbody_moves.inl` (impulse 212) |
| Falls, landings | Falling plays a fall loop; a hard landing a crouch-and-recover, or a roll when running. | `cl_dll/fpbody_anim.cpp` |
| Weapon draws | Drawing a gun plays a draw animation for its kind. | same |

| ExtendedER Player Animations | Fidgets after standing around (head nods and shakes, stretches, arm gestures), a bend-down when you pick things up and at the top of a ladder, cowering / crouch-walking / panicked running when empty-handed near a fight, flinches by damage type (shock spasms, acid gagging, burns, crushing, blasts, bullets), and a lowered gun comes up when a hostile is in front of you. `cl_fpbody_epa 0` turns it off; `cl_fpbody_epa_fidget_*` tune the fidgets. | `cl_dll/fpbody_anim.cpp`; fights and hostiles from the server (`fpbody_moves.inl`) |
| Contextual Player Animations | A push when you open a door, a press for buttons, a reach for anything else you +use (health and HEV chargers keep reaching while you hold use), bullet flinches where you were hit (head, chest, stomach, either arm or leg), and a flinch going under water and coming up for air. `cl_fpbody_contextual 0` turns it off. | `cl_dll/fpbody_anim.cpp`; what you used and the hit group from the server (`fpbody_moves.inl`, `PlayerUse`) |
| COD IW idle | The empty-hands standing idle is the [xdR] COD IW Idle animation when its model is given to `add_freeman.py` (6th argument; Garry's Mod's idle otherwise). | `tools/gmod_anims/add_freeman.py` |
| Half-Life: Source bodies | With the GMod animations (`cl_fpbody_classic 0`), the bodies come from the Half-Life: Source / Blue Shift / Opposing Force Garry's Mod playermodels (Workshop 107768377, 608040494, 2361014789): `models/fpbody_hls_suit.mdl` / `fpbody_hls_presuit.mdl`. The skeleton is re-proportioned to Garry's Mod's, which those models and the animations share, so the animations fit them exactly. `cl_fpbody_hls 0` goes back to the other bodies. Built locally with `tools/gmod_anims/hls_body.py` (reads Source MDL/VVD/VTX and VMT/VTF with `srcmesh.py`); the results contain the playermodels' data and are not committed. | `cl_dll/fpbody.cpp` |
| Sprint | Hold Shift (`+alt1`) while moving forward: 25% faster (400 instead of 320), with stamina - 6 seconds of sprint on a full bar, refilling over 4 seconds starting a second after you stop; run it dry and it waits until a third is back and you let go. Shooting or reloading stops it. Each weapon type has its own sprint animation (Black Ops III, Workshop 3807533640). `cl_fpbody_sprint 0` turns it off; `cl_fpbody_sprint_time` / `cl_fpbody_sprint_recover` tune the stamina. | `pm_shared/fpbody_pm_move.h` (FPM_PostDuck), `cl_dll/fpbody_anim.cpp`, `cl_dll/input.cpp` |
| Left 4 Dead animations | With the GMod animations, the walk / run / crouch / jump / swim cycles and every weapon hold come from the [xdR] Left 4 Dead animations (Workshop 2411672781), their layers (world-space upper body, arms, aim matrix, idle noise) combined by `tools/gmod_anims/add_l4d.py`. Attack gestures the pack lacks stay Garry's Mod's. | `tools/gmod_anims/add_l4d.py` |

Fidgets and flinches are *additive* layers (`fa_` sequences): the studio
renderer adds their bone rotations on top of whatever the body is playing
(`FPAnim_GetAdditive` in `StudioSetupBones`), the way Source layers gestures.
Some fidgets are Half-Life 2's own male gestures: `add_freeman.py` takes
`models/humans/male_gestures.mdl` (from `hl2/hl2_misc_dir.vpk`, see `vpk.py`)
as an optional last argument.

The movement runs in `pm_shared`, so it's predicted on the client like the
rest of Half-Life's movement; the state is in the player's `fuser4` (bits) and
`fuser1` (timer). **Each mod folder needs its own `delta.lst`** with `fuser4`
widened, made from the game's with `tools/port/delta_lst.py`; without it the
client never learns about moves the server confirmed. `fpbody/autoexec.cfg`
binds the keys. `cl_fpbody_moves 0` turns the animations off (the moves keep
working), `cl_fpbody_atease 0` the lowered gun, `cl_fpbody_doubletap 0` the
double-taps. Other mods: `tools/port/freeman_moves.py <sdk>` (run by
`apply_fpbody.py`).

## Limitations

- The first-person view model isn't drawn (the engine hides it in third
  person); you aim with the gun in the body's hands and the crosshair.
- Arms are moved as rigid pieces, so shoulders can separate slightly during
  strong motions.
- The software renderer gets the body and camera but not the procedural
  animations.
