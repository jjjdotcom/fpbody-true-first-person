"""Long jump camera: a long jump starts with duck while running, which starts a
slide (fm_slide); the jump ends the slide, but its animation played on into the
air (it was only cut after half a second), with the head - and the camera -
far behind the body, so you saw your own back. Now leaving the ground ends the
slide animation at once.

  python3 longjump_cam.py <sdk dir> [...]      (cl_dll/fpbody_anim.cpp, idempotent)
"""
import sys

OLD = '\t// a one-off move that no longer fits: getting up, moving off, or a vault cut short\n'
NEW = ('\t// a slide cut short by a jump (the long jump: duck while running, then jump):\n'
       '\t// off the ground the slide\'s pose puts the head - the camera - behind the body\n'
       '\tif ( oneShot && OverlayIs( "fm_slide" ) && !( st & FPM_SLIDE ) && !onground )\n'
       '\t{\n'
       '\t\tStopOverlay();\n'
       '\t\toneShot = false;\n'
       '\t}\n\n') + OLD

for d in sys.argv[1:]:
    p = d + '/cl_dll/fpbody_anim.cpp'
    s = open(p, encoding='latin-1', newline='').read()
    nl = '\r\n' if '\r\n' in s else '\n'
    s = s.replace('\r\n', '\n')
    if 'a slide cut short by a jump' not in s:
        if OLD not in s:
            sys.exit('not found in ' + p)
        s = s.replace(OLD, NEW, 1)
    open(p, 'w', encoding='latin-1', newline='').write(s.replace('\n', nl))
    print('ok', d)
