"""Genera los JSON del apworld Manual de Mortal Kombat XL."""
import json, os, sys

OUT = sys.argv[1]

GAME = "MortalKombatXL"
CREATOR = "Kombatiente"

# 33 personajes jugables de MKXL (PC)
PERSONAJES = [
    "Alien", "Bo' Rai Cho", "Cassie Cage", "D'Vorah", "Ermac", "Erron Black",
    "Ferra/Torr", "Goro", "Jacqui Briggs", "Jason Voorhees", "Jax", "Johnny Cage",
    "Kano", "Kenshi", "Kitana", "Kotal Kahn", "Kung Jin", "Kung Lao", "Leatherface",
    "Liu Kang", "Mileena", "Predator", "Quan Chi", "Raiden", "Reptile", "Scorpion",
    "Shinnok", "Sonya Blade", "Sub-Zero", "Takeda", "Tanya", "Tremor", "Triborg",
]
assert len(PERSONAJES) == 33

# Capítulos del Modo Historia y su protagonista
HISTORIA = [
    "Johnny Cage", "Kotal Kahn", "Sub-Zero", "Kung Jin", "Sonya Blade", "D'Vorah",
    "Takeda", "Jax", "Scorpion", "Raiden", "Jacqui Briggs", "Cassie Cage",
]

FRAGMENTO = "Fragmento del Amuleto de Shinnok"
FRAG_TOTAL = 12
FRAG_NECESARIOS = 8
PERSONAJES_NECESARIOS = 10
KRYPTA_CHECKS = 20       # "Krypta: compra N" (el cliente cuenta cada cambio de Koins dentro de la Krypta)

SCHEMA = "https://github.com/ManualForArchipelago/Manual/raw/main/schemas/Manual.{}.schema.json"


def dump(name, data):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        f.write("\n")


game = {
    "$schema": SCHEMA.format("game"),
    "game": GAME,
    "creator": CREATOR,
    "filler_item_name": "1000 Koins",
    "starting_items": [
        {"item_categories": ["Personajes"], "random": 3}
    ],
    "death_link": True,
}

items = [
    {"name": p, "category": ["Personajes"], "progression": True}
    for p in PERSONAJES
]
items.append({
    "name": FRAGMENTO, "category": ["Amuleto"], "count": FRAG_TOTAL,
    "progression": True,
})
trampas = [
    "Trampa: Próxima pelea sin bloquear",
    "Trampa: Próxima pelea sin movimientos especiales",
    "Trampa: Próxima pelea sin saltar",
    "Trampa: Próxima pelea en dificultad Muy Difícil",
]
for t in trampas:
    items.append({"name": t, "category": ["Trampas"], "trap": True, "count": 0})

locations = []
for p in PERSONAJES:
    locations.append({
        "name": f"Torre Klásica completada - {p}",
        "category": ["Torre Klásica"], "requires": f"|{p}|",
    })
for p in PERSONAJES:
    locations.append({
        "name": f"Fatality - {p}",
        "category": ["Fatalities"], "requires": f"|{p}|",
    })
for p in PERSONAJES:
    locations.append({
        "name": f"Brutality - {p}",
        "category": ["Brutalities"], "requires": f"|{p}|",
    })
for i, p in enumerate(HISTORIA, start=1):
    # Los capítulos van en orden: necesitas al protagonista de este y de todos los anteriores
    req = " and ".join(f"|{x}|" for x in dict.fromkeys(HISTORIA[:i]))
    locations.append({
        "name": f"Historia Capítulo {i} - {p}",
        "category": ["Modo Historia"], "requires": req,
    })
for i in range(1, KRYPTA_CHECKS + 1):
    # Solo hacen falta Koins, que se ganan peleando con cualquier personaje
    locations.append({"name": f"Krypta: compra {i}", "category": ["Krypta"]})
locations.append({
    "name": "Restaurar el Amuleto y derrotar a Shinnok",
    "category": ["Meta"], "victory": True,
    "requires": f"|{FRAGMENTO}:{FRAG_NECESARIOS}| and |@Personajes:{PERSONAJES_NECESARIOS}|",
})

categories = {
    "$schema": SCHEMA.format("categories"),
    "Personajes": {},
    "Amuleto": {},
    "Trampas": {},
    "Torre Klásica": {},
    "Fatalities": {},
    "Brutalities": {"yaml_option": ["incluir_brutalities"]},
    "Modo Historia": {"yaml_option": ["incluir_modo_historia"]},
    "Krypta": {"yaml_option": ["incluir_krypta"]},
    "Meta": {},
}

options = {
    "$schema": "https://raw.githubusercontent.com/ManualForArchipelago/Manual/main/schemas/Manual.options.schema.json",
    "core": {
        "goal": {"display_name": "Objetivo", "hidden": True},
        "filler_traps": {"values": {"recomendado": 20}},
    },
    "user": {
        "incluir_brutalities": {
            "type": "Toggle", "default": False,
            "display_name": "Incluir Brutalities",
            "description": ["Agrega un check por hacer un Brutality con cada personaje.",
                            "Más difícil: muchos Brutalities tienen condiciones especiales."],
        },
        "incluir_modo_historia": {
            "type": "Toggle", "default": True,
            "display_name": "Incluir Modo Historia",
            "description": ["Agrega un check por cada uno de los 12 capítulos de la historia.",
                            "Cada capítulo exige tener a su protagonista y a los de los capítulos anteriores."],
        },
        "incluir_krypta": {
            "type": "Toggle", "default": True,
            "display_name": "Incluir Krypta",
            "description": [f"Agrega {KRYPTA_CHECKS} checks: 'Krypta: compra N'.",
                            "Cuenta cada cosa que compres con Koins en la Krypta, sea lo que sea",
                            "(objetos nuevos, cofres de Koins, consumibles). No se agota."],
        },
    },
}

dump("game.json", game)
dump("items.json", {"$schema": SCHEMA.format("items"), "data": items})
dump("locations.json", {"$schema": SCHEMA.format("locations"), "data": locations})
dump("categories.json", categories)
dump("options.json", options)
dump("regions.json", {"$schema": SCHEMA.format("regions")})
dump("events.json", {"$schema": SCHEMA.format("events"), "data": []})
print(f"{len(items)} items, {len(locations)} locations")
