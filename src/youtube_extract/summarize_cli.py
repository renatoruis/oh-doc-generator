"""CLI: resumos do culto e do sermão com Claude (API Anthropic)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from youtube_extract.summarize import DEFAULT_MAX_CHARS, run_summaries


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Lê o JSON gerado pelo youtube-extract e pede ao Claude (API Anthropic) "
            "dois textos: resumo do culto inteiro e resumo focado no sermão."
        ),
    )
    parser.add_argument(
        "json_file",
        help="Caminho para o ficheiro .json (ex.: VIDEO_ID.json)",
    )
    parser.add_argument(
        "-o",
        "--out-dir",
        default=".",
        help="Pasta onde gravar os .md (default: diretório atual)",
    )
    parser.add_argument(
        "--model",
        default="claude-3-5-sonnet-20241022",
        help="Modelo Anthropic (ex.: claude-3-5-sonnet-20241022, claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=8192,
        help="Máximo de tokens na resposta de cada chamada (default: 8192)",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help=(
            "Máximo de caracteres da transcrição a enviar (default: "
            f"{DEFAULT_MAX_CHARS}; reduz se a API der erro de contexto)"
        ),
    )
    parser.add_argument(
        "--with-timestamps",
        action="store_true",
        help="Prefixa cada linha com [MM:SS] (ajuda o modelo a localizar o sermão)",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        p_culto, p_sermao = run_summaries(
            args.json_file,
            out_dir=args.out_dir,
            model=args.model,
            max_tokens=args.max_tokens,
            max_chars=args.max_chars,
            include_timestamps=args.with_timestamps,
        )
    except (RuntimeError, ValueError, OSError) as e:
        print(str(e), file=sys.stderr)
        return 1
    except Exception as e:
        err = str(e)
        print(f"Erro ao chamar a API: {e}", file=sys.stderr)
        if "usage limits" in err.lower():
            print(
                "\nDica: limite da chave na Consola Anthropic. Podes gerar os pedidos sem API:\n"
                "  youtube-prepare-claude SEU_VIDEO.json -o ./saidas\n"
                "Depois abre os .md no Cursor (@ficheiro) ou no Claude Code.",
                file=sys.stderr,
            )
        return 1

    print(f"Resumo do culto:    {p_culto}", file=sys.stderr)
    print(f"Resumo do sermão:   {p_sermao}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
