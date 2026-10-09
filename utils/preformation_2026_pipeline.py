# utils/preformation_2026_pipeline.py

from __future__ import annotations

from dataclasses import dataclass
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
from utils.question_detector import (
    QuestionCandidate,
    detect_question_candidates,
)
from utils.question_mapper import (
    QuestionMapping,
    map_question_candidates,
)
from utils.question_block_builder import (
    QuestionOccurrenceBlock,
    build_question_occurrence_blocks,
)
from utils.question_block_chunker import (
    QuestionOccurrenceChunk,
    chunk_mapped_question_blocks,
)
from utils.question_extraction_tasks import (
    QuestionExtractionTask,
    QuestionOccurrenceTaskGroup,
    build_question_extraction_tasks,
    group_question_extraction_tasks,
)
from utils.question_hybrid_extractor import (
    FallbackTaskExtractor,
    make_question_hybrid_extractor,
)
from utils.question_result_consolidator import (
    OccurrenceExtractionResult,
)
from utils.question_task_executor import (
    execute_and_consolidate_question_groups,
)


# =====================================================
# Résultat public
# =====================================================

@dataclass(frozen=True)
class Preformation2026PipelineResult:
    """
    Résultat complet du pipeline préformation 2026.

    Les différentes étapes sont volontairement
    conservées pour permettre :
    - l'audit ;
    - le diagnostic ;
    - les tests ;
    - l'évolution future du mapping métier.
    """

    pdf_result: PdfReadResult

    section_detection: SectionDetectionResult

    section: Optional[
        ReportSection
    ]

    candidates: Tuple[
        QuestionCandidate,
        ...,
    ]

    mappings: Tuple[
        QuestionMapping,
        ...,
    ]

    blocks: Tuple[
        QuestionOccurrenceBlock,
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
    def has_preformation(
        self,
    ) -> bool:
        return self.section is not None

    @property
    def candidate_count(
        self,
    ) -> int:
        return len(
            self.candidates
        )

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
# Résultat vide lorsqu'il n'y a pas de préformation
# =====================================================

def _empty_result(
    *,
    pdf_result: PdfReadResult,
    section_detection: SectionDetectionResult,
) -> Preformation2026PipelineResult:
    """
    Un rapport peut légitimement ne pas contenir
    de questionnaire préformation.

    Ce cas n'est donc pas considéré comme une erreur.
    """

    return Preformation2026PipelineResult(
        pdf_result=pdf_result,
        section_detection=section_detection,
        section=None,
        candidates=(),
        mappings=(),
        blocks=(),
        chunks=(),
        tasks=(),
        groups=(),
        occurrences=(),
    )


# =====================================================
# Pipeline public
# =====================================================

def extract_preformation_2026(
    pdf_bytes: bytes,
    *,
    fallback_extractor: Optional[
        FallbackTaskExtractor
    ] = None,
    ocr_on_empty: bool = True,
    dpi: int = 300,
) -> Preformation2026PipelineResult:
    """
    Exécute le pipeline complet de préformation 2026.

    Chaîne :

        PDF
        -> lecture
        -> détection des sections
        -> candidats questions
        -> mapping métier
        -> blocs
        -> chunks
        -> tâches
        -> groupes d'occurrences
        -> extraction hybride
        -> consolidation

    Le moteur déterministe reste prioritaire.

    fallback_extractor est optionnel :
    - il peut être factice dans les tests ;
    - il pourra devenir l'extracteur OpenAI ciblé
      en production.

    Aucun appel OpenAI n'est imposé par ce module.
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

    # -------------------------------------------------
    # 1. Lecture du PDF
    # -------------------------------------------------

    pdf_result = read_pdf(
        pdf_bytes,
        ocr_on_empty=ocr_on_empty,
        dpi=dpi,
    )

    # -------------------------------------------------
    # 2. Détection des grandes sections
    # -------------------------------------------------

    section_detection = (
        detect_sections(
            pdf_result
        )
    )

    section = (
        section_detection.get(
            "pre_formation"
        )
    )

    # -------------------------------------------------
    # Préformation absente :
    # résultat vide mais valide.
    # -------------------------------------------------

    if section is None:

        return _empty_result(
            pdf_result=pdf_result,
            section_detection=(
                section_detection
            ),
        )

    # -------------------------------------------------
    # 3. Détection des questions
    # -------------------------------------------------

    candidates = (
        detect_question_candidates(
            result=pdf_result,
            section=section,
        )
    )

    # -------------------------------------------------
    # 4. Mapping vers les business keys
    # -------------------------------------------------

    mappings = (
        map_question_candidates(
            candidates
        )
    )

    # -------------------------------------------------
    # 5. Construction de TOUS les blocs
    #
    # Les unmapped restent indispensables
    # comme frontières géométriques.
    # -------------------------------------------------

    blocks = (
        build_question_occurrence_blocks(
            result=pdf_result,
            section=section,
            mappings=mappings,
        )
    )

    # -------------------------------------------------
    # 6. Chunking des seuls blocs métier mappés
    # -------------------------------------------------

    chunks = (
        chunk_mapped_question_blocks(
            blocks
        )
    )

    # -------------------------------------------------
    # 7. Plan d'extraction
    # -------------------------------------------------

    tasks = (
        build_question_extraction_tasks(
            chunks
        )
    )

    groups = (
        group_question_extraction_tasks(
            tasks
        )
    )

    # -------------------------------------------------
    # Rien de mappé :
    # on conserve néanmoins le diagnostic complet.
    # -------------------------------------------------

    if not groups:

        return Preformation2026PipelineResult(
            pdf_result=pdf_result,
            section_detection=(
                section_detection
            ),
            section=section,
            candidates=tuple(
                candidates
            ),
            mappings=tuple(
                mappings
            ),
            blocks=tuple(
                blocks
            ),
            chunks=tuple(
                chunks
            ),
            tasks=tuple(
                tasks
            ),
            groups=(),
            occurrences=(),
        )

    # -------------------------------------------------
    # 8. Déterministe d'abord, fallback ensuite
    # -------------------------------------------------

    extractor = (
        make_question_hybrid_extractor(
            pdf_bytes=pdf_bytes,
            blocks=blocks,
            fallback_extractor=(
                fallback_extractor
            ),
        )
    )

    # -------------------------------------------------
    # 9. Exécution + consolidation par occurrence
    # -------------------------------------------------

    occurrences = (
        execute_and_consolidate_question_groups(
            groups=groups,
            extractor=extractor,
        )
    )

    # -------------------------------------------------
    # 10. Résultat complet
    # -------------------------------------------------

    return Preformation2026PipelineResult(
        pdf_result=pdf_result,
        section_detection=(
            section_detection
        ),
        section=section,
        candidates=tuple(
            candidates
        ),
        mappings=tuple(
            mappings
        ),
        blocks=tuple(
            blocks
        ),
        chunks=tuple(
            chunks
        ),
        tasks=tuple(
            tasks
        ),
        groups=tuple(
            groups
        ),
        occurrences=tuple(
            occurrences
        ),
    )
