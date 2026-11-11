"""Never cull your own body (cl_dll/StudioModelRenderer.cpp, StudioDrawPlayer).

  python3 body_nocull.py <sdk dir> [...]          (idempotent)

The engine skips a model whose bounding box is out of view. The player's box
is the sequence's, round the origin; lying down the camera is at the head, far
in front of the origin, so looking ahead the box was behind the camera: the
body wasn't drawn, the camera lost the head and fell back to the origin -
behind the body, looking at your own back - where the box was in view again,
and so on every frame (the flashing). Your own body is always drawn now.
"""
import re
import sys

for d in sys.argv[1:]:
    p = d + '/cl_dll/StudioModelRenderer.cpp'
    s = open(p, encoding='latin-1', newline='').read()
    if 'fpbody: never cull your own body' not in s:
        a = s.index('::StudioDrawPlayer(')
        m = re.compile(r'if\s*\(\s*(?:0\s*==\s*IEngineStudio\.StudioCheckBBox\s*\(\s*\)|!\s*IEngineStudio\.StudioCheckBBox\s*\(\s*\))\s*\)').search(s, a)
        if not m:
            sys.exit('no bbox check after StudioDrawPlayer in ' + p)
        new = ('if ( !IEngineStudio.StudioCheckBBox() && !( FPBody_Active() && gEngfuncs.GetLocalPlayer() && '
               'pplayer->number == gEngfuncs.GetLocalPlayer()->index ) )\t// fpbody: never cull your own body')
        s = s[:m.start()] + new + s[m.end():]
    open(p, 'w', encoding='latin-1', newline='').write(s)
    print('ok', d)
