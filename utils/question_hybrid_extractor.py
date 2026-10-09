# utils/question_hybrid_extractor.py

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Callable,
    Optional,
    Sequence,
    Tuple,
)

from utils.question_block_builder import (
    QuestionOccurrenceBlock,
)
from utils.question_deterministic_extractor import (
    DISTRIBUTION_DATA_KINDS,
    extract_question_deterministically,
)
from utils.question_deterministic_payload_adapter import (
    DeterministicTypedPayload,
    deterministic_extraction_to_typed_payload,
)
from utils.question_extraction_tasks import (
    QuestionExtractionTask,
)
from utils.question_layout_context import (
    build_question_layout_context,
)


# =====================================================
# Contrat du fallback
# =====================================================

FallbackTaskExtractor = Callable[
    [QuestionExtractionTask],
    object,
]


# =====================================================
# Extracteur déterministe -> fallback
# =====================================================

@dataclass(frozen=True)
class QuestionHybridExtractor:
    """
    Extracteur de tâche privilégiant l'extraction
    déterministe locale.

    Ordre :

        tâche
        -> bloc source
        -> contexte PyMuPDF
        -> extraction déterministe
        -> payload typé

    Si le déterministe n'est pas applicable ou ne
    produit pas un résultat suffisamment fiable,
    le fallback est utilisé lorsqu'il existe.

    Le fallback peut notamment être un
    QuestionOpenAIExtractor, mais cette classe
    n'a aucune dépendance directe envers OpenAI.
    """

    pdf_bytes: bytes

    # IMPORTANT :
    # fournir la liste COMPLETE des blocs détectés,
    # y compris les blocs non mappés, car ils servent
    # de frontières géométriques.
    blocks: Tuple[
        QuestionOccurrenceBlock,
        ...,
    ]

    fallback_extractor: Optional[
        FallbackTaskExtractor
    ] = None

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.pdf_bytes,
            bytes,
        ):
            raise TypeError(
                "pdf_bytes doit être de type bytes."
            )

        if not self.pdf_bytes:
            raise ValueError(
                "pdf_bytes est vide."
            )

        seen_block_ids: set[str] = set()

        for block in self.blocks:

            if not isinstance(
                block,
                QuestionOccurrenceBlock,
            ):
                raise TypeError(
                    "blocks doit contenir uniquement "
                    "des QuestionOccurrenceBlock."
                )

            if block.block_id in seen_block_ids:
                raise ValueError(
                    "block_id dupliqué : "
                    f"{block.block_id}"
                )

            seen_block_ids.add(
                block.block_id
            )

    # =================================================
    # Bloc courant + vraie frontière suivante
    # =================================================

    def _block_and_next(
        self,
        task: QuestionExtractionTask,
    ) -> Tuple[
        QuestionOccurrenceBlock,
        Optional[
            QuestionOccurrenceBlock
        ],
    ]:

        matches = [
            block
            for block in self.blocks
            if (
                block.block_id
                == task.parent_block_id
            )
        ]

        if len(matches) != 1:
            raise ValueError(
                "Impossible de retrouver exactement "
                "un bloc parent pour "
                f"{task.task_id} : "
                f"{task.parent_block_id!r}."
            )

        block = matches[0]

        self._validate_task_against_block(
            task=task,
            block=block,
        )

        section_blocks = sorted(
            (
                candidate
                for candidate in self.blocks
                if (
                    candidate.section_key
                    == block.section_key
                )
            ),
            key=lambda candidate: (
                candidate.source_order,
                candidate.start_page,
                candidate.start_line,
            ),
        )

        block_index = next(
            index
            for index, candidate
            in enumerate(section_blocks)
            if (
                candidate.block_id
                == block.block_id
            )
        )

        next_block = (
            section_blocks[
                block_index + 1
            ]
            if (
                block_index + 1
                < len(section_blocks)
            )
            else None
        )

        return (
            block,
            next_block,
        )

    # =================================================
    # Cohérence tâche <-> bloc
    # =================================================

    @staticmethod
    def _validate_task_against_block(
        *,
        task: QuestionExtractionTask,
        block: QuestionOccurrenceBlock,
    ) -> None:

        checks = (
            (
                "candidate_id",
                task.candidate_id,
                block.candidate_id,
            ),
            (
                "section_key",
                task.section_key,
                block.section_key,
            ),
            (
                "business_key",
                task.business_key,
                block.business_key,
            ),
            (
                "business_occurrence_index",
                task.business_occurrence_index,
                block.business_occurrence_index,
            ),
            (
                "data_kind",
                task.data_kind,
                block.data_kind,
            ),
            (
                "merge_strategy",
                task.merge_strategy,
                block.merge_strategy,
            ),
            (
                "output_paths",
                task.output_paths,
                block.output_paths,
            ),
            (
                "matched_prompt",
                task.matched_prompt,
                block.matched_prompt,
            ),
            (
                "block_start_page",
                task.block_start_page,
                block.start_page,
            ),
            (
                "block_end_page",
                task.block_end_page,
                block.end_page,
            ),
        )

        for (
            field_name,
            task_value,
            block_value,
        ) in checks:

            if task_value != block_value:
                raise ValueError(
                    "Incohérence tâche/bloc pour "
                    f"{task.task_id} / "
                    f"{field_name} : "
                    f"task={task_value!r}, "
                    f"block={block_value!r}"
                )

    # =================================================
    # Fallback
    # =================================================

    def _fallback(
        self,
        task: QuestionExtractionTask,
        *,
        reason: str,
    ) -> object:

        if self.fallback_extractor is None:
            raise RuntimeError(
                "Extraction déterministe "
                "indisponible et aucun fallback "
                "n'est configuré pour "
                f"{task.task_id}. "
                f"Raison : {reason}"
            )

        return self.fallback_extractor(
            task
        )

    # =================================================
    # Exécution publique
    # =================================================

    def __call__(
        self,
        task: QuestionExtractionTask,
    ) -> object:
        """
        Retourne :

        - DeterministicTypedPayload en cas de
          réussite déterministe ;

        - la sortie du fallback sinon.

        Aucun appel OpenAI n'est imposé ici.
        """

        if not isinstance(
            task,
            QuestionExtractionTask,
        ):
            raise TypeError(
                "task doit être un "
                "QuestionExtractionTask."
            )

        block, next_block = (
            self._block_and_next(
                task
            )
        )

        # -----------------------------------------
        # Sécurité multi-chunk
        #
        # Le moteur géométrique travaille sur le
        # bloc entier. L'utiliser pour chaque chunk
        # du même bloc reproduirait plusieurs fois
        # la même distribution.
        # -----------------------------------------

        if task.is_multi_chunk_occurrence:

            return self._fallback(
                task,
                reason=(
                    "multi_chunk_occurrence"
                ),
            )

        # -----------------------------------------
        # Le déterministe actuel ne traite encore
        # que les distributions.
        # -----------------------------------------

        if (
            task.data_kind
            not in DISTRIBUTION_DATA_KINDS
        ):

            return self._fallback(
                task,
                reason=(
                    "data_kind_not_supported_"
                    "deterministically"
                ),
            )

        # -----------------------------------------
        # Construction du contexte géométrique
        # -----------------------------------------

        try:
            context = (
                build_question_layout_context(
                    self.pdf_bytes,
                    block=block,
                    next_block=next_block,
                )
            )

        except ValueError as exc:

            return self._fallback(
                task,
                reason=(
                    "layout_context_error: "
                    f"{exc}"
                ),
            )

        # -----------------------------------------
        # Extraction locale
        # -----------------------------------------

        extraction = (
            extract_question_deterministically(
                context,
                expected_data_kind=(
                    task.data_kind
                ),
            )
        )

        # -----------------------------------------
        # Succès : aucun fallback
        # -----------------------------------------

        if extraction.succeeded:

            typed = (
                deterministic_extraction_to_typed_payload(
                    extraction
                )
            )

            if not isinstance(
                typed,
                DeterministicTypedPayload,
            ):
                raise TypeError(
                    "L'adaptateur déterministe "
                    "doit retourner un "
                    "DeterministicTypedPayload."
                )

            return typed

        # -----------------------------------------
        # Déterministe insuffisant :
        # fallback ciblé
        # -----------------------------------------

        reason = (
            extraction.status
        )

        if extraction.issues:

            reason += (
                ": "
                + ", ".join(
                    extraction.issues
                )
            )

        return self._fallback(
            task,
            reason=reason,
        )


# =====================================================
# Factory publique
# =====================================================

def make_question_hybrid_extractor(
    *,
    pdf_bytes: bytes,
    blocks: Sequence[
        QuestionOccurrenceBlock
    ],
    fallback_extractor: Optional[
        FallbackTaskExtractor
    ] = None,
) -> QuestionHybridExtractor:
    """
    Construit l'extracteur déterministe-first.

    Aucun appel réseau n'est effectué ici.
    """

    return QuestionHybridExtractor(
        pdf_bytes=pdf_bytes,
        blocks=tuple(
            blocks
        ),
        fallback_extractor=(
            fallback_extractor
        ),
    )
