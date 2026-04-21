"""CLI unificado Open Heavens — Typer app + entry points compatíveis."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

app = typer.Typer(
    name="open-heavens",
    help=(
        "Open Heavens — pipeline único que extrai legendas do YouTube, segmenta o culto com IA, "
        "gera resumo da ministração e produz dois PDFs do guia Open Groups (PT + EN)."
    ),
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.command("run")
def cmd_run(
    url: str = typer.Argument(..., help="URL do YouTube (incl. /live/…) ou ID de 11 caracteres"),
    output_base: Path = typer.Option(Path("entrega"), "-o", "--output", help="Pasta de trabalho (default: ./entrega; removida no fim)"),
    destination: Path | None = typer.Option(None, "-d", "--dest", help="Onde copiar os PDFs finais (default: CWD)"),
    lang: str = typer.Option("pt,en", "-l", "--lang", help="Idiomas das legendas, por ordem"),
    with_timestamps: bool = typer.Option(False, "--with-timestamps", help="Inclui [MM:SS] no prompt"),
    max_chars: int = typer.Option(450_000, "--max-chars", help="Máx. caracteres no prompt"),
    skip_claude: bool = typer.Option(False, "--skip-claude", help="Só extrai e grava — não chama Claude"),
    skip_segment: bool = typer.Option(False, "--skip-segment", help="Salta a segmentação prévia do culto"),
    force: bool = typer.Option(False, "--force", help="Refaz segmentação/resumo mesmo com cache"),
    keep_workdir: bool = typer.Option(False, "--keep-workdir", help="Mantém a pasta de trabalho no fim (debug)"),
    cookies: Path | None = typer.Option(None, "--cookies", help="Cookies Netscape para vídeos restritos"),
    proxy_http: str = typer.Option("", "--proxy-http", help="Proxy HTTP"),
    proxy_https: str = typer.Option("", "--proxy-https", help="Proxy HTTPS"),
    claude_bin: str | None = typer.Option(None, "--claude-bin", help="Caminho alternativo para `claude`"),
    claude_extra: str | None = typer.Option(None, "--claude-extra", help="Args extra para o Claude CLI"),
) -> None:
    """Pipeline completo — gera dois PDFs (PT + EN) na pasta de destino."""
    from youtube_extract.client_pipeline import run_client_delivery

    langs = [p.strip() for p in lang.split(",") if p.strip()] or ["pt", "en"]
    code, pdfs = run_client_delivery(
        url,
        output_base=output_base,
        languages=langs,
        include_timestamps=with_timestamps,
        max_chars=max_chars,
        skip_claude=skip_claude,
        skip_segment=skip_segment,
        force=force,
        cookie_path=str(cookies) if cookies else None,
        proxy_http=proxy_http or None,
        proxy_https=proxy_https or None,
        claude_bin=claude_bin,
        claude_extra=claude_extra,
        destination=destination,
        keep_workdir=keep_workdir,
    )
    if pdfs:
        typer.secho("\nPDFs gerados:", fg=typer.colors.GREEN, err=True)
        for p in pdfs:
            typer.secho(f"  - {p}", err=True)
    raise typer.Exit(code=code)


@app.command("extract")
def cmd_extract() -> None:
    """Só extrai a transcrição (sem Claude, sem guia). Ver `youtube-extract --help`."""
    from youtube_extract.cli import main as _main

    raise typer.Exit(code=_main(sys.argv[2:]))


@app.command("summarize")
def cmd_summarize() -> None:
    """Gera resumo via API Anthropic. Ver `youtube-summarize --help`."""
    from youtube_extract.summarize_cli import main as _main

    raise typer.Exit(code=_main(sys.argv[2:]))


@app.command("prepare-claude")
def cmd_prepare() -> None:
    """Prepara prompts para colar no Claude Code / Cursor."""
    from youtube_extract.export_claude_prompts_cli import main as _main

    raise typer.Exit(code=_main(sys.argv[2:]))


@app.command("ministracao")
def cmd_ministracao() -> None:
    """Só ministração (sem guia/cartões). Ver `youtube-ministracao --help`."""
    from youtube_extract.ministracao_cli import main as _main

    raise typer.Exit(code=_main(sys.argv[2:]))


# ────────────────────────── entry points compatíveis (pyproject.toml) ──────────────────────────


def extract_entry() -> None:
    from youtube_extract.cli import main as _main

    raise SystemExit(_main())


def summarize_entry() -> None:
    from youtube_extract.summarize_cli import main as _main

    raise SystemExit(_main())


def prepare_claude_entry() -> None:
    from youtube_extract.export_claude_prompts_cli import main as _main

    raise SystemExit(_main())


def ministracao_entry() -> None:
    from youtube_extract.ministracao_cli import main as _main

    raise SystemExit(_main())


if __name__ == "__main__":
    app()
