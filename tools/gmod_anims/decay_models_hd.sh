#!/bin/sh
# Decay: True First Person's own models in the PS2 / HD style:
#   Gina: the PS2 Gina of Workshop 610047566 (models/player/hl1/ps2/gina.mdl)
#   Colette: Jabroni Brawl Episode 3's (Workshop 2974010532,
#     models/player/jbep3/colette.mdl), her suit in Decay's red (Garry's Mod's
#     player colour: hls_body.py --player-color)
# both on their own proportions (hls_body.py --own-skeleton), with their own
# PS2 gloves. tools/port/BUILD_FPBODY_DECAY.bat copies them from the SDK's
# decay_models folder:
#   fpbody_hls_suit / fpbody_suit / fpbody_classic_suit (+ _helmet, the PS2
#     helmet tinted tan): Gina on the fpbody skeletons
#   fpbody_helmet_prop.mdl: the helmet in her hands (fp_helmet)
#   fpbody_colette.mdl: Colette, the companion, on fpbody_buddy.mdl
# Usage: decay_models_hd.sh <bs models dir> <fpbody_buddy.mdl> <p_crowbar.mdl>
#        <workshop dir> <m_anm_gmod.mdl> <out dir>
# Optional: IDLE=<female idle pack .mdl> in the environment (see the end).
# The results contain the games' model data: keep them local.
set -e
BS=$1; BUDDY=$2; REFP=$3; W=$4; REF=$5; OUT=$6
T=$(dirname "$0"); TMP=$(mktemp -d)
R=$W/2974010532,$W/610047566,$W/107768377
mkdir -p "$OUT"
python3 -I "$T/hls_body.py" "$BS/fpbody_hls_suit.mdl" "$W/2974010532/models/player/jbep3/colette.mdl" "$TMP/colette.mdl" "$REF" \
  --roots "$R" --own-skeleton --player-color 240,60,45
python3 -I "$T/reskin_buddy.py" "$BUDDY" "$TMP/colette.mdl" "$OUT/fpbody_colette.mdl"
for m in fpbody_hls_suit fpbody_suit fpbody_classic_suit; do
  python3 -I "$T/hls_body.py" "$BS/$m.mdl" "$W/610047566/models/player/hl1/ps2/gina.mdl" "$TMP/$m.mdl" "$REF" \
    --roots "$R" --own-skeleton
  python3 -I -c "import sys; sys.path.insert(0, '$T'); from compact import compact; compact('$TMP/$m.mdl', '$OUT/$m.mdl')"
  python3 -I "$T/make_helmet.py" "$OUT/$m.mdl" "$W/610047566/models/player/hl1/ps2/helmet.mdl" "$OUT/${m}_helmet.mdl" "$REF" --roots "$R" --tint 35 --sat 0.35 --own-skeleton
done
python3 -I "$T/make_helmet_prop.py" "$OUT/fpbody_hls_suit_helmet.mdl" "$REFP" "$OUT/fpbody_helmet_prop.mdl"
# IDLE=<f_anm_slot_019.mdl> (Workshop 3270357830, [xdR] idle Re-animation2
# female): the women's standing idle (add_idle.py)
if [ -n "$IDLE" ]; then
  for f in "$OUT"/fpbody_*suit*.mdl; do
    python3 -I "$T/add_idle.py" "$f" "$f" "$IDLE" "$REF"
  done
  python3 -I "$T/add_idle.py" "$OUT/fpbody_colette.mdl" "$OUT/fpbody_colette.mdl" "$IDLE" "$REF" idle1,idle2,idle3,idle4
fi
rm -rf "$TMP"
