# Azure Sheep: True First Person

Built on the Azure Sheep reimplementation
(https://github.com/HL1-Mods-Reimplementations-and-Ports/hl-asheep, commit a4fda3a):

    git clone https://github.com/HL1-Mods-Reimplementations-and-Ports/hl-asheep fpbody_asheep_sdk
    cd fpbody_asheep_sdk && git checkout a4fda3a && git apply ../tools/port/asheep/fpbody_asheep.patch

The patch is this repository's fpbody changes (3-way merged onto the
reimplementation; weapon hold types go through `FPBody_HoldFor` in
`DefaultDeploy`, including Azure Sheep's pool stick, M41A, Beretta, medkit and
toad), `BUILD_FPBODY_ASHEEP.bat` and `fpbody_launcher/` (a small exe that runs
`hl.exe -game fpbody_asheep`, built by the bat with Azure Sheep's icon).

Outfits (`asheep_models/`, not committed: game assets): Blue Shift's Barney -
the guard uniform, then the blue HEV suit once he has the suit item (Azure
Sheep's HEV Barney is blue too).
