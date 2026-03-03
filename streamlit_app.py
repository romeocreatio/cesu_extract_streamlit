# streamlit_app.py

import os
import json
import re
from pathlib import Path

import streamlit as st

# phase 1
from utils.pdf_reader import read_pdf_all_text
from utils.llm_client import load_prompt, call_llm_extract_json
from utils.schema import OutputPayload  # v2.2

# phase 2
from utils.convert_v2_to_excel import generate_json_excel

# phase 3
# Google Sheets injection
from utils.google_sheets_writer import append_json_to_google_sheet


# =====================================================
# 🔐 Authentification simple via secrets
# =====================================================

def check_auth():
    """
    Authentification basique (login + mot de passe).

    Sources possibles :
    1) Variables d'environnement / secrets plats (Cloud ou .env) :
       - AUTH_USERNAME ou USERNAME
       - AUTH_PASSWORD ou PASSWORD
    2) Secrets sectionnés (local : .streamlit/secrets.toml) :
       [auth]
       USERNAME = "..."
       PASSWORD = "..."
    """

    # 1) Essayer d'abord env / secrets plats
    username = os.getenv("AUTH_USERNAME") or os.getenv("USERNAME")
    password = os.getenv("AUTH_PASSWORD") or os.getenv("PASSWORD")

    try:
        # secrets plats (cloud) → st.secrets["AUTH_USERNAME"], st.secrets["USERNAME"], etc.
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

        # 2) Fallback local : section [auth]
        if ("auth" in st.secrets) and (not username or not password):
            auth_sec = st.secrets["auth"]
            if not username:
                username = auth_sec.get("USERNAME")
            if not password:
                password = auth_sec.get("PASSWORD")
    except Exception:
        # Si st.secrets pas dispo ou autre, on ignore
        pass

    # Si toujours rien → pas d'auth configurée → app ouverte
    if not username or not password:
        st.warning("Authentification non configurée — accès non protégé.")
        return

    # État de session
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return

    # Formulaire de login
    
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

st.set_page_config(page_title="CESU 83 - Extracteur Qualité", page_icon="🩺", layout="wide")

# Appliquer l'auth dès le début
check_auth()

# =====================================================
# 🔧 Helpers extraction / correction
# =====================================================

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
    a_ch = (v2.get("a_chaud") or {})
    items = a_ch.get("satisfaction_contenu") or []
    for it in (items or []):
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
    si pourcentage == null mais on a "N votants" + total => calcule % (arrondi 0.1)
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
        # récupérer la clé "echele X"
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
    Transforme un JSON ancien vers v2.1 (clé à clé). Si déjà v2/v2.1, renvoie inchangé.
    """
    pre = (json_result or {}).get("pre_formation") or {}
    # heuristique: si "volonte_suivi_formation" existe → déjà v2
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
        svs = (old_pre.get("souhaitez_vous_suivre") or {})
        voters_total = svs.get("voters_total") or svs.get("votants") or None
        old_dist = old_pre.get("souhaitez_vous_suivre_distribution")

        # Rebuild distribution (ancien format → v2-like)
        target_labels = ["5", "4", "3", "2", "1"]
        idx = {str(d.get("label")): d for d in (old_dist or []) if isinstance(d, dict)}
        v2_dist = []
        for lab in target_labels:
            d = idx.get(lab, {})
            item = {
                f"echele {lab}": _fmt_votants(d.get("count")),
                "pourcentage": _safe_float(d.get("percent")),
            }
            v2_dist.append(item)

        sujets = old_pre.get("sujets_a_aborder") or old_pre.get("demande_sujets_a_aborder") or None
        mpo = old_pre.get("maitrise_objectifs") or old_pre.get("maitrise_objectifs_preformation") or {}
        v2_pre_mo = {
            "mode": mpo.get("mode"),
            "par_objectif": mpo.get("par_objectif"),
            "note_globale_objectifs_preformation": mpo.get("note_globale_objectifs_sur_10")
            or mpo.get("note_globale_objectifs_preformation"),
        }

        out["pre_formation"] = {
            "volonte_suivi_formation": {"nb votants": voters_total},
            "souhaitez_vous_suivre_distribution": v2_dist,
            "demande_sujets_a_aborder": sujets,
            "maitrise_objectifs_preformation": v2_pre_mo,
        }

        # A chaud
        old_hot = json_result.get("a_chaud") or {}
        out["a_chaud"] = {
            "formation_profitable": old_hot.get("profitable"),
            "satisfaction_contenu": old_hot.get("satisfaction_contenu"),
            "note_globale_a_chaud": old_hot.get("impression_globale_note_sur_10")
            or old_hot.get("note_globale_a_chaud"),
            "points_forts": old_hot.get("points_forts"),
            "points_a_ajuster": old_hot.get("points_a_ajuster"),
            "suggestions_complement_sur_formation": old_hot.get("suggestions_complement")
            or old_hot.get("suggestions_complement_sur_formation"),
            "appreciations_intervenants": old_hot.get("appreciations_intervenants"),
            "maitrise_objectifs_a_chaud": {
                "mode": (old_hot.get("maitrise_objectifs") or {}).get("mode"),
                "par_objectif": (old_hot.get("maitrise_objectifs") or {}).get("par_objectif"),
                "note_globale_objectifs_a_chaud": (old_hot.get("maitrise_objectifs") or {}).get(
                    "note_globale_objectifs_sur_10"
                ),
            }
            if old_hot.get("maitrise_objectifs")
            else None,
        }

        # A froid
        old_cold = json_result.get("a_froid") or {}
        out["a_froid"] = {
            "note_sur_10": old_cold.get("note_sur_10"),
            "maitrise_objectifs_a_froid": {
                "mode": (old_cold.get("maitrise_objectifs") or {}).get("mode"),
                "par_objectif": (old_cold.get("maitrise_objectifs") or {}).get("par_objectif"),
                "note_globale_objectifs_a_froid": (old_cold.get("maitrise_objectifs") or {}).get(
                    "note_globale_objectifs_sur_10"
                )
                or old_cold.get("note_globale_objectifs_a_froid"),
            }
            if old_cold.get("maitrise_objectifs") or old_cold.get("maitrise_objectifs_a_froid")
            else None,
            "elements_les_plus_utiles": old_cold.get("elements_les_plus_utiles"),
        }

    # Normalise labels & complète pourcentages
    _normalize_satisfaction_labels(out)
    fill_missing_percentages_from_counts(out)

    # Marque la version du schéma
    out["version_prompt"] = "v2.1"
    return out


# =====================================================
# 🧩  Interface Streamlit
# =====================================================

project_root = Path(__file__).parent
logo_path = project_root / "assets" / "logo_cesu83.jpeg"

col_logo, col_title, col_spacer = st.columns([1, 2, 1])
with col_logo:
    if logo_path.exists():
        st.image(str(logo_path), use_container_width=90)
    else:
        st.markdown(
            "<div style='padding:14px;border:1px dashed #bbb;border-radius:8px;text-align:center;'>"
            "Logo manquant<br><code>assets/logo_cesu83.jpeg</code></div>",
            unsafe_allow_html=True,
        )
with col_title:
    st.markdown(
        "<h2 style='text-align:center;margin-top:0;'>CESU 83 — Extracteur de Rapports Qualité </h2>",
        unsafe_allow_html=True,
    )

st.markdown("---")

# =====================================================
# Étape 1  — Extraction Rapport Qualité : PDF Digiforma
# =====================================================

st.subheader("Phase 1 - Analyse du rapport qualité Digiforma")

with st.form("meta_form", clear_on_submit=False):
    c1, c2 = st.columns(2)
    with c1:
        nom_formation = st.text_input("Nom de la formation", placeholder="ex: AFGSU 1")
    with c2:
        semestre = st.text_input("Semestre", placeholder="ex: S1 2025")

    uploaded_pdf = st.file_uploader("Uploader le rapport qualité", type=["pdf"])
    submitted = st.form_submit_button("Analyser le rapport", use_container_width=True, type="primary")

if submitted:
    if not uploaded_pdf or not nom_formation or not semestre:
        st.error("Veuillez renseigner le nom de la formation, le semestre, et uploader un PDF.")
        st.stop()

    # 1) Lecture du PDF complet (texte brut + OCR fallback si vide)
    file_bytes = uploaded_pdf.read()
    with st.spinner("Lecture du fichier (texte + OCR si nécessaire) ..."):
        full_text, pages_text, used_ocr = read_pdf_all_text(file_bytes)

    with st.expander("🔎 Aperçu du texte lu (pré-traitement)", expanded=False):
        st.markdown(f"**OCR utilisé :** {'✅ Oui' if used_ocr else '❌ Non'}")
        st.text_area(
            "Aperçu du texte lu (limité à 20 000 caractères)",
            full_text[:20000],
            height=300,
        )

    # 2) Charger le prompt maître
    prompt_path = project_root / "prompts" / "prompt_reference.txt"
    try:
        prompt_master = load_prompt(str(prompt_path))
    except Exception as e:
        st.error(f"Impossible de charger le prompt : {e}")
        st.stop()

    # 3) Appel IA (le LLM peut renvoyer ancien schéma / v2 / v2.1)
    with st.spinner("Extraction des données par sessions via l'IA ..."):
        try:
            json_result = call_llm_extract_json(
                prompt_master,
                full_text,
                meta={
                    "nom_formation": nom_formation,
                    "semestre": semestre,
                    "filename": uploaded_pdf.name,
                },
            )
        except Exception as e:
            st.error(f"Erreur IA: {e}")
            st.stop()

    # 4) Forcer les champs top-level
    json_result["Nom formation"] = nom_formation
    json_result[" semestre"] = semestre
    json_result["lien_vers_formation"] = uploaded_pdf.name

    # 5) Mapper vers v2.1 (clé à clé) + normalisations
    v2_payload = map_old_payload_to_v2(json_result, full_text)

    # 6) Validation Pydantic v2 (tolère sections manquantes)
    try:
        validated = OutputPayload.model_validate(v2_payload)
    except Exception as e:
        st.error(f"Le JSON retourné ne respecte pas le schéma v2.2: {e}")
        st.json(v2_payload)
        st.stop()

    # 7) Sauvegarde JSON v2.1 dans le dossier /json_v2 (pour usage local / debug)
    DIR_JSON_V2 = project_root / "json_v2"
    DIR_JSON_V2.mkdir(exist_ok=True)

    safe_name = f"{nom_formation.strip().replace(' ', '_')}_{semestre.strip().replace(' ', '_')}.json"

    # on conserve temporairement la version complète (avec None)
    payload_dict_full = validated.model_dump(by_alias=True, exclude_none=False)
    payload_dict = validated.model_dump(by_alias=True, exclude_none=True)

    json_str = json.dumps(payload_dict, ensure_ascii=False, indent=2)

    path_v2 = DIR_JSON_V2 / safe_name
    path_v2.write_text(json_str, encoding="utf-8")

    st.success(f"Extraction réussie ✅ — Fichier enregistré dans json_v2 : {path_v2.name}")

    # 8) Affichage JSON (dans des expanders)
    st.subheader("Résultat de l'extraction")

    with st.expander("🧾 Aperçu du JSON", expanded=False):
        st.code(json_str, language="json")

    # 9) Avertissements sections manquantes (ou vides)
    def _is_missing_or_empty(x):
        if x is None:
            return True
        if isinstance(x, dict) and len(x) == 0:
            return True
        if isinstance(x, list) and len(x) == 0:
            return True
        return False

    missing_msgs = []
    sections_to_check = ["pre_formation", "a_chaud", "a_froid", "intervenants", "resultats_evaluations"]

    for section in sections_to_check:
        val_full = payload_dict_full.get(section)
        if _is_missing_or_empty(val_full):
            kind = "absente (null)" if val_full is None else "présente mais vide"
            missing_msgs.append(f"Section **{section}** {kind}.")

    if missing_msgs:
        with st.expander("⚠️ Avertissements — Sections manquantes ou vides", expanded=False):
            for msg in missing_msgs:
                st.markdown(f"- {msg}")

    # 10) Téléchargement JSON v2.2
    st.download_button(
        label="📥 Télécharger le JSON v2.2",
        data=json_str,
        file_name=safe_name,
        mime="application/json",
        use_container_width=True,
    )

st.markdown("---")

# =====================================================
# Étape 2 — Transformation Excel format (json_v2 ➜ json_excel)
# =====================================================

st.subheader("Phase 2 - Structuration des données")

DIR_JSON_V2 = project_root / "json_v2"
DIR_JSON_EXCEL = project_root / "json_excel"
DIR_JSON_EXCEL.mkdir(exist_ok=True)


@st.cache_data(ttl=30)
def list_json_v2_files():
    if not DIR_JSON_V2.exists():
        return []
    files = sorted([p.name for p in DIR_JSON_V2.glob("*.json")])
    return files


files = list_json_v2_files()
if not files:
    st.info("Aucun fichier trouvé dans /json_v2 pour le moment.")
else:
    with st.form("form_excel", clear_on_submit=False):
        c1, c2 = st.columns([2, 1])
        with c1:
            selected = st.selectbox("Choisir un fichier JSON (v2.2) :", files, index=0)
        with c2:
            demande_as_list = st.toggle(
                "Sujets en liste (Excel)",
                value=True,
                help="Si OFF, une phrase de synthèse sera générée (comme ton exemple).",
            )

        do_transform = st.form_submit_button("Créer le JSON Excel", use_container_width=True, type="primary")

    if do_transform and selected:
        path_v2 = DIR_JSON_V2 / selected
        try:
            v2_payload = json.loads(path_v2.read_text(encoding="utf-8"))
        except Exception as e:
            st.error(f"Impossible de lire {selected} : {e}")
            st.stop()

        with st.spinner("Transformation json v2 ➜ json_excel (règles + IA) en cours ..."):
            json_excel = generate_json_excel(v2_payload, DEMANDE_AS_LIST=demande_as_list)

        # nom de sortie identique
        path_excel = DIR_JSON_EXCEL / selected
        path_excel.write_text(json.dumps(json_excel, ensure_ascii=False, indent=2), encoding="utf-8")

        st.success(f"✅ JSON Excel créé dans json_excel/{path_excel.name}")

        # Téléchargement JSON Excel (Phase 2)
        st.download_button(
            "📥 Télécharger le JSON Excel",
            data=json.dumps(json_excel, ensure_ascii=False, indent=2),
            file_name=path_excel.name,
            mime="application/json",
            use_container_width=True,
        )

        with st.expander("Aperçu (json_excel)", expanded=False):
            st.json(json_excel, expanded=False)

st.markdown("---")

# =====================================================
# Phase 3 — Injection Google Sheets (prod)
# =====================================================

st.subheader("Phase 3 — Intégration dans le suivi qualité ")

json_excel_dir = DIR_JSON_EXCEL
json_excel_dir.mkdir(exist_ok=True)

colL, colR = st.columns([2, 1])
with colL:
    mode = st.radio(
        "Source du JSON Excel",
        ["Depuis le dossier JSON-Excel", "Upload d'un fichier .json"],
        horizontal=True,
    )

json_payload = None
chosen_name = None

if mode == "Depuis le dossier JSON-Excel":
    files = sorted([f.name for f in json_excel_dir.glob("*.json")])
    chosen_name = st.selectbox("Choisir un JSON Excel", ["— Sélectionner —"] + files)
    if chosen_name and chosen_name != "— Sélectionner —":
        try:
            path_json = json_excel_dir / chosen_name
            json_payload = json.loads(path_json.read_text(encoding="utf-8"))
            st.success(f"JSON Excel « {chosen_name} » chargé.")
        except Exception as e:
            st.error(f"Lecture impossible: {e}")
else:
    up = st.file_uploader("Charger un JSON Excel", type=["json"])
    if up is not None:
        try:
            json_payload = json.load(up)
            chosen_name = getattr(up, "name", "upload.json")
            st.success("JSON Excel chargé.")
        except Exception as e:
            st.error(f"JSON invalide: {e}")

# Aperçu des clés JSON (utile en prod)
if json_payload:
    st.caption("Aperçu des clés du JSON Excel détectées :")
    st.code(", ".join(json_payload.keys()), language="text")

# Anti-doublon (simple et efficace)
import hashlib

def _payload_hash(d: dict) -> str:
    raw = json.dumps(d, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

if "injected_hashes" not in st.session_state:
    st.session_state.injected_hashes = set()

# Bouton unique : injecter dans Google Sheets
inject_gs = st.button(
    "📤 Injecter dans Google Sheets (Drive)",
    type="primary",
    use_container_width=True,
    disabled=(json_payload is None),
)

if inject_gs and json_payload:
    h = _payload_hash(json_payload)

    if h in st.session_state.injected_hashes:
        st.warning("⚠️ Ce JSON semble déjà injecté (doublon évité).")
    else:
        with st.spinner("Injection dans Google Sheets en cours…"):
            try:
                row_idx = append_json_to_google_sheet(json_payload)
                st.session_state.injected_hashes.add(h)
                st.success(f"✅ Données injectées dans Google Sheets (ligne {row_idx}).")
            except Exception as e:
                st.error("❌ Erreur lors de l'injection dans Google Sheets")
                st.exception(e)
