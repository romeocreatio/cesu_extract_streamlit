# utils/mastery_layout_extractor.py

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import (
    Literal,
    Optional,
    Tuple,
)

from utils.distribution_layout_extractor import (
    LayoutLine,
    normalize_layout_text,
)
from utils.question_layout_context import (
    QuestionLayoutContext,
)


# =====================================================
# Types
# =====================================================

Number = int | float

MasteryLayoutStatus = Literal[
    "success",
    "not_detected",
    "unreliable",
]


# =====================================================
# Configuration métier / géométrique
# =====================================================

MODALITY_SPECS = (
    (
        "totalement",
        "totalement",
    ),
    (
        "en partie",
        "en_partie",
    ),
    (
        "insuffisamment",
        "insuffisamment",
    ),
    (
        "pas du tout",
        "pas_du_tout",
    ),
)

EXPECTED_MODALITIES = tuple(
    source_label
    for (
        source_label,
        _,
    ) in MODALITY_SPECS
)

INLINE_NOTE_RE = re.compile(
    r"^(\d+(?:[.,]\d+)?)/$"
)

NUMBER_RE = re.compile(
    r"^\d+(?:[.,]\d+)?$"
)


# =====================================================
# Résultats internes
# =====================================================

@dataclass(frozen=True)
class _PhraseMatch:
    start_index: int
    end_index: int

    x0: float
    x1: float


@dataclass(frozen=True)
class _DetectedModality:
    source_label: str
    output_key: str

    x0: float
    x1: float


@dataclass(frozen=True)
class _ModalityRow:
    line_index: int

    source_label: str
    output_key: str

    x0: float
    x1: float

    nb_votants: Number
    pourcentage: Number

    source_text: str


@dataclass(frozen=True)
class _InlineNote:
    value: Number

    page_number: int
    y: float

    x0: float
    x1: float


# =====================================================
# Résultat public
# =====================================================

@dataclass(frozen=True)
class MasteryLayoutExtraction:
    """
    Résultat de l'extraction géométrique de la question
    maitrise_objectifs.

    raw_payload respecte directement le schéma JSON
    attendu par le parseur métier lorsque status=success.

    Aucun calcul métier n'est effectué :
    - aucun pourcentage n'est recalculé ;
    - aucun effectif n'est déduit ;
    - aucune note n'est moyennée.
    """

    status: MasteryLayoutStatus

    raw_payload: Optional[
        dict
    ]

    issues: Tuple[
        str,
        ...,
    ] = ()

    method: str = (
        "pymupdf_mastery_layout"
    )

    @property
    def succeeded(self) -> bool:
        return (
            self.status
            == "success"
        )


# =====================================================
# Helpers génériques
# =====================================================

def _number_from_text(
    value: str,
) -> Optional[
    Number
]:
    cleaned = (
        value
        .strip()
        .replace(",", ".")
    )

    if not NUMBER_RE.fullmatch(
        cleaned
    ):
        return None

    number = float(
        cleaned
    )

    if number.is_integer():
        return int(
            number
        )

    return number


def _normalized_words(
    line: LayoutLine,
) -> Tuple[
    str,
    ...,
]:
    return tuple(
        normalize_layout_text(
            word.text
        )
        for word in line.words
    )


# =====================================================
# Recherche exacte d'une phrase dans une ligne
# =====================================================

def _phrase_matches(
    line: LayoutLine,
    phrase: str,
) -> Tuple[
    _PhraseMatch,
    ...,
]:
    target_tokens = tuple(
        normalize_layout_text(
            token
        )
        for token
        in phrase.split()
    )

    if not target_tokens:
        return ()

    words = _normalized_words(
        line
    )

    width = len(
        target_tokens
    )

    matches = []

    for index in range(
        len(words)
        - width
        + 1
    ):
        candidate = words[
            index:index + width
        ]

        if (
            candidate
            != target_tokens
        ):
            continue

        selected = line.words[
            index:index + width
        ]

        matches.append(
            _PhraseMatch(
                start_index=index,
                end_index=(
                    index
                    + width
                    - 1
                ),
                x0=selected[0].x0,
                x1=selected[-1].x1,
            )
        )

    return tuple(
        matches
    )


# =====================================================
# Détection d'une modalité
# =====================================================

def _detect_modality(
    line: LayoutLine,
) -> Optional[
    _DetectedModality
]:
    candidates = []

    for (
        source_label,
        output_key,
    ) in MODALITY_SPECS:

        for match in _phrase_matches(
            line,
            source_label,
        ):
            candidates.append(
                (
                    match.x0,
                    _DetectedModality(
                        source_label=(
                            source_label
                        ),
                        output_key=(
                            output_key
                        ),
                        x0=match.x0,
                        x1=match.x1,
                    ),
                )
            )

    if not candidates:
        return None

    # La vraie modalité Digiforma est située
    # dans la colonne de droite.
    #
    # Cela évite notamment de confondre :
    #
    # "Mises en situations En partie"
    #
    # avec le mot "en" du libellé.
    return max(
        candidates,
        key=lambda item: item[0],
    )[1]


# =====================================================
# Effectif + pourcentage
# =====================================================

def _numbers_right_of_modality(
    line: LayoutLine,
    modality: _DetectedModality,
) -> Tuple[
    Number,
    ...,
]:
    values = []

    for word in line.words:

        if (
            word.x0
            <= modality.x1
        ):
            continue

        value = _number_from_text(
            word.text
        )

        if value is None:
            continue

        values.append(
            value
        )

    return tuple(
        values
    )


# =====================================================
# Note /10 d'un sous-objectif
# =====================================================

def _inline_note_candidates(
    lines: Tuple[
        LayoutLine,
        ...,
    ],
) -> Tuple[
    _InlineNote,
    ...,
]:
    output = []

    for line in lines:

        for word in line.words:

            match = INLINE_NOTE_RE.fullmatch(
                word.text.strip()
            )

            if not match:
                continue

            value = float(
                match.group(1)
                .replace(",", ".")
            )

            if not (
                0 <= value <= 10
            ):
                continue

            if value.is_integer():
                parsed_value: Number = int(
                    value
                )
            else:
                parsed_value = value

            output.append(
                _InlineNote(
                    value=parsed_value,
                    page_number=(
                        line.page_number
                    ),
                    y=line.y,
                    x0=word.x0,
                    x1=word.x1,
                )
            )

    return tuple(
        output
    )


# =====================================================
# Note globale de la question principale
# =====================================================

def _global_note_candidates(
    lines: Tuple[
        LayoutLine,
        ...,
    ],
) -> Tuple[
    Number,
    ...,
]:
    """
    Cherche une structure géométrique :

        5.7
           /
        10

    avant la première modalité.

    Le numéro de page isolé n'est donc pas retenu.
    """

    output = []

    for line in lines:

        for word in line.words:

            value = _number_from_text(
                word.text
            )

            if value is None:
                continue

            if not (
                0 <= value <= 10
            ):
                continue

            slash_found = False
            denominator_found = False

            for other_line in lines:

                if (
                    other_line.page_number
                    != line.page_number
                ):
                    continue

                for other_word in (
                    other_line.words
                ):

                    raw = (
                        other_word.text
                        .strip()
                    )

                    if raw == "/":

                        if (
                            other_word.x0
                            >= word.x0
                            and (
                                other_word.x0
                                - word.x0
                            ) < 45
                            and abs(
                                other_line.y
                                - line.y
                            ) < 12
                        ):
                            slash_found = True

                    elif raw == "10":

                        if (
                            other_line.y
                            > line.y
                            and (
                                other_line.y
                                - line.y
                            ) < 30
                            and abs(
                                other_word.x0
                                - word.x0
                            ) < 45
                        ):
                            denominator_found = (
                                True
                            )

            if (
                slash_found
                and denominator_found
            ):
                output.append(
                    value
                )

    return tuple(
        output
    )


# =====================================================
# Reconstruction du libellé
# =====================================================

def _extract_label_and_note(
    lines: Tuple[
        LayoutLine,
        ...,
    ],
    *,
    modality_start_x: float,
) -> Tuple[
    str,
    Number,
]:
    notes = (
        _inline_note_candidates(
            lines
        )
    )

    if len(notes) != 1:
        raise ValueError(
            "Une seule note /10 "
            "était attendue pour "
            "le sous-objectif ; "
            f"trouvé={len(notes)}."
        )

    note = notes[0]

    fragments = []

    for line in lines:

        selected_words = []

        for word in line.words:

            # La colonne du libellé est située
            # avant la vraie colonne des modalités.
            if (
                word.x0
                >= modality_start_x
            ):
                continue

            raw = (
                word.text
                .strip()
            )

            # Numérateur de la note :
            # 4.8/
            # 8.4/
            if INLINE_NOTE_RE.fullmatch(
                raw
            ):
                continue

            # Dénominateur de la même note.
            if (
                raw == "10"
                and word.x0 > note.x0
                and (
                    word.x0
                    - note.x0
                ) < 60
                and (
                    line.page_number
                    == note.page_number
                )
                and abs(
                    line.y
                    - note.y
                ) < 10
            ):
                continue

            selected_words.append(
                raw
            )

        if selected_words:
            fragments.append(
                " ".join(
                    selected_words
                )
            )

    label = ""

    for fragment in fragments:

        if not label:
            label = fragment
            continue

        # Mot coupé en fin de ligne :
        #
        # cardio-
        # respiratoire
        #
        # -> cardio-respiratoire
        if label.endswith("-"):
            label += fragment

        else:
            label += (
                " "
                + fragment
            )

    label = label.strip()

    if not label:
        raise ValueError(
            "Libellé de sous-objectif vide."
        )

    if re.search(
        r"\d+(?:[.,]\d+)?/",
        label,
    ):
        raise ValueError(
            "Une note /10 subsiste "
            "dans le libellé : "
            f"{label!r}"
        )

    normalized = (
        normalize_layout_text(
            label
        )
    )

    if (
        "evaluer vos competences"
        in normalized
    ):
        raise ValueError(
            "Une famille suivante "
            "'Evaluer vos competences' "
            "a été absorbée dans "
            f"le libellé : {label!r}"
        )

    return (
        label,
        note.value,
    )


# =====================================================
# Résultats d'échec
# =====================================================

def _failure(
    *,
    status: MasteryLayoutStatus,
    issue: str,
) -> MasteryLayoutExtraction:
    return MasteryLayoutExtraction(
        status=status,
        raw_payload=None,
        issues=(
            issue,
        ),
    )


# =====================================================
# Extraction publique
# =====================================================

def extract_mastery_layout(
    context: QuestionLayoutContext,
) -> MasteryLayoutExtraction:
    """
    Extrait de manière déterministe une question
    maitrise_objectifs au format Digiforma observé
    dans le corpus CESU 83 2026.

    Structure reconnue :

        note globale /10

        sous-objectif
        note /10
        Totalement       effectif + %
        En partie        effectif + %
        Insuffisamment   effectif + %
        Pas du tout      effectif + %

    Aucun appel réseau.
    Aucun LLM.
    Aucun calcul de valeurs absentes.
    """

    if not isinstance(
        context,
        QuestionLayoutContext,
    ):
        raise TypeError(
            "context doit être un "
            "QuestionLayoutContext."
        )

    if not context.lines:
        return _failure(
            status="not_detected",
            issue="empty_layout_context",
        )

    rows = []

    first_modality_line_index = None

    for (
        line_index,
        line,
    ) in enumerate(
        context.lines
    ):

        modality = (
            _detect_modality(
                line
            )
        )

        if modality is None:
            continue

        if (
            first_modality_line_index
            is None
        ):
            first_modality_line_index = (
                line_index
            )

        numbers = (
            _numbers_right_of_modality(
                line,
                modality,
            )
        )

        if len(numbers) != 2:
            return _failure(
                status="unreliable",
                issue=(
                    "distribution_values_"
                    "not_exactly_two: "
                    f"{line.text!r} / "
                    f"{numbers!r}"
                ),
            )

        rows.append(
            _ModalityRow(
                line_index=(
                    line_index
                ),
                source_label=(
                    modality.source_label
                ),
                output_key=(
                    modality.output_key
                ),
                x0=modality.x0,
                x1=modality.x1,
                nb_votants=numbers[0],
                pourcentage=numbers[1],
                source_text=line.text,
            )
        )

    if not rows:
        return _failure(
            status="not_detected",
            issue="no_mastery_modality_rows",
        )

    if (
        len(rows) % 4
        != 0
    ):
        return _failure(
            status="unreliable",
            issue=(
                "modality_row_count_"
                "not_multiple_of_four: "
                f"{len(rows)}"
            ),
        )

    if (
        first_modality_line_index
        is None
    ):
        return _failure(
            status="unreliable",
            issue=(
                "first_modality_line_"
                "index_missing"
            ),
        )

    # ---------------------------------------------
    # Note globale
    # ---------------------------------------------

    header_lines = tuple(
        context.lines[
            :first_modality_line_index
        ]
    )

    global_candidates = (
        _global_note_candidates(
            header_lines
        )
    )

    if len(global_candidates) > 1:
        return _failure(
            status="unreliable",
            issue=(
                "multiple_global_notes: "
                f"{global_candidates!r}"
            ),
        )

    global_note = (
        global_candidates[0]
        if global_candidates
        else None
    )

    # ---------------------------------------------
    # Sous-objectifs
    # ---------------------------------------------

    objectives = []

    for offset in range(
        0,
        len(rows),
        4,
    ):

        group = rows[
            offset:offset + 4
        ]

        actual_order = tuple(
            row.source_label
            for row in group
        )

        if (
            actual_order
            != EXPECTED_MODALITIES
        ):
            return _failure(
                status="unreliable",
                issue=(
                    "unexpected_modality_order: "
                    f"{actual_order!r}"
                ),
            )

        start_line_index = (
            group[0].line_index
        )

        if (
            offset + 4
            < len(rows)
        ):
            end_line_index = (
                rows[
                    offset + 4
                ].line_index
            )

        else:
            end_line_index = len(
                context.lines
            )

        objective_lines = tuple(
            context.lines[
                start_line_index:
                end_line_index
            ]
        )

        modality_start_x = min(
            row.x0
            for row in group
        )

        try:
            (
                label,
                note,
            ) = _extract_label_and_note(
                objective_lines,
                modality_start_x=(
                    modality_start_x
                ),
            )

        except ValueError as exc:
            return _failure(
                status="unreliable",
                issue=(
                    "objective_parse_error: "
                    f"{exc}"
                ),
            )

        levels = {}

        for row in group:

            levels[
                row.output_key
            ] = {
                "nb_votants": (
                    row.nb_votants
                ),
                "pourcentage": (
                    row.pourcentage
                ),
            }

        objectives.append(
            {
                "objectif_label": label,
                "levels": levels,
                "note_sur_10": note,
            }
        )

    raw_payload = {
        "mode": "4_niveaux",
        "par_objectif": (
            objectives
        ),
        (
            "note_globale_"
            "objectifs_preformation"
        ): global_note,
    }

    return MasteryLayoutExtraction(
        status="success",
        raw_payload=raw_payload,
        issues=(),
    )
