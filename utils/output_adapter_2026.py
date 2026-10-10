# utils/output_adapter_2026.py

from __future__ import annotations

from typing import Dict, Optional, Tuple, Union

from utils.business_model_2026 import (
    MasteryBusinessSummary2026,
    PreformationBusinessModel2026,
    VolonteBusinessOccurrence2026,
)


Number = Union[int, float]


# =====================================================
# En-tetes exacts de la maquette CESU 83
# =====================================================

OUTPUT_HEADERS_2026: Tuple[str, ...] = (
    "Formation",
    "Semestre",
    "Volonté de suivre cette session",
    "Demande particulière de sujet à aborder",
    "AutoEvaluation compétence pré-formation",
    "formation Profitable",
    "Satisfaction du contenu",
    "Note /10 à chaud",
    "Points forts",
    "Points faibles",
    (
        "Sujets non traité à reboucler avec formateur "
        "ou nouvelle formation ou attendu"
    ),
    "Evaluation formateurs",
    "Autoanalyse compétence",
    "Note /10 à froid",
    "Auto-analyse progression",
    "Impact / Progression des compétences",
    "Avec le recul ",
    "Problématiques remontées",
    "Adaptations de programme",
    "Synthese",
    "Lien du rapport qualité",
    "Actions correctrices",
)


OutputRow2026 = Dict[str, str]


# =====================================================
# Formatage numerique
# =====================================================

def _format_number_fr(
    value: Number,
    *,
    decimals: int = 2,
) -> str:
    """
    Formate une valeur numerique pour l'affichage
    metier francais.

    Exemples :
        5.0       -> "5"
        5.5       -> "5,5"
        5.708536  -> "5,71"

    L'arrondi appartient uniquement a la couche
    de sortie. La valeur metier interne n'est jamais
    modifiee.
    """

    formatted = (
        f"{float(value):.{decimals}f}"
        .rstrip("0")
        .rstrip(".")
    )

    return formatted.replace(
        ".",
        ",",
    )


def _format_score_sur_10(
    value: Number,
) -> str:
    """
    Formate une note sur 10.
    """

    return (
        f"{_format_number_fr(value)}/10"
    )


# =====================================================
# Volonte de suivre la session
# =====================================================

def _format_volonte_occurrence(
    occurrence: VolonteBusinessOccurrence2026,
) -> str:
    """
    Produit l'affichage valide CESU 83 :

        91 % favorables, 4 % neutre,
        3 % non favorables

    Aucun pourcentage absent n'est reconstruit.
    """

    favorable = occurrence.favorable_pct
    neutre = occurrence.neutre_pct
    non_favorable = (
        occurrence.non_favorable_pct
    )

    if (
        favorable is None
        or neutre is None
        or non_favorable is None
    ):
        return ""

    return (
        f"{_format_number_fr(favorable)} % favorables, "
        f"{_format_number_fr(neutre)} % neutre, "
        f"{_format_number_fr(non_favorable)} % "
        "non favorables"
    )


def _format_volonte(
    model: PreformationBusinessModel2026,
) -> str:
    """
    Conserve l'ordre des occurrences.

    Le corpus standard 2026 contient actuellement
    une occurrence par rapport.

    Si plusieurs occurrences legitimes apparaissent
    plus tard, elles sont conservees separement et
    non fusionnees arbitrairement.
    """

    values = tuple(
        _format_volonte_occurrence(
            occurrence
        )
        for occurrence
        in model.volonte_suivi
    )

    values = tuple(
        value
        for value in values
        if value
    )

    return " ; ".join(
        values
    )


# =====================================================
# Auto-evaluation competence pre-formation
# =====================================================

def _format_mastery_summary(
    summary: MasteryBusinessSummary2026,
) -> str:
    """
    Transforme la synthese metier en affichage final.

    Regles validees :

    missing
        -> cellule vide

    single_source
        -> note source
        -> ex. 5,5/10

    weighted_same_objectives
        -> moyenne ponderee calculee dans
           business_model_2026
        -> ex. 5,71/10 (moy. pondérée)

    multiple_unmerged
        -> notes sources conservees separement
        -> ex. 7,5/10 ; 6,1/10

    Aucun calcul metier n'est effectue ici.
    """

    method = (
        summary.aggregation_method
    )

    if method == "missing":
        return ""

    if method == "single_source":

        if summary.value_sur_10 is None:
            return ""

        return _format_score_sur_10(
            summary.value_sur_10
        )

    if method == "weighted_same_objectives":

        if summary.value_sur_10 is None:
            return ""

        return (
            f"{_format_score_sur_10(summary.value_sur_10)} "
            "(moy. pondérée)"
        )

    if method == "multiple_unmerged":

        values = tuple(
            _format_score_sur_10(note)
            for note in summary.source_notes
            if note is not None
        )

        return " ; ".join(
            values
        )

    raise ValueError(
        "Methode d'agregation de maitrise "
        f"inconnue : {method!r}"
    )


# =====================================================
# Construction de la ligne finale
# =====================================================

def build_output_row_2026(
    model: PreformationBusinessModel2026,
) -> OutputRow2026:
    """
    Transforme le modele metier 2026 en une ligne
    compatible avec les 22 colonnes de la maquette
    CESU 83.

    Cette premiere version remplit uniquement les
    colonnes dont les regles ont deja ete validees.

    Les autres colonnes restent volontairement vides.

    Aucune extraction PDF.
    Aucun appel OpenAI.
    Aucun calcul de moyenne metier.
    Aucun acces Excel ou Google Sheets.
    """

    if not isinstance(
        model,
        PreformationBusinessModel2026,
    ):
        raise TypeError(
            "model doit etre un "
            "PreformationBusinessModel2026."
        )

    row: OutputRow2026 = {
        header: ""
        for header in OUTPUT_HEADERS_2026
    }

    # -------------------------------------------------
    # 1. Formation
    # -------------------------------------------------

    row["Formation"] = (
        model.metadata.formation
    )

    # -------------------------------------------------
    # 2. Semestre
    # -------------------------------------------------

    row["Semestre"] = (
        model.metadata.semestre
    )

    # -------------------------------------------------
    # 3. Volonte de suivre cette session
    # -------------------------------------------------

    row[
        "Volonté de suivre cette session"
    ] = _format_volonte(
        model
    )

    # -------------------------------------------------
    # 4. Demande particuliere de sujet a aborder
    #
    # Verbatims fiables disponibles dans le modele,
    # mais regle de synthese finale pas encore validee.
    # Donc cellule volontairement vide.
    # -------------------------------------------------

    row[
        "Demande particulière de sujet à aborder"
    ] = ""

    # -------------------------------------------------
    # 5. AutoEvaluation competence pre-formation
    # -------------------------------------------------

    row[
        "AutoEvaluation compétence pré-formation"
    ] = _format_mastery_summary(
        model.maitrise_summary
    )

    # -------------------------------------------------
    # 6 -> 20
    #
    # Pas encore branches dans le nouveau pipeline
    # metier 2026.
    # Ils restent volontairement vides.
    # -------------------------------------------------

    # -------------------------------------------------
    # 21. Lien du rapport qualite
    # -------------------------------------------------

    row[
        "Lien du rapport qualité"
    ] = model.metadata.report_url

    # -------------------------------------------------
    # 22. Actions correctrices
    #
    # Colonne manuelle.
    # -------------------------------------------------

    row[
        "Actions correctrices"
    ] = ""

    # -------------------------------------------------
    # Garantie structurelle
    # -------------------------------------------------

    if tuple(row.keys()) != OUTPUT_HEADERS_2026:
        raise AssertionError(
            "L'ordre ou les en-tetes de sortie "
            "2026 ont ete modifies."
        )

    if len(row) != 22:
        raise AssertionError(
            "La sortie 2026 doit contenir "
            "exactement 22 colonnes."
        )

    return row
