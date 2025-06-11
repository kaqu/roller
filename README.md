# Multi-Dice Roller

This project contains a terminal application built with [Textual](https://github.com/Textualize/textual) for rolling multiple dice. The specification describing expected functionality is provided in `SPECIFICATION.md`.

## Requirements

- Python 3.12+
- `uv` package manager

## Running

Dependencies are managed via `uv`. To run the app:

```bash
uv run multi_dice_roller.py
```

If you encounter import errors, try clearing the `uv` cache first:

```bash
uv cache clean && uv run multi_dice_roller.py
```

The application uses keyboard controls for rolling dice, locking/unlocking, and adjusting the dice count. See on-screen instructions for details.

## Development

Linting and static type checks are configured using [Ruff](https://docs.astral.sh/ruff/) and [Pyright](https://github.com/microsoft/pyright). Run them from the project root:

```bash
ruff check .
pyright
```

