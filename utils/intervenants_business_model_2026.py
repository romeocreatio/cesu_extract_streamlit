# utils/intervenants_business_model_2026.py

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from utils.question_extraction_contracts import (
    DistributionYesNoResult,
    TextResult,
)
from utils.question_registry import (
    normalize_question_text,
)
from utils.question_result_consolidator import (
    OccurrenceExtractionResult,
)


Number = Union[int, float]


# =====================================================
# Texte source intervenants
# =====================================================

@dataclass(frozen=True)
class IntervenantsTextBusinessOccurrence2026:
    """
    Une occurrence de texte libre du questionnaire
    intervenants.

    Le texte provient directement du payload déterministe.
    Aucune reformulation, synthèse ou interprétation
    n'est effectuée ici.
    """

    occurrence_id: str
    business_occurrence_index: int

    text: str

    source: TextResult


# =====================================================
# Valeur catégorielle source
# =====================================================

@dataclass(frozen=True)
class IntervenantsSourceCategoryValue2026:
    """
    Une modalité source exactement telle qu'extraite.

    Aucun effectif ni pourcentage manquant n'est
    reconstruit.
    """

    label: str
    nb_votants: Optional[Number]
    pourcentage: Optional[Number]


# =====================================================
# Adaptation des horaires
# =====================================================

@dataclass(frozen=True)
class IntervenantsAdaptationHorairesOccurrence2026:
    """
    Une occurrence de la question sur l'adaptation
    des horaires.

    Les quatre valeurs métier proviennent uniquement
    des valeurs explicitement extraites de la source.

    Aucun calcul du type :
        NON = 100 - OUI
    n'est autorisé.
    """

    occurrence_id: str
    business_occurrence_index: int

    source_items: Tuple[
        IntervenantsSourceCategoryValue2026,
        ...,
    ]

    oui_count: Optional[Number]
    oui_percentage: Optional[Number]

    non_count: Optional[Number]
    non_percentage: Optional[Number]

    source: DistributionYesNoResult


# =====================================================
# Modèle public
# =====================================================

@dataclass(frozen=True)
class IntervenantsBusinessModel2026:
    """
    Modèle métier brut de la section intervenants 2026.

    Sources destinées ultérieurement à :
    - colonne 18 : Problématiques remontées ;
    - colonne 19 : Adaptations de programme.

    Ce modèle est indépendant :
    - du PDF ;
    - d'Excel ;
    - de Google Sheets ;
    - de Streamlit ;
    - d'OpenAI ;
    - de la synthèse finale.
    """

    commentaire_conditions_materielles: Tuple[
        IntervenantsTextBusinessOccurrence2026,
        ...,
    ]

    commentaire_groupe_apprenants: Tuple[
        IntervenantsTextBusinessOccurrence2026,
        ...,
    ]

    commentaire_organisation_generale: Tuple[
        IntervenantsTextBusinessOccurrence2026,
        ...,
    ]

    adaptation_horaires: Tuple[
        IntervenantsAdaptationHorairesOccurrence2026,
        ...,
    ]

    explication_modification_programme: Tuple[
        IntervenantsTextBusinessOccurrence2026,
        ...,
    ]

    issues: Tuple[
        str,
        ...,
    ] = ()


# =====================================================
# Sélection des occurrences
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
    Sélectionne une clé métier intervenants en
    préservant l'ordre des occurrences source.
    """

    selected = [
        occurrence
        for occurrence in occurrences
        if (
            occurrence.section_key
            == "intervenants"
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
# Texte libre
# =====================================================

def _build_text_occurrences(
    occurrences: Sequence[
        OccurrenceExtractionResult
    ],
    *,
    business_key: str,
    issues: List[str],
) -> Tuple[
    IntervenantsTextBusinessOccurrence2026,
    ...,
]:

    selected = _select_occurrences(
        occurrences,
        business_key=business_key,
    )

    output: List[
        IntervenantsTextBusinessOccurrence2026
    ] = []

    for occurrence in selected:

        payload = occurrence.payload

        if not isinstance(
            payload,
            TextResult,
        ):
            issues.append(
                f"{business_key} / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "payload incompatible."
            )
            continue

        output.append(
            IntervenantsTextBusinessOccurrence2026(
                occurrence_id=(
                    occurrence.occurrence_id
                ),
                business_occurrence_index=(
                    occurrence
                    .business_occurrence_index
                ),
                text=payload.text,
                source=payload,
            )
        )

    return tuple(
        output
    )


# =====================================================
# Adaptation horaires
# =====================================================

def _source_category_items(
    payload: DistributionYesNoResult,
) -> Tuple[
    IntervenantsSourceCategoryValue2026,
    ...,
]:

    return tuple(
        IntervenantsSourceCategoryValue2026(
            label=item.label,
            nb_votants=item.nb_votants,
            pourcentage=item.pourcentage,
        )
        for item in payload.items
    )


def _single_category(
    payload: DistributionYesNoResult,
    *,
    normalized_label: str,
    business_key: str,
    occurrence_index: int,
    issues: List[str],
):
    """
    Retourne la modalité uniquement lorsqu'elle existe
    exactement une fois.

    Aucun choix arbitraire n'est effectué en cas de
    doublon ou d'absence.
    """

    matches = [
        item
        for item in payload.items
        if (
            normalize_question_text(
                item.label
            )
            == normalized_label
        )
    ]

    if len(matches) != 1:

        issues.append(
            f"{business_key} / occurrence "
            f"{occurrence_index}: "
            f"modalité {normalized_label!r} "
            f"présente {len(matches)} fois."
        )

        return None

    return matches[0]


def _build_adaptation_horaires(
    occurrences: Sequence[
        OccurrenceExtractionResult
    ],
    issues: List[str],
) -> Tuple[
    IntervenantsAdaptationHorairesOccurrence2026,
    ...,
]:

    business_key = (
        "intervenants.adaptation_horaires"
    )

    selected = _select_occurrences(
        occurrences,
        business_key=business_key,
    )

    output: List[
        IntervenantsAdaptationHorairesOccurrence2026
    ] = []

    for occurrence in selected:

        payload = occurrence.payload

        if not isinstance(
            payload,
            DistributionYesNoResult,
        ):
            issues.append(
                f"{business_key} / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "payload incompatible."
            )
            continue

        normalized_labels = tuple(
            normalize_question_text(
                item.label
            )
            for item in payload.items
        )

        unknown_labels = tuple(
            label
            for label in normalized_labels
            if label not in {
                "oui",
                "non",
            }
        )

        if unknown_labels:

            issues.append(
                f"{business_key} / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "modalités inattendues "
                f"{unknown_labels!r}."
            )

        oui = _single_category(
            payload,
            normalized_label="oui",
            business_key=business_key,
            occurrence_index=(
                occurrence
                .business_occurrence_index
            ),
            issues=issues,
        )

        non = _single_category(
            payload,
            normalized_label="non",
            business_key=business_key,
            occurrence_index=(
                occurrence
                .business_occurrence_index
            ),
            issues=issues,
        )

        output.append(
            IntervenantsAdaptationHorairesOccurrence2026(
                occurrence_id=(
                    occurrence.occurrence_id
                ),
                business_occurrence_index=(
                    occurrence
                    .business_occurrence_index
                ),
                source_items=(
                    _source_category_items(
                        payload
                    )
                ),
                oui_count=(
                    oui.nb_votants
                    if oui is not None
                    else None
                ),
                oui_percentage=(
                    oui.pourcentage
                    if oui is not None
                    else None
                ),
                non_count=(
                    non.nb_votants
                    if non is not None
                    else None
                ),
                non_percentage=(
                    non.pourcentage
                    if non is not None
                    else None
                ),
                source=payload,
            )
        )

    return tuple(
        output
    )


# =====================================================
# Builder public
# =====================================================

def build_intervenants_business_model_2026(
    occurrences: Sequence[
        OccurrenceExtractionResult
    ],
) -> IntervenantsBusinessModel2026:
    """
    Construit le modèle métier intervenants 2026
    depuis les occurrences consolidées.

    Aucun accès PDF.
    Aucun appel OpenAI.
    Aucun accès Excel ou Google Sheets.
    """

    issues: List[str] = []

    conditions = (
        _build_text_occurrences(
            occurrences,
            business_key=(
                "intervenants."
                "commentaire_conditions_materielles"
            ),
            issues=issues,
        )
    )

    groupe = (
        _build_text_occurrences(
            occurrences,
            business_key=(
                "intervenants."
                "commentaire_groupe_apprenants"
            ),
            issues=issues,
        )
    )

    organisation = (
        _build_text_occurrences(
            occurrences,
            business_key=(
                "intervenants."
                "commentaire_organisation_generale"
            ),
            issues=issues,
        )
    )

    adaptation = (
        _build_adaptation_horaires(
            occurrences,
            issues,
        )
    )

    modification = (
        _build_text_occurrences(
            occurrences,
            business_key=(
                "intervenants."
                "explication_modification_programme"
            ),
            issues=issues,
        )
    )

    return IntervenantsBusinessModel2026(
        commentaire_conditions_materielles=(
            conditions
        ),
        commentaire_groupe_apprenants=(
            groupe
        ),
        commentaire_organisation_generale=(
            organisation
        ),
        adaptation_horaires=(
            adaptation
        ),
        explication_modification_programme=(
            modification
        ),
        issues=tuple(
            issues
        ),
    )
