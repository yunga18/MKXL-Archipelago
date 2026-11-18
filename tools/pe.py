"""Utilidades de ingeniería inversa para MK10.exe: símbolos del PDB, referencias y desensamblado anotado.

Uso:
    python tools/msf.py "<ruta>/MK10.pdb" tools/publics.tsv      # una vez, genera la tabla de símbolos
    python tools/pe.py buscar "GetIsCharacterLocked"             # busca símbolos por regex
    python tools/pe.py dis 0x140484500                           # desensambla una función (necesita llvm-objdump)
    python tools/pe.py refs 0x14048ec50                          # quién llama a esa dirección

Variables de entorno:
    MKX_EXE   ruta a MK10.exe (por defecto la de Steam en D:)
"""
import bisect
import os
import re
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = os.environ.get("MKX_EXE", r"D:\SteamLibrary\steamapps\common\MK10\Binaries\Retail\MK10.exe")
PUBLICS = os.path.join(HERE, "publics.tsv")
BASE = 0x140000000
SECTS = {1: 0x1000, 2: 0x25B7000, 3: 0x3095000}  # RVA de .text, .rdata, .data (índices de sección del PDB)

_data = open(EXE, "rb").read()
_pe = struct.unpack("<I", _data[0x3C:0x40])[0]
_nsec = struct.unpack("<H", _data[_pe + 6:_pe + 8])[0]
_optsz = struct.unpack("<H", _data[_pe + 20:_pe + 22])[0]
SECTIONS = []
for i in range(_nsec):
    s = _data[_pe + 24 + _optsz + 40 * i:_pe + 24 + _optsz + 40 * (i + 1)]
    vsize, va, rawsz, rawptr = struct.unpack("<IIII", s[8:24])
    SECTIONS.append((s[:8].rstrip(b"\0").decode(), va, vsize, rawptr, rawsz))


def va2off(va):
    rva = va - BASE
    for _, sva, _, rp, rs in SECTIONS:
        if sva <= rva < sva + rs:
            return rp + rva - sva
    return None


def read(va, n):
    o = va2off(va)
    return _data[o:o + n]


SYMS = {}
if os.path.exists(PUBLICS):
    for line in open(PUBLICS, encoding="utf-8"):
        seg, off, _, name = line.rstrip("\n").split("\t", 3)
        if int(seg) in SECTS:
            SYMS[BASE + SECTS[int(seg)] + int(off, 16)] = name
ADDRS = sorted(SYMS)
BYNAME = {}
for a, n in SYMS.items():
    BYNAME.setdefault(n, a)


def sym(va):
    i = bisect.bisect_right(ADDRS, va) - 1
    if i < 0:
        return hex(va)
    d = va - ADDRS[i]
    return SYMS[ADDRS[i]] + (f"+{d:#x}" if d else "")


def find(pattern):
    r = re.compile(pattern)
    return sorted((a, n) for a, n in SYMS.items() if r.search(n))


def _text():
    for name, sva, vs, rp, rs in SECTIONS:
        if name == ".text":
            return BASE + sva, _data[rp:rp + min(vs, rs)]


def call_xrefs(target):
    start, t = _text()
    out = []
    for op in (b"\xe8", b"\xe9"):
        i = t.find(op)
        while i != -1:
            if i + 5 <= len(t) and start + i + 5 + struct.unpack("<i", t[i + 1:i + 5])[0] == target:
                out.append(start + i)
            i = t.find(op, i + 1)
    return out


def disasm(start, end):
    tool = shutil.which("llvm-objdump") or shutil.which("objdump")
    if not tool:
        sys.exit("Necesitas llvm-objdump (instala LLVM) para desensamblar.")
    r = subprocess.run([tool, "-d", "--no-show-raw-insn", f"--start-address={start:#x}",
                        f"--stop-address={end:#x}", EXE], capture_output=True, text=True)
    out = []
    for l in r.stdout.splitlines()[6:]:
        l = re.sub(r"\s*<[^>]*>", "", l)
        for h in re.findall(r"0x(1[0-9a-f]{8})", l):
            l += "  ; " + sym(int(h, 16))[:100]
        out.append(l)
    return "\n".join(out)


def dfunc(va, maxlen=0x400):
    i = bisect.bisect_right(ADDRS, va)
    end = min(ADDRS[i] if i < len(ADDRS) else va + maxlen, va + maxlen)
    return disasm(va, end)


if __name__ == "__main__":
    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd == "buscar":
        for a, n in find(arg)[:200]:
            print(hex(a), n)
    elif cmd == "dis":
        print(dfunc(int(arg, 16)))
    elif cmd == "refs":
        for x in call_xrefs(int(arg, 16)):
            print(hex(x), sym(x))
