#!/bin/sh
# Decay: True First Person's own models (tools/port/BUILD_FPBODY_DECAY.bat
# copies them from the SDK's decay_models folder):
#   fpbody_hls_suit / fpbody_suit / fpbody_classic_suit (+ _helmet): Gina -
#     Half-Life's multiplayer Gina (valve/models/player/gina/Gina.mdl, its
#     high-detail submodel) recoloured to Decay's tan suit, on the fpbody
#     skeletons, with the PS2 hands of Half-Life's fpbody_hls_suit (tan too)
#   fpbody_helmet_prop.mdl: the helmet in her hands (fp_helmet)
#   fpbody_colette.mdl: Colette, the companion - the same Gina in red with
#     Colette's head (Decay - Classic's dm_colette), on the companion
#     (fpbody_buddy.mdl: skeleton, sequences, guns)
# Usage: decay_models.sh <Gina.mdl> <dm_colette.mdl> <bs models dir> <hl fpbody_hls_suit.mdl>
#        <fpbody_buddy.mdl> <p_crowbar.mdl> <workshop dir> <m_anm_gmod.mdl> <out dir>
# The results contain the games' model data: keep them local.
set -e
GINA=$1; COL=$2; BS=$3; HLS=$4; BUDDY=$5; REFP=$6; W=$7; REF=$8; OUT=$9
T=$(dirname "$0"); TMP=$(mktemp -d)
R=$W/107768377,$W/1399300695,$W/608040494,$W/2361014789,$W/610047566
mkdir -p "$OUT"
python3 -I - "$GINA" "$TMP" <<'PY'
import struct, sys, colorsys
d = bytearray(open(sys.argv[1], 'rb').read())
nbp, bpi = struct.unpack_from('<2i', d, 204)
nm, b, mi = struct.unpack_from('<3i', d, bpi + 64)
struct.pack_into('<3i', d, bpi + 64, 1, 1, mi + 112)        # the high-detail submodel only
open(sys.argv[2] + '/gina_hi.mdl', 'wb').write(d)
PY
python3 -I "$T/tint_mdl.py" "$TMP/gina_hi.mdl" "$TMP/gina_tan.mdl" 38 0.35 --only DM_Base.bmp
python3 -I "$T/tint_mdl.py" "$TMP/gina_hi.mdl" "$TMP/gina_red.mdl" 3 1.0 --only DM_Base.bmp
python3 -I - "$TMP/gina_tan.mdl" <<'PY'
import struct, sys, colorsys
p = sys.argv[1]; d = bytearray(open(p, 'rb').read())
ntex, ti = struct.unpack_from('<2i', d, 180)
for t in range(ntex):
    o = ti + t * 80
    if d[o:o + 64].split(b'\0')[0] != b'DM_Base.bmp':
        continue
    w, h, idx = struct.unpack_from('<3i', d, o + 68); pp = idx + w * h
    for i in range(256):          # Gina's maroon trim: dark brown, like Decay's
        r, g, b = d[pp + i * 3:pp + i * 3 + 3]
        H, S, V = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if (H * 360 >= 320 or H * 360 < 8) and S > 0.3:
            nr, ng, nb = colorsys.hsv_to_rgb(30 / 360, S * 0.25, V * 0.8)
            d[pp + i * 3:pp + i * 3 + 3] = bytes((round(nr * 255), round(ng * 255), round(nb * 255)))
open(p, 'wb').write(d)
PY
python3 -I "$T/merge_head.py" "$TMP/gina_red.mdl" "$COL" "$TMP/colette_red.mdl" 0 2
python3 -I "$T/reskin_buddy.py" "$BUDDY" "$TMP/colette_red.mdl" "$OUT/fpbody_colette.mdl"
for m in fpbody_hls_suit fpbody_suit fpbody_classic_suit; do
  python3 -I "$T/build_outfit.py" "$BS/$m.mdl" "$TMP/gina_tan.mdl" - "$TMP/$m.mdl" --blend
  python3 -I "$T/merge_head.py" "$TMP/$m.mdl" "$HLS" "$TMP/h_$m.mdl" 0 2 hands
  python3 -I "$T/tint_mdl.py" "$TMP/h_$m.mdl" "$TMP/h_$m.mdl" 35 0.35 --only leg
  python3 -I -c "import sys; sys.path.insert(0, '$T'); from compact import compact; compact('$TMP/h_$m.mdl', '$OUT/$m.mdl')"
  python3 -I "$T/make_helmet.py" "$OUT/$m.mdl" "$W/107768377/models/player/hl1/helmet.mdl" "$OUT/${m}_helmet.mdl" "$REF" --roots "$R" --tint 35 --sat 0.35
done
python3 -I "$T/make_helmet_prop.py" "$OUT/fpbody_hls_suit_helmet.mdl" "$REFP" "$OUT/fpbody_helmet_prop.mdl"
rm -rf "$TMP"
