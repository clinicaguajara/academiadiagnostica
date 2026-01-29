# pages/2_Autismo.py

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
    page_title="Autismo",
    page_icon="🧩",
    layout="centered",
)

# Custom CSS injection
inject_custom_css()

# =========================================
# Page Rendering
# =========================================

# Page title and description
st.title("Autismo")

st.markdown(
    "<h3 class='section-title-accent'>Rastreamento de traços do espectro autista</h3>",
    unsafe_allow_html=True,
)

st.markdown(
    """
    <p class='text-justify'>
    Esta seção reúne instrumentos de autorrelato voltados ao rastreamento de características associadas ao Transtorno do Espectro Autista (TEA).
    Os resultados têm finalidade informativa e devem ser interpretados no contexto clínico, considerando entrevista, história do desenvolvimento e outras fontes de conhecimento e atuação profissional.
    </p>
    """,
    unsafe_allow_html=True,
)

# Render scale selector for autism instruments
render_scale_selector(SCALES_DIR, category="autism")
