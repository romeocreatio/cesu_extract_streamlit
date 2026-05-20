# streamlit_app.py

import os
import json
import re
from pathlib import Path
import hashlib

import streamlit as st

# phase 1
from utils.pdf_reader import read_pdf_all_text
from utils.llm_client import load_prompt, call_llm_extract_json
from utils.schema import OutputPayload  # v2.2

# phase 2
from utils.convert_v2_to_excel import generate_json_excel

# phase 3
from utils.google_sheets_writer import append_json_to_google_sheet


# =====================================================
# 🔐 Authentification simple via secrets
# =====================================================

def check_auth():
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
    On évite volontairement os.getenv("USERNAME"), car sous Windows cette variable
    existe déjà et peut entrer en conflit avec l'identifiant applicatif.
    """
    username = None
    password = None

    try:
        if not username:
            username = (
                st.secrets.get("AUTH_USERNAME")
                if "AUTH_USERNAME" in st.secrets
                else st.secrets.get("USERNAME", username)
            )

        if not password:
            password = (
                st.secrets.get("AUTH_PASSWORD")
                if "AUTH_PASSWORD" in st.secrets
                else st.secrets.get("PASSWORD", password)
            )

        if ("auth" in st.secrets) and (not username or not password):
            auth_sec = st.secrets["auth"]

            if not username:
                username = auth_sec.get("USERNAME")

            if not password:
                password = auth_sec.get("PASSWORD")

    except Exception:
        pass

    if not username or not password:
        st.warning("Authentification non configurée — accès non protégé.")
        return

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return

    st.title("🔐 Authentification requise")
    in_user = st.text_input("Identifiant")
    in_pass = st.text_input("Mot de passe", type="password")
    login = st.button("Se connecter")

    if login:
        if in_user == username and in_pass == password:
            st.session_state.authenticated = True
            st.success("Connexion réussie ✅")
            st.rerun()
        else:
            st.error("Identifiants incorrects ❌")

    st.stop()


# =====================================================
# ⚙️ Config Streamlit
# =====================================================

st.set_page_config(
    page_title="CESU 83 - Extracteur Qualité",
    page_icon="🩺",
    layout="wide",
)

check_auth()


# =====================================================
# 🔧 Helpers extraction / correction
# =====================================================

def get_secret_value(name: str, default: str | None = None) -> str | None:
    """
    Lit une valeur dans Streamlit Secrets, puis dans les variables
    d'environnement si elle n'existe pas.
    """
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass

    return os.getenv(name, default)


def _safe_float(x):
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).replace(",", ".").strip().replace("%", "")
        return float(s)
    except Exception:
        return None


def _fmt_votants(count):
    if count is None:
        return None
    try:
        return f"{int(round(float(count)))} votants"
    except Exception:
        return None


def _normalize_satisfaction_labels(v2: dict) -> None:
    mapping = {
        "Très satisfait-e": "Très satisfait(e)",
        "Tres satisfait(e)": "Très satisfait(e)",
        "Satisfait-e": "Satisfait(e)",
        "Déçu-e": "Déçu(e)",
        "Deçu(e)": "Déçu(e)",
        "Sans-opinion": "Sans opinion",
        "Sans opinion ": "Sans opinion",
    }

    a_ch = v2.get("a_chaud") or {}
    items = a_ch.get("satisfaction_contenu") or []

    for it in items or []:
        lbl = it.get("label")
        if lbl in mapping:
            it["label"] = mapping[lbl]


def _coerce_int_from_votants(s: str):
    if not isinstance(s, str):
        return None

    m = re.search(r"(\d+)\s+votant", s)
    return int(m.group(1)) if m else None


def fill_missing_percentages_from_counts(v2: dict) -> None:
    """
    Dans pre_formation.souhaitez_vous_suivre_distribution,
    si pourcentage == null mais on a "N votants" + total => calcule %.
    """
    pre = v2.get("pre_formation") or {}
    vol = pre.get("volonte_suivi_formation") or {}
    total = vol.get("nb votants") or vol.get("nb_votants") or None
    dist = pre.get("souhaitez_vous_suivre_distribution") or []

    if not total or not isinstance(dist, list):
        return

    total = float(total)

    for item in dist:
        if not isinstance(item, dict):
            continue

        keys = [k for k in item.keys() if k.startswith("echele ")]

        if not keys:
            continue

        k = keys[0]
        n = _coerce_int_from_votants(item.get(k))

        if n is None:
            continue

        if item.get("pourcentage") is None:
            pct = round((n / total) * 100, 1)
            item["pourcentage"] = pct


def map_old_payload_to_v2(json_result: dict, full_text: str) -> dict:
    """
    Transforme un JSON ancien vers v2.1. Si déjà v2/v2.1, renvoie inchangé.
    """
    pre = (json_result or {}).get("pre_formation") or {}

    if "volonte_suivi_formation" in pre:
        out = json_result
    else:
        out = {
            "Nom formation": json_result.get("Nom formation"),
            " semestre": json_result.get(" semestre"),
            "pre_formation": None,
            "a_chaud": None,
            "a_froid": None,
            "intervenants": json_result.get("intervenants"),
            "resultats_evaluations": json_result.get("resultats_evaluations"),
            "lien_vers_formation": json_result.get("lien_vers_formation"),
        }

        old_pre = json_result.get("pre_formation") or {}
        svs = old_pre.get("souhaitez_vous_suivre") or {}
        voters_total = svs.get("voters_total") or svs.get("votants") or None
        old_dist = old_pre.get("souhaitez_vous_suivre_distribution")

        target_labels = ["5", "4", "3", "2", "1"]
        idx = {
            str(d.get("label")): d
            for d in (old_dist or [])
            if isinstance(d, dict)
        }

        v2_dist = []

        for lab in target_labels:
            d = idx.get(lab, {})
            item = {
                f"echele {lab}": _fmt_votants(d.get("count")),
                "pourcentage": _safe_float(d.get("percent")),
            }
            v2_dist.append(item)

        sujets = (
            old_pre.get("sujets_a_aborder")
            or old_pre.get("demande_sujets_a_aborder")
            or None
        )

        mpo = (
            old_pre.get("maitrise_objectifs")
            or old_pre.get("maitrise_objectifs_preformation")
            or {}
        )

        v2_pre_mo = {
            "mode": mpo.get("mode"),
            "par_objectif": mpo.get("par_objectif"),
            "note_globale_objectifs_preformation": (
                mpo.get("note_globale_objectifs_sur_10")
                or mpo.get("note_globale_objectifs_preformation")
            ),
        }

        out["pre_formation"] = {
            "volonte_suivi_formation": {"nb votants": voters_total},
            "souhaitez_vous_suivre_distribution": v2_dist,
            "demande_sujets_a_aborder": sujets,
            "maitrise_objectifs_preformation": v2_pre_mo,
        }

        old_hot = json_result.get("a_chaud") or {}

        out["a_chaud"] = {
            "formation_profitable": old_hot.get("profitable"),
            "satisfaction_contenu": old_hot.get("satisfaction_contenu"),
            "note_globale_a_chaud": (
                old_hot.get("impression_globale_note_sur_10")
                or old_hot.get("note_globale_a_chaud")
            ),
            "points_forts": old_hot.get("points_forts"),
            "points_a_ajuster": old_hot.get("points_a_ajuster"),
            "suggestions_complement_sur_formation": (
                old_hot.get("suggestions_complement")
                or old_hot.get("suggestions_complement_sur_formation")
            ),
            "appreciations_intervenants": old_hot.get("appreciations_intervenants"),
            "maitrise_objectifs_a_chaud": {
                "mode": (old_hot.get("maitrise_objectifs") or {}).get("mode"),
                "par_objectif": (old_hot.get("maitrise_objectifs") or {}).get("par_objectif"),
                "note_globale_objectifs_a_chaud": (
                    old_hot.get("maitrise_objectifs") or {}
                ).get("note_globale_objectifs_sur_10"),
            }
            if old_hot.get("maitrise_objectifs")
            else None,
        }

        old_cold = json_result.get("a_froid") or {}

        out["a_froid"] = {
            "note_sur_10": old_cold.get("note_sur_10"),
            "maitrise_objectifs_a_froid": {
                "mode": (old_cold.get("maitrise_objectifs") or {}).get("mode"),
                "par_objectif": (old_cold.get("maitrise_objectifs") or {}).get("par_objectif"),
                "note_globale_objectifs_a_froid": (
                    (old_cold.get("maitrise_objectifs") or {}).get(
                        "note_globale_objectifs_sur_10"
                    )
                    or old_cold.get("note_globale_objectifs_a_froid")
                ),
            }
            if old_cold.get("maitrise_objectifs")
            or old_cold.get("maitrise_objectifs_a_froid")
            else None,
            "elements_les_plus_utiles": old_cold.get("elements_les_plus_utiles"),
        }

    _normalize_satisfaction_labels(out)
    fill_missing_percentages_from_counts(out)
    out["version_prompt"] = "v2.1"

    return out


def _payload_hash(d: dict) -> str:
    raw = json.dumps(d, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


# =====================================================
# 🧩 Interface Streamlit
# =====================================================

project_root = Path(__file__).parent
logo_path = project_root / "assets" / "logo_cesu83.jpeg"

col_logo, col_title, col_spacer = st.columns([1, 2, 1])

with col_logo:
    if logo_path.exists():
        st.image(str(logo_path), use_container_width=100)
    else:
        st.markdown(
            "<div style='padding:14px;border:1px dashed #bbb;border-radius:8px;text-align:center;'>"
            "Logo manquant<br><code>assets/logo_cesu83.jpeg</code></div>",
            unsafe_allow_html=True,
        )

with col_title:
    st.markdown(
        "<h2 style='text-align:center;margin-top:0;'> CESU 83 — Extracteur de Rapports Qualité </h2>",
        unsafe_allow_html=True,
    )

st.markdown("---")


# =====================================================
# Phase 1 — Analyse du rapport qualité
# =====================================================

def build_model_candidates(nom_formation: str, is_large_pdf: bool) -> list[str]:
    """
    Définit l'ordre des modèles à essayer automatiquement.
    Objectif : éviter de bloquer l'utilisateur final si un modèle échoue.
    """
    standard_model = get_secret_value("OPENAI_MODEL", "gpt-4.1-mini")
    large_model = get_secret_value("OPENAI_MODEL_LARGE", "gpt-4.1-mini-long-context")
    reliable_model = get_secret_value("OPENAI_MODEL_RELIABLE", "gpt-4.1")

    formation_upper = (nom_formation or "").upper()

    if "AFGSU" in formation_upper:
        candidates = [
            reliable_model,
            large_model,
            standard_model,
        ]
    elif is_large_pdf:
        candidates = [
            large_model,
            reliable_model,
            standard_model,
        ]
    else:
        candidates = [
            standard_model,
            large_model,
            reliable_model,
        ]

    deduped = []
    for model in candidates:
        if model and model not in deduped:
            deduped.append(model)

    return deduped


st.subheader("Phase 1 - Analyse du rapport qualité Digiforma")

with st.form("meta_form", clear_on_submit=False):
    c1, c2 = st.columns(2)

    with c1:
        nom_formation = st.text_input("Nom de la formation", placeholder="ex: AFGSU 1")

    with c2:
        semestre = st.text_input("Semestre", placeholder="ex: S1 2025")

    uploaded_pdf = st.file_uploader("Charger le rapport qualité", type=["pdf"])
    submitted = st.form_submit_button(
        "Analyser le rapport",
        use_container_width=True,
        type="primary",
    )

if submitted:
    if not uploaded_pdf or not nom_formation or not semestre:
        st.error("Veuillez renseigner le nom de la formation, le semestre, et charger un rapport PDF.")
        st.stop()

    file_bytes = uploaded_pdf.read()

    with st.spinner("Lecture du rapport en cours..."):
        full_text, pages_text, used_ocr = read_pdf_all_text(file_bytes)

        page_count = len(pages_text)
        char_count = len(full_text)

        is_large_pdf = page_count > 80 or char_count > 180000

        model_candidates = build_model_candidates(
            nom_formation=nom_formation,
            is_large_pdf=is_large_pdf,
        )

        if is_large_pdf:
            st.info(
                f"Rapport détaillé détecté : {page_count} pages, "
                f"{char_count:,} caractères.\n\n"
                "Traitement avancé en cours."
            )
        else:
            st.info(
                f"Rapport standard détecté : {page_count} pages, "
                f"{char_count:,} caractères.\n\n"
                "Analyse automatique en cours."
            )

    # Aperçu du texte lu masqué en production.
    # Bloc utile uniquement pour debug développeur :
    # with st.expander("🔎 Aperçu du texte lu (pré-traitement)", expanded=False):
    #     st.markdown(f"**OCR utilisé :** {'✅ Oui' if used_ocr else '❌ Non'}")
    #     st.text_area(
    #         "Aperçu du texte lu (limité à 20 000 caractères)",
    #         full_text[:20000],
    #         height=300,
    #     )

    prompt_path = project_root / "prompts" / "prompt_reference.txt"

    try:
        prompt_master = load_prompt(str(prompt_path))
    except Exception as e:
        st.error(f"Impossible de charger le prompt de référence : {e}")
        st.stop()

    last_error = None
    json_result = None
    model_used = None

    with st.spinner("Analyse du rapport en cours..."):
        for model_name in model_candidates:
            try:
                json_result = call_llm_extract_json(
                    prompt_master,
                    full_text,
                    meta={
                        "nom_formation": nom_formation,
                        "semestre": semestre,
                        "filename": uploaded_pdf.name,
                        "page_count": page_count,
                        "char_count": char_count,
                        "is_large_pdf": is_large_pdf,
                        "model_attempted": model_name,
                    },
                    model_override=model_name,
                )

                model_used = model_name
                break

            except Exception as e:
                last_error = e
                continue

    if json_result is None:
        st.error(
            "L'analyse du rapport n'a pas pu être finalisée automatiquement. "
            "Le rapport semble trop complexe ou trop volumineux pour le traitement actuel."
        )
        if last_error:
            st.exception(last_error)
        st.stop()

    # Message discret, sans exposer le modèle technique à l'utilisateur métier
    st.caption("Traitement finalisé avec le mode d’analyse adapté.")

    json_result["Nom formation"] = nom_formation
    json_result[" semestre"] = semestre
    json_result["lien_vers_formation"] = uploaded_pdf.name

    v2_payload = map_old_payload_to_v2(json_result, full_text)

    try:
        validated = OutputPayload.model_validate(v2_payload)
    except Exception as e:
        st.error("Le rapport a été lu, mais les données extraites ne respectent pas le format attendu.")
        st.exception(e)
        st.stop()

    DIR_JSON_V2 = project_root / "json_v2"
    DIR_JSON_V2.mkdir(exist_ok=True)

    safe_name = f"{nom_formation.strip().replace(' ', '_')}_{semestre.strip().replace(' ', '_')}.json"

    payload_dict_full = validated.model_dump(by_alias=True, exclude_none=False)
    payload_dict = validated.model_dump(by_alias=True, exclude_none=True)

    json_str = json.dumps(payload_dict, ensure_ascii=False, indent=2)

    path_v2 = DIR_JSON_V2 / safe_name
    path_v2.write_text(json_str, encoding="utf-8")

    st.success(
        "✅ Analyse du rapport réussie. "
        "Les données ont été extraites avec succès. "
        "Vous pouvez passer à la Phase 2 pour structurer les données."
    )

    # Aperçu JSON masqué en production.
    # with st.expander("🧾 Aperçu du schéma", expanded=False):
    #     st.code(json_str, language="json")

    def _is_missing_or_empty(x):
        if x is None:
            return True
        if isinstance(x, dict) and len(x) == 0:
            return True
        if isinstance(x, list) and len(x) == 0:
            return True
        return False

    missing_msgs = []
    sections_to_check = [
        "pre_formation",
        "a_chaud",
        "a_froid",
        "intervenants",
        "resultats_evaluations",
    ]

    for section in sections_to_check:
        val_full = payload_dict_full.get(section)
        if _is_missing_or_empty(val_full):
            kind = "absente (null)" if val_full is None else "présente mais vide"
            missing_msgs.append(f"Section **{section}** {kind}.")

    if missing_msgs:
        with st.expander("⚠️ Avertissements — Sections manquantes ou vides", expanded=False):
            for msg in missing_msgs:
                st.markdown(f"- {msg}")

    # Masqué en prod
    # st.download_button(
    #     label="📥 Télécharger le fichier d’analyse",
    #     data=json_str,
    #     file_name=safe_name,
    #     mime="application/json",
    #     use_container_width=True,
    # )

st.markdown("---")


# =====================================================
# Phase 2 — Structuration des données
# =====================================================

st.subheader("Phase 2 - Structuration des données")

DIR_JSON_V2 = project_root / "json_v2"
DIR_JSON_EXCEL = project_root / "json_excel"
DIR_JSON_EXCEL.mkdir(exist_ok=True)


@st.cache_data(ttl=30)
def list_json_v2_files():
    if not DIR_JSON_V2.exists():
        return []
    return sorted([p.name for p in DIR_JSON_V2.glob("*.json")])


files = list_json_v2_files()

if not files:
    st.info(
        """
        ℹ️ Aucun fichier d'analyse n'est disponible pour le moment.

        Pour utiliser la Phase 2, vous devez d'abord exécuter la Phase 1 :
        1. Renseigner le nom de la formation.
        2. Indiquer le semestre et l'année.
        3. Charger le rapport qualité Digiforma au format PDF.
        4. Cliquer sur « Analyser le rapport ».

        Une fois l'analyse terminée, le fichier sera disponible pour cette étape.
        """
    )
else:
    with st.form("form_excel", clear_on_submit=False):
        c1, c2 = st.columns([2, 1])

        with c1:
            selected = st.selectbox("Choisir un fichier d’analyse :", files, index=0)

        with c2:
            demande_as_list = st.toggle(
                "Sujets en liste",
                value=True,
                help="Si désactivé, une phrase de synthèse sera générée.",
            )

        do_transform = st.form_submit_button(
            "Structurer les données",
            use_container_width=True,
            type="primary",
        )

    if do_transform and selected:
        path_v2 = DIR_JSON_V2 / selected

        try:
            v2_payload = json.loads(path_v2.read_text(encoding="utf-8"))
        except Exception as e:
            st.error(f"Impossible de lire le fichier sélectionné : {e}")
            st.stop()

        with st.spinner("Structuration des données en cours..."):
            json_excel = generate_json_excel(
                v2_payload,
                DEMANDE_AS_LIST=demande_as_list,
            )

        path_excel = DIR_JSON_EXCEL / selected
        path_excel.write_text(
            json.dumps(json_excel, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        st.success(
            "✅ Structuration des données réussie. "
            "Les données sont prêtes pour l’intégration dans le suivi qualité. "
            "Vous pouvez passer à la Phase 3."
        )

        # st.download_button(
        #     "📥 Télécharger le fichier structuré",
        #     data=json.dumps(json_excel, ensure_ascii=False, indent=2),
        #     file_name=path_excel.name,
        #     mime="application/json",
        #     use_container_width=True,
        # )

        # Aperçu JSON Excel masqué en production.
        # with st.expander("Aperçu (json_excel)", expanded=False):
        #     st.json(json_excel, expanded=False)

st.markdown("---")


# =====================================================
# Phase 3 — Intégration Google Sheets
# =====================================================

st.subheader("Phase 3 — Intégration dans le suivi qualité")

json_excel_dir = DIR_JSON_EXCEL
json_excel_dir.mkdir(exist_ok=True)

colL, colR = st.columns([2, 1])

with colL:
    mode = st.radio(
        "Source du fichier structuré",
        ["Depuis le dossier JSON-Excel", "Charger un fichier .json"],
        horizontal=True,
    )

json_payload = None
chosen_name = None

if mode == "Depuis le dossier JSON-Excel":
    files = sorted([f.name for f in json_excel_dir.glob("*.json")])
    chosen_name = st.selectbox("Choisir un fichier structuré", ["— Sélectionner —"] + files)

    if chosen_name and chosen_name != "— Sélectionner —":
        try:
            path_json = json_excel_dir / chosen_name
            json_payload = json.loads(path_json.read_text(encoding="utf-8"))
            st.success("Fichier chargé avec succès.")
        except Exception as e:
            st.error(f"Lecture impossible : {e}")

else:
    up = st.file_uploader("Charger un fichier structuré", type=["json"])

    if up is not None:
        try:
            json_payload = json.load(up)
            chosen_name = getattr(up, "name", "upload.json")
            st.success("Fichier structuré chargé avec succès.")
        except Exception as e:
            st.error(f"Fichier JSON invalide : {e}")

# Aperçu des clés masqué en production.
if json_payload:
    st.caption("Aperçu des clés du JSON Excel détectées :")
    st.code(", ".join(json_payload.keys()), language="text")

if "injected_hashes" not in st.session_state:
    st.session_state.injected_hashes = set()

inject_gs = st.button(
    "📤 Intégrer dans Google Sheets",
    type="primary",
    use_container_width=True,
    disabled=(json_payload is None),
)

if inject_gs and json_payload:
    h = _payload_hash(json_payload)

    if h in st.session_state.injected_hashes:
        st.warning("⚠️ Ce fichier semble déjà avoir été intégré pendant cette session.")
    else:
        with st.spinner("Intégration dans le suivi qualité en cours..."):
            try:
                # La fonction retourne normalement le numéro de ligne insérée
                row_idx = append_json_to_google_sheet(json_payload)

                # Mémorisation pour éviter les doublons pendant la session
                st.session_state.injected_hashes.add(h)

                # Message de succès détaillé avec numéro de ligne
                st.success(
                    "✅ Intégration réussie.\n"
                    "Les données ont été ajoutées au tableau de suivi qualité : "
                    "Analyse globale des formations.\n\n"
                    f"📍 Ligne d'insertion : {row_idx}"
                )

                # Information complémentaire
                st.info(
                    "Vous pouvez retrouver immédiatement cet enregistrement "
                    f"à la ligne {row_idx} du Google Sheet."
                )

            except Exception as e:
                st.error(
                    "❌ Une erreur est survenue lors de l’intégration dans Google Sheets."
                )
                st.exception(e)