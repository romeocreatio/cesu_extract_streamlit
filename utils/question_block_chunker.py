# utils/question_block_chunker.py

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from utils.extraction_pipeline import ExtractionSegment
from utils.question_block_builder import (
    QuestionOccurrenceBlock,
)
from utils.question_registry import (
    DataKind,
    MergeStrategy,
)
from utils.segment_chunker import (
    DEFAULT_OVERLAP_CHARS,
    DEFAULT_TARGET_CHUNK_CHARS,
    SegmentChunk,
    chunk_extraction_segment,
)


# =====================================================
# Chunk métier
# =====================================================

@dataclass(frozen=True)
class QuestionOccurrenceChunk:
    """
    Chunk d'une occurrence de question métier.

    Cette structure conserve explicitement :
    - l'identité du bloc source ;
    - la business_key ;
    - l'occurrence métier ;
    - la stratégie future de consolidation ;
    - les positions exactes du chunk dans le texte
      du bloc parent.

    Aucune extraction de valeur n'est réalisée ici.
    """

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
    def char_count(self) -> int:
        return len(self.text)

    @property
    def is_split(self) -> bool:
        return self.chunk_count > 1


# =====================================================
# Validation métier
# =====================================================

def _validate_mapped_block(
    block: QuestionOccurrenceBlock,
) -> None:
    """
    Vérifie qu'un bloc contient toutes les
    informations nécessaires avant chunking métier.
    """

    if not block.is_mapped:
        raise ValueError(
            "Le bloc n'est pas mappé vers "
            "une business_key : "
            f"{block.block_id}"
        )

    if block.business_key is None:
        raise ValueError(
            "business_key absente : "
            f"{block.block_id}"
        )

    if block.business_occurrence_index is None:
        raise ValueError(
            "business_occurrence_index absent : "
            f"{block.block_id}"
        )

    if block.data_kind is None:
        raise ValueError(
            "data_kind absent : "
            f"{block.block_id}"
        )

    if block.merge_strategy is None:
        raise ValueError(
            "merge_strategy absente : "
            f"{block.block_id}"
        )

    if not block.output_paths:
        raise ValueError(
            "output_paths vide : "
            f"{block.block_id}"
        )

    if not block.text:
        raise ValueError(
            "Bloc métier vide : "
            f"{block.block_id}"
        )


# =====================================================
# Adaptation vers le chunker existant
# =====================================================

def _as_extraction_segment(
    block: QuestionOccurrenceBlock,
    max_segment_chars: int,
) -> ExtractionSegment:
    """
    Adapte temporairement un QuestionOccurrenceBlock
    au contrat actuel de segment_chunker.py.

    routing_strategy="none" signifie uniquement ici
    que le bloc n'est PAS issu de l'ancien routeur
    numbered/anchored.

    Cette valeur technique n'est pas exposée dans
    QuestionOccurrenceChunk.

    max_segment_chars est volontairement égal à la
    taille cible du chunk : cela garantit que tout
    bloc dépassant cette limite sera effectivement
    découpé.
    """

    return ExtractionSegment(
        segment_id=block.block_id,
        section_key=block.section_key,
        block_identifier=block.block_id,
        routing_strategy="none",
        title=block.matched_prompt,
        start_page=block.start_page,
        end_page=block.end_page,
        text=block.text,
        max_segment_chars=max_segment_chars,
    )


# =====================================================
# Conversion d'un chunk technique
# =====================================================

def _as_question_chunk(
    block: QuestionOccurrenceBlock,
    chunk: SegmentChunk,
) -> QuestionOccurrenceChunk:
    """
    Réinjecte les métadonnées métier du bloc parent
    dans un chunk produit par segment_chunker.py.
    """

    if block.business_key is None:
        raise RuntimeError(
            "business_key absente après validation."
        )

    if block.business_occurrence_index is None:
        raise RuntimeError(
            "business_occurrence_index absent "
            "après validation."
        )

    if block.data_kind is None:
        raise RuntimeError(
            "data_kind absent après validation."
        )

    if block.merge_strategy is None:
        raise RuntimeError(
            "merge_strategy absente après validation."
        )

    return QuestionOccurrenceChunk(
        chunk_id=chunk.chunk_id,
        parent_block_id=block.block_id,
        candidate_id=block.candidate_id,
        section_key=block.section_key,
        pattern_id=block.pattern_id,
        source_order=block.source_order,
        business_key=block.business_key,
        business_occurrence_index=(
            block.business_occurrence_index
        ),
        output_paths=block.output_paths,
        data_kind=block.data_kind,
        merge_strategy=block.merge_strategy,
        matched_prompt=block.matched_prompt,
        block_start_page=block.start_page,
        block_end_page=block.end_page,
        chunk_index=chunk.chunk_index,
        chunk_count=chunk.chunk_count,
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        start_char=chunk.start_char,
        end_char=chunk.end_char,
        text=chunk.text,
    )


# =====================================================
# Un bloc métier -> chunks
# =====================================================

def chunk_question_occurrence_block(
    block: QuestionOccurrenceBlock,
    target_chunk_chars: int = (
        DEFAULT_TARGET_CHUNK_CHARS
    ),
    overlap_chars: int = (
        DEFAULT_OVERLAP_CHARS
    ),
) -> List[QuestionOccurrenceChunk]:
    """
    Découpe une occurrence de question métier.

    Principes :
    - aucune fusion entre occurrences ;
    - même business_key conservée ;
    - même business_occurrence_index conservé ;
    - texte source non réécrit par le chunker ;
    - chevauchement autorisé ;
    - aucune IA.
    """

    _validate_mapped_block(
        block
    )

    segment = _as_extraction_segment(
        block=block,
        max_segment_chars=target_chunk_chars,
    )

    technical_chunks = (
        chunk_extraction_segment(
            segment=segment,
            target_chunk_chars=(
                target_chunk_chars
            ),
            overlap_chars=overlap_chars,
        )
    )

    return [
        _as_question_chunk(
            block=block,
            chunk=chunk,
        )
        for chunk in technical_chunks
    ]


# =====================================================
# Liste de blocs -> chunks métier
# =====================================================

def chunk_mapped_question_blocks(
    blocks: Sequence[
        QuestionOccurrenceBlock
    ],
    target_chunk_chars: int = (
        DEFAULT_TARGET_CHUNK_CHARS
    ),
    overlap_chars: int = (
        DEFAULT_OVERLAP_CHARS
    ),
) -> List[QuestionOccurrenceChunk]:
    """
    Prépare les chunks de tous les blocs métier.

    Les blocs UNMAPPED restent utiles en amont pour
    construire les bonnes frontières, mais ils ne sont
    pas envoyés vers l'étape d'extraction métier.

    L'ordre source des blocs puis l'ordre des chunks
    sont conservés.
    """

    output: List[
        QuestionOccurrenceChunk
    ] = []

    for block in blocks:

        if not block.is_mapped:
            continue

        output.extend(
            chunk_question_occurrence_block(
                block=block,
                target_chunk_chars=(
                    target_chunk_chars
                ),
                overlap_chars=overlap_chars,
            )
        )

    return output
