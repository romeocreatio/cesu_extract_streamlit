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

AUTH_CSS_PATH = (
    PROJECT_ROOT
    / "assets"
    / "authentication.css"
)


def _load_authentication_styles():
    if not AUTH_CSS_PATH.exists():
        return

    css = AUTH_CSS_PATH.read_text(
        encoding="utf-8"
    )

    st.markdown(
        f"<style>{css}</style>",
        unsafe_allow_html=True,
    )


def _render_login(
    username: str,
    password: str,
):
    _load_authentication_styles()

    left, center, right = st.columns(
        [1, 1.15, 1]
    )

    with center:
        if LOGO_PATH.exists():
            logo_left, logo_center, logo_right = (
                st.columns(
                    [1, 1, 1]
                )
            )

            with logo_center:
                st.image(
                    str(LOGO_PATH),
                    use_container_width=True,
                )

        st.markdown(
            """
            <div class="cesu-login-header">
                <div class="cesu-login-title">
                    Analyse des rapports qualité
                </div>
                <div class="cesu-login-subtitle">
                    Centre d'Enseignement des Soins d'Urgence 83
                </div>
                <div class="cesu-login-description">
                    Extraction · Synthèse · Suivi qualité
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container(
            border=True
        ):
            st.markdown(
                """
                <div class="cesu-login-card-title">
                    Connexion
                </div>
                """,
                unsafe_allow_html=True,
            )

            in_user = st.text_input(
                "Identifiant",
                key="auth_username_input",
            )

            in_pass = st.text_input(
                "Mot de passe",
                type="password",
                key="auth_password_input",
            )

            login = st.button(
                "Se connecter",
                type="primary",
                use_container_width=True,
            )

            if login:
                if (
                    in_user == username
                    and in_pass == password
                ):
                    st.session_state.authenticated = True
                    st.rerun()

                st.error(
                    "Identifiant ou mot de passe incorrect. "
                    "Vérifiez vos informations puis réessayez."
                )

        st.markdown(
            """
            <div class="cesu-login-footer">
                Accès réservé — CESU 83
            </div>
            """,
            unsafe_allow_html=True,
        )


def require_authentication():
    """
    Authentification applicative CESU 83.

    Sources possibles :
    1) Secrets plats Streamlit Cloud :
       - AUTH_USERNAME ou USERNAME
       - AUTH_PASSWORD ou PASSWORD
    2) Secrets sectionnés :
       [auth]
       USERNAME = "..."
       PASSWORD = "..."
    """
    username = None
    password = None

    try:
        if not username:
            username = (
                st.secrets.get(
                    "AUTH_USERNAME"
                )
                if "AUTH_USERNAME" in st.secrets
                else st.secrets.get(
                    "USERNAME",
                    username,
                )
            )

        if not password:
            password = (
                st.secrets.get(
                    "AUTH_PASSWORD"
                )
                if "AUTH_PASSWORD" in st.secrets
                else st.secrets.get(
                    "PASSWORD",
                    password,
                )
            )

        if (
            "auth" in st.secrets
            and (
                not username
                or not password
            )
        ):
            auth_sec = st.secrets[
                "auth"
            ]

            if not username:
                username = auth_sec.get(
                    "USERNAME"
                )

            if not password:
                password = auth_sec.get(
                    "PASSWORD"
                )

    except Exception:
        pass

    if not username or not password:
        st.error(
            "Configuration de sécurité incomplète. "
            "L'accès à l'application est bloqué."
        )
        st.stop()

    if (
        "authenticated"
        not in st.session_state
    ):
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return

    _render_login(
        username,
        password,
    )

    st.stop()
