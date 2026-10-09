# utils/question_layout_context.py

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Optional,
    Sequence,
    Tuple,
)

import fitz

from utils.distribution_layout_extractor import (
    LayoutLine,
    group_words_into_lines,
    normalize_layout_text,
    words_from_pymupdf,
)
from utils.question_block_builder import (
    QuestionOccurrenceBlock,
)


# =====================================================
# Configuration
# =====================================================

DEFAULT_PROMPT_SIGNATURE_TOKENS = 7
DEFAULT_MAX_PROMPT_LINES = 4


# =====================================================
# Résultat public
# =====================================================

@dataclass(frozen=True)
class QuestionLayoutContext:
    """
    Contexte géométrique exact d'un bloc de question.

    Il contient uniquement les lignes comprises entre :
    - le début visuel de la question courante ;
    - le début visuel de la question suivante,
      lorsqu'elle commence sur la même page.

    Aucun appel LLM.
    Aucune extraction métier.
    """

    block_id: str
    candidate_id: str

    section_key: str

    start_page: int
    end_page: int

    matched_prompt: str

    lines: Tuple[
        LayoutLine,
        ...
    ]

    @property
    def line_count(self) -> int:
        return len(
            self.lines
        )

    @property
    def text(self) -> str:
        return "\n".join(
            line.text
            for line in self.lines
        )


# =====================================================
# Signature du prompt
# =====================================================

def prompt_signature(
    value: str,
    *,
    max_tokens: int = (
        DEFAULT_PROMPT_SIGNATURE_TOKENS
    ),
) -> str:
    """
    Produit une signature normalisée utilisée
    uniquement pour localiser visuellement une question.

    Le texte source n'est jamais modifié.
    """

    if max_tokens < 1:
        raise ValueError(
            "max_tokens doit être >= 1."
        )

    normalized = normalize_layout_text(
        value
    )

    tokens = normalized.split()

    return " ".join(
        tokens[:max_tokens]
    )


# =====================================================
# Localisation verticale d'un prompt
# =====================================================

def find_prompt_y(
    lines: Sequence[
        LayoutLine
    ],
    prompt: str,
    *,
    max_prompt_lines: int = (
        DEFAULT_MAX_PROMPT_LINES
    ),
) -> Optional[float]:
    """
    Recherche le début réel d'une question.

    Les fenêtres sont testées de la plus courte
    à la plus longue :

        1 ligne
        2 lignes
        3 lignes
        4 lignes

    Cette priorité empêche une fenêtre contenant
    encore la fin de la question précédente
    d'être retenue lorsque la question recherchée
    existe déjà sur une ligne plus précise.
    """

    if max_prompt_lines < 1:
        raise ValueError(
            "max_prompt_lines doit être >= 1."
        )

    signature = prompt_signature(
        prompt
    )

    if not signature:
        return None

    for width in range(
        1,
        max_prompt_lines + 1,
    ):
        for index in range(
            len(lines)
        ):
            selected = lines[
                index:index + width
            ]

            if len(selected) < width:
                continue

            combined = " ".join(
                line.text
                for line in selected
            )

            normalized = (
                normalize_layout_text(
                    combined
                )
            )

            if signature in normalized:
                return lines[index].y

    return None


# =====================================================
# Page PyMuPDF -> lignes géométriques
# =====================================================

def page_layout_lines(
    page,
    *,
    page_number: int,
) -> Tuple[
    LayoutLine,
    ...
]:
    """
    Convertit une page PyMuPDF en lignes géométriques
    grâce au moteur commun de layout.
    """

    if page_number < 1:
        raise ValueError(
            "page_number doit être >= 1."
        )

    raw_words = page.get_text(
        "words",
        sort=True,
    )

    words = words_from_pymupdf(
        raw_words
    )

    return group_words_into_lines(
        words,
        page_number=page_number,
    )


# =====================================================
# Validation des frontières
# =====================================================

def _validate_block_boundaries(
    block: QuestionOccurrenceBlock,
    next_block: Optional[
        QuestionOccurrenceBlock
    ],
) -> None:
    """
    Vérifie uniquement la cohérence structurelle
    nécessaire à l'extraction géométrique.
    """

    if block.start_page < 1:
        raise ValueError(
            "start_page invalide pour "
            f"{block.block_id}."
        )

    if (
        block.end_page
        < block.start_page
    ):
        raise ValueError(
            "Pages inversées pour "
            f"{block.block_id}."
        )

    if not block.matched_prompt:
        raise ValueError(
            "matched_prompt vide pour "
            f"{block.block_id}."
        )

    if next_block is None:
        return

    if (
        next_block.section_key
        != block.section_key
    ):
        raise ValueError(
            "Le bloc suivant appartient "
            "à une autre section."
        )

    if (
        next_block.source_order
        <= block.source_order
    ):
        raise ValueError(
            "Ordre source incohérent entre "
            f"{block.block_id} et "
            f"{next_block.block_id}."
        )

    if (
        next_block.start_page
        < block.start_page
    ):
        raise ValueError(
            "Le bloc suivant commence avant "
            "le bloc courant."
        )


# =====================================================
# Localisation d'une frontière
# =====================================================

def _find_block_prompt_y(
    lines: Sequence[
        LayoutLine
    ],
    block: QuestionOccurrenceBlock,
) -> Optional[float]:
    """
    Essaie d'abord matched_prompt puis,
    si nécessaire, original_question.
    """

    y = find_prompt_y(
        lines,
        block.matched_prompt,
    )

    if (
        y is None
        and block.original_question
    ):
        y = find_prompt_y(
            lines,
            block.original_question,
        )

    return y


# =====================================================
# Extraction depuis un document PyMuPDF ouvert
# =====================================================

def layout_context_from_document(
    document,
    *,
    block: QuestionOccurrenceBlock,
    next_block: Optional[
        QuestionOccurrenceBlock
    ] = None,
) -> QuestionLayoutContext:
    """
    Extrait le contexte géométrique exact
    d'un QuestionOccurrenceBlock.

    Le document PyMuPDF reste sous la responsabilité
    de l'appelant.
    """

    _validate_block_boundaries(
        block,
        next_block,
    )

    page_count = len(
        document
    )

    if (
        block.start_page > page_count
        or block.end_page > page_count
    ):
        raise ValueError(
            "Bloc hors limites du PDF : "
            f"{block.block_id} / "
            f"pages {block.start_page}-"
            f"{block.end_page} / "
            f"PDF={page_count} pages."
        )

    output = []

    for page_number in range(
        block.start_page,
        block.end_page + 1,
    ):
        page = document[
            page_number - 1
        ]

        lines = list(
            page_layout_lines(
                page,
                page_number=page_number,
            )
        )

        # -----------------------------------------
        # Début du bloc
        # -----------------------------------------

        start_y = None

        if (
            page_number
            == block.start_page
        ):
            start_y = (
                _find_block_prompt_y(
                    lines,
                    block,
                )
            )

            if start_y is None:
                raise ValueError(
                    "Début visuel du bloc "
                    "introuvable : "
                    f"{block.block_id} / "
                    f"page {page_number} / "
                    f"{block.matched_prompt!r}"
                )

        # -----------------------------------------
        # Fin du bloc
        # -----------------------------------------

        end_y = None

        if (
            next_block is not None
            and next_block.start_page
            == page_number
        ):
            end_y = (
                _find_block_prompt_y(
                    lines,
                    next_block,
                )
            )

            if end_y is None:
                raise ValueError(
                    "Début visuel du bloc suivant "
                    "introuvable : "
                    f"{next_block.block_id} / "
                    f"page {page_number} / "
                    f"{next_block.matched_prompt!r}"
                )

            if (
                start_y is not None
                and end_y <= start_y
            ):
                raise ValueError(
                    "Frontières géométriques "
                    "inversées entre "
                    f"{block.block_id} et "
                    f"{next_block.block_id}."
                )

        # -----------------------------------------
        # Conservation des lignes appartenant
        # réellement au bloc
        # -----------------------------------------

        for line in lines:
            if (
                start_y is not None
                and line.y < start_y
            ):
                continue

            if (
                end_y is not None
                and line.y >= end_y
            ):
                continue

            output.append(
                line
            )

    if not output:
        raise ValueError(
            "Aucune ligne géométrique extraite "
            f"pour {block.block_id}."
        )

    return QuestionLayoutContext(
        block_id=block.block_id,
        candidate_id=block.candidate_id,
        section_key=block.section_key,
        start_page=block.start_page,
        end_page=block.end_page,
        matched_prompt=(
            block.matched_prompt
        ),
        lines=tuple(
            output
        ),
    )


# =====================================================
# Entrée publique depuis les bytes du PDF
# =====================================================

def build_question_layout_context(
    pdf_bytes: bytes,
    *,
    block: QuestionOccurrenceBlock,
    next_block: Optional[
        QuestionOccurrenceBlock
    ] = None,
) -> QuestionLayoutContext:
    """
    Point d'entrée principal pour l'application.

    Accepte directement les bytes du PDF, ce qui est
    compatible avec les fichiers uploadés dans Streamlit.

    Le document PyMuPDF est toujours fermé ici.
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

    document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    try:
        return layout_context_from_document(
            document,
            block=block,
            next_block=next_block,
        )

    finally:
        document.close()
