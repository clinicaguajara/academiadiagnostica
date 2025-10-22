# modules/scales_selector.py

# =========================================
# Necessary imports and utilities
# =========================================

import re
import json
import unicodedata
import streamlit as st

from pathlib              import Path
from typing               import Dict, List, Tuple, Optional
from collections          import defaultdict
from modules.scales_forms import ScaleConfig, render_scale_form

# =========================================
# Normalization
# =========================================

def _humanize_folder(name: str) -> str:
    """
    Converts a folder name (used internally to organize scales) into a
    human-readable label for display in the Streamlit UI.

    """
    # Manual dictionary that maps internal folder identifiers to their corresponding display names
    mapping = {
        "personality": "Personalidade",
        "autism": "Autismo",
        "scale": "Escalas",
        "scales": "Escalas",
        "raiz": "Raiz",
    }

    # Normalize the input name to lowercase, look it up in the mapping,
    # and return the friendly label. If not found, capitalize the name
    # (fallback behavior).
    return mapping.get(name.lower(), name.capitalize())

def _strip_accents(s: str) -> str:
    """
    Removes all accent marks (diacritics) from a given string.

    """

    # Normalize the string into its decomposed form (NFKD),
    # where characters like "é" become "e" + "´" (base + accent mark).
    # Then, remove all characters classified as nonspacing marks ("Mn"),
    # which correspond to diacritical marks such as accents and tildes.
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if unicodedata.category(c) != "Mn"
    )

def _normalize_key(s: str) -> str:
    """
    Normalizes a string key for consistent text comparison.

    Operations performed:
        1. Removes accent marks (via _strip_accents)
        2. Converts to lowercase
        3. Strips leading and trailing whitespace

    This ensures that different variations of a label (with accents, capitalization, or extra spaces)
    are treated as equivalent when matching category or scale names.
    """
    return _strip_accents(s).lower().strip()

def _resolve_category_key(user_cat: str, available: List[str]) -> Optional[str]:
    """
    Attempts to match the category name provided by the user (`user_cat`)
    with one of the available category keys (`available`).

    Matching rules:
        - Case-insensitive
        - Accent-insensitive
        - Accepts both internal names ("personality") and humanized names
          ("Personalidade", "Autismo", etc.)
        - Uses a predefined alias map to translate common labels

    Returns:
        The canonical category key (e.g., "personality") if a match is found,
        otherwise None.

    """
    # If the user did not provide a category, stop early.
    if not user_cat:
        return None

    # Normalize the input (remove accents, lowercase, trim spaces)
    norm_user = _normalize_key(user_cat)

    # 1) Direct alias mapping for known categories.
    #    This dictionary serves as a manual translation layer between
    #    Portuguese labels and internal folder names.
    aliases = {
        "personalidade": "personality",
        "personality": "personality",
        "autismo": "autism",
        "autism": "autism",
        "raiz": "Raiz",
    }

    # Check if the normalized user input matches a known alias,
    # and that alias exists in the list of available categories.
    if norm_user in aliases and aliases[norm_user] in available:
        return aliases[norm_user]

    # 2) Try a direct match against the available category keys
    #    (after normalizing both sides).
    norm_map = { _normalize_key(k): k for k in available }
    if norm_user in norm_map:
        return norm_map[norm_user]

    # 3) Try matching against the humanized (display) form of the categories.
    #    Example: user inputs "Autismo" → matches folder "autism".
    human_map = { _normalize_key(_humanize_folder(k)): k for k in available }
    if norm_user in human_map:
        return human_map[norm_user]

    # 4) No match found → return None.
    return None

# =========================================
# Data management
# =========================================

@st.cache_data(show_spinner=False)
def _discover_scales(scales_root: str | Path) -> Dict[str, List[Tuple[str, Path]]]:
    """
    Recursively scans the given root directory (`scales_root`) for JSON files
    that define psychological scales.

    It organizes all discovered files into categories based on their
    immediate subfolder name under the root directory.

    Returns:
        A dictionary of the following structure:
            {
                "personality": [("PID-5 – Full Version", Path("...")), ...],
                "autism": [("AQ – Adult", Path("...")), ...],
                "Raiz": [("General Scale", Path("...")), ...]
            }

    Notes:
        - Each JSON file represents a scale definition.
        - Category is determined by the first-level subfolder under `scales_root`.
        - Files directly under `scales_root` are grouped under the category "Raiz".
        - Each category’s list is sorted alphabetically by the label.
        - Uses Streamlit’s @st.cache_data decorator to cache results for performance.
    """
    
    # Convert the input to a Path object (handles both str and Path inputs)
    root = Path(scales_root)

    # Dictionary structure:
    # {
    #     "category": [ (label, path_to_json), ... ]
    # }
    found: Dict[str, List[Tuple[str, Path]]] = defaultdict(list)

    # Safety check: if the root directory does not exist, return an empty dict.
    if not root.exists():
        return {}

    # Recursively find all JSON files in the directory tree.
    for f in sorted(root.rglob("*.json")):
        # Try to compute the path of the file relative to the root folder.
        # If it fails (for example, due to different drives), use the full path.
        try:
            rel = f.relative_to(root)
        except Exception:
            rel = f

        # Break the relative path into parts to extract the first folder.
        parts = rel.parts
        # The first-level folder defines the category (e.g., 'personality', 'autism').
        # If the file is directly under the root, assign it to category "Raiz".
        categoria = parts[0] if len(parts) > 1 else "Raiz"

        # Default label = file name without extension.
        label = f.stem
        try:
            # Try to open and read the JSON file to extract a more descriptive label.
            with f.open("r", encoding="utf-8") as fh:
                data = json.load(fh)

            # Try to use the "name" or "titulo" field as the display label,
            # falling back to the file name if not available.
            label = str(data.get("name") or data.get("titulo") or f.stem)

            # Clean up extra spaces or line breaks in the label.
            label = re.sub(r"\s+", " ", label).strip()
        except Exception:
            # If the file cannot be read or parsed, keep the default filename label.
            pass

        # Append the label and file path to the corresponding category list.
        found[categoria].append((label, f))

    # Sort each category’s scales alphabetically by label (case-insensitive).
    for cat, arr in found.items():
        arr.sort(key=lambda t: t[0].lower())

    # Convert defaultdict back to a standard dict before returning.
    return dict(found)

# =========================================
# UI rendering
# =========================================

def render_scale_selector(
    scales_dir: str | Path,
    category: Optional[str] = None,
    strict: bool = False,
) -> None:
    """
    Se 'category' vier (ex.: 'personality' ou 'Personalidade'), não mostra seletor de categoria
    e lista apenas as escalas daquela categoria.
    strict=True → se a categoria não existir, não renderiza nada e exibe aviso.
    """
    scales_by_cat = _discover_scales(scales_dir)
    if not scales_by_cat:
        st.info("Nenhuma escala .json encontrada no diretório informado.")
        return

    # Modo “categoria travada” (hardcoded)
    if category:
        resolved = _resolve_category_key(category, list(scales_by_cat.keys()))
        if not resolved:
            if strict:
                st.warning(f"Categoria '{category}' não encontrada em {scales_dir}.")
                return
            # fallback: segue o fluxo antigo com seletor de categoria
        else:
            labels, lookup = [], {}
            for label, path in scales_by_cat.get(resolved, []):
                labels.append(label)
                lookup[label] = path

            st.subheader(f"Instrumentos")

            if not labels:
                st.warning("Nenhuma escala nesta categoria.")
                return

            # índice persistente por categoria resolvida
            per_cat_idx_key = f"_sf_scale_idx__{resolved}"
            scale_idx = st.session_state.get(per_cat_idx_key, 0)
            chosen = st.selectbox("Selecione", labels, index=min(scale_idx, len(labels)-1))
            st.session_state[per_cat_idx_key] = labels.index(chosen)

            cfg = ScaleConfig(
                page_size=30,
                allow_blank=True,
                blank_sentinel="__BLANK__",
                show_id_badge=True,
                test_prefill=False,
            )
            submitted, answers = render_scale_form(lookup[chosen], cfg=cfg)
            if submitted:
                key_data = "escalas_respondidas"
                key_names = "escalas_display_names"
                st.session_state.setdefault(key_data, {})
                st.session_state.setdefault(key_names, {})
                norm_key = chosen.strip().lower()
                st.session_state[key_data][norm_key] = answers
                st.session_state[key_names][norm_key] = chosen
                st.switch_page("pages/3_Resultados.py")
            return  # encerra aqui no modo travado

    # ---------- Fluxo antigo (sem categoria hardcoded) ----------
    only_root = (len(scales_by_cat) == 1 and "Raiz" in scales_by_cat)
    st.subheader("Selecione a escala")

    if only_root:
        labels, lookup = [], {}
        for label, path in scales_by_cat["Raiz"]:
            labels.append(label)
            lookup[label] = path
        chosen = st.selectbox("Escala", labels, index=0)

    else:
        categorias = sorted(scales_by_cat.keys(), key=lambda s: s.lower())
        prefer = ["personality", "autism"]
        categorias = sorted(
            categorias,
            key=lambda c: (prefer.index(c) if c in prefer else 99, c.lower())
        )
        cat_display = [_humanize_folder(c) for c in categorias]
        cat_idx = st.session_state.get("_sf_cat_idx", 0)
        cat_choice = st.selectbox("Categoria", cat_display, index=cat_idx)
        cat_key = categorias[cat_display.index(cat_choice)]
        st.session_state["_sf_cat_idx"] = categorias.index(cat_key)

        labels, lookup = [], {}
        for label, path in scales_by_cat[cat_key]:
            labels.append(label)
            lookup[label] = path

        if not labels:
            st.warning("Nenhuma escala nesta categoria.")
            return

        per_cat_idx_key = f"_sf_scale_idx__{cat_key}"
        scale_idx = st.session_state.get(per_cat_idx_key, 0)
        chosen = st.selectbox("Escala", labels, index=min(scale_idx, len(labels)-1))
        st.session_state[per_cat_idx_key] = labels.index(chosen)

    cfg = ScaleConfig(
        page_size=30,
        allow_blank=True,
        blank_sentinel="__BLANK__",
        show_id_badge=True,
        test_prefill=False,
    )
    submitted, answers = render_scale_form(lookup[chosen], cfg=cfg)
    if submitted:
        key_data = "escalas_respondidas"
        key_names = "escalas_display_names"
        st.session_state.setdefault(key_data, {})
        st.session_state.setdefault(key_names, {})
        norm_key = chosen.strip().lower()
        st.session_state[key_data][norm_key] = answers
        st.session_state[key_names][norm_key] = chosen
        st.switch_page("pages/3_Resultados.py")
