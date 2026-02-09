# modules/scales_selector.py

# =========================================
# Necessary imports
# =========================================

from __future__ import annotations

import streamlit as st

from pathlib               import Path
from typing                import Dict, List, Optional, Tuple
from modules.scales_forms  import ScaleConfig, render_scale_form
from utils.data_management import discover_scales
from utils.normalize       import humanize_folder, norm_key


# =========================================
# Helpers
# =========================================

def _resolve_category_key(user_cat: str, available: List[str]) -> Optional[str]:
    """
    Resolve a user-provided category label into an available category key.

    Matching rules:
    - Case-insensitive
    - Accent-insensitive
    - Whitespace-normalized
    - Accepts both internal keys ("development") and humanized labels ("Desenvolvimento")

    Parameters
    ----------
    user_cat:
        The category string provided by the caller/user.
    available:
        The list of available category keys discovered on disk.

    Returns
    -------
    The canonical category key (as present in `available`) or None if not found.
    """
    
    # Early exit on empty input
    if not user_cat:
        return None

    # Normalize user input
    norm_user = norm_key(user_cat)
    norm_map = {norm_key(k): k for k in available}

    # Common aliases
    aliases = {
        "personalidade": "personality",
        "personality": "personality",
        "desenvolvimento": "development",
        "development": "development",
        # Backward-compatibility (old category name)
        "autismo": "development",
        "autism": "development",
        "raiz": "raiz",
        "root": "raiz",
    }

    # Alias mapping
    if norm_user in aliases:
        aliased = aliases[norm_user]
        if aliased in norm_map:
            return norm_map[aliased]

    # Direct match against available keys
    if norm_user in norm_map:
        return norm_map[norm_user]

    # Match against humanized category labels
    human_map = {norm_key(humanize_folder(k)): k for k in available}
    if norm_user in human_map:
        return human_map[norm_user]

    return None


# =========================================
# Streamlit-cached wrapper
# =========================================

@st.cache_data(show_spinner=False)
def _discover_scales(scales_root: str | Path) -> Dict[str, List[Tuple[str, Path]]]:
    """
    Streamlit-cached wrapper around utils.data_management.discover_scales().
    """
    return discover_scales(scales_root)


# =========================================
# UI rendering
# =========================================

def render_scale_selector(
    scales_dir: str | Path,
    category: Optional[str] = None,
) -> None:
    """
    Render a scale selector and its form for a given category folder.

    Parameters
    ----------
    scales_dir:
        Root folder that contains category subfolders (e.g., "scales/").
    category:
        Category key or label (e.g., "development", "Desenvolvimento").
    """
    scales_by_cat = _discover_scales(scales_dir)

    if not scales_by_cat:
        st.info("Nenhuma escala .json encontrada no diretório informado.")
        return

    if not category:
        st.warning("Categoria obrigatória não informada para renderização da escala.")
        return

    resolved = _resolve_category_key(category, list(scales_by_cat.keys()))
    if not resolved:
        st.warning(f"Categoria '{category}' não encontrada em {scales_dir}.")
        return

    labels: List[str] = []
    lookup: Dict[str, Path] = {}
    for label, path in scales_by_cat.get(resolved, []):
        labels.append(label)
        lookup[label] = path

    st.subheader("Instrumentos")

    if not labels:
        st.warning("Nenhuma escala nesta categoria.")
        return

    per_cat_idx_key = f"_sf_scale_idx__{resolved}"
    scale_idx = st.session_state.get(per_cat_idx_key, 0)
    chosen = st.selectbox("Selecione", labels, index=min(scale_idx, len(labels) - 1))
    st.session_state[per_cat_idx_key] = labels.index(chosen)

    cfg = ScaleConfig(
        page_size=100,
        allow_blank=True,
        blank_sentinel="__BLANK__",
        show_id_badge=True,
        test_prefill=False,
    )

    submitted, answers = render_scale_form(lookup[chosen], cfg=cfg)
    if not submitted:
        return

    key_data = "escalas_respondidas"
    key_names = "escalas_display_names"
    st.session_state.setdefault(key_data, {})
    st.session_state.setdefault(key_names, {})
    norm_key_name = chosen.strip().lower()
    st.session_state[key_data][norm_key_name] = answers
    st.session_state[key_names][norm_key_name] = chosen
    st.switch_page("pages/3_Resultados.py")
