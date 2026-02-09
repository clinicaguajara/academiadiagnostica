# pages/2_Desenvolvimento.py

# =========================================
# Necessary Imports
# =========================================

import streamlit as st

from utils.design            import inject_custom_css
from modules.scales_selector import render_scale_selector
from utils.global_variables  import SCALES_DIR

# =========================================
# Page Configuration
# =========================================

st.set_page_config(
    page_title="Desenvolvimento",
    page_icon="🧩",
    layout="centered",
)

# Custom CSS injection
inject_custom_css()

# =========================================
# Page Rendering
# =========================================

# Page title and description
st.title("Desenvolvimento")

st.markdown(
    "<h3 class='section-title-accent'>Cognição e Comportamentos Autorrelatados</h3>",
    unsafe_allow_html=True,
)

st.markdown(
    """
    <p class='text-justify'>
    Esta seção reúne instrumentos voltados ao rastreamento de características associadas ao neurodesenvolvimento
    (ex.: TDAH, autismo, e outros perfis).
    Os resultados têm finalidade informativa e devem ser interpretados no contexto clínico, considerando entrevista,
    história do desenvolvimento e outras fontes de informação.
    </p>
    """,
    unsafe_allow_html=True,
)

# Render scale selector for development instruments
render_scale_selector(SCALES_DIR, category="development")
