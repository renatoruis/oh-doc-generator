"""Resumos do culto e do sermão via API Anthropic (Claude)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

# Limite conservador de caracteres (~<150k tokens em português) para evitar erro de contexto
DEFAULT_MAX_CHARS = 450_000


def load_transcript_json(path: str | Path) -> dict[str, Any]:
    p = Path(path).expanduser().resolve()
    data = json.loads(p.read_text(encoding="utf-8"))
    if "segments" not in data or not isinstance(data["segments"], list):
        raise ValueError("JSON inválido: falta a chave 'segments' (lista).")
    return data


def segments_to_plain_text(segments: list[dict[str, Any]], *, include_timestamps: bool) -> str:
    lines: list[str] = []
    for s in segments:
        text = (s.get("text") or "").strip()
        if not text:
            continue
        if include_timestamps:
            start = float(s.get("start", 0))
            mm = int(start // 60)
            ss = int(start % 60)
            lines.append(f"[{mm:02d}:{ss:02d}] {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


def approximate_tokens(chars: int) -> int:
    return max(1, chars // 4)


def truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def sanitize_filename(video_id: str) -> str:
    return re.sub(r"[^\w\-]", "_", video_id) or "transcricao"


PROMPT_CULTO_HEAD = """\
Com base na transcrição abaixo de um culto cristão (reunião de igreja), escreve em português de Portugal ou do Brasil (mantém o registo que fizer mais sentido pelo vocabulário da transcrição):

1. **Resumo geral** (5–10 frases): o que aconteceu no culto, ordem aproximada dos momentos (acolhimento, louvor, orações, ofertas, mensagem, encerramento, etc., conforme apareçam).
2. **Destaques**: 3–5 bullet points com momentos ou frases marcantes (sem inventar factos que não estejam na transcrição).

Se a transcrição estiver incompleta ou com ruído (música sem letra clara, outras línguas), indica-o com naturalidade. Não inventes nomes próprios ou citações que não apareçam no texto.

--- TRANSCRIÇÃO ---
"""

PROMPT_CULTO_TAIL = """
--- FIM ---
"""

PROMPT_SERMAO_HEAD = """\
Com base na transcrição abaixo de um culto cristão, identifica o trecho que corresponde à **pregação / sermão** (mensagem central, geralmente um discurso mais longo e contínuo, em torno de um tema bíblico). Se houver vários momentos de pregação, foca-te no sermão principal.

Escreve em português:

1. **Onde começa o sermão** (referência aproximada ao tempo ou à primeira frase do pregador, conforme a transcrição).
2. **Resumo do sermão** (estruturado): tema central, argumentos ou pontos principais, referências bíblicas mencionadas (se existirem na transcrição), aplicação ou desafio final.
3. Se não for possível distinguir claramente o sermão do resto (ex.: só música ou transcrição muito pobre), explica essa limitação e resume o que parecer ser a parte mais próxima de uma mensagem.

Não inventes citações bíblicas nem histórias que não estejam no texto.

--- TRANSCRIÇÃO ---
"""

PROMPT_SERMAO_TAIL = """
--- FIM ---
"""


def _prompt_culto(transcript: str) -> str:
    return PROMPT_CULTO_HEAD + transcript + PROMPT_CULTO_TAIL


def _prompt_sermao(transcript: str) -> str:
    return PROMPT_SERMAO_HEAD + transcript + PROMPT_SERMAO_TAIL


def build_prompt_culto(transcript: str) -> str:
    """Prompt completo para resumo do culto (uso em API ou Claude Code / Cursor)."""
    return _prompt_culto(transcript)


def build_prompt_sermao(transcript: str) -> str:
    """Prompt completo para resumo só do sermão."""
    return _prompt_sermao(transcript)


def _load_dotenv() -> None:
    """Carrega `.env` na raiz do projeto e no diretório atual (este último sobrepõe)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    # src/youtube_extract/summarize.py → raiz do repositório
    repo_root = Path(__file__).resolve().parent.parent.parent
    load_dotenv(repo_root / ".env")
    load_dotenv()


def call_claude(
    prompt: str,
    *,
    model: str,
    max_tokens: int,
) -> str:
    _load_dotenv()

    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError(
            "Instala o cliente: pip install anthropic"
        ) from e

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Define a variável de ambiente ANTHROPIC_API_KEY com a tua chave da Anthropic."
        )

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    parts: list[str] = []
    for block in msg.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "".join(parts).strip()


def run_summaries(
    json_path: str | Path,
    *,
    out_dir: str | Path,
    model: str,
    max_tokens: int,
    max_chars: int,
    include_timestamps: bool,
) -> tuple[Path, Path]:
    data = load_transcript_json(json_path)
    video_id = str(data.get("video_id", "unknown"))
    segments = data["segments"]
    plain = segments_to_plain_text(segments, include_timestamps=include_timestamps)
    plain, was_truncated = truncate_text(plain, max_chars)

    if not plain.strip():
        raise ValueError("Transcrição vazia após processar os segmentos.")

    header_note = ""
    if was_truncated:
        header_note = (
            f"\n\n> Aviso: a transcrição foi truncada aos primeiros {max_chars} caracteres "
            f"(~{approximate_tokens(max_chars)} tokens aprox.) para caber no contexto do modelo.\n\n"
        )

    text = plain
    base = sanitize_filename(video_id)
    out = Path(out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    culto_body = call_claude(
        build_prompt_culto(text),
        model=model,
        max_tokens=max_tokens,
    )
    sermao_body = call_claude(
        build_prompt_sermao(text),
        model=model,
        max_tokens=max_tokens,
    )

    path_culto = out / f"{base}_resumo_culto.md"
    path_sermao = out / f"{base}_resumo_sermao.md"

    meta = (
        f"<!-- video_id: {video_id} | model: {model} | chars: {len(plain)} "
        f"| truncated: {was_truncated} -->\n"
    )
    path_culto.write_text(meta + header_note + culto_body + "\n", encoding="utf-8")
    path_sermao.write_text(meta + header_note + sermao_body + "\n", encoding="utf-8")

    return path_culto, path_sermao
