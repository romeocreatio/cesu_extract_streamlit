# utils/question_task_executor.py

from __future__ import annotations

from typing import (
    Callable,
    List,
    Sequence,
)

from utils.question_deterministic_payload_adapter import (
    DeterministicTypedPayload,
)
from utils.question_extraction_contracts import (
    validate_extraction_payload,
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
# Contrat de l'extracteur de tâche
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
# Normalisation de la sortie d'un extracteur
# =====================================================

def _chunk_result_from_extractor_output(
    task: QuestionExtractionTask,
    extractor_output: object,
) -> ChunkExtractionResult:
    """
    Transforme la sortie d'un extracteur en
    ChunkExtractionResult.

    Deux chemins sont supportés :

    1. sortie historique brute :
       parsing selon task.data_kind ;

    2. sortie déterministe déjà typée :
       conservation du detected_data_kind réel.
    """

    # ---------------------------------------------
    # Nouveau chemin déterministe
    # ---------------------------------------------

    if isinstance(
        extractor_output,
        DeterministicTypedPayload,
    ):

        # Le type attendu transporté par
        # l'extraction déterministe doit correspondre
        # à la tâche lorsqu'il est renseigné.
        if (
            extractor_output.expected_data_kind
            is not None
            and extractor_output.expected_data_kind
            != task.data_kind
        ):
            raise ValueError(
                "expected_data_kind incohérent entre "
                "la tâche et l'extraction "
                f"déterministe pour {task.task_id} : "
                f"task={task.data_kind!r}, "
                "extraction="
                f"{extractor_output.expected_data_kind!r}"
            )

        # Défense supplémentaire :
        # le payload doit bien respecter le type
        # réellement détecté.
        validate_extraction_payload(
            data_kind=(
                extractor_output.detected_data_kind
            ),
            payload=extractor_output.payload,
        )

        return ChunkExtractionResult(
            task_id=task.task_id,
            payload=extractor_output.payload,
            detected_data_kind=(
                extractor_output.detected_data_kind
            ),
        )

    # ---------------------------------------------
    # Chemin historique : JSON brut / dict
    # ---------------------------------------------

    payload = parse_extraction_payload(
        data_kind=task.data_kind,
        raw=extractor_output,
    )

    return ChunkExtractionResult(
        task_id=task.task_id,
        payload=payload,
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
    2. il renvoie soit un objet JSON brut,
       soit un DeterministicTypedPayload ;
    3. le chemin brut est parsé selon task.data_kind ;
    4. le chemin déterministe conserve le type réel ;
    5. un ChunkExtractionResult est produit.

    Aucun appel OpenAI n'est imposé ici.
    """

    _validate_tasks(
        [task]
    )

    extractor_output = extractor(
        task
    )

    return _chunk_result_from_extractor_output(
        task=task,
        extractor_output=extractor_output,
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
