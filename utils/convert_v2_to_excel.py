# utils/convert_v2_to_excel.py
import json
import re
from typing import List, Dict, Any, Tuple, Optional
from decimal import Decimal

from utils.llm_client import call_llm_extract_json


# ----------------------------
# Constantes
# ----------------------------

NO_INFO = "Aucune remarque – les données indiquent l’absence d’informations."


# ----------------------------
# Helpers "règles déterministes"
# ----------------------------

BRUIT = {
    "ras", "r.a.s", "aucun", "aucune", "aucuns", "aucunes",
    "rien", "néant", "x", "-", "/", ".", "..", "...", "ok", "0",
    "je ne sais pas", "ne sait pas", "je sais pas",
    "pas de sujet", "pas de sujet particulier", "pas de particulier",
    "pas d'idée", "pas d’idée", "pas d'idée particulière", "pas d’idée particulière",
    "pas concerné", "sans réponse", "non", "merci",
    "pas de suggestion", "aucune suggestion", "je n'en ai pas", "pas à ma connaissance"
}


def _norm(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip()


def _is_bruit(s: str) -> bool:
    t = s.strip().lower()
    return (not t) or (t in BRUIT) or (len(t) <= 2)


def _clean_list(items: Optional[List[Any]]) -> List[str]:
    out = []
    for s in items or []:
        if s is None:
            continue
        txt = _norm(s)
        if _is_bruit(txt):
            continue
        txt = re.sub(r"\s+", " ", txt)
        txt = txt.strip(" -–—·•")
        if not txt:
            continue
        out.append(txt)

    seen = set()
    dedup = []
    for x in out:
        k = x.lower()
        if k in seen:
            continue
        seen.add(k)
        dedup.append(x)
    return dedup


def _safe_number(x: Any) -> float:
    try:
        if x is None:
            return 0.0
        if isinstance(x, (int, float)):
            return float(x)
        return float(str(x).replace(",", ".").replace("%", "").strip())
    except Exception:
        return 0.0


def _rebalance_to_100(a: float, b: float, c: float) -> Tuple[int, int, int]:
    A, B, C = round(a), round(b), round(c)
    delta = 100 - (A + B + C)
    if delta == 0:
        return A, B, C

    triple = [A, B, C]
    idx = max(range(3), key=lambda i: triple[i])
    triple[idx] += delta
    return tuple(triple)


def _calc_volonte(v2: Dict[str, Any]) -> str:
    pre = v2.get("pre_formation") or {}
    dist = pre.get("souhaitez_vous_suivre_distribution") or []
    total_votants = _safe_number((pre.get("volonte_suivi_formation") or {}).get("nb votants"))

    p = {"5": 0.0, "4": 0.0, "3": 0.0, "2": 0.0, "1": 0.0}
    c = {"5": 0.0, "4": 0.0, "3": 0.0, "2": 0.0, "1": 0.0}

    for d in dist:
        for k in ("echele 5", "echele 4", "echele 3", "echele 2", "echele 1"):
            if k in d and d[k] is not None:
                level = k.split()[-1]
                p[level] = _safe_number(d.get("pourcentage"))
                if "nb_votants" in d and d["nb_votants"] is not None:
                    c[level] = _safe_number(d["nb_votants"])
                break

    if sum(p.values()) == 0 and total_votants > 0 and sum(c.values()) > 0:
        for lvl in p.keys():
            p[lvl] = 100.0 * (c[lvl] / total_votants)

    favorables = p["5"] + p["4"]
    neutre = p["3"]
    nonfav = p["2"] + p["1"]

    A, B, C = _rebalance_to_100(favorables, neutre, nonfav)
    return f"{A} % favorables, {B} % neutre, {C} % non favorables"


def _mean_notes_sur10(objs: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not objs:
        return None

    vals = []
    for o in objs:
        v = o.get("note_sur_10")
        if isinstance(v, (int, float)):
            vals.append(float(v))

    if not vals:
        return None

    m = sum(vals) / len(vals)
    return f"{m:.1f}/10"


def _format_note(n: Any) -> Optional[str]:
    if n is None:
        return None
    try:
        f = float(n)
        return f"{f:.1f}/10"
    except Exception:
        return None


def _satisfaction_globale(a_chaud: Dict[str, Any]) -> Optional[str]:
    items = a_chaud.get("satisfaction_contenu") or []
    if not items:
        return None

    tot = sum(_safe_number(i.get("count")) for i in items)

    if not tot:
        pct = sum(
            _safe_number(i.get("percent"))
            for i in items
            if i.get("label") in ["Très satisfait(e)", "Satisfait(e)"]
        )
        return f"{round(pct):d} %"

    pos = sum(
        _safe_number(i.get("count"))
        for i in items
        if i.get("label") in ["Très satisfait(e)", "Satisfait(e)"]
    )

    val = round((pos / tot) * 100)
    return f"{val} %"


def _profitable(a_chaud: Dict[str, Any]) -> Optional[str]:
    pf = a_chaud.get("formation_profitable") or {}
    p = pf.get("oui_percent")

    if p is None:
        return None

    try:
        return f"{float(p):.0f} %"
    except Exception:
        return f"{p} %"


def _format_decimal_preserve_precision(x: Any, max_dec=2) -> Optional[str]:
    if x is None:
        return None

    try:
        dec = Decimal(str(x))
        q = Decimal("0.01")
        dec_q = dec.quantize(q)
        s = format(dec_q.normalize(), "f")
        return s
    except Exception:
        return str(x)


def _impact_plus(v2: Dict[str, Any]) -> Optional[str]:
    r = (v2.get("resultats_evaluations") or {}).get("progression_competences_plus_sur_10")

    if r is None:
        return None

    s = _format_decimal_preserve_precision(r, max_dec=2)
    if not s:
        s = str(r)

    return f"+{s}/10"


# ----------------------------
# Helpers IA
# ----------------------------

def _llm_text(prompt: str) -> str:
    try:
        res = call_llm_extract_json(prompt, "", {"mode": "summary"})

        if res is None:
            return ""

        if isinstance(res, str):
            return res.strip()

        if isinstance(res, dict):
            for k in (
                "phrase", "résumé", "resume", "synthese", "synthèse",
                "summary", "text", "content", "result", "output"
            ):
                v = res.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()

            return json.dumps(res, ensure_ascii=False)

        if isinstance(res, list):
            return " ".join(str(x) for x in res).strip()

        return str(res).strip()

    except Exception:
        return ""


def _unwrap_summary_text(text: str) -> str:
    if not text:
        return ""

    t = text.strip()

    if (t.startswith("{") and t.endswith("}")) or (t.startswith("[") and t.endswith("]")):
        try:
            obj = json.loads(t)

            if isinstance(obj, dict):
                for k in ("phrase", "résumé", "resume", "synthese", "synthèse", "summary", "text", "content", "result", "output"):
                    v = obj.get(k)
                    if isinstance(v, str) and v.strip():
                        return v.strip()

            t = re.sub(r"\s+", " ", t)
            return t

        except Exception:
            pass

    t = t.strip().strip('"').strip("'")
    t = re.sub(r"\s+", " ", t)
    return t


def _clean_summary_punctuation(text: str) -> str:
    """
    Nettoie les ponctuations maladroites générées par le LLM,
    notamment les points utilisés entre des idées qui devraient être liées par des virgules.
    """
    if not text:
        return ""

    t = text.strip()

    # Cas fréquent : "aborder. il y a" -> "aborder, il y a"
    t = re.sub(
        r"aborder\.\s*il y a",
        "aborder, il y a",
        t,
        flags=re.IGNORECASE,
    )

    # Cas fréquent : "abordées. il y a" -> "abordées, il y a"
    t = re.sub(
        r"abordées?\.\s*il y a",
        "aborder, il y a",
        t,
        flags=re.IGNORECASE,
    )

    # Remplace les points suivis d'une minuscule par une virgule
    # Ex : "urgences. la réactualisation" -> "urgences, la réactualisation"
    t = re.sub(
        r"\.\s+(?=[a-zàâäéèêëîïôöùûüç])",
        ", ",
        t,
    )

    # Nettoyage espaces
    t = re.sub(r"\s+", " ", t).strip()

    # Évite les doubles ponctuations
    t = re.sub(r",\s*,", ",", t)
    t = re.sub(r"\s+,", ",", t)

    # Point final unique
    t = t.rstrip(" ,;")
    if t and not t.endswith("."):
        t += "."

    return t


def _summarize_list_with_ai(title: str, items: List[str], temperature: float = 0.4) -> str:
    clean = _clean_list(items)

    if not clean:
        return NO_INFO

    prompt = (
        "Rédige un résumé concis, professionnel et médicalisé, en 1 à 2 phrases maximum. "
        "N'utilise pas de puces, pas de liste et pas de redondances. "
        "Utilise une ponctuation fluide, avec des virgules et des connecteurs logiques "
        "lorsque plusieurs idées sont liées. "
        "Ne crée aucune information non présente.\n\n"
        f"Thème: {title}\n"
        f"Éléments bruts:\n- " + "\n- ".join(clean)
    )

    res = _llm_text(prompt).strip()
    txt = _unwrap_summary_text(res) or NO_INFO
    return _clean_summary_punctuation(txt)


def _synthesize_from_text(text: str, title: str) -> str:
    if not text:
        return NO_INFO

    prompt = (
        "À partir de ce texte brut, rédige une synthèse courte, professionnelle et médicalisée, "
        "en 1 à 2 phrases maximum. "
        "N'utilise pas de puces ni de liste. "
        "Utilise une ponctuation fluide, avec des virgules et des connecteurs logiques "
        "lorsque plusieurs idées sont liées.\n\n"
        f"Thème: {title}\n\n"
        f"Texte:\n{text}"
    )

    res = _llm_text(prompt).strip()
    txt = _unwrap_summary_text(res) or NO_INFO
    return _clean_summary_punctuation(txt)


# ----------------------------
# Transformateur v2.x ➜ json_excel
# ----------------------------

def generate_json_excel(
    v2: Dict[str, Any],
    *,
    DEMANDE_AS_LIST: bool = True
) -> Dict[str, Any]:

    formation = _norm(v2.get("Nom formation"))
    semestre = _norm(v2.get(" semestre"))

    volonte = _calc_volonte(v2)

    # Demande particulière de sujet à aborder
    sujets_bruts = (v2.get("pre_formation") or {}).get("demande_sujets_a_aborder") or []
    sujets_list = _clean_list(sujets_bruts)

    if not sujets_list:
        demande_val = "Aucune remarque."
    else:
        prompt_sujets = (
            "À partir de la liste suivante, rédige une phrase unique, fluide, professionnelle "
            "et médicalisée, mettant en avant uniquement les thèmes médicaux ou de formation évoqués. "
            "Commence exactement par : Parmi les demandes de sujet à aborder, il y a "
            "La réponse doit être une seule phrase complète. "
            "N'utilise pas de puces, pas de liste, pas de points entre les idées, "
            "pas de phrases courtes juxtaposées. "
            "Utilise des virgules, des connecteurs logiques et termine par un seul point final. "
            "Ne mentionne jamais les noms de personnes. "
            "Ne crée aucune information non présente.\n\n"
            "Thème: Demande particulière de sujet à aborder\n"
            "Éléments bruts:\n- " + "\n- ".join(sujets_list)
        )

        res = _llm_text(prompt_sujets).strip()
        demande_val = _unwrap_summary_text(res) or "Aucune remarque."
        demande_val = _clean_summary_punctuation(demande_val)

    # Notes pré-formation
    pre_mo = (v2.get("pre_formation") or {}).get("maitrise_objectifs_preformation") or {}

    note_pre = (
        _format_note(pre_mo.get("note_globale_objectifs_preformation"))
        or _mean_notes_sur10(pre_mo.get("par_objectif"))
        or "Données indisponibles"
    )

    a_chaud = v2.get("a_chaud") or {}

    note_chaud = _format_note(a_chaud.get("note_globale_a_chaud")) or "Données indisponibles"
    profitable = _profitable(a_chaud) or "Données indisponibles"
    satisfaction = _satisfaction_globale(a_chaud) or "Données indisponibles"

    points_forts = _summarize_list_with_ai("Points forts", a_chaud.get("points_forts") or [])
    points_faibles = _summarize_list_with_ai("Points faibles", a_chaud.get("points_a_ajuster") or [])
    sujets_reboucler = _summarize_list_with_ai(
        "Sujets non traités / à re-boucler",
        a_chaud.get("suggestions_complement_sur_formation") or [],
    )
    eval_formateurs = _summarize_list_with_ai(
        "Évaluation formateurs",
        a_chaud.get("appreciations_intervenants") or [],
    )

    # À froid & progression
    a_froid = v2.get("a_froid") or {}

    note_froid = _format_note(a_froid.get("note_sur_10")) or "Données indisponibles"

    cold_mo = a_froid.get("maitrise_objectifs_a_froid") or {}

    auto_prog = (
        _format_note(cold_mo.get("note_globale_objectifs_a_froid"))
        or _mean_notes_sur10(cold_mo.get("par_objectif"))
        or "Données indisponibles"
    )

    impact_plus = _impact_plus(v2) or "Données indisponibles"

    avec_recul = _summarize_list_with_ai(
        "Avec le recul",
        a_froid.get("elements_les_plus_utiles") or [],
    )

    inter = v2.get("intervenants") or {}

    prob_text = " ".join([
        _norm(inter.get("commentaire_conditions_materielles")),
        _norm(inter.get("commentaire_groupe_apprenants")),
        _norm(inter.get("commentaire_organisation_generale")),
    ]).strip()

    problematiques = _synthesize_from_text(prob_text, "Problématiques remontées")

    adapt_text = " ".join([
        json.dumps(inter.get("adaptation_horaires") or {}, ensure_ascii=False),
        _norm(inter.get("explication_modification_programme")),
    ]).strip()

    adaptations = _synthesize_from_text(adapt_text, "Adaptations de programme")

    lien = _norm(v2.get("lien_vers_formation"))

    out = {
        "Formation": formation,
        "Semestre": semestre,
        "Volonté de suivre cette session": volonte,
        "Demande particulière de sujet à aborder": demande_val,
        "AutoEvaluation compétence pré-formation": note_pre,
        "formation Profitable": profitable,
        "Satisfaction du contenu": satisfaction,
        "Note /10 à chaud": note_chaud,
        "Points forts": points_forts,
        "Points faibles": points_faibles,
        "Sujets non traité à reboucler avec formateur ou nouvelle formation ou attendu": sujets_reboucler,
        "Evaluation formateurs": eval_formateurs,
        "Autoanalyse compétence": (
            _format_note((a_chaud.get("maitrise_objectifs_a_chaud") or {}).get("note_globale_objectifs_a_chaud"))
            or _mean_notes_sur10((a_chaud.get("maitrise_objectifs_a_chaud") or {}).get("par_objectif"))
            or "Données indisponibles"
        ),
        "Note /10 à froid": note_froid,
        "Auto-analyse progression": auto_prog,
        "Impact / Progression des compétences": impact_plus,
        "Avec le recul": avec_recul,
        "Problématiques remontées": problematiques,
        "Adaptations de programme": adaptations,
        "Synthese": "",
        "Lien du rapport qualité": lien,
        "Actions correctrices": "",
        "meta_generation": {
            "auteur": "IA pro CESU",
            "mode": "rédaction médicale harmonisée",
        },
    }

    return out