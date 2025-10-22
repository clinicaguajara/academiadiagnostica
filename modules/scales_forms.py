# modules/scales_forms.py

# =========================================
# Necessary imports and utilities
# =========================================

import json
import streamlit as st

from pathlib     import Path
from dataclasses import dataclass
from typing      import Any, Dict, List, Optional, Sequence, Tuple

from utils.global_variables  import SCROLL_FLAG
from streamlit_scroll_to_top import scroll_to_here


# =========================================
# Data models
# =========================================

@dataclass
class ScaleItem:
    id: str
    text: str

@dataclass
class ScaleData:
    name: str
    answer_options: List[str]
    items: List[ScaleItem]
    instruction_html: Optional[str] = None

@dataclass
class ScaleConfig:
    page_size: int = 30
    allow_blank: bool = True
    blank_sentinel: str = "__BLANK__"
    show_id_badge: bool = True
    test_prefill: bool = False # for development/demo
    form_instruction_html: Optional[str] = None

@dataclass
class ScaleKeys:
    slug: str
    page_key: str
    answers_key: str
    init_key: str
    signature_key: str

# =========================================
# Public API
# =========================================

def _inject_styles_once() -> None:
    key = "_styles_scales_forms"
    if not st.session_state.get(key):
        st.markdown("""
        <style>
        .item-badge{
            display:inline-block;
            background:#2196F3;
            color:#fff;
            border:1px solid #0b74d6;
            border-radius:10px;
            padding:2px 10px;
            font-weight:700;
            min-width:2.4rem;
            text-align:center;
        }
        .item-row{ display:flex; align-items:flex-start; gap:.6rem; margin:.4rem 0 .2rem 0; }
        .item-text{ flex:1; }
        </style>
        """, unsafe_allow_html=True)
        st.session_state[key] = True

def _scroll_to_top_if_needed() -> None:
    if st.session_state.get(SCROLL_FLAG):
        st.session_state[SCROLL_FLAG] = False
        k = st.session_state.get("_scroll_exec_counter", 0)
        st.session_state["_scroll_exec_counter"] = k + 1
        # scrolls until Y=0 (top). single key forces execution with each navigation
        scroll_to_here(0, key=f"top_{k}")

def render_scale_form(
    scale_ref: str | Path | Dict[str, Any],
    *,
    cfg: Optional[ScaleConfig] = None,
) -> Tuple[bool, Dict[str, str]]:
    cfg = cfg or ScaleConfig()

    raw = _load_scale(scale_ref)
    data = _normalize_scale(raw)

    keys = _build_keys(data.name)

    # (opcional) CSS global, se você tiver a função no arquivo
    try:
        _inject_styles_once()
    except Exception:
        pass

    signature = _compute_signature(cfg, data)
    _ensure_initial_state(cfg, keys, data.items, data.answer_options, signature)

    _scroll_to_top_if_needed()

    current_page = st.session_state[keys.page_key]
    total_pages = _total_pages(len(data.items), cfg.page_size)

    _render_header(data, current_page, total_pages)

    # Form por página -> o próprio botão valida e avança
    go_next, finished = _render_items_form(cfg, data, keys, current_page, total_pages)

    if go_next:
        st.session_state[keys.page_key] = min(total_pages, current_page + 1)
        st.session_state[SCROLL_FLAG] = True
        st.rerun()

    if finished:
        answers = st.session_state[keys.answers_key].copy()
        return True, answers

    return False, {}

# =========================
# Internals
# =========================

def _load_scale(scale_ref: str | Path | Dict[str, Any]) -> Dict[str, Any]:
    """
    Load a scale definition from various input formats into a Python dictionary.

    This helper accepts multiple types of references for flexibility when defining or 
    previewing scales in Streamlit:

    Parameters
    ----------
    scale_ref : str | Path | Dict[str, Any]
        - If a `dict` is provided, it is assumed to already represent a parsed scale and is returned as-is.
        - If a `Path` object is provided, the function reads the file (UTF-8 encoded) and parses it as JSON.
        - If a `str` is provided, it can be either:
            * a filesystem path to a JSON file, or
            * a raw JSON string (the function automatically distinguishes between them).

    Returns
    -------
    Dict[str, Any]
        A Python dictionary representing the loaded scale data.

    Behavior
    --------
    - The function first checks if the input is already a dictionary (in-memory object).
    - Then, it tries to interpret it as a file path (using `Path.exists()`).
    - If that fails, it finally assumes the input is a JSON string and attempts to parse it.
    - If any step fails to parse valid JSON, a `json.JSONDecodeError` will propagate.

    Notes
    -----
    This function is intentionally permissive: it is designed for flexible usage in 
    dynamic interfaces (e.g., Streamlit forms) where the input might come from 
    direct JSON text, local files, or preloaded data structures.
    """
    if isinstance(scale_ref, dict):
        return scale_ref
    if isinstance(scale_ref, Path):
        text = scale_ref.read_text(encoding="utf-8")
        return json.loads(text)
    
    # accept either a file path string or a JSON string
    try:
        p = Path(str(scale_ref))
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return json.loads(str(scale_ref))

def _normalize_scale(obj: Dict[str, Any]) -> ScaleData:
    """
    Normalize heterogeneous raw scale data (loaded from JSON or dict) into a 
    consistent internal representation (`ScaleData`).

    This function standardizes various possible input formats — accounting for 
    different field names, value types, and data shapes — so that downstream 
    components (UI rendering, validation, scoring) can work with a uniform schema.

    Parameters
    ----------
    obj : Dict[str, Any]
        A raw dictionary describing a scale. It may come from different sources 
        (e.g., user-defined JSON, localized formats, or legacy data), with fields 
        named in Portuguese ("titulo", "itens", "respostas") or English 
        ("name", "items", "answers").

    Returns
    -------
    ScaleData
        A structured dataclass instance containing:
        - `name` (str): normalized title of the scale.
        - `answer_options` (List[str]): list of response labels with a blank sentinel prepended.
        - `items` (List[ScaleItem]): standardized items with `id` and `text` fields.
        - `instruction_html` (Optional[str]): instructions in text or HTML format.

    Normalization logic
    -------------------
    1. **Scale name**
       - Extracted from "name" or "titulo"; defaults to "Escala" if missing.

    2. **Answer options**
       - Accepts multiple input shapes:
         * Dictionary (e.g., `{"Nunca": 0, "Às vezes": 1}`) → use the keys as labels.
         * Scalar (string/int/float) → wrap into a single-element list.
         * Iterable → cast all elements to strings.
       - Ensures a `"__BLANK__"` sentinel is added at the beginning so the UI can 
         display an empty option by default.

    3. **Items**
       - Accepts a list of dictionaries **or** a list of plain strings.
       - Each item dictionary can use any of the following keys:
         * `"id"`, `"numero"`, or `"index"` → item identifier.
         * `"text"`, `"texto"`, or `"label"` → display text.
       - If the item is a simple string or number, it becomes the text, and the 
         position index becomes its ID.
       - Each normalized item becomes a `ScaleItem(id, text)`.

    4. **UI metadata and instructions**
       - If `"ui"` is present and a dictionary, it is preserved (for potential 
         layout customization; not directly used here).
       - `"instructions"` are cast to string and stored as `instruction_html`.

    Example
    -------
    >>> raw = {
    ...     "titulo": "Inventário de Ansiedade",
    ...     "respostas": {"Nunca": 0, "Às vezes": 1, "Frequentemente": 2},
    ...     "itens": ["Sente-se nervoso?", "Tem dificuldade para relaxar?"],
    ...     "instructions": "Leia cada frase e selecione a opção que mais o descreve."
    ... }
    >>> _normalize_scale(raw)
    ScaleData(
        name='Inventário de Ansiedade',
        answer_options=['__BLANK__', 'Nunca', 'Às vezes', 'Frequentemente'],
        items=[
            ScaleItem(id='1', text='Sente-se nervoso?'),
            ScaleItem(id='2', text='Tem dificuldade para relaxar?')
        ],
        instruction_html='Leia cada frase e selecione a opção que mais o descreve.'
    )

    Notes
    -----
    - This function does not perform scoring or validation — it only cleans and 
      unifies input structure.
    - It tolerates missing or extra fields for forward compatibility.
    - The blank sentinel ensures downstream UI components can easily detect 
      unanswered items.
    """
    # Scale name (fallback to "Escala")
    name = str(obj.get("name") or obj.get("titulo") or "Escala")

    # Response options → ensure a list of strings
    options = obj.get("respostas") or obj.get("answers") or []

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
    
    ui = obj.get("ui") if isinstance(obj.get("ui"), dict) else {}
    instr = obj.get("instructions")
    instruction_html = str(instr) if instr is not None else None

    return ScaleData(name=name, answer_options=list(options), items=items, instruction_html=instruction_html)

def _slugify(name: str) -> str:
    """
    Convert an arbitrary string into a simple, lowercase slug identifier.

    This helper ensures that names (such as scale titles, facet labels, or item IDs)
    are transformed into a standardized format suitable for file names, keys,
    or URL fragments — removing accents, punctuation, and spacing inconsistencies.

    Parameters
    ----------
    name : str
        The input string to normalize (e.g., "Agressividade / Hostilidade").

    Returns
    -------
    str
        A lowercase string containing only alphanumeric characters and underscores.
        Multiple consecutive underscores are collapsed into one, and leading/trailing
        underscores are removed.

    Behavior
    --------
    1. Replaces every non-alphanumeric character with an underscore ("_").
    2. Collapses consecutive underscores and trims them from the edges.
    3. Converts the result to lowercase.

    Example
    -------
    >>> _slugify("Faceta: Ansiedade Geral")
    'faceta_ansiedade_geral'

    >>> _slugify("   Agressividade / Hostilidade!!  ")
    'agressividade_hostilidade'

    Notes
    -----
    - This function does not remove diacritics (accents). If accent-insensitive
      normalization is required, additional Unicode normalization (e.g. `unicodedata.normalize`)
      should be applied before calling `_slugify`.
    - Useful for generating internal dictionary keys, file names, or state keys
      in Streamlit where strict naming conventions are required.
    """
    s = "".join(ch if ch.isalnum() else "_" for ch in name.strip())
    s = "_".join([t for t in s.split("_") if t])
    return s.lower()

def _build_keys(scale_name: str) -> ScaleKeys:
    """
    Build a consistent set of Streamlit session-state keys for a given scale.

    This helper uses the scale name to generate a unique "slug" and then derives
    related state keys (for page tracking, user answers, initialization flag,
    and integrity signature). It ensures that multiple scales can coexist in the
    same Streamlit session without key collisions.

    Parameters
    ----------
    scale_name : str
        The display name of the scale (e.g., "PID-5 | Versão do Informante").

    Returns
    -------
    ScaleKeys
        A dataclass containing:
        - `slug`: a simplified identifier derived from the scale name.
        - `page_key`: session-state key for the current page index.
        - `answers_key`: key under which user answers are stored.
        - `init_key`: flag indicating whether the scale has been initialized.
        - `signature_key`: checksum key used to detect data changes or reloads.

    Behavior
    --------
    1. Calls `_slugify(scale_name)` to produce a lowercase, underscore-separated
       version of the scale name that is safe for use in session state.
    2. Constructs five related keys by appending double-underscore suffixes
       (`__page`, `__answers`, etc.).
    3. Returns them packaged inside a `ScaleKeys` dataclass for convenient access.

    Example
    -------
    >>> _build_keys("PID-5 | Versão do Informante")
    ScaleKeys(
        slug='pid_5_versao_do_informante',
        page_key='pid_5_versao_do_informante__page',
        answers_key='pid_5_versao_do_informante__answers',
        init_key='pid_5_versao_do_informante__initialized',
        signature_key='pid_5_versao_do_informante__signature'
    )

    Notes
    -----
    - Keeps all state keys grouped under the same prefix, avoiding accidental
      overlap between multiple scales.
    - The `slug` is also useful as a general identifier for file names or logs.
    """
    slug = _slugify(scale_name)
    return ScaleKeys(
        slug=slug,
        page_key=f"{slug}__page",
        answers_key=f"{slug}__answers",
        init_key=f"{slug}__initialized",
        signature_key=f"{slug}__signature",
    )

def _compute_signature(cfg: ScaleConfig, data: ScaleData) -> Tuple[Any, ...]:
    """
    Compute a tuple-based signature representing the structural identity of a scale.

    This lightweight checksum is used to detect whether a scale’s configuration or
    core data has changed — for example, when reloading JSON definitions or 
    switching between scales. If the computed signature differs from the one stored 
    in the Streamlit session state, the form is reinitialized.

    Parameters
    ----------
    cfg : ScaleConfig
        The runtime configuration of the scale (pagination size, UI flags, etc.).
    data : ScaleData
        The normalized data structure describing the scale’s name, items, and 
        answer options.

    Returns
    -------
    Tuple[Any, ...]
        An immutable tuple capturing key structural attributes of the current scale:
        - `data.name` → scale title or identifier
        - `tuple(data.answer_options)` → ordered list of response options
        - `len(data.items)` → total number of items in the scale
        - `cfg.allow_blank` → whether unanswered items are permitted
        - `cfg.page_size` → number of items per page
        - `cfg.show_id_badge` → whether to display item IDs beside text

    Example
    -------
    >>> sig = _compute_signature(cfg, data)
    >>> sig
    ('PID-5 | Versão do Informante',
     ('__BLANK__', 'Nunca', 'Às vezes', 'Frequentemente', 'Sempre'),
     220, True, 8, True)

    Notes
    -----
    - The returned tuple is hashable and can be safely stored or compared in 
      `st.session_state` to determine if a re-render or state reset is needed.
    - Only stable, structural aspects are included; transient data (like user answers)
      are intentionally excluded to avoid unnecessary resets.
    - This signature is *not* cryptographic — it’s designed for equality comparison,
      not for security or version control.
    """
    return (
        data.name,
        tuple(o for o in data.answer_options),
        len(data.items),
        cfg.allow_blank,
        cfg.page_size,
        cfg.show_id_badge,
    )

def _ensure_initial_state(
    cfg: ScaleConfig,
    keys: ScaleKeys,
    items: Sequence[ScaleItem],
    options: Sequence[str],
    signature: Tuple[Any, ...],
) -> None:
    """
    Initialize or refresh Streamlit session-state variables for a scale form.

    This function ensures that all required state keys exist in `st.session_state`
    before rendering the form. It creates default values for page index, user 
    answers, and metadata, and reinitializes them whenever the scale’s signature 
    changes (indicating a different or modified scale).

    Parameters
    ----------
    cfg : ScaleConfig
        Configuration object defining UI and behavior flags 
        (e.g., `allow_blank`, `test_prefill`, `blank_sentinel`).
    keys : ScaleKeys
        The unique set of Streamlit state keys for this scale 
        (from `_build_keys()`).
    items : Sequence[ScaleItem]
        The list of scale items for which initial answers must be created.
    options : Sequence[str]
        The list of response options (first element usually `"__BLANK__"`).
    signature : Tuple[Any, ...]
        The computed structural signature (from `_compute_signature()`),
        used to detect when the scale definition has changed.

    Behavior
    --------
    1. If the page key is missing, initialize it to `1` (start at first page).
    2. Determine whether reinitialization is needed:
       - If no previous answers exist, or
       - If the stored signature differs from the current one.
    3. If reinitialization is required:
       - Choose the appropriate default response for each item:
         * If `cfg.test_prefill` is True → use the first non-blank option.
         * If blanks are allowed → use the blank sentinel.
         * Otherwise → use the first valid option.
       - Populate `st.session_state[keys.answers_key]` as a dict mapping
         item IDs to their default values.
       - Mark initialization complete (`keys.init_key = True`).
       - Save the new signature in session state.

    Example
    -------
    >>> _ensure_initial_state(cfg, keys, data.items, data.answer_options, sig)
    # Session state now contains:
    # - {slug}__page = 1
    # - {slug}__answers = {'1': '__BLANK__', '2': '__BLANK__', ...}
    # - {slug}__initialized = True
    # - {slug}__signature = ('PID-5', ('__BLANK__', 'Nunca', 'Raramente', ...), ...)

    Notes
    -----
    - This ensures consistent behavior when switching scales or reloading JSON files.
    - The structural signature mechanism prevents stale answer data from a
      previously loaded scale.
    - The logic is intentionally simple and deterministic for reproducibility.
    """
    # Initialize page counter if missing
    if keys.page_key not in st.session_state:
        st.session_state[keys.page_key] = 1

    # Determine if we need to (re)initialize session state
    need_init = (keys.answers_key not in st.session_state) or (
        st.session_state.get(keys.signature_key) != signature
    )

    if need_init:
        if cfg.test_prefill:
            default_value = options[1] if len(options) > 1 else (options[0] if options else "")
        else:
            default_value = (
                cfg.blank_sentinel
                if cfg.allow_blank
                else (options[1] if len(options) > 1 else options[0])
            )

        # Initialize answers for all items
        st.session_state[keys.answers_key] = {str(it.id): default_value for it in items}
        st.session_state[keys.init_key] = True
        st.session_state[keys.signature_key] = signature

def _total_pages(n_items: int, page_size: int) -> int:
    """
    Compute the total number of pages required to display all items in a paginated scale.

    This helper determines how many pages are needed when splitting a list of items
    into chunks of fixed size (`page_size`). It ensures that at least one page is 
    always returned, even if the number of items is zero.

    Parameters
    ----------
    n_items : int
        Total number of items in the scale.
    page_size : int
        Number of items displayed per page.

    Returns
    -------
    int
        The total number of pages (minimum value = 1).

    Formula
    --------
    The computation uses ceiling division:
        total_pages = ceil(n_items / page_size)
    implemented efficiently as:
        (n_items + page_size - 1) // page_size

    Example
    -------
    >>> _total_pages(25, 10)
    3

    >>> _total_pages(0, 8)
    1

    Notes
    -----
    - Guarantees a positive result even when `n_items` is 0, preventing 
      division-by-zero errors and simplifying pagination logic in the UI.
    - Often used together with `_page_window()` to compute item indices per page.
    """
    return max(1, (n_items + page_size - 1) // page_size)

def _page_window(page: int, page_size: int, n_items: int) -> Tuple[int, int]:
    """
    Compute the start and end indices (slice window) for a given pagination page.

    This helper determines which subset of items should be displayed based on the
    current page number and the configured page size. It safely clamps the indices 
    so they never exceed the total number of items.

    Parameters
    ----------
    page : int
        The current page number (1-indexed).
    page_size : int
        The number of items to display per page.
    n_items : int
        The total number of items in the scale.

    Returns
    -------
    Tuple[int, int]
        A pair of indices `(start, end)` suitable for slicing Python lists:
        - `start` → inclusive start index.
        - `end` → exclusive end index (safe upper bound).

    Behavior
    --------
    - Calculates the zero-based starting index as `(page - 1) * page_size`.
    - The end index is the smaller of `n_items` or `start + page_size`.
    - Ensures the range is always within valid bounds, even for the last page.

    Example
    -------
    >>> _page_window(page=1, page_size=8, n_items=20)
    (0, 8)

    >>> _page_window(page=3, page_size=8, n_items=20)
    (16, 20)

    >>> _page_window(page=5, page_size=10, n_items=42)
    (40, 42)

    Notes
    -----
    - Designed to work seamlessly with Python list slicing:
          subset = items[start:end]
    - Used by pagination logic in the Streamlit form renderer to select which 
      items appear on the current page.
    """
    start = (page - 1) * page_size
    end = min(n_items, start + page_size)
    return start, end

def _render_header(data: ScaleData, current_page: int, total_pages: int) -> None:
    st.markdown(f"### {data.name}")
    st.caption(f"Página {current_page} de {total_pages}")
    st.divider()

def _render_item_row(
    cfg: ScaleConfig,
    keys: ScaleKeys,
    it: ScaleItem,
    options: Sequence[str],
    current_value: str,
) -> None:
    """
    Render a single item (question) row in the Streamlit scale form UI.

    This function draws one question line — including its optional numeric badge,
    text prompt, and a dropdown (selectbox) for response options. It also updates
    the Streamlit session state whenever the user changes their selection.

    Parameters
    ----------
    cfg : ScaleConfig
        Configuration object controlling rendering behavior:
        - `allow_blank`: whether an unanswered state is permitted.
        - `blank_sentinel`: value used to represent a blank response.
        - `show_id_badge`: whether to display the item’s ID number visually.
    keys : ScaleKeys
        Unique namespaced keys for this scale, used to store per-item responses
        inside `st.session_state`.
    it : ScaleItem
        The item (question) being rendered. Contains its `id` and text content.
    options : Sequence[str]
        The list of available response options, including `"__BLANK__"` if applicable.
    current_value : str
        The currently selected value for this item (from the session state).

    Behavior
    --------
    1. **Option filtering**
       - If blank answers are not allowed (`allow_blank=False`), removes the 
         blank sentinel from the options list.
    2. **Validation of current value**
       - If the stored `current_value` is invalid or no longer present in 
         `display_options`, falls back to the first available option.
    3. **Badge rendering**
       - Optionally displays an HTML-styled badge showing the item ID 
         (e.g., “#12”) if `show_id_badge=True`.
    4. **Text rendering**
       - Renders the item text beside the badge using a small HTML block for 
         layout control (`flex`, `gap`, and minimal margin).
    5. **Selectbox widget**
       - Displays a Streamlit `selectbox` for the user to choose one of the options.
       - Uses integer indices internally for stable selection.
       - The `format_func` (`_fmt`) hides the blank sentinel from view (shows empty label instead).
       - The widget key follows the convention `{slug}__sb__{item_id}` to maintain uniqueness.
    6. **Session state update**
       - Once the user selects an option, the chosen value is stored under
         `st.session_state[keys.answers_key][item_id]`.

    Example
    -------
    >>> _render_item_row(cfg, keys, item, ["__BLANK__", "Nunca", "Às vezes", "Sempre"], "__BLANK__")
    # Renders one line:
    # [#1] Sente-se nervoso(a)?  [ ☐ Nunca ☐ Às vezes ☐ Sempre ]

    Notes
    -----
    - The selectbox uses numeric indices rather than direct string values to 
      prevent Streamlit from losing widget state when the list of options changes.
    - The inline HTML provides fine-grained control over spacing and font 
      styling beyond default Streamlit markdown behavior.
    - Called repeatedly inside `_render_items_form()` to render each item on 
      the current page.
    """
    display_options = list(options)
    if not cfg.allow_blank:
        display_options = [o for o in display_options if o != cfg.blank_sentinel]

    # Fix invalid current value
    if current_value not in display_options:
        current_value = display_options[0] if display_options else ""

    try:
        idx = display_options.index(current_value)
    except ValueError:
        idx = 0

    # Render item row with optional badge
    badge_html = (
        f"<span class='item-badge' "
        f"style='display:inline-block;background:#2196F3;color:#fff;border:1px solid #fff;"
        f"border-radius:10px;padding:2px 10px;font-weight:700;min-width:2.4rem;text-align:center;'>"
        f"#{it.id}</span>"
    ) if cfg.show_id_badge else ""

    st.markdown(
        f"""
        <div class="item-row" style="display:flex;align-items:flex-start;gap:.6rem;margin:.4rem 0 .4rem 0;">
            {badge_html}
            <div class="item-text" style="flex:1;">{it.text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Dropdown (selectbox) widget
    select_key = f"{keys.slug}__sb__{it.id}"

    def _fmt(idx: int) -> str:
        val = display_options[idx]
        return "" if val == cfg.blank_sentinel else str(val)

    chosen_idx = st.selectbox(
        " ",
        options=list(range(len(display_options))),
        index=idx,
        key=select_key,
        format_func=_fmt,
        label_visibility="collapsed",
    )
    chosen_value = display_options[chosen_idx]
    st.session_state[keys.answers_key][str(it.id)] = chosen_value

def _validate_answers(
    cfg: ScaleConfig,
    data: ScaleData,
    answers: Dict[str, str],
    scope_items: Optional[Sequence[ScaleItem]] = None,
) -> List[Dict[str, Any]]:
    """
    Validate that all required items in the current scope have been answered.

    This function checks user responses for missing or blank values, even when
    blank answers are allowed globally (`cfg.allow_blank=True`). The idea is to
    ensure that each page is completed before advancing, while still permitting
    blank values in the final dataset if desired.

    Parameters
    ----------
    cfg : ScaleConfig
        The configuration for this scale, including:
        - `blank_sentinel`: the placeholder value representing a blank response.
        - `page_size`: the number of items per page (used to infer page numbers).
        - `allow_blank`: global policy for blank responses (does not override
          per-page validation).
    data : ScaleData
        The normalized scale definition, containing all items and their text.
    answers : Dict[str, str]
        A mapping of item IDs to their current selected values from the user.
    scope_items : Optional[Sequence[ScaleItem]], default=None
        If provided, restricts validation to a specific subset of items (e.g., 
        only those visible on the current page). If `None`, all items are checked.

    Returns
    -------
    List[Dict[str, Any]]
        A list of dictionaries describing items that are missing responses.
        Each dictionary includes:
        - `"Item"`: the item’s ID.
        - `"Página"`: the page number where it appears (1-indexed).
        - `"Pergunta"`: the item’s text (for informative display).

        Returns an empty list if all required items have been answered.

    Behavior
    --------
    - Determines the validation scope (current page or full form).
    - Iterates through all items in order, skipping those not in `scope_items`.
    - Checks each item’s answer:
        * If the value equals the blank sentinel, is `None`, or an empty string,
          it is marked as missing.
    - Calculates the page number of each missing item using integer division
      based on its position and `page_size`.

    Example
    -------
    >>> missing = _validate_answers(cfg, data, st.session_state["answers"], current_page_items)
    >>> missing
    [{'Item': '7', 'Página': 2, 'Pergunta': 'Sente-se tenso(a)?'}]

    Notes
    -----
    - Even if blank answers are permitted globally, this function enforces
      per-page completeness to prevent users from skipping items inadvertently.
    - The resulting list is typically displayed as a warning table in the UI,
      helping the respondent locate unanswered questions before proceeding.
    - Does not modify session state; it only analyzes and reports missing data.
    """
    # Even if allow_blank=True, we still require answers before page advancement
    # (blank_sentinel is treated as "missing" during validation).
    scope = scope_items if scope_items is not None else data.items
    missing: List[Dict[str, Any]] = []

    # Determine each item's page to include in the report
    for pos, it in enumerate(data.items, start=1):
        if scope_items is not None and it not in scope_items:
            continue
        val = answers.get(str(it.id), cfg.blank_sentinel)
        if val == cfg.blank_sentinel or val is None or val == "":
            page = ((pos - 1) // cfg.page_size) + 1
            missing.append({"Item": it.id, "Página": page, "Pergunta": it.text})
    return missing

def _render_items_form(
    cfg: ScaleConfig,
    data: ScaleData,
    keys: ScaleKeys,
    current_page: int,
    total_pages: int,
) -> Tuple[bool, bool]:
    """
    Render the paginated form for the current page of a scale and handle submission.

    This function draws the page-level UI (optional instructions + the list of items
    for the current page), manages the Streamlit `st.form` submit flow, validates
    answers for the visible items, and returns navigation flags to the caller.

    Parameters
    ----------
    cfg : ScaleConfig
        Rendering/behavior configuration (e.g., `page_size`, `allow_blank`,
        `blank_sentinel`, `show_id_badge`).
    data : ScaleData
        Normalized scale definition, including `items`, `answer_options`,
        and optional `instruction_html`.
    keys : ScaleKeys
        Namespaced keys used to read/write into `st.session_state`.
    current_page : int
        The 1-based index of the page currently being displayed.
    total_pages : int
        The total number of pages in the scale (from `_total_pages()`).

    Returns
    -------
    Tuple[bool, bool]
        `(go_next, finished)`:
        - `go_next`   → True if the current page was completed and the UI
                        should advance to the next page.
        - `finished`  → True if the user completed the last page and the
                        whole scale passed final validation.

    Behavior
    --------
    1) **Page window**
       - Computes `(start, end)` with `_page_window(...)` and slices items for this page.

    2) **Instructions block (optional)**
       - If `instruction_html` exists, it is sanitized for display:
         * Strips any incoming HTML tags to plain text.
         * Escapes it to avoid accidental HTML rendering.
         * Converts line breaks (`\n`, `\n\n`) into `<br>` for layout.
       - Renders a labeled “Instruções” section above the form.

    3) **Form rendering**
       - Uses `st.form(key=...)` so submission is atomic and the warning
         stays visually attached to the submit button.
       - For each item on the page:
         * Reads the current value from `st.session_state[keys.answers_key]`.
         * Calls `_render_item_row(...)` to draw the row and sync state.

    4) **Validation & submit handling**
       - Shows a warning placeholder (`warn_box`) above the button.
       - The submit button label is “Enviar escala” on the last page,
         otherwise “Próxima página”.
       - On submit:
         * Validates **only the current page** via `_validate_answers(..., scope_items=page_items)`.
         * If missing answers → shows a concise warning listing item IDs.
         * If no missing answers:
             - If last page: runs a **global** validation pass to ensure other
               pages weren’t left incomplete. If none missing, sets `finished=True`.
             - If not last page: sets `go_next=True`.

    Design notes
    ------------
    - `clear_on_submit=False` preserves user selections after submit.
    - Warnings are placed **inside** the form so they remain visually “glued”
      to the submit button.
    - The function itself does not mutate pagination state; it only signals
      intent via `(go_next, finished)` for the caller to act on.

    Example
    -------
    >>> go_next, finished = _render_items_form(cfg, data, keys, current_page=2, total_pages=5)
    >>> go_next, finished
    (True, False)  # advance to page 3
    """
    start, end = _page_window(current_page, cfg.page_size, len(data.items))
    page_items = data.items[start:end]

    form_key = f"{keys.slug}__form__{current_page}"
    go_next = False
    finished = False

    instr_raw = data.instruction_html

    if instr_raw:
        st.markdown(
            "<h4 style='color:#FFB300; margin:0 0 .25rem 0;'>Instruções</h4>",
            unsafe_allow_html=True
        )

        import re, html as ihtml
        # Strip any HTML that may come from JSON and keep plain text only
        txt = re.sub(r"<[^>]+>", "", str(instr_raw)).strip()
        # Escape to avoid rendering as HTML, then handle line breaks
        txt = ihtml.escape(txt)
        txt = txt.replace("\n\n", "<br><br>").replace("\n", "<br>")

        st.markdown(
            f"""<div style="text-align: justify; text-justify: inter-word; line-height: 1.45;">
                    {txt}
                </div>""",
            unsafe_allow_html=True
        )
    
        st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

    with st.form(key=form_key, clear_on_submit=False):

        # Render items on this page
        for it in page_items:
            val = st.session_state[keys.answers_key][str(it.id)]
            _render_item_row(cfg, keys, it, data.answer_options, val)

        # Placeholder for warnings (appears ABOVE the button)
        warn_box = st.empty()

        # Submit button
        is_last = (current_page == total_pages)
        label = "Enviar escala" if is_last else "Próxima página"
        submitted = st.form_submit_button(label, use_container_width=True)

        # Validation & decision — INSIDE the form so the warning stays attached
        if submitted:
            # Validate only the items on the current page
            missing = _validate_answers(cfg, data, st.session_state[keys.answers_key], scope_items=page_items)
            if missing:
                # Build a short message with missing IDs
                ids = ", ".join(str(row["Item"]) for row in missing)
                warn_box.warning(f"Ainda faltam respostas nesta página: itens {ids}.")
            else:
                if is_last:
                    # Global final check (optional, but ensures integrity)
                    missing_all = _validate_answers(cfg, data, st.session_state[keys.answers_key], scope_items=None)
                    if missing_all:
                        ids_all = ", ".join(str(row["Item"]) for row in missing_all)
                        warn_box.warning(f"Faltam respostas em outras páginas: itens {ids_all}.")
                    else:
                        finished = True
                else:
                    go_next = True

    return go_next, finished

