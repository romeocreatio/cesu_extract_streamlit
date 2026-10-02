# utils/extraction_pipeline.py

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional

from utils.pdf_reader import PdfReadResult
from utils.question_splitter import (
    AnchoredQuestionBlock,
    QuestionBlock,
)
from utils.report_router import (
    RoutingStrategy,
    route_section_questions,
)
from utils.section_splitter import (
    ReportSection,
    detect_sections,
)


# =====================================================
# Configuration
# =====================================================

DEFAULT_MAX_SEGMENT_CHARS = 12_000

SECTION_ORDER = (
    "pre_formation",
    "a_chaud",
    "a_froid",
    "intervenants",
)


# =====================================================
# Types
# =====================================================

SectionPlanStatus = Literal[
    "ready",
    "pending",
    "missing",
    "unroutable",
]


# =====================================================
# Segment préparé
# =====================================================

@dataclass(frozen=True)
class ExtractionSegment:
    """
    Segment déterministe préparé pour une future
    extraction structurée.

    À ce stade, un segment correspond à un bloc
    de question détecté par le moteur déterministe.

    Aucun appel LLM n'est effectué ici.
    """

    segment_id: str
    section_key: str
    block_identifier: str

    routing_strategy: RoutingStrategy

    title: str
    start_page: int
    end_page: int

    text: str

    max_segment_chars: int

    @property
    def char_count(self) -> int:
        return len(self.text)

    @property
    def page_count(self) -> int:
        return self.end_page - self.start_page + 1

    @property
    def requires_chunking(self) -> bool:
        """
        Indique si le segment devra être subdivisé
        avant son futur envoi au LLM.
        """

        return self.char_count > self.max_segment_chars


# =====================================================
# Plan d'une section
# =====================================================

@dataclass
class SectionExtractionPlan:
    """
    Plan déterministe d'une section du rapport.
    """

    section_key: str
    label: Optional[str]

    status: SectionPlanStatus
    routing_strategy: RoutingStrategy

    start_page: Optional[int]
    end_page: Optional[int]

    segments: List[ExtractionSegment]

    reason: Optional[str] = None

    @property
    def segment_count(self) -> int:
        return len(self.segments)

    @property
    def total_char_count(self) -> int:
        return sum(
            segment.char_count
            for segment in self.segments
        )

    @property
    def largest_segment_char_count(self) -> int:
        return max(
            (
                segment.char_count
                for segment in self.segments
            ),
            default=0,
        )

    @property
    def oversized_segment_count(self) -> int:
        return sum(
            1
            for segment in self.segments
            if segment.requires_chunking
        )


# =====================================================
# Plan global
# =====================================================

@dataclass
class ExtractionPlan:
    """
    Plan global de préparation du rapport.

    Ce plan décrit ce que le moteur déterministe
    a réussi à préparer avant toute intervention
    du LLM.
    """

    page_count: int
    char_count: int

    max_segment_chars: int

    sections: Dict[str, SectionExtractionPlan]
    missing_sections: List[str]

    @property
    def segments(self) -> List[ExtractionSegment]:
        """
        Retourne tous les segments préparés,
        dans l'ordre logique des sections.
        """

        output: List[ExtractionSegment] = []

        for section_key in SECTION_ORDER:

            section_plan = self.sections.get(
                section_key
            )

            if section_plan is None:
                continue

            output.extend(
                section_plan.segments
            )

        return output

    @property
    def segment_count(self) -> int:
        return len(self.segments)

    @property
    def total_segment_char_count(self) -> int:
        return sum(
            segment.char_count
            for segment in self.segments
        )

    @property
    def oversized_segments(
        self,
    ) -> List[ExtractionSegment]:
        return [
            segment
            for segment in self.segments
            if segment.requires_chunking
        ]

    @property
    def oversized_segment_count(self) -> int:
        return len(
            self.oversized_segments
        )


# =====================================================
# Identifiant d'un bloc
# =====================================================

def _block_identifier(
    block: QuestionBlock | AnchoredQuestionBlock,
) -> str:
    """
    Produit un identifiant stable pour un bloc.

    Exemples :
        question_01
        question_28
        maitrise_objectifs
        handicap_signale
    """

    if isinstance(
        block,
        QuestionBlock,
    ):
        return (
            f"question_{block.number:02d}"
        )

    return block.key


# =====================================================
# Conversion bloc -> segment
# =====================================================

def _build_segment(
    section: ReportSection,
    routing_strategy: RoutingStrategy,
    block: QuestionBlock | AnchoredQuestionBlock,
    max_segment_chars: int,
) -> ExtractionSegment:
    """
    Convertit un bloc routé en segment préparé.
    """

    block_identifier = _block_identifier(
        block
    )

    segment_id = (
        f"{section.key}:"
        f"{block_identifier}"
    )

    return ExtractionSegment(
        segment_id=segment_id,
        section_key=section.key,
        block_identifier=block_identifier,
        routing_strategy=routing_strategy,
        title=block.title,
        start_page=block.start_page,
        end_page=block.end_page,
        text=block.text,
        max_segment_chars=max_segment_chars,
    )


# =====================================================
# Section manquante
# =====================================================

def _build_missing_section_plan(
    section_key: str,
) -> SectionExtractionPlan:
    """
    Construit le plan d'une section absente du PDF.
    """

    return SectionExtractionPlan(
        section_key=section_key,
        label=None,
        status="missing",
        routing_strategy="none",
        start_page=None,
        end_page=None,
        segments=[],
        reason=(
            "Section non détectée dans le rapport."
        ),
    )


# =====================================================
# Préformation temporairement en attente
# =====================================================

def _build_pending_preformation_plan(
    section: ReportSection,
) -> SectionExtractionPlan:
    """
    La préformation est détectée mais volontairement
    laissée en attente.

    Certains rapports contiennent plusieurs occurrences
    de questions similaires ou identiques.

    La règle métier de consolidation doit être définie
    avant de construire les segments de cette section.
    """

    return SectionExtractionPlan(
        section_key=section.key,
        label=section.label,
        status="pending",
        routing_strategy="none",
        start_page=section.start_page,
        end_page=section.end_page,
        segments=[],
        reason=(
            "Règle métier en attente pour les "
            "occurrences répétées en préformation."
        ),
    )


# =====================================================
# Préparation d'une section routable
# =====================================================

def _build_routed_section_plan(
    result: PdfReadResult,
    section: ReportSection,
    max_segment_chars: int,
) -> SectionExtractionPlan:
    """
    Prépare une section prise en charge par
    le routeur déterministe.
    """

    routing = route_section_questions(
        result=result,
        section=section,
    )

    if (
        routing.strategy == "none"
        or not routing.blocks
    ):
        return SectionExtractionPlan(
            section_key=section.key,
            label=section.label,
            status="unroutable",
            routing_strategy="none",
            start_page=section.start_page,
            end_page=section.end_page,
            segments=[],
            reason=(
                "Section détectée mais aucun bloc "
                "exploitable n'a été reconnu."
            ),
        )

    segments = [
        _build_segment(
            section=section,
            routing_strategy=routing.strategy,
            block=block,
            max_segment_chars=max_segment_chars,
        )
        for block in routing.blocks
    ]

    return SectionExtractionPlan(
        section_key=section.key,
        label=section.label,
        status="ready",
        routing_strategy=routing.strategy,
        start_page=section.start_page,
        end_page=section.end_page,
        segments=segments,
        reason=None,
    )


# =====================================================
# Point d'entrée du pipeline déterministe
# =====================================================

def build_extraction_plan(
    result: PdfReadResult,
    max_segment_chars: int = DEFAULT_MAX_SEGMENT_CHARS,
) -> ExtractionPlan:
    """
    Construit le plan déterministe complet d'un rapport.

    Étapes :
        1. détection des grandes sections ;
        2. préformation mise en attente ;
        3. routage des sections exploitables ;
        4. création des segments initiaux ;
        5. détection des segments nécessitant
           un futur sous-découpage.

    Aucun appel OpenAI n'est effectué.
    Aucun texte source n'est modifié.
    """

    if max_segment_chars <= 0:
        raise ValueError(
            "max_segment_chars doit être "
            "strictement supérieur à 0."
        )

    detection = detect_sections(
        result
    )

    section_plans: Dict[
        str,
        SectionExtractionPlan,
    ] = {}

    for section_key in SECTION_ORDER:

        section = detection.get(
            section_key
        )

        if section is None:
            section_plans[
                section_key
            ] = _build_missing_section_plan(
                section_key
            )

            continue

        if section_key == "pre_formation":
            section_plans[
                section_key
            ] = (
                _build_pending_preformation_plan(
                    section
                )
            )

            continue

        section_plans[
            section_key
        ] = _build_routed_section_plan(
            result=result,
            section=section,
            max_segment_chars=max_segment_chars,
        )

    return ExtractionPlan(
        page_count=result.page_count,
        char_count=result.char_count,
        max_segment_chars=max_segment_chars,
        sections=section_plans,
        missing_sections=list(
            detection.missing_sections
        ),
    )