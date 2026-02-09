# pages/1_Personalidade.py

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
    page_title="Personalidade",
    page_icon="🎭",
    layout="centered"
)

inject_custom_css()

# =========================================
# Page Rendering
# =========================================

# Page title and description
st.title("Personalidade")

st.markdown(
    "<h3 class='section-title-accent'>Operacionalize com o Modelo Dimensional</h3>",
    unsafe_allow_html=True
)

st.markdown(
    """
    <p class='text-justify'>
    O escopo teórico dos instrumentos para avaliação da personalidade deste aplicativo são estruturados segundo o Modelo Alternativo para Transtornos da Personalidade (AMPD),
    proposto na Seção III do Manual Diagnóstico e Estatístico de Transtornos Mentais – DSM-5 (APA, 2022).
    Esse modelo adota uma perspectiva dimensional, enfatizando a avaliação de traços patológicos de personalidade
    organizados em cinco domínios amplos e 25 facetas específicas.
    </p>
    """,
    unsafe_allow_html=True
)

st.info("""
**📄 Referência:**

American Psychiatric Association. (2022). Diagnostic and Statistical Manual of Mental Disorders, 5th ed., text rev. American Psychiatric Publishing.

""")

# Render scale selector for personality instruments
render_scale_selector(SCALES_DIR, category="personality")
