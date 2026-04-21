"""Progresso do pipeline — versão com rich (spinner + tabela final)."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.theme import Theme

TOTAL_PHASES = 5

_theme = Theme(
    {
        "oh.obsidian": "#101820 on default",
        "oh.green": "bold #279F00",
        "oh.lime": "bold #C0DF16",
        "oh.cream": "#F2EBE7",
        "phase": "bold cyan",
        "ok": "bold green",
        "warn": "yellow",
        "err": "bold red",
    }
)

_console: Console | None = None


def console() -> Console:
    global _console
    if _console is None:
        _console = Console(stderr=True, theme=_theme, highlight=False)
    return _console


def phase(current: int, total: int, message: str) -> None:
    """Imprime uma linha de fase numerada, estilo `[n/total] mensagem`."""
    console().print(f"[phase][{current}/{total}][/phase] {message}")


def info(message: str) -> None:
    console().print(f"  [oh.green]·[/oh.green] {message}")


def warn(message: str) -> None:
    console().print(f"  [warn]![/warn] {message}")


def err(message: str) -> None:
    console().print(f"  [err]x[/err] {message}")


@contextmanager
def spinner(message: str) -> Iterator[None]:
    """Context manager com spinner rich; desliga em non-TTY."""
    c = console()
    if not sys.stderr.isatty():
        c.print(f"  … {message}")
        yield
        return
    with c.status(f"[oh.green]{message}[/oh.green]", spinner="dots"):
        yield


def final_summary_table(title: str, out_dir: Path, artefactos: list[tuple[str, Path]]) -> None:
    """Tabela final com paths clicáveis (file://) e tamanho."""
    table = Table(
        title=title,
        title_style="oh.green",
        show_lines=False,
        expand=False,
        header_style="oh.lime",
    )
    table.add_column("Ficheiro", overflow="fold")
    table.add_column("Tamanho", justify="right")
    table.add_column("Nota", overflow="fold")
    total_bytes = 0
    for nota, path in artefactos:
        if not path.exists():
            table.add_row(f"[dim]{path.name}[/dim]", "-", f"[warn]ausente[/warn] {nota}")
            continue
        size = path.stat().st_size
        total_bytes += size
        table.add_row(
            f"[link=file://{path.resolve()}]{path.name}[/link]",
            _human_size(size),
            nota,
        )
    console().print()
    console().print(table)
    console().print(
        f"[oh.green]Pasta:[/oh.green] [link=file://{out_dir.resolve()}]{out_dir}[/link]  "
        f"[dim]({_human_size(total_bytes)} total)[/dim]"
    )


def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} TB"
