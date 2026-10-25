import struct
def read_cstr(d, o):
    e = d.index(b'\0', o); return d[o:e].decode('latin-1'), e + 1
def read_dir(path):
    d = open(path, 'rb').read()
    sig, ver, treesize = struct.unpack_from('<III', d, 0)
    assert sig == 0x55aa1234, hex(sig)
    hdr = 12 if ver == 1 else 28
    o = hdr; files = {}
    while True:
        ext, o = read_cstr(d, o)
        if not ext: break
        while True:
            p, o = read_cstr(d, o)
            if not p: break
            while True:
                n, o = read_cstr(d, o)
                if not n: break
                crc, preload, arch, off, length, term = struct.unpack_from('<IHHIIH', d, o); o += 18
                pre = d[o:o + preload]; o += preload
                full = (p.strip() + '/' if p.strip() else '') + n + '.' + ext
                files[full.lower()] = (arch, off, length, pre)
    return files, d, hdr + treesize
