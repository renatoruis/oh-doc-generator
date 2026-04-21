"""Workflow: URL → transcrição → (segmentação) → resumo da ministração (PT-PT + EN)."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import time
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from youtube_transcript_api import FetchedTranscript

from youtube_extract.cookies import session_with_netscape_cookies
from youtube_extract.extract import (
    fetch_transcript,
    proxy_from_urls,
    write_json_file,
)
from youtube_extract.progress import TOTAL_PHASES, info, phase, warn
from youtube_extract.segmentacao import (
    Segmentacao,
    build_segmentation_prompt,
    carregar_segmentacao_cache,
    contexto_outros_blocos,
    extrair_ministracao,
    gravar_artefactos,
    parse_segmentation_response,
)
from youtube_extract.summarize import segments_to_plain_text, truncate_text
from youtube_extract.video_id import extract_video_id

DEFAULT_MAX_CHARS = 450_000
CLAUDE_RETRY_ATTEMPTS = 2
CLAUDE_RETRY_BACKOFF_S = 5.0


def _templates_dir() -> Path:
    return Path(__file__).resolve().parent / "templates"


def build_ministracao_prompt(
    transcript_plain: str,
    *,
    segmentado: bool,
    contexto: str = "",
) -> str:
    """Renderiza o prompt via template Jinja; `segmentado=True` quando já recebe só o bloco."""
    env = Environment(
        loader=FileSystemLoader(str(_templates_dir() / "prompts")),
        autoescape=False,
        keep_trailing_newline=True,
    )
    tpl = env.get_template("ministracao.md.j2")
    return tpl.render(
        transcript=transcript_plain,
        segmentado=segmentado,
        contexto_outros_blocos=contexto,
    )


def run_claude_print(
    prompt: str,
    *,
    claude_bin: str,
    extra_args: Sequence[str] | None = None,
    cwd: Path | None = None,
    retry_attempts: int = CLAUDE_RETRY_ATTEMPTS,
    backoff_s: float = CLAUDE_RETRY_BACKOFF_S,
) -> tuple[int, str, str]:
    """Executa `claude -p` com retry em caso de falha. Devolve (código, stdout, stderr)."""
    cmd: list[str] = [
        claude_bin,
        "-p",
        prompt,
        "--output-format",
        "text",
    ]
    if extra_args:
        cmd.extend(extra_args)

    last_code, last_out, last_err = 1, "", ""
    attempts = max(1, retry_attempts + 1)
    for i in range(attempts):
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=3600,
            env=os.environ.copy(),
            check=False,
        )
        last_code = proc.returncode
        last_out = proc.stdout or ""
        last_err = proc.stderr or ""
        if last_code == 0 and last_out.strip():
            return last_code, last_out, last_err
        if i < attempts - 1:
            info(
                f"Claude devolveu código {last_code}; a tentar de novo em {backoff_s:.0f}s "
                f"(tentativa {i + 2}/{attempts})."
            )
            time.sleep(backoff_s)
            backoff_s *= 2
    return last_code, last_out, last_err


def resolve_claude_bin(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    return shutil.which("claude")


def parse_extra_args(cli_string: str | None) -> list[str]:
    """Argumentos extra para o `claude`. Default vazio — `--effort` não existe no Claude Code CLI."""
    raw = (cli_string or "").strip()
    if not raw:
        raw = os.environ.get("YOUTUBE_MINISTRACAO_CLAUDE_ARGS", "").strip()
    if not raw:
        return []
    return shlex.split(raw)


def _fetched_to_plain(
    transcript: FetchedTranscript, *, include_timestamps: bool
) -> tuple[str, list[dict[str, Any]]]:
    segs = [asdict(s) for s in transcript.snippets]
    plain = segments_to_plain_text(segs, include_timestamps=include_timestamps)
    return plain, segs


def _write_stderr_log(out_dir: Path, stderr: str, label: str) -> Path | None:
    if not stderr.strip():
        return None
    log_path = out_dir / "_claude_stderr.log"
    existing = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    log_path.write_text(
        existing + f"\n--- {label} ---\n{stderr.strip()}\n", encoding="utf-8"
    )
    return log_path


def segmentar_com_claude(
    transcript: FetchedTranscript,
    *,
    out_dir: Path,
    video_id: str,
    claude_bin: str,
    extra_args: Sequence[str],
    force: bool,
) -> Segmentacao:
    """Chama Claude #1 para segmentar o culto. Reusa cache se existir (a menos que force)."""
    if not force:
        cached = carregar_segmentacao_cache(out_dir)
        if cached and cached.blocos:
            info("Segmentação reutilizada de transcricao_segmentada.json (cache).")
            return cached

    plain_with_ts, segments = _fetched_to_plain(transcript, include_timestamps=True)
    prompt = build_segmentation_prompt(plain_with_ts)
    code, out, err = run_claude_print(
        prompt, claude_bin=claude_bin, extra_args=extra_args, cwd=out_dir
    )
    _write_stderr_log(out_dir, err, "segmentacao")
    if code != 0:
        warn(f"Claude (segmentação) código {code}; a tentar extrair JSON parcial.")
    seg = parse_segmentation_response(out)
    if not seg.blocos:
        warn("Segmentação vazia — o pipeline continua com a transcrição completa.")
    texto_ministracao = extrair_ministracao(seg, segments, include_timestamps=False)
    gravar_artefactos(out_dir, seg, video_id, texto_ministracao)
    return seg


def _resumo_paths(out_dir: Path) -> Path:
    return out_dir / "resumo_ministracao.md"


def run_ministracao_workflow(
    url_or_id: str,
    *,
    out_dir: Path,
    languages: list[str],
    include_timestamps: bool,
    max_chars: int,
    cookie_path: str | None,
    proxy_http: str | None,
    proxy_https: str | None,
    skip_claude: bool,
    skip_segment: bool = False,
    force: bool = False,
    claude_bin: str | None,
    claude_extra: str | None,
    missing_claude_ok: bool = False,
    show_progress: bool = False,
) -> dict[str, Any]:
    """
    Pipeline da ministração (passos 2 → 4 na fase geral de 8 fases):

    - [2/8] legendas → `<video_id>.json`
    - [3/8] (opcional) segmentação do culto com Claude → `transcricao_segmentada.{json,md}` + `ministracao_texto.txt`
    - [4/8] resumo da ministração com Claude → `resumo_ministracao.md`
    """
    video_id = extract_video_id(url_or_id)
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    http_client = session_with_netscape_cookies(cookie_path) if cookie_path else None
    proxy_config = proxy_from_urls(proxy_http, proxy_https)

    if show_progress:
        phase(2, TOTAL_PHASES, "A extrair legendas do YouTube…")

    json_path = out_dir / f"{video_id}.json"
    if json_path.is_file() and not force:
        info("Transcrição já presente — a reutilizar.")
        transcript = None  # será lida do JSON se necessário
    else:
        transcript = fetch_transcript(
            video_id, languages, proxy_config=proxy_config, http_client=http_client
        )
        write_json_file(transcript, json_path)

    if transcript is None:
        transcript = fetch_transcript(
            video_id, languages, proxy_config=proxy_config, http_client=http_client
        )
        write_json_file(transcript, json_path)

    full_plain, segments = _fetched_to_plain(transcript, include_timestamps=include_timestamps)

    result: dict[str, Any] = {
        "video_id": video_id,
        "json": json_path,
        "prompt": None,
        "claude_stdout": None,
        "claude_stderr": None,
        "claude_code": None,
        "resumo": None,
        "segmentacao": None,
        "ministracao_texto": None,
        "claude_skip_reason": None,
    }

    bin_path = resolve_claude_bin(claude_bin)
    if skip_claude:
        if show_progress:
            phase(3, TOTAL_PHASES, "A saltar segmentação Claude (--skip-claude).")
            phase(4, TOTAL_PHASES, "A saltar resumo Claude (--skip-claude).")
        result["claude_skip_reason"] = "user_skip"
        _write_fallback_prompt(out_dir, video_id, full_plain, max_chars, segmentado=False)
        return result

    if not bin_path:
        if show_progress:
            phase(3, TOTAL_PHASES, "Claude CLI não encontrado — a saltar segmentação.")
            phase(4, TOTAL_PHASES, "Claude CLI não encontrado — a saltar resumo.")
        if not missing_claude_ok:
            raise RuntimeError(
                "Comando `claude` não encontrado no PATH. "
                "Instala o Claude Code CLI ou usa --skip-claude."
            )
        result["claude_skip_reason"] = "binary_missing"
        result["claude_stderr"] = "Comando `claude` não encontrado no PATH."
        _write_fallback_prompt(out_dir, video_id, full_plain, max_chars, segmentado=False)
        return result

    extra = parse_extra_args(claude_extra)

    seg: Segmentacao | None = None
    if not skip_segment:
        if show_progress:
            phase(3, TOTAL_PHASES, "A segmentar o culto com Claude…")
        seg = segmentar_com_claude(
            transcript,
            out_dir=out_dir,
            video_id=video_id,
            claude_bin=bin_path,
            extra_args=extra,
            force=force,
        )
        result["segmentacao"] = seg
    else:
        if show_progress:
            phase(3, TOTAL_PHASES, "Segmentação saltada (--skip-segment).")

    if seg and seg.blocos:
        texto_ministracao = extrair_ministracao(seg, segments, include_timestamps=False)
    else:
        texto_ministracao = ""

    if texto_ministracao.strip():
        result["ministracao_texto"] = out_dir / "ministracao_texto.txt"
        base_text, was_truncated = truncate_text(texto_ministracao, max_chars)
        contexto = contexto_outros_blocos(seg) if seg else ""
        prompt = build_ministracao_prompt(base_text, segmentado=True, contexto=contexto)
        info(
            f"Resumo vai usar {len(base_text):,} caracteres do bloco de ministração"
            + (" (truncado)" if was_truncated else "")
            + "."
        )
    else:
        if seg and seg.blocos:
            warn("Segmentação existe mas não identificou bloco de ministração; uso transcrição completa.")
        base_text, was_truncated = truncate_text(full_plain, max_chars)
        prompt = build_ministracao_prompt(base_text, segmentado=False, contexto="")

    prompt_path = out_dir / "ministracao_prompt.md"
    meta = (
        f"<!-- video_id: {video_id} | segmentado: "
        f"{bool(seg and seg.encontrar_ministracao())} | truncated: {was_truncated} "
        f"| max_chars: {max_chars} -->\n\n"
    )
    prompt_path.write_text(meta + prompt, encoding="utf-8")
    result["prompt"] = prompt_path

    resumo_path = _resumo_paths(out_dir)
    if resumo_path.is_file() and not force:
        info("Resumo já existe — a reutilizar.")
        result["resumo"] = resumo_path
        return result

    if show_progress:
        phase(4, TOTAL_PHASES, "A gerar resumo da ministração com Claude…")

    code, out, err = run_claude_print(
        prompt, claude_bin=bin_path, extra_args=extra, cwd=out_dir
    )
    result["claude_code"] = code
    result["claude_stdout"] = out
    result["claude_stderr"] = err
    _write_stderr_log(out_dir, err, "resumo")

    body = out.strip() or "(sem saída do Claude — ver _claude_stderr.log)"
    parts: list[str] = [meta, f"# Resumo da ministração — {video_id}\n\n"]
    if was_truncated:
        parts.append("_Aviso: transcrição truncada._\n\n")
    if code != 0:
        parts.append(f"> **Claude CLI** terminou com código `{code}`.\n\n")
    parts.append(body)
    parts.append("\n")
    resumo_path.write_text("".join(parts), encoding="utf-8")
    result["resumo"] = resumo_path
    return result


def _write_fallback_prompt(
    out_dir: Path, video_id: str, plain_text: str, max_chars: int, *, segmentado: bool
) -> None:
    """Grava o prompt mesmo sem Claude (útil para copiar para Cursor/Console)."""
    base, was_truncated = truncate_text(plain_text, max_chars)
    prompt = build_ministracao_prompt(base, segmentado=segmentado, contexto="")
    meta = (
        f"<!-- video_id: {video_id} | segmentado: {segmentado} "
        f"| truncated: {was_truncated} | max_chars: {max_chars} -->\n\n"
    )
    (out_dir / "ministracao_prompt.md").write_text(meta + prompt, encoding="utf-8")
