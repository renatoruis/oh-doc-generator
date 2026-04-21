"""Tests do parser do resumo_ministracao.md e dos helpers."""

from __future__ import annotations

from youtube_extract.pdf_export import MAX_PERGUNTAS, _linkify_bible_refs, parse_resumo

RESUMO = """<!-- video_id: abc -->

# Resumo da ministração — abc

<!-- BEGIN CONTENT -->

## Português (Portugal)

**Tema:** Cultura de honra.

**Resumo executivo:** uma frase curta.

### Pontos principais
- Ponto A
- Ponto B

### Referências bíblicas
- 1 Samuel 2:30
- Mateus 10:41-42

### Limitações da transcrição
Há ruído no início.

### Open Groups — perguntas para discussão
1. Como é que honras alguém esta semana?
2. Que pessoa te vem à cabeça?
3. Que gesto concreto vais ter?
4. Quarta pergunta extra que deve ser cortada.
5. Quinta pergunta que também deve ser cortada.

---

## English

**Theme:** Culture of honour.

### Limitations of the transcript
Some noise at the beginning.

### Open Groups — discussion questions
1. Who can you honour this week?
2. What gesture will you offer?
3. How does this challenge you?
4. Extra question that should be cut.

<!-- END CONTENT -->
"""


def test_parse_resumo_pt_en_cap_3_questoes() -> None:
    parsed = parse_resumo(RESUMO)
    assert "Cultura de honra" in parsed.pt_html
    assert "Culture of honour" in parsed.en_html
    assert len(parsed.perguntas_pt) == MAX_PERGUNTAS == 3
    assert len(parsed.perguntas_en) == MAX_PERGUNTAS == 3
    assert "Quarta pergunta extra" not in " ".join(parsed.perguntas_pt)
    assert "Extra question" not in " ".join(parsed.perguntas_en)


def test_parse_resumo_remove_limitacoes() -> None:
    parsed = parse_resumo(RESUMO)
    assert "Limita" not in parsed.pt_html
    assert "Limitations" not in parsed.en_html
    assert "ruído no início" not in parsed.pt_html
    assert "noise at the beginning" not in parsed.en_html


def test_linkify_bible_refs_pt() -> None:
    html = "<p>Leitura: 1 Samuel 2:30 e Mateus 10:41-42.</p>"
    out = _linkify_bible_refs(html)
    assert "bible.com/pt/bible/1608/1SA.2.30" in out
    assert "bible.com/pt/bible/1608/MAT.10.41" in out


def test_parse_resumo_sem_marcadores_ignora_stderr() -> None:
    legacy = """<!-- meta -->

## Português (Portugal)

Texto PT.

---

## stderr (Claude CLI)

NoSuchFileError: foo
"""
    parsed = parse_resumo(legacy)
    assert "Texto PT" in parsed.pt_html
    assert "NoSuchFileError" not in parsed.pt_html
