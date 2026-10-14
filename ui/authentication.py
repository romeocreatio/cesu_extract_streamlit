import streamlit as st


def require_authentication():
    """
    Authentification basique.

    Sources possibles :
    1) Secrets plats Streamlit Cloud :
       - AUTH_USERNAME ou USERNAME
       - AUTH_PASSWORD ou PASSWORD
    2) Secrets sectionnés :
       [auth]
       USERNAME = "..."
       PASSWORD = "..."

    Remarque :
    On évite volontairement os.getenv("USERNAME"), car sous Windows
    cette variable existe déjà et peut entrer en conflit avec
    l'identifiant applicatif.
    """
    username = None
    password = None

    try:
        if not username:
            username = (
                st.secrets.get("AUTH_USERNAME")
                if "AUTH_USERNAME" in st.secrets
                else st.secrets.get(
                    "USERNAME",
                    username,
                )
            )

        if not password:
            password = (
                st.secrets.get("AUTH_PASSWORD")
                if "AUTH_PASSWORD" in st.secrets
                else st.secrets.get(
                    "PASSWORD",
                    password,
                )
            )

        if (
            "auth" in st.secrets
            and (not username or not password)
        ):
            auth_sec = st.secrets["auth"]

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
        st.warning(
            "Authentification non configurée — "
            "accès non protégé."
        )
        return

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return

    st.title(
        "🔐 Authentification requise"
    )

    in_user = st.text_input(
        "Identifiant"
    )

    in_pass = st.text_input(
        "Mot de passe",
        type="password",
    )

    login = st.button(
        "Se connecter"
    )

    if login:
        if (
            in_user == username
            and in_pass == password
        ):
            st.session_state.authenticated = True
            st.success(
                "Connexion réussie ✅"
            )
            st.rerun()
        else:
            st.error(
                "Identifiants incorrects ❌"
            )

    st.stop()
