# utils/business_model_2026.py

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
    Distribution1To5Result,
    MasteryObjectivesResult,
    VerbatimsResult,
)
from utils.question_result_consolidator import (
    OccurrenceExtractionResult,
)


Number = Union[int, float]


# =====================================================
# Metadonnees externes
# =====================================================

@dataclass(frozen=True)
class BusinessMetadata2026:
    """
    Metadonnees fournies par l'application.

    Elles ne sont pas extraites du PDF :
    - formation ;
    - semestre ;
    - URL Google Drive du rapport qualite.
    """

    formation: str
    semestre: str
    report_url: str


# =====================================================
# Volonte de suivre la formation
# =====================================================

@dataclass(frozen=True)
class SourceScaleLevel2026:
    """
    Valeur source d'un niveau 1 -> 5.

    Effectif et pourcentage restent exactement
    ceux fournis par l'extraction.
    """

    level: int
    nb_votants: Optional[Number]
    pourcentage: Optional[Number]


@dataclass(frozen=True)
class VolonteBusinessOccurrence2026:
    """
    Une occurrence metier de la question
    'Souhaitiez-vous suivre cette formation ?'.

    Regle CESU 83 :
        4 + 5 -> favorable
        3     -> neutre
        1 + 2 -> non favorable

    Aucun pourcentage manquant n'est reconstruit.
    Aucun reequilibrage vers 100 % n'est applique.
    """

    occurrence_id: str
    business_occurrence_index: int

    source_levels: Tuple[
        SourceScaleLevel2026,
        ...,
    ]

    favorable_pct: Optional[Number]
    neutre_pct: Optional[Number]
    non_favorable_pct: Optional[Number]


# =====================================================
# Sujets a aborder
# =====================================================

@dataclass(frozen=True)
class VerbatimsBusinessOccurrence2026:
    """
    Une occurrence de verbatims.

    Les textes restent strictement ceux issus
    de l'extraction consolidee.

    Aucune suppression, reformulation ou synthese
    n'est faite dans le modele metier.
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
class MasteryBusinessOccurrence2026:
    """
    Une occurrence de maitrise des objectifs.

    La note globale est exposee pour la future
    sortie metier, mais le payload detaille complet
    reste conserve.

    Plusieurs occurrences restent distinctes.
    """

    occurrence_id: str
    business_occurrence_index: int

    note_globale_sur_10: Optional[Number]

    source: MasteryObjectivesResult


# =====================================================
# Modele public preformation
# =====================================================

@dataclass(frozen=True)
class PreformationBusinessModel2026:
    """
    Modele metier 2026 de la preformation.

    Ce modele est independant :
    - d'Excel ;
    - de Google Sheets ;
    - de Streamlit ;
    - d'OpenAI.

    Il conserve les occurrences separement et
    applique seulement les regles metier validees.
    """

    metadata: BusinessMetadata2026

    volonte_suivi: Tuple[
        VolonteBusinessOccurrence2026,
        ...,
    ]

    sujets_a_aborder: Tuple[
        VerbatimsBusinessOccurrence2026,
        ...,
    ]

    maitrise_objectifs: Tuple[
        MasteryBusinessOccurrence2026,
        ...,
    ]

    issues: Tuple[
        str,
        ...,
    ] = ()


# =====================================================
# Helpers
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
    Selectionne une business key de preformation
    et conserve l'ordre des occurrences.
    """

    selected = [
        occurrence
        for occurrence in occurrences
        if (
            occurrence.section_key
            == "pre_formation"
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


def _sum_if_complete(
    *values: Optional[Number],
) -> Optional[Number]:
    """
    Additionne uniquement des valeurs toutes presentes.

    Si une valeur source manque, aucun calcul
    de remplacement n'est effectue.
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
# Construction : volonte de suivre
# =====================================================

def _build_volonte_occurrences(
    occurrences: Sequence[
        OccurrenceExtractionResult
    ],
    issues: List[str],
) -> Tuple[
    VolonteBusinessOccurrence2026,
    ...,
]:

    selected = _select_occurrences(
        occurrences,
        business_key=(
            "pre_formation.volonte_suivi"
        ),
    )

    output: List[
        VolonteBusinessOccurrence2026
    ] = []

    for occurrence in selected:

        payload = occurrence.payload

        if not isinstance(
            payload,
            Distribution1To5Result,
        ):
            issues.append(
                "pre_formation.volonte_suivi / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "payload incompatible."
            )
            continue

        by_level = {
            level.level: level
            for level in payload.levels
        }

        source_levels = tuple(
            SourceScaleLevel2026(
                level=level,
                nb_votants=(
                    by_level[level].nb_votants
                ),
                pourcentage=(
                    by_level[level].pourcentage
                ),
            )
            for level in (
                1,
                2,
                3,
                4,
                5,
            )
        )

        favorable = _sum_if_complete(
            by_level[4].pourcentage,
            by_level[5].pourcentage,
        )

        neutre = (
            by_level[3].pourcentage
        )

        non_favorable = _sum_if_complete(
            by_level[1].pourcentage,
            by_level[2].pourcentage,
        )

        if (
            favorable is None
            or neutre is None
            or non_favorable is None
        ):
            issues.append(
                "pre_formation.volonte_suivi / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "pourcentage source manquant ; "
                "aucune valeur n'a ete reconstruite."
            )

        output.append(
            VolonteBusinessOccurrence2026(
                occurrence_id=(
                    occurrence.occurrence_id
                ),
                business_occurrence_index=(
                    occurrence
                    .business_occurrence_index
                ),
                source_levels=source_levels,
                favorable_pct=favorable,
                neutre_pct=neutre,
                non_favorable_pct=(
                    non_favorable
                ),
            )
        )

    return tuple(
        output
    )


# =====================================================
# Construction : sujets a aborder
# =====================================================

def _build_subject_occurrences(
    occurrences: Sequence[
        OccurrenceExtractionResult
    ],
    issues: List[str],
) -> Tuple[
    VerbatimsBusinessOccurrence2026,
    ...,
]:

    selected = _select_occurrences(
        occurrences,
        business_key=(
            "pre_formation.sujets_a_aborder"
        ),
    )

    output: List[
        VerbatimsBusinessOccurrence2026
    ] = []

    for occurrence in selected:

        payload = occurrence.payload

        if not isinstance(
            payload,
            VerbatimsResult,
        ):
            issues.append(
                "pre_formation.sujets_a_aborder / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "payload incompatible."
            )
            continue

        output.append(
            VerbatimsBusinessOccurrence2026(
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
# Construction : maitrise des objectifs
# =====================================================

def _build_mastery_occurrences(
    occurrences: Sequence[
        OccurrenceExtractionResult
    ],
    issues: List[str],
) -> Tuple[
    MasteryBusinessOccurrence2026,
    ...,
]:

    selected = _select_occurrences(
        occurrences,
        business_key=(
            "pre_formation.maitrise_objectifs"
        ),
    )

    output: List[
        MasteryBusinessOccurrence2026
    ] = []

    for occurrence in selected:

        payload = occurrence.payload

        if not isinstance(
            payload,
            MasteryObjectivesResult,
        ):
            issues.append(
                "pre_formation.maitrise_objectifs / "
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
                "pre_formation.maitrise_objectifs / "
                f"occurrence "
                f"{occurrence.business_occurrence_index}: "
                "note globale absente ; "
                "aucune moyenne des objectifs "
                "n'a ete calculee."
            )

        output.append(
            MasteryBusinessOccurrence2026(
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


# =====================================================
# API publique
# =====================================================

def build_preformation_business_model_2026(
    occurrences: Sequence[
        OccurrenceExtractionResult
    ],
    *,
    formation: str,
    semestre: str,
    report_url: str = "",
) -> PreformationBusinessModel2026:
    """
    Construit le modele metier preformation 2026
    a partir des occurrences deja validees.

    Cette fonction ne :
    - modifie pas les extracteurs ;
    - n'appelle aucun LLM ;
    - ne reconstruit aucune donnee manquante ;
    - ne moyenne pas plusieurs occurrences ;
    - ne connait aucune colonne Excel.
    """

    if not isinstance(
        formation,
        str,
    ):
        raise TypeError(
            "formation doit etre une chaine."
        )

    if not isinstance(
        semestre,
        str,
    ):
        raise TypeError(
            "semestre doit etre une chaine."
        )

    if not isinstance(
        report_url,
        str,
    ):
        raise TypeError(
            "report_url doit etre une chaine."
        )

    formation_clean = (
        formation.strip()
    )

    semestre_clean = (
        semestre.strip()
    )

    report_url_clean = (
        report_url.strip()
    )

    if not formation_clean:
        raise ValueError(
            "formation ne doit pas etre vide."
        )

    if not semestre_clean:
        raise ValueError(
            "semestre ne doit pas etre vide."
        )

    issues: List[str] = []

    metadata = BusinessMetadata2026(
        formation=formation_clean,
        semestre=semestre_clean,
        report_url=report_url_clean,
    )

    return PreformationBusinessModel2026(
        metadata=metadata,
        volonte_suivi=(
            _build_volonte_occurrences(
                occurrences,
                issues,
            )
        ),
        sujets_a_aborder=(
            _build_subject_occurrences(
                occurrences,
                issues,
            )
        ),
        maitrise_objectifs=(
            _build_mastery_occurrences(
                occurrences,
                issues,
            )
        ),
        issues=tuple(
            issues
        ),
    )
