"""Reproduce un MKXL_debug.log contra la lógica de detección del cliente, sin abrir el juego.

    set AP_SRC=C:\ruta\al\codigo\fuente\de\Archipelago   (git clone de ArchipelagoMW/Archipelago)
    python tools/replay_test.py research/MKXL_debug_prueba1.log

Requiere que mkx.apworld esté en %AP_SRC%\custom_worlds y las dependencias de Archipelago instaladas.
"""
import ast, asyncio, os, sys, types
sys.path.insert(0, os.environ["AP_SRC"])
os.chdir(os.environ["AP_SRC"])
import ModuleUpdate
ModuleUpdate.update_ran = True
import worlds  # noqa
from worlds.mkx.mkxl import client as C
from worlds.mkx.mkxl.memory import GAME_MODES

lines = [l.split(' ', 1)[1] for l in open(sys.argv[1], encoding='utf-8') if "{'state'" in l]
states = []
for l in lines:
    d = ast.literal_eval(l.strip())
    d['mode_name'] = GAME_MODES.get(d['mode'], str(d['mode']))
    d.setdefault('fatality', False)
    d.setdefault('brutality', False)
    states.append(d)


class FakeMem:
    def __init__(self): self.i = 0
    def game_state(self): return states[self.i]


class Ctx:
    pass


ctx = Ctx()
for name in ['prev', 'last_snapshot', 'story_char', 'last_story_fight']:
    setattr(ctx, name, None)
ctx.fight_sent, ctx.story_wins, ctx.story_done_session = set(), set(), set()
ctx.finished_game = False
ctx.mem = FakeMem()
ctx.debug = lambda m: None
sent = []
received = {"Reptile", "Kano", "Leatherface"}


async def send(name): sent.append(name)
ctx.send_location_by_name = send
ctx.received_characters = lambda: received
ctx.counts = lambda: (0, 3)
for fn in ['detect', 'check_if_received', 'story_chapter_done']:
    setattr(ctx, fn, types.MethodType(getattr(C.MKXLContext, fn), ctx))


async def run():
    for i in range(len(states)):
        ctx.mem.i = i
        await ctx.detect()
    # simular salida de la historia
    states.append(dict(states[-1], mode=-1, mode_name='MENU', state=3))
    ctx.mem.i = len(states) - 1
    await ctx.detect()

asyncio.run(run())
print("checks enviados:", sent)
print("historia: personaje", ctx.story_char, "victorias", ctx.story_wins)
