# utils/output_adapter_2026.py

from __future__ import annotations

import re

from typing import Dict, Optional, Tuple, Union

from utils.business_model_2026 import (
    MasteryBusinessSummary2026,
    PreformationBusinessModel2026,
    VolonteBusinessOccurrence2026,
)
from utils.a_chaud_business_model_2026 import (
    AChaudBusinessModel2026,
    AChaudMasteryBusinessSummary2026,
    ProfitableBusinessOccurrence2026,
    SatisfactionBusinessOccurrence2026,
)
from utils.a_chaud_verbatim_synthesis_2026 import (
    VerbatimSynthesis2026,
)
from utils.preformation_verbatim_synthesis_2026 import (
    PreformationVerbatimSynthesis2026,
)
from utils.a_froid_business_model_2026 import (
    AFroidBusinessModel2026,
    AFroidMasteryBusinessSummary2026,
    AFroidProgressionBusinessMetric2026,
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
# A chaud
# =====================================================

def _format_percentage(
    value: Optional[Number],
) -> str:
    """
    Formate un pourcentage source.

    Aucun recalcul ni reequilibrage.
    """

    if value is None:
        return ""

    return (
        f"{_format_number_fr(value)} %"
    )


def _format_profitable_occurrence(
    occurrence: ProfitableBusinessOccurrence2026,
) -> str:
    """
    Affiche uniquement le pourcentage OUI source.
    """

    return _format_percentage(
        occurrence.oui_pct
    )


def _format_profitable(
    model: AChaudBusinessModel2026,
) -> str:
    values = tuple(
        _format_profitable_occurrence(
            occurrence
        )
        for occurrence
        in model.formation_profitable
    )

    values = tuple(
        value
        for value in values
        if value
    )

    return " ; ".join(
        values
    )


def _format_satisfaction_occurrence(
    occurrence: SatisfactionBusinessOccurrence2026,
) -> str:
    """
    Affiche le pourcentage satisfait CESU 83 :

        Tres satisfait-e + Satisfait-e

    Cette valeur est deja calculee dans le modele
    metier a partir des pourcentages source.
    """

    return _format_percentage(
        occurrence.satisfait_pct
    )


def _format_satisfaction(
    model: AChaudBusinessModel2026,
) -> str:
    values = tuple(
        _format_satisfaction_occurrence(
            occurrence
        )
        for occurrence
        in model.satisfaction_contenu
    )

    values = tuple(
        value
        for value in values
        if value
    )

    return " ; ".join(
        values
    )


def _format_a_chaud_note(
    model: AChaudBusinessModel2026,
) -> str:
    values = tuple(
        _format_score_sur_10(
            occurrence.note_sur_10
        )
        for occurrence
        in model.note_globale
        if occurrence.note_sur_10
        is not None
    )

    return " ; ".join(
        values
    )


def _format_a_chaud_mastery_summary(
    summary: AChaudMasteryBusinessSummary2026,
) -> str:
    """
    Meme logique d'affichage que la preformation.

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
        f"A chaud inconnue : {method!r}"
    )


# =====================================================
# A froid
# =====================================================

def _format_a_froid_note(
    model: AFroidBusinessModel2026,
) -> str:
    """
    Affiche uniquement les notes globales A froid
    explicitement presentes dans la source.

    Plusieurs occurrences legitimes restent separees.
    """

    values = tuple(
        _format_score_sur_10(
            occurrence.note_sur_10
        )
        for occurrence
        in model.note_globale
        if occurrence.note_sur_10 is not None
    )

    return " ; ".join(
        values
    )


def _format_a_froid_mastery_summary(
    summary: AFroidMasteryBusinessSummary2026,
) -> str:
    """
    Formatage conservateur de la maitrise A froid.

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
        f"A froid inconnue : {method!r}"
    )


def _format_progression_metric(
    metric: AFroidProgressionBusinessMetric2026,
) -> str:
    """
    Formate la progression explicitement extraite
    du rapport.

    Le signe positif est conserve :
        +2,8/10

    Le signe negatif est conserve :
        -2,8/10

    Pour une valeur nulle, le texte source est consulte
    afin de conserver +0 ou -0 lorsqu'il est explicite.
    Aucun calcul entre notes n'est effectue.
    """

    value = float(
        metric.value_sur_10
    )

    if value > 0:
        sign = "+"

    elif value < 0:
        sign = "-"

    else:
        source_text = (
            metric.source_text
            or ""
        )

        if re.search(
            r"-\s*0(?:[.,]0+)?\s*/\s*10",
            source_text,
        ):
            sign = "-"

        elif re.search(
            r"\+\s*0(?:[.,]0+)?\s*/\s*10",
            source_text,
        ):
            sign = "+"

        else:
            sign = ""

    return (
        f"{sign}"
        f"{_format_number_fr(abs(value))}"
        "/10"
    )



# =====================================================
# Construction de la ligne finale
# =====================================================

def build_output_row_2026(
    model: PreformationBusinessModel2026,
    *,
    preformation_synthesis: Optional[
        PreformationVerbatimSynthesis2026
    ] = None,
    a_chaud_model: Optional[
        AChaudBusinessModel2026
    ] = None,
    a_chaud_synthesis: Optional[
        VerbatimSynthesis2026
    ] = None,
    a_froid_model: Optional[
        AFroidBusinessModel2026
    ] = None,
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

    if (
        preformation_synthesis is not None
        and not isinstance(
            preformation_synthesis,
            PreformationVerbatimSynthesis2026,
        )
    ):
        raise TypeError(
            "preformation_synthesis doit etre un "
            "PreformationVerbatimSynthesis2026 ou None."
        )

    if (
        a_chaud_model is not None
        and not isinstance(
            a_chaud_model,
            AChaudBusinessModel2026,
        )
    ):
        raise TypeError(
            "a_chaud_model doit etre un "
            "AChaudBusinessModel2026 ou None."
        )

    if (
        a_chaud_synthesis is not None
        and not isinstance(
            a_chaud_synthesis,
            VerbatimSynthesis2026,
        )
    ):
        raise TypeError(
            "a_chaud_synthesis doit etre un "
            "VerbatimSynthesis2026 ou None."
        )

    if (
        a_froid_model is not None
        and not isinstance(
            a_froid_model,
            AFroidBusinessModel2026,
        )
    ):
        raise TypeError(
            "a_froid_model doit etre un "
            "AFroidBusinessModel2026 ou None."
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
    # La synthese est produite en amont.
    # Aucun appel OpenAI n'est effectue ici.
    # -------------------------------------------------

    if preformation_synthesis is not None:
        row[
            "Demande particulière de sujet à aborder"
        ] = (
            preformation_synthesis.sujets_a_aborder
        )

    # -------------------------------------------------
    # 5. AutoEvaluation competence pre-formation
    # -------------------------------------------------

    row[
        "AutoEvaluation compétence pré-formation"
    ] = _format_mastery_summary(
        model.maitrise_summary
    )

    # -------------------------------------------------
    # 6. Formation profitable
    # -------------------------------------------------

    if a_chaud_model is not None:

        row[
            "formation Profitable"
        ] = _format_profitable(
            a_chaud_model
        )

        # ---------------------------------------------
        # 7. Satisfaction du contenu
        # ---------------------------------------------

        row[
            "Satisfaction du contenu"
        ] = _format_satisfaction(
            a_chaud_model
        )

        # ---------------------------------------------
        # 8. Note /10 a chaud
        # ---------------------------------------------

        row[
            "Note /10 à chaud"
        ] = _format_a_chaud_note(
            a_chaud_model
        )

        # ---------------------------------------------
        # 13. Autoanalyse competence
        # ---------------------------------------------

        row[
            "Autoanalyse compétence"
        ] = (
            _format_a_chaud_mastery_summary(
                a_chaud_model.maitrise_summary
            )
        )

    # -------------------------------------------------
    # 9 -> 12. Syntheses des verbatims A chaud
    #
    # La synthese est produite en amont.
    # Aucun appel OpenAI n'est effectue ici.
    # -------------------------------------------------

    if a_chaud_synthesis is not None:

        row[
            "Points forts"
        ] = (
            a_chaud_synthesis.points_forts
        )

        row[
            "Points faibles"
        ] = (
            a_chaud_synthesis.points_faibles
        )

        row[
            (
                "Sujets non traité à reboucler avec formateur "
                "ou nouvelle formation ou attendu"
            )
        ] = (
            a_chaud_synthesis.sujets_reboucler
        )

        row[
            "Evaluation formateurs"
        ] = (
            a_chaud_synthesis.evaluation_formateurs
        )

    # -------------------------------------------------
    # 14 -> 16. A froid
    # -------------------------------------------------

    if a_froid_model is not None:

        # ---------------------------------------------
        # 14. Note /10 a froid
        # ---------------------------------------------

        row[
            "Note /10 à froid"
        ] = _format_a_froid_note(
            a_froid_model
        )

        # ---------------------------------------------
        # 15. Auto-analyse progression
        # ---------------------------------------------

        row[
            "Auto-analyse progression"
        ] = _format_a_froid_mastery_summary(
            a_froid_model.maitrise_summary
        )

        # ---------------------------------------------
        # 16. Impact / Progression des competences
        # ---------------------------------------------

        if (
            a_froid_model.progression_competences
            is not None
        ):
            row[
                "Impact / Progression des compétences"
            ] = _format_progression_metric(
                a_froid_model.progression_competences
            )

    # -------------------------------------------------
    # 17 -> 20
    #
    # Pas encore branches :
    # - synthese A froid ;
    # - questionnaire intervenants ;
    # - synthese finale.
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
