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
| `fpbody_presuit.mdl` | Barney in his guard uniform, while he has no armor |
| `fpbody_suit.mdl` | a blue HEV suit with Barney's head, while he has armor |

`cl_dll/fpbody_game.h` decides what "suited" means: the HEV suit item in
Half-Life and Opposing Force, armor in Blue Shift (its vest and helmet only
add armor).
