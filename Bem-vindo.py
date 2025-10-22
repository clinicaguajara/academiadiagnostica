# Bem-vindo.py

# =========================================
# Necessary imports and utilities
# =========================================

import streamlit as st

from utils.design           import inject_custom_css

# =========================================
# Page configuration
# =========================================

st.set_page_config(
    page_title="Sistema de Correções Informatizadas",
    page_icon="💻",
    layout="centered"
)

# Custom CSS injection
inject_custom_css()

# =========================================
# Page drawing
# =========================================

# Page title and description
st.title("Bem-vindo(a)")

st.markdown(
    "<h3 style='color:#ffd000;'>Sistema de Correções Informatizadas</h3>",
    unsafe_allow_html=True
)

st.markdown(
    """
    <p style='text-align: justify;'>
    O conteúdo e os resultados apresentados neste aplicativo têm finalidade exclusivamente informativa e educacional. 
    As interpretações geradas baseiam-se em dados psicométricos e modelos normativos, 
    não devendo ser utilizadas isoladamente para fins diagnósticos, clínicos ou jurídicos. 
    A análise diagnóstica adequada requer avaliação profissional conduzida por especialistas devidamente qualificados por área de atuação clínica.
    </p>
    """,
    unsafe_allow_html=True
)

st.divider()

# Sub-section title
st.markdown(
    "<h4 style='color: white;'>Instrumentos disponíveis</h4>",
    unsafe_allow_html=True
)

# Buttons for navigation
col1, col2 = st.columns(2)
with col1:
    if st.button("Personalidade", use_container_width=True):
        st.switch_page("pages/1_Personalidade.py")
with col2:
    if st.button("Autismo", use_container_width=True):
        st.switch_page("pages/2_Autismo.py")

