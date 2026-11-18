"""Traducción entre los nombres internos del juego y los nombres de Archipelago."""
from __future__ import annotations

import re
from typing import Optional

# nombre interno base (minúsculas) -> item de Archipelago
INTERNAL_TO_AP = {
    "alien": "Alien",
    "boraichodlc": "Bo' Rai Cho",
    "boraicho": "Bo' Rai Cho",
    "cagejr": "Cassie Cage",
    "ladybug": "D'Vorah",
    "ermac": "Ermac",
    "nomad": "Erron Black",
    "mastermale": "Ferra/Torr",
    "goro": "Goro",
    "jaxjr": "Jacqui Briggs",
    "jason": "Jason Voorhees",
    "jax": "Jax",
    "johnnycage": "Johnny Cage",
    "kano": "Kano",
    "kenshi": "Kenshi",
    "kitana": "Kitana",
    "aztec": "Kotal Kahn",
    "kunglaojr": "Kung Jin",
    "kunglao": "Kung Lao",
    "leatherface": "Leatherface",
    "liukang": "Liu Kang",
    "mileena": "Mileena",
    "predator": "Predator",
    "quanchi": "Quan Chi",
    "raiden": "Raiden",
    "reptile": "Reptile",
    "scorpion": "Scorpion",
    "shinnok": "Shinnok",
    "sonya": "Sonya Blade",
    "subzero": "Sub-Zero",
    "kenshijr": "Takeda",
    "tanyadlc": "Tanya",
    "tanya": "Tanya",
    "tremor": "Tremor",
    "triborg": "Triborg",
}

_PREFIXES = ("char_", "ui_ps_", "trait_")


def internal_to_ap(name: str) -> Optional[str]:
    """'CHAR_KungLaoJr_B' -> 'Kung Jin'. Devuelve None si no es un personaje jugable conocido."""
    if not name:
        return None
    n = name.strip().lower()
    for p in _PREFIXES:
        if n.startswith(p):
            n = n[len(p):]
    base = n.split("_", 1)[0]
    base = re.sub(r"[^a-z]", "", base)
    return INTERNAL_TO_AP.get(base)
