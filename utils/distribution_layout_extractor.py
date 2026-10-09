# utils/distribution_layout_extractor.py

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import (
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
)
import math
import re
import unicodedata


# =====================================================
# Constantes
# =====================================================

DEFAULT_Y_TOLERANCE = 2.2
DEFAULT_COLUMN_TOLERANCE = 8.0
DEFAULT_GROUP_GAP = 22.0

_NUMBER_RE = re.compile(
    r"^-?\d+(?:[.,]\d+)?$"
)


# =====================================================
# Structures géométriques
# =====================================================

@dataclass(frozen=True)
class LayoutWord:
    text: str

    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class LayoutLine:
    page_number: int

    y: float

    words: Tuple[
        LayoutWord,
        ...
    ]

    @property
    def text(self) -> str:
        return " ".join(
            word.text
            for word in self.words
            if word.text.strip()
        ).strip()


# =====================================================
# Distribution générique
# =====================================================

@dataclass(frozen=True)
class DistributionRow:
    label: str

    nb_votants: float | int
    pourcentage: float | int

    page_number: int
    y: float

    count_x: float
    percentage_x: float

    source_text: str


@dataclass(frozen=True)
class DistributionDiagnostics:
    reliable: bool

    issues: Tuple[
        str,
        ...
    ]

    count_column_spread: Optional[float]

    count_sum: Optional[float]
    percentage_sum: Optional[float]

    explicit_total: Optional[
        float | int
    ]


@dataclass(frozen=True)
class DistributionLayoutResult:
    rows: Tuple[
        DistributionRow,
        ...
    ]

    diagnostics: DistributionDiagnostics

    method: str = "pymupdf_layout"

    @property
    def reliable(self) -> bool:
        return (
            self.diagnostics.reliable
        )


# =====================================================
# Normalisation
# =====================================================

def normalize_layout_text(
    value: str,
) -> str:
    """
    Normalisation uniquement pour comparer
    des libellés.

    Ne jamais utiliser cette fonction pour
    modifier le texte source conservé.
    """

    if not value:
        return ""

    text = (
        value
        .replace("’", "'")
        .replace("‘", "'")
        .replace("–", "-")
        .replace("—", "-")
        .replace("\u00a0", " ")
    )

    text = unicodedata.normalize(
        "NFKD",
        text,
    )

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(
            char
        )
    )

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# =====================================================
# Nombres
# =====================================================

def _parse_number(
    value: str,
) -> Optional[
    float | int
]:
    text = (
        value
        .strip()
        .replace(",", ".")
    )

    if not _NUMBER_RE.fullmatch(
        text
    ):
        return None

    number = float(
        text
    )

    if not math.isfinite(
        number
    ):
        return None

    if number.is_integer():
        return int(
            number
        )

    return number


# =====================================================
# Conversion PyMuPDF -> LayoutWord
# =====================================================

def words_from_pymupdf(
    raw_words: Iterable[
        tuple
    ],
) -> Tuple[
    LayoutWord,
    ...
]:
    """
    Convertit page.get_text("words") en structure
    indépendante de PyMuPDF.

    Les quatre premières valeurs sont :
        x0, y0, x1, y1

    La cinquième est le texte.
    """

    output: List[
        LayoutWord
    ] = []

    for item in raw_words:

        if len(item) < 5:
            continue

        x0, y0, x1, y1, text = (
            item[:5]
        )

        text = str(
            text
        )

        if not text.strip():
            continue

        output.append(
            LayoutWord(
                text=text,
                x0=float(x0),
                y0=float(y0),
                x1=float(x1),
                y1=float(y1),
            )
        )

    return tuple(
        output
    )


# =====================================================
# Mots -> lignes
# =====================================================

def group_words_into_lines(
    words: Sequence[
        LayoutWord
    ],
    *,
    page_number: int,
    y_tolerance: float = (
        DEFAULT_Y_TOLERANCE
    ),
) -> Tuple[
    LayoutLine,
    ...
]:
    """
    Regroupe géométriquement les mots situés
    sur une même ligne visuelle.
    """

    ordered = sorted(
        words,
        key=lambda word: (
            word.y0,
            word.x0,
        ),
    )

    groups: List[
        List[LayoutWord]
    ] = []

    anchors: List[
        float
    ] = []

    for word in ordered:

        target_index: Optional[int] = (
            None
        )

        for index in range(
            len(groups) - 1,
            max(-1, len(groups) - 5),
            -1,
        ):

            if (
                abs(
                    anchors[index]
                    - word.y0
                )
                <= y_tolerance
            ):
                target_index = index
                break

        if target_index is None:

            groups.append(
                [word]
            )

            anchors.append(
                word.y0
            )

        else:

            groups[
                target_index
            ].append(
                word
            )

    lines: List[
        LayoutLine
    ] = []

    for group in groups:

        ordered_group = tuple(
            sorted(
                group,
                key=lambda word: (
                    word.x0
                ),
            )
        )

        lines.append(
            LayoutLine(
                page_number=(
                    page_number
                ),
                y=min(
                    word.y0
                    for word
                    in ordered_group
                ),
                words=ordered_group,
            )
        )

    return tuple(
        sorted(
            lines,
            key=lambda line: (
                line.page_number,
                line.y,
            ),
        )
    )


# =====================================================
# Détection du couple pourcentage / effectif
# =====================================================

@dataclass(frozen=True)
class _NumericTail:
    count_index: int
    percentage_index: int

    count: float | int
    percentage: float | int

    count_x: float
    percentage_x: float


def _find_numeric_tail(
    line: LayoutLine,
) -> Optional[
    _NumericTail
]:
    """
    Cherche depuis la droite :

        effectif | pourcentage | %

    ou :

        effectif | "76%"

    Le moteur ne suppose aucune coordonnée x fixe.
    """

    words = line.words

    if not words:
        return None

    percentage_index: Optional[int] = (
        None
    )

    percentage: Optional[
        float | int
    ] = None

    # ---------------------------------------------
    # Pourcentage
    # ---------------------------------------------

    for index in range(
        len(words) - 1,
        -1,
        -1,
    ):

        token = (
            words[index]
            .text
            .strip()
        )

        if (
            token == "%"
            and index >= 1
        ):

            parsed = _parse_number(
                words[
                    index - 1
                ].text
            )

            if parsed is not None:

                percentage_index = (
                    index - 1
                )

                percentage = parsed
                break

        if token.endswith("%"):

            parsed = _parse_number(
                token[:-1]
            )

            if parsed is not None:

                percentage_index = (
                    index
                )

                percentage = parsed
                break

    if (
        percentage_index is None
        or percentage is None
    ):
        return None

    # ---------------------------------------------
    # Effectif
    # ---------------------------------------------

    count_index: Optional[int] = (
        None
    )

    count: Optional[
        float | int
    ] = None

    for index in range(
        percentage_index - 1,
        -1,
        -1,
    ):

        parsed = _parse_number(
            words[index].text
        )

        if parsed is not None:

            count_index = index
            count = parsed
            break

    if (
        count_index is None
        or count is None
    ):
        return None

    return _NumericTail(
        count_index=count_index,
        percentage_index=(
            percentage_index
        ),
        count=count,
        percentage=percentage,
        count_x=(
            words[count_index].x0
        ),
        percentage_x=(
            words[
                percentage_index
            ].x0
        ),
    )


# =====================================================
# Reconstruction du libellé
# =====================================================

def _horizontal_groups(
    words: Sequence[
        LayoutWord
    ],
    *,
    gap_threshold: float = (
        DEFAULT_GROUP_GAP
    ),
) -> Tuple[
    Tuple[LayoutWord, ...],
    ...
]:
    """
    Sépare des groupes de texte lorsque
    l'écart horizontal est important.

    Exemple :

        "10.0/"        "Insuffisamment"   0 0 %

    permet d'isoler "Insuffisamment".
    """

    if not words:
        return ()

    ordered = sorted(
        words,
        key=lambda word: (
            word.x0
        ),
    )

    groups: List[
        List[LayoutWord]
    ] = [
        [ordered[0]]
    ]

    for previous, current in zip(
        ordered,
        ordered[1:],
    ):

        gap = (
            current.x0
            - previous.x1
        )

        if gap > gap_threshold:

            groups.append(
                [current]
            )

        else:

            groups[-1].append(
                current
            )

    return tuple(
        tuple(group)
        for group in groups
    )


def _extract_label(
    line: LayoutLine,
    tail: _NumericTail,
) -> str:
    """
    Le libellé est le groupe de texte le plus
    à droite avant la colonne d'effectifs.

    Cela évite de prendre une note /10 ou une partie
    de question située à gauche de la modalité.
    """

    prefix = line.words[
        :tail.count_index
    ]

    if not prefix:
        return ""

    groups = _horizontal_groups(
        prefix
    )

    if not groups:
        return ""

    rightmost = groups[-1]

    return " ".join(
        word.text
        for word
        in rightmost
    ).strip()


# =====================================================
# Parsing d'une ligne
# =====================================================

def parse_distribution_line(
    line: LayoutLine,
) -> Optional[
    DistributionRow
]:
    tail = _find_numeric_tail(
        line
    )

    if tail is None:
        return None

    label = _extract_label(
        line,
        tail,
    )

    return DistributionRow(
        label=label,
        nb_votants=tail.count,
        pourcentage=(
            tail.percentage
        ),
        page_number=(
            line.page_number
        ),
        y=line.y,
        count_x=tail.count_x,
        percentage_x=(
            tail.percentage_x
        ),
        source_text=line.text,
    )


# =====================================================
# Total explicite
# =====================================================

_TOTAL_WORDS = {
    "votant",
    "votants",
    "repondant",
    "repondants",
    "participant",
    "participants",
}


def find_explicit_total(
    lines: Sequence[
        LayoutLine
    ],
) -> Optional[
    float | int
]:
    """
    Cherche uniquement un total explicitement écrit :

        309 votants
        24 répondants

    Le nombre retenu est celui situé au plus près
    du mot indiquant le total.

    Aucun total n'est calculé ici.
    """

    for line in lines:

        normalized_tokens = [
            normalize_layout_text(
                word.text
            )
            for word in line.words
        ]

        for total_index, token in enumerate(
            normalized_tokens
        ):

            if token not in _TOTAL_WORDS:
                continue

            # -------------------------------------
            # Priorité au nombre immédiatement
            # situé avant "votants/répondants..."
            # -------------------------------------

            for index in range(
                total_index - 1,
                -1,
                -1,
            ):

                parsed = _parse_number(
                    line.words[
                        index
                    ].text
                )

                if parsed is not None:
                    return parsed

            # -------------------------------------
            # Cas éventuel :
            # "votants 309"
            # -------------------------------------

            for index in range(
                total_index + 1,
                len(line.words),
            ):

                parsed = _parse_number(
                    line.words[
                        index
                    ].text
                )

                if parsed is not None:
                    return parsed

    return None


# =====================================================
# Diagnostics
# =====================================================

def _sum_numeric(
    values: Iterable[
        float | int
    ],
) -> float:
    return float(
        sum(values)
    )


def analyze_distribution_rows(
    rows: Sequence[
        DistributionRow
    ],
    *,
    explicit_total: Optional[
        float | int
    ] = None,
    column_tolerance: float = (
        DEFAULT_COLUMN_TOLERANCE
    ),
) -> DistributionDiagnostics:
    """
    Produit un diagnostic conservateur.

    Important :
    la somme des pourcentages n'est PAS obligée
    de faire 100, car Digiforma peut arrondir ou
    tronquer ses pourcentages.
    """

    issues: List[
        str
    ] = []

    if not rows:

        return DistributionDiagnostics(
            reliable=False,
            issues=(
                "no_distribution_rows",
            ),
            count_column_spread=None,
            count_sum=None,
            percentage_sum=None,
            explicit_total=explicit_total,
        )

    # ---------------------------------------------
    # Libellés
    # ---------------------------------------------

    if any(
        not row.label.strip()
        for row in rows
    ):
        issues.append(
            "missing_label"
        )

    normalized_labels = [
        normalize_layout_text(
            row.label
        )
        for row in rows
        if row.label.strip()
    ]

    if (
        normalized_labels
        and len(
            set(normalized_labels)
        )
        != len(normalized_labels)
    ):
        issues.append(
            "duplicate_label"
        )

    # ---------------------------------------------
    # Colonnes
    # ---------------------------------------------

    count_positions = [
        row.count_x
        for row in rows
    ]

    spread = (
        max(count_positions)
        - min(count_positions)
    )

    if spread > column_tolerance:

        issues.append(
            "inconsistent_count_column"
        )

    # ---------------------------------------------
    # Valeurs
    # ---------------------------------------------

    if any(
        row.nb_votants < 0
        for row in rows
    ):
        issues.append(
            "negative_count"
        )

    if any(
        (
            row.pourcentage < 0
            or row.pourcentage > 100
        )
        for row in rows
    ):
        issues.append(
            "invalid_percentage"
        )

    count_sum = _sum_numeric(
        row.nb_votants
        for row in rows
    )

    percentage_sum = _sum_numeric(
        row.pourcentage
        for row in rows
    )

    # ---------------------------------------------
    # Total explicite
    # ---------------------------------------------

    if (
        explicit_total is not None
        and abs(
            count_sum
            - float(explicit_total)
        )
        > 0.001
    ):
        issues.append(
            "count_sum_differs_from_explicit_total"
        )

    # La somme des pourcentages est informative.
    # Elle ne rend pas le résultat invalide.
    if (
        percentage_sum < 90
        or percentage_sum > 110
    ):
        issues.append(
            "unusual_percentage_sum"
        )

    hard_failures = {
        "no_distribution_rows",
        "missing_label",
        "duplicate_label",
        "inconsistent_count_column",
        "negative_count",
        "invalid_percentage",
        "count_sum_differs_from_explicit_total",
    }

    reliable = not any(
        issue in hard_failures
        for issue in issues
    )

    return DistributionDiagnostics(
        reliable=reliable,
        issues=tuple(
            issues
        ),
        count_column_spread=spread,
        count_sum=count_sum,
        percentage_sum=(
            percentage_sum
        ),
        explicit_total=(
            explicit_total
        ),
    )


# =====================================================
# Parsing générique d'un ensemble de lignes
# =====================================================

def parse_distribution_lines(
    lines: Sequence[
        LayoutLine
    ],
) -> DistributionLayoutResult:
    """
    Parse toutes les lignes qui ressemblent à
    des lignes de distribution.

    Cette fonction ne cherche PAS encore le bloc
    d'une question dans un PDF.

    Elle constitue le coeur géométrique réutilisable.
    """

    rows: List[
        DistributionRow
    ] = []

    for line in lines:

        row = parse_distribution_line(
            line
        )

        if row is not None:

            rows.append(
                row
            )

    explicit_total = (
        find_explicit_total(
            lines
        )
    )

    diagnostics = (
        analyze_distribution_rows(
            rows,
            explicit_total=(
                explicit_total
            ),
        )
    )

    return DistributionLayoutResult(
        rows=tuple(rows),
        diagnostics=diagnostics,
    )


# =====================================================
# Classification métier générique
# =====================================================

def classify_distribution(
    result: DistributionLayoutResult,
) -> str:
    """
    Classification informative.

    Retour possible :
        numeric_scale
        yes_no
        categorical
        unresolved
    """

    if not result.rows:
        return "unresolved"

    labels = [
        normalize_layout_text(
            row.label
        )
        for row in result.rows
    ]

    if any(
        not label
        for label in labels
    ):
        return "unresolved"

    if all(
        _NUMBER_RE.fullmatch(
            label.replace(",", ".")
        )
        for label in labels
    ):
        return "numeric_scale"

    if set(labels).issubset(
        {
            "oui",
            "non",
        }
    ):
        return "yes_no"

    return "categorical"


# =====================================================
# Adaptateur distribution 1 -> 5
# =====================================================

def distribution_1_to_5_payload(
    result: DistributionLayoutResult,
) -> dict:
    """
    Transforme une distribution générique fiable
    en payload compatible avec le contrat
    distribution_1_5 actuel.

    Aucun calcul d'effectif ou de pourcentage.
    """

    if not result.reliable:

        raise ValueError(
            "Distribution non suffisamment fiable : "
            + ", ".join(
                result.diagnostics.issues
            )
        )

    by_level = {}

    for row in result.rows:

        normalized = (
            normalize_layout_text(
                row.label
            )
        )

        parsed_level = _parse_number(
            normalized
        )

        if not isinstance(
            parsed_level,
            int,
        ):
            raise ValueError(
                "Échelon non entier : "
                f"{row.label!r}"
            )

        if parsed_level not in {
            1,
            2,
            3,
            4,
            5,
        }:
            raise ValueError(
                "Échelon hors 1..5 : "
                f"{parsed_level}"
            )

        if parsed_level in by_level:
            raise ValueError(
                "Échelon dupliqué : "
                f"{parsed_level}"
            )

        by_level[
            parsed_level
        ] = row

    expected = {
        1,
        2,
        3,
        4,
        5,
    }

    if set(
        by_level
    ) != expected:

        raise ValueError(
            "Distribution 1..5 incomplète. "
            f"Niveaux trouvés : "
            f"{sorted(by_level)}"
        )

    return {
        "nb_votants": (
            result
            .diagnostics
            .explicit_total
        ),
        "levels": [
            {
                "level": level,
                "nb_votants": (
                    by_level[
                        level
                    ].nb_votants
                ),
                "pourcentage": (
                    by_level[
                        level
                    ].pourcentage
                ),
            }
            for level in (
                1,
                2,
                3,
                4,
                5,
            )
        ],
    }
