"""Prone on a double-tap of walk (+speed: Shift, LB on a controller) instead
of duck.

  python3 prone_shift.py <sdk dir> [...]          (idempotent)

cl_dll/input.cpp        IN_SpeedDown reports a fresh press (FPBody_SpeedPressed)
cl_dll/fpbody_anim.cpp  FPBody_SpeedPressed: a double-tap lies down / gets up;
                        a double-tap of duck no longer does
"""
import re
import sys

DECL = 'void FPBody_SpeedPressed( int fresh );\t// fpbody: double-tap walk (Shift / LB) = prone\n'

ANIM_OLD = '''void FPBody_DuckPressed( int fresh )
{
	if ( FPM_ENABLE_PRONE && fresh && cl_fpbody_doubletap && cl_fpbody_doubletap->value != 0.0f && FPBody_Active() &&
		 DoubleTap( g_mvLastDuck ) )
		PM_ProneCmd();
}
'''
ANIM_NEW = '''// prone is a double-tap of walk (+speed: Shift, LB on a controller), not of duck
void FPBody_DuckPressed( int fresh )
{
}

void FPBody_SpeedPressed( int fresh )
{
	if ( FPM_ENABLE_PRONE && fresh && cl_fpbody_doubletap && cl_fpbody_doubletap->value != 0.0f && FPBody_Active() &&
		 DoubleTap( g_mvLastDuck ) )
		PM_ProneCmd();
}
'''


def rd(p):
    s = open(p, encoding='latin-1', newline='').read()
    return s.replace('\r\n', '\n'), ('\r\n' if '\r\n' in s else '\n')


for d in sys.argv[1:]:
    p = d + '/cl_dll/fpbody_anim.cpp'
    s, nl = rd(p)
    if 'FPBody_SpeedPressed' not in s:
        if ANIM_OLD not in s:
            sys.exit('anim: ' + p)
        s = s.replace(ANIM_OLD, ANIM_NEW)
        s = s.replace('//   cl_fpbody_doubletap 1    double-tap duck = prone,', '//   cl_fpbody_doubletap 1    double-tap walk (Shift / LB) = prone,')
        s = s.replace('//   pm_prone          lie down / get up (or double-tap duck)', '//   pm_prone          lie down / get up (or double-tap walk: Shift / LB)')
        s = s.replace('// double-taps (duck = prone, reload = holster all)', '// double-taps (walk = prone, reload = holster all)')
    open(p, 'w', encoding='latin-1', newline='').write(s.replace('\n', nl))

    p = d + '/cl_dll/input.cpp'
    s, nl = rd(p)
    if 'FPBody_SpeedPressed' not in s:
        s = re.sub(r'(void FPBody_DuckPressed\( int fresh \);[^\n]*\n)', lambda m: m.group(1) + DECL, s, count=1)
        s, k = re.subn(r'(void IN_SpeedDown\s*\(\s*(?:void)?\s*\)\s*\{)(\s*)(KeyDown\s*\(\s*&in_speed\s*\);)',
                       lambda m: m.group(1) + m.group(2) + 'FPBody_SpeedPressed( !( in_speed.state & 1 ) );\t/* fpbody */' +
                       ( m.group(2) if '\n' in m.group(2) else ' ' ) + m.group(3), s, count=1)
        if not k or 'FPBody_SpeedPressed( int' not in s:
            sys.exit('input: ' + p)
    open(p, 'w', encoding='latin-1', newline='').write(s.replace('\n', nl))
    print('ok', d)
