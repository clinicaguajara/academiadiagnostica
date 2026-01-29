# pages/4_Graficos.py

# =========================================
# Necessary Imports
# =========================================

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd
import streamlit as st

from utils.design import inject_custom_css
from utils.data_management import find_bibliography_candidates
from utils.global_variables import BLANK
from utils.normalize import norm_key
from modules.corrections import (
    build_classification_table,
    get_norm_group_description,
    get_norm_group_options_from_facets,
    score_scales,
    summarize_with_norms,
    use_item_mean_for_z,
)


def _facet_n_items(scale_ref: Dict[str, Any], facet: str) -> int:
    f = (scale_ref.get("facets") or {}).get(str(facet), {})
    if "n_items" in f and isinstance(f["n_items"], (int, float)):
        try:
            return int(f["n_items"])
        except Exception:
            pass
    items = f.get("items") or []
    return int(len(items))


def _infer_max_per_item(scale_ref: Dict[str, Any]) -> int:
    response_map = scale_ref.get("response_map", {}) or {}
    try:
        return int(max(int(v) for v in response_map.values()))
    except Exception:
        return 3


def _is_total_label(label: object) -> bool:
    k = norm_key(str(label or ""))
    return k in {
        "total",
        "pontuacao total",
        "pontuacao_total",
        "funcionamento intrapessoal",
        "funcionamento interpessoal",
    }

def _normalize_answers(answers_raw: Dict[Any, Any]) -> Dict[int, Any]:
    answers_norm: Dict[int, Any] = {}
    for k, v in (answers_raw or {}).items():
        try:
            ik = int(str(k))
        except Exception:
            continue
        answers_norm[ik] = None if v in (None, "", BLANK) else v
    return answers_norm


inject_custom_css()
st.title("Gráficos")

data_key = "escalas_respondidas"
names_key = "escalas_display_names"
all_answers: Dict[str, Dict[Any, Any]] = st.session_state.get(data_key, {})
display_names: Dict[str, str] = st.session_state.get(names_key, {})

if not all_answers:
    st.info("Nenhuma escala respondida encontrada na sessão. Volte e aplique uma escala primeiro.")
    st.stop()

# Optional: preload defaults from the last Results run (if available)
ctx = st.session_state.get("results::context") if isinstance(st.session_state.get("results::context"), dict) else {}
default_label = str(ctx.get("sel_label") or "")
default_selected_path = str(ctx.get("selected_path") or "")
default_norm_group = str(ctx.get("norm_group") or "")

display_options = []
slug_lookup = {}
for slug, _ans in all_answers.items():
    label = display_names.get(slug, slug)
    display_options.append(label)
    slug_lookup[label] = slug

display_options = sorted(display_options)
default_idx = display_options.index(default_label) if default_label in display_options else 0
sel_label = st.selectbox("Selecione o instrumento", display_options, index=default_idx)
scale_key = slug_lookup[sel_label]

answers_raw = all_answers.get(scale_key, {})
if not answers_raw:
    st.error("Não encontrei respostas para essa escala. Verifique o salvamento.")
    st.stop()

answers = _normalize_answers(answers_raw)

# Study selection (bibliography)
candidates = find_bibliography_candidates(sel_label)
if not candidates:
    st.warning(
        "Não encontrei estudo normativo cujo campo 'scale' (ou 'name'/'titulo') "
        f"seja idêntico ao nome da escala selecionada: “{sel_label}”.\n\n"
        "Verifique o JSON normativo e se ele está em 'scales/' ou 'bibliography/'."
    )
    st.stop()

labels = [lab for _, __, lab in candidates]
default_study_idx = 0
if default_selected_path:
    for i, (p, _, _) in enumerate(candidates):
        if str(p) == default_selected_path:
            default_study_idx = i
            break
idx_study = st.selectbox(
    "Selecione o estudo normativo",
    options=list(range(len(labels))),
    format_func=lambda i: labels[i],
    index=default_study_idx,
)
selected_path, scale_ref, _ = candidates[idx_study]

study_name = str(scale_ref.get("name") or scale_ref.get("titulo") or Path(selected_path).stem)
study_ver = str(scale_ref.get("version") or scale_ref.get("versao") or "").strip()

# Norm group selection
groups, group_labels = get_norm_group_options_from_facets(scale_ref)
if groups:
    default_group_idx = 0
    if default_norm_group:
        for i, g in enumerate(groups):
            if norm_key(str(g)) == norm_key(default_norm_group):
                default_group_idx = i
                break
    idx = st.radio(
        "Selecione o grupo normativo",
        options=list(range(len(groups))),
        format_func=lambda i: group_labels[i],
        horizontal=True,
        index=default_group_idx,
    )
    norm_group, norm_label = groups[idx], group_labels[idx]
else:
    fallback = [("clinico", "Clínico"), ("comunitario", "Comunitário"), ("total", "Total")]
    idx = st.radio(
        "Selecione o grupo normativo",
        options=list(range(len(fallback))),
        format_func=lambda i: fallback[i][1],
        horizontal=True,
        index=2,
    )
    norm_group, norm_label = fallback[idx]

cite = scale_ref.get("cite", None)
if cite:
    st.info(cite, icon="📄")

group_desc = get_norm_group_description(scale_ref, norm_group)
if group_desc:
    st.write(f"{group_desc}")

has_facets = isinstance(scale_ref.get("facets"), dict)
if not has_facets:
    st.warning(
        "Esta escala não possui 'facets' no estudo selecionado. "
        "A página de gráficos atualmente suporta apenas escalas com facetas."
    )
    st.stop()

facet_stats = score_scales(scale_ref, answers, use_item_mean=True)
rows = summarize_with_norms(
    scale_ref,
    facet_stats,
    norm_group=norm_group,
    use_item_mean_for_z=use_item_mean_for_z(scale_ref),
)
df_rows = pd.DataFrame(rows)
df_classif = pd.DataFrame(build_classification_table(scale_ref, rows))

for c in ["faceta", "media_itens", "z", "percentil", "bruta", "mean_ref", "sd_ref", "norma"]:
    if c not in df_rows.columns:
        df_rows[c] = pd.NA

domains = (scale_ref.get("domains") or {})
facet_to_domain = {str(f): dom for dom, facets in domains.items() for f in facets}
df_rows["dominio"] = df_rows["faceta"].map(lambda f: facet_to_domain.get(str(f), "—"))

if not df_classif.empty and {"faceta", "classificacao"} <= set(df_classif.columns):
    df_master = df_rows.merge(df_classif[["faceta", "classificacao"]], on="faceta", how="left")
else:
    df_master = df_rows.assign(classificacao=pd.NA)

df_master = df_master.sort_values(["dominio", "faceta"], kind="stable").reset_index(drop=True)

st.divider()

# =========================================
# Mode selector
# =========================================

domains_ok = []
if {"dominio", "faceta"} <= set(df_master.columns):
    dom_counts = (
        df_master[["dominio", "faceta"]]
        .dropna()
        .groupby("dominio", as_index=False)
        .agg(n_facetas=("faceta", "nunique"))
    )
    domains_ok = [
        str(r.dominio)
        for r in dom_counts.itertuples(index=False)
        if str(r.dominio).strip() not in {"—", "-", ""} and int(r.n_facetas) > 2
    ]

mode_options = ["Facetas (distribuição)"]
if domains_ok:
    mode_options.append("Domínios (facetas)")

mode = st.radio("Selecione o tipo de gráfico:", options=mode_options, horizontal=True)

# =========================================
# Plot (interactive)
# =========================================

import numpy as np
import plotly.graph_objects as go

if mode == "Domínios (facetas)":
    if not domains_ok:
        st.info("Não há nenhum domínio com mais de duas facetas para gerar gráficos por domínio.")
        st.stop()
    if {"dominio", "faceta", "z"} - set(df_master.columns):
        st.info("Este resultado não possui colunas suficientes para gráficos por domínio (preciso de 'dominio', 'faceta' e 'z').")
        st.stop()

    dom = st.selectbox("Selecione o domínio:", options=domains_ok)
    df = df_master.loc[df_master["dominio"].astype(str) == str(dom)].copy()
    df = df[["faceta", "z", "percentil", "classificacao", "bruta", "media_itens"]].copy()
    df = df.dropna(subset=["faceta", "z"])
    # Sort facets by z-score (desc), but always keep Total/Pontuação Total as the last line.
    df["_is_total"] = df["faceta"].map(_is_total_label)
    df = pd.concat(
        [
            df.loc[~df["_is_total"]].sort_values("z", ascending=False, kind="stable"),
            df.loc[df["_is_total"]].sort_values("z", ascending=False, kind="stable"),
        ],
        ignore_index=True,
    )
    if df["faceta"].nunique() <= 2:
        st.info("Este domínio não possui mais de duas facetas com z-score disponível.")
        st.stop()

    y_order = df["faceta"].astype(str).tolist()

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["z"],
            y=df["faceta"],
            orientation="h",
            customdata=np.column_stack([
                df.get("percentil", pd.Series([pd.NA] * len(df))),
                df.get("classificacao", pd.Series([pd.NA] * len(df))),
                df.get("bruta", pd.Series([pd.NA] * len(df))),
                df.get("media_itens", pd.Series([pd.NA] * len(df))),
            ]),
            hovertemplate=(
                "Faceta: %{y}<br>"
                "Z: %{x:.3f}<br>"
                "Percentil: %{customdata[0]}<br>"
                "Classificação: %{customdata[1]}<br>"
                "Escore: %{customdata[2]}<br>"
                "Média (itens): %{customdata[3]}<extra></extra>"
            ),
            marker=dict(color="#5DADE2"),
        )
    )
    fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="#FFFFFF")
    fig.update_layout(
        title=f"{dom} — facetas (z-score)",
        xaxis_title="Z-score",
        yaxis_title="Faceta",
        template="plotly_dark",
        margin=dict(l=10, r=10, t=60, b=10),
        height=420,
    )
    fig.update_yaxes(categoryorder="array", categoryarray=y_order, autorange="reversed")
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})
else:
    from modules.gauss_plot import NormSpec, compute_discrete_points
    import math

    _opts = (
        df_master[["dominio", "faceta"]]
        .dropna()
        .sort_values(["dominio", "faceta"], kind="stable")
    )
    if _opts.empty:
        st.info("Não há facetas para plotar.")
        st.stop()

    _opt_labels = [f"{row.dominio} • {row.faceta}" for row in _opts.itertuples(index=False)]
    _opt_index = st.selectbox(
        "Selecione a faceta para visualizar a distribuição e percentil estimado:",
        options=list(range(len(_opt_labels))),
        format_func=lambda i: _opt_labels[i],
    )

    sel_dom = _opts.iloc[_opt_index]["dominio"]
    sel_fac = _opts.iloc[_opt_index]["faceta"]

    n_items = _facet_n_items(scale_ref, str(sel_fac))
    max_per_item = _infer_max_per_item(scale_ref)

    row_sel = df_master.loc[df_master["faceta"] == sel_fac].iloc[0]
    mean_ref = float(row_sel["mean_ref"]) if pd.notna(row_sel.get("mean_ref")) else None
    sd_ref = float(row_sel["sd_ref"]) if pd.notna(row_sel.get("sd_ref")) else None
    raw_sum = float(row_sel["bruta"]) if pd.notna(row_sel.get("bruta")) else None

    if mean_ref is None or sd_ref in (None, 0) or raw_sum is None:
        st.info("Não há informações suficientes (média/DP de referência e/ou pontuação bruta) para plotar esta faceta.")
        st.stop()

    metric = "mean_items" if use_item_mean_for_z(scale_ref) else "raw_sum"
    spec = NormSpec(
        mean_ref=mean_ref,
        sd_ref=sd_ref,
        metric=metric,
        n_items=int(max(1, n_items)),
        max_per_item=int(max(1, max_per_item)),
    )

    calc = compute_discrete_points(spec, observed_raw_sum=int(raw_sum))
    mu_sum = calc["mu_sum"]
    sd_sum = calc["sd_sum"]
    max_sum = calc["max_sum"]
    pts = calc["points_df"]  # columns: [raw_sum, mean_items, z, percentile]
    obs_pct = calc["observed_percentile"]

    xs = np.linspace(0, max_sum, 500)
    if sd_sum and sd_sum > 0:
        ys = (1.0 / (sd_sum * math.sqrt(2.0 * math.pi))) * np.exp(-0.5 * ((xs - mu_sum) / sd_sum) ** 2)
    else:
        ys = np.zeros_like(xs)

    xk = pts[:, 0]
    yk = (
        (1.0 / (sd_sum * math.sqrt(2.0 * math.pi))) * np.exp(-0.5 * ((xk - mu_sum) / sd_sum) ** 2)
        if sd_sum and sd_sum > 0
        else np.zeros_like(xk)
    )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="lines",
            name="Reference density",
            line=dict(color="#2196F3", width=2),
            hovertemplate="Sum: %{x:.1f}<br>Density: %{y:.4f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=xk,
            y=yk,
            mode="markers",
            name="Discrete points",
            hovertemplate=(
                "Raw sum: %{x}<br>"
                "Item mean: %{customdata[0]:.3f}<br>"
                "Z: %{customdata[1]:.3f}<br>"
                "Percentile: %{customdata[2]:.1f}<extra></extra>"
            ),
            marker=dict(size=6, color="#ffae00", line=dict(width=0)),
            customdata=np.column_stack([pts[:, 1], pts[:, 2], pts[:, 3]]),
        )
    )

    obs = max(0, min(int(raw_sum), int(max_sum)))
    fig.add_vline(x=obs, line_dash="dash", line_color="#FFFFFF", line_width=1)
    if obs_pct is not None:
        fig.add_annotation(
            x=obs,
            y=float(
                (1.0 / (sd_sum * math.sqrt(2.0 * math.pi))) * math.exp(-0.5 * ((obs - mu_sum) / sd_sum) ** 2)
            )
            if sd_sum and sd_sum > 0
            else 0,
            text=f"{obs} • {obs_pct:.1f} pct",
            showarrow=False,
            yshift=14,
        )

    fig.update_layout(
        title=f"{sel_dom} • {sel_fac} — reference distribution and possible points",
        xaxis_title="Raw sum (sum of items)",
        yaxis_title="Density (reference Normal)",
        template="plotly_dark",
        margin=dict(l=10, r=10, t=60, b=10),
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})

    desc_map = (scale_ref.get("facet_descriptions") or {})
    desc = desc_map.get(str(sel_fac))
    classif = str(row_sel["classificacao"]) if pd.notna(row_sel.get("classificacao")) else ""
    if desc:
        st.caption(f"{desc} | **Classificação:** {classif}")
