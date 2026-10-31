"""Renames the HD pack p_ models' right-arm bones to the player model's names.

  python3 hd_arm_bones.py <in.mdl> <out.mdl>

The HD pack's player weapon models call the arm "Bip01 R Clavicle / UpperArm /
Forearm"; the player models (and Half-Life's own p_ models) call it "Bip01 R Arm /
Arm1 / Arm2". The engine attaches a p_ model by matching bone names, so a mesh
on one of those bones (the HD Gluon gun, on the forearm) did not follow the arm.
Same rig and rest pose, so a rename is all it needs; the file length is unchanged.
"""
import struct
import sys

REN = {b'Bip01 R Clavicle': b'Bip01 R Arm', b'Bip01 R UpperArm': b'Bip01 R Arm1', b'Bip01 R Forearm': b'Bip01 R Arm2'}


def main(src, dst):
    b = bytearray(open(src, 'rb').read())
    numbones, boneindex = struct.unpack_from('<ii', b, 0x8c)
    n = 0
    for i in range(numbones):
        o = boneindex + i * 112
        name = bytes(b[o:o + 32]).split(b'\0')[0]
        if name in REN:
            b[o:o + 32] = REN[name].ljust(32, b'\0')
            n += 1
    open(dst, 'wb').write(b)
    return n


if __name__ == '__main__':
    print(main(sys.argv[1], sys.argv[2]), 'bones renamed')
