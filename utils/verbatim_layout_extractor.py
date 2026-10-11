# utils/verbatim_layout_extractor.py

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Literal,
    Optional,
    Tuple,
)

import fitz

from utils.question_layout_context import (
    QuestionLayoutContext,
)


# =====================================================
# Configuration validee sur le profil standard 2026
# =====================================================

IDENTITY_MIN_FONT_SIZE = 7.5
IDENTITY_MAX_FONT_SIZE = 9.0

RESPONSE_MIN_FONT_SIZE = 10.0
RESPONSE_MAX_FONT_SIZE = 11.0

LEFT_COLUMN_MAX_X = 200.0

LINE_Y_TOLERANCE = 1.0


# =====================================================
# Types
# =====================================================

VerbatimLayoutStatus = Literal[
    "success",
    "not_detected",
    "unreliable",
]


@dataclass(frozen=True)
class LocatedVerbatim:
    """
    Verbatim exact localise dans le texte du bloc.

    start_char / end_char sont relatifs au
    QuestionOccurrenceBlock complet.
    """

    text: str
    start_char: int
    end_char: int


@dataclass(frozen=True)
class VerbatimLayoutExtraction:
    """
    Resultat deterministe d'extraction des verbatims.

    Les identites des repondants ne sont jamais
    stockees dans ce resultat.
    """

    status: VerbatimLayoutStatus

    items: Tuple[
        str,
        ...,
    ]

    located_items: Tuple[
        LocatedVerbatim,
        ...,
    ]

    issues: Tuple[
        str,
        ...,
    ] = ()

    method: str = (
        "pymupdf_verbatim_typography"
    )

    @property
    def succeeded(
        self,
    ) -> bool:
        return self.status == "success"

    @property
    def raw_payload(
        self,
    ) -> Optional[dict]:
        if not self.succeeded:
            return None

        return {
            "items": list(
                self.items
            ),
        }


# =====================================================
# Ligne issue de get_text("dict")
# =====================================================

@dataclass(frozen=True)
class _StyledLine:
    text: str
    y: float
    font_size: float


def _page_dict_lines(
    page,
) -> Tuple[
    _StyledLine,
    ...,
]:
    """
    Extrait texte + position verticale + taille
    de police depuis une page PyMuPDF.
    """

    output = []

    data = page.get_text(
        "dict",
        sort=True,
    )

    for block in data.get(
        "blocks",
        [],
    ):

        for line in block.get(
            "lines",
            [],
        ):

            spans = line.get(
                "spans",
                [],
            )

            if not spans:
                continue

            text = "".join(
                span.get(
                    "text",
                    "",
                )
                for span in spans
            ).strip()

            if not text:
                continue

            sizes = [
                float(
                    span.get(
                        "size",
                        0,
                    )
                )
                for span in spans
                if span.get(
                    "text",
                    "",
                ).strip()
            ]

            if not sizes:
                continue

            output.append(
                _StyledLine(
                    text=text,
                    y=float(
                        line["bbox"][1]
                    ),
                    font_size=max(
                        sizes
                    ),
                )
            )

    return tuple(
        output
    )


# =====================================================
# Association ligne contexte -> style PDF
# =====================================================

def _style_for_context_line(
    source_lines: Tuple[
        _StyledLine,
        ...,
    ],
    *,
    context_text: str,
    context_y: float,
) -> Optional[
    _StyledLine
]:
    """
    Retrouve la ligne graphique correspondant
    a une ligne du QuestionLayoutContext.
    """

    candidates = [
        line
        for line in source_lines
        if abs(
            line.y
            - context_y
        ) <= LINE_Y_TOLERANCE
    ]

    if not candidates:
        return None

    exact = [
        line
        for line in candidates
        if (
            line.text.strip()
            == context_text.strip()
        )
    ]

    if exact:
        candidates = exact

    return min(
        candidates,
        key=lambda line: abs(
            line.y
            - context_y
        ),
    )


# =====================================================
# Classification typographique
# =====================================================

def _contains_letter(
    value: str,
) -> bool:
    return any(
        char.isalpha()
        for char in value
    )


def _is_identity_line(
    *,
    text: str,
    font_size: float,
    x0: float,
) -> bool:
    """
    Ligne d'identite Digiforma standard 2026.

    L'identite sert uniquement de separateur
    structurel et n'est jamais retournee.
    """

    return (
        IDENTITY_MIN_FONT_SIZE
        <= font_size
        <= IDENTITY_MAX_FONT_SIZE
        and x0 < LEFT_COLUMN_MAX_X
        and _contains_letter(
            text
        )
    )


def _is_response_line(
    *,
    font_size: float,
    x0: float,
) -> bool:
    """
    Ligne appartenant au contenu libre saisi
    par un repondant.
    """

    return (
        RESPONSE_MIN_FONT_SIZE
        <= font_size
        <= RESPONSE_MAX_FONT_SIZE
        and x0 < LEFT_COLUMN_MAX_X
    )


# =====================================================
# Localisation exacte dans block.text
# =====================================================

def _locate_responses(
    responses: Tuple[
        str,
        ...,
    ],
    *,
    block_text: str,
) -> Optional[
    Tuple[
        LocatedVerbatim,
        ...,
    ]
]:
    """
    Retrouve chaque reponse exactement et dans
    l'ordre source dans le texte du bloc.

    Cela preserve aussi plusieurs reponses identiques
    donnees par des personnes differentes.
    """

    output = []

    search_from = 0

    for response in responses:

        start = block_text.find(
            response,
            search_from,
        )

        if start < 0:
            return None

        end = (
            start
            + len(response)
        )

        output.append(
            LocatedVerbatim(
                text=response,
                start_char=start,
                end_char=end,
            )
        )

        search_from = end

    return tuple(
        output
    )


# =====================================================
# Extraction publique
# =====================================================

def extract_verbatim_layout(
    pdf_bytes: bytes,
    context: QuestionLayoutContext,
    *,
    block_text: str,
    chunk_start_char: int = 0,
    chunk_end_char: Optional[
        int
    ] = None,
) -> VerbatimLayoutExtraction:
    """
    Extrait les reponses libres d'un bloc Digiforma.

    Principes :
    - aucune identite n'est retournee ;
    - aucun nettoyage des verbatims ;
    - aucune reformulation ;
    - chaque reponse doit etre retrouvee exactement
      dans block_text ;
    - pour un bloc multi-chunk, seules les reponses
      entierement contenues dans le chunk courant
      sont retournees.

    Aucun appel externe.
    """

    if not isinstance(
        pdf_bytes,
        bytes,
    ):
        raise TypeError(
            "pdf_bytes doit etre de type bytes."
        )

    if not pdf_bytes:
        raise ValueError(
            "pdf_bytes est vide."
        )

    if not isinstance(
        context,
        QuestionLayoutContext,
    ):
        raise TypeError(
            "context doit etre un "
            "QuestionLayoutContext."
        )

    if not isinstance(
        block_text,
        str,
    ):
        raise TypeError(
            "block_text doit etre une chaine."
        )

    if not block_text:
        raise ValueError(
            "block_text est vide."
        )

    if chunk_start_char < 0:
        raise ValueError(
            "chunk_start_char doit etre >= 0."
        )

    if chunk_end_char is None:
        chunk_end_char = len(
            block_text
        )

    if (
        chunk_end_char
        < chunk_start_char
        or chunk_end_char
        > len(block_text)
    ):
        raise ValueError(
            "Bornes de chunk invalides."
        )

    document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    try:

        page_cache = {}

        styled_context = []

        style_failures = 0

        for line in context.lines:

            page_number = (
                line.page_number
            )

            if (
                page_number
                not in page_cache
            ):
                page_cache[
                    page_number
                ] = _page_dict_lines(
                    document[
                        page_number - 1
                    ]
                )

            style = (
                _style_for_context_line(
                    page_cache[
                        page_number
                    ],
                    context_text=(
                        line.text
                    ),
                    context_y=line.y,
                )
            )

            if style is None:
                style_failures += 1
                continue

            if not line.words:
                continue

            x0 = min(
                word.x0
                for word in line.words
            )

            styled_context.append(
                (
                    line.text,
                    style.font_size,
                    x0,
                )
            )

    finally:
        document.close()

    if style_failures:
        return VerbatimLayoutExtraction(
            status="unreliable",
            items=(),
            located_items=(),
            issues=(
                "layout_style_match_failure",
            ),
        )

    # -------------------------------------------------
    # Reconstitution des reponses entre identites
    # -------------------------------------------------

    responses = []

    current_lines = []

    identity_detected = False

    for (
        text,
        font_size,
        x0,
    ) in styled_context:

        if _is_identity_line(
            text=text,
            font_size=font_size,
            x0=x0,
        ):

            if (
                identity_detected
                and current_lines
            ):
                responses.append(
                    "\n".join(
                        current_lines
                    )
                )

            current_lines = []

            identity_detected = True

            continue

        if not identity_detected:
            continue

        if _is_response_line(
            font_size=font_size,
            x0=x0,
        ):
            current_lines.append(
                text
            )

    if (
        identity_detected
        and current_lines
    ):
        responses.append(
            "\n".join(
                current_lines
            )
        )

    # -------------------------------------------------
    # Sans identite, la structure n'est pas reconnue.
    # -------------------------------------------------

    if not identity_detected:
        return VerbatimLayoutExtraction(
            status="not_detected",
            items=(),
            located_items=(),
            issues=(
                "no_identity_separator_detected",
            ),
        )

    # -------------------------------------------------
    # Localisation exacte dans le texte source.
    # -------------------------------------------------

    located = _locate_responses(
        tuple(
            responses
        ),
        block_text=block_text,
    )

    if located is None:
        return VerbatimLayoutExtraction(
            status="unreliable",
            items=(),
            located_items=(),
            issues=(
                "verbatim_not_found_exactly_"
                "in_block_text",
            ),
        )

    # -------------------------------------------------
    # Filtrage par chunk.
    #
    # Une reponse doit etre ENTIEREMENT presente
    # dans le chunk.
    # -------------------------------------------------

    selected = tuple(
        item
        for item in located
        if (
            item.start_char
            >= chunk_start_char
            and item.end_char
            <= chunk_end_char
        )
    )

    return VerbatimLayoutExtraction(
        status="success",
        items=tuple(
            item.text
            for item in selected
        ),
        located_items=selected,
        issues=(),
    )
