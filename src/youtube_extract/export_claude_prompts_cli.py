"""Gera ficheiros .md com prompt + transcrição para usar no Claude Code ou Cursor (sem API)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from youtube_extract.summarize import (
    DEFAULT_MAX_CHARS,
    build_prompt_culto,
    build_prompt_sermao,
    load_transcript_json,
    sanitize_filename,
    segments_to_plain_text,
    truncate_text,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Cria dois Markdown com a transcrição e as instruções de resumo. "
            "Abre no Cursor (Chat/Composer) com @ficheiro ou cola no Claude Code — "
            "não usa ANTHROPIC_API_KEY."
        ),
    )
    parser.add_argument(
        "json_file",
        help="Caminho para o .json gerado pelo youtube-extract",
    )
    parser.add_argument(
        "-o",
        "--out-dir",
        default=".",
        help="Pasta de saída (default: atual)",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help=f"Máximo de caracteres da transcrição a incluir (default: {DEFAULT_MAX_CHARS})",
    )
    parser.add_argument(
        "--with-timestamps",
        action="store_true",
        help="Prefixa cada linha com [MM:SS] na transcrição",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        data = load_transcript_json(args.json_file)
    except (OSError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1

    video_id = str(data.get("video_id", "unknown"))
    segments = data["segments"]
    plain = segments_to_plain_text(segments, include_timestamps=args.with_timestamps)
    plain, was_truncated = truncate_text(plain, args.max_chars)

    if not plain.strip():
        print("Transcrição vazia.", file=sys.stderr)
        return 1

    base = sanitize_filename(video_id)
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    header = (
        "# Pedido para o Claude\n\n"
        "_Cola isto numa conversa (Cursor ou Claude Code) ou usa o ficheiro com @ no Cursor._\n\n"
    )
    if was_truncated:
        header += (
            f"> Aviso: transcrição truncada aos primeiros {args.max_chars} caracteres.\n\n"
        )

    path_culto = out_dir / f"{base}_para_claude_culto.md"
    path_sermao = out_dir / f"{base}_para_claude_sermao.md"

    path_culto.write_text(header + build_prompt_culto(plain) + "\n", encoding="utf-8")
    path_sermao.write_text(header + build_prompt_sermao(plain) + "\n", encoding="utf-8")

    print(f"Culto:  {path_culto}", file=sys.stderr)
    print(f"Sermão: {path_sermao}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
