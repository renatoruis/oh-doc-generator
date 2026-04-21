"""Smoke tests para extractors e utilitários gerais."""

from __future__ import annotations

import pytest

from youtube_extract.client_pipeline import is_client_delivery_argv, looks_like_url_or_id
from youtube_extract.video_id import extract_video_id
from youtube_extract.youtube_metadata import format_cult_date_pt


@pytest.mark.parametrize(
    "token, expected",
    [
        ("https://www.youtube.com/watch?v=abcdefghijk", "abcdefghijk"),
        ("abcdefghijk", "abcdefghijk"),
        ("https://youtu.be/6x1v9jEZGPk", "6x1v9jEZGPk"),
        ("https://www.youtube.com/live/6x1v9jEZGPk?feature=share", "6x1v9jEZGPk"),
    ],
)
def test_extract_video_id(token: str, expected: str) -> None:
    assert extract_video_id(token) == expected


def test_format_cult_date_pt() -> None:
    assert format_cult_date_pt("20251102") == "2 de novembro de 2025"
    assert format_cult_date_pt("19991231") == "31 de dezembro de 1999"
    assert format_cult_date_pt(None) is None
    assert format_cult_date_pt("invalid") is None
    assert format_cult_date_pt("20251301") is None


def test_is_client_delivery_argv() -> None:
    assert is_client_delivery_argv(["https://youtu.be/6x1v9jEZGPk"])
    assert is_client_delivery_argv(["6x1v9jEZGPk", "-o", "entrega"])
    assert not is_client_delivery_argv([])
    assert not is_client_delivery_argv(["extract", "6x1v9jEZGPk"])
    assert not is_client_delivery_argv(["--help"])
    assert not is_client_delivery_argv(["help"])


def test_looks_like_url_or_id() -> None:
    assert looks_like_url_or_id("abcdefghijk")
    assert looks_like_url_or_id("https://youtu.be/abc")
    assert not looks_like_url_or_id("extract")
    assert not looks_like_url_or_id("--help")
