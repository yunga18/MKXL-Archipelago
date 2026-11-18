"""Acceso a la memoria de MK10.exe (Mortal Kombat XL, Steam) usando solo ctypes.

Todas las direcciones son RVAs (relativas a la base del módulo) obtenidas del
MK10.pdb que viene con el juego (GUID d1feff98-49a5-164f-b4b0-0a5183ecf6a7, age 2).
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import struct
import sys
from typing import Optional

PROCESS_NAME = "MK10.exe"

# --- RVAs (MK10.exe Steam, build con PDB incluido) ---
RVA_GET_IS_CHARACTER_LOCKED = 0x484500       # FG_GAME_INFO::GetIsCharacterLocked (para verificar la versión)
SIGNATURE = bytes.fromhex("48895c2408574883ec20488bda8bf94885d2")
RVA_GCHARACTER_LIST = 0x33196A8              # TArray<MK10CharacterContentInfo> GCharacterList {data*, num, max}
RVA_FNAME_NAMES = 0x3800518                  # TArray<FNameEntry*> FName::Names {data*, num, max}
RVA_GFGGAMEINFO = 0x30DBA00                  # FG_GAME_INFO* GFGGameInfo

CHAR_ENTRY_SIZE = 0x38
CHAR_OFF_FNAME = 0x00
CHAR_OFF_UNLOCK_PAGE = 0x08
CHAR_OFF_UNLOCK_BIT = 0x0C
CHAR_OFF_FLAGS = 0x10                        # bit 0 = desbloqueado (MKContentInfo::IsUnlocked)
FNAMEENTRY_OFF_STR = 0x10

RVA_GMK10UNLOCKABLES = 0x331DCD0             # MK10Unlockables GMK10Unlockables
RVA_GPROGRESSIONDATA = 0x32166C0             # FGProgressionData GProgressionData (perfil cargado)
RVA_GISINKRYPTMODE = 0x37B7290               # int GIsInKryptMode
RVA_GEXPERIENCEMANAGER = 0x3311D00           # MK10ExperienceManager GExperienceManager
EXP_KOINS = 0x90 + 3 * 0x148                 # pad*0x548 + tipo 3 (Koins)*0x148 + ExperienceStats+0x8 (GetExperience)
EXP_PAD_STRIDE = 0x548
RVA_PROFILE_STATS = 0x3308C80                # StatsAccumulator[4] (ProfileStatManager), stride 0x100
STATS_CAT_EXPERIENCE = 3                     # categoría usada por ExperienceView::GetExperience
ENCODED_XOR = 0x01000193                     # CEncodedValue<int>: valor = enc ^ clave ^ esto (enc +0, clave +4)
STAT_OFF_VALUE = 0x28
UNLOCK_PAGES = 97                          # MK10Unlockables: 0x61 páginas de 32 bits
UNL_OFF_SESSION_BITS = 0x1EA8                # uint32[páginas] (IsItemUnLockedByGamepad, offline)
PROG_OFF_UNLOCK_BITS = 0xB713C               # uint32[páginas] en los datos de progreso guardados
UNL_OFF_NAME_MAPS = 0x58                     # TMap<FName,uint máscara> por página, stride 0x50, par de 20 bytes

GI_OFF_FLAGS = 0x08                         # QWORD de banderas de la pelea
GI_FLAG_BRUTALITY_STARTED = 1 << 26          # HasBrutalityStarted()
GI_FLAG_FATALITY_STARTED = 1 << 31           # HasFatalityStarted()
GI_FLAG_FATALITY_FINISHED = 1 << 33          # HasFatalityFinished()
GI_OFF_PLAYERS = 0x1968                      # PLAYER_INFO* [2]
GI_OFF_ROUND_WINNER = 0x1980                 # PLAYER_INFO*
GI_OFF_GAME_STATE = 0x1988                   # GAME_STATE
GI_OFF_GAME_MODE = 0x198C                    # GAME_MODES
GI_OFF_GAME_MODE_STR = 0x1990                # FString {wchar_t*, num, max}
PI_OFF_CHAR_NAME = 0x128                     # const char*
PI_OFF_CHAR_NAME_VALID = 0x130
PI_OFF_ACTIVE_OBJ = 0x20                     # FGCharacterObj* (PLAYER_INFO::GetActiveFGCharacterObj)
PI_OFF_ACTIVE_OBJ_ID = 0x28                  # debe coincidir con obj+0x8 (bit30 = inválido)
OBJ_OFF_ID = 0x08
OBJ_OFF_LIFE = 0xA38                         # float 0..1 (FGCharacterObj::GetLife); escribir 0 = KO inmediato
OBJ_OFF_MAX_LIFE = 0xA3C                     # float (tope en FGCharacterObj::SetLife)
# Bits de "desactivado" del luchador: 4 QWORD (uno por EMoveSetDisabledType). Ver FGCharacterObj::GetIs*Disabled.
OBJ_OFF_DISABLE = 0xF20
DISABLE_SLOT = 3                             # usamos el último tipo para no pisar lo que pone el juego
DISABLE_BLOCKING = 1 << 19                   # GetIsBlockingDisabled (probado en juego)
DISABLE_JUMPING = 1 << 8                     # GetIsJumpingDisabled (probado en juego)
DISABLE_SPECIALS = 1 << 4                    # SetSpecialMovesEnabled; además hay que apagar cada comando
OBJ_OFF_CMD_ARRAY = 0x9458                   # GenericCommand* [] (comandos del luchador)
OBJ_OFF_CMD_COUNT = 0x96B0
CMD_MAX = (OBJ_OFF_CMD_COUNT - OBJ_OFF_CMD_ARRAY) // 8
CMD_OFF_FLAGS = 0x20                         # bit1 = habilitado
CMD_OFF_KIND = 0x24                          # bit3 = movimiento especial
PI_OFF_AI_DRONE = 0x2D8                      # AIDrone* (PLAYER_INFO::GetAIDrone)
PI_OFF_AI_DRONE_ID = 0x2E0
DRONE_OFF_LEVEL = 0xD0                       # float, máx. 19.0 (AIDrone::SetDifficultyLevel)

GAME_STATES = ["GS_INIT", "GS_LOADING_FIGHT", "GS_ATTRACT", "GS_MAINMENU", "GS_ONLINE", "GS_KOTH",
               "GS_PROFILES", "GS_PSELECT", "GS_PLAY", "GS_GAME_OVER", "GS_MOVIE", "GS_FATALITY",
               "GS_LADDER", "GS_INVALID"]
GS_LOADING_FIGHT = 1
GS_PSELECT = 7
GS_PLAY = 8
GS_GAME_OVER = 9
GS_MOVIE = 10
GS_FATALITY = 11
GS_LADDER = 12

GAME_MODES = {-1: "MENU", 0: "ATTRACT", 1: "VERSUS", 2: "MODO2", 3: "HISTORIA", 4: "TORRE"}
GM_STORY = 3
GM_LADDER = 4

# Parches de código: (RVA, bytes originales, bytes nuevos)
# Hacen que las torres y la selección aleatoria ignoren los bloqueos, para que los rivales sigan
# siendo variados aunque tú tengas pocos personajes.
CODE_PATCHES = [
    # LadderCharacterList::PopulateWithAllUnlockedCharacters: call IsUnlocked -> mov eax, 1
    (0x270831, bytes.fromhex("e81ae42100"), bytes.fromhex("b801000000")),
    # FG_GAME_INFO::GetRandomCharacter: call IsUnlocked -> mov eax, 1
    (0x486A40, bytes.fromhex("e80b820000"), bytes.fromhex("b801000000")),
]
PAGE_EXECUTE_READWRITE = 0x40

PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400
TH32CS_SNAPPROCESS = 0x2
TH32CS_SNAPMODULE = 0x8
TH32CS_SNAPMODULE32 = 0x10


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("th32ModuleID", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("GlblcntUsage", wt.DWORD), ("ProccntUsage", wt.DWORD),
                ("modBaseAddr", ctypes.c_void_p), ("modBaseSize", wt.DWORD),
                ("hModule", wt.HMODULE), ("szModule", ctypes.c_wchar * 256),
                ("szExePath", ctypes.c_wchar * 260)]


class MemoryError_(Exception):
    pass


class GameMemory:
    def __init__(self):
        if sys.platform != "win32":
            raise MemoryError_("El cliente de MKXL solo funciona en Windows.")
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.k32.OpenProcess.restype = wt.HANDLE
        self.k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
        self.k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                               ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        self.k32.VirtualProtectEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wt.DWORD,
                                              ctypes.POINTER(wt.DWORD)]
        self.k32.WriteProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                                ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        self.handle = None
        self.pid = None
        self.base = None

    # ---------- conexión ----------
    def _find_pid(self) -> Optional[int]:
        snap = self.k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if not snap or snap == wt.HANDLE(-1).value:
            return None
        try:
            e = PROCESSENTRY32W()
            e.dwSize = ctypes.sizeof(e)
            ok = self.k32.Process32FirstW(snap, ctypes.byref(e))
            while ok:
                if e.szExeFile.lower() == PROCESS_NAME.lower():
                    return e.th32ProcessID
                ok = self.k32.Process32NextW(snap, ctypes.byref(e))
        finally:
            self.k32.CloseHandle(snap)
        return None

    def _find_base(self, pid: int) -> Optional[int]:
        snap = self.k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
        if not snap or snap == wt.HANDLE(-1).value:
            return None
        try:
            m = MODULEENTRY32W()
            m.dwSize = ctypes.sizeof(m)
            ok = self.k32.Module32FirstW(snap, ctypes.byref(m))
            while ok:
                if m.szModule.lower() == PROCESS_NAME.lower():
                    return m.modBaseAddr
                ok = self.k32.Module32NextW(snap, ctypes.byref(m))
        finally:
            self.k32.CloseHandle(snap)
        return None

    def attach(self) -> bool:
        """Devuelve True si quedó conectado. Lanza MemoryError_ si la versión no coincide."""
        if self.attached():
            return True
        pid = self._find_pid()
        if pid is None:
            return False
        base = self._find_base(pid)
        if base is None:
            return False
        h = self.k32.OpenProcess(PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION |
                                 PROCESS_QUERY_INFORMATION, False, pid)
        if not h:
            raise MemoryError_("No se pudo abrir MK10.exe. Prueba a abrir el cliente como administrador.")
        self.handle, self.pid, self.base = h, pid, base
        sig = self.read(base + RVA_GET_IS_CHARACTER_LOCKED, len(SIGNATURE))
        if sig != SIGNATURE:
            self.detach()
            raise MemoryError_("Esta versión de MK10.exe no es la que conoce el cliente (firma distinta).")
        return True

    def attached(self) -> bool:
        if not self.handle:
            return False
        code = wt.DWORD()
        if not self.k32.GetExitCodeProcess(self.handle, ctypes.byref(code)) or code.value != 259:
            self.detach()
            return False
        return True

    def detach(self):
        if self.handle:
            self.k32.CloseHandle(self.handle)
        self.handle = self.pid = self.base = None

    # ---------- lectura/escritura ----------
    def read(self, addr: int, size: int) -> bytes:
        buf = ctypes.create_string_buffer(size)
        n = ctypes.c_size_t()
        if not self.k32.ReadProcessMemory(self.handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(n)) \
                or n.value != size:
            raise MemoryError_(f"No se pudo leer {size} bytes en {addr:#x}")
        return buf.raw

    def write(self, addr: int, data: bytes):
        n = ctypes.c_size_t()
        if not self.k32.WriteProcessMemory(self.handle, ctypes.c_void_p(addr), data, len(data), ctypes.byref(n)) \
                or n.value != len(data):
            raise MemoryError_(f"No se pudo escribir en {addr:#x}")

    def write_code(self, addr: int, data: bytes):
        old = wt.DWORD()
        if not self.k32.VirtualProtectEx(self.handle, ctypes.c_void_p(addr), len(data), PAGE_EXECUTE_READWRITE,
                                         ctypes.byref(old)):
            raise MemoryError_(f"No se pudo desproteger {addr:#x}")
        try:
            self.write(addr, data)
        finally:
            tmp = wt.DWORD()
            self.k32.VirtualProtectEx(self.handle, ctypes.c_void_p(addr), len(data), old.value, ctypes.byref(tmp))
        self.k32.FlushInstructionCache(self.handle, ctypes.c_void_p(addr), len(data))

    def apply_patches(self, enable: bool) -> int:
        """Aplica (o quita) los parches de código. Devuelve cuántos quedaron en el estado pedido."""
        ok = 0
        for rva, orig, new in CODE_PATCHES:
            addr = self.base + rva
            cur = self.read(addr, len(orig))
            want = new if enable else orig
            if cur == want:
                ok += 1
            elif cur == (orig if enable else new):
                self.write_code(addr, want)
                ok += 1
        return ok

    def u32(self, a): return struct.unpack("<I", self.read(a, 4))[0]
    def i32(self, a): return struct.unpack("<i", self.read(a, 4))[0]
    def u64(self, a): return struct.unpack("<Q", self.read(a, 8))[0]

    def cstr(self, a, maxlen=128) -> str:
        raw = self.read(a, maxlen)
        return raw.split(b"\0", 1)[0].decode("latin-1")

    def wstr(self, a, n) -> str:
        if not a or n <= 0:
            return ""
        return self.read(a, n * 2).decode("utf-16-le", "replace").rstrip("\0")

    # ---------- estructuras del juego ----------
    def fname(self, index: int) -> str:
        names = self.u64(self.base + RVA_FNAME_NAMES)
        entry = self.u64(names + index * 8)
        if not entry:
            return f"<fname {index}>"
        return self.cstr(entry + FNAMEENTRY_OFF_STR)

    def character_list(self):
        """Lista de (dirección_entrada, nombre_interno, unlock_page, unlock_bit, flags)."""
        data = self.u64(self.base + RVA_GCHARACTER_LIST)
        num = self.i32(self.base + RVA_GCHARACTER_LIST + 8)
        if not data or num <= 0 or num > 512:
            return []
        raw = self.read(data, num * CHAR_ENTRY_SIZE)
        out = []
        for i in range(num):
            e = raw[i * CHAR_ENTRY_SIZE:(i + 1) * CHAR_ENTRY_SIZE]
            idx, = struct.unpack_from("<i", e, CHAR_OFF_FNAME)
            page, bit = struct.unpack_from("<iI", e, CHAR_OFF_UNLOCK_PAGE)
            flags, = struct.unpack_from("<Q", e, CHAR_OFF_FLAGS)
            out.append((data + i * CHAR_ENTRY_SIZE, self.fname(idx), page, bit, flags))
        return out

    def set_unlocked(self, entry_addr: int, unlocked: bool):
        a = entry_addr + CHAR_OFF_FLAGS
        flags = self.u32(a)
        new = (flags | 1) if unlocked else (flags & ~1)
        if new != flags:
            self.write(a, struct.pack("<I", new))

    def fighter(self, player: int = 0) -> int:
        """Dirección del FGCharacterObj activo del jugador (0 = P1), o 0 si no hay pelea."""
        gi = self.game_info()
        if not gi:
            return 0
        pi = self.u64(gi + GI_OFF_PLAYERS + 8 * player)
        if not pi:
            return 0
        obj = self.u64(pi + PI_OFF_ACTIVE_OBJ)
        oid = self.u32(pi + PI_OFF_ACTIVE_OBJ_ID)
        if not obj or oid == 0xFFFFFFFF:
            return 0
        cur = self.u32(obj + OBJ_OFF_ID)
        if cur & (1 << 30) or cur != oid:
            return 0
        return obj

    def life(self, player: int = 0) -> tuple[float, float] | None:
        """(vida, vida máxima) del jugador, o None si no hay luchador."""
        obj = self.fighter(player)
        if not obj:
            return None
        return struct.unpack("<ff", self.read(obj + OBJ_OFF_LIFE, 8))

    def set_life(self, value: float, player: int = 0) -> bool:
        obj = self.fighter(player)
        if not obj:
            return False
        self.write(obj + OBJ_OFF_LIFE, struct.pack("<f", value))
        return True

    def set_disabled(self, mask: int, on: bool, player: int = 0) -> bool:
        obj = self.fighter(player)
        if not obj:
            return False
        a = obj + OBJ_OFF_DISABLE + 8 * DISABLE_SLOT
        cur = self.u64(a)
        new = (cur | mask) if on else (cur & ~mask)
        if new != cur:
            self.write(a, struct.pack("<Q", new))
        return True

    def special_commands(self, player: int = 0) -> list[int]:
        """Direcciones de los comandos de movimientos especiales del luchador."""
        obj = self.fighter(player)
        if not obj:
            return []
        n = min(self.u32(obj + OBJ_OFF_CMD_COUNT), CMD_MAX)
        out = []
        for p in struct.unpack(f"<{n}Q", self.read(obj + OBJ_OFF_CMD_ARRAY, 8 * n)) if n else ():
            if p and self.u32(p + CMD_OFF_KIND) & 8:
                out.append(p)
        return out

    def set_command_enabled(self, cmd: int, on: bool):
        cur = self.u32(cmd + CMD_OFF_FLAGS)
        new = (cur | 2) if on else (cur & ~2)
        if new != cur:
            self.write(cmd + CMD_OFF_FLAGS, struct.pack("<I", new))

    def ai_drone(self, player: int = 1) -> int:
        """AIDrone del jugador si lo controla la CPU, si no 0."""
        gi = self.game_info()
        pi = self.u64(gi + GI_OFF_PLAYERS + 8 * player) if gi else 0
        if not pi:
            return 0
        d = self.u64(pi + PI_OFF_AI_DRONE)
        oid = self.u32(pi + PI_OFF_AI_DRONE_ID)
        if not d or oid == 0xFFFFFFFF or self.u32(d + OBJ_OFF_ID) != oid:
            return 0
        return d

    def unlock_words(self) -> list[int]:
        """Bits de desbloqueo por página (sesión | perfil guardado)."""
        n = UNLOCK_PAGES * 4
        a = struct.unpack(f"<{UNLOCK_PAGES}I", self.read(self.base + RVA_GMK10UNLOCKABLES + UNL_OFF_SESSION_BITS, n))
        b = struct.unpack(f"<{UNLOCK_PAGES}I", self.read(self.base + RVA_GPROGRESSIONDATA + PROG_OFF_UNLOCK_BITS, n))
        return [x | y for x, y in zip(a, b)]

    def unlock_name(self, page: int, mask: int) -> str:
        """Nombre interno de un desbloqueo (para registros), o '?'."""
        base = self.base + RVA_GMK10UNLOCKABLES + UNL_OFF_NAME_MAPS + page * 0x50
        data, num = self.u64(base), self.i32(base + 8)
        if not data or not 0 < num < 5000:
            return "?"
        raw = self.read(data, num * 20)
        for i in range(num):
            idx, _, val = struct.unpack_from("<iII", raw, i * 20)
            if val == mask:
                return self.fname(idx)
        return "?"

    def koins(self, pad: int = 0) -> int:
        """Saldo de Koins (probado: baja al comprar en la Krypta; un cofre de Koins lo sube de golpe)."""
        return self.i32(self.base + RVA_GEXPERIENCEMANAGER + pad * EXP_PAD_STRIDE + EXP_KOINS)

    def _koins_stat(self) -> int:
        """StatScalar<int> de los Koins en el perfil (lo que se guarda). 0 si el perfil no está cargado."""
        view = self.base + RVA_GEXPERIENCEMANAGER + 3 * 0x148 + 8
        stat_id = self.u32(view + 4)
        acc = self.base + RVA_PROFILE_STATS
        data, num = self.u64(acc + 8), self.i32(acc + 16)
        if not data or not 0 < num < 1000:
            return 0
        for i in range(num):
            e = data + i * 0x60
            if self.u32(e) != STATS_CAT_EXPERIENCE:
                continue
            idata, inum = self.u64(e + 8), self.i32(e + 16)
            if not idata or not 0 < inum < 100000:
                return 0
            raw = self.read(idata, inum * 24)
            for j in range(inum):
                key, = struct.unpack_from("<I", raw, j * 24)
                if key == stat_id:
                    return struct.unpack_from("<Q", raw, j * 24 + 8)[0]
        return 0

    def add_koins(self, amount: int) -> int | None:
        """Suma Koins al perfil (y a la copia que muestra el juego). Devuelve el nuevo saldo o None."""
        st = self._koins_stat()
        if not st:
            return None
        enc, key = struct.unpack("<II", self.read(st + STAT_OFF_VALUE, 8))
        old = enc ^ key ^ ENCODED_XOR
        if old >= 1 << 31:
            old -= 1 << 32
        new = max(0, min(old + amount, 2_000_000_000))
        self.write(st + STAT_OFF_VALUE, struct.pack("<I", (new ^ key ^ ENCODED_XOR) & 0xFFFFFFFF))
        for pad in range(4):
            a = self.base + RVA_GEXPERIENCEMANAGER + pad * EXP_PAD_STRIDE + EXP_KOINS
            if self.i32(a) == old:
                self.write(a, struct.pack("<i", new))
        return new

    def in_krypt(self) -> bool:
        return self.i32(self.base + RVA_GISINKRYPTMODE) != 0

    def game_info(self) -> int:
        return self.u64(self.base + RVA_GFGGAMEINFO)

    def game_state(self) -> dict:
        gi = self.game_info()
        if not gi:
            return {}
        state = self.i32(gi + GI_OFF_GAME_STATE)
        mode = self.i32(gi + GI_OFF_GAME_MODE)
        flags = self.u64(gi + GI_OFF_FLAGS)
        players = [self.u64(gi + GI_OFF_PLAYERS + 8 * i) for i in range(2)]
        winner = self.u64(gi + GI_OFF_ROUND_WINNER)
        names = []
        for p in players:
            n = ""
            if p and self.i32(p + PI_OFF_CHAR_NAME_VALID):
                ptr = self.u64(p + PI_OFF_CHAR_NAME)
                if ptr:
                    n = self.cstr(ptr)
            names.append(n)
        winner_idx = players.index(winner) if winner and winner in players else -1
        return {
            "state": state,
            "state_name": GAME_STATES[state] if 0 <= state < len(GAME_STATES) else str(state),
            "mode": mode,
            "mode_name": GAME_MODES.get(mode, str(mode)),
            "fatality": bool(flags & GI_FLAG_FATALITY_STARTED),
            "brutality": bool(flags & GI_FLAG_BRUTALITY_STARTED),
            "p1": names[0], "p2": names[1],
            "winner": winner_idx,
        }
