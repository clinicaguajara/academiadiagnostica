# utils/normalize.py

# =========================================
# Necessary imports
# =========================================

from __future__ import annotations

import unicodedata

# =========================================
# Normalization
# =========================================

def strip_accents(text: str) -> str:
    """
    Remove diacritical marks (accents) from a string.

    This is useful for accent-insensitive comparisons. Example:
        "Comunicação" -> "Comunicacao"
    """
    s = str(text or "")
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", s)
        if unicodedata.category(ch) != "Mn"
    )

def collapse_whitespace(text: str) -> str:
    """
    Normalize whitespace by trimming and collapsing consecutive spaces/newlines.

    Example:
        "  hello\\n   world " -> "hello world"
    """
    return " ".join(str(text or "").strip().split())

def norm_key(text: str) -> str:
    """
    Build a stable, comparison-friendly key from a string.

    Operations:
    - Convert to string (safe for None)
    - Trim and collapse whitespace
    - Lowercase
    - Remove accents

    This is intended for matching user input / labels against internal keys.
    """
    s = collapse_whitespace(text).lower()
    return strip_accents(s)

def humanize_folder(folder: str) -> str:
    """
    Convert internal category folder names into human-friendly labels for the UI.

    Unknown names fall back to a simple capitalization.
    """
    mapping = {
        "personality": "Personalidade",
        "development": "Desenvolvimento",
        # Backward-compatibility (old category name)
        "autism": "Desenvolvimento",
        "scale": "Escalas",
        "scales": "Escalas",
        "raiz": "Raiz",
    }
    key = norm_key(folder)
    return mapping.get(key, str(folder or "").capitalize())

def slugify(text: str) -> str:
    """
    Convert an arbitrary string into a stable, ASCII-ish slug.

    Operations:
    - Remove accents
    - Trim/collapse whitespace
    - Replace non-alphanumeric characters with underscores
    - Collapse consecutive underscores and lowercase

    Example:
        "Faceta: Ansiedade Geral" -> "faceta_ansiedade_geral"
    """
    s = strip_accents(collapse_whitespace(text))
    s = "".join(ch if ch.isalnum() else "_" for ch in s)
    s = "_".join([t for t in s.split("_") if t])
    return s.lower()
