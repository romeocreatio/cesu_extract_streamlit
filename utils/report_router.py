# utils/report_router.py

from dataclasses import dataclass
from typing import List, Literal, Union

from utils.pdf_reader import PdfReadResult
from utils.section_splitter import ReportSection
from utils.question_splitter import (
    AnchoredQuestionBlock,
    QuestionBlock,
    split_a_froid_questions,
    split_anchored_questions,
    split_intervenants_questions,
    split_numbered_questions,
)


# =====================================================
# Types
# =====================================================

RoutingStrategy = Literal[
    "numbered",
    "anchored",
    "none",
]

RoutedBlock = Union[
    QuestionBlock,
    AnchoredQuestionBlock,
]


# =====================================================
# Résultat du routage
# =====================================================

@dataclass
class SectionRoutingResult:
    """
    Résultat du choix automatique de la stratégie
    de découpage d'une section.
    """

    strategy: RoutingStrategy
    blocks: List[RoutedBlock]

    numbered_count: int
    anchored_count: int

    @property
    def block_count(self) -> int:
        return len(self.blocks)

    @property
    def total_char_count(self) -> int:
        return sum(
            block.char_count
            for block in self.blocks
        )

    @property
    def largest_block_char_count(self) -> int:
        return max(
            (
                block.char_count
                for block in self.blocks
            ),
            default=0,
        )


# =====================================================
# Validation d'une structure numérotée
# =====================================================

def _is_reliable_numbered_structure(
    blocks: List[QuestionBlock],
) -> bool:
    """
    Vérifie que la détection numérotée ressemble
    réellement à un questionnaire structuré.

    On évite ainsi de sélectionner cette stratégie
    à cause de quelques lignes numérotées présentes
    accidentellement dans le contenu.
    """

    if len(blocks) < 5:
        return False

    numbers = [
        block.number
        for block in blocks
    ]

    # Les numéros doivent déjà être strictement croissants
    # grâce à split_numbered_questions(), mais on conserve
    # cette vérification ici pour rendre le routeur autonome.
    if any(
        current <= previous
        for previous, current in zip(
            numbers,
            numbers[1:],
        )
    ):
        return False

    # Un questionnaire numéroté doit commencer assez tôt.
    # Cela évite qu'un numéro isolé au milieu d'un rapport
    # soit interprété comme une structure de questionnaire.
    if numbers[0] > 3:
        return False

    return True


# =====================================================
# Routage — section À CHAUD
# =====================================================

def route_a_chaud_questions(
    result: PdfReadResult,
    section: ReportSection,
) -> SectionRoutingResult:
    """
    Choisit automatiquement la meilleure stratégie
    de découpage pour une section À CHAUD.

    Ordre de décision :

    1. tentative de détection d'un questionnaire numéroté ;
    2. si cette structure est fiable, elle est prioritaire ;
    3. sinon, utilisation des ancres métier Digiforma ;
    4. si aucune méthode ne produit de bloc exploitable,
       retourne la stratégie "none".
    """

    numbered_blocks = split_numbered_questions(
        result=result,
        section=section,
    )

    if _is_reliable_numbered_structure(
        numbered_blocks
    ):
        return SectionRoutingResult(
            strategy="numbered",
            blocks=list(numbered_blocks),
            numbered_count=len(numbered_blocks),
            anchored_count=0,
        )

    anchored_blocks = split_anchored_questions(
        result=result,
        section=section,
    )

    if anchored_blocks:
        return SectionRoutingResult(
            strategy="anchored",
            blocks=list(anchored_blocks),
            numbered_count=len(numbered_blocks),
            anchored_count=len(anchored_blocks),
        )

    return SectionRoutingResult(
        strategy="none",
        blocks=[],
        numbered_count=len(numbered_blocks),
        anchored_count=0,
    )


# =====================================================
# Routage — section À FROID
# =====================================================

def route_a_froid_questions(
    result: PdfReadResult,
    section: ReportSection,
) -> SectionRoutingResult:
    """
    Route une section À FROID vers son découpage
    spécialisé par ancres métier.
    """

    anchored_blocks = split_a_froid_questions(
        result=result,
        section=section,
    )

    if anchored_blocks:
        return SectionRoutingResult(
            strategy="anchored",
            blocks=list(anchored_blocks),
            numbered_count=0,
            anchored_count=len(anchored_blocks),
        )

    return SectionRoutingResult(
        strategy="none",
        blocks=[],
        numbered_count=0,
        anchored_count=0,
    )


# =====================================================
# Routage — section INTERVENANTS
# =====================================================

def route_intervenants_questions(
    result: PdfReadResult,
    section: ReportSection,
) -> SectionRoutingResult:
    """
    Route une section INTERVENANTS vers son découpage
    spécialisé par ancres métier.
    """

    anchored_blocks = split_intervenants_questions(
        result=result,
        section=section,
    )

    if anchored_blocks:
        return SectionRoutingResult(
            strategy="anchored",
            blocks=list(anchored_blocks),
            numbered_count=0,
            anchored_count=len(anchored_blocks),
        )

    return SectionRoutingResult(
        strategy="none",
        blocks=[],
        numbered_count=0,
        anchored_count=0,
    )


# =====================================================
# Point d'entrée unique
# =====================================================

def route_section_questions(
    result: PdfReadResult,
    section: ReportSection,
) -> SectionRoutingResult:
    """
    Point d'entrée unique pour choisir automatiquement
    la stratégie de découpage d'une section détectée.

    Sections actuellement prises en charge :
        - a_chaud
        - a_froid
        - intervenants

    La section pre_formation reste volontairement
    non routée tant que sa logique métier concernant
    les occurrences répétées n'est pas définie.
    """

    if section.key == "a_chaud":
        return route_a_chaud_questions(
            result=result,
            section=section,
        )

    if section.key == "a_froid":
        return route_a_froid_questions(
            result=result,
            section=section,
        )

    if section.key == "intervenants":
        return route_intervenants_questions(
            result=result,
            section=section,
        )

    return SectionRoutingResult(
        strategy="none",
        blocks=[],
        numbered_count=0,
        anchored_count=0,
    )