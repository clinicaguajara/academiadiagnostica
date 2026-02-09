# modules/corrections.py

# =========================================
# Necessary Imports
# =========================================

from math            import erf, sqrt
from typing          import Dict, Any, List, Tuple, Optional
from utils.normalize import norm_key

# =========================================
# Helpers
# =========================================

def use_item_mean_for_z(scale_ref: Dict[str, Any]) -> bool:
    """
    Decide whether the z-score should be computed from item mean (default)
    or from raw sum (useful for binary-scored instruments, e.g. AQ-50).

    Reads, in order, the following optional fields from `scale_ref`:
    - z_from
    - z_metric
    - norm_metric
    """
    raw = (
        scale_ref.get("z_from")
        or scale_ref.get("z_metric")
        or scale_ref.get("norm_metric")
        or ""
    )
    k = norm_key(raw)
    if k in {"raw", "raw_sum", "sum", "bruta", "bruto", "weighted_sum"}:
        return False
    if k in {
        "mean",
        "mean_items",
        "media",
        "media_itens",
        "item_mean",
        "weighted_mean",
        "weighted_items_mean",
    }:
        return True
    return True


def _response_range(scale: Dict[str, Any]) -> Tuple[float, float]:
    response_map = scale.get("response_map", {}) or {}
    vals: List[float] = []
    for v in response_map.values():
        try:
            vals.append(float(v))
        except Exception:
            continue
    if not vals:
        return 0.0, 3.0
    return float(min(vals)), float(max(vals))


def get_facet_item_weights(scale: Dict[str, Any], facet: str) -> Dict[str, float]:
    """
    Return a per-item weight map for a given facet.

    Weights can be provided either globally under `item_weights` or per facet under
    `facets.<facet>.item_weights`. Keys are strings to match JSON conventions.

    If a weight is missing or invalid, it is treated as 1.0 at scoring time.
    """
    f = (scale.get("facets") or {}).get(str(facet), {}) or {}
    global_w = (scale.get("item_weights") or {}) if isinstance(scale.get("item_weights"), dict) else {}
    facet_w = (f.get("item_weights") or {}) if isinstance(f.get("item_weights"), dict) else {}

    out: Dict[str, float] = {}
    for src in (global_w, facet_w):
        for k, v in src.items():
            try:
                out[str(k)] = float(v)
            except Exception:
                continue
    return out


def get_facet_sum_range(scale: Dict[str, Any], facet: str) -> Tuple[float, float]:
    """
    Return the theoretical (min_sum, max_sum) for a facet raw sum.

    Supports negative weights:
      - if w >= 0: min uses min_response, max uses max_response
      - if w < 0:  min uses max_response, max uses min_response
    """
    f = (scale.get("facets") or {}).get(str(facet), {}) or {}
    items = f.get("items") or []
    wmap = get_facet_item_weights(scale, facet)
    vmin, vmax = _response_range(scale)

    lo = 0.0
    hi = 0.0
    for item in items:
        w = wmap.get(str(item), 1.0)
        try:
            wf = float(w)
        except Exception:
            wf = 1.0

        if wf >= 0:
            lo += vmin * wf
            hi += vmax * wf
        else:
            lo += vmax * wf
            hi += vmin * wf

    if lo <= hi:
        return float(lo), float(hi)
    return float(hi), float(lo)

def get_norm_group_options_from_facets(scale_ref: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """
    Collect available norm groups by scanning `facets.*.norms` and return:
      (groups, labels)

    - `groups` preserves the original keys as they appear in the JSON (case-sensitive).
    - `labels` is a human-friendly version of each group key.
    """
    pretty = {
        "clinico": "Clínico",
        "clínico": "Clínico",
        "comunitario": "Comunitário",
        "comunitário": "Comunitário",
        "total": "Total",
        "alto risco": "Alto Risco",
        "normativo": "Normativo",
        "controle": "Controle",
        "autistas": "Autistas",
    }

    groups: List[str] = []
    seen: set[str] = set()
    for f in (scale_ref.get("facets") or {}).values():
        for g in (f.get("norms") or {}).keys():
            raw = str(g).strip()
            norm = norm_key(raw)
            if norm not in seen:
                seen.add(norm)
                groups.append(raw)

    order_pref = ["clinico", "comunitario", "total", "controle", "autistas"]
    groups = sorted(
        groups,
        key=lambda g: (
            order_pref.index(norm_key(g)) if norm_key(g) in order_pref else 99,
            norm_key(g),
        ),
    )
    labels = [pretty.get(norm_key(g), g) for g in groups]
    return groups, labels


def get_norm_group_description(scale_ref: Dict[str, Any], group: str) -> Optional[str]:
    """
    Return a human-readable description for a norm group (if provided in the study JSON).

    Expected JSON field:
        norm_group_descriptions: { "<group>": "<free text>" }

    Matching is attempted by:
    - exact key (case-sensitive)
    - accent/case/whitespace-insensitive key via norm_key
    """
    raw_map = scale_ref.get("norm_group_descriptions") or {}
    if not isinstance(raw_map, dict) or not raw_map:
        return None

    if group in raw_map:
        txt = raw_map.get(group)
        return str(txt).strip() if str(txt).strip() else None

    target = norm_key(str(group))
    for k, v in raw_map.items():
        if norm_key(str(k)) == target:
            txt = str(v).strip()
            return txt if txt else None

    return None

def _get_norm_params(scale: Dict[str, Any], facet: str, group: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Return (mean, sd) for a given facet and norm group, with practical fallbacks.

    - First tries `facets[facet].norms[group]` (exact match).
    - Then tries an accent/case/whitespace-insensitive match against available groups.
    - Then falls back to `default_norm_group`, or any available group.
    - Finally falls back to `facets[facet].mean` / `facets[facet].sd` if present.
    """
    fdata = scale["facets"][facet]
    norms = fdata.get("norms")
    if norms:
        # Direct match first.
        if group in norms:
            return norms[group].get("mean"), norms[group].get("sd")

        # Case/space/accent-insensitive match (e.g., "controle" -> "Controle")
        target = norm_key(group)
        for k, v in norms.items():
            if norm_key(k) == target:
                return v.get("mean"), v.get("sd")

    # Fallbacks: default group -> any available group
    if norms:
        gdef = scale.get("default_norm_group")
        if gdef:
            if gdef in norms:
                return norms[gdef].get("mean"), norms[gdef].get("sd")
            target_def = norm_key(gdef)
            for k, v in norms.items():
                if norm_key(k) == target_def:
                    return v.get("mean"), v.get("sd")
        if len(norms) > 0:
            any_group = next(iter(norms.values()))
            return any_group.get("mean"), any_group.get("sd")

    # Final fallback: mean/sd stored directly on the facet object.
    return fdata.get("mean"), fdata.get("sd")


# =========================================
# Scoring
# =========================================

def _reverse_value(v: Optional[int], max_val: int = 3) -> Optional[int]:
    """Reverse a scored value given the maximum possible value."""
    if v is None:
        return None
    return max_val - int(v)

def _z_to_percentile(z: Optional[float]) -> Optional[float]:
    """Convert a z-score to a percentile (0..100)."""
    if z is None:
        return None
    pct = 50.0 * (1.0 + erf(z / sqrt(2.0)))
    # Clamp to avoid values like 100.0000001 due to floating point rounding.
    if pct < 0.0:
        pct = 0.0
    elif pct > 100.0:
        pct = 100.0
    return pct

def _compute_z(x: Optional[float], mean: Optional[float], sd: Optional[float]) -> Optional[float]:
    """Compute a z-score (x - mean) / sd with basic guards."""
    if x is None or mean is None or sd in (None, 0):
        return None
    return (x - mean) / sd

def summarize_with_norms(
    scale: Dict[str, Any],
    facet_stats: Dict[str, Dict[str, Any]],
    norm_group: str,
    *,
    use_item_mean_for_z: bool = True
) -> List[Dict[str, Any]]:
    """
    For each facet, retrieve (mean, sd) for the selected norm group, compute z and percentile,
    and return rows suitable for building a results DataFrame.
    """
    rows: List[Dict[str, Any]] = []
    for facet, stats in facet_stats.items():
        mean_ref, sd_ref = _get_norm_params(scale, facet, norm_group)

        base_value = stats["mean_items"] if use_item_mean_for_z else stats["raw_sum"]
        z = _compute_z(base_value, mean_ref, sd_ref)
        pct = _z_to_percentile(z)

        rows.append({
            "faceta": facet,
            "media_itens": None if stats["mean_items"] is None else round(stats["mean_items"], 3),
            "z": None if z is None else round(z, 3),
            "percentil": None if pct is None else round(pct, 1),
            "bruta": None if stats["raw_sum"] is None else round(stats["raw_sum"], 3),
            "norma": norm_group,
            "mean_ref": mean_ref,
            "sd_ref": sd_ref,
        })
    return rows

def build_classification_table(
    scale: Dict[str, Any],
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Build a classification table based on JSON rules under `classification`.

    Rules are evaluated in order based on `abs(z)` and choose `label_above` or `label_below`
    depending on the sign of z.
    """
    classes = scale.get("classification", [])
    out = []
    for r in rows:
        z = r.get("z")
        if z is None:
            label = None
        else:
            abs_z = abs(z)
            label_above = None
            label_below = None

            # Find the first applicable rule.
            chosen = None
            for rule in classes:
                max_abs = rule.get("max_abs_z")
                if max_abs is None or abs_z <= float(max_abs):
                    chosen = rule
                    break

            if chosen is None:
                label = None
            else:
                label_above = chosen.get("label_above")
                label_below = chosen.get("label_below")
                label = label_above if z >= 0 else label_below

        out.append({
            "faceta": r["faceta"],
            "z": r["z"],
            "classificacao": label
        })
    return out

def score_scales(
    scale: Dict[str, Any],
    answers: Dict[int, Any],
    *,
    use_item_mean: bool = True,
) -> Dict[str, Dict[str, Any]]:
    """
    Score a faceted scale, producing per-facet raw sums and item means.

    - `answers`: maps item id (1..N) -> either an int score or a response label present in `response_map`.
    - `reverse_items`: items to reverse-score using the inferred `max_val`.
    """
    response_map = scale.get("response_map", {})
    # Infer maximum response value from response_map (supports binary scoring like AQ-50).
    try:
        max_val = max(int(v) for v in response_map.values())
    except Exception:
        max_val = 3
    reverse_items = set(scale.get("reverse_items", []))
    apply_weights = bool(scale.get("apply_item_weights", False))
    global_weights = (scale.get("item_weights") or {}) if isinstance(scale.get("item_weights"), dict) else {}

    out: Dict[str, Dict[str, Any]] = {}
    for facet, fdata in scale["facets"].items():
        item_ids: List[int] = fdata["items"]
        facet_weights = (fdata.get("item_weights") or {}) if isinstance(fdata.get("item_weights"), dict) else {}

        scored_vals: List[int] = []
        unweighted_sum = 0.0
        weighted_sum = 0.0

        for item in item_ids:
            raw = answers.get(item)
            if raw is None:
                continue
            # Convert response labels to numeric scores via response_map when needed.
            if isinstance(raw, str):
                if raw not in response_map:
                    continue
                val = response_map[raw]
            else:
                val = int(raw)

            # Reverse-score items when required.
            if item in reverse_items:
                val = _reverse_value(val, max_val=max_val)

            scored_vals.append(val)
            unweighted_sum += float(val)

            if apply_weights:
                w = facet_weights.get(str(item), global_weights.get(str(item), 1.0))
                try:
                    wf = float(w)
                except Exception:
                    wf = 1.0
                weighted_sum += float(val) * wf
            else:
                weighted_sum += float(val)

        if len(scored_vals) == 0:
            raw_sum = None
            mean_items = None
        else:
            raw_sum = float(weighted_sum)
            mean_items = (unweighted_sum / len(scored_vals)) if use_item_mean else None

        out[facet] = {
            "raw_sum": raw_sum,
            "mean_items": mean_items,
            "n_answered": len(scored_vals),
            "n_items": len(item_ids),
        }
    return out
