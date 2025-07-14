
# --- IMPORTAÇÕES NECESSÁRIAS ---

import streamlit as st

from utils.design   import inject_custom_css
from modules.scales import render_scale_selector


# --- CONFIGURAÇÕES DA PÁGINA ---

st.set_page_config(
    page_title="Academia Diagnóstica",
    page_icon="🏛️",
    layout="centered"
)

inject_custom_css()


# --- TÍTULO E LEGIBILIDADE ---

st.title("Academia Diagnóstica")
st.markdown(
    "<h2 style='color:#FFB300;'>Sistema de Correções Informatizadas</h2>",
    unsafe_allow_html=True
)

st.caption("Descubra, compreenda e operacionalize com o novo paradigma unificado dos transtornos mentais.")
st.divider()

# --- ESPAÇO DE RESERVA PARA EXPANSÃO FUTURA ---

render_scale_selector("scales")
