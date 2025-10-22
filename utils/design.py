# utils/design.py

# =========================================
# Necessary imports and utilities
# =========================================

import streamlit as st

from pathlib import Path

# =========================================
# Custom CSS injection
# =========================================

def inject_custom_css():
    css_path = Path("assets/style.css")
    if css_path.exists():
        # forçar UTF-8 para não dar UnicodeDecodeError no Windows
        with open(css_path, encoding="utf-8") as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    
    inject_scale_form_css()

def inject_scale_form_css():
    """Injeta o CSS específico para os formulários de escalas, apenas uma vez."""
    key = "_styles_scales_forms"
    if not st.session_state.get(key):
        st.markdown("""
        <style>
        .item-badge{
            display:inline-block;
            background:#2196F3;
            color:#fff;
            border:1px solid #0b74d6;
            border-radius:10px;
            padding:2px 10px;
            font-weight:700;
            min-width:2.4rem;
            text-align:center;
        }
        .item-row{ display:flex; align-items:flex-start; gap:.6rem; margin:.4rem 0 .2rem 0; }
        .item-text{ flex:1; }
        </style>
        """, unsafe_allow_html=True)
        st.session_state[key] = True