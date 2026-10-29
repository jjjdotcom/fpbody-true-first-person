# GMod animations → Half-Life player model

Converts Garry's Mod's player animations (`models/m_anm.mdl` + `m_anm.ani`,
ValveBiped skeleton) onto Half-Life's `player.mdl` (Bip01 skeleton) and writes
`fpbody/models/player.mdl`. **You need your own copy of both games**; the
converted model contains Valve/Facepunch animation data, so keep it local and
don't publish it.

## What it does

- `srcmdl.py` reads Source MDL v44–49 skeletons and animations (compressed
  tracks, `.ani` blocks, delta animations), following the Source SDK 2013.
- `retarget.py` maps ValveBiped bones to Bip01 in world space, correcting for
  the different rest poses (T-pose vs A-pose) and the 36-unit origin offset.
- `goldsrc.py` reads/writes GoldSrc studio models; existing sequences are
  re-encoded, bone scales recomputed, long clips automatically halved in frame
  rate to fit 16-bit offsets.
- `build.py` replaces Half-Life's sequences by name (gaits, jump/swim, deaths,
  `ref_aim_*` / `ref_shoot_*` / `crouch_*` per weapon with pitch blends built
  from GMod's aim layers) and appends gestures, taunts, poses and reloads as
  `gm_*` sequences, which the client plays with `fp_act`.

## Running

Requires Python 3 with numpy (and matplotlib for `viz.py`).

1. Extract `models/m_anm.mdl` and `models/m_anm.ani` from
   `GarrysMod/garrysmod/garrysmod_dir.vpk` (use `vpk.py`: `read_dir()` gives
   archive index, offset and length) into `src/`.
2. Copy `Half-Life/valve/models/player.mdl` to `src/hl_player.mdl`.
3. `python3 build.py src/hl_player.mdl src/m_anm.mdl src/m_anm.ani out/player.mdl`
4. Copy `out/player.mdl` to `Half-Life/fpbody/models/player.mdl`.

To add or remap animations, edit the `HOLD` table (weapon poses), the gait /
death lists, or the extras filter at the bottom of `build.py`.

## Pre-suit outfit (Blue Shift lab coat)

`fpbody/models/fpbody_scientist.mdl` (shown until the HEV suit is picked up)
is built from Blue Shift's own lab-coat Gordon. Its mesh is moved onto the
converted player skeleton, so every fpbody/GMod sequence still works:

    python3 -I build_outfit.py fpbody/models/player.mdl \
        bshift_hd/models/gordon_scientist.mdl bshift_hd/models/gordon_scientistT.mdl \
        fpbody/models/fpbody_scientist.mdl

(Use `bshift/models/...` and `-` for the T model for the SD version.)
`render_mdl.py` draws a model in a few poses as a quick check. The generated
model contains Blue Shift data and is not committed.
