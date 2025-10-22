# pages/1_Personalidade.py

# =========================================
# Necessary imports and utilities
# =========================================

import streamlit as st

from utils.design            import inject_custom_css
from modules.scales_selector import render_scale_selector
from utils.global_variables   import SCALES_DIR

# =========================================
# Page configuration
# =========================================

st.set_page_config(
    page_title="Personalidade",
    page_icon="🎭",
    layout="centered"
)

inject_custom_css()

# =========================================
# Page drawing
# =========================================

# Page title and description
st.title("Personalidade")

st.markdown(
    "<h3 style='color:#ffd000;'>Operacionalize com o Modelo Dimensional</h3>",
    unsafe_allow_html=True
)

st.markdown(
    """
    <p style='text-align: justify;'>
    O escopo teórico dos instrumentos para avaliação da personalidade desta seção são estruturados segundo o Modelo Alternativo para Transtornos da Personalidade (AMPD),
    proposto na Seção III do Manual Diagnóstico e Estatístico de Transtornos Mentais – DSM-5 (APA, 2013).
    Esse modelo adota uma perspectiva dimensional, enfatizando a avaliação de traços patológicos de personalidade
    organizados em cinco domínios amplos e 25 facetas específicas.
    </p>
    """,
    unsafe_allow_html=True
)

st.info("""
**📄 Referência:**

American Psychiatric Association. (2013). *Diagnostic and Statistical Manual of Mental Disorders* (5ª ed., Seção III). Arlington, VA: American Psychiatric Publishing.
""")

render_scale_selector(SCALES_DIR, category="personality", strict=True)