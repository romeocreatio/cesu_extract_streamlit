# utils/progression_metric_extractor_2026.py

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import (
    Literal,
    Optional,
    Tuple,
)

from utils.pdf_reader import (
    PdfReadResult,
)
from utils.question_extraction_contracts import (
    ReportMetricResult,
)
from utils.question_payload_parser import (
    parse_extraction_payload,
)


# =====================================================
# Types
# =====================================================

ProgressionMetricStatus2026 = Literal[
    "success",
    "not_detected",
    "ambiguous",
]


# =====================================================
# Resultat public
# =====================================================

@dataclass(frozen=True)
class ProgressionMetricExtraction2026:
    """
    Extraction de la metrique de progression affichee
    explicitement dans le rapport Digiforma.

    Aucun calcul entre une note preformation et une
    note ulterieure n'est effectue.

    source_text conserve la representation source
    utilisee pour l'extraction.
    """

    status: ProgressionMetricStatus2026

    payload: Optional[
        ReportMetricResult
    ]

    source_text: Optional[str]

    page_number: Optional[int]

    issues: Tuple[
        str,
        ...,
    ] = ()

    method: str = "pdfplumber_page_text"

    @property
    def succeeded(self) -> bool:
        return self.status == "success"


# =====================================================
# Constantes
# =====================================================

_TARGET_HEADING = (
    "progression des competences"
)

# Cas compact :
# +2.8 / 10
_COMPACT_METRIC_RE = re.compile(
    r"^\s*"
    r"(?P<sign>[+\-\u2212])"
    r"\s*"
    r"(?P<number>\d+(?:[.,]\d+)?)"
    r"\s*/\s*10"
    r"\s*$",
    flags=re.IGNORECASE,
)

# Cas Digiforma observe en 2026 :
# +2.8
_STANDALONE_SIGNED_VALUE_RE = re.compile(
    r"^\s*"
    r"(?P<sign>[+\-\u2212])"
    r"\s*"
    r"(?P<number>\d+(?:[.,]\d+)?)"
    r"\s*$",
)

# Ligne separee :
# / 10
_STANDALONE_DENOMINATOR_RE = re.compile(
    r"^\s*/\s*10\s*$",
    flags=re.IGNORECASE,
)

# La metrique apparait juste avant le titre.
_LINES_BEFORE_HEADING = 8

# Pour la structure split :
# valeur signee -> au maximum 3 lignes -> /10
_MAX_DENOMINATOR_DISTANCE = 3


# =====================================================
# Helpers
# =====================================================

def _normalize_text(
    text: str,
) -> str:
    """
    Normalisation uniquement destinee a la detection
    du titre.

    Le texte source de la metrique n'est pas modifie.
    """

    decomposed = unicodedata.normalize(
        "NFKD",
        text,
    )

    without_accents = "".join(
        char
        for char in decomposed
        if not unicodedata.combining(
            char
        )
    )

    return " ".join(
        without_accents
        .lower()
        .split()
    )


def _parse_signed_value(
    *,
    sign: str,
    number: str,
) -> int | float:
    """
    Convertit uniquement la valeur explicitement
    affichee dans la source.

    Aucun calcul de progression n'est effectue.
    """

    numeric_text = (
        number
        .replace(",", ".")
        .strip()
    )

    value = float(
        numeric_text
    )

    if sign in {
        "-",
        "\u2212",
    }:
        value = -value

    if value.is_integer():
        return int(value)

    return value


def _build_payload(
    *,
    sign: str,
    number: str,
) -> ReportMetricResult:
    """
    Passe par le parseur commun report_metric afin
    d'appliquer le contrat interne valide.
    """

    value = _parse_signed_value(
        sign=sign,
        number=number,
    )

    payload = parse_extraction_payload(
        "report_metric",
        {
            "value_sur_10": value,
        },
    )

    if not isinstance(
        payload,
        ReportMetricResult,
    ):
        raise TypeError(
            "Le parseur report_metric n'a pas retourne "
            "un ReportMetricResult."
        )

    return payload


def _compact_candidates_before_heading(
    *,
    lines: list[str],
    heading_index: int,
) -> list[
    tuple[
        str,
        ReportMetricResult,
    ]
]:
    """
    Recherche une metrique deja compacte :

        +2.8 / 10

    uniquement AVANT le titre de progression.
    """

    start = max(
        0,
        heading_index
        - _LINES_BEFORE_HEADING,
    )

    candidates = []

    for index in range(
        start,
        heading_index,
    ):

        line = lines[index]

        match = (
            _COMPACT_METRIC_RE
            .fullmatch(line)
        )

        if match is None:
            continue

        payload = _build_payload(
            sign=match.group("sign"),
            number=match.group("number"),
        )

        candidates.append(
            (
                line,
                payload,
            )
        )

    return candidates


def _split_candidates_before_heading(
    *,
    lines: list[str],
    heading_index: int,
) -> list[
    tuple[
        str,
        ReportMetricResult,
    ]
]:
    """
    Recherche la structure Digiforma observee :

        +2.8
        APPRENANTS
        / 10

    Les deux fragments doivent se situer avant le
    titre PROGRESSION DES COMPETENCES.
    """

    start = max(
        0,
        heading_index
        - _LINES_BEFORE_HEADING,
    )

    candidates = []

    for value_index in range(
        start,
        heading_index,
    ):

        value_line = lines[
            value_index
        ]

        value_match = (
            _STANDALONE_SIGNED_VALUE_RE
            .fullmatch(
                value_line
            )
        )

        if value_match is None:
            continue

        denominator_start = (
            value_index + 1
        )

        denominator_end = min(
            heading_index,
            value_index
            + _MAX_DENOMINATOR_DISTANCE
            + 1,
        )

        denominator_matches = []

        for denominator_index in range(
            denominator_start,
            denominator_end,
        ):

            denominator_line = lines[
                denominator_index
            ]

            if (
                _STANDALONE_DENOMINATOR_RE
                .fullmatch(
                    denominator_line
                )
                is not None
            ):
                denominator_matches.append(
                    denominator_line
                )

        # Une seule ligne /10 doit correspondre
        # a cette valeur signee.
        if len(
            denominator_matches
        ) != 1:
            continue

        payload = _build_payload(
            sign=(
                value_match.group(
                    "sign"
                )
            ),
            number=(
                value_match.group(
                    "number"
                )
            ),
        )

        # Conservation des deux fragments source.
        source_text = (
            value_line
            + "\n"
            + denominator_matches[0]
        )

        candidates.append(
            (
                source_text,
                payload,
            )
        )

    return candidates


# =====================================================
# Extraction publique
# =====================================================

def extract_progression_metric_2026(
    pdf_result: PdfReadResult,
) -> ProgressionMetricExtraction2026:
    """
    Extrait uniquement une metrique de progression
    explicitement affichee.

    Regles :

    - le titre PROGRESSION DES COMPETENCES doit exister ;
    - seule la zone precedant immediatement le titre
      est consideree ;
    - la valeur doit porter un signe explicite ;
    - /10 doit etre explicitement present ;
    - aucun calcul entre notes n'est autorise ;
    - aucune valeur n'est choisie en cas d'ambiguite.
    """

    if not isinstance(
        pdf_result,
        PdfReadResult,
    ):
        raise TypeError(
            "pdf_result doit etre un PdfReadResult."
        )

    candidates = []

    for page in pdf_result.pages:

        lines = [
            line.strip()
            for line in page.text.splitlines()
            if line.strip()
        ]

        normalized_lines = [
            _normalize_text(
                line
            )
            for line in lines
        ]

        heading_indexes = [
            index
            for index, line
            in enumerate(
                normalized_lines
            )
            if (
                _TARGET_HEADING
                in line
            )
        ]

        for heading_index in heading_indexes:

            local_candidates = []

            local_candidates.extend(
                _compact_candidates_before_heading(
                    lines=lines,
                    heading_index=(
                        heading_index
                    ),
                )
            )

            local_candidates.extend(
                _split_candidates_before_heading(
                    lines=lines,
                    heading_index=(
                        heading_index
                    ),
                )
            )

            for (
                source_text,
                payload,
            ) in local_candidates:

                candidates.append(
                    (
                        page.number,
                        source_text,
                        payload,
                    )
                )

    # ---------------------------------------------
    # Aucun indicateur fiable
    # ---------------------------------------------

    if not candidates:

        return (
            ProgressionMetricExtraction2026(
                status="not_detected",
                payload=None,
                source_text=None,
                page_number=None,
                issues=(
                    "progression_metric_not_detected",
                ),
            )
        )

    # ---------------------------------------------
    # Dedoublonnage strict
    # ---------------------------------------------

    unique_candidates = []

    seen = set()

    for (
        page_number,
        source_text,
        payload,
    ) in candidates:

        key = (
            page_number,
            source_text,
            payload.value_sur_10,
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        unique_candidates.append(
            (
                page_number,
                source_text,
                payload,
            )
        )

    # ---------------------------------------------
    # Plusieurs candidats distincts :
    # aucun choix arbitraire.
    # ---------------------------------------------

    if len(
        unique_candidates
    ) != 1:

        return (
            ProgressionMetricExtraction2026(
                status="ambiguous",
                payload=None,
                source_text=None,
                page_number=None,
                issues=(
                    "multiple_progression_metrics_detected",
                ),
            )
        )

    (
        page_number,
        source_text,
        payload,
    ) = unique_candidates[0]

    return (
        ProgressionMetricExtraction2026(
            status="success",
            payload=payload,
            source_text=source_text,
            page_number=page_number,
            issues=(),
        )
    )
