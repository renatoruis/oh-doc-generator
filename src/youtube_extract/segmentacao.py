"""Segmentação do culto com Claude antes da sumarização.

Recebe a transcrição completa (com timestamps) e devolve um JSON estruturado
identificando cada bloco do culto (abertura, louvor, avisos, ofertas, ministração…).
Extrai o bloco de ministração para ser sumarizado à parte — resumo mais assertivo.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

_TIPOS_PERMITIDOS = {
    "abertura",
    "louvor",
    "testemunho",
    "leitura_biblica",
    "avisos",
    "ofertas",
    "oracao",
    "ministracao",
    "ministracao_final",
    "ministracao_profetica",
    "ministerio_infantil",
    "encerramento",
    "outro",
}

_TIPOS_MINISTRACAO = {"ministracao", "ministracao_final", "ministracao_profetica"}


@dataclass
class Bloco:
    tipo: str
    inicio_s: float
    fim_s: float
    titulo: str = ""
    resumo_curto: str = ""
    cancoes: list[str] = field(default_factory=list)

    @property
    def inicio_label(self) -> str:
        return _segundos_para_label(self.inicio_s)

    @property
    def fim_label(self) -> str:
        return _segundos_para_label(self.fim_s)

    @property
    def duracao_min(self) -> int:
        return max(0, int((self.fim_s - self.inicio_s) // 60))


@dataclass
class Segmentacao:
    blocos: list[Bloco]
    notas: str = ""
    raw_json: str = ""

    def encontrar_ministracao(self) -> list[Bloco]:
        return [b for b in self.blocos if b.tipo in _TIPOS_MINISTRACAO]


def _segundos_para_label(s: float) -> str:
    s = max(0, int(s))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _label_para_segundos(label: str) -> float:
    """Converte 'HH:MM:SS' ou 'MM:SS' em segundos."""
    parts = [int(x) for x in re.split(r"[:.]", label.strip()) if x]
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h, m, s = 0, parts[0], parts[1]
    elif len(parts) == 1:
        return float(parts[0])
    else:
        return 0.0
    return float(h * 3600 + m * 60 + s)


def _templates_dir() -> Path:
    return Path(__file__).resolve().parent / "templates"


def build_segmentation_prompt(transcript_with_timestamps: str) -> str:
    env = Environment(
        loader=FileSystemLoader(str(_templates_dir() / "prompts")),
        autoescape=False,
        keep_trailing_newline=True,
    )
    tpl = env.get_template("segmentacao.md.j2")
    rendered = tpl.render(transcript="__TRANSCRIPT__")
    return rendered.replace("__TRANSCRIPT__", transcript_with_timestamps)


def _extract_json_block(text: str) -> str:
    """
    Extrai o primeiro bloco JSON balanceado do texto.
    Tolera cercas markdown e preâmbulo.
    """
    if not text:
        return ""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if m:
        return m.group(1)
    start = text.find("{")
    if start == -1:
        return ""
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return ""


def parse_segmentation_response(raw: str) -> Segmentacao:
    """Converte o output do Claude em `Segmentacao`. Nunca lança — devolve vazia se falhar."""
    if not raw or not raw.strip():
        return Segmentacao(blocos=[], notas="(sem resposta do modelo)", raw_json="")

    js = _extract_json_block(raw) or raw.strip()
    try:
        data = json.loads(js)
    except json.JSONDecodeError:
        return Segmentacao(blocos=[], notas="(JSON inválido do modelo)", raw_json=raw)

    blocos_raw = data.get("blocos") or []
    if not isinstance(blocos_raw, list):
        return Segmentacao(blocos=[], notas="(campo 'blocos' ausente)", raw_json=raw)

    blocos: list[Bloco] = []
    for item in blocos_raw:
        if not isinstance(item, dict):
            continue
        tipo = str(item.get("tipo") or "outro").strip().lower()
        if tipo not in _TIPOS_PERMITIDOS:
            tipo = "outro"
        inicio = _label_para_segundos(str(item.get("inicio") or "00:00:00"))
        fim = _label_para_segundos(str(item.get("fim") or str(inicio)))
        cancoes_raw = item.get("cancoes") or []
        if not isinstance(cancoes_raw, list):
            cancoes_raw = []
        blocos.append(
            Bloco(
                tipo=tipo,
                inicio_s=inicio,
                fim_s=fim,
                titulo=str(item.get("titulo") or "").strip(),
                resumo_curto=str(item.get("resumo_curto") or "").strip(),
                cancoes=[str(c).strip() for c in cancoes_raw if str(c).strip()],
            )
        )
    notas = str(data.get("notas") or "").strip()
    return Segmentacao(blocos=blocos, notas=notas, raw_json=raw)


def extrair_ministracao(
    segmentacao: Segmentacao,
    segments: Sequence[dict[str, Any]],
    *,
    include_timestamps: bool = False,
) -> str:
    """Concatena o texto dos segmentos cujo tempo cai nos blocos `ministracao*`."""
    blocos_min = segmentacao.encontrar_ministracao()
    if not blocos_min:
        return ""
    pedacos: list[str] = []
    for seg in segments:
        start = float(seg.get("start", 0))
        for b in blocos_min:
            if b.inicio_s <= start <= b.fim_s:
                text = (seg.get("text") or "").strip()
                if not text:
                    break
                if include_timestamps:
                    mm = int(start // 60)
                    ss = int(start % 60)
                    pedacos.append(f"[{mm:02d}:{ss:02d}] {text}")
                else:
                    pedacos.append(text)
                break
    return "\n".join(pedacos)


def render_segmentacao_md(seg: Segmentacao, video_id: str) -> str:
    """Tabela legível pelo pastor com o mapa do culto."""
    lines: list[str] = [
        f"# Mapa do culto — {video_id}",
        "",
        "| Início | Fim | Duração | Tipo | Título | Notas |",
        "|-------:|----:|--------:|:-----|:-------|:------|",
    ]
    for b in seg.blocos:
        titulo = b.titulo or "—"
        notas = b.resumo_curto or ""
        if b.cancoes:
            notas = (notas + (" · " if notas else "")) + "Cânticos: " + ", ".join(b.cancoes)
        notas = notas.replace("|", "\\|")
        titulo = titulo.replace("|", "\\|")
        lines.append(
            f"| {b.inicio_label} | {b.fim_label} | {b.duracao_min} min | "
            f"`{b.tipo}` | {titulo} | {notas} |"
        )
    if seg.notas:
        lines.extend(["", "## Notas do modelo", "", seg.notas.strip(), ""])
    return "\n".join(lines) + "\n"


def contexto_outros_blocos(seg: Segmentacao) -> str:
    """Texto curto com os outros blocos (para contexto no prompt da ministração)."""
    linhas: list[str] = []
    for b in seg.blocos:
        if b.tipo in _TIPOS_MINISTRACAO:
            continue
        resumo = b.resumo_curto or b.titulo or "—"
        linhas.append(
            f"- [{b.inicio_label}–{b.fim_label}] **{b.tipo}**: {resumo}"
        )
    return "\n".join(linhas)


def gravar_artefactos(
    out_dir: Path,
    seg: Segmentacao,
    video_id: str,
    ministracao_texto: str,
) -> dict[str, Path]:
    """Escreve `transcricao_segmentada.json/.md` + `ministracao_texto.txt` (se existir)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    json_path = out_dir / "transcricao_segmentada.json"
    payload = {
        "video_id": video_id,
        "blocos": [
            {
                "tipo": b.tipo,
                "inicio": b.inicio_label,
                "fim": b.fim_label,
                "inicio_s": b.inicio_s,
                "fim_s": b.fim_s,
                "duracao_min": b.duracao_min,
                "titulo": b.titulo,
                "resumo_curto": b.resumo_curto,
                "cancoes": b.cancoes,
            }
            for b in seg.blocos
        ],
        "notas": seg.notas,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["json"] = json_path

    md_path = out_dir / "transcricao_segmentada.md"
    md_path.write_text(render_segmentacao_md(seg, video_id), encoding="utf-8")
    paths["md"] = md_path

    if ministracao_texto.strip():
        txt = out_dir / "ministracao_texto.txt"
        txt.write_text(ministracao_texto, encoding="utf-8")
        paths["ministracao_txt"] = txt

    return paths


def carregar_segmentacao_cache(out_dir: Path) -> Segmentacao | None:
    """Se já existir `transcricao_segmentada.json`, reconstrói a Segmentacao (idempotência)."""
    p = out_dir / "transcricao_segmentada.json"
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    blocos: list[Bloco] = []
    for item in data.get("blocos", []) or []:
        blocos.append(
            Bloco(
                tipo=str(item.get("tipo") or "outro"),
                inicio_s=float(item.get("inicio_s") or 0),
                fim_s=float(item.get("fim_s") or 0),
                titulo=str(item.get("titulo") or ""),
                resumo_curto=str(item.get("resumo_curto") or ""),
                cancoes=list(item.get("cancoes") or []),
            )
        )
    return Segmentacao(blocos=blocos, notas=str(data.get("notas") or ""))
