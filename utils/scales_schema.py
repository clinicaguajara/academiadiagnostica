# utils/scales_schema.py

# =========================================
# Necessary Imports
# =========================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# =========================================
# Data Models
# =========================================

@dataclass
class ScaleItem:
    """
    A single questionnaire item.

    Attributes
    ----------
    id:
        Item identifier, stored as a string to avoid losing formatting and to
        match how Streamlit session_state stores keys.
    text:
        Item prompt shown to the user.
    """

    id: str
    text: str

@dataclass
class ScaleData:
    """
    Normalized representation of a scale definition used by the UI layer.

    Attributes
    ----------
    name:
        Display name of the scale.
    answer_options:
        List of response labels. The UI expects a blank sentinel at position 0.
    items:
        List of normalized items.
    instruction_html:
        Optional instructions (plain text or HTML) to show above the form.
    traduction:
        Optional translation source/citation to show under the title.
    """

    name: str
    answer_options: List[str]
    items: List[ScaleItem]
    instruction_html: Optional[str] = None
    traduction: Optional[str] = None


# =========================================
# Psychometric Schemas
# =========================================

def scales_schema(obj: Dict[str, Any]) -> ScaleData:
    """
    Normalize heterogeneous raw scale data (loaded from JSON or dict) into a
    consistent internal representation (`ScaleData`).

    This function standardizes various possible input formats—accounting for
    different field names, value types, and data shapes—so that downstream
    components (UI rendering, validation, scoring) can work with a uniform schema.

    Parameters
    ----------
    obj:
        A raw dictionary describing a scale. It may come from different sources
        (e.g., user-defined JSON, localized formats, or legacy data), with fields
        named in Portuguese ("titulo", "itens") or English ("name", "items").

    Returns
    -------
    ScaleData
        A structured dataclass instance containing:
        - `name`: normalized title of the scale
        - `answer_options`: list of response labels with a blank sentinel prepended
        - `items`: standardized items with `id` and `text` fields
        - `instruction_html`: instructions in text or HTML format (optional)
    """
    # Scale name (fallback to "Escala")
    name = str(obj.get("name") or obj.get("titulo") or "Escala")

    # Response options → ensure a list of strings and fallback
    options = obj.get("answer_options") or []

    if isinstance(options, dict):
        # If provided as dict (e.g., {"Nunca": 0, "Às vezes": 1, ...}),
        # preserve the natural order of the keys
        options = list(options.keys())
    elif isinstance(options, (str, int, float)):
        options = [str(options)]
    else:
        options = [str(o) for o in options]

    # Guarantee the blank sentinel at the start (to allow "no answer" later)
    if options and options[0] != "__BLANK__":
        options = ["__BLANK__"] + options

    # Items: accept list of dicts or list of strings
    items_raw = obj.get("items") or obj.get("itens") or []
    items: List[ScaleItem] = []
    for idx, it in enumerate(items_raw, start=1):
        if isinstance(it, dict):
            it_id = str(it.get("id") or it.get("numero") or it.get("index") or idx)
            it_text = str(it.get("text") or it.get("texto") or it.get("label") or "")
        else:
            # String, number, etc. → becomes text; id = position
            it_id = str(idx)
            it_text = str(it)
        items.append(ScaleItem(id=it_id, text=it_text))

    instr = obj.get("instructions")
    instruction_html = str(instr) if instr is not None else None
    trad = (
        obj.get("traduction")
        or obj.get("translation")
        or obj.get("traducao")
        or obj.get("tradução")
    )
    traduction = str(trad).strip() if trad is not None else None

    return ScaleData(
        name=name,
        answer_options=list(options),
        items=items,
        instruction_html=instruction_html,
        traduction=traduction,
    )
