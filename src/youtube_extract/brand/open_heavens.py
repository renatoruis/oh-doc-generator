"""Constantes da identidade visual Open Heavens (Manual de identidade)."""

from __future__ import annotations

from pathlib import Path

COLORS = {
    "obsidian": "#101820",
    "green": "#279F00",
    "cream": "#F2EBE7",
    "lime": "#C0DF16",
}

CHURCH_NAME = "Open Heavens Church"
CHURCH_CITY = "Coimbra, Portugal"
CHURCH_TAGLINE = "Céus abertos — vida de fé além do tradicional"
CHURCH_INSTAGRAM = "@openheavens.church"
CHURCH_WEBSITE = "openheavenschurch.pt"

# Tipografia: manual prescreve Nohemi (Pangram Pangram).
# Fallback público: Space Grotesk (Google Fonts) → Inter → system-ui.
FONT_HEADING = '"Nohemi", "Space Grotesk", "Inter", system-ui, sans-serif'
FONT_BODY = '"Inter", "Space Grotesk", system-ui, sans-serif'

GOOGLE_FONTS_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=Inter:wght@400;500;600;700&"
    "family=Space+Grotesk:wght@400;500;600;700&display=swap"
)

OPEN_GROUPS_NAME = "Open Groups"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


def fonts_local_dir() -> Path:
    """Diretório onde o utilizador coloca os .woff2 da Nohemi."""
    return _repo_root() / "src" / "utils" / "fonts" / "Nohemi"


def nohemi_faces() -> list[tuple[str, str, int]]:
    """
    Devolve lista (nome_ficheiro, style, weight) dos .woff2 Nohemi existentes.
    Vazia se nenhum estiver instalado — o template usa fallback.
    """
    d = fonts_local_dir()
    if not d.is_dir():
        return []
    wanted = [
        ("Nohemi-Regular.woff2", "normal", 400),
        ("Nohemi-Medium.woff2", "normal", 500),
        ("Nohemi-SemiBold.woff2", "normal", 600),
        ("Nohemi-Bold.woff2", "normal", 700),
    ]
    return [(name, style, weight) for (name, style, weight) in wanted if (d / name).is_file()]
