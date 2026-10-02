# utils/segment_chunker.py

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from utils.extraction_pipeline import ExtractionSegment
from utils.report_router import RoutingStrategy


# =====================================================
# Configuration
# =====================================================

DEFAULT_TARGET_CHUNK_CHARS = 8_000
DEFAULT_OVERLAP_CHARS = 1_500


# =====================================================
# Structures internes
# =====================================================

@dataclass(frozen=True)
class _LineSpan:
    """
    Position exacte d'une ligne dans le texte source.

    start est inclusif.
    end est exclusif.
    """

    start: int
    end: int

    @property
    def char_count(self) -> int:
        return self.end - self.start


# =====================================================
# Chunk préparé
# =====================================================

@dataclass(frozen=True)
class SegmentChunk:
    """
    Sous-segment prêt pour une future extraction LLM.

    Pour un segment qui n'a pas besoin d'être découpé :
        chunk_id == parent_segment_id
        chunk_count == 1

    Pour un segment découpé :
        parent:chunk_01
        parent:chunk_02
        etc.

    Les positions start_char/end_char permettent de
    retrouver exactement le texte dans le segment parent.
    """

    chunk_id: str
    parent_segment_id: str

    section_key: str
    block_identifier: str
    routing_strategy: RoutingStrategy

    title: str

    chunk_index: int
    chunk_count: int

    start_line: int
    end_line: int

    start_char: int
    end_char: int

    source_start_page: int
    source_end_page: int

    text: str

    max_segment_chars: int

    @property
    def char_count(self) -> int:
        return len(self.text)

    @property
    def is_split(self) -> bool:
        return self.chunk_count > 1


# =====================================================
# Analyse exacte des lignes
# =====================================================

def _build_line_spans(
    text: str,
) -> List[_LineSpan]:
    """
    Construit les positions exactes des lignes dans
    le texte sans modifier son contenu.

    splitlines(keepends=True) permet de conserver
    les retours à la ligne dans les positions.
    """

    if not text:
        return []

    spans: List[_LineSpan] = []

    offset = 0

    for line in text.splitlines(
        keepends=True
    ):
        end = offset + len(line)

        spans.append(
            _LineSpan(
                start=offset,
                end=end,
            )
        )

        offset = end

    # Sécurité : tout le texte doit avoir été couvert.
    if offset != len(text):
        raise RuntimeError(
            "Le calcul des lignes ne couvre pas "
            "l'intégralité du texte source."
        )

    return spans


# =====================================================
# Validation configuration
# =====================================================

def _validate_chunking_parameters(
    segment: ExtractionSegment,
    target_chunk_chars: int,
    overlap_chars: int,
) -> None:
    """
    Vérifie que les paramètres permettent un découpage
    cohérent et borné.
    """

    if target_chunk_chars <= 0:
        raise ValueError(
            "target_chunk_chars doit être "
            "strictement supérieur à 0."
        )

    if overlap_chars < 0:
        raise ValueError(
            "overlap_chars ne peut pas être négatif."
        )

    if overlap_chars >= target_chunk_chars:
        raise ValueError(
            "overlap_chars doit être strictement "
            "inférieur à target_chunk_chars."
        )

    if (
        target_chunk_chars
        > segment.max_segment_chars
    ):
        raise ValueError(
            "target_chunk_chars ne peut pas dépasser "
            "la limite max_segment_chars du segment."
        )


# =====================================================
# Calcul des plages de lignes
# =====================================================

def _build_chunk_ranges(
    text: str,
    target_chunk_chars: int,
    overlap_chars: int,
) -> Tuple[
    List[_LineSpan],
    List[Tuple[int, int]],
]:
    """
    Calcule les plages de lignes des chunks.

    Une plage est représentée par :
        (start_line_index, end_line_index)

    avec end_line_index exclusif.

    Principes :
        - aucune ligne n'est coupée ;
        - chaque chunk reste <= target_chunk_chars ;
        - les chunks consécutifs peuvent se chevaucher ;
        - le chevauchement utilise uniquement des lignes
          complètes ;
        - aucune partie du texte n'est perdue.
    """

    line_spans = _build_line_spans(
        text
    )

    if not line_spans:
        return line_spans, []

    for index, span in enumerate(
        line_spans,
        start=1,
    ):
        if span.char_count > target_chunk_chars:
            raise ValueError(
                "Impossible de découper sans couper "
                "une ligne : "
                f"ligne {index} = "
                f"{span.char_count} caractères, "
                f"limite = {target_chunk_chars}."
            )

    ranges: List[
        Tuple[int, int]
    ] = []

    line_count = len(line_spans)

    start_index = 0

    while start_index < line_count:

        end_index = start_index

        # -----------------------------------------
        # Remplissage du chunk jusqu'à la limite
        # -----------------------------------------

        while end_index < line_count:

            candidate_size = (
                line_spans[end_index].end
                - line_spans[start_index].start
            )

            if (
                candidate_size
                > target_chunk_chars
            ):
                break

            end_index += 1

        if end_index == start_index:
            raise RuntimeError(
                "Le découpeur n'a pas réussi à "
                "faire progresser le segment."
            )

        ranges.append(
            (
                start_index,
                end_index,
            )
        )

        # Tout le texte est couvert.
        if end_index >= line_count:
            break

        # -----------------------------------------
        # Calcul du chevauchement
        # -----------------------------------------
        #
        # On réserve obligatoirement assez de place
        # pour inclure au moins la prochaine ligne
        # encore jamais traitée.
        # -----------------------------------------

        next_new_line = line_spans[
            end_index
        ]

        available_overlap = (
            target_chunk_chars
            - next_new_line.char_count
        )

        allowed_overlap = min(
            overlap_chars,
            available_overlap,
        )

        next_start_index = end_index

        accumulated_overlap = 0

        candidate_index = (
            end_index - 1
        )

        while (
            candidate_index
            >= start_index
        ):

            candidate_line = line_spans[
                candidate_index
            ]

            candidate_overlap = (
                accumulated_overlap
                + candidate_line.char_count
            )

            if (
                candidate_overlap
                > allowed_overlap
            ):
                break

            accumulated_overlap = (
                candidate_overlap
            )

            next_start_index = (
                candidate_index
            )

            candidate_index -= 1

        # Sécurité contre une boucle infinie.
        if (
            next_start_index
            <= start_index
        ):
            next_start_index = (
                end_index
            )

        start_index = next_start_index

    return line_spans, ranges


# =====================================================
# Validation de la couverture
# =====================================================

def _validate_ranges(
    text: str,
    line_spans: Sequence[_LineSpan],
    ranges: Sequence[
        Tuple[int, int]
    ],
    target_chunk_chars: int,
) -> None:
    """
    Vérifie les propriétés essentielles du découpage.

    On contrôle notamment :
        - première ligne couverte ;
        - dernière ligne couverte ;
        - absence de trou entre deux chunks ;
        - progression des chunks ;
        - taille maximale respectée.
    """

    if not text:
        return

    if not line_spans:
        raise RuntimeError(
            "Texte non vide mais aucune ligne détectée."
        )

    if not ranges:
        raise RuntimeError(
            "Texte non vide mais aucun chunk calculé."
        )

    first_start, _ = ranges[0]

    if first_start != 0:
        raise RuntimeError(
            "Le découpage ne commence pas "
            "à la première ligne."
        )

    _, last_end = ranges[-1]

    if last_end != len(line_spans):
        raise RuntimeError(
            "Le découpage ne couvre pas "
            "la dernière ligne."
        )

    previous_start = -1
    previous_end = 0

    for index, (
        start_index,
        end_index,
    ) in enumerate(
        ranges,
        start=1,
    ):

        if start_index < 0:
            raise RuntimeError(
                f"Chunk {index}: début invalide."
            )

        if end_index <= start_index:
            raise RuntimeError(
                f"Chunk {index}: plage vide."
            )

        if end_index > len(line_spans):
            raise RuntimeError(
                f"Chunk {index}: fin invalide."
            )

        if start_index <= previous_start:
            raise RuntimeError(
                f"Chunk {index}: absence de "
                "progression."
            )

        # Un chevauchement est autorisé,
        # un trou ne l'est jamais.
        if (
            index > 1
            and start_index > previous_end
        ):
            raise RuntimeError(
                f"Chunk {index}: trou détecté "
                "dans le texte source."
            )

        start_char = line_spans[
            start_index
        ].start

        end_char = line_spans[
            end_index - 1
        ].end

        chunk_size = (
            end_char - start_char
        )

        if (
            chunk_size
            > target_chunk_chars
        ):
            raise RuntimeError(
                f"Chunk {index}: "
                f"{chunk_size} caractères, "
                f"limite {target_chunk_chars}."
            )

        previous_start = (
            start_index
        )

        previous_end = (
            end_index
        )


# =====================================================
# Segment -> chunks
# =====================================================

def chunk_extraction_segment(
    segment: ExtractionSegment,
    target_chunk_chars: int = (
        DEFAULT_TARGET_CHUNK_CHARS
    ),
    overlap_chars: int = (
        DEFAULT_OVERLAP_CHARS
    ),
) -> List[SegmentChunk]:
    """
    Découpe un segment uniquement si son indicateur
    requires_chunking est True.

    Les segments normaux sont conservés intégralement.

    Pour les gros segments :
        - découpage par lignes complètes ;
        - taille cible <= target_chunk_chars ;
        - chevauchement constitué de lignes complètes ;
        - aucun caractère source n'est réécrit.
    """

    _validate_chunking_parameters(
        segment=segment,
        target_chunk_chars=target_chunk_chars,
        overlap_chars=overlap_chars,
    )

    # ---------------------------------------------
    # Segment déjà suffisamment petit
    # ---------------------------------------------

    if not segment.requires_chunking:

        line_count = len(
            segment.text.splitlines()
        )

        return [
            SegmentChunk(
                chunk_id=segment.segment_id,
                parent_segment_id=(
                    segment.segment_id
                ),
                section_key=(
                    segment.section_key
                ),
                block_identifier=(
                    segment.block_identifier
                ),
                routing_strategy=(
                    segment.routing_strategy
                ),
                title=segment.title,
                chunk_index=1,
                chunk_count=1,
                start_line=(
                    1
                    if line_count > 0
                    else 0
                ),
                end_line=line_count,
                start_char=0,
                end_char=len(
                    segment.text
                ),
                source_start_page=(
                    segment.start_page
                ),
                source_end_page=(
                    segment.end_page
                ),
                text=segment.text,
                max_segment_chars=(
                    segment.max_segment_chars
                ),
            )
        ]

    # ---------------------------------------------
    # Segment nécessitant un découpage
    # ---------------------------------------------

    line_spans, ranges = (
        _build_chunk_ranges(
            text=segment.text,
            target_chunk_chars=(
                target_chunk_chars
            ),
            overlap_chars=overlap_chars,
        )
    )

    _validate_ranges(
        text=segment.text,
        line_spans=line_spans,
        ranges=ranges,
        target_chunk_chars=(
            target_chunk_chars
        ),
    )

    chunk_count = len(
        ranges
    )

    chunks: List[
        SegmentChunk
    ] = []

    for chunk_index, (
        start_index,
        end_index,
    ) in enumerate(
        ranges,
        start=1,
    ):

        start_char = line_spans[
            start_index
        ].start

        end_char = line_spans[
            end_index - 1
        ].end

        chunk_text = segment.text[
            start_char:end_char
        ]

        chunk_id = (
            f"{segment.segment_id}:"
            f"chunk_{chunk_index:02d}"
        )

        chunks.append(
            SegmentChunk(
                chunk_id=chunk_id,
                parent_segment_id=(
                    segment.segment_id
                ),
                section_key=(
                    segment.section_key
                ),
                block_identifier=(
                    segment.block_identifier
                ),
                routing_strategy=(
                    segment.routing_strategy
                ),
                title=segment.title,
                chunk_index=chunk_index,
                chunk_count=chunk_count,
                start_line=(
                    start_index + 1
                ),
                end_line=end_index,
                start_char=start_char,
                end_char=end_char,
                source_start_page=(
                    segment.start_page
                ),
                source_end_page=(
                    segment.end_page
                ),
                text=chunk_text,
                max_segment_chars=(
                    segment.max_segment_chars
                ),
            )
        )

    return chunks


# =====================================================
# Liste de segments -> liste de chunks
# =====================================================

def chunk_extraction_segments(
    segments: Sequence[
        ExtractionSegment
    ],
    target_chunk_chars: int = (
        DEFAULT_TARGET_CHUNK_CHARS
    ),
    overlap_chars: int = (
        DEFAULT_OVERLAP_CHARS
    ),
) -> List[SegmentChunk]:
    """
    Applique le découpage à une liste complète
    de segments tout en conservant leur ordre.
    """

    chunks: List[
        SegmentChunk
    ] = []

    for segment in segments:

        chunks.extend(
            chunk_extraction_segment(
                segment=segment,
                target_chunk_chars=(
                    target_chunk_chars
                ),
                overlap_chars=(
                    overlap_chars
                ),
            )
        )

    return chunks