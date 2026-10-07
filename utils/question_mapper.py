# utils/question_mapper.py

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence, Tuple

from utils.question_detector import QuestionCandidate
from utils.question_registry import (
    DataKind,
    MergeStrategy,
    QuestionDefinition,
    match_known_question,
)


# =====================================================
# Types
# =====================================================

MappingStatus = Literal[
    "mapped",
    "unmapped",
]

MappingMethod = Literal[
    "registry_alias",
    "none",
]

MappingConfidence = Literal[
    "high",
    "none",
]


# =====================================================
# Structure publique
# =====================================================

@dataclass(frozen=True)
class QuestionMapping:
    """
    Résultat du rattachement d'un QuestionCandidate
    à une donnée métier stable.

    Cette structure ne contient encore aucune valeur
    extraite du questionnaire.

    Important :
    - toutes les occurrences sont conservées ;
    - aucune occurrence n'est fusionnée ici ;
    - une question structurelle peut rester unmapped ;
    - aucune IA n'est appelée.
    """

    candidate_id: str
    section_key: str

    pattern_id: str
    source_order: int

    start_page: int
    start_line: int

    original_question: str
    matched_prompt: str

    business_key: Optional[str]
    business_occurrence_index: Optional[int]

    output_paths: Tuple[str, ...]
    data_kind: Optional[DataKind]
    merge_strategy: Optional[MergeStrategy]

    mapping_status: MappingStatus
    mapping_method: MappingMethod
    mapping_confidence: MappingConfidence


# =====================================================
# Matching déterministe
# =====================================================

def _match_candidate_definition(
    candidate: QuestionCandidate,
) -> Optional[QuestionDefinition]:
    """
    Recherche une définition métier connue.

    On utilise en priorité matched_prompt car il représente
    la formulation structurelle reconnue par le détecteur.

    Cela évite notamment les perturbations du texte PDF
    lorsque Digiforma injecte un score au milieu du libellé.

    Exemple :

        À ce jour, considérez-vous maîtriser les 7.5
        /
        objectifs du programme ?

    matched_prompt reste :

        À ce jour, considérez-vous maîtriser
        les objectifs du programme

    Le texte source original reste néanmoins conservé.
    """

    definition = match_known_question(
        section_key=candidate.section_key,
        question_text=candidate.matched_prompt,
    )

    if definition is not None:
        return definition

    # Fallback déterministe :
    # utile si le prompt du profil ne correspond pas
    # exactement à un alias mais que le texte source
    # le permet.
    return match_known_question(
        section_key=candidate.section_key,
        question_text=candidate.source_text,
    )


# =====================================================
# Mapping public
# =====================================================

def map_question_candidates(
    candidates: Sequence[QuestionCandidate],
) -> List[QuestionMapping]:
    """
    Mappe une liste de QuestionCandidate vers les
    définitions métier connues du registre.

    Principes :
    - ordre source conservé ;
    - occurrences répétées conservées ;
    - occurrence_index recalculé par business_key ;
    - candidats non connus conservés avec status=unmapped ;
    - aucune fusion ;
    - aucune extraction ;
    - aucune IA.
    """

    ordered_candidates = sorted(
        candidates,
        key=lambda candidate: (
            candidate.source_order,
            candidate.start_page,
            candidate.start_line,
        ),
    )

    occurrence_counts: dict[
        str,
        int,
    ] = {}

    mappings: List[
        QuestionMapping
    ] = []

    for candidate in ordered_candidates:

        definition = _match_candidate_definition(
            candidate
        )

        # -------------------------------------------------
        # Question structurelle sans donnée métier connue
        # -------------------------------------------------

        if definition is None:

            mappings.append(
                QuestionMapping(
                    candidate_id=candidate.candidate_id,
                    section_key=candidate.section_key,
                    pattern_id=candidate.pattern_id,
                    source_order=candidate.source_order,
                    start_page=candidate.start_page,
                    start_line=candidate.start_line,
                    original_question=candidate.source_text,
                    matched_prompt=candidate.matched_prompt,
                    business_key=None,
                    business_occurrence_index=None,
                    output_paths=(),
                    data_kind=None,
                    merge_strategy=None,
                    mapping_status="unmapped",
                    mapping_method="none",
                    mapping_confidence="none",
                )
            )

            continue

        # -------------------------------------------------
        # Question rattachée à une donnée métier
        # -------------------------------------------------

        business_key = definition.business_key

        occurrence_counts[
            business_key
        ] = (
            occurrence_counts.get(
                business_key,
                0,
            )
            + 1
        )

        business_occurrence_index = (
            occurrence_counts[
                business_key
            ]
        )

        mappings.append(
            QuestionMapping(
                candidate_id=candidate.candidate_id,
                section_key=candidate.section_key,
                pattern_id=candidate.pattern_id,
                source_order=candidate.source_order,
                start_page=candidate.start_page,
                start_line=candidate.start_line,
                original_question=candidate.source_text,
                matched_prompt=candidate.matched_prompt,
                business_key=business_key,
                business_occurrence_index=(
                    business_occurrence_index
                ),
                output_paths=definition.output_paths,
                data_kind=definition.data_kind,
                merge_strategy=definition.merge_strategy,
                mapping_status="mapped",
                mapping_method="registry_alias",
                mapping_confidence="high",
            )
        )

    return mappings
