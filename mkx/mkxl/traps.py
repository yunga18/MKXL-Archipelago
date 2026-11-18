"""Trampas reales: se aplican a P1 (o a la IA rival) durante la siguiente pelea.

Una trampa por pelea, en el orden en que llegaron. Las trampas ya aplicadas se guardan en un
archivo por partida (seed + slot), así no se repiten al reconectar ni se pierden si llegaron
con el cliente cerrado.
"""
from __future__ import annotations

import json
import os
import struct

from .memory import DISABLE_BLOCKING, DISABLE_JUMPING, DISABLE_SPECIALS, DRONE_OFF_LEVEL, GM_LADDER, GM_STORY, \
    GS_GAME_OVER, GS_LOADING_FIGHT, GS_PLAY, GameMemory

GS_INIT = 0

TRAP_NO_BLOCK = "Trampa: Próxima pelea sin bloquear"
TRAP_NO_SPECIALS = "Trampa: Próxima pelea sin movimientos especiales"
TRAP_NO_JUMP = "Trampa: Próxima pelea sin saltar"
TRAP_VERY_HARD = "Trampa: Próxima pelea en dificultad Muy Difícil"
ALL_TRAPS = (TRAP_NO_BLOCK, TRAP_NO_SPECIALS, TRAP_NO_JUMP, TRAP_VERY_HARD)

DISABLE_MASK = {TRAP_NO_BLOCK: DISABLE_BLOCKING, TRAP_NO_JUMP: DISABLE_JUMPING, TRAP_NO_SPECIALS: DISABLE_SPECIALS}
VERY_HARD_LEVEL = 3.0           # nivel de AIDrone en Versus "Muy Difícil" (medido en juego)
FIGHT_MODES = (1, GM_STORY, GM_LADDER)   # versus, historia, torre

SHORT = {TRAP_NO_BLOCK: "sin bloquear", TRAP_NO_SPECIALS: "sin especiales", TRAP_NO_JUMP: "sin saltar",
         TRAP_VERY_HARD: "rival en Muy Difícil"}


class TrapManager:
    def __init__(self, mem: GameMemory, debug, notify):
        self.mem = mem
        self.debug = debug
        self.notify = notify
        self.path: str | None = None
        self.applied = 0                 # cuántas trampas (de las recibidas) ya se aplicaron
        self.received: list[str] = []    # trampas recibidas, en orden
        self.test_queue: list[str] = []  # trampas de prueba (/mk_trampa), no cuentan como aplicadas
        self.active: str | None = None   # trampa de la pelea en curso
        self.disabled_cmds: list[int] = []
        self.drone_orig: tuple[int, float] | None = None
        self.obj = 0                     # luchador P1 al que se aplicó

    # ---------- persistencia ----------
    def load(self, path: str):
        self.path = path
        try:
            with open(path, encoding="utf-8") as f:
                self.applied = int(json.load(f).get("applied", 0))
        except (OSError, ValueError):
            self.applied = 0

    def save(self):
        if not self.path:
            return
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"applied": self.applied}, f)
        except OSError:
            pass

    def set_received(self, names: list[str]):
        self.received = [n for n in names if n in ALL_TRAPS]

    def pending(self) -> list[str]:
        return self.test_queue + self.received[self.applied:]

    # ---------- bucle ----------
    def tick(self, st: dict, prev: dict):
        mode, state = st["mode"], st["state"]
        in_fight = mode in FIGHT_MODES
        if self.active and (state in (GS_GAME_OVER, GS_INIT, GS_LOADING_FIGHT) or not in_fight):
            self.finish()
        if not in_fight or state != GS_PLAY:
            return
        if not self.active:
            pend = self.pending()
            if not pend:
                return
            trap = pend[0]
            if trap == TRAP_VERY_HARD and not self.mem.ai_drone(1):
                return                    # rival humano: se guarda para una pelea contra la CPU
            self.obj = self.mem.fighter(0)
            if not self.obj:
                return
            self.active = trap
            if self.test_queue:
                self.test_queue.pop(0)
            else:
                self.applied += 1
                self.save()
            self.notify(f"¡Trampa! Esta pelea: {SHORT[trap]}", "trap")
            self.debug(f"trampa aplicada: {trap}")
        self.enforce()

    def enforce(self):
        """Se repite en cada vuelta: así sobrevive a los cambios de ronda."""
        trap = self.active
        if trap in DISABLE_MASK:
            self.mem.set_disabled(DISABLE_MASK[trap], True)
        if trap == TRAP_NO_SPECIALS:
            for c in self.mem.special_commands(0):
                self.mem.set_command_enabled(c, False)
                if c not in self.disabled_cmds:
                    self.disabled_cmds.append(c)
        if trap == TRAP_VERY_HARD:
            d = self.mem.ai_drone(1)
            if d:
                lvl, = struct.unpack("<f", self.mem.read(d + DRONE_OFF_LEVEL, 4))
                if self.drone_orig is None or self.drone_orig[0] != d:
                    self.drone_orig = (d, lvl)
                if lvl < VERY_HARD_LEVEL:   # solo sube: nunca facilita a un rival que ya es más duro
                    self.mem.write(d + DRONE_OFF_LEVEL, struct.pack("<f", VERY_HARD_LEVEL))

    def finish(self):
        """Deshace la trampa, solo si el luchador al que se aplicó sigue existiendo."""
        trap = self.active
        try:
            alive = self.obj and self.mem.fighter(0) == self.obj
        except Exception:  # noqa: BLE001
            alive = False
        self.debug(f"trampa terminada: {trap} (restaurar={bool(alive)})")
        if alive:
            try:
                if trap in DISABLE_MASK:
                    self.mem.set_disabled(DISABLE_MASK[trap], False)
                valid = set(self.mem.special_commands(0))
                for c in self.disabled_cmds:
                    if c in valid:
                        self.mem.set_command_enabled(c, True)
                if self.drone_orig and self.mem.ai_drone(1) == self.drone_orig[0]:
                    self.mem.write(self.drone_orig[0] + DRONE_OFF_LEVEL, struct.pack("<f", self.drone_orig[1]))
            except Exception as e:  # noqa: BLE001 - la pelea puede estar descargándose
                self.debug(f"no se pudo restaurar la trampa: {e!r}")
        self.active = None
        self.disabled_cmds = []
        self.drone_orig = None
        self.obj = 0
