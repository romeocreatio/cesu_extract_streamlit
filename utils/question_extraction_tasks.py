# utils/question_extraction_tasks.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from utils.question_block_chunker import (
    QuestionOccurrenceChunk,
)
from utils.question_registry import (
    DataKind,
    MergeStrategy,
)


# =====================================================
# Tâche d'extraction unitaire
# =====================================================

@dataclass(frozen=True)
class QuestionExtractionTask:
    """
    Unité déterministe prête pour une future
    extraction structurée.

    Une tâche correspond exactement à un chunk.

    Aucun appel LLM n'est effectué ici.
    Aucun résultat n'est fusionné ici.
    """

    task_id: str
    occurrence_id: str

    chunk_id: str
    parent_block_id: str
    candidate_id: str

    section_key: str
    pattern_id: str
    source_order: int

    business_key: str
    business_occurrence_index: int

    output_paths: Tuple[str, ...]
    data_kind: DataKind
    merge_strategy: MergeStrategy

    matched_prompt: str

    block_start_page: int
    block_end_page: int

    chunk_index: int
    chunk_count: int

    start_line: int
    end_line: int

    start_char: int
    end_char: int

    text: str

    @property
    def is_multi_chunk_occurrence(self) -> bool:
        return self.chunk_count > 1


# =====================================================
# Groupe d'une occurrence métier
# =====================================================

@dataclass(frozen=True)
class QuestionOccurrenceTaskGroup:
    """
    Ensemble des tâches appartenant à UNE occurrence
    métier précise.

    Important :
    deux occurrences de la même business_key restent
    deux groupes différents.

    Exemple AFGSU2 :

        pre_formation.maitrise_objectifs / occ 1
        pre_formation.maitrise_objectifs / occ 2

    ne doivent jamais être confondus.
    """

    occurrence_id: str

    section_key: str
    business_key: str
    business_occurrence_index: int

    parent_block_id: str
    candidate_id: str

    output_paths: Tuple[str, ...]
    data_kind: DataKind
    merge_strategy: MergeStrategy

    matched_prompt: str

    block_start_page: int
    block_end_page: int

    tasks: Tuple[
        QuestionExtractionTask,
        ...
    ]

    @property
    def task_count(self) -> int:
        return len(self.tasks)

    @property
    def is_chunked(self) -> bool:
        return self.task_count > 1


# =====================================================
# Identifiants
# =====================================================

def _occurrence_id(
    chunk: QuestionOccurrenceChunk,
) -> str:
    """
    Identifiant métier stable de l'occurrence.

    La business_key contient déjà la section.
    """

    return (
        f"{chunk.business_key}:"
        f"occ_{chunk.business_occurrence_index:02d}"
    )


def _task_id(
    chunk: QuestionOccurrenceChunk,
) -> str:
    """
    Identifiant unique de la tâche.

    Même lorsqu'un bloc n'est pas découpé,
    on ajoute explicitement le numéro de chunk
    pour garder un contrat uniforme.
    """

    occurrence_id = _occurrence_id(
        chunk
    )

    return (
        f"{occurrence_id}:"
        f"chunk_{chunk.chunk_index:02d}"
    )


# =====================================================
# Validation des chunks
# =====================================================

def _validate_chunks(
    chunks: Sequence[
        QuestionOccurrenceChunk
    ],
) -> None:
    """
    Vérifie les invariants avant création
    du plan d'extraction.
    """

    seen_chunk_ids: set[str] = set()
    seen_task_ids: set[str] = set()

    for chunk in chunks:

        if chunk.chunk_id in seen_chunk_ids:
            raise ValueError(
                "chunk_id dupliqué : "
                f"{chunk.chunk_id}"
            )

        seen_chunk_ids.add(
            chunk.chunk_id
        )

        task_id = _task_id(
            chunk
        )

        if task_id in seen_task_ids:
            raise ValueError(
                "task_id dupliqué : "
                f"{task_id}"
            )

        seen_task_ids.add(
            task_id
        )

        if chunk.business_occurrence_index < 1:
            raise ValueError(
                "business_occurrence_index invalide : "
                f"{chunk.chunk_id}"
            )

        if chunk.chunk_index < 1:
            raise ValueError(
                "chunk_index invalide : "
                f"{chunk.chunk_id}"
            )

        if chunk.chunk_count < 1:
            raise ValueError(
                "chunk_count invalide : "
                f"{chunk.chunk_id}"
            )

        if chunk.chunk_index > chunk.chunk_count:
            raise ValueError(
                "chunk_index supérieur à chunk_count : "
                f"{chunk.chunk_id}"
            )

        if not chunk.business_key:
            raise ValueError(
                "business_key vide : "
                f"{chunk.chunk_id}"
            )

        if not chunk.output_paths:
            raise ValueError(
                "output_paths vide : "
                f"{chunk.chunk_id}"
            )

        if not chunk.text:
            raise ValueError(
                "texte vide : "
                f"{chunk.chunk_id}"
            )


# =====================================================
# Chunk -> tâche
# =====================================================

def _build_task(
    chunk: QuestionOccurrenceChunk,
) -> QuestionExtractionTask:
    """
    Transforme un chunk métier en tâche d'extraction.
    """

    occurrence_id = _occurrence_id(
        chunk
    )

    return QuestionExtractionTask(
        task_id=_task_id(chunk),
        occurrence_id=occurrence_id,
        chunk_id=chunk.chunk_id,
        parent_block_id=(
            chunk.parent_block_id
        ),
        candidate_id=chunk.candidate_id,
        section_key=chunk.section_key,
        pattern_id=chunk.pattern_id,
        source_order=chunk.source_order,
        business_key=chunk.business_key,
        business_occurrence_index=(
            chunk.business_occurrence_index
        ),
        output_paths=chunk.output_paths,
        data_kind=chunk.data_kind,
        merge_strategy=chunk.merge_strategy,
        matched_prompt=chunk.matched_prompt,
        block_start_page=(
            chunk.block_start_page
        ),
        block_end_page=(
            chunk.block_end_page
        ),
        chunk_index=chunk.chunk_index,
        chunk_count=chunk.chunk_count,
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        start_char=chunk.start_char,
        end_char=chunk.end_char,
        text=chunk.text,
    )


# =====================================================
# Construction des tâches
# =====================================================

def build_question_extraction_tasks(
    chunks: Sequence[
        QuestionOccurrenceChunk
    ],
) -> List[QuestionExtractionTask]:
    """
    Construit les tâches unitaires dans l'ordre
    source puis dans l'ordre des chunks.

    Aucun appel OpenAI.
    """

    if not chunks:
        return []

    _validate_chunks(
        chunks
    )

    ordered_chunks = sorted(
        chunks,
        key=lambda chunk: (
            chunk.source_order,
            chunk.business_occurrence_index,
            chunk.chunk_index,
        ),
    )

    return [
        _build_task(
            chunk
        )
        for chunk in ordered_chunks
    ]


# =====================================================
# Validation d'un groupe
# =====================================================

def _validate_group_tasks(
    occurrence_id: str,
    tasks: Sequence[
        QuestionExtractionTask
    ],
) -> None:
    """
    Vérifie que toutes les tâches d'un groupe
    décrivent réellement la même occurrence.
    """

    if not tasks:
        raise ValueError(
            "Groupe vide : "
            f"{occurrence_id}"
        )

    first = tasks[0]

    expected_chunk_count = (
        first.chunk_count
    )

    if len(tasks) != expected_chunk_count:
        raise ValueError(
            "Nombre de chunks incohérent pour "
            f"{occurrence_id} : "
            f"{len(tasks)} tâches pour "
            f"chunk_count={expected_chunk_count}"
        )

    expected_indexes = list(
        range(
            1,
            expected_chunk_count + 1,
        )
    )

    actual_indexes = [
        task.chunk_index
        for task in tasks
    ]

    if actual_indexes != expected_indexes:
        raise ValueError(
            "Ordre des chunks incohérent pour "
            f"{occurrence_id} : "
            f"{actual_indexes}"
        )

    for task in tasks:

        if task.occurrence_id != occurrence_id:
            raise ValueError(
                "occurrence_id incohérent dans "
                f"{occurrence_id}"
            )

        if task.business_key != first.business_key:
            raise ValueError(
                "business_key incohérente dans "
                f"{occurrence_id}"
            )

        if (
            task.business_occurrence_index
            != first.business_occurrence_index
        ):
            raise ValueError(
                "Numéro d'occurrence incohérent dans "
                f"{occurrence_id}"
            )

        if (
            task.parent_block_id
            != first.parent_block_id
        ):
            raise ValueError(
                "parent_block_id incohérent dans "
                f"{occurrence_id}"
            )

        if task.data_kind != first.data_kind:
            raise ValueError(
                "data_kind incohérent dans "
                f"{occurrence_id}"
            )

        if (
            task.merge_strategy
            != first.merge_strategy
        ):
            raise ValueError(
                "merge_strategy incohérente dans "
                f"{occurrence_id}"
            )

        if (
            task.output_paths
            != first.output_paths
        ):
            raise ValueError(
                "output_paths incohérents dans "
                f"{occurrence_id}"
            )


# =====================================================
# Tâches -> groupes d'occurrences
# =====================================================

def group_question_extraction_tasks(
    tasks: Sequence[
        QuestionExtractionTask
    ],
) -> List[QuestionOccurrenceTaskGroup]:
    """
    Regroupe uniquement les chunks appartenant à
    la MÊME occurrence métier.

    Cette fonction ne fusionne aucun résultat.

    Elle prépare simplement la frontière logique
    nécessaire à la future extraction/consolidation.
    """

    if not tasks:
        return []

    grouped: Dict[
        str,
        List[QuestionExtractionTask],
    ] = {}

    occurrence_order: List[str] = []

    for task in tasks:

        if (
            task.occurrence_id
            not in grouped
        ):
            grouped[
                task.occurrence_id
            ] = []

            occurrence_order.append(
                task.occurrence_id
            )

        grouped[
            task.occurrence_id
        ].append(task)

    output: List[
        QuestionOccurrenceTaskGroup
    ] = []

    for occurrence_id in occurrence_order:

        occurrence_tasks = sorted(
            grouped[occurrence_id],
            key=lambda task: (
                task.chunk_index
            ),
        )

        _validate_group_tasks(
            occurrence_id=occurrence_id,
            tasks=occurrence_tasks,
        )

        first = occurrence_tasks[0]

        output.append(
            QuestionOccurrenceTaskGroup(
                occurrence_id=occurrence_id,
                section_key=first.section_key,
                business_key=first.business_key,
                business_occurrence_index=(
                    first.business_occurrence_index
                ),
                parent_block_id=(
                    first.parent_block_id
                ),
                candidate_id=first.candidate_id,
                output_paths=first.output_paths,
                data_kind=first.data_kind,
                merge_strategy=(
                    first.merge_strategy
                ),
                matched_prompt=(
                    first.matched_prompt
                ),
                block_start_page=(
                    first.block_start_page
                ),
                block_end_page=(
                    first.block_end_page
                ),
                tasks=tuple(
                    occurrence_tasks
                ),
            )
        )

    return output
