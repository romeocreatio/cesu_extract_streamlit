# utils/question_block_builder.py

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from utils.pdf_reader import PdfReadResult
from utils.question_mapper import (
    MappingStatus,
    QuestionMapping,
)
from utils.question_registry import (
    DataKind,
    MergeStrategy,
)
from utils.section_splitter import ReportSection


# =====================================================
# Structure publique
# =====================================================

@dataclass(frozen=True)
class QuestionOccurrenceBlock:
    """
    Bloc complet correspondant à une occurrence
    de question détectée dans une section.

    Le bloc commence exactement au début du candidat
    et se termine juste avant le candidat suivant.

    Tous les candidats participent au découpage,
    y compris ceux qui ne sont pas mappés vers
    une business_key.

    Cela évite qu'une question métier absorbe
    le contenu d'une question structurelle suivante.
    """

    block_id: str
    candidate_id: str

    section_key: str
    pattern_id: str
    source_order: int

    business_key: Optional[str]
    business_occurrence_index: Optional[int]

    mapping_status: MappingStatus

    output_paths: Tuple[str, ...]
    data_kind: Optional[DataKind]
    merge_strategy: Optional[MergeStrategy]

    matched_prompt: str
    original_question: str

    start_page: int
    start_line: int

    end_page: int
    end_line: int

    text: str

    @property
    def page_count(self) -> int:
        """
        Nombre de pages physiques couvertes
        par le bloc.
        """

        return (
            self.end_page
            - self.start_page
            + 1
        )

    @property
    def char_count(self) -> int:
        """
        Nombre de caractères du bloc.
        """

        return len(self.text)

    @property
    def is_mapped(self) -> bool:
        """
        Indique si ce bloc correspond à une
        donnée métier connue.
        """

        return (
            self.mapping_status == "mapped"
            and self.business_key is not None
        )


# =====================================================
# Structure interne
# =====================================================

@dataclass(frozen=True)
class _LineRecord:
    """
    Ligne source non vide d'une section.

    line_number correspond au numéro réel obtenu
    par splitlines() dans la page PDF.
    """

    record_index: int

    page_number: int
    line_number: int

    text: str


# =====================================================
# Construction des lignes de section
# =====================================================

def _section_line_records(
    result: PdfReadResult,
    section: ReportSection,
) -> List[_LineRecord]:
    """
    Reconstruit les lignes non vides de la section
    dans leur ordre source.

    Cette logique est cohérente avec celle utilisée
    par question_detector.py :
    - pages dans l'ordre ;
    - splitlines() ;
    - lignes vides ignorées ;
    - numéros de ligne d'origine conservés.
    """

    records: List[_LineRecord] = []

    record_index = 0

    for page in result.pages[
        section.start_page - 1:
        section.end_page
    ]:

        for line_number, line in enumerate(
            page.text.splitlines(),
            start=1,
        ):

            clean = line.strip()

            if not clean:
                continue

            records.append(
                _LineRecord(
                    record_index=record_index,
                    page_number=page.number,
                    line_number=line_number,
                    text=clean,
                )
            )

            record_index += 1

    return records


# =====================================================
# Validation
# =====================================================

def _validate_mappings(
    mappings: Sequence[QuestionMapping],
    section: ReportSection,
) -> None:
    """
    Vérifie que les mappings peuvent servir
    de frontières de blocs sans ambiguïté.
    """

    seen_candidate_ids: set[str] = set()

    seen_positions: set[
        tuple[int, int]
    ] = set()

    for mapping in mappings:

        if mapping.section_key != section.key:
            raise ValueError(
                "Mapping provenant d'une autre section : "
                f"{mapping.candidate_id} / "
                f"{mapping.section_key} "
                f"au lieu de {section.key}"
            )

        if mapping.candidate_id in seen_candidate_ids:
            raise ValueError(
                "candidate_id dupliqué : "
                f"{mapping.candidate_id}"
            )

        seen_candidate_ids.add(
            mapping.candidate_id
        )

        position = (
            mapping.start_page,
            mapping.start_line,
        )

        if position in seen_positions:
            raise ValueError(
                "Deux candidats commencent exactement "
                "au même emplacement : "
                f"page {mapping.start_page}, "
                f"ligne {mapping.start_line}"
            )

        seen_positions.add(
            position
        )

        if not (
            section.start_page
            <= mapping.start_page
            <= section.end_page
        ):
            raise ValueError(
                "Candidat hors de la section : "
                f"{mapping.candidate_id} "
                f"page {mapping.start_page}"
            )


# =====================================================
# Index des positions
# =====================================================

def _position_index(
    records: Sequence[_LineRecord],
) -> dict[tuple[int, int], int]:
    """
    Associe :

        (page, ligne)

    à la position correspondante dans
    la séquence de lignes de la section.
    """

    return {
        (
            record.page_number,
            record.line_number,
        ): index
        for index, record in enumerate(records)
    }


# =====================================================
# Construction d'un bloc
# =====================================================

def _build_one_block(
    mapping: QuestionMapping,
    records: Sequence[_LineRecord],
    start_index: int,
    stop_index: int,
) -> QuestionOccurrenceBlock:
    """
    Construit un bloc entre deux positions.

    stop_index est exclusif.
    """

    if stop_index <= start_index:
        raise ValueError(
            "Bloc vide ou inversé pour "
            f"{mapping.candidate_id}"
        )

    block_records = records[
        start_index:stop_index
    ]

    if not block_records:
        raise ValueError(
            "Aucune ligne dans le bloc "
            f"{mapping.candidate_id}"
        )

    first_record = block_records[0]
    last_record = block_records[-1]

    text = "\n".join(
        record.text
        for record in block_records
    )

    return QuestionOccurrenceBlock(
        block_id=(
            f"{mapping.section_key}:"
            f"block_{mapping.source_order:03d}"
        ),
        candidate_id=mapping.candidate_id,
        section_key=mapping.section_key,
        pattern_id=mapping.pattern_id,
        source_order=mapping.source_order,
        business_key=mapping.business_key,
        business_occurrence_index=(
            mapping.business_occurrence_index
        ),
        mapping_status=mapping.mapping_status,
        output_paths=mapping.output_paths,
        data_kind=mapping.data_kind,
        merge_strategy=mapping.merge_strategy,
        matched_prompt=mapping.matched_prompt,
        original_question=(
            mapping.original_question
        ),
        start_page=first_record.page_number,
        start_line=first_record.line_number,
        end_page=last_record.page_number,
        end_line=last_record.line_number,
        text=text,
    )


# =====================================================
# Point d'entrée public
# =====================================================

def build_question_occurrence_blocks(
    result: PdfReadResult,
    section: ReportSection,
    mappings: Sequence[QuestionMapping],
) -> List[QuestionOccurrenceBlock]:
    """
    Construit les blocs complets de toutes les
    questions détectées dans une section.

    Principes :
    - tous les mappings servent de frontières ;
    - mapped et unmapped sont conservés ;
    - aucune occurrence n'est fusionnée ;
    - aucun numéro de page n'est codé en dur ;
    - aucune extraction de valeur n'est faite ;
    - aucune IA n'est appelée.

    Le dernier bloc se termine à la fin réelle
    de la section.
    """

    if not mappings:
        return []

    _validate_mappings(
        mappings=mappings,
        section=section,
    )

    records = _section_line_records(
        result=result,
        section=section,
    )

    if not records:
        return []

    positions = _position_index(
        records
    )

    ordered_mappings = sorted(
        mappings,
        key=lambda mapping: (
            mapping.source_order,
            mapping.start_page,
            mapping.start_line,
        ),
    )

    start_indexes: List[int] = []

    for mapping in ordered_mappings:

        position = (
            mapping.start_page,
            mapping.start_line,
        )

        if position not in positions:
            raise ValueError(
                "Position du candidat introuvable "
                "dans le texte de la section : "
                f"{mapping.candidate_id} / "
                f"page {mapping.start_page}, "
                f"ligne {mapping.start_line}"
            )

        start_indexes.append(
            positions[position]
        )

    # Les candidats doivent progresser réellement
    # dans le texte source.
    for previous, current in zip(
        start_indexes,
        start_indexes[1:],
    ):

        if current <= previous:
            raise ValueError(
                "Ordre source incohérent dans "
                "les candidats de la section."
            )

    blocks: List[
        QuestionOccurrenceBlock
    ] = []

    for index, mapping in enumerate(
        ordered_mappings
    ):

        start_index = start_indexes[index]

        if index + 1 < len(start_indexes):
            stop_index = start_indexes[
                index + 1
            ]
        else:
            # Dernière question :
            # jusqu'à la dernière ligne de la section.
            stop_index = len(records)

        blocks.append(
            _build_one_block(
                mapping=mapping,
                records=records,
                start_index=start_index,
                stop_index=stop_index,
            )
        )

    return blocks


# =====================================================
# Helpers publics
# =====================================================

def mapped_question_blocks(
    blocks: Sequence[
        QuestionOccurrenceBlock
    ],
) -> List[QuestionOccurrenceBlock]:
    """
    Retourne uniquement les blocs associés
    à une business_key connue.

    Le découpage complet reste néanmoins basé
    sur TOUS les candidats.
    """

    return [
        block
        for block in blocks
        if block.is_mapped
    ]
