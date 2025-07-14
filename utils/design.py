# utils/styling.py

import streamlit as st
from pathlib import Path

def inject_custom_css():
    css_path = Path("assets/style.css")  # ou onde estiver
    if css_path.exists():
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
