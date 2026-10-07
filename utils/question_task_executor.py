# utils/question_task_executor.py

from __future__ import annotations

from typing import (
    Callable,
    List,
    Sequence,
)

from utils.question_extraction_tasks import (
    QuestionExtractionTask,
    QuestionOccurrenceTaskGroup,
)
from utils.question_payload_parser import (
    parse_extraction_payload,
)
from utils.question_result_consolidator import (
    ChunkExtractionResult,
    OccurrenceExtractionResult,
    consolidate_question_results,
)


# =====================================================
# Contrat de l'extracteur brut
# =====================================================

RawTaskExtractor = Callable[
    [QuestionExtractionTask],
    object,
]


# =====================================================
# Validation des tâches
# =====================================================

def _validate_tasks(
    tasks: Sequence[
        QuestionExtractionTask
    ],
) -> None:
    """
    Vérifie les invariants minimaux avant exécution.

    L'ordre fourni est conservé.
    """

    seen_task_ids: set[str] = set()

    for task in tasks:

        if not task.task_id:
            raise ValueError(
                "task_id vide."
            )

        if task.task_id in seen_task_ids:
            raise ValueError(
                "task_id dupliqué : "
                f"{task.task_id}"
            )

        seen_task_ids.add(
            task.task_id
        )

        if not task.text:
            raise ValueError(
                "Texte de tâche vide : "
                f"{task.task_id}"
            )

        if task.chunk_index < 1:
            raise ValueError(
                "chunk_index invalide : "
                f"{task.task_id}"
            )

        if task.chunk_count < 1:
            raise ValueError(
                "chunk_count invalide : "
                f"{task.task_id}"
            )

        if (
            task.chunk_index
            > task.chunk_count
        ):
            raise ValueError(
                "chunk_index supérieur "
                "à chunk_count : "
                f"{task.task_id}"
            )


# =====================================================
# Exécution d'une tâche
# =====================================================

def execute_question_extraction_task(
    task: QuestionExtractionTask,
    extractor: RawTaskExtractor,
) -> ChunkExtractionResult:
    """
    Exécute UNE tâche.

    Étapes :

    1. l'extracteur reçoit la tâche ;
    2. il renvoie un objet JSON brut ;
    3. le parseur transforme ce JSON selon data_kind ;
    4. le payload est validé ;
    5. un ChunkExtractionResult est produit.

    Aucun appel OpenAI n'est imposé ici.
    """

    _validate_tasks(
        [task]
    )

    raw_payload = extractor(
        task
    )

    payload = parse_extraction_payload(
        data_kind=task.data_kind,
        raw=raw_payload,
    )

    return ChunkExtractionResult(
        task_id=task.task_id,
        payload=payload,
    )


# =====================================================
# Exécution d'une liste de tâches
# =====================================================

def execute_question_extraction_tasks(
    tasks: Sequence[
        QuestionExtractionTask
    ],
    extractor: RawTaskExtractor,
) -> List[
    ChunkExtractionResult
]:
    """
    Exécute plusieurs tâches dans leur ordre source.

    Une tâche produit exactement
    un ChunkExtractionResult.
    """

    _validate_tasks(
        tasks
    )

    results: List[
        ChunkExtractionResult
    ] = []

    for task in tasks:

        results.append(
            execute_question_extraction_task(
                task=task,
                extractor=extractor,
            )
        )

    return results


# =====================================================
# Tâches contenues dans les groupes d'occurrences
# =====================================================

def _tasks_from_groups(
    groups: Sequence[
        QuestionOccurrenceTaskGroup
    ],
) -> List[
    QuestionExtractionTask
]:
    """
    Extrait les tâches des groupes dans leur
    ordre d'occurrence puis de chunk.

    Une tâche ne peut appartenir qu'à un seul groupe.
    """

    tasks: List[
        QuestionExtractionTask
    ] = []

    seen_task_ids: set[str] = set()

    for group in groups:

        for task in group.tasks:

            if (
                task.occurrence_id
                != group.occurrence_id
            ):
                raise ValueError(
                    "Tâche rattachée au mauvais "
                    "groupe d'occurrence : "
                    f"{task.task_id}"
                )

            if task.task_id in seen_task_ids:
                raise ValueError(
                    "task_id présent dans "
                    "plusieurs groupes : "
                    f"{task.task_id}"
                )

            seen_task_ids.add(
                task.task_id
            )

            tasks.append(
                task
            )

    return tasks


# =====================================================
# Exécution + consolidation
# =====================================================

def execute_and_consolidate_question_groups(
    groups: Sequence[
        QuestionOccurrenceTaskGroup
    ],
    extractor: RawTaskExtractor,
) -> List[
    OccurrenceExtractionResult
]:
    """
    Pipeline déterministe complet au niveau question :

        groupes
        -> tâches
        -> extraction brute
        -> parsing typé
        -> résultats de chunks
        -> consolidation par occurrence

    Important :
    cette fonction ne fusionne pas plusieurs
    occurrences d'une même business_key.
    """

    tasks = _tasks_from_groups(
        groups
    )

    if not tasks:

        return []

    chunk_results = (
        execute_question_extraction_tasks(
            tasks=tasks,
            extractor=extractor,
        )
    )

    return consolidate_question_results(
        groups=groups,
        results=chunk_results,
    )
