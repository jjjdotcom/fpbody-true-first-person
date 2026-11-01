# Ports to Blue Shift and Opposing Force

The fpbody client code also runs on the community-maintained
[Blue Shift Updated](https://github.com/twhl-community/halflife-bs-updated) and
[Opposing Force Updated](https://github.com/twhl-community/halflife-op4-updated)
SDKs. Their source isn't copied here; `apply_fpbody.py` patches a checkout:

    git clone https://github.com/twhl-community/halflife-bs-updated fpbody_bs_sdk
    python3 tools/port/apply_fpbody.py fpbody_bs_sdk bshift
    copy tools\port\BUILD_FPBODY_BS.bat fpbody_bs_sdk\

Put `fpbody_bs_sdk` in the Half-Life folder (next to `bshift`) and run
`BUILD_FPBODY_BS.bat`. It builds client.dll and hl.dll into `..\fpbody_bs`
and copies Blue Shift's maps there with their BSP header fixed (Blue Shift
swaps the first two lumps, which only the original `bshift` folder accepts).

Outfits (built with `tools/gmod_anims/outfits.py`, not committed because they
contain game assets) go in `fpbody_bs/models`:

| file | shown |
| --- | --- |
| `player.mdl` | the converted fpbody player model (skeleton + GMod sequences) |
| `fpbody_presuit.mdl` | Barney in his guard uniform (original model), while he has no armor |
| `fpbody_suit.mdl` | a blue HEV suit with Barney's head, while he has armor |

`cl_dll/fpbody_game.h` decides what "suited" means: the HEV suit item in
Half-Life and Opposing Force, armor in Blue Shift (its vest and helmet only
add armor).

## Opposing Force

    git clone https://github.com/twhl-community/halflife-op4-updated fpbody_op4_sdk
    python3 tools/port/apply_fpbody.py fpbody_op4_sdk op4
    copy tools\port\BUILD_FPBODY_OP4.bat fpbody_op4_sdk\

`BUILD_FPBODY_OP4.bat` builds into `..\fpbody_op4` (Opposing Force maps need no
conversion). Outfits (`outfits.py op4`): `fpbody_presuit.mdl` is Shephard
without the PCV vest (his player model's second body), `fpbody_suit.mdl` a
green HEV suit with his helmet and gas mask, shown once he has the PCV
(the suit item). The player model also gets `*_penguin` sequences (held like
the snark), which Opposing Force's penguin asks for.

## Half-Life: Echoes

Echoes' code is public as the `echoes` branch of FWGS's
[hlsdk-portable](https://github.com/FWGS/hlsdk-portable/tree/echoes) (Spirit of
Half-Life based, built with CMake):

    git clone -b echoes --recursive https://github.com/FWGS/hlsdk-portable fpbody_echoes_sdk
    python3 tools/port/apply_echoes.py fpbody_echoes_sdk
    copy tools\port\BUILD_FPBODY_ECHOES.bat fpbody_echoes_sdk\

Put `fpbody_echoes_sdk` in the Half-Life folder, next to an installed `echoes`
folder, and run `BUILD_FPBODY_ECHOES.bat` (it needs Visual Studio's "C++ CMake
tools for Windows"). It builds client.dll and echoes.dll into `..\fpbody_echoes`,
writes its liblist.gam from Echoes' own (with `fallback_dir "echoes"`, so the
maps, sounds and models come from Echoes) and copies the body models,
delta.lst and settings from the Half-Life mod (`..\fpbody`). Echoes keeps its
own weapon and ammo balance.

## Half-Life: Field Intensity

Field Intensity's code is the `field_intensity_1.7` branch of FreeSlave's
[Half-Life Featureful SDK](https://github.com/FreeSlave/halflife-featureful)
(hlsdk-portable based, CMake):

    git clone -b field_intensity_1.7 --recursive https://github.com/FreeSlave/halflife-featureful fpbody_fi_sdk
    python3 tools/port/apply_fi.py fpbody_fi_sdk
    copy tools\port\BUILD_FPBODY_FI.bat fpbody_fi_sdk\

`BUILD_FPBODY_FI.bat` builds into `..\fpbody_fi` with `fallback_dir
"field_intensity"`. Its weapons take their player animation extension from
templates, so `DefaultDeploy` maps them by the gun's p_ model to the fpbody
holds. delta.lst is Field Intensity's own, with fuser4 widened to 24 bits; the
Half-Life p_ models are copied only where Field Intensity has none of its own.
