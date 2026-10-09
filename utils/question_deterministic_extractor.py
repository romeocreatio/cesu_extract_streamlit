# utils/question_deterministic_extractor.py

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Literal,
    Optional,
    Tuple,
)

from utils.distribution_layout_extractor import (
    DistributionLayoutResult,
    classify_distribution,
    distribution_1_to_5_payload,
    normalize_layout_text,
    parse_distribution_lines,
)
from utils.question_layout_context import (
    QuestionLayoutContext,
)
from utils.question_registry import (
    DataKind,
)


# =====================================================
# Types
# =====================================================

DeterministicStatus = Literal[
    "success",
    "not_applicable",
    "not_detected",
    "unreliable",
    "unsupported_shape",
]

DistributionShape = Literal[
    "numeric_scale",
    "yes_no",
    "categorical",
    "unresolved",
]


DISTRIBUTION_DATA_KINDS = frozenset(
    {
        "distribution_1_5",
        "distribution_yes_no",
        "distribution_categories",
    }
)


# =====================================================
# Résultat public
# =====================================================

@dataclass(frozen=True)
class DeterministicQuestionExtraction:
    """
    Résultat d'une tentative d'extraction déterministe.

    expected_data_kind :
        type prévu par le registre métier.

    detected_data_kind :
        type réellement reconnu dans le PDF.

    Les deux sont volontairement distincts.

    Exemple réel 2026 :
        expected = distribution_1_5
        detected = distribution_categories

    pour Hémoc-DIV.

    Aucun résultat n'est forcé pour correspondre
    artificiellement au registre.
    """

    status: DeterministicStatus

    expected_data_kind: Optional[
        DataKind
    ]

    detected_data_kind: Optional[
        DataKind
    ]

    detected_shape: Optional[
        DistributionShape
    ]

    distribution: Optional[
        DistributionLayoutResult
    ]

    issues: Tuple[
        str,
        ...
    ] = ()

    method: str = "pymupdf_layout"

    @property
    def succeeded(self) -> bool:
        return self.status == "success"

    @property
    def should_fallback(self) -> bool:
        """
        Un fallback externe pourra être tenté
        lorsque le déterministe n'a pas produit
        un résultat exploitable.
        """

        return not self.succeeded

    @property
    def matches_expected_data_kind(
        self,
    ) -> Optional[bool]:
        """
        None :
            comparaison impossible.

        True :
            la forme détectée correspond au registre.

        False :
            le PDF contient une autre forme réelle.
        """

        if (
            self.expected_data_kind
            is None
            or self.detected_data_kind
            is None
        ):
            return None

        return (
            self.expected_data_kind
            == self.detected_data_kind
        )


# =====================================================
# Helpers
# =====================================================

def _result(
    *,
    status: DeterministicStatus,
    expected_data_kind: Optional[
        DataKind
    ],
    detected_data_kind: Optional[
        DataKind
    ] = None,
    detected_shape: Optional[
        DistributionShape
    ] = None,
    distribution: Optional[
        DistributionLayoutResult
    ] = None,
    issues: Tuple[
        str,
        ...
    ] = (),
) -> DeterministicQuestionExtraction:
    return DeterministicQuestionExtraction(
        status=status,
        expected_data_kind=(
            expected_data_kind
        ),
        detected_data_kind=(
            detected_data_kind
        ),
        detected_shape=(
            detected_shape
        ),
        distribution=distribution,
        issues=issues,
    )


def _normalized_labels(
    distribution: DistributionLayoutResult,
) -> Tuple[
    str,
    ...
]:
    return tuple(
        normalize_layout_text(
            row.label
        )
        for row in distribution.rows
    )


# =====================================================
# Validation échelle 1 -> 5
# =====================================================

def _is_distribution_1_to_5(
    distribution: DistributionLayoutResult,
) -> bool:
    """
    Utilise l'adaptateur 1->5 existant comme
    validation stricte de la structure.

    Aucun calcul n'est effectué.
    """

    try:
        distribution_1_to_5_payload(
            distribution
        )

    except (
        TypeError,
        ValueError,
    ):
        return False

    return True


# =====================================================
# Validation oui / non
# =====================================================

def _is_yes_no_distribution(
    distribution: DistributionLayoutResult,
) -> bool:
    """
    Une distribution Oui/Non doit contenir
    exactement les deux modalités.

    Une seule modalité n'est pas considérée
    suffisamment sûre pour une extraction
    déterministe.
    """

    labels = _normalized_labels(
        distribution
    )

    return (
        len(labels) == 2
        and set(labels)
        == {
            "oui",
            "non",
        }
    )


# =====================================================
# Détermination du type réel
# =====================================================

def _detect_distribution_data_kind(
    distribution: DistributionLayoutResult,
    shape: DistributionShape,
) -> Optional[
    DataKind
]:
    """
    Transforme la forme géométrique reconnue
    en data_kind métier lorsqu'on peut le faire
    sans ambiguïté.
    """

    if shape == "numeric_scale":

        if _is_distribution_1_to_5(
            distribution
        ):
            return "distribution_1_5"

        return None

    if shape == "yes_no":

        if _is_yes_no_distribution(
            distribution
        ):
            return "distribution_yes_no"

        return None

    if shape == "categorical":

        if len(
            distribution.rows
        ) >= 2:
            return "distribution_categories"

        return None

    return None


# =====================================================
# Extraction déterministe
# =====================================================

def extract_question_deterministically(
    context: QuestionLayoutContext,
    *,
    expected_data_kind: Optional[
        DataKind
    ] = None,
) -> DeterministicQuestionExtraction:
    """
    Tente une extraction locale sans LLM.

    Pour l'instant cette brique prend en charge
    uniquement les questions de type distribution.

    Important :
    expected_data_kind décrit le registre.
    detected_data_kind décrit ce qui est réellement
    présent dans le document.

    Une différence entre les deux n'est PAS masquée.
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
        return _result(
            status="not_detected",
            expected_data_kind=(
                expected_data_kind
            ),
            issues=(
                "empty_layout_context",
            ),
        )

    # ---------------------------------------------
    # Si le registre demande explicitement
    # autre chose qu'une distribution,
    # ce moteur n'est pas encore applicable.
    # ---------------------------------------------

    if (
        expected_data_kind is not None
        and expected_data_kind
        not in DISTRIBUTION_DATA_KINDS
    ):
        return _result(
            status="not_applicable",
            expected_data_kind=(
                expected_data_kind
            ),
            issues=(
                "data_kind_not_supported_"
                "by_deterministic_extractor",
            ),
        )

    # ---------------------------------------------
    # Parsing géométrique générique
    # ---------------------------------------------

    distribution = (
        parse_distribution_lines(
            context.lines
        )
    )

    if not distribution.rows:
        return _result(
            status="not_detected",
            expected_data_kind=(
                expected_data_kind
            ),
            distribution=distribution,
            issues=(
                "no_distribution_rows",
            ),
        )

    # ---------------------------------------------
    # Fiabilité
    # ---------------------------------------------

    if not distribution.reliable:
        return _result(
            status="unreliable",
            expected_data_kind=(
                expected_data_kind
            ),
            distribution=distribution,
            issues=(
                distribution
                .diagnostics
                .issues
            ),
        )

    # ---------------------------------------------
    # Classification de la forme
    # ---------------------------------------------

    shape = classify_distribution(
        distribution
    )

    if shape not in (
        "numeric_scale",
        "yes_no",
        "categorical",
        "unresolved",
    ):
        return _result(
            status="unsupported_shape",
            expected_data_kind=(
                expected_data_kind
            ),
            distribution=distribution,
            issues=(
                "unknown_distribution_shape",
            ),
        )

    detected_data_kind = (
        _detect_distribution_data_kind(
            distribution,
            shape,
        )
    )

    # ---------------------------------------------
    # Forme reconnue mais contrat déterministe
    # encore insuffisant
    # ---------------------------------------------

    if detected_data_kind is None:
        return _result(
            status="unsupported_shape",
            expected_data_kind=(
                expected_data_kind
            ),
            detected_shape=shape,
            distribution=distribution,
            issues=(
                "distribution_shape_not_"
                "supported_safely",
            ),
        )

    # ---------------------------------------------
    # Succès
    # ---------------------------------------------

    return _result(
        status="success",
        expected_data_kind=(
            expected_data_kind
        ),
        detected_data_kind=(
            detected_data_kind
        ),
        detected_shape=shape,
        distribution=distribution,
        issues=(),
    )
