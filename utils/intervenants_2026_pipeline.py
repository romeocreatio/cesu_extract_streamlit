# utils/intervenants_2026_pipeline.py

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import (
    Optional,
    Tuple,
)

from utils.pdf_reader import (
    PdfReadResult,
    read_pdf,
)
from utils.section_splitter import (
    ReportSection,
    SectionDetectionResult,
    detect_sections,
)
from utils.question_splitter import (
    AnchoredQuestionBlock,
    split_intervenants_questions,
)
from utils.question_registry import (
    find_by_source_key,
    normalize_question_text,
)
from utils.question_block_chunker import (
    QuestionOccurrenceChunk,
)
from utils.question_extraction_tasks import (
    QuestionExtractionTask,
    QuestionOccurrenceTaskGroup,
    build_question_extraction_tasks,
    group_question_extraction_tasks,
)
from utils.question_deterministic_payload_adapter import (
    DeterministicTypedPayload,
)
from utils.question_extraction_contracts import (
    DistributionCategoryItem,
    DistributionYesNoResult,
    TextResult,
)
from utils.question_result_consolidator import (
    OccurrenceExtractionResult,
)
from utils.question_task_executor import (
    execute_and_consolidate_question_groups,
)


# =====================================================
# Sources intervenants utiles aux colonnes 18 / 19
# =====================================================

TARGET_SOURCE_KEYS = frozenset(
    {
        "commentaire_conditions",
        "commentaire_groupe",
        "commentaire_organisation",
        "adaptation_horaires",
        "explication_modification",
    }
)


# =====================================================
# Résultat public
# =====================================================

@dataclass(frozen=True)
class Intervenants2026PipelineResult:
    """
    Résultat complet du pipeline intervenants 2026.

    Tous les blocs ancrés sont conservés pour audit,
    mais seules les sources actuellement nécessaires
    aux colonnes 18 et 19 sont extraites métier.

    Aucun appel OpenAI n'est effectué ici.
    """

    pdf_result: PdfReadResult

    section_detection: SectionDetectionResult

    section: Optional[
        ReportSection
    ]

    blocks: Tuple[
        AnchoredQuestionBlock,
        ...,
    ]

    chunks: Tuple[
        QuestionOccurrenceChunk,
        ...,
    ]

    tasks: Tuple[
        QuestionExtractionTask,
        ...,
    ]

    groups: Tuple[
        QuestionOccurrenceTaskGroup,
        ...,
    ]

    occurrences: Tuple[
        OccurrenceExtractionResult,
        ...,
    ]

    @property
    def has_intervenants(
        self,
    ) -> bool:
        return self.section is not None

    @property
    def mapped_occurrence_count(
        self,
    ) -> int:
        return len(
            self.groups
        )

    @property
    def task_count(
        self,
    ) -> int:
        return len(
            self.tasks
        )

    @property
    def result_count(
        self,
    ) -> int:
        return len(
            self.occurrences
        )


# =====================================================
# Résultat vide
# =====================================================

def _empty_result(
    *,
    pdf_result: PdfReadResult,
    section_detection: SectionDetectionResult,
) -> Intervenants2026PipelineResult:

    return Intervenants2026PipelineResult(
        pdf_result=pdf_result,
        section_detection=section_detection,
        section=None,
        blocks=(),
        chunks=(),
        tasks=(),
        groups=(),
        occurrences=(),
    )


# =====================================================
# Nettoyage source déterministe
# =====================================================

def _clean_answer_lines(
    task: QuestionExtractionTask,
) -> Tuple[str, ...]:
    """
    Retire uniquement les éléments techniques connus :

    - le libellé de la question ;
    - les numéros de page isolés compris dans la
      plage réelle du bloc ;
    - les lignes constituées uniquement de ponctuation.

    Les réponses source ne sont ni corrigées,
    ni dédupliquées, ni reformulées.
    """

    lines = tuple(
        line.strip()
        for line in task.text.splitlines()
        if line.strip()
    )

    prompt_normalized = (
        normalize_question_text(
            task.matched_prompt
        )
    )

    consumed = 0
    accumulated = []

    for index, line in enumerate(
        lines
    ):
        accumulated.append(
            line
        )

        current_normalized = (
            normalize_question_text(
                " ".join(
                    accumulated
                )
            )
        )

        if (
            prompt_normalized
            and prompt_normalized
            in current_normalized
        ):
            consumed = index + 1
            break

    if (
        prompt_normalized
        and consumed == 0
    ):
        raise ValueError(
            "Impossible de retrouver le libellé "
            "de question dans la tâche "
            f"{task.task_id}."
        )

    output = []

    for line in lines[
        consumed:
    ]:

        # Numéro de page isolé injecté
        # dans le flux texte du PDF.
        if line.isdigit():

            page_number = int(
                line
            )

            if (
                task.block_start_page
                <= page_number
                <= task.block_end_page
            ):
                continue

        # Parasite typographique isolé.
        if re.fullmatch(
            r"[.\-–—]+",
            line,
        ):
            continue

        output.append(
            line
        )

    return tuple(
        output
    )


# =====================================================
# Parsing déterministe Oui / Non
# =====================================================

def _parse_distribution_region(
    region: str,
) -> Tuple[
    Optional[int],
    Optional[int],
]:
    """
    Retourne :

        (effectif explicite, pourcentage explicite)

    Aucune valeur absente n'est calculée.
    """

    pair = re.search(
        r"(?<!\d)(\d+)\s+(\d+)\s*%",
        region,
    )

    if pair:

        return (
            int(
                pair.group(1)
            ),
            int(
                pair.group(2)
            ),
        )

    percentage_match = re.search(
        r"(?<!\d)(\d+)\s*%",
        region,
    )

    percentage = (
        int(
            percentage_match.group(1)
        )
        if percentage_match
        else None
    )

    without_percentage = re.sub(
        r"(?<!\d)\d+\s*%",
        " ",
        region,
    )

    count_match = re.search(
        r"(?<!\d)(\d+)(?!\d)",
        without_percentage,
    )

    count = (
        int(
            count_match.group(1)
        )
        if count_match
        else None
    )

    return (
        count,
        percentage,
    )


def _adaptation_horaires_payload(
    task: QuestionExtractionTask,
) -> DistributionYesNoResult:
    """
    Extrait uniquement les valeurs Oui / Non
    explicitement présentes dans la source.

    Aucun total, effectif ou pourcentage manquant
    n'est reconstruit.
    """

    text = "\n".join(
        _clean_answer_lines(
            task
        )
    )

    upper = text.upper()

    oui_start = upper.find(
        "OUI"
    )

    non_start = upper.find(
        "NON"
    )

    if oui_start < 0:

        oui_region = ""

    elif non_start > oui_start:

        oui_region = text[
            oui_start:non_start
        ]

    else:

        oui_region = text[
            oui_start:
        ]

    if non_start < 0:

        non_region = ""

    else:

        non_region = text[
            non_start:
        ]

    (
        oui_count,
        oui_percentage,
    ) = _parse_distribution_region(
        oui_region
    )

    (
        non_count,
        non_percentage,
    ) = _parse_distribution_region(
        non_region
    )

    return DistributionYesNoResult(
        nb_votants=None,
        items=(
            DistributionCategoryItem(
                label="OUI",
                nb_votants=oui_count,
                pourcentage=(
                    oui_percentage
                ),
            ),
            DistributionCategoryItem(
                label="NON",
                nb_votants=non_count,
                pourcentage=(
                    non_percentage
                ),
            ),
        ),
    )


# =====================================================
# Extracteur local intervenants
# =====================================================

def _extract_intervenants_task(
    task: QuestionExtractionTask,
) -> DeterministicTypedPayload:
    """
    Extracteur 100 % local.

    - texte :
        texte source nettoyé des seuls artefacts
        techniques connus ;

    - adaptation_horaires :
        distribution Oui / Non explicite.

    Aucun fallback et aucun appel OpenAI.
    """

    if task.data_kind == "texte":

        payload = TextResult(
            text="\n".join(
                _clean_answer_lines(
                    task
                )
            )
        )

        return DeterministicTypedPayload(
            expected_data_kind=(
                task.data_kind
            ),
            detected_data_kind="texte",
            payload=payload,
            method=(
                "intervenants_2026_"
                "anchored_text"
            ),
        )

    if (
        task.business_key
        == "intervenants.adaptation_horaires"
    ):

        payload = (
            _adaptation_horaires_payload(
                task
            )
        )

        return DeterministicTypedPayload(
            expected_data_kind=(
                task.data_kind
            ),
            detected_data_kind=(
                "distribution_yes_no"
            ),
            payload=payload,
            method=(
                "intervenants_2026_"
                "anchored_yes_no"
            ),
        )

    raise NotImplementedError(
        "Aucun extracteur intervenants 2026 "
        "défini pour "
        f"business_key={task.business_key!r}, "
        f"data_kind={task.data_kind!r}."
    )


# =====================================================
# Blocs ancrés -> chunks métier mono-chunk
# =====================================================

def _build_target_chunks(
    blocks: Tuple[
        AnchoredQuestionBlock,
        ...,
    ],
) -> Tuple[
    QuestionOccurrenceChunk,
    ...,
]:

    output = []

    for source_order, block in enumerate(
        blocks,
        start=1,
    ):

        if (
            block.key
            not in TARGET_SOURCE_KEYS
        ):
            continue

        definition = (
            find_by_source_key(
                "intervenants",
                block.key,
            )
        )

        if definition is None:
            raise RuntimeError(
                "Aucune définition registre pour "
                f"la source intervenants "
                f"{block.key!r}."
            )

        block_id = (
            "intervenants:"
            f"{block.key}:"
            f"occ_{block.occurrence_index:02d}"
        )

        candidate_id = (
            "intervenants:"
            f"anchor_{source_order:03d}:"
            f"{block.key}"
        )

        chunk_id = (
            f"{block_id}:chunk_01"
        )

        line_count = max(
            1,
            len(
                block.text.splitlines()
            ),
        )

        output.append(
            QuestionOccurrenceChunk(
                chunk_id=chunk_id,
                parent_block_id=block_id,
                candidate_id=candidate_id,
                section_key="intervenants",
                pattern_id=(
                    f"anchor:{block.key}"
                ),
                source_order=source_order,
                business_key=(
                    definition.business_key
                ),
                business_occurrence_index=(
                    block.occurrence_index
                ),
                output_paths=(
                    definition.output_paths
                ),
                data_kind=(
                    definition.data_kind
                ),
                merge_strategy=(
                    definition.merge_strategy
                ),
                matched_prompt=(
                    block.title
                ),
                block_start_page=(
                    block.start_page
                ),
                block_end_page=(
                    block.end_page
                ),
                chunk_index=1,
                chunk_count=1,
                start_line=1,
                end_line=line_count,
                start_char=0,
                end_char=len(
                    block.text
                ),
                text=block.text,
            )
        )

    return tuple(
        output
    )


# =====================================================
# Pipeline public
# =====================================================

def extract_intervenants_2026(
    pdf_bytes: bytes,
    *,
    ocr_on_empty: bool = True,
    dpi: int = 300,
) -> Intervenants2026PipelineResult:
    """
    Exécute le pipeline intervenants 2026.

    Chaîne :

        PDF
        -> lecture
        -> section intervenants
        -> blocs ancrés
        -> sélection des 5 sources métier
        -> chunks mono-chunk
        -> tâches
        -> groupes
        -> extraction locale
        -> consolidation

    Aucun appel OpenAI n'est effectué.
    """

    if not isinstance(
        pdf_bytes,
        bytes,
    ):
        raise TypeError(
            "pdf_bytes doit être de type bytes."
        )

    if not pdf_bytes:
        raise ValueError(
            "pdf_bytes est vide."
        )

    pdf_result = read_pdf(
        pdf_bytes,
        ocr_on_empty=ocr_on_empty,
        dpi=dpi,
    )

    section_detection = (
        detect_sections(
            pdf_result
        )
    )

    section = (
        section_detection.get(
            "intervenants"
        )
    )

    if section is None:

        return _empty_result(
            pdf_result=pdf_result,
            section_detection=(
                section_detection
            ),
        )

    blocks = tuple(
        split_intervenants_questions(
            result=pdf_result,
            section=section,
        )
    )

    chunks = _build_target_chunks(
        blocks
    )

    tasks = tuple(
        build_question_extraction_tasks(
            chunks
        )
    )

    groups = tuple(
        group_question_extraction_tasks(
            tasks
        )
    )

    if not groups:

        return Intervenants2026PipelineResult(
            pdf_result=pdf_result,
            section_detection=(
                section_detection
            ),
            section=section,
            blocks=blocks,
            chunks=chunks,
            tasks=tasks,
            groups=(),
            occurrences=(),
        )

    occurrences = tuple(
        execute_and_consolidate_question_groups(
            groups=groups,
            extractor=(
                _extract_intervenants_task
            ),
        )
    )

    return Intervenants2026PipelineResult(
        pdf_result=pdf_result,
        section_detection=(
            section_detection
        ),
        section=section,
        blocks=blocks,
        chunks=chunks,
        tasks=tasks,
        groups=groups,
        occurrences=occurrences,
    )
