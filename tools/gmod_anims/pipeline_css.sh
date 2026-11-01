set -e
cd /home/claude/hlsdk/tools/gmod_anims
F=/mnt/user-data/uploads/Freeman/models
C=/home/claude/gmodconv/src/css/cs_player_shared.mdl
W=/home/claude/gmodconv/src/ws; R=$W/107768377,$W/1399300695,$W/608040494,$W/2361014789
REF=$F/m_anm_gmod.mdl; HEV=$W/107768377/models/player/hl1/player.mdl; OP="$W/2361014789/models/player/opposing force"
S2=/mnt/user-data/outputs/p2; S3=/mnt/user-data/outputs/p3; FIN=/mnt/user-data/outputs/final_css
rm -rf $S3; mkdir -p $S3/fpbody $S3/fpbody_bs $S3/fpbody_op4
for m in fpbody fpbody_bs fpbody_op4; do
  for f in /mnt/user-data/outputs/freeman2/$m/*.mdl; do b=$(basename $f)
    case $b in fpbody_classic*) cp $S2/$m/$b $S3/$m/$b;;
      *) ( python3 -I add_css.py $C $F $S2/$m/$b $S3/$m/$b >/dev/null && echo "css $m/$b" ) & ;;
    esac
  done
done; wait
b(){ python3 -I hls_body.py "$@" --roots $R | tail -1; }
b $S3/fpbody/player.mdl $HEV $S3/fpbody/fpbody_hls_suit.mdl $REF &
b $S3/fpbody/player.mdl $W/608040494/models/player/blueshift/scientist_gordon.mdl $S3/fpbody/fpbody_hls_presuit.mdl $REF &
b $S3/fpbody_bs/fpbody_suit.mdl $W/608040494/models/player/blueshift/barney.mdl $S3/fpbody_bs/fpbody_hls_presuit.mdl $REF --body armor=0,helmet=0 &
b $S3/fpbody_bs/fpbody_suit.mdl $HEV $S3/fpbody_bs/fpbody_hls_suit.mdl $REF --head $W/608040494/models/player/blueshift/barney.mdl --head-body armor=0,helmet=0 --tint 215 &
b $S3/fpbody_op4/fpbody_suit.mdl "$OP/recruit.mdl" $S3/fpbody_op4/fpbody_hls_presuit.mdl $REF &
b $S3/fpbody_op4/fpbody_suit.mdl $HEV $S3/fpbody_op4/fpbody_hls_suit.mdl $REF --head "$OP/hgrunt_opfor_mask.mdl" --tint 80 --sat 0.5 &
wait
rm -rf $FIN; for m in fpbody fpbody_bs fpbody_op4; do mkdir -p $FIN/$m; for f in $S3/$m/*.mdl; do python3 -I compact.py $f $FIN/$m/$(basename $f) >/dev/null & done; done; wait
du -sh $FIN/*; ls $FIN/* | wc -l
