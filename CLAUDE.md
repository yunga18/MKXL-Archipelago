# Mortal Kombat X (XL) para Archipelago

Mundo de Archipelago + cliente automático para **Mortal Kombat XL (PC, Steam)**.
El usuario (Yunga) no programa: explícale en español, en pasos simples, y haz tú el trabajo técnico.

## Estructura

- `mkx/` — el apworld (basado en la plantilla Manual for Archipelago). Nombre del juego: **"Mortal Kombat X"** (forzado en `mkx/Game.py`).
  - `mkx/data/*.json` — items, locations, opciones. **Se generan** con `tools/gen_data.py`; edita ese script, no los JSON a mano.
  - `mkx/mkxl/memory.py` — lectura/escritura de memoria de MK10.exe con ctypes (offsets, parches de código).
  - `mkx/mkxl/names.py` — nombres internos del juego → nombres de Archipelago.
  - `mkx/mkxl/client.py` — cliente "Mortal Kombat XL Client" (CommonClient): bloqueos + detección de checks.
  - `mkx/__init__.py` — al final registra el componente del Launcher. `add_client_to_launcher()` del Manual está desactivado a propósito.
- `tools/` — `gen_data.py`, `build_apworld.py`, `msf.py` (lector de PDB), `pe.py` (símbolos/desensamblado), `replay_test.py`.
- `research/` — registros reales de partidas (`MKXL_debug.log`, `MKXL_volcado.txt`).
- `Yunga_MKX.yaml` — YAML del jugador.

## Flujo de trabajo

1. Cambiar datos: editar `tools/gen_data.py` → `python tools/gen_data.py mkx/data`.
2. Subir `world_version` en `mkx/archipelago.json` cuando cambie algo.
3. Empaquetar e instalar: `python tools/build_apworld.py --instalar` (copia a `C:\ProgramData\Archipelago\custom_worlds`). Reiniciar el Launcher.
4. Si cambian nombres de items/locations, hay que **generar una partida nueva**.
5. El cliente escribe `C:\ProgramData\Archipelago\MKXL_debug.log` (cambios de estado) y `/mk_volcado` escribe `MKXL_volcado.txt`. Úsalos para investigar.

## Diseño del mundo (v0.4)

- Items: 33 personajes (progresión), 12 "Fragmento del Amuleto de Shinnok", relleno "1000 Koins", 4 trampas (por `filler_traps`). Se empieza con 3 personajes al azar.
- Locations: "Torre Klásica completada - X", "Fatality - X", "Brutality - X" (opción `incluir_brutalities`), "Historia Capítulo N - X" (opción `incluir_modo_historia`; cada capítulo requiere a su protagonista y a los anteriores), "Krypta: compra 1..20" (opción `incluir_krypta`, sin requisitos).
- Meta: "Restaurar el Amuleto y derrotar a Shinnok" = 8 fragmentos + 10 personajes; el cliente la envía al completar una Torre Klásica cumpliendo eso.
- Orden real de la historia: Johnny Cage, Kotal Kahn, Sub-Zero, Kung Jin, Sonya Blade, D'Vorah, Takeda, Jax, Scorpion, Raiden, Jacqui Briggs, Cassie Cage.

## Ingeniería inversa (MK10.exe de Steam)

`Binaries\Retail\MK10.pdb` coincide con `MK10.exe` (GUID d1feff98-49a5-164f-b4b0-0a5183ecf6a7, age 2). `MK10Game.exe` es otra build (otro GUID): no la usamos.
llvm-pdbutil no puede con este PDB (directorio demasiado grande) → usa `tools/msf.py`. Ojo: en `tools/publics.tsv` los offsets son relativos a la sección; para .text suma 0x1000 (RVA = off + 0x1000).
Base preferida 0x140000000; RVA = VA − 0x140000000. El cliente verifica la versión con la firma de `GetIsCharacterLocked`.

| Qué | RVA / offset |
|---|---|
| `FG_GAME_INFO::GetIsCharacterLocked(PLAYER_NUM, const char*)` | 0x484500 |
| `MKContentInfo::IsUnlocked(int player)` | 0x48EC50 |
| `GCharacterList` (TArray<MK10CharacterContentInfo>, stride 0x38) | 0x33196A8 (data*, num en +8) |
| entrada: FName +0x0, unlock page +0x8, unlock bit +0xC, **flags +0x10 (bit0 = desbloqueado)** | |
| `FName::Names` (TArray<FNameEntry*>), texto en entry+0x10 | 0x3800518 |
| `GFGGameInfo` (puntero a FG_GAME_INFO) | 0x30DBA00 |
| FG_GAME_INFO +0x8: QWORD flags — bit26 brutality iniciado, bit31 fatality iniciado, bit33 fatality terminado | |
| FG_GAME_INFO +0x1968: PLAYER_INFO*[2]; +0x1980 ganador de ronda; +0x1988 GAME_STATE; +0x198C GAME_MODES | |
| PLAYER_INFO +0x128: const char* nombre del personaje (válido si +0x130 != 0) | |
| Parche: `PopulateWithAllUnlockedCharacters` call IsUnlocked → `mov eax,1` | 0x270831 (`e81ae42100` → `b801000000`) |
| Parche: `GetRandomCharacter` call IsUnlocked → `mov eax,1` | 0x486A40 (`e80b820000` → `b801000000`) |

GAME_STATE: 0 INIT, 1 LOADING_FIGHT, 2 ATTRACT, 3 MAINMENU, 4 ONLINE, 5 KOTH, 6 PROFILES, 7 PSELECT, 8 PLAY, 9 GAME_OVER, 10 MOVIE, 11 FATALITY ("Finish Him", NO significa que se hizo), 12 LADDER, 13 INVALID.
GAME_MODES observados: −1 menú, 0 attract, 1 versus, 3 historia, 4 torre.

IsUnlocked: si offline / flags de debug / unlock page == −1 → usa flags+0x10 bit0; si no, `MK10Unlockables::IsItemUnLockedByGamepad`. En la prueba real, limpiar el bit0 bloqueó correctamente la selección.

Nombres internos: Aztec=Kotal Kahn, LadyBug=D'Vorah, Nomad=Erron Black, MasterMale=Ferra/Torr, CageJr=Cassie, JaxJr=Jacqui, KungLaoJr=Kung Jin, KenshiJr=Takeda, TanyaDLC=Tanya, BoRaiChoDLC=Bo' Rai Cho. Jefe final de la torre: `shinnokboss_a`.

Otros símbolos útiles: `MK10Unlockables`, `MK10TrophySystem::*`, `PlayerStats` (FATALITIES_PERFORMED, CHARACTER_LADDER_COMPLETIONS…), `BISendStoryProgressionEvent`, `UIChapterSelectScreen::*`.

## Estado y pendientes

- [x] Bloqueo de personajes en la selección (probado en juego).
- [x] Torre Klásica y capítulo 1 de historia detectados (probado con registro real vía replay).
- [x] Fatality/Brutality con las banderas de FG_GAME_INFO+0x8 (probado en juego 2026-11-17: Fatality en Versus y Torre, Brutality en Versus; bit26 = brutality confirmado).
- [x] Parches de rivales: rivales variados en la torre (confirmado por el usuario 2026-11-17; el registro muestra Triborg, Johnny Cage…).
- [x] Historia probada en juego (2026-11-17): Cap. 2 completo con una derrota+reintento → check al empezar Cap. 3; salir a mitad del Cap. 3 → sin check. v0.4.1: el personaje de historia solo se toma en GS_PLAY (al entrar, p1/p2 conservan los de la demo del menú → capítulos falsos).
- [x] v0.5.0 DeathLink: envía al perder (GAME_OVER, winner 1) en Torre/Historia; al recibir, pone a 0 la vida de P1 (`PLAYER_INFO+0x20` → FGCharacterObj, vida float 0..1 `+0xA38`, máx `+0xA3C`) en cada GS_PLAY hasta GAME_OVER. Probado en vivo 2026-11-17 escribiendo memoria: vida=0 → KO en <0,2 s; 2.ª ronda → GS_FATALITY (winner 1) → GAME_OVER winner 1. Envío probado en partida real (Torre, 2026-11-17). Falta recibir uno de otro jugador vía servidor. `/mk_morir` = prueba local.
- [x] v0.5.0 Avisos en pantalla (`mkxl/overlay.py`, tkinter transparente en hilo propio; requiere juego en ventana/sin bordes). `/mk_avisos` los activa o desactiva. Probado con el cliente real (2026-11-17).
- [ ] Historia: detección más robusta (ideal: leer el progreso guardado de capítulos en vez de heurística por cambio de personaje / 4 victorias).
- [ ] Cuando un personaje elegido al azar no fue recibido, hoy solo se ignoran sus checks.
- [x] v0.6.0 Trampas reales (`mkxl/traps.py`), una por pelea, persistidas en `MKXL_trampas/<seed>_<slot>.json`. Bits de desactivado en FGCharacterObj+0xF20 (4 QWORD, usamos el [3]): bloqueo bit19, salto bit8 (probados en juego). Especiales: bit4 + apagar bit1 de GenericCommand+0x20 en cada comando con +0x24 bit3 (array FGCharacterObj+0x9458, count +0x96B0; probado). Muy Difícil: AIDrone (PLAYER_INFO+0x2D8, id +0x2E0) nivel float +0xD0 (máx 19). Dificultad del menú en FG_GAME_INFO+0x19E4 (0 Muy Fácil … 4 Muy Difícil); con 0 la IA de Versus tenía nivel 2.0. `VERY_HARD_LEVEL` = 3.0 (medido: Versus Muy Difícil → nivel 3.0). Comandos `/mk_trampa`, `/mk_trampas`. Confirmado por el usuario en juego con el cliente 0.6.0 (2026-11-17).
- [x] v0.8.0 Krypta: 20 locations "Krypta: compra N" (opción `incluir_krypta`). Antes (0.7.0) contaba objetos nuevos, pero la Krypta se agota entre partidas → ahora cuenta cada **cambio de Koins** dentro de la Krypta (`GIsInKryptMode` RVA 0x37B7290, +5 s de gracia; cambios a <1 s = una compra). Koins: GExperienceManager RVA 0x3311D00 + pad*0x548 + 0x90 + 3*0x148 (pad 0). Probado en vivo: objeto −2300, cofre de Koins +1885 (costo y premio juntos), arte −1350. Los bits de desbloqueo (`GMK10Unlockables` RVA 0x331DCD0 +0x1EA8 | `GProgressionData` RVA 0x32166C0 +0xB713C, 97 páginas; nombres en +0x58, stride 0x50, pares {FName, máscara}) solo se registran en el log. Probado con el cliente real (2026-11-17).
- [x] v0.8.1 Koins reales: cada "1000 Koins" recibido suma 1000 al perfil (aplicados en `MKXL_koins/<seed>_<slot>.json`; el seed es `server_seed_name`/RoomInfo — en 0.8.1 salía `None_<slot>.json`, 0.8.2 lo migra). Valor real = estadística de perfil: StatsAccumulator (RVA 0x3308C80, usuario 0) +8 TSet de categorías (elem 0x60, clave u32; categoría 3) → TMap interno en elem+8 (elem 24 bytes: {statId u32, StatBase* +8}); statId = [vista Koins +4]. Valor `CEncodedValue<int>` en stat+0x28: valor = enc ^ clave(+0x2C) ^ 0x01000193. También se actualiza la copia de ExperienceStats (+0x90). Probado en vivo: +1000 se ve y se gasta. Persiste tras reiniciar el juego (confirmado por el usuario 2026-11-17). Probado con el cliente 0.8.2 (aviso + saldo 28 395; migración de None_1.json OK).
- [ ] Ideas: Torre Test Your Luck, Test Your Might (solo en Historia).

Probar cosas en vivo: el usuario abre el juego y el cliente; tú lees `MKXL_debug.log`. En Windows puedes también leer memoria directamente con un script Python usando `mkx/mkxl/memory.py`.
