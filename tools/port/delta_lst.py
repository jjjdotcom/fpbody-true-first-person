"""Widen fuser4 in a mod's delta.lst so the Freeman move state reaches the client.

  python3 delta_lst.py <game's delta.lst> <mod folder>/delta.lst

The stock clientdata_t entry sends fuser4 with 2 bits at 1/128 (useless for
the state bits in pm_shared/fpbody_pm.h); client prediction then loses every
prone / vault / slide the server confirms. This copies the game's own file
(valve/, bshift/ or gearbox/ - it isn't redistributed here) with that one
line changed to 18 bits of whole numbers (the state bits, the hit group and
what was just used; see pm_shared/fpbody_pm.h).
"""
import sys

OLD = 'DEFINE_DELTA( fuser4, DT_SIGNED | DT_FLOAT, 2, 128.0 )'
NEW = 'DEFINE_DELTA( fuser4, DT_SIGNED | DT_FLOAT, 18, 1.0 ) // fpbody: Freeman move state (pm_shared/fpbody_pm.h)'
OLD12 = 'DEFINE_DELTA( fuser4, DT_SIGNED | DT_FLOAT, 12, 1.0 ) // fpbody: Freeman move state (pm_shared/fpbody_pm.h)'


def main(src, dst):
    s = open(src, 'rb').read().decode('latin-1')
    s = s.replace(OLD12, NEW)       # an earlier fpbody delta.lst (state bits up to 512)
    if NEW not in s:
        assert s.count(OLD) == 1, 'unexpected delta.lst'
        s = s.replace(OLD, NEW)
    open(dst, 'wb').write(s.encode('latin-1'))


if __name__ == '__main__':
    main(*sys.argv[1:3])
