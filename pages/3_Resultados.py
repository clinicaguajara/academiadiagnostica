# pages/3_Resultados.py

# =========================================
# Necessary Iports
# =========================================

from __future__     import annotations

import pandas as pd
import streamlit as st

from pathlib        import Path
from typing         import Any, Dict, List, Tuple, Optional

from utils.global_variables import BLANK
from utils.design           import inject_custom_css
from utils.data_management  import find_bibliography_candidates, find_scale_definition
from utils.global_variables import DOWNLOAD_REPORT_SPINNER_TEXT
from modules.corrections    import (
    score_scales,
    summarize_with_norms,
    build_classification_table,
    use_item_mean_for_z,
    get_norm_group_options_from_facets,
    get_norm_group_description,
)

# =========================================
# Normalization
# =========================================

def _normalize_answers(answers_raw: Dict[Any, Any]) -> Dict[int, Any]:
    """Convert string keys to int and replace empty/sentinel values with None."""
    answers_norm: Dict[int, Any] = {}
    for k, v in answers_raw.items():
        try:
            ik = int(str(k))
        except Exception:
            continue
        answers_norm[ik] = None if v in (None, "", BLANK) else v
    return answers_norm

def _use_item_mean_for_z(scale_ref: Dict[str, Any]) -> bool:
    return use_item_mean_for_z(scale_ref)

def _select_norm_group_from_facets(scale_ref: Dict[str, Any]) -> tuple[str, str]:
    groups, labels = get_norm_group_options_from_facets(scale_ref)
    if groups:
        idx = st.radio(
            "Selecione o grupo normativo",
            options=list(range(len(groups))),
            format_func=lambda i: labels[i],
            horizontal=True,
            index=min(2, len(groups) - 1),
        )
        return groups[idx], labels[idx]

    fallback = [("clinico", "Clínico"), ("comunitario", "Comunitário"), ("total", "Total")]
    idx = st.radio(
        "Selecione o grupo normativo",
        options=list(range(len(fallback))),
        format_func=lambda i: fallback[i][1],
        horizontal=True,
        index=2,
    )
    return fallback[idx]


# =========================================
# Page Rendering
# =========================================

inject_custom_css()

st.title("Correção de Instrumentos")

# 1) Recupera escalas respondidas na sessão
data_key = "escalas_respondidas"
names_key = "escalas_display_names"
all_answers: Dict[str, Dict[Any, Any]] = st.session_state.get(data_key, {})
display_names: Dict[str, str] = st.session_state.get(names_key, {})

if not all_answers:
    st.info("Nenhuma escala respondida encontrada na sessão. Volte e aplique uma escala primeiro.")
    st.stop()

# 2) Seleção da escala aplicada
display_options = []
slug_lookup = {}
for slug, _ans in all_answers.items():
    label = display_names.get(slug, slug)
    display_options.append(label)
    slug_lookup[label] = slug

sel_label = st.selectbox("Selecione o instrumento", sorted(display_options))
scale_key = slug_lookup[sel_label]

answers_raw = all_answers.get(scale_key, {})
if not answers_raw:
    st.error("Não encontrei respostas para essa escala. Verifique o salvamento.")
    st.stop()

# 3) Normaliza respostas (answers_item_ids não é mais necessário)
answers = _normalize_answers(answers_raw)

# 4) Seleção do ESTUDO normativo — match estrito por nome
candidates = find_bibliography_candidates(sel_label)
if not candidates:
    st.warning(
        "Não encontrei estudo normativo cujo campo 'scale' (ou 'name'/'titulo') "
        f"seja idêntico ao nome da escala selecionada: “{sel_label}”.\n\n"
        "Verifique o JSON normativo e se ele está em 'scales/' ou 'bibliography/'."
    )
    st.stop()

labels = [lab for _, __, lab in candidates]
idx_study = st.selectbox("Selecione o estudo normativo", options=list(range(len(labels))), format_func=lambda i: labels[i])
selected_path, scale_ref, _ = candidates[idx_study]

# 5) Grupo normativo (extraído do estudo)
norm_group, norm_label = _select_norm_group_from_facets(scale_ref)
cite = scale_ref.get("cite", None)
if cite:
    st.info(cite, icon="📄")

group_desc = get_norm_group_description(scale_ref, norm_group)
if group_desc:
    st.write(f"{group_desc}")
st.divider()

# 6) Correção por FACETAS (PID-5 e afins)
has_facets = isinstance(scale_ref.get("facets"), dict)

if has_facets:
    try:
        facet_stats = score_scales(scale_ref, answers, use_item_mean=True)
        rows = summarize_with_norms(
            scale_ref,
            facet_stats,
            norm_group=norm_group,
            use_item_mean_for_z=_use_item_mean_for_z(scale_ref),
        )
        df_classif = pd.DataFrame(build_classification_table(scale_ref, rows))
    except Exception as e:
        st.exception(e)
        st.error(
            "Erro durante a correção da escala com facetas. "
            "Revise 'response_map', 'reverse_items' e o bloco de normas (mean/sd) no JSON."
        )
        st.stop()

    study_name = str(scale_ref.get("name") or scale_ref.get("titulo") or Path(selected_path).stem)
    study_ver = str(scale_ref.get("version") or scale_ref.get("versao") or "").strip()


    # 7) DataFrames (visão por domínio + tabelão)
    df_rows = pd.DataFrame(rows)
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
    
    st.markdown(
        "<h3 class='section-title-accent'>Resultados</h3>",
        unsafe_allow_html=True
    ) # Sub-title
    
    for dom in df_master["dominio"].dropna().unique():
        sdf = df_master.loc[df_master["dominio"] == dom, ["faceta", "classificacao"]].reset_index(drop=True)
        sdf = sdf.rename(columns={"faceta": "Faceta", "classificacao": "Classificação"})
        st.markdown(f"**{dom}**")
        st.dataframe(
            sdf,
            use_container_width=True,
            hide_index=True,
            column_config={"Faceta": "Faceta", "Classificação": st.column_config.TextColumn("Classificação")},
        )
    

    # =========================================
    # Tabelão psicométrico
    # =========================================
    show_key = f"show_psy_table::{scale_key}::{norm_group}::{Path(selected_path).name}"
    show_psy = st.session_state.get(show_key, False)
    show_psy = st.toggle("📊 Mostrar tabela psicométrica completa", value=show_psy)
    st.session_state[show_key] = show_psy

    if show_psy:
        st.markdown("### Dados psicomÃ©tricos completos")
        df_big = (
            df_master[
                ["faceta", "dominio", "classificacao", "z", "percentil", "bruta", "media_itens", "mean_ref", "sd_ref"]
            ]
            .rename(columns={
                "faceta": "Faceta",
                "dominio": "DomÃ­nio",
                "classificacao": "ClassificaÃ§Ã£o",
                "z": "Z-score",
                "percentil": "Percentil",
                "bruta": "PontuaÃ§Ã£o bruta",
                "media_itens": "MÃ©dia (itens)",
                "mean_ref": "MÃ©dia ref. (norma)",
                "sd_ref": "DP ref. (norma)",
            })
        )
        df_big["Estudo"] = f"{study_name}{f' ({study_ver})' if study_ver else ''}"
        df_big["Grupo"] = norm_label

        st.dataframe(
            df_big,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Z-score": st.column_config.NumberColumn(format="%.3f"),
                "Percentil": st.column_config.NumberColumn(format="%.1f"),
                "PontuaÃ§Ã£o bruta": st.column_config.NumberColumn(format="%.3f"),
                "MÃ©dia (itens)": st.column_config.NumberColumn(format="%.3f"),
                "MÃ©dia ref. (norma)": st.column_config.NumberColumn(format="%.3f"),
                "DP ref. (norma)": st.column_config.NumberColumn(format="%.3f"),
            },
        )

    # Graphs (moved to a dedicated page)
    # =========================================

    # Save the computed results so the Graphs page can render plots on demand.
    st.session_state["results::context"] = {
        "sel_label": sel_label,
        "scale_key": scale_key,
        "selected_path": str(selected_path),
        "study_name": study_name,
        "study_ver": study_ver,
        "norm_group": norm_group,
        "norm_label": norm_label,
        "df_master": df_master,
        "scale_ref": scale_ref,
    }

    if st.button("Abrir gráficos", use_container_width=True):
        st.switch_page("pages/4_Graficos.py")

    # =========================================
    # Download
    # =========================================
    from utils.pdf_export import build_pdf_table_and_graphs

    with st.spinner(DOWNLOAD_REPORT_SPINNER_TEXT):
        scale_def = find_scale_definition(sel_label)
        scale_items = None
        if isinstance(scale_def, dict):
            items = scale_def.get("items")
            if isinstance(items, list):
                scale_items = items

        pdf_bytes, pdf_name = build_pdf_table_and_graphs(
            sel_label=sel_label,
            study_name=study_name,
            study_ver=study_ver,
            norm_label=norm_label,
            df_master=df_master,
            scale_ref=scale_ref,
            answers_raw=answers_raw,
            scale_items=scale_items,
        )

    st.download_button(
        label="Download (Relatório Completo)",
        data=pdf_bytes,
        file_name=pdf_name,
        mime="application/pdf",
        use_container_width=True,
    )

else:
    # Aqui é onde plugaríamos o pipeline de escalas **sem** facetas (ex.: AQ-50, BIS-11 etc.)
    st.warning(
        "Esta escala não possui 'facets' no estudo selecionado. "
        "Pipelines de correção variam por instrumento; vamos plugar aqui a rotina específica "
        "(ex.: subescalas, percentis próprios, cortes clínicos)."
    )
