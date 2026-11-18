# Mortal Kombat X (XL) para Archipelago

Mundo de [Archipelago](https://archipelago.gg) para **Mortal Kombat XL (PC, Steam)**, con un cliente
automático que lee el juego en vivo: bloquea a los personajes que aún no recibiste, detecta tus checks
solo y aplica trampas, DeathLink y Koins de verdad.

*English summary at the bottom.*

## Qué hace

- **Personajes bloqueados:** empiezas con 3 personajes al azar; el resto se desbloquea al recibirlos.
  Los rivales de la torre siguen siendo variados.
- **Checks automáticos:**
  - *Torre Klásica completada* con cada personaje (33).
  - *Fatality* con cada personaje (33).
  - *Brutality* con cada personaje (33, opcional).
  - *Historia*: los 12 capítulos (opcional).
  - *Krypta*: 20 compras con Koins (opcional; cualquier compra cuenta, así nunca se agota).
- **Objetos:** 33 personajes, 12 *Fragmentos del Amuleto de Shinnok*, *1000 Koins* (se suman de verdad a
  tu saldo) y 4 trampas reales (sin bloquear, sin saltar, sin especiales, rival en Muy Difícil).
- **Meta:** reunir 8 fragmentos y 10 personajes, y completar una Torre Klásica.
- **DeathLink** (opcional) y **avisos en pantalla** de lo que recibes y envías.

## Requisitos

- **Mortal Kombat XL de Steam (PC)**, actualizado. El cliente comprueba la versión del ejecutable.
- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.x o posterior.
- Para ver los avisos en pantalla, el juego debe estar en **Ventana** o **Ventana sin bordes**.

## Instalación

1. Descarga `mkx.apworld` de la sección [Releases](../../releases).
2. Haz doble clic en `mkx.apworld` (o cópialo a la carpeta `custom_worlds` de Archipelago,
   normalmente `C:\ProgramData\Archipelago\custom_worlds`).
3. Reinicia el **Archipelago Launcher**.
4. Copia [`plantilla_MKXL.yaml`](plantilla_MKXL.yaml), cambia `name` por tu nombre y ajusta las opciones.

## Cómo jugar

1. Genera y hostea la partida como cualquier otra de Archipelago.
2. En el Launcher abre **Mortal Kombat XL Client** y conéctate.
3. Abre el juego (antes o después, da igual): el cliente se engancha solo.
4. Juega normal. Los checks se envían solos y verás avisos arriba a la derecha.

Comandos útiles en el cliente:

| Comando | Qué hace |
|---|---|
| `/mk_estado` | Si el cliente ve el juego y qué personajes tienes |
| `/pendientes` | Lista los checks que te faltan |
| `/marcar <texto>` | Envía a mano un check (por si algo no se detectó) |
| `/mk_trampas` | Trampas pendientes para tus próximas peleas |
| `/mk_trampa bloqueo\|salto\|especiales\|dificil` | Prueba una trampa en la próxima pelea |
| `/mk_avisos` | Activa o desactiva los avisos en pantalla |
| `/mk_morir` | Prueba local de DeathLink (no se envía a nadie) |

## Notas

- El cliente lee y escribe la memoria del juego (como un *trainer*). Úsalo **sin conexión / fuera de
  partidas online**.
- Los *1000 Koins* se suman a tu perfil de verdad y se guardan.
- Los bloqueos de personajes solo existen mientras el cliente está abierto; al cerrarlo, el juego vuelve
  a la normalidad.
- La detección del Modo Historia es aproximada; si un capítulo no se envía, usa `/marcar`.

## Para desarrolladores

- `mkx/` es el apworld (basado en [Manual for Archipelago](https://github.com/ManualForArchipelago/Manual)).
  Los JSON de `mkx/data/` se generan con `python tools/gen_data.py mkx/data`.
- `mkx/mkxl/` es el cliente: `memory.py` (offsets de MK10.exe), `client.py`, `traps.py`, `overlay.py`.
- `python tools/build_apworld.py` crea `dist/mkx.apworld` (`--instalar` lo copia a Archipelago).
- `CLAUDE.md` tiene las notas de ingeniería inversa (offsets, estructuras y qué está probado).
- `tools/msf.py` + `tools/pe.py` leen los símbolos de `MK10.pdb` (incluido con el juego).

## English summary

Archipelago world + automatic client for **Mortal Kombat XL (PC/Steam)**. Characters are locked until
received; Klassic Tower, Fatality, Brutality, Story chapter and Krypt purchase checks are detected
automatically by reading game memory. Includes real traps, DeathLink, real Koins and an on-screen
overlay. Install: download `mkx.apworld` from Releases, double-click it, restart the Launcher, use
`plantilla_MKXL.yaml` as your YAML, then run *Mortal Kombat XL Client* from the Launcher. The game must
be in windowed/borderless mode for the overlay. The in-game texts and item names are in Spanish.

---

Fan-made project, not affiliated with Warner Bros. or NetherRealm Studios. No game files are included.
License: [MIT](LICENSE).
