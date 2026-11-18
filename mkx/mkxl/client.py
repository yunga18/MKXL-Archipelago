"""Cliente automático de Archipelago para Mortal Kombat XL (PC, Steam).

- Bloquea en la selección de personajes a los que todavía no recibiste.
- Detecta Fatalities y los envía como checks.
- Registra lo que pasa en el juego en MKXL_debug.log (para seguir automatizando checks).
- /marcar permite enviar a mano los checks que aún no se detectan solos.
"""
from __future__ import annotations

import asyncio
import datetime
import difflib
import json
import logging
import os
import time

import Utils
from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, \
    handle_url_arg, logger, server_loop
from NetUtils import ClientStatus

from .memory import GM_LADDER, GM_STORY, GS_GAME_OVER, GS_LOADING_FIGHT, GS_MOVIE, GS_PLAY, GameMemory, \
    MemoryError_
from .names import INTERNAL_TO_AP, internal_to_ap
from .overlay import Overlay
from .traps import ALL_TRAPS, SHORT as TRAP_SHORT, TrapManager

GAME = "Mortal Kombat X"
VICTORY_LOCATION = "Restaurar el Amuleto y derrotar a Shinnok"
POLL_SECONDS = 0.2
FRAGMENT = "Fragmento del Amuleto de Shinnok"
FRAGMENTS_NEEDED = 8
CHARACTERS_NEEDED = 10
ALL_CHARACTERS = set(INTERNAL_TO_AP.values())
KRYPTA_CHECKS = 20
KRYPTA_LOCATIONS = [f"Krypta: compra {i}" for i in range(1, KRYPTA_CHECKS + 1)]
KRYPT_GRACE_SECONDS = 5.0   # el saldo puede actualizarse justo después de salir de la Krypta
KOINS_ITEM = "1000 Koins"
KOINS_PER_ITEM = 1000
KRYPT_PURCHASE_GAP = 1.0    # cambios de Koins más juntos que esto cuentan como una sola compra
STORY_CHAPTERS = {name: i for i, name in enumerate(
    ["Johnny Cage", "Kotal Kahn", "Sub-Zero", "Kung Jin", "Sonya Blade", "D'Vorah", "Takeda", "Jax",
     "Scorpion", "Raiden", "Jacqui Briggs", "Cassie Cage"], start=1)}


def _debug_path() -> str:
    return Utils.user_path("MKXL_debug.log")


class MKXLCommandProcessor(ClientCommandProcessor):
    ctx: "MKXLContext"

    def _cmd_mk_estado(self) -> bool:
        """Muestra si el cliente está enganchado al juego y qué personajes tienes."""
        ctx = self.ctx
        logger.info(f"Juego: {'conectado' if ctx.mem.attached() else 'no encontrado'}")
        got = sorted(ctx.received_characters())
        logger.info(f"Personajes recibidos ({len(got)}): {', '.join(got) if got else 'ninguno'}")
        if ctx.mem.attached():
            try:
                logger.info(f"Estado: {ctx.mem.game_state()}")
            except MemoryError_ as e:
                logger.info(f"No se pudo leer el estado: {e}")
        return True

    def _cmd_mk_volcado(self) -> bool:
        """Guarda un volcado de diagnóstico en MKXL_volcado.txt (para desarrollo)."""
        ctx = self.ctx
        if not ctx.mem.attached():
            logger.info("Abre Mortal Kombat XL primero.")
            return False
        path = Utils.user_path("MKXL_volcado.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now().isoformat()}\nbase={ctx.mem.base:#x}\n")
            f.write(f"estado={ctx.mem.game_state()}\n\n")
            for addr, name, page, bit, flags in ctx.mem.character_list():
                f.write(f"{addr:#x}\t{name}\tpage={page}\tbit={bit}\tflags={flags:#x}\tap={internal_to_ap(name)}\n")
        logger.info(f"Volcado guardado en {path}")
        return True

    def _cmd_mk_avisos(self) -> bool:
        """Activa/desactiva los avisos en pantalla encima del juego."""
        ov = self.ctx.overlay
        ov.enabled = not ov.enabled
        logger.info(f"Avisos en pantalla: {'activados' if ov.enabled else 'desactivados'}")
        if ov.enabled:
            ov.show("Avisos activados", "info")
        return True

    def _cmd_mk_morir(self) -> bool:
        """Prueba local: hace perder la pelea actual como un DeathLink (no envía nada a los demás)."""
        self.ctx.deathlink_pending = True
        self.ctx.deathlink_from_test = True
        logger.info("Muerte de prueba preparada: se aplicará en la pelea actual o la siguiente.")
        return True

    def _cmd_mk_trampas(self) -> bool:
        """Muestra las trampas que esperan a la próxima pelea."""
        pend = self.ctx.traps.pending()
        logger.info("Trampas pendientes: " + (", ".join(TRAP_SHORT[t] for t in pend) if pend else "ninguna"))
        return True

    def _cmd_mk_trampa(self, tipo: str = "") -> bool:
        """Prueba local de una trampa en la próxima pelea: bloqueo, salto, especiales o dificil."""
        keys = {"bloqueo": 0, "especiales": 1, "salto": 2, "dificil": 3}
        if tipo.lower() not in keys:
            logger.info("Uso: /mk_trampa bloqueo|salto|especiales|dificil")
            return False
        trap = ALL_TRAPS[keys[tipo.lower()]]
        self.ctx.traps.test_queue.append(trap)
        logger.info(f"Trampa de prueba preparada: {TRAP_SHORT[trap]}")
        return True

    def _cmd_pendientes(self) -> bool:
        """Lista los checks que te faltan."""
        names = sorted(self.ctx.location_names.lookup_in_game(l) for l in self.ctx.missing_locations)
        logger.info(f"Faltan {len(names)}:\n" + "\n".join(names))
        return True

    def _cmd_marcar(self, *texto: str) -> bool:
        """Envía a mano un check. Ej.: /marcar torre scorpion"""
        ctx = self.ctx
        query = " ".join(texto).strip().lower()
        if not query:
            logger.info("Uso: /marcar <parte del nombre del check>")
            return False
        candidates = {ctx.location_names.lookup_in_game(l): l for l in ctx.missing_locations}
        if VICTORY_LOCATION not in candidates and not ctx.finished_game:
            candidates[VICTORY_LOCATION] = None
        words = query.split()
        matches = [n for n in candidates if all(w in n.lower() for w in words)]
        if not matches:
            matches = difflib.get_close_matches(query, list(candidates), n=5, cutoff=0.4)
        if len(matches) != 1:
            logger.info("Sé más específico. Coincidencias: " + (", ".join(matches) if matches else "ninguna"))
            return False
        asyncio.create_task(ctx.send_location_by_name(matches[0]))
        return True


class MKXLContext(CommonContext):
    game = GAME
    items_handling = 0b111
    command_processor = MKXLCommandProcessor

    def __init__(self, server_address, password):
        super().__init__(server_address, password)
        self.mem = GameMemory()
        self.original_flags: dict[int, int] = {}
        self.last_snapshot = None
        self.prev = None
        self.fight_sent: set[str] = set()
        self.story_char = None
        self.story_wins: set[str] = set()
        self.last_story_fight = None
        self.story_done_session: set[str] = set()
        self.patched = False
        self.attach_error_shown = False
        self.unknown_logged: set[str] = set()
        self.location_ids: dict[str, int] = {}
        self.overlay = Overlay()
        self.deathlink_pending = False      # llegó una muerte y falta aplicarla
        self.deathlink_from_test = False
        self.deathlink_active = False       # estamos matando a P1 en esta pelea (no reenviar la muerte)
        self.traps = TrapManager(self.mem, self.debug, self.overlay.show)
        self.unlock_prev: list[int] | None = None
        self.koins_prev: int | None = None
        self.koins_applied = 0              # cuántos "1000 Koins" ya se sumaron al juego en esta partida
        self.koins_path: str | None = None
        self.room_seed: str | None = None   # seed_name del paquete RoomInfo
        self.last_purchase = 0.0
        self.krypt_until = 0.0
        self.krypt_sent: set[str] = set()

    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def state_path(self, folder: str) -> str:
        """Archivo de estado por partida (seed + slot). Hasta 0.8.1 el seed llegaba vacío ('None_<slot>.json'):
        si existe ese archivo viejo y no el nuevo, se adopta para la partida actual."""
        seed = self.room_seed or getattr(self, "server_seed_name", None) or self.seed_name or "sin_seed"
        path = Utils.user_path(folder, f"{seed}_{self.slot}.json")
        legacy = Utils.user_path(folder, f"None_{self.slot}.json")
        if seed != "None" and not os.path.exists(path) and os.path.exists(legacy):
            try:
                os.replace(legacy, path)
                self.debug(f"estado migrado: {legacy} -> {path}")
            except OSError:
                pass
        return path

    def on_package(self, cmd: str, args: dict):
        if cmd == "RoomInfo":
            self.room_seed = args.get("seed_name")
        elif cmd == "Connected":
            from worlds.AutoWorld import AutoWorldRegister
            world = AutoWorldRegister.world_types.get(GAME)
            if world:
                self.location_ids = dict(world.location_name_to_id)
            self.traps.load(self.state_path("MKXL_trampas"))
            self.koins_path = self.state_path("MKXL_koins")
            try:
                with open(self.koins_path, encoding="utf-8") as f:
                    self.koins_applied = int(json.load(f).get("applied", 0))
            except (OSError, ValueError):
                self.koins_applied = 0
            if args.get("slot_data", {}).get("death_link"):
                asyncio.create_task(self.update_death_link(True))
                logger.info("DeathLink activado: si pierdes una pelea de Torre o Historia, mueren todos.")
            logger.info("Conectado. Abre Mortal Kombat XL (o déjalo abierto) y el cliente se enganchará solo.")
            self.overlay.show("Conectado a Archipelago", "info")
        elif cmd == "ReceivedItems" and args.get("index", 0) > 0:
            for it in args.get("items", []):
                name = self.item_names.lookup_in_game(it.item, GAME)
                kind = "trap" if it.flags & 0b100 else "item"
                if it.player == self.slot:
                    self.overlay.show(f"Encontraste: {name}", kind)
                else:
                    self.overlay.show(f"Recibiste {name} de {self.player_names.get(it.player, '?')}", kind)

    def on_deathlink(self, data: dict):
        super().on_deathlink(data)
        self.deathlink_pending = True
        self.deathlink_from_test = False
        who = data.get("source", "alguien")
        cause = data.get("cause") or ""
        logger.info(f"DeathLink de {who}. {cause}".strip())
        self.overlay.show(f"DeathLink: {who} murió. ¡Te toca!", "death")

    def make_gui(self):
        ui = super().make_gui()
        ui.base_title = "Archipelago - Mortal Kombat XL"
        return ui

    # ---------- utilidades ----------
    def received_characters(self) -> set[str]:
        out = set()
        for it in self.items_received:
            out.add(self.item_names.lookup_in_game(it.item, GAME))
        return out

    async def send_location_by_name(self, name: str):
        if name == VICTORY_LOCATION:
            if name in self.location_ids:
                await self.check_locations([self.location_ids[name]])
            await self.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
            self.finished_game = True
            logger.info("¡Meta completada! Shinnok ha caído.")
            return
        loc_id = self.location_ids.get(name)
        if loc_id is None:
            logger.info(f"No existe el check '{name}'.")
            return
        if loc_id in self.missing_locations:
            await self.check_locations([loc_id])
            logger.info(f"Check enviado: {name}")
            self.overlay.show(f"Check: {name}", "check")

    def debug(self, msg: str):
        try:
            with open(_debug_path(), "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
        except OSError:
            pass

    # ---------- bloqueo de personajes ----------
    def enforce_locks(self):
        if self.slot is None:
            return
        allowed = self.received_characters()
        for addr, name, page, bit, flags in self.mem.character_list():
            ap = internal_to_ap(name)
            if ap is None:
                if name not in self.unknown_logged:
                    self.unknown_logged.add(name)
                    self.debug(f"personaje sin traducir: {name} page={page} bit={bit} flags={flags:#x}")
                continue
            if addr not in self.original_flags:
                self.original_flags[addr] = flags
            self.mem.set_unlocked(addr, ap in allowed)

    def restore_locks(self):
        if not self.original_flags or not self.mem.attached():
            return
        import struct
        for addr, flags in self.original_flags.items():
            try:
                self.mem.write(addr + 0x10, struct.pack("<I", flags & 0xFFFFFFFF))
            except MemoryError_:
                pass
        self.original_flags.clear()

    # ---------- detección de checks ----------
    def counts(self) -> tuple[int, int]:
        got = [self.item_names.lookup_in_game(it.item, GAME) for it in self.items_received]
        frags = sum(1 for n in got if n == FRAGMENT)
        chars = len({n for n in got if n in ALL_CHARACTERS})
        return frags, chars

    async def check_if_received(self, kind: str, ap: str | None):
        if not ap:
            return
        if ap not in self.received_characters():
            logger.info(f"{kind} con {ap}, pero aún no tienes a {ap}: no cuenta.")
            return
        await self.send_location_by_name(f"{kind} - {ap}")

    async def story_chapter_done(self, ap: str | None):
        if not ap or ap in self.story_done_session:
            return
        self.story_done_session.add(ap)
        chapter = STORY_CHAPTERS.get(ap)
        if chapter:
            await self.send_location_by_name(f"Historia Capítulo {chapter} - {ap}")

    async def handle_deathlink(self, st: dict, prev: dict):
        mode, state = st["mode"], st["state"]
        in_fight_mode = mode in (1, GM_STORY, GM_LADDER)
        # enviar: perder una pelea de Torre o Historia (no por un DeathLink recibido)
        if state == GS_GAME_OVER and prev["state"] != GS_GAME_OVER and st["winner"] == 1:
            if self.deathlink_active:
                self.debug("pelea perdida por DeathLink recibido: no se reenvía")
            elif mode in (GM_STORY, GM_LADDER) and "DeathLink" in self.tags:
                p1 = internal_to_ap(st["p1"]) or st["p1"]
                await self.send_death(f"{self.player_names.get(self.slot, 'Alguien')} cayó peleando con {p1}.")
                self.debug("DeathLink enviado")
                self.overlay.show("Perdiste: DeathLink enviado", "death")
        if self.deathlink_active and (state == GS_GAME_OVER or not in_fight_mode):
            self.deathlink_active = False
        # recibir: empezar a matar a P1 en cuanto haya pelea
        if self.deathlink_pending and state == GS_PLAY and in_fight_mode:
            self.deathlink_pending = False
            self.deathlink_active = True
            self.debug(f"aplicando DeathLink (prueba={self.deathlink_from_test})")
        if self.deathlink_active and state == GS_PLAY:
            life = self.mem.life(0)
            if life and life[0] > 0:
                self.mem.set_life(0.0)
                self.debug(f"vida P1 {life[0]:.0%} -> 0")

    async def detect_krypt(self):
        """Cada compra en la Krypta (cualquier cambio de Koins estando dentro) envía el siguiente 'Krypta: compra N'."""
        now = time.monotonic()
        if self.mem.in_krypt():
            self.krypt_until = now + KRYPT_GRACE_SECONDS
        in_krypt = now <= self.krypt_until
        koins = self.mem.koins()
        prev_koins, self.koins_prev = self.koins_prev, koins
        if prev_koins is not None and koins != prev_koins:
            self.debug(f"Koins {prev_koins} -> {koins} (krypta={in_krypt})")
            if in_krypt and now - self.last_purchase >= KRYPT_PURCHASE_GAP and self.slot is not None:
                self.last_purchase = now
                await self.send_next_krypt()
        # solo para el registro: qué objetos nuevos aparecen
        cur = self.mem.unlock_words()
        prev, self.unlock_prev = self.unlock_prev, cur
        if prev is not None:
            for page, (old, new) in enumerate(zip(prev, cur)):
                added = new & ~old
                for bit in range(32):
                    if added >> bit & 1:
                        self.debug(f"desbloqueo nuevo: {self.mem.unlock_name(page, 1 << bit)} (página {page})")

    def apply_koins(self):
        """Suma al juego los '1000 Koins' recibidos que aún no se aplicaron (también los que llegaron offline)."""
        if self.slot is None or not self.koins_path:
            return
        got = sum(1 for it in self.items_received if self.item_names.lookup_in_game(it.item, GAME) == KOINS_ITEM)
        pending = got - self.koins_applied
        if pending <= 0:
            return
        new = self.mem.add_koins(pending * KOINS_PER_ITEM)
        if new is None:
            return                          # perfil aún no cargado: se reintenta luego
        self.koins_applied = got
        if self.koins_prev is not None:
            self.koins_prev = self.mem.koins()   # que no cuente como compra en la Krypta
        try:
            os.makedirs(os.path.dirname(self.koins_path), exist_ok=True)
            with open(self.koins_path, "w", encoding="utf-8") as f:
                json.dump({"applied": self.koins_applied}, f)
        except OSError:
            pass
        self.debug(f"+{pending * KOINS_PER_ITEM} Koins -> {new}")
        logger.info(f"Se sumaron {pending * KOINS_PER_ITEM} Koins. Saldo: {new}")
        self.overlay.show(f"+{pending * KOINS_PER_ITEM} Koins (saldo {new})", "item")

    async def send_next_krypt(self):
        for loc in KRYPTA_LOCATIONS:
            loc_id = self.location_ids.get(loc)
            if loc_id is not None and loc_id in self.missing_locations and loc not in self.krypt_sent:
                self.krypt_sent.add(loc)
                await self.send_location_by_name(loc)
                return

    async def detect(self):
        st = self.mem.game_state()
        if not st:
            return
        snap = (st["state_name"], st["mode_name"], st["p1"], st["p2"], st["winner"], st["fatality"], st["brutality"])
        if snap != self.last_snapshot:
            self.debug(f"{st}")
            self.last_snapshot = snap
        prev = self.prev or st
        self.prev = st
        p1 = internal_to_ap(st["p1"])
        mode, state = st["mode"], st["state"]

        if state == GS_LOADING_FIGHT and prev["state"] != GS_LOADING_FIGHT:
            self.fight_sent = set()

        await self.handle_deathlink(st, prev)
        if self.slot is not None:
            self.traps.set_received([self.item_names.lookup_in_game(it.item, GAME) for it in self.items_received])
        self.traps.tick(st, prev)

        # Fatality / Brutality: la bandera se enciende cuando empieza la animación (no en "Finish Him")
        if mode not in (0,) and st["winner"] == 0:
            if st["fatality"] and "fatality" not in self.fight_sent:
                self.fight_sent.add("fatality")
                if mode != GM_STORY:
                    await self.check_if_received("Fatality", p1)
            if st["brutality"] and "brutality" not in self.fight_sent:
                self.fight_sent.add("brutality")
                if mode != GM_STORY:
                    await self.check_if_received("Brutality", p1)

        # Torre Klásica: ganar al jefe final (shinnokboss)
        if mode == GM_LADDER and st["p2"].lower().startswith("shinnokboss") and st["winner"] == 0 \
                and state in (GS_MOVIE, GS_GAME_OVER) and "tower" not in self.fight_sent:
            self.fight_sent.add("tower")
            await self.check_if_received("Torre Klásica completada", p1)
            frags, chars = self.counts()
            if p1 in self.received_characters() and frags >= FRAGMENTS_NEEDED and chars >= CHARACTERS_NEEDED \
                    and not self.finished_game:
                await self.send_location_by_name(VICTORY_LOCATION)

        # Modo Historia
        if mode == GM_STORY and p1:
            # Solo GS_PLAY: al entrar a la historia, p1/p2 conservan unos instantes los
            # personajes de la demo del menú (p. ej. Cassie), lo que daba capítulos falsos.
            if state == GS_PLAY and self.story_char and p1 != self.story_char and prev["mode"] == GM_STORY:
                await self.story_chapter_done(self.story_char)   # pasó al siguiente capítulo
                self.story_wins = set()
            if state == GS_PLAY and p1 != self.story_char:
                self.story_char = p1
                self.story_wins = set()
            # una pelea se gana si el siguiente rival es distinto (si pierdes, repites contra el mismo)
            if state == GS_LOADING_FIGHT and prev["state"] != GS_LOADING_FIGHT and self.last_story_fight:
                last_p1, last_p2 = self.last_story_fight
                if last_p1 == st["p1"] and last_p2 != st["p2"]:
                    self.story_wins.add(last_p2)
            if state == GS_PLAY:
                self.last_story_fight = (st["p1"], st["p2"])
            # último capítulo (Cassie) termina venciendo a Shinnok
            if p1 == "Cassie Cage" and "shinnok" in st["p2"].lower() and st["winner"] == 0 \
                    and state in (GS_MOVIE, GS_GAME_OVER):
                await self.story_chapter_done(p1)
        elif prev["mode"] == GM_STORY and mode != GM_STORY:
            # saliste de la historia: si ganaste las 4 peleas del capítulo, cuenta
            if self.last_story_fight and self.last_story_fight[1] not in self.story_wins and prev["winner"] == 0:
                self.story_wins.add(self.last_story_fight[1])
            if self.story_char and len(self.story_wins) >= 4:
                await self.story_chapter_done(self.story_char)
            self.story_char, self.story_wins, self.last_story_fight = None, set(), None


async def game_loop(ctx: MKXLContext):
    while not ctx.exit_event.is_set():
        try:
            was = ctx.mem.attached()
            if ctx.mem.attach():
                if not was:
                    logger.info("Enganchado a Mortal Kombat XL.")
                    ctx.original_flags.clear()
                    ctx.prev = None
                    ctx.patched = False
                    ctx.unlock_prev = None
                    ctx.koins_prev = None
                ctx.attach_error_shown = False
                if ctx.slot is not None and not ctx.patched:
                    n = ctx.mem.apply_patches(True)
                    ctx.patched = True
                    ctx.debug(f"parches aplicados: {n}")
                ctx.enforce_locks()
                await ctx.detect()
                ctx.apply_koins()
                await ctx.detect_krypt()
        except MemoryError_ as e:
            if not ctx.attach_error_shown:
                logger.error(str(e))
                ctx.attach_error_shown = True
        except Exception as e:  # el juego puede estar cargando; no tumbar el cliente
            ctx.debug(f"error: {e!r}")
        await asyncio.sleep(POLL_SECONDS)


async def main(args):
    ctx = MKXLContext(args.connect, args.password)
    ctx.auth = args.name
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
    if gui_enabled:
        ctx.run_gui()
    ctx.run_cli()
    loop_task = asyncio.create_task(game_loop(ctx), name="MKXL game loop")
    await ctx.exit_event.wait()
    ctx.overlay.stop()
    if ctx.traps.active and ctx.mem.attached():
        ctx.traps.finish()
    ctx.restore_locks()
    try:
        if ctx.mem.attached():
            ctx.mem.apply_patches(False)
    except MemoryError_:
        pass
    ctx.server_address = None
    await ctx.shutdown()
    loop_task.cancel()


def launch(*launch_args):
    import colorama
    parser = get_base_parser(description="Cliente de Archipelago para Mortal Kombat XL")
    parser.add_argument("--name", default=None, help="Nombre del slot")
    parser.add_argument("url", nargs="?", help="URL de conexión de Archipelago")
    args = parser.parse_args(launch_args)
    args = handle_url_arg(args, parser=parser)
    Utils.init_logging("MKXLClient", exception_logger="Client")
    colorama.just_fix_windows_console()
    asyncio.run(main(args))
    colorama.deinit()
