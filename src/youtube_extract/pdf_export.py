"""Gera PDF do guia Open Groups (identidade Open Heavens).

Gera **dois PDFs** (PT + EN) com a mesma estrutura visual, cada um numa só língua.
O HTML é usado apenas como formato intermediário para o WeasyPrint — nunca é escrito em disco.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from youtube_extract.brand import open_heavens as brand

# Mapeamento de nomes de livros bíblicos → abreviação YouVersion (NVI-PT, translation 1608)
_BIBLE_BOOKS = {
    r"Génesis|Genesis|Gn": "GEN",
    r"Êxodo|Exodo|Ex": "EXO",
    r"Levítico|Levitico|Lv": "LEV",
    r"Números|Numeros|Nm": "NUM",
    r"Deuteronómio|Deuteronomio|Dt": "DEU",
    r"Josué|Josue|Js": "JOS",
    r"Juízes|Juizes|Jz": "JDG",
    r"Rute|Rt": "RUT",
    r"1\s*Samuel|1\s*Sm": "1SA",
    r"2\s*Samuel|2\s*Sm": "2SA",
    r"1\s*Reis|1\s*Rs": "1KI",
    r"2\s*Reis|2\s*Rs": "2KI",
    r"1\s*Crónicas|1\s*Cronicas|1\s*Cr": "1CH",
    r"2\s*Crónicas|2\s*Cronicas|2\s*Cr": "2CH",
    r"Esdras|Ed": "EZR",
    r"Neemias|Ne": "NEH",
    r"Ester|Et": "EST",
    r"Job|Jó": "JOB",
    r"Salmos|Salmo|Sl": "PSA",
    r"Provérbios|Proverbios|Pv|Pr": "PRO",
    r"Eclesiastes|Ec": "ECC",
    r"Cânticos|Canticos|Ct": "SNG",
    r"Isaías|Isaias|Is": "ISA",
    r"Jeremias|Jr": "JER",
    r"Lamentações|Lamentacoes|Lm": "LAM",
    r"Ezequiel|Ez": "EZK",
    r"Daniel|Dn": "DAN",
    r"Oseias|Os": "HOS",
    r"Joel|Jl": "JOL",
    r"Amós|Amos|Am": "AMO",
    r"Obadias|Ob": "OBA",
    r"Jonas|Jn": "JON",
    r"Miqueias|Mq": "MIC",
    r"Naum|Na": "NAM",
    r"Habacuque|Hc": "HAB",
    r"Sofonias|Sf": "ZEP",
    r"Ageu|Ag": "HAG",
    r"Zacarias|Zc": "ZEC",
    r"Malaquias|Ml": "MAL",
    r"Mateus|Mt": "MAT",
    r"Marcos|Mc": "MRK",
    r"Lucas|Lc": "LUK",
    r"João|Joao|Jo": "JHN",
    r"Atos|At": "ACT",
    r"Romanos|Rm": "ROM",
    r"1\s*Coríntios|1\s*Corintios|1\s*Co": "1CO",
    r"2\s*Coríntios|2\s*Corintios|2\s*Co": "2CO",
    r"Gálatas|Galatas|Gl": "GAL",
    r"Efésios|Efesios|Ef": "EPH",
    r"Filipenses|Fp": "PHP",
    r"Colossenses|Cl": "COL",
    r"1\s*Tessalonicenses|1\s*Ts": "1TH",
    r"2\s*Tessalonicenses|2\s*Ts": "2TH",
    r"1\s*Timóteo|1\s*Timoteo|1\s*Tm": "1TI",
    r"2\s*Timóteo|2\s*Timoteo|2\s*Tm": "2TI",
    r"Tito|Tt": "TIT",
    r"Filémon|Filemon|Fm": "PHM",
    r"Hebreus|Hb": "HEB",
    r"Tiago|Tg": "JAS",
    r"1\s*Pedro|1\s*Pe": "1PE",
    r"2\s*Pedro|2\s*Pe": "2PE",
    r"1\s*João|1\s*Joao|1\s*Jo": "1JN",
    r"2\s*João|2\s*Joao|2\s*Jo": "2JN",
    r"3\s*João|3\s*Joao|3\s*Jo": "3JN",
    r"Judas|Jd": "JUD",
    r"Apocalipse|Ap": "REV",
}

MAX_PERGUNTAS = 3


# Strings de UI por idioma
_STRINGS = {
    "pt": {
        "badge": "Guia Open Groups",
        "lang_label": "Português",
        "kicker": "Estudo pós-culto para grupos nas casas",
        "cult_of": "Culto de",
        "video": "Vídeo",
        "how_to_use": "Como usar este guia",
        "sermon_summary": "Resumo da ministração",
        "discussion_heading": "Perguntas para discussão",
        "discussion_intro": "Escolhe 1 ou 2 destas 3 perguntas — vai fundo, dá espaço para cada pessoa partilhar.",
        "no_summary": "Resumo não disponível — corre o fluxo com Claude para o gerar.",
        "page": "pág.",
        "q_prefix": "Q",
        "q_label": "Pergunta",
        "footer_note": (
            "Documento gerado para estudo pós-culto e para os "
            "<strong>Open Groups</strong> da <strong>Open Heavens Church</strong>"
        ),
    },
    "en": {
        "badge": "Open Groups Guide",
        "lang_label": "English",
        "kicker": "After-service study for home groups",
        "cult_of": "Service of",
        "video": "Video",
        "how_to_use": "How to use this guide",
        "sermon_summary": "Sermon summary",
        "discussion_heading": "Discussion questions",
        "discussion_intro": "Pick 1 or 2 of these 3 questions — go deep, make room for each person to share.",
        "no_summary": "Summary not available — run the pipeline with Claude to generate it.",
        "page": "p.",
        "q_prefix": "Q",
        "q_label": "Question",
        "footer_note": (
            "Document prepared for after-service study and the "
            "<strong>Open Groups</strong> of <strong>Open Heavens Church</strong>"
        ),
    },
}


@dataclass
class ResumoParseado:
    pt_html: str = ""
    en_html: str = ""
    perguntas_pt: list[str] = None  # type: ignore[assignment]
    perguntas_en: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.perguntas_pt is None:
            self.perguntas_pt = []
        if self.perguntas_en is None:
            self.perguntas_en = []


# ────────────────────────────────────────── helpers ──────────────────────────────────────────


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _logos_dir() -> Path:
    return _repo_root() / "src" / "utils" / "logos"


def _read_svg_sanitized(path: Path, fill: str = "currentColor") -> str:
    """Lê um SVG e força uma cor **hardcoded** em cada path/shape.

    O WeasyPrint (via CairoSVG) **não aplica CSS externo** a elementos dentro de
    SVG inline. A única forma garantida de colorir é ter `fill="<cor>"` directamente
    em cada elemento desenhável. Passa `fill=` (ex. `#C0DF16`) para fixar a cor
    deste SVG para o contexto onde vai ser usado.
    """
    if not path.is_file():
        return ""
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        try:
            raw = path.read_text(encoding="latin-1")
        except OSError:
            return ""

    raw = re.sub(r"<\?xml[^>]+\?>\s*", "", raw)
    raw = re.sub(r"<defs[^>]*>.*?</defs>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"<style[^>]*>.*?</style>", "", raw, flags=re.DOTALL | re.IGNORECASE)

    raw = re.sub(r'\sclass="[^"]*"', "", raw)

    raw = re.sub(r'fill="[^"]*"', f'fill="{fill}"', raw)
    raw = re.sub(r'stroke="[^"]*"', f'stroke="{fill}"', raw)

    def _inject_fill(match: re.Match[str]) -> str:
        tag = match.group(0)
        if re.search(r'\sfill\s*=', tag):
            return tag
        if tag.endswith("/>"):
            return tag[:-2].rstrip() + f' fill="{fill}"/>'
        return tag[:-1].rstrip() + f' fill="{fill}">'

    raw = re.sub(
        r"<(?:path|circle|ellipse|rect|polygon|polyline)\b[^>]*?/?>",
        _inject_fill,
        raw,
        flags=re.IGNORECASE,
    )

    return raw


def _read_symbol_svg(fill: str = "currentColor") -> str:
    return _read_svg_sanitized(_logos_dir() / "symbol.svg", fill=fill)


def _read_logo_svg(fill: str = "currentColor") -> str:
    return _read_svg_sanitized(_logos_dir() / "logo.svg", fill=fill)


def _nohemi_faces_for_template() -> list[dict[str, Any]]:
    faces: list[dict[str, Any]] = []
    for name, style, weight in brand.nohemi_faces():
        path = brand.fonts_local_dir() / name
        faces.append({"uri": path.resolve().as_uri(), "style": style, "weight": weight})
    return faces


def _markdown_to_html(text: str) -> str:
    import markdown

    return markdown.markdown(text, extensions=["extra", "nl2br", "sane_lists"])


def _linkify_bible_refs(html: str) -> str:
    """Converte 'Mateus 10:41-42', '1 Samuel 2:30', 'Jo 3:16' em links YouVersion NVI-PT (1608)."""
    books_pattern = "|".join(_BIBLE_BOOKS.keys())
    regex = re.compile(
        r"\b(?P<book>" + books_pattern + r")\s*(?P<chap>\d+)(?::(?P<verse>\d+(?:[\-–]\d+)?))?",
        flags=re.IGNORECASE,
    )

    def _sub(m: re.Match[str]) -> str:
        book_text = m.group("book")
        chap = m.group("chap")
        verse = m.group("verse")
        code: str | None = None
        for pat, c in _BIBLE_BOOKS.items():
            if re.fullmatch(pat, book_text.strip(), flags=re.IGNORECASE):
                code = c
                break
        if not code:
            return m.group(0)
        ref = f"{code}.{chap}"
        if verse:
            first_verse = re.split(r"[\-–]", verse)[0]
            ref = f"{ref}.{first_verse}"
        href = f"https://www.bible.com/pt/bible/1608/{ref}"
        return f'<a href="{href}" target="_blank" rel="noopener">{m.group(0)}</a>'

    return regex.sub(_sub, html)


# ────────────────────────────────────────── parser do resumo ──────────────────────────────────────────


def _extract_between_markers(raw: str) -> str:
    m = re.search(
        r"<!--\s*BEGIN CONTENT\s*-->(.*?)<!--\s*END CONTENT\s*-->",
        raw,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    cleaned = re.sub(
        r"\n?---\s*\n+##\s+stderr.*$", "", raw, flags=re.DOTALL | re.IGNORECASE
    ).strip()
    cleaned = re.sub(r"^\s*<!--[^>]*-->\s*", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"^\s*#\s+Resumo da ministração[^\n]*\n+", "", cleaned)
    return cleaned.strip()


_LANG_PT_HEADINGS = (
    re.compile(r"^#{1,3}\s*Português.*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^#{1,3}\s*\(?PT(?:-PT)?\)?.*$", re.MULTILINE),
)
_LANG_EN_HEADINGS = (
    re.compile(r"^#{1,3}\s*English.*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^#{1,3}\s*\(?EN\)?.*$", re.MULTILINE),
)


def _split_pt_en(content: str) -> tuple[str, str]:
    pt_match = None
    for pat in _LANG_PT_HEADINGS:
        pt_match = pat.search(content)
        if pt_match:
            break
    en_match = None
    for pat in _LANG_EN_HEADINGS:
        en_match = pat.search(content)
        if en_match:
            break

    if not pt_match and not en_match:
        return content.strip(), ""
    if pt_match and en_match:
        pt_start = pt_match.end()
        en_start = en_match.start()
        if pt_match.start() < en_match.start():
            pt_body = content[pt_start:en_start]
            en_body = content[en_match.end():]
        else:
            en_body = content[en_match.end(): pt_match.start()]
            pt_body = content[pt_start:]
        return pt_body.strip(), en_body.strip()
    if pt_match:
        return content[pt_match.end():].strip(), ""
    return "", content[en_match.end():].strip()  # type: ignore[union-attr]


# Aceita 3 estilos de "heading" para a secção de perguntas:
#   ### Open Groups — perguntas para discussão
#   8. **Open Groups — perguntas para discussão**
#   **Open Groups — perguntas para discussão**
_HEADING_PREFIX = r"^(?:#{1,4}\s+|\d+\.\s*\*{0,2}|\*{2})\s*"

_PERGUNTAS_HEADING_PT = re.compile(
    _HEADING_PREFIX
    + r"(?:Open\s*Groups.*?(?:perguntas|discuss|discussão)|Perguntas.*?(?:Open\s*Groups|discuss|grupo))[^\n]*$",
    re.IGNORECASE | re.MULTILINE,
)
_PERGUNTAS_HEADING_EN = re.compile(
    _HEADING_PREFIX
    + r"(?:Open\s*Groups.*?(?:discussion|questions)|Discussion.*?questions)[^\n]*$",
    re.IGNORECASE | re.MULTILINE,
)
_LIMITACOES_HEADING_PT = re.compile(
    _HEADING_PREFIX + r"Limita[çc][õo]es[^\n]*$",
    re.IGNORECASE | re.MULTILINE,
)
_LIMITACOES_HEADING_EN = re.compile(
    _HEADING_PREFIX + r"Limitations?(?:\s+of\s+the\s+transcript)?[^\n]*$",
    re.IGNORECASE | re.MULTILINE,
)
# "Próximo heading" — apenas markdown headings (## ou ###). Itens numerados
# (1., 2., 3.) NÃO contam, porque dentro da secção de perguntas é normal ter
# uma lista numerada `1. ... 2. ... 3. ...`.
_NEXT_HEADING = re.compile(r"^#{1,4}\s+", re.MULTILINE)


def _remove_section(section: str, heading_regex: re.Pattern[str]) -> str:
    """Remove uma secção (heading + corpo até ao próximo heading)."""
    m = heading_regex.search(section)
    if not m:
        return section
    tail = section[m.end():]
    next_h = _NEXT_HEADING.search(tail)
    if next_h:
        after = tail[next_h.start():]
        return (section[: m.start()] + after).strip()
    return section[: m.start()].strip()


def _extract_questions(section: str, heading_regex: re.Pattern[str]) -> tuple[str, list[str]]:
    m = heading_regex.search(section)
    if not m:
        return section, []
    tail = section[m.end():]
    next_h = _NEXT_HEADING.search(tail)
    block = tail[: next_h.start()] if next_h else tail
    before = section[: m.start()]
    after_tail = tail[next_h.start():] if next_h else ""
    raw_lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    questions: list[str] = []
    for ln in raw_lines:
        stripped = re.sub(r"^[\-\*•]\s*\*{0,2}", "", ln)
        stripped = re.sub(r"^\d+[\.\)]\s*\*{0,2}", "", stripped)
        stripped = re.sub(r"\*{2}$", "", stripped)
        stripped = stripped.strip().rstrip("*").strip()
        if not stripped:
            continue
        if len(stripped) < 6:
            continue
        questions.append(stripped)
    return (before + after_tail).strip(), questions


def parse_resumo(raw: str) -> ResumoParseado:
    if not raw:
        return ResumoParseado()
    content = _extract_between_markers(raw)
    pt_md, en_md = _split_pt_en(content)

    pt_md, perguntas_pt = _extract_questions(pt_md, _PERGUNTAS_HEADING_PT)
    en_md, perguntas_en = _extract_questions(en_md, _PERGUNTAS_HEADING_EN)

    pt_md = _remove_section(pt_md, _LIMITACOES_HEADING_PT)
    en_md = _remove_section(en_md, _LIMITACOES_HEADING_EN)

    pt_html = _linkify_bible_refs(_markdown_to_html(pt_md)) if pt_md.strip() else ""
    en_html = _linkify_bible_refs(_markdown_to_html(en_md)) if en_md.strip() else ""

    perguntas_pt = perguntas_pt[:MAX_PERGUNTAS]
    perguntas_en = perguntas_en[:MAX_PERGUNTAS]

    return ResumoParseado(
        pt_html=pt_html,
        en_html=en_html,
        perguntas_pt=perguntas_pt,
        perguntas_en=perguntas_en,
    )


# ────────────────────────────────────────── render ──────────────────────────────────────────


def _load_como_usar(lang: str) -> str:
    tpl_dir = Path(__file__).resolve().parent / "templates"
    env = Environment(loader=FileSystemLoader(str(tpl_dir)), autoescape=False)
    try:
        tpl = env.get_template("como_usar.md.j2")
    except Exception:
        return ""
    md = tpl.render(
        open_groups_name=brand.OPEN_GROUPS_NAME,
        church_name=brand.CHURCH_NAME,
        lang=lang,
    )
    return _markdown_to_html(md)


def render_html_str(
    *,
    lang: str,
    metadata: dict[str, Any],
    parsed: ResumoParseado,
    video_id: str,
    source_url: str,
) -> str:
    """Render do guia num único idioma → string HTML (não escreve em disco).

    Usado como intermediário para o WeasyPrint gerar o PDF e também por testes.
    """
    tpl_dir = Path(__file__).resolve().parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(tpl_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("guia_open_groups.html.j2")

    title = metadata.get("title") or f"Culto — {video_id}"
    cult_date = metadata.get("cult_date_label_pt") or metadata.get("upload_date") or "—"
    live_note = ""
    if metadata.get("was_live") or metadata.get("live_status") == "was_live":
        live_note = "Gravação de transmissão em direto." if lang == "pt" else "Recording of a live stream."

    if lang == "en":
        resumo_html = parsed.en_html
        perguntas = parsed.perguntas_en
    else:
        resumo_html = parsed.pt_html
        perguntas = parsed.perguntas_pt

    return template.render(
        html_lang="en" if lang == "en" else "pt-PT",
        church_name=brand.CHURCH_NAME,
        church_city=brand.CHURCH_CITY,
        church_website=brand.CHURCH_WEBSITE,
        church_instagram=brand.CHURCH_INSTAGRAM,
        tagline=brand.CHURCH_TAGLINE,
        open_groups_name=brand.OPEN_GROUPS_NAME,
        colors=brand.COLORS,
        google_fonts_url=brand.GOOGLE_FONTS_URL,
        font_heading=brand.FONT_HEADING,
        font_body=brand.FONT_BODY,
        nohemi_faces=_nohemi_faces_for_template(),
        symbol_svg_lime=_read_symbol_svg(fill=brand.COLORS["lime"]),
        logo_svg_lime=_read_logo_svg(fill=brand.COLORS["lime"]),
        logo_svg_dark=_read_logo_svg(fill=brand.COLORS["obsidian"]),
        strings=_STRINGS[lang],
        title=title,
        cult_date_label=cult_date,
        source_url=source_url,
        video_id=video_id,
        live_note=live_note,
        como_usar_html=_load_como_usar(lang),
        resumo_html=resumo_html,
        perguntas=perguntas,
    )


def _render_single_pdf(
    out_dir: Path,
    *,
    lang: str,
    metadata: dict[str, Any],
    parsed: ResumoParseado,
    video_id: str,
    source_url: str,
) -> Path | None:
    """Render de um único idioma → `guia_open_groups_<lang>.pdf` (apenas PDF)."""
    html_str = render_html_str(
        lang=lang,
        metadata=metadata,
        parsed=parsed,
        video_id=video_id,
        source_url=source_url,
    )

    pdf_path = out_dir / f"guia_open_groups_{lang}.pdf"
    try:
        from weasyprint import HTML
    except Exception:
        return None

    try:
        HTML(string=html_str, base_url=str(out_dir)).write_pdf(str(pdf_path))
    except Exception:
        return None

    return pdf_path


def render_open_groups_files(
    out_dir: Path,
    *,
    metadata: dict[str, Any],
    resumo_md_path: Path | None,
    video_id: str,
    source_url: str,
    logo_path: Path | None = None,  # mantido por compatibilidade
) -> dict[str, Path | None]:
    """Escreve os guias PT **e** EN em PDF em `out_dir`.

    Devolve mapping ``{pdf_pt, pdf_en}``. O HTML é gerado em memória e nunca
    chega ao disco.
    """
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    raw = resumo_md_path.read_text(encoding="utf-8") if resumo_md_path and resumo_md_path.is_file() else ""
    parsed = parse_resumo(raw)

    result: dict[str, Path | None] = {}
    for lang in ("pt", "en"):
        result[f"pdf_{lang}"] = _render_single_pdf(
            out_dir,
            lang=lang,
            metadata=metadata,
            parsed=parsed,
            video_id=video_id,
            source_url=source_url,
        )

    # Remove ficheiros legados (single-file ou HTMLs antigos)
    for legacy in (
        "guia_open_groups.html",
        "guia_open_groups.pdf",
        "guia_open_groups_pt.html",
        "guia_open_groups_en.html",
    ):
        p = out_dir / legacy
        if p.exists():
            p.unlink()

    return result
