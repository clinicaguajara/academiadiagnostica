# utils/data_management.py

# =========================================
# Necessary imports
# =========================================

from __future__ import annotations

import json
import re

from collections import defaultdict
from pathlib     import Path
from typing      import Any, Dict, List, Optional, Tuple

from utils.normalize import norm_key


# =========================================
# Data management
# =========================================

def load_json(source: str | Path | Dict) -> Dict:
    """
    Load a JSON object from multiple input types.

    Parameters
    ----------
    source:
        - dict: returned as-is
        - Path: read as UTF-8 (accepts BOM via utf-8-sig) and parsed as JSON
        - str: either a filesystem path to a JSON file, or a raw JSON string

    Returns
    -------
    dict
        The parsed JSON object.

    Notes
    -----
    This helper is intentionally permissive to support UI code that may pass
    either a path or raw JSON contents.
    """
    if isinstance(source, dict):
        return source

    if isinstance(source, Path):
        return json.loads(source.read_text(encoding="utf-8-sig"))

    p = Path(str(source))
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8-sig"))

    return json.loads(str(source).lstrip("\ufeff"))


def find_bibliography_candidates(
    display_label: str,
    search_dirs: Optional[List[str | Path]] = None,
) -> List[Tuple[Path, Dict[str, Any], str]]:
    """
    Find bibliography JSON candidates that match a scale display label.

    This function performs an accent-/case-/whitespace-insensitive comparison
    between the provided `display_label` and the candidate JSON fields:
    - "scale" (preferred)
    - "name" or "titulo"
    - filename stem (fallback)

    Parameters
    ----------
    display_label:
        The scale label shown in the UI (e.g., "PID-5 | Autorrelato Completo").
    search_dirs:
        Optional list of directories to search. Defaults to ["bibliography"].

    Returns
    -------
    list[tuple[Path, dict, str]]
        A list of (path, parsed_json, ui_label) sorted by ui_label.
    """
    project_root = Path(__file__).resolve().parents[1]
    candidates_dirs = search_dirs or [project_root / "bibliography"]
    target = norm_key(display_label)

    matches: List[Tuple[Path, Dict[str, Any], str]] = []
    for d in candidates_dirs:
        base = Path(d)
        if not base.exists():
            # Support callers running Streamlit from a different working directory.
            # If a relative path does not exist, try resolving it from the project root.
            if not base.is_absolute():
                base = project_root / base
        if not base.exists():
            continue

        for p in base.rglob("*.json"):
            try:
                data = load_json(p)
            except Exception:
                continue

            cand_name_raw = data.get("scale") or data.get("name") or data.get("titulo") or p.stem
            if norm_key(cand_name_raw) != target:
                continue

            study_bits = [
                data.get("version") or data.get("versao") or "",
                data.get("cite") or "",
                data.get("name") or data.get("titulo") or p.stem,
            ]
            label = " • ".join([str(b) for b in study_bits if str(b).strip()]).strip(" •")
            matches.append((p, data, label or p.stem))

    matches.sort(key=lambda t: (t[2] or "").lower())
    return matches


def discover_scales(scales_root: str | Path) -> Dict[str, List[Tuple[str, Path]]]:
    """
    Scans `scales_root` recursively for *.json scale definition files.

    Returns a mapping:
        { "category": [ (label, path_to_json), ... ] }

    Notes
    -----
    - Category is the first-level folder under `scales_root` (e.g., "personality", "development").
    - Files directly under `scales_root` are grouped under "Raiz".
    - The label is extracted from JSON ("name" or "titulo") when present; otherwise, file stem.
    """
    
    # Ensure Path object
    root = Path(scales_root)

    # Scan for JSON files
    found: Dict[str, List[Tuple[str, Path]]] = defaultdict(list)
    if not root.exists():
        return {} # Early return if root does not exist

    # Iterate over JSON files
    for f in sorted(root.rglob("*.json")):
        try:
            # Get relative path
            rel = f.relative_to(root)
        except Exception:
            # If relative_to fails, use absolute path as fallback
            rel = f

        parts = rel.parts # Split path parts
        categoria = parts[0] if len(parts) > 1 else "Raiz" # First-level folder or "Raiz"

        # Determine label
        label = f.stem
        try:
            data = load_json(f)

            # Extract label from JSON metadata
            label = str(data.get("name") or data.get("titulo") or f.stem)
            label = re.sub(r"\s+", " ", label).strip()
        
        except Exception:
            pass # Ignore errors and use file stem as label
        
        # Append to found mapping
        found[categoria].append((label, f))

    # Sort entries within each category
    for _, arr in found.items():
        arr.sort(key=lambda t: t[0].lower())

    return dict(found)
