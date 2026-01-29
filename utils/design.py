# utils/design.py

# =========================================
# Necessary imports
# =========================================

import streamlit as st

from pathlib import Path

# =========================================
# Custom CSS injection
# =========================================

def inject_custom_css():
    css_path = Path("assets/style.css")
    if css_path.exists():

        # Force UTF-8 to avoid UnicodeDecodeError on Windows
        with open(css_path, encoding="utf-8") as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
