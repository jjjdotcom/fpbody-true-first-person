"""ExtendedER hooks in the client: the additive gesture layer in the studio
renderer and the damage types for the flinches.

  python3 epa_hooks.py <sdk folder>

cl_dll/StudioModelRenderer.cpp  StudioSetupBones: add the fa_ layer
                                (FPAnim_GetAdditive / FPAnim_AddLayer) before the bones
                                are built
cl_dll/health.cpp               MsgFunc_Damage: FPAnim_OnDamage( amount, bits )
Idempotent.
"""
import os
import re
import sys

LAYER = '''
	// fpbody: an additive gesture layer on the local player (ExtendedER fidgets, flinches)
	{
		int addSeq;
		float addFrame, addWeight;
		if ( m_pPlayerInfo && FPAnim_GetAdditive( m_pCurrentEntity->index, m_pStudioHeader, &addSeq, &addFrame, &addWeight ) )
		{
			mstudioseqdesc_t *pad = (mstudioseqdesc_t *)( (byte *)m_pStudioHeader + m_pStudioHeader->seqindex ) + addSeq;
			unsigned char ctl[ 4 ], prev[ 4 ], neutral[ 4 ];
			memcpy( ctl, m_pCurrentEntity->curstate.controller, 4 );
			memcpy( prev, m_pCurrentEntity->latched.prevcontroller, 4 );
			FPAnim_NeutralControllers( m_pStudioHeader, neutral );	// the layer must not turn the controller bones again
			memcpy( m_pCurrentEntity->curstate.controller, neutral, 4 );
			memcpy( m_pCurrentEntity->latched.prevcontroller, neutral, 4 );
			StudioCalcRotations( pos3, q3, pad, StudioGetAnim( m_pRenderModel, pad ), addFrame );
			memcpy( m_pCurrentEntity->curstate.controller, ctl, 4 );
			memcpy( m_pCurrentEntity->latched.prevcontroller, prev, 4 );
			FPAnim_AddLayer( q, q3, m_pStudioHeader->numbones, addWeight );
		}
	}

'''


def patch(path, fn, marker):
    s = open(path, encoding='latin-1', newline='').read()
    if marker in s:
        print('already patched', path)
        return
    nl = '\r\n' if '\r\n' in s else '\n'
    s2 = fn(s.replace('\r\n', '\n')).replace('\n', nl)
    assert s2 != s
    open(path, 'w', encoding='latin-1', newline='').write(s2)
    print('patched', path)


def renderer(s):
    i = s.index('::StudioSetupBones')
    m = re.compile(r'\n([ \t]*)for\s*\(\s*i\s*=\s*0;\s*i\s*<\s*m_pStudioHeader->numbones;\s*i\+\+\s*\)\s*\n\s*\{\s*\n(?:[^\n]*\n){0,3}?\s*QuaternionMatrix\(\s*q\[i\],\s*bonematrix\s*\);').search(s, i)
    assert m
    return s[:m.start()] + '\n' + LAYER.rstrip('\n') + '\n' + s[m.start():]


def health(s):
    s, n = re.subn(r'(\n([ \t]*)(?:const\s+)?long\s+bitsDamage\s*=\s*READ_LONG\(\s*\);[^\n]*\n)',
                   r'\1\2FPAnim_OnDamage( damageTaken + armor, bitsDamage );\t// fpbody: ExtendedER flinches\n', s, count=1)
    assert n == 1
    s, n = re.subn(r'(#include "hud\.h"[^\n]*\n)', r'\1#include "fpbody_anim.h"\n', s, count=1)
    assert n == 1
    return s


def main(sdk):
    patch(os.path.join(sdk, 'cl_dll', 'StudioModelRenderer.cpp'), renderer, 'FPAnim_GetAdditive')
    patch(os.path.join(sdk, 'cl_dll', 'health.cpp'), health, 'FPAnim_OnDamage')


if __name__ == '__main__':
    main(sys.argv[1])
