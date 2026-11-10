#!/bin/sh
# Decay: True First Person's own models from Garry's Mod playermodels of Gina
# and Colette, on their own proportions (hls_body.py --own-skeleton), with the
# PS2 hands (hls_body.py --hands: the wrists closed against the hands):
#   LD (the default): Decay's own low-detail models (Workshop 3369374707,
#     "Gina Cross & Colette Green PM": models/half/gina/dm_gina.mdl,
#     models/half/colette/dm_colette.mdl, body choice head=0), with the hands
#     of Workshop 610047566's PS2 Gina and Colette (models/player/hl1/ps2/
#     gina.mdl, colette.mdl: tan and red gloves)
#   or the Extended Workforce ones (Workshop 3478625938,
#     *_scientist_extended.mdl, body choice body=3: the HEV suit)
# tools/port/BUILD_FPBODY_DECAY.bat copies them from the SDK's decay_models folder:
#   fpbody_hls_suit / fpbody_suit / fpbody_classic_suit (+ _helmet): Gina on
#     the fpbody skeletons
#   fpbody_helmet_prop.mdl: the helmet in her hands (fp_helmet)
#   fpbody_colette.mdl: Colette, the companion, on fpbody_buddy.mdl
#     (its skeleton, sequences, guns)
# Usage: decay_models_src.sh <gina.mdl> <colette.mdl> <body choice> <gina hands.mdl>
#        <colette hands.mdl> <bs models dir> <fpbody_buddy.mdl> <p_crowbar.mdl>
#        <workshop dir> <m_anm_gmod.mdl> <out dir>
# Optional: IDLE=<female idle pack .mdl> in the environment (see the end).
# The results contain the games' model data: keep them local.
set -e
GINA=$1; COL=$2; BODY=$3; GH=$4; CH=$5; BS=$6; BUDDY=$7; REFP=$8; W=$9
shift 9; REF=$1; OUT=$2
T=$(dirname "$0"); TMP=$(mktemp -d)
R=$W/3369374707,$W/3478625938,$W/107768377,$W/1399300695,$W/608040494,$W/2361014789,$W/610047566
mkdir -p "$OUT"
python3 -I "$T/hls_body.py" "$BS/fpbody_hls_suit.mdl" "$COL" "$TMP/colette.mdl" "$REF" \
  --roots "$R" --body "$BODY" --own-skeleton --hands "$CH"
python3 -I "$T/reskin_buddy.py" "$BUDDY" "$TMP/colette.mdl" "$OUT/fpbody_colette.mdl"
for m in fpbody_hls_suit fpbody_suit fpbody_classic_suit; do
  python3 -I "$T/hls_body.py" "$BS/$m.mdl" "$GINA" "$TMP/$m.mdl" "$REF" \
    --roots "$R" --body "$BODY" --own-skeleton --hands "$GH"
  python3 -I -c "import sys; sys.path.insert(0, '$T'); from compact import compact; compact('$TMP/$m.mdl', '$OUT/$m.mdl')"
  python3 -I "$T/make_helmet.py" "$OUT/$m.mdl" "$W/107768377/models/player/hl1/helmet.mdl" "$OUT/${m}_helmet.mdl" "$REF" --roots "$R" --tint 35 --sat 0.35 --own-skeleton
done
python3 -I "$T/make_helmet_prop.py" "$OUT/fpbody_hls_suit_helmet.mdl" "$REFP" "$OUT/fpbody_helmet_prop.mdl"
# IDLE=<f_anm_slot_019.mdl> (Workshop 3270357830, [xdR] idle Re-animation2
# female): the women's standing idle (add_idle.py)
if [ -n "$IDLE" ]; then
  for m in fpbody_hls_suit fpbody_suit fpbody_classic_suit; do
    for f in "$OUT/$m.mdl" "$OUT/${m}_helmet.mdl"; do
      python3 -I "$T/add_idle.py" "$f" "$f" "$IDLE" "$REF" --base "$BS/$m.mdl"
    done
  done
  python3 -I "$T/add_idle.py" "$OUT/fpbody_colette.mdl" "$OUT/fpbody_colette.mdl" "$IDLE" "$REF" idle1,idle2,idle3,idle4
fi
rm -rf "$TMP"
