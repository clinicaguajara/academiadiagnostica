
# --- IMPORTAÇÕES NECESSÁRIAS ---

import json
import streamlit as st

from pathlib        import Path
from modules.scales import render_results_with_reference
from utils.design   import inject_custom_css

# --- FUNÇÕES ---


# --- CONFIGURAÇÕES DA PÁGINA ---

st.set_page_config(
    page_title="Relatórios",
    page_icon="📝",
    layout="centered"
)

inject_custom_css()

def buscar_arquivo_da_escala(nome_escala: str, pasta: str = "scales") -> Path:
    for path in Path(pasta).glob("*.json"):
        with open(path, "r", encoding="utf-8") as f:
            escala = json.load(f)
            if escala.get("name", "").strip().lower() == nome_escala.strip().lower():
                return path
    return None

# --- Identifica escalas respondidas na sessão ---

escalas_respondidas = st.session_state.get("escalas_respondidas", {})
opcoes_escalas = list(escalas_respondidas.keys())

if not opcoes_escalas:
    st.warning("⚠️ Nenhuma escala foi respondida durante a sessão.")
else:
    # --- Usuário escolhe qual escala deseja visualizar ---
    st.title("Correções Automáticas")
    st.markdown(
        "<h2 style='color:#FFB300;'>Selecione a escala e o estudo normativo</h2>",
        unsafe_allow_html=True
    )
    st.divider()

    escala_escolhida = st.selectbox("Escalas respondidas durante a sessão:", opcoes_escalas)

    # --- Carrega JSON da escala correspondente ---
    path_escala = buscar_arquivo_da_escala(escala_escolhida)
    if not path_escala:
        st.error(f"Arquivo de definição da escala '{escala_escolhida}' não encontrado.")
    else:
        with open(path_escala, "r", encoding="utf-8") as f:
            escala_json = json.load(f)

        # --- Mapeia normas compatíveis com a escala escolhida ---
        path_data = Path("data")
        normas_opcoes = {}

        for norma_path in path_data.glob("*.json"):
            with open(norma_path, "r", encoding="utf-8") as f:
                norma = json.load(f)
                if norma.get("name", "").lower() == escala_escolhida.lower():
                    referencia = norma.get("referencia", norma_path.stem)
                    normas_opcoes[referencia] = norma

        if not normas_opcoes:
            st.warning(f"⚠️ Nenhuma norma encontrada para a escala '{escala_escolhida}'.")
        else:
            # --- Renderiza interface interativa com referência e percentil ---
            render_results_with_reference(escala_escolhida, escala_json, normas_opcoes)