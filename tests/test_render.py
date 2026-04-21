"""Render smoke test: template gera HTML PT e EN com paginação e sem mapa do culto."""

from __future__ import annotations

from youtube_extract.pdf_export import parse_resumo, render_html_str

RESUMO_MIN = """<!-- BEGIN CONTENT -->
## Português (Portugal)

**Tema:** Teste.

### Open Groups — perguntas para discussão
1. Primeira pergunta em português?
2. Segunda pergunta em português?
3. Terceira pergunta em português?

## English

**Theme:** Test.

### Open Groups — discussion questions
1. First question in English?
2. Second question in English?
3. Third question in English?
<!-- END CONTENT -->
"""


def _render(lang: str) -> str:
    parsed = parse_resumo(RESUMO_MIN)
    return render_html_str(
        lang=lang,
        metadata={"title": "Culto teste", "cult_date_label_pt": "1 de janeiro de 2026"},
        parsed=parsed,
        video_id="testid12345",
        source_url="https://example.com/watch?v=testid12345",
    )


def test_render_produz_pt_e_en_com_4_paginas() -> None:
    pt_text = _render("pt")
    en_text = _render("en")

    # Conteúdo específico por idioma
    assert "Guia Open Groups" in pt_text
    assert "Open Groups Guide" in en_text
    assert "Primeira pergunta em português?" in pt_text
    assert "First question in English?" in en_text

    # 4 páginas (capa + como usar + resumo + perguntas)
    assert pt_text.count('class="page') >= 4
    assert en_text.count('class="page') >= 4

    # Mapa do culto removido
    assert "Mapa do culto" not in pt_text
    assert "Service map" not in en_text
    assert "cult_map" not in pt_text

    # Linhas tracejadas removidas
    assert 'class="lines"' not in pt_text
    assert 'class="line"' not in pt_text
    assert 'class="checkbox"' not in pt_text

    # Sem canal
    assert "Riverside" not in pt_text
    assert "Riverside" not in en_text
