from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

LOGO_PATH = (
    PROJECT_ROOT
    / "assets"
    / "logo_cesu83.jpeg"
)

APP_CSS_PATH = (
    PROJECT_ROOT
    / "assets"
    / "app.css"
)


def _load_app_styles():
    if not APP_CSS_PATH.exists():
        return

    css = APP_CSS_PATH.read_text(
        encoding="utf-8"
    )

    st.markdown(
        f"<style>{css}</style>",
        unsafe_allow_html=True,
    )


def render_phase_intro(
    number: int,
    title: str,
    description: str,
):
    st.markdown(
        (
            '<div class="cesu-phase-header">'
            f'<div class="cesu-phase-title">'
            f'<span class="cesu-phase-number">{number}</span>'
            f'{title}'
            '</div>'
            f'<div class="cesu-phase-description">'
            f'{description}'
            '</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def render_app_header():
    _load_app_styles()

    col_logo, col_title, col_logout = st.columns(
        [0.8, 5.2, 1.2],
        vertical_alignment="center",
    )

    with col_logo:
        if LOGO_PATH.exists():
            st.image(
                str(LOGO_PATH),
                width=90,
            )

    with col_title:
        st.markdown(
            """
            <div class="cesu-app-title">
                Analyse des rapports qualité
            </div>
            <div class="cesu-app-subtitle">
                Centre d'Enseignement des Soins d'Urgence 83
            </div>
            <div class="cesu-app-description">
                Extraction · Synthèse · Suivi qualité
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_logout:
        if st.button(
            "Se déconnecter",
            use_container_width=True,
            key="logout_button",
        ):
            st.session_state.authenticated = False
            st.rerun()

    process_html = (
        '<div class="cesu-process">'
        '<div class="cesu-process-step">'
        '<span class="cesu-process-number">1</span>'
        '<span class="cesu-process-title">'
        'Analyse du rapport'
        '</span>'
        '<span class="cesu-process-description">'
        'Importer et contrôler le rapport qualité'
        '</span>'
        '</div>'
        '<div class="cesu-process-step">'
        '<span class="cesu-process-number">2</span>'
        '<span class="cesu-process-title">'
        'Synthèse'
        '</span>'
        '<span class="cesu-process-description">'
        'Analyser et synthétiser les données qualité'
        '</span>'
        '</div>'
        '<div class="cesu-process-step">'
        '<span class="cesu-process-number">3</span>'
        '<span class="cesu-process-title">'
        'Intégration'
        '</span>'
        '<span class="cesu-process-description">'
        'Ajouter les données au suivi qualité'
        '</span>'
        '</div>'
        '</div>'
        '<hr class="cesu-app-divider">'
    )

    st.markdown(
        process_html,
        unsafe_allow_html=True,
    )
