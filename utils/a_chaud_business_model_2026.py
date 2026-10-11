# utils/a_chaud_business_model_2026.py

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

from utils.question_extraction_contracts import (
    DistributionCategoriesResult,
    DistributionYesNoResult,
    MasteryObjectivesResult,
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
# Source categorical values
# =====================================================

@dataclass(frozen=True)
class SourceCategoryValue2026:
    """
    One source category exactly as extracted.

    Label, count and percentage are preserved.
    """

    label: str
    nb_votants: Optional[Number]
    pourcentage: Optional[Number]


# =====================================================
# Formation profitable
# =====================================================

@dataclass(frozen=True)
class ProfitableBusinessOccurrence2026:
    """
    One occurrence of the profitable question.

    oui_pct / non_pct come only from displayed
    source percentages.

    Counts are never used to reconstruct percentages.
    """

    occurrence_id: str
    business_occurrence_index: int

    source_items: Tuple[
        SourceCategoryValue2026,
        ...,
    ]

    oui_pct: Optional[Number]
    non_pct: Optional[Number]


# =====================================================
# Satisfaction contenu
# =====================================================

@dataclass(frozen=True)
class SatisfactionBusinessOccurrence2026:
    """
    CESU 83 business grouping:

        Tres satisfait-e
        + Satisfait-e
        = satisfait_pct

        Decu-e
        = decu_pct

        Sans opinion
        = sans_opinion_pct

    Only displayed source percentages are used.
    No rebalance to 100 percent.
    """

    occurrence_id: str
    business_occurrence_index: int

    source_items: Tuple[
        SourceCategoryValue2026,
        ...,
    ]

    satisfait_pct: Optional[Number]
    decu_pct: Optional[Number]
    sans_opinion_pct: Optional[Number]


# =====================================================
# Note globale a chaud
# =====================================================

@dataclass(frozen=True)
class ScoreBusinessOccurrence2026:
    """
    Global score explicitly displayed in the source.
    """

    occurrence_id: str
    business_occurrence_index: int

    note_sur_10: Optional[Number]


# =====================================================
# Verbatims
# =====================================================

@dataclass(frozen=True)
class AChaudVerbatimsBusinessOccurrence2026:
    """
    Exact consolidated source verbatims.

    No cleaning, deduplication, rewriting or summary
    is performed in the business model.
    """

    occurrence_id: str
    business_occurrence_index: int

    items: Tuple[
        str,
        ...,
    ]


# =====================================================
# Maitrise des objectifs
# =====================================================

@dataclass(frozen=True)
class AChaudMasteryBusinessOccurrence2026:
    """
    One source mastery occurrence.

    The global source score is exposed while the
    complete detailed payload remains preserved.
    """

    occurrence_id: str
    business_occurrence_index: int

    note_globale_sur_10: Optional[Number]

    source: MasteryObjectivesResult


AChaudMasteryAggregationMethod2026 = Literal[
    "missing",
    "single_source",
    "weighted_same_objectives",
    "multiple_unmerged",
]


@dataclass(frozen=True)
class AChaudMasteryBusinessSummary2026:
    """
    Conservative business summary of mastery.

    Rules:
    - no occurrence -> missing;
    - one occurrence -> source score;
    - same objective set + reliable N -> weighted
      source global scores;
    - otherwise -> preserve separate source scores.

    Objective-level scores are never averaged to
    reconstruct a missing global score.
    """

    aggregation_method: (
        AChaudMasteryAggregationMethod2026
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
# Public model
# =====================================================

@dataclass(frozen=True)
class AChaudBusinessModel2026:
    """
    Business model for the standard 2026 A chaud
    section.

    Independent from:
    - Excel;
    - Google Sheets;
    - Streamlit;
    - OpenAI;
    - final text synthesis.
    """

    formation_profitable: Tuple[
        ProfitableBusinessOccurrence2026,
        ...,
    ]

    satisfaction_contenu: Tuple[
        SatisfactionBusinessOccurrence2026,
        ...,
    ]

    note_globale: Tuple[
        ScoreBusinessOccurrence2026,
        ...,
    ]

    points_forts: Tuple[
        AChaudVerbatimsBusinessOccurrence2026,
        ...,
    ]

    points_a_ajuster: Tuple[
        AChaudVerbatimsBusinessOccurrence2026,
        ...,
    ]

    suggestions_complement: Tuple[
        AChaudVerbatimsBusinessOccurrence2026,
        ...,
    ]

    appreciations_intervenants: Tuple[
        AChaudVerbatimsBusinessOccurrence2026,
        ...,
    ]

    maitrise_objectifs: Tuple[
        AChaudMasteryBusinessOccurrence2026,
        ...,
    ]

    maitrise_summary: (
        AChaudMasteryBusinessSummary2026
    )

    issues: Tuple[
        str,
        ...,
    ] = ()


# =====================================================
# Generic helpers
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
    Select one A chaud business key while preserving
    occurrence order.
    """

    selected = [
        occurrence
        for occurrence in occurrences
        if (
            occurrence.section_key == "a_chaud"
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


def _source_category_items(
    items,
) -> Tuple[
    SourceCategoryValue2026,
    ...,
]:
    return tuple(
        SourceCategoryValue2026(
            label=item.label,
            nb_votants=item.nb_votants,
            pourcentage=item.pourcentage,
        )
        for item in items
    )


def _sum_if_complete(
    *values: Optional[Number],
) -> Optional[Number]:
    """
    Sum only explicit source values.

    Missing input means missing result.
    """

    if any(
        value is None
        for value in values
    ):
        return None

    return sum(
        value
        for value in values
        if value is not None
    )


# =====================================================
# Formation profitable
# =====================================================

def _build_profitable_occurrences(
    occurrences: Sequence[
        OccurrenceExtractionResult
    ],
    issues: List[str],
) -> Tuple[
    ProfitableBusinessOccurrence2026,
    ...,
]:

    selected = _select_occurrences(
        occurrences,
        business_key=(
            "a_chaud.formation_profitable"
        ),
    )

    output: List[
        ProfitableBusinessOccurrence2026
    ] = []

    for occurrence in selected:

        payload = occurrence.payload

        if not isinstance(
            payload,
            DistributionYesNoResult,
        ):
            issues.append(
                "a_chaud.formation_profitable / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "payload incompatible."
            )
            continue

        source_items = (
            _source_category_items(
                payload.items
            )
        )

        by_label = {
            normalize_question_text(
                item.label
            ): item
            for item in payload.items
        }

        unknown_labels = tuple(
            label
            for label in by_label
            if label not in {
                "oui",
                "non",
            }
        )

        if unknown_labels:
            issues.append(
                "a_chaud.formation_profitable / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "modalite source inconnue."
            )

        oui_item = by_label.get(
            "oui"
        )

        non_item = by_label.get(
            "non"
        )

        oui_pct = (
            oui_item.pourcentage
            if oui_item is not None
            else None
        )

        non_pct = (
            non_item.pourcentage
            if non_item is not None
            else None
        )

        if (
            oui_item is None
            or non_item is None
        ):
            issues.append(
                "a_chaud.formation_profitable / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "modalite OUI ou NON absente."
            )

        if (
            oui_pct is None
            or non_pct is None
        ):
            issues.append(
                "a_chaud.formation_profitable / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "pourcentage source manquant ; "
                "aucun recalcul depuis les effectifs."
            )

        output.append(
            ProfitableBusinessOccurrence2026(
                occurrence_id=(
                    occurrence.occurrence_id
                ),
                business_occurrence_index=(
                    occurrence
                    .business_occurrence_index
                ),
                source_items=source_items,
                oui_pct=oui_pct,
                non_pct=non_pct,
            )
        )

    return tuple(
        output
    )


# =====================================================
# Satisfaction contenu
# =====================================================

_SATISFACTION_POSITIVE_LABELS = {
    "tres satisfait e",
    "satisfait e",
}

_SATISFACTION_DECU_LABELS = {
    "decu e",
}

_SATISFACTION_SANS_OPINION_LABELS = {
    "sans opinion",
}


def _build_satisfaction_occurrences(
    occurrences: Sequence[
        OccurrenceExtractionResult
    ],
    issues: List[str],
) -> Tuple[
    SatisfactionBusinessOccurrence2026,
    ...,
]:

    selected = _select_occurrences(
        occurrences,
        business_key=(
            "a_chaud.satisfaction_contenu"
        ),
    )

    output: List[
        SatisfactionBusinessOccurrence2026
    ] = []

    for occurrence in selected:

        payload = occurrence.payload

        if not isinstance(
            payload,
            DistributionCategoriesResult,
        ):
            issues.append(
                "a_chaud.satisfaction_contenu / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "payload incompatible."
            )
            continue

        source_items = (
            _source_category_items(
                payload.items
            )
        )

        positive_values: List[
            Optional[Number]
        ] = []

        decu_values: List[
            Optional[Number]
        ] = []

        sans_opinion_values: List[
            Optional[Number]
        ] = []

        unknown_labels: List[str] = []

        for item in payload.items:

            label = normalize_question_text(
                item.label
            )

            if (
                label
                in _SATISFACTION_POSITIVE_LABELS
            ):
                positive_values.append(
                    item.pourcentage
                )

            elif (
                label
                in _SATISFACTION_DECU_LABELS
            ):
                decu_values.append(
                    item.pourcentage
                )

            elif (
                label
                in _SATISFACTION_SANS_OPINION_LABELS
            ):
                sans_opinion_values.append(
                    item.pourcentage
                )

            else:
                unknown_labels.append(
                    item.label
                )

        if unknown_labels:
            issues.append(
                "a_chaud.satisfaction_contenu / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "modalite source inconnue."
            )

        if len(
            positive_values
        ) != 2:
            issues.append(
                "a_chaud.satisfaction_contenu / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "categories positives incompletes."
            )

        if len(
            decu_values
        ) != 1:
            issues.append(
                "a_chaud.satisfaction_contenu / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "categorie decu incomplete."
            )

        if len(
            sans_opinion_values
        ) != 1:
            issues.append(
                "a_chaud.satisfaction_contenu / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "categorie sans opinion incomplete."
            )

        satisfait_pct = (
            _sum_if_complete(
                *positive_values
            )
            if len(
                positive_values
            ) == 2
            else None
        )

        decu_pct = (
            decu_values[0]
            if len(
                decu_values
            ) == 1
            else None
        )

        sans_opinion_pct = (
            sans_opinion_values[0]
            if len(
                sans_opinion_values
            ) == 1
            else None
        )

        if (
            satisfait_pct is None
            or decu_pct is None
            or sans_opinion_pct is None
        ):
            issues.append(
                "a_chaud.satisfaction_contenu / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "pourcentage source manquant ; "
                "aucun recalcul depuis les effectifs."
            )

        output.append(
            SatisfactionBusinessOccurrence2026(
                occurrence_id=(
                    occurrence.occurrence_id
                ),
                business_occurrence_index=(
                    occurrence
                    .business_occurrence_index
                ),
                source_items=source_items,
                satisfait_pct=satisfait_pct,
                decu_pct=decu_pct,
                sans_opinion_pct=(
                    sans_opinion_pct
                ),
            )
        )

    return tuple(
        output
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
    ScoreBusinessOccurrence2026,
    ...,
]:

    selected = _select_occurrences(
        occurrences,
        business_key=(
            "a_chaud.note_globale"
        ),
    )

    output: List[
        ScoreBusinessOccurrence2026
    ] = []

    for occurrence in selected:

        payload = occurrence.payload

        if not isinstance(
            payload,
            ScoreSur10Result,
        ):
            issues.append(
                "a_chaud.note_globale / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "payload incompatible."
            )
            continue

        if payload.note_sur_10 is None:
            issues.append(
                "a_chaud.note_globale / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "note source absente."
            )

        output.append(
            ScoreBusinessOccurrence2026(
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
    *,
    business_key: str,
    issues: List[str],
) -> Tuple[
    AChaudVerbatimsBusinessOccurrence2026,
    ...,
]:

    selected = _select_occurrences(
        occurrences,
        business_key=business_key,
    )

    output: List[
        AChaudVerbatimsBusinessOccurrence2026
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
            AChaudVerbatimsBusinessOccurrence2026(
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
    AChaudMasteryBusinessOccurrence2026,
    ...,
]:

    selected = _select_occurrences(
        occurrences,
        business_key=(
            "a_chaud.maitrise_objectifs"
        ),
    )

    output: List[
        AChaudMasteryBusinessOccurrence2026
    ] = []

    for occurrence in selected:

        payload = occurrence.payload

        if not isinstance(
            payload,
            MasteryObjectivesResult,
        ):
            issues.append(
                "a_chaud.maitrise_objectifs / "
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
                "a_chaud.maitrise_objectifs / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "note globale source absente ; "
                "aucune moyenne des objectifs."
            )

        output.append(
            AChaudMasteryBusinessOccurrence2026(
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
    occurrence: AChaudMasteryBusinessOccurrence2026,
) -> Optional[Number]:
    """
    Return N only when every objective has complete
    counts and all objectives produce the same N.
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
    occurrence: AChaudMasteryBusinessOccurrence2026,
) -> Tuple[str, ...]:
    """
    Comparison signature only.

    Source objective labels remain untouched.
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
        AChaudMasteryBusinessOccurrence2026
    ],
) -> AChaudMasteryBusinessSummary2026:

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

    if not occurrences:
        return AChaudMasteryBusinessSummary2026(
            aggregation_method="missing",
            value_sur_10=None,
            source_notes=(),
            respondent_counts=(),
            source_occurrence_ids=(),
        )

    if len(
        occurrences
    ) == 1:
        return AChaudMasteryBusinessSummary2026(
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

        return AChaudMasteryBusinessSummary2026(
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

    return AChaudMasteryBusinessSummary2026(
        aggregation_method="multiple_unmerged",
        value_sur_10=None,
        source_notes=source_notes,
        respondent_counts=respondent_counts,
        source_occurrence_ids=occurrence_ids,
    )


# =====================================================
# Public builder
# =====================================================

def build_a_chaud_business_model_2026(
    occurrences: Sequence[
        OccurrenceExtractionResult
    ],
) -> AChaudBusinessModel2026:
    """
    Build the A chaud 2026 business model from
    consolidated extraction occurrences.

    No PDF access.
    No OpenAI call.
    No Excel or Google Sheets access.
    """

    issues: List[str] = []

    profitable = (
        _build_profitable_occurrences(
            occurrences,
            issues,
        )
    )

    satisfaction = (
        _build_satisfaction_occurrences(
            occurrences,
            issues,
        )
    )

    note_globale = (
        _build_score_occurrences(
            occurrences,
            issues,
        )
    )

    points_forts = (
        _build_verbatim_occurrences(
            occurrences,
            business_key=(
                "a_chaud.points_forts"
            ),
            issues=issues,
        )
    )

    points_a_ajuster = (
        _build_verbatim_occurrences(
            occurrences,
            business_key=(
                "a_chaud.points_a_ajuster"
            ),
            issues=issues,
        )
    )

    suggestions_complement = (
        _build_verbatim_occurrences(
            occurrences,
            business_key=(
                "a_chaud.suggestions_complement"
            ),
            issues=issues,
        )
    )

    appreciations_intervenants = (
        _build_verbatim_occurrences(
            occurrences,
            business_key=(
                "a_chaud.appreciations_intervenants"
            ),
            issues=issues,
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

    return AChaudBusinessModel2026(
        formation_profitable=profitable,
        satisfaction_contenu=satisfaction,
        note_globale=note_globale,
        points_forts=points_forts,
        points_a_ajuster=(
            points_a_ajuster
        ),
        suggestions_complement=(
            suggestions_complement
        ),
        appreciations_intervenants=(
            appreciations_intervenants
        ),
        maitrise_objectifs=mastery,
        maitrise_summary=(
            mastery_summary
        ),
        issues=tuple(
            issues
        ),
    )
