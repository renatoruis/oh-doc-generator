"""Pipeline único: URL → dois PDFs (PT/EN) na pasta de invocação.

Durante a execução usa uma pasta temporária (``<output_base>/<video_id>/``,
por omissão ``./entrega/<video_id>/``) para guardar artefactos intermédios
(transcrição, segmentação, resumo). No fim do pipeline:

1. Os dois PDFs (``guia_open_groups_pt.pdf`` e ``guia_open_groups_en.pdf``)
   são copiados para a pasta em que o comando foi invocado.
2. Toda a pasta ``entrega/`` é removida.

Não gera HTML, cartões sociais, flyer nem ``.ics``.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from youtube_extract.extract import NoCaptionsAvailable
from youtube_extract.ministracao import run_ministracao_workflow
from youtube_extract.pdf_export import render_open_groups_files
from youtube_extract.progress import TOTAL_PHASES, err, final_summary_table, info, phase
from youtube_extract.video_id import extract_video_id
from youtube_extract.youtube_metadata import fetch_youtube_metadata, write_metadata_json

EXIT_NO_CAPTIONS = 2

KNOWN_SUBCOMMANDS = frozenset(
    {"extract", "summarize", "prepare-claude", "ministracao", "help"}
)


def looks_like_url_or_id(token: str) -> bool:
    if token in KNOWN_SUBCOMMANDS:
        return False
    if token.startswith("-"):
        return False
    if token.startswith(("http://", "https://", "www.")):
        return True
    return bool(re.fullmatch(r"[a-zA-Z0-9_-]{11}", token))


def is_client_delivery_argv(argv: Sequence[str]) -> bool:
    if not argv:
        return False
    if argv[0] in KNOWN_SUBCOMMANDS:
        return False
    if argv[0] in ("-h", "--help", "help"):
        return False
    return any(looks_like_url_or_id(t) for t in argv)


def _rename_if_exists(src: Path, dst: Path) -> Path | None:
    """Move src → dst (apaga dst se já existir). Devolve dst se existir no fim."""
    if src.exists():
        if dst.exists() and src.resolve() != dst.resolve():
            dst.unlink()
        if src.resolve() != dst.resolve():
            src.rename(dst)
    return dst if dst.exists() else None


def run_client_delivery(
    url_or_id: str,
    *,
    output_base: Path,
    languages: list[str],
    include_timestamps: bool,
    max_chars: int,
    skip_claude: bool,
    skip_segment: bool = False,
    force: bool = False,
    cookie_path: str | None,
    proxy_http: str | None,
    proxy_https: str | None,
    claude_bin: str | None,
    claude_extra: str | None,
    destination: Path | None = None,
    keep_workdir: bool = False,
) -> tuple[int, list[Path]]:
    """Executa o pipeline e devolve ``(exit_code, [pdfs_finais])``.

    Parameters
    ----------
    destination:
        Pasta final onde os PDFs são copiados. Por omissão usa ``Path.cwd()``.
    keep_workdir:
        Se ``True``, mantém ``output_base/<video_id>/`` com todos os artefactos
        intermédios (útil para debugging). Por omissão, toda a pasta
        ``output_base`` é apagada no fim.
    """
    video_id = extract_video_id(url_or_id)
    entrega_root = output_base.expanduser().resolve()
    out_dir = entrega_root / video_id
    out_dir.mkdir(parents=True, exist_ok=True)

    dest_dir = (destination or Path.cwd()).expanduser().resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    source_url = (
        url_or_id if url_or_id.startswith("http") else f"https://www.youtube.com/watch?v={video_id}"
    )

    phase(1, TOTAL_PHASES, "A obter metadados do vídeo (yt-dlp)…")
    meta_path = out_dir / "metadata.json"
    if meta_path.is_file() and not force:
        import json as _json

        metadata = _json.loads(meta_path.read_text(encoding="utf-8"))
        info("Metadados já presentes — a reutilizar.")
    else:
        metadata = fetch_youtube_metadata(source_url)
        write_metadata_json(meta_path, metadata)

    # Fases 2-4 (transcrição, segmentação, resumo) são emitidas pelo workflow.
    try:
        result = run_ministracao_workflow(
            url_or_id,
            out_dir=out_dir,
            languages=languages,
            include_timestamps=include_timestamps,
            max_chars=max_chars,
            cookie_path=cookie_path,
            proxy_http=proxy_http,
            proxy_https=proxy_https,
            skip_claude=skip_claude,
            skip_segment=skip_segment,
            force=force,
            claude_bin=claude_bin,
            claude_extra=claude_extra,
            missing_claude_ok=True,
            show_progress=True,
        )
    except NoCaptionsAvailable as exc:
        err(f"Sem legendas para {exc.video_id} — {exc.reason}")
        info(f"URL: {source_url}")
        info(
            "Sugestões: verifica se o vídeo é público e recente (lives demoram algumas horas "
            "a gerar legendas automáticas), ou passa outro URL com legendas já disponíveis."
        )
        info("Podes confirmar com: yt-dlp --list-subs <URL>")
        if not keep_workdir:
            try:
                if entrega_root.exists() and entrega_root.is_dir():
                    shutil.rmtree(entrega_root)
            except Exception:
                pass
        return EXIT_NO_CAPTIONS, []

    vid = str(result["video_id"])

    _rename_if_exists(out_dir / f"{vid}.json", out_dir / "transcricao.json")
    _rename_if_exists(out_dir / f"{vid}_ministracao_prompt.md", out_dir / "ministracao_prompt.md")
    _rename_if_exists(out_dir / f"{vid}_resumo_ministracao.md", out_dir / "resumo_ministracao.md")

    resumo_path = out_dir / "resumo_ministracao.md"
    resumo_ok = resumo_path.is_file() and bool(resumo_path.read_text(encoding="utf-8").strip())

    phase(5, TOTAL_PHASES, "A gerar guias Open Groups (PDF PT + EN)…")
    meta_for_pdf = {**metadata, "video_id": vid}
    guias = render_open_groups_files(
        out_dir,
        metadata=meta_for_pdf,
        resumo_md_path=resumo_path if resumo_ok else None,
        video_id=vid,
        source_url=source_url,
    )
    pdf_pt = guias.get("pdf_pt")
    pdf_en = guias.get("pdf_en")

    # Copia PDFs para a pasta de destino
    final_pdfs: list[Path] = []
    for src in (pdf_pt, pdf_en):
        if src and src.exists():
            dst = dest_dir / src.name
            shutil.copy2(str(src), str(dst))
            final_pdfs.append(dst)
            info(f"PDF copiado → {dst}")

    # Limpeza: remove a pasta entrega/ (output_base), a menos que --keep-workdir
    if not keep_workdir:
        try:
            if entrega_root.exists() and entrega_root.is_dir():
                shutil.rmtree(entrega_root)
                info(f"Pasta de trabalho removida: {entrega_root}")
        except Exception as e:  # pragma: no cover - defensive
            info(f"Falha ao remover {entrega_root}: {e}")

    # Sumário final
    if final_pdfs:
        rows: list[tuple[str, Path]] = []
        for pdf in final_pdfs:
            label = "Guia PDF (PT)" if pdf.name.endswith("_pt.pdf") else "Guia PDF (EN)"
            rows.append((label, pdf))
        final_summary_table("Entrega Open Heavens", dest_dir, rows)
    else:
        info("Nenhum PDF foi gerado — verifica as mensagens acima.")

    exit_code = 0
    code = result.get("claude_code")
    if not skip_claude and isinstance(code, int) and code != 0:
        exit_code = 1
    if not final_pdfs:
        exit_code = exit_code or 1
    return exit_code, final_pdfs


def main(argv: Sequence[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description=(
            "Entrega Open Heavens: extrai legendas, segmenta o culto com Claude, gera resumo "
            "da ministração e produz dois PDFs do guia Open Groups (PT + EN) na pasta actual."
        ),
    )
    parser.add_argument("url", help="URL do YouTube (incl. /live/...) ou ID de 11 caracteres")
    parser.add_argument(
        "-o",
        "--output",
        default="entrega",
        dest="output_base",
        help="Pasta de trabalho intermediária (default: ./entrega)",
    )
    parser.add_argument(
        "-d",
        "--dest",
        default=None,
        dest="destination",
        help="Pasta onde copiar os PDFs finais (default: directório actual)",
    )
    parser.add_argument("-l", "--lang", default="pt,en", help="Idiomas (default: pt,en)")
    parser.add_argument(
        "--with-timestamps",
        action="store_true",
        help="Inclui [MM:SS] no texto usado no resumo",
    )
    parser.add_argument("--max-chars", type=int, default=450_000)
    parser.add_argument("--skip-claude", action="store_true")
    parser.add_argument(
        "--skip-segment",
        action="store_true",
        help="Salta a segmentação do culto (um chamado Claude a menos; resumo sobre a transcrição inteira).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Refaz segmentação/resumo mesmo que artefactos já existam",
    )
    parser.add_argument(
        "--keep-workdir",
        action="store_true",
        help="Não remove a pasta de trabalho no fim (útil para debug).",
    )
    parser.add_argument("--cookies", metavar="PATH", default=None)
    parser.add_argument("--proxy-http", default="", metavar="URL")
    parser.add_argument("--proxy-https", default="", metavar="URL")
    parser.add_argument("--claude-bin", default=None)
    parser.add_argument("--claude-extra", default=None)

    args = parser.parse_args(list(argv) if argv is not None else None)
    langs = [p.strip() for p in args.lang.split(",") if p.strip()] or ["pt", "en"]

    try:
        code, pdfs = run_client_delivery(
            args.url,
            output_base=Path(args.output_base),
            languages=langs,
            include_timestamps=args.with_timestamps,
            max_chars=args.max_chars,
            skip_claude=args.skip_claude,
            skip_segment=args.skip_segment,
            force=args.force,
            cookie_path=args.cookies,
            proxy_http=args.proxy_http or None,
            proxy_https=args.proxy_https or None,
            claude_bin=args.claude_bin,
            claude_extra=args.claude_extra,
            destination=Path(args.destination) if args.destination else None,
            keep_workdir=args.keep_workdir,
        )
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1

    if pdfs:
        print("PDFs gerados:", file=sys.stderr)
        for p in pdfs:
            print(f"  - {p}", file=sys.stderr)
    return code


def _write_entrega_md(*_args: Any, **_kwargs: Any) -> None:  # pragma: no cover - compat shim
    """Compat: ENTREGA.md já não é gerado (pasta é removida no final)."""
    return None


def brand_name() -> str:  # pragma: no cover - usado apenas como referência
    from youtube_extract.brand import open_heavens as brand

    return brand.CHURCH_NAME
