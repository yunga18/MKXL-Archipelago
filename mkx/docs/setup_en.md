# Mortal Kombat X (XL) Setup Guide

## Required Software

- Mortal Kombat XL (PC, Steam), up to date.
- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.x or newer.

## Installation Procedures

1. Download `mkx.apworld` from the project's Releases page.
2. Double-click it (or copy it to Archipelago's `custom_worlds` folder) and restart the Launcher.
3. Use `plantilla_MKXL.yaml` from the project as a template for your YAML.

## Joining a MultiWorld Game

1. Open **Mortal Kombat XL Client** from the Archipelago Launcher and connect to the room.
2. Start the game (before or after connecting). The client hooks into `MK10.exe` automatically.
3. Locked characters cannot be picked until you receive them. Checks are sent automatically.
4. Run the game in windowed or borderless mode to see the on-screen notifications.

## Game Troubleshooting

- `/mk_estado` shows whether the client sees the game.
- `/marcar <text>` sends a check manually if something was not detected.
- The client writes `MKXL_debug.log` in the Archipelago folder; include it when reporting bugs.
- Play offline: the client reads and writes game memory like a trainer.
