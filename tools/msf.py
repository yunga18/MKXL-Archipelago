"""Lector mínimo de PDB (MSF 7.00) que soporta directorios grandes."""
import struct, sys, mmap


class MSF:
    def __init__(self, path):
        self.f = open(path, 'rb')
        self.m = mmap.mmap(self.f.fileno(), 0, access=mmap.ACCESS_READ)
        hdr = self.m[32:56]
        self.bs, self.fpm, self.nb, self.dirsz, _ = struct.unpack('<5I', hdr[:20])
        ndirblocks = (self.dirsz + self.bs - 1) // self.bs
        nmap = (ndirblocks * 4 + self.bs - 1) // self.bs
        mapblocks = struct.unpack(f'<{nmap}I', self.m[52:52 + 4 * nmap])
        maps = b''.join(self.block(b) for b in mapblocks)
        dirblocks = struct.unpack(f'<{ndirblocks}I', maps[:4 * ndirblocks])
        d = b''.join(self.block(b) for b in dirblocks)[:self.dirsz]
        n = struct.unpack('<I', d[:4])[0]
        sizes = struct.unpack(f'<{n}I', d[4:4 + 4 * n])
        off = 4 + 4 * n
        self.streams = []
        for s in sizes:
            if s == 0xFFFFFFFF:
                s = 0
            nb = (s + self.bs - 1) // self.bs
            blks = struct.unpack(f'<{nb}I', d[off:off + 4 * nb])
            off += 4 * nb
            self.streams.append((s, blks))

    def block(self, b):
        return self.m[b * self.bs:(b + 1) * self.bs]

    def stream(self, i):
        s, blks = self.streams[i]
        return b''.join(self.block(b) for b in blks)[:s]


def publics(msf):
    dbi = msf.stream(3)
    sym_idx = struct.unpack('<H', dbi[20:22])[0]
    data = msf.stream(sym_idx)
    out = []
    off = 0
    while off + 4 <= len(data):
        reclen, kind = struct.unpack('<HH', data[off:off + 4])
        if kind == 0x110E:  # S_PUB32
            flags, offset, seg = struct.unpack('<IIH', data[off + 4:off + 14])
            name = data[off + 14:data.index(b'\0', off + 14)].decode('utf-8', 'replace')
            out.append((seg, offset, flags, name))
        off += reclen + 2
    return out


if __name__ == '__main__':
    m = MSF(sys.argv[1])
    info = m.stream(1)
    ver, sig, age = struct.unpack('<III', info[:12])
    print('version', ver, 'age', age, 'guid', info[12:28].hex())
    pubs = publics(m)
    print('publics', len(pubs))
    with open(sys.argv[2], 'w') as f:
        for seg, off, fl, name in pubs:
            f.write(f'{seg}\t{off:08x}\t{fl}\t{name}\n')
