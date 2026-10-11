# utils/a_froid_business_model_2026.py

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from utils.progression_metric_extractor_2026 import (
    ProgressionMetricExtraction2026,
)
from utils.question_extraction_contracts import (
    MasteryObjectivesResult,
    ReportMetricResult,
    ScoreSur10Result,
    VerbatimsResult,
)
from utils.question_registry import (
    normalize_question_text,
)
from utils.question_result_consolidator import (
    OccurrenceExtractionResult,
)


Number = Union[int, float]


# =====================================================
# Note globale a froid
# =====================================================

@dataclass(frozen=True)
class AFroidScoreBusinessOccurrence2026:
    """
    Une note globale A froid explicitement affichee
    dans la source.
    """

    occurrence_id: str
    business_occurrence_index: int
    note_sur_10: Optional[Number]


# =====================================================
# Verbatims "Avec le recul"
# =====================================================

@dataclass(frozen=True)
class AFroidVerbatimsBusinessOccurrence2026:
    """
    Verbatims source consolides exactement.

    Aucun nettoyage, dedoublonnage metier,
    reformulation ou resume n'est effectue ici.
    """

    occurrence_id: str
    business_occurrence_index: int

    items: Tuple[
        str,
        ...,
    ]


# =====================================================
# Maitrise des objectifs a froid
# =====================================================

@dataclass(frozen=True)
class AFroidMasteryBusinessOccurrence2026:
    """
    Une occurrence source de maitrise A froid.

    La note globale source est exposee tandis que
    le payload detaille reste conserve integralement.
    """

    occurrence_id: str
    business_occurrence_index: int

    note_globale_sur_10: Optional[Number]

    source: MasteryObjectivesResult


AFroidMasteryAggregationMethod2026 = Literal[
    "missing",
    "single_source",
    "weighted_same_objectives",
    "multiple_unmerged",
]


@dataclass(frozen=True)
class AFroidMasteryBusinessSummary2026:
    """
    Resume metier conservateur de la maitrise A froid.

    Regles :
    - aucune occurrence -> missing ;
    - une occurrence -> note globale source ;
    - memes objectifs + N fiables -> moyenne ponderee
      des notes globales source ;
    - sinon -> conservation des notes separees.

    Les notes par objectif ne servent jamais a
    reconstruire une note globale absente.
    """

    aggregation_method: (
        AFroidMasteryAggregationMethod2026
    )

    value_sur_10: Optional[Number]

    source_notes: Tuple[
        Optional[Number],
        ...,
    ]

    respondent_counts: Tuple[
        Optional[Number],
        ...,
    ]

    source_occurrence_ids: Tuple[
        str,
        ...,
    ]


# =====================================================
# Progression des competences
# =====================================================

@dataclass(frozen=True)
class AFroidProgressionBusinessMetric2026:
    """
    Metrique de progression explicitement affichee
    dans le rapport.

    Aucun calcul entre une note avant et une note
    apres formation n'est autorise.

    source_text conserve les fragments textuels
    effectivement lus dans le PDF.
    """

    value_sur_10: Number

    source_text: str

    page_number: int

    source: ReportMetricResult


# =====================================================
# Modele public
# =====================================================

@dataclass(frozen=True)
class AFroidBusinessModel2026:
    """
    Modele metier de la partie A froid / resultats
    utile a la sortie standard CESU 83 2026.

    Correspondances futures :
    - note_globale -> colonne 14 ;
    - maitrise_summary -> colonne 15 ;
    - progression_competences -> colonne 16 ;
    - elements_utiles -> colonne 17.

    Ce modele est independant :
    - du PDF ;
    - d'Excel ;
    - de Google Sheets ;
    - de Streamlit ;
    - d'OpenAI ;
    - de la synthese finale des verbatims.
    """

    note_globale: Tuple[
        AFroidScoreBusinessOccurrence2026,
        ...,
    ]

    maitrise_objectifs: Tuple[
        AFroidMasteryBusinessOccurrence2026,
        ...,
    ]

    maitrise_summary: (
        AFroidMasteryBusinessSummary2026
    )

    progression_competences: Optional[
        AFroidProgressionBusinessMetric2026
    ]

    elements_utiles: Tuple[
        AFroidVerbatimsBusinessOccurrence2026,
        ...,
    ]

    issues: Tuple[
        str,
        ...,
    ] = ()


# =====================================================
# Selection des occurrences
# =====================================================

def _select_occurrences(
    occurrences: Sequence[
        OccurrenceExtractionResult
    ],
    *,
    business_key: str,
) -> List[
    OccurrenceExtractionResult
]:
    """
    Selectionne une cle metier A froid tout en
    preservant l'ordre des occurrences source.
    """

    selected = [
        occurrence
        for occurrence in occurrences
        if (
            occurrence.section_key == "a_froid"
            and occurrence.business_key
            == business_key
        )
    ]

    return sorted(
        selected,
        key=lambda occurrence: (
            occurrence.business_occurrence_index,
            occurrence.occurrence_id,
        ),
    )


# =====================================================
# Note globale
# =====================================================

def _build_score_occurrences(
    occurrences: Sequence[
        OccurrenceExtractionResult
    ],
    issues: List[str],
) -> Tuple[
    AFroidScoreBusinessOccurrence2026,
    ...,
]:

    selected = _select_occurrences(
        occurrences,
        business_key=(
            "a_froid.note_globale"
        ),
    )

    output: List[
        AFroidScoreBusinessOccurrence2026
    ] = []

    for occurrence in selected:

        payload = occurrence.payload

        if not isinstance(
            payload,
            ScoreSur10Result,
        ):
            issues.append(
                "a_froid.note_globale / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "payload incompatible."
            )
            continue

        if payload.note_sur_10 is None:
            issues.append(
                "a_froid.note_globale / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "note source absente."
            )

        output.append(
            AFroidScoreBusinessOccurrence2026(
                occurrence_id=(
                    occurrence.occurrence_id
                ),
                business_occurrence_index=(
                    occurrence
                    .business_occurrence_index
                ),
                note_sur_10=(
                    payload.note_sur_10
                ),
            )
        )

    return tuple(
        output
    )


# =====================================================
# Verbatims
# =====================================================

def _build_verbatim_occurrences(
    occurrences: Sequence[
        OccurrenceExtractionResult
    ],
    issues: List[str],
) -> Tuple[
    AFroidVerbatimsBusinessOccurrence2026,
    ...,
]:

    business_key = (
        "a_froid.elements_utiles"
    )

    selected = _select_occurrences(
        occurrences,
        business_key=business_key,
    )

    output: List[
        AFroidVerbatimsBusinessOccurrence2026
    ] = []

    for occurrence in selected:

        payload = occurrence.payload

        if not isinstance(
            payload,
            VerbatimsResult,
        ):
            issues.append(
                f"{business_key} / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "payload incompatible."
            )
            continue

        output.append(
            AFroidVerbatimsBusinessOccurrence2026(
                occurrence_id=(
                    occurrence.occurrence_id
                ),
                business_occurrence_index=(
                    occurrence
                    .business_occurrence_index
                ),
                items=tuple(
                    payload.items
                ),
            )
        )

    return tuple(
        output
    )


# =====================================================
# Maitrise
# =====================================================

def _build_mastery_occurrences(
    occurrences: Sequence[
        OccurrenceExtractionResult
    ],
    issues: List[str],
) -> Tuple[
    AFroidMasteryBusinessOccurrence2026,
    ...,
]:

    selected = _select_occurrences(
        occurrences,
        business_key=(
            "a_froid.maitrise_objectifs"
        ),
    )

    output: List[
        AFroidMasteryBusinessOccurrence2026
    ] = []

    for occurrence in selected:

        payload = occurrence.payload

        if not isinstance(
            payload,
            MasteryObjectivesResult,
        ):
            issues.append(
                "a_froid.maitrise_objectifs / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "payload incompatible."
            )
            continue

        note_globale = (
            payload
            .note_globale_objectifs_preformation
        )

        if note_globale is None:
            issues.append(
                "a_froid.maitrise_objectifs / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "note globale source absente ; "
                "aucune moyenne des objectifs."
            )

        output.append(
            AFroidMasteryBusinessOccurrence2026(
                occurrence_id=(
                    occurrence.occurrence_id
                ),
                business_occurrence_index=(
                    occurrence
                    .business_occurrence_index
                ),
                note_globale_sur_10=(
                    note_globale
                ),
                source=payload,
            )
        )

    return tuple(
        output
    )


def _mastery_respondent_count(
    occurrence: AFroidMasteryBusinessOccurrence2026,
) -> Optional[Number]:
    """
    Retourne N uniquement lorsque chaque objectif
    contient les quatre effectifs et que tous les
    objectifs donnent le meme N.
    """

    objectives = (
        occurrence.source.par_objectif
    )

    if not objectives:
        return None

    totals: List[Number] = []

    for objective in objectives:

        levels = objective.levels

        values = (
            levels.totalement.nb_votants,
            levels.en_partie.nb_votants,
            levels.insuffisamment.nb_votants,
            levels.pas_du_tout.nb_votants,
        )

        if any(
            value is None
            for value in values
        ):
            return None

        total = sum(
            value
            for value in values
            if value is not None
        )

        totals.append(
            total
        )

    if len(
        set(totals)
    ) != 1:
        return None

    return totals[0]


def _mastery_objective_signature(
    occurrence: AFroidMasteryBusinessOccurrence2026,
) -> Tuple[str, ...]:
    """
    Signature uniquement destinee a comparer les
    ensembles d'objectifs entre occurrences.

    Les libelles source ne sont pas modifies.
    """

    return tuple(
        sorted(
            normalize_question_text(
                objective.objectif_label
            )
            for objective
            in occurrence.source.par_objectif
        )
    )


def _build_mastery_summary(
    occurrences: Sequence[
        AFroidMasteryBusinessOccurrence2026
    ],
) -> AFroidMasteryBusinessSummary2026:

    source_notes = tuple(
        occurrence.note_globale_sur_10
        for occurrence in occurrences
    )

    respondent_counts = tuple(
        _mastery_respondent_count(
            occurrence
        )
        for occurrence in occurrences
    )

    occurrence_ids = tuple(
        occurrence.occurrence_id
        for occurrence in occurrences
    )

    # ---------------------------------------------
    # Aucune occurrence
    # ---------------------------------------------

    if not occurrences:
        return AFroidMasteryBusinessSummary2026(
            aggregation_method="missing",
            value_sur_10=None,
            source_notes=(),
            respondent_counts=(),
            source_occurrence_ids=(),
        )

    # ---------------------------------------------
    # Une occurrence : note source uniquement
    # ---------------------------------------------

    if len(
        occurrences
    ) == 1:
        return AFroidMasteryBusinessSummary2026(
            aggregation_method="single_source",
            value_sur_10=source_notes[0],
            source_notes=source_notes,
            respondent_counts=(
                respondent_counts
            ),
            source_occurrence_ids=(
                occurrence_ids
            ),
        )

    # ---------------------------------------------
    # Plusieurs occurrences
    # ---------------------------------------------

    signatures = tuple(
        _mastery_objective_signature(
            occurrence
        )
        for occurrence in occurrences
    )

    same_objectives = (
        len(
            set(signatures)
        )
        == 1
    )

    reliable_counts = all(
        count is not None
        for count in respondent_counts
    )

    reliable_notes = all(
        note is not None
        for note in source_notes
    )

    total_respondents = (
        sum(
            count
            for count in respondent_counts
            if count is not None
        )
        if reliable_counts
        else 0
    )

    if (
        same_objectives
        and reliable_counts
        and reliable_notes
        and total_respondents > 0
    ):

        weighted = (
            sum(
                float(note)
                * float(count)
                for note, count
                in zip(
                    source_notes,
                    respondent_counts,
                )
                if (
                    note is not None
                    and count is not None
                )
            )
            / float(
                total_respondents
            )
        )

        return AFroidMasteryBusinessSummary2026(
            aggregation_method=(
                "weighted_same_objectives"
            ),
            value_sur_10=weighted,
            source_notes=source_notes,
            respondent_counts=(
                respondent_counts
            ),
            source_occurrence_ids=(
                occurrence_ids
            ),
        )

    return AFroidMasteryBusinessSummary2026(
        aggregation_method="multiple_unmerged",
        value_sur_10=None,
        source_notes=source_notes,
        respondent_counts=respondent_counts,
        source_occurrence_ids=occurrence_ids,
    )


# =====================================================
# Progression
# =====================================================

def _build_progression_metric(
    extraction: Optional[
        ProgressionMetricExtraction2026
    ],
    issues: List[str],
) -> Optional[
    AFroidProgressionBusinessMetric2026
]:
    """
    Transforme l'extraction deterministe de progression
    en donnee metier.

    Aucun calcul ou reconstruction n'est effectue.
    """

    if extraction is None:
        return None

    if not isinstance(
        extraction,
        ProgressionMetricExtraction2026,
    ):
        raise TypeError(
            "progression_extraction doit etre un "
            "ProgressionMetricExtraction2026 ou None."
        )

    # Absence legitime dans certains rapports.
    if extraction.status == "not_detected":
        return None

    # Ne jamais choisir une valeur en cas d'ambiguite.
    if extraction.status == "ambiguous":
        issues.append(
            "resultats.progression_competences : "
            "metrique source ambigue ; "
            "aucune valeur retenue."
        )
        return None

    if extraction.status != "success":
        issues.append(
            "resultats.progression_competences : "
            f"statut inconnu {extraction.status!r}."
        )
        return None

    payload = extraction.payload

    if not isinstance(
        payload,
        ReportMetricResult,
    ):
        issues.append(
            "resultats.progression_competences : "
            "payload incompatible."
        )
        return None

    if payload.value_sur_10 is None:
        issues.append(
            "resultats.progression_competences : "
            "valeur source absente."
        )
        return None

    if extraction.source_text is None:
        issues.append(
            "resultats.progression_competences : "
            "texte source absent."
        )
        return None

    if extraction.page_number is None:
        issues.append(
            "resultats.progression_competences : "
            "numero de page source absent."
        )
        return None

    return AFroidProgressionBusinessMetric2026(
        value_sur_10=(
            payload.value_sur_10
        ),
        source_text=(
            extraction.source_text
        ),
        page_number=(
            extraction.page_number
        ),
        source=payload,
    )


# =====================================================
# Public builder
# =====================================================

def build_a_froid_business_model_2026(
    occurrences: Sequence[
        OccurrenceExtractionResult
    ],
    *,
    progression_extraction: Optional[
        ProgressionMetricExtraction2026
    ] = None,
) -> AFroidBusinessModel2026:
    """
    Construit le modele metier A froid 2026 depuis :

    - les occurrences consolidees A froid ;
    - la metrique de progression deterministe
      lorsqu'elle existe.

    Aucun acces PDF.
    Aucun appel OpenAI.
    Aucun acces Excel ou Google Sheets.
    """

    issues: List[str] = []

    note_globale = (
        _build_score_occurrences(
            occurrences,
            issues,
        )
    )

    mastery = (
        _build_mastery_occurrences(
            occurrences,
            issues,
        )
    )

    mastery_summary = (
        _build_mastery_summary(
            mastery
        )
    )

    progression = (
        _build_progression_metric(
            progression_extraction,
            issues,
        )
    )

    elements_utiles = (
        _build_verbatim_occurrences(
            occurrences,
            issues,
        )
    )

    return AFroidBusinessModel2026(
        note_globale=note_globale,
        maitrise_objectifs=mastery,
        maitrise_summary=(
            mastery_summary
        ),
        progression_competences=(
            progression
        ),
        elements_utiles=(
            elements_utiles
        ),
        issues=tuple(
            issues
        ),
    )
