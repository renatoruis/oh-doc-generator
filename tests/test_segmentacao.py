"""Smoke tests do parser de segmentação."""

from __future__ import annotations

from youtube_extract.segmentacao import (
    Segmentacao,
    _extract_json_block,
    _label_para_segundos,
    _segundos_para_label,
    contexto_outros_blocos,
    extrair_ministracao,
    parse_segmentation_response,
    render_segmentacao_md,
)

RAW_JSON_OK = """
Claro, aqui está a segmentação:

```json
{
  "blocos": [
    {"tipo": "abertura", "inicio": "00:00:00", "fim": "00:04:00", "titulo": "Boas-vindas", "resumo_curto": "Saudação inicial."},
    {"tipo": "louvor", "inicio": "00:04:00", "fim": "00:25:00", "cancoes": ["Grande e Fiel", "Aleluia"]},
    {"tipo": "avisos", "inicio": "00:25:00", "fim": "00:28:00"},
    {"tipo": "ministracao", "inicio": "00:28:00", "fim": "01:28:00", "titulo": "Cultura de honra"},
    {"tipo": "encerramento", "inicio": "01:28:00", "fim": "01:32:00"}
  ],
  "notas": "Culto com áudio limpo."
}
```
"""


def test_parse_segmentation_response_ok() -> None:
    seg = parse_segmentation_response(RAW_JSON_OK)
    assert len(seg.blocos) == 5
    tipos = [b.tipo for b in seg.blocos]
    assert tipos == ["abertura", "louvor", "avisos", "ministracao", "encerramento"]
    min_blocos = seg.encontrar_ministracao()
    assert len(min_blocos) == 1
    assert min_blocos[0].titulo == "Cultura de honra"
    assert min_blocos[0].duracao_min == 60


def test_parse_segmentation_response_invalid() -> None:
    seg = parse_segmentation_response("não sei segmentar isto desculpa")
    assert seg.blocos == []
    assert "JSON" in seg.notas or seg.notas


def test_parse_segmentation_response_empty() -> None:
    seg = parse_segmentation_response("")
    assert isinstance(seg, Segmentacao)
    assert seg.blocos == []


def test_tipo_invalido_cai_em_outro() -> None:
    raw = '{"blocos": [{"tipo": "xpto", "inicio": "00:00:00", "fim": "00:01:00"}]}'
    seg = parse_segmentation_response(raw)
    assert seg.blocos[0].tipo == "outro"


def test_labels_tempo() -> None:
    assert _segundos_para_label(0) == "00:00:00"
    assert _segundos_para_label(65) == "00:01:05"
    assert _segundos_para_label(3700) == "01:01:40"
    assert _label_para_segundos("00:02:30") == 150
    assert _label_para_segundos("2:30") == 150
    assert _label_para_segundos("01:00:00") == 3600


def test_extrair_ministracao() -> None:
    seg = parse_segmentation_response(RAW_JSON_OK)
    segments = [
        {"start": 10, "text": "Bem-vindos"},
        {"start": 300, "text": "Cantemos"},
        {"start": 1700, "text": "Hoje vamos falar sobre honra"},
        {"start": 3600, "text": "Concluindo"},
        {"start": 5200, "text": "Boa semana"},
    ]
    texto = extrair_ministracao(seg, segments)
    assert "Hoje vamos falar sobre honra" in texto
    assert "Concluindo" in texto
    assert "Bem-vindos" not in texto
    assert "Cantemos" not in texto


def test_render_segmentacao_md() -> None:
    seg = parse_segmentation_response(RAW_JSON_OK)
    md = render_segmentacao_md(seg, "abc123")
    assert "Mapa do culto" in md
    assert "ministracao" in md
    assert "| 00:28:00 |" in md


def test_contexto_outros_blocos_exclui_ministracao() -> None:
    seg = parse_segmentation_response(RAW_JSON_OK)
    ctx = contexto_outros_blocos(seg)
    assert "abertura" in ctx
    assert "louvor" in ctx
    assert "ministracao" not in ctx


def test_extract_json_block_tolera_preambulo() -> None:
    raw = 'Aqui: {"a": 1, "b": {"c": [1,2,3]}} fim'
    out = _extract_json_block(raw)
    assert out == '{"a": 1, "b": {"c": [1,2,3]}}'
