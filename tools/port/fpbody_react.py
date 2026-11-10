"""Hit reactions by who hit us (sv_fpbody_knockdown): copy dlls/fpbody_react.inl
into an SDK and hook it in. Run after the fpbody port (apply_*.py / freeman_moves.py).

  python3 fpbody_react.py <sdk root> <classic|updated|fi|op4>

  pm_shared/fpbody_pm.h  FPM_KNOCK (bit 22 of the move state), FPM_KNOCK_DUR
  dlls/game.cpp          sv_fpbody_knockdown (1 / 0, archived)
  dlls/player.cpp        #include "fpbody_react.inl"; TakeDamage calls
                         FPReact_OnDamage first; PreThink FPReact_Think
The client side (fm_knockdown while FPM_KNOCK is set) is in cl_dll/fpbody_anim.cpp,
the animation in the player models from tools/gmod_anims/add_knockdown.py.
"""
import os, re, shutil, sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
root, flavour = sys.argv[1], sys.argv[2]
def rd(p):
    return open(os.path.join(root, p), encoding='latin-1', newline='').read()
def wr(p, s):
    open(os.path.join(root, p), 'w', encoding='latin-1', newline='').write(s)
def nl(s):
    return '\r\n' if '\r\n' in s else '\n'
if os.path.abspath(root) != REPO:
    shutil.copy(os.path.join(REPO, 'dlls/fpbody_react.inl'), os.path.join(root, 'dlls/fpbody_react.inl'))
p = 'pm_shared/fpbody_pm.h'; s = rd(p); n = nl(s)
if 'FPM_KNOCK' not in s:
    a = '#define FPM_JOB_SHIFT\t\t19'
    i = s.index(a); j = s.index(n, i) + len(n)
    s = s[:j] + '#define FPM_KNOCK\t\t\t4194304\t// set by the server: knocked down by a big enemy (dlls/fpbody_react.inl; bit 22, the last that fits in fuser4\'s 24 signed bits)' + n + s[j:]
    a = '#define FPM_JOB_DUR_STORE'
    i = s.index(a); j = s.index(n, i) + len(n)
    s = s[:j] + '#define FPM_KNOCK_DUR\t\t3.5f\t// fm_knockdown: falling, a moment down, getting up' + n + s[j:]
    wr(p, s)
p = 'dlls/game.cpp'; s = rd(p); n = nl(s)
if 'sv_fpbody_knockdown' not in s:
    m = re.search(r'cvar_t sv_fpbody_buddy = [^\r\n]*\r?\n', s)
    s = s[:m.end()] + 'cvar_t sv_fpbody_knockdown = { "sv_fpbody_knockdown", "1", FCVAR_ARCHIVE };\t// fpbody: big enemies knock you down, small ones throw you back (fpbody_react.inl)' + n + s[m.end():]
    m = re.search(r'\n([ \t]*)CVAR_REGISTER\( &sv_fpbody_buddy \);[^\r\n]*', s)
    s = s[:m.end()] + n + m.group(1) + 'CVAR_REGISTER( &sv_fpbody_knockdown );' + s[m.end():]
    wr(p, s)
p = 'dlls/player.cpp'; s = rd(p); n = nl(s)
if 'fpbody_react.inl' not in s:
    inc = '#include "fpbody_jobs.inl"' if flavour == 'op4' else '#include "fpbody_moves.inl"'
    m = re.search(re.escape(inc) + r'[^\r\n]*\r?\n', s)
    pre = '#define FPR_TANK( pl ) ( (CBaseEntity *)( pl )->m_hTankControls != NULL )' + n if flavour == 'fi' else ''
    s = s[:m.end()] + pre + '#include "fpbody_react.inl"\t// fpbody: knocked down by big enemies, thrown back by small ones' + n + s[m.end():]
    a = 'FPMoves_Think();\t// fpbody: kick, redeploy after holster-all' + n
    assert s.count(a) == 1, 'FPMoves_Think'
    i = s.index(a); ind = s[s.rindex(n, 0, i) + len(n):i]
    s = s.replace(a, a + ind + 'FPReact_Think( this );\t// fpbody: knocked down / getting up' + n)
    if flavour == 'fi':
        hook = '\tint bitsDamage = damageInfo.type;' + n; dmg = 'damageInfo.damage'
    else:
        hook = '\tint bitsDamage = bitsDamageType;' + n; dmg = 'flDamage'
    m = re.search(r'\n[^\n]*CBasePlayer\s*::\s*TakeDamage\(', s)
    j = s.index(hook, m.end()) + len(hook)
    s = s[:j] + '\tFPReact_OnDamage( this, pevInflictor, pevAttacker, %s );\t// fpbody: knocked down / thrown back by who hit us' % dmg + n + s[j:]
    s = s[:m.start() + 1] + 'void FPReact_OnDamage( CBasePlayer *pl, entvars_t *pevInflictor, entvars_t *pevAttacker, float flDamage );\t// fpbody_react.inl' + n + \
        'void FPReact_Think( CBasePlayer *pl );' + n + n + s[m.start() + 1:]
    wr(p, s)
print('ok', root)
