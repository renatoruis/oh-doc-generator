#!/usr/bin/env python3
"""Ponto de entrada: `python main.py URL` (entrega ao cliente) ou `python main.py <comando> …`."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Callable

# Permite `python main.py` sem `pip install` (usa o pacote em src/)
_root = Path(__file__).resolve().parent
_src = _root / "src"
if _src.is_dir():
    p = str(_src)
    if p not in sys.path:
        sys.path.insert(0, p)

CommandMain = Callable[[list[str] | None], int]

_COMMANDS: dict[str, tuple[str, str]] = {
    "extract": ("youtube_extract.cli", "main"),
    "summarize": ("youtube_extract.summarize_cli", "main"),
    "prepare-claude": ("youtube_extract.export_claude_prompts_cli", "main"),
    "ministracao": ("youtube_extract.ministracao_cli", "main"),
}


def _print_help() -> int:
    print(__doc__ or "")
    print()
    print("Fluxo único (entrega para clientes):")
    print("  ./main.py https://www.youtube.com/watch?v=…")
    print("  → gera guia_open_groups_pt.pdf e guia_open_groups_en.pdf na pasta actual")
    print()
    print("Comandos avançados:", ", ".join(sorted(_COMMANDS.keys())))
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        _print_help()
        return 1
    if argv[0] in ("-h", "--help", "help"):
        return _print_help()

    from youtube_extract.client_pipeline import is_client_delivery_argv, main as client_main

    if is_client_delivery_argv(argv):
        return client_main(argv)

    cmd = argv[0]
    if cmd not in _COMMANDS:
        print(f"Comando desconhecido: {cmd!r}", file=sys.stderr)
        _print_help()
        return 1
    mod_name, fn_name = _COMMANDS[cmd]
    mod = importlib.import_module(mod_name)
    fn: CommandMain = getattr(mod, fn_name)
    return fn(argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
