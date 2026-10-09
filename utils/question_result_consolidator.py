# utils/question_result_consolidator.py

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
)

from utils.question_extraction_contracts import (
    QuestionExtractionPayload,
    VerbatimsResult,
    validate_extraction_payload,
)
from utils.question_extraction_tasks import (
    QuestionExtractionTask,
    QuestionOccurrenceTaskGroup,
)
from utils.question_registry import (
    DataKind,
    MergeStrategy,
)


# =====================================================
# Résultat d'une tâche / d'un chunk
# =====================================================

@dataclass(frozen=True)
class ChunkExtractionResult:
    """
    Résultat structuré produit pour UNE tâche
    d'extraction.

    À ce stade, ce résultat pourra être synthétique
    dans les tests ou produit plus tard par le LLM.
    """

    task_id: str
    payload: QuestionExtractionPayload

    # Type réellement produit par l'extraction.
    #
    # None conserve le comportement historique :
    # le data_kind attendu par la tâche est utilisé.
    detected_data_kind: Optional[
        DataKind
    ] = None


# =====================================================
# Résultat consolidé d'une occurrence
# =====================================================

@dataclass(frozen=True)
class OccurrenceExtractionResult:
    """
    Résultat consolidé d'UNE occurrence métier.

    Important :
    deux occurrences différentes de la même
    business_key restent deux objets distincts.
    """

    occurrence_id: str

    section_key: str
    business_key: str
    business_occurrence_index: int

    output_paths: Tuple[str, ...]
    data_kind: DataKind
    merge_strategy: MergeStrategy

    source_task_ids: Tuple[str, ...]

    payload: QuestionExtractionPayload

    # Type réellement observé dans la source.
    #
    # data_kind reste le type attendu par le registre
    # pour préserver la compatibilité du pipeline.
    detected_data_kind: Optional[
        DataKind
    ] = None

    @property
    def effective_data_kind(
        self,
    ) -> DataKind:
        """
        Type à utiliser pour valider/interpréter
        le payload.
        """

        return (
            self.detected_data_kind
            or self.data_kind
        )

    @property
    def matches_expected_data_kind(
        self,
    ) -> Optional[bool]:
        """
        Compare le type réel au type du registre.

        None signifie qu'aucun type réellement
        détecté n'a été fourni.
        """

        if self.detected_data_kind is None:
            return None

        return (
            self.detected_data_kind
            == self.data_kind
        )


# =====================================================
# Type réellement porté par un résultat de chunk
# =====================================================

def _effective_chunk_data_kind(
    task: QuestionExtractionTask,
    result: ChunkExtractionResult,
) -> DataKind:
    """
    Retourne le type réellement extrait lorsqu'il
    est fourni.

    Sinon, conserve le comportement historique
    basé sur le data_kind attendu par la tâche.
    """

    return (
        result.detected_data_kind
        or task.data_kind
    )



# =====================================================
# Verbatim localisé dans le bloc parent
# =====================================================

@dataclass(frozen=True)
class _LocatedVerbatim:
    """
    Verbatim rattaché à sa position absolue dans
    le bloc parent.

    Cela permet de distinguer :

    - le même verbatim répété par deux répondants
      à deux positions différentes ;

    - le même verbatim vu deux fois uniquement
      parce que deux chunks se chevauchent.
    """

    text: str

    absolute_start: int
    absolute_end: int


# =====================================================
# Index des résultats
# =====================================================

def _index_chunk_results(
    results: Sequence[
        ChunkExtractionResult
    ],
) -> Dict[str, ChunkExtractionResult]:
    """
    Construit un index task_id -> résultat
    et refuse les doublons.
    """

    indexed: Dict[
        str,
        ChunkExtractionResult,
    ] = {}

    for result in results:

        if result.task_id in indexed:
            raise ValueError(
                "Résultat dupliqué pour task_id="
                f"{result.task_id}"
            )

        indexed[
            result.task_id
        ] = result

    return indexed


# =====================================================
# Association tâches -> résultats
# =====================================================

def _ordered_task_results(
    group: QuestionOccurrenceTaskGroup,
    results: Sequence[
        ChunkExtractionResult
    ],
) -> List[
    Tuple[
        QuestionExtractionTask,
        ChunkExtractionResult,
    ]
]:
    """
    Vérifie qu'il existe exactement un résultat
    pour chaque tâche du groupe, sans résultat
    supplémentaire.
    """

    indexed = _index_chunk_results(
        results
    )

    expected_task_ids = {
        task.task_id
        for task in group.tasks
    }

    actual_task_ids = set(
        indexed
    )

    missing = (
        expected_task_ids
        - actual_task_ids
    )

    extra = (
        actual_task_ids
        - expected_task_ids
    )

    if missing:
        raise ValueError(
            "Résultats manquants pour "
            f"{group.occurrence_id} : "
            f"{sorted(missing)}"
        )

    if extra:
        raise ValueError(
            "Résultats inattendus pour "
            f"{group.occurrence_id} : "
            f"{sorted(extra)}"
        )

    output: List[
        Tuple[
            QuestionExtractionTask,
            ChunkExtractionResult,
        ]
    ] = []

    for task in group.tasks:

        result = indexed[
            task.task_id
        ]

        validate_extraction_payload(
            data_kind=(
                _effective_chunk_data_kind(
                    task,
                    result,
                )
            ),
            payload=result.payload,
        )

        output.append(
            (
                task,
                result,
            )
        )

    return output


# =====================================================
# Type réel d'une occurrence
# =====================================================

def _occurrence_effective_data_kind(
    pairs: Sequence[
        Tuple[
            QuestionExtractionTask,
            ChunkExtractionResult,
        ]
    ],
) -> DataKind:
    """
    Type à utiliser réellement pour valider
    et consolider les payloads.

    detected_data_kind est prioritaire lorsqu'il
    existe ; sinon le data_kind attendu par la tâche
    conserve le comportement historique.
    """

    if not pairs:
        raise ValueError(
            "Impossible de déterminer le type "
            "d'une occurrence vide."
        )

    kinds = [
        _effective_chunk_data_kind(
            task,
            result,
        )
        for task, result in pairs
    ]

    unique_kinds = set(
        kinds
    )

    if len(unique_kinds) != 1:
        raise ValueError(
            "Types effectifs incohérents entre "
            "les chunks d'une même occurrence : "
            f"{sorted(unique_kinds)}"
        )

    return kinds[0]


def _occurrence_detected_data_kind(
    pairs: Sequence[
        Tuple[
            QuestionExtractionTask,
            ChunkExtractionResult,
        ]
    ],
) -> Optional[
    DataKind
]:
    """
    Retourne uniquement le type explicitement
    détecté dans la source.

    Aucun type détecté :
        None

    Tous les chunks détectent le même type :
        ce DataKind

    Mélange de chunks détectés et non détectés :
        refus explicite pour ne pas inventer un
        type à l'échelle de toute l'occurrence.
    """

    detected = [
        result.detected_data_kind
        for _, result in pairs
    ]

    if all(
        value is None
        for value in detected
    ):
        return None

    if any(
        value is None
        for value in detected
    ):
        raise ValueError(
            "detected_data_kind partiellement "
            "renseigné dans une même occurrence."
        )

    unique_detected = set(
        detected
    )

    if len(unique_detected) != 1:
        raise ValueError(
            "Types réellement détectés incohérents "
            "entre les chunks d'une même occurrence : "
            f"{sorted(unique_detected)}"
        )

    return detected[0]


# =====================================================
# Localisation exacte des verbatims
# =====================================================

def _locate_verbatims_in_task(
    task: QuestionExtractionTask,
    payload: VerbatimsResult,
) -> List[_LocatedVerbatim]:
    """
    Retrouve chaque verbatim exactement dans
    le texte source du chunk.

    Les items doivent être :
    - exacts ;
    - dans l'ordre source ;
    - non reformulés.

    La recherche progresse dans le texte pour
    permettre de conserver plusieurs occurrences
    identiques lorsqu'elles existent réellement.
    """

    located: List[
        _LocatedVerbatim
    ] = []

    search_from = 0

    for index, item in enumerate(
        payload.items,
        start=1,
    ):

        local_start = task.text.find(
            item,
            search_from,
        )

        if local_start < 0:
            raise ValueError(
                "Verbatim introuvable exactement "
                "dans le chunk source : "
                f"{task.task_id} / item {index} / "
                f"{item!r}"
            )

        local_end = (
            local_start
            + len(item)
        )

        located.append(
            _LocatedVerbatim(
                text=item,
                absolute_start=(
                    task.start_char
                    + local_start
                ),
                absolute_end=(
                    task.start_char
                    + local_end
                ),
            )
        )

        search_from = local_end

    return located


# =====================================================
# Consolidation sûre des verbatims
# =====================================================

def _consolidate_verbatims(
    pairs: Sequence[
        Tuple[
            QuestionExtractionTask,
            ChunkExtractionResult,
        ]
    ],
) -> VerbatimsResult:
    """
    Consolide les verbatims de plusieurs chunks.

    Déduplication uniquement selon :
        texte exact
        + position source exacte.

    Donc :

        "RAS" position 500
        "RAS" position 900

    restent DEUX réponses.

    En revanche, si la réponse située position 500
    apparaît dans deux chunks qui se chevauchent,
    elle n'est conservée qu'une seule fois.
    """

    located_items: List[
        _LocatedVerbatim
    ] = []

    for task, result in pairs:

        if not isinstance(
            result.payload,
            VerbatimsResult,
        ):
            raise TypeError(
                "concat_verbatims attend "
                "uniquement VerbatimsResult."
            )

        located_items.extend(
            _locate_verbatims_in_task(
                task=task,
                payload=result.payload,
            )
        )

    # ---------------------------------------------
    # Déduplication par provenance exacte
    # ---------------------------------------------

    unique_by_source: Dict[
        Tuple[int, int, str],
        _LocatedVerbatim,
    ] = {}

    for item in located_items:

        source_key = (
            item.absolute_start,
            item.absolute_end,
            item.text,
        )

        if source_key not in unique_by_source:
            unique_by_source[
                source_key
            ] = item

    # ---------------------------------------------
    # Retour dans l'ordre réel du bloc parent
    # ---------------------------------------------

    ordered = sorted(
        unique_by_source.values(),
        key=lambda item: (
            item.absolute_start,
            item.absolute_end,
        ),
    )

    return VerbatimsResult(
        items=tuple(
            item.text
            for item in ordered
        )
    )


# =====================================================
# Consolidation d'une occurrence
# =====================================================

def consolidate_occurrence_results(
    group: QuestionOccurrenceTaskGroup,
    results: Sequence[
        ChunkExtractionResult
    ],
) -> OccurrenceExtractionResult:
    """
    Consolide les résultats des chunks appartenant
    à UNE occurrence métier.

    Ce niveau ne fusionne JAMAIS plusieurs
    occurrences d'une même business_key.

    Comportement actuel :

    - 1 seul chunk :
        validation + passage direct du payload ;

    - plusieurs chunks + concat_verbatims :
        consolidation par provenance source ;

    - plusieurs chunks pour distributions ou maîtrise :
        refus explicite plutôt qu'une addition ou
        moyenne potentiellement incorrecte.
    """

    pairs = _ordered_task_results(
        group=group,
        results=results,
    )

    if not pairs:
        raise ValueError(
            "Aucun résultat pour "
            f"{group.occurrence_id}"
        )

    effective_data_kind = (
        _occurrence_effective_data_kind(
            pairs
        )
    )

    detected_data_kind = (
        _occurrence_detected_data_kind(
            pairs
        )
    )

    # ---------------------------------------------
    # Verbatims
    # ---------------------------------------------

    if (
        group.merge_strategy
        == "concat_verbatims"
    ):

        if group.data_kind != "verbatims":
            raise ValueError(
                "concat_verbatims incohérent avec "
                f"data_kind={group.data_kind!r}"
            )

        if effective_data_kind != "verbatims":
            raise ValueError(
                "concat_verbatims incohérent avec "
                "effective_data_kind="
                f"{effective_data_kind!r}"
            )

        payload: QuestionExtractionPayload = (
            _consolidate_verbatims(
                pairs
            )
        )

    # ---------------------------------------------
    # Un seul chunk : passage direct sûr
    # ---------------------------------------------

    elif len(pairs) == 1:

        payload = pairs[0][1].payload

    # ---------------------------------------------
    # Plusieurs chunks structurés :
    # pas d'agrégation naïve
    # ---------------------------------------------

    else:

        raise NotImplementedError(
            "La consolidation multi-chunk n'est "
            "pas encore définie de façon sûre pour "
            f"data_kind={group.data_kind!r}, "
            f"merge_strategy="
            f"{group.merge_strategy!r}. "
            "Aucune addition ou moyenne automatique "
            "ne sera appliquée."
        )

    validate_extraction_payload(
        data_kind=effective_data_kind,
        payload=payload,
    )

    return OccurrenceExtractionResult(
        occurrence_id=group.occurrence_id,
        section_key=group.section_key,
        business_key=group.business_key,
        business_occurrence_index=(
            group.business_occurrence_index
        ),
        output_paths=group.output_paths,
        data_kind=group.data_kind,
        merge_strategy=group.merge_strategy,
        source_task_ids=tuple(
            task.task_id
            for task, _ in pairs
        ),
        payload=payload,
        detected_data_kind=(
            detected_data_kind
        ),
    )


# =====================================================
# Consolidation d'une liste de groupes
# =====================================================

def consolidate_question_results(
    groups: Sequence[
        QuestionOccurrenceTaskGroup
    ],
    results: Sequence[
        ChunkExtractionResult
    ],
) -> List[OccurrenceExtractionResult]:
    """
    Consolide tous les groupes d'occurrences.

    Chaque résultat de chunk doit appartenir
    exactement à une tâche connue.

    Les occurrences restent séparées dans la
    liste retournée.
    """

    if not groups:

        if results:
            raise ValueError(
                "Résultats fournis alors qu'aucun "
                "groupe d'occurrence n'existe."
            )

        return []

    task_to_occurrence: Dict[
        str,
        str,
    ] = {}

    for group in groups:

        for task in group.tasks:

            if task.task_id in task_to_occurrence:
                raise ValueError(
                    "task_id présent dans plusieurs "
                    "groupes : "
                    f"{task.task_id}"
                )

            task_to_occurrence[
                task.task_id
            ] = group.occurrence_id

    results_by_occurrence: Dict[
        str,
        List[ChunkExtractionResult],
    ] = {
        group.occurrence_id: []
        for group in groups
    }

    for result in results:

        occurrence_id = task_to_occurrence.get(
            result.task_id
        )

        if occurrence_id is None:
            raise ValueError(
                "Résultat pour une tâche inconnue : "
                f"{result.task_id}"
            )

        results_by_occurrence[
            occurrence_id
        ].append(result)

    output: List[
        OccurrenceExtractionResult
    ] = []

    for group in groups:

        output.append(
            consolidate_occurrence_results(
                group=group,
                results=(
                    results_by_occurrence[
                        group.occurrence_id
                    ]
                ),
            )
        )

    return output
