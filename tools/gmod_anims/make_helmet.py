"""The HEV helmet on an fpbody suit model: <suit>_helmet.mdl, drawn while the
helmet is on (fp_helmet, cl_dll/fpbody.cpp).

  python3 -I make_helmet.py <suit.mdl> <helmet playermodel (Source)> <out.mdl> \
        <ref m_anm_gmod.mdl> --roots dir,... [--tint hue] [--sat s]

The helmet comes from a Garry's Mod playermodel on the ValveBiped skeleton:
Half-Life: Source's helmet (Workshop 107768377, low detail) or the PS2 one
(Workshop 610047566, high detail, for Echoes). It is put on the suit model's
skeleton with hls_body.py (recoloured with --tint / --sat like the suit, so a
blue or green suit gets a matching collar), then its head and neck - every
triangle with a corner on the head - replace the suit model's (merge_head.py,
corners 1). Everything else of the suit model is kept: its body, skeleton,
sequences, hitboxes and attachments. The result contains the models' data:
keep it local.
"""
import argparse
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import merge_head                     # noqa: E402
from compact import compact           # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('suit'); ap.add_argument('helmet'); ap.add_argument('out'); ap.add_argument('ref')
    ap.add_argument('--roots', default='')
    ap.add_argument('--tint', type=float, default=None)
    ap.add_argument('--sat', type=float, default=1.0)
    ap.add_argument('--corners', default='1', help="merge_head.py's corners: 2 leaves the suit's own collar")
    ap.add_argument('--own-skeleton', action='store_true', help='hls_body.py --own-skeleton (a suit model built that way)')
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        body = os.path.join(tmp, 'helmet_body.mdl')
        cmd = [sys.executable, '-I', os.path.join(HERE, 'hls_body.py'), a.suit, a.helmet, body, a.ref, '--roots', a.roots]
        if a.tint is not None:
            cmd += ['--tint', str(a.tint), '--sat', str(a.sat)]
        if a.own_skeleton:
            cmd += ['--own-skeleton']
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        merged = os.path.join(tmp, 'merged.mdl')
        merge_head.main(a.suit, body, merged, '0', a.corners)
        compact(merged, a.out)
    print('wrote', a.out)


if __name__ == '__main__':
    main()
