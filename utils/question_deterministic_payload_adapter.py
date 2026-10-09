# utils/question_deterministic_payload_adapter.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from utils.distribution_layout_extractor import (
    distribution_1_to_5_payload,
)
from utils.question_deterministic_extractor import (
    DeterministicQuestionExtraction,
)
from utils.mastery_layout_extractor import (
    MasteryLayoutExtraction,
)
from utils.question_extraction_contracts import (
    QuestionExtractionPayload,
)
from utils.question_payload_parser import (
    parse_extraction_payload,
)
from utils.question_registry import (
    DataKind,
)


# =====================================================
# Résultat public
# =====================================================

@dataclass(frozen=True)
class DeterministicTypedPayload:
    """
    Payload déterministe validé selon le type
    réellement détecté dans le document.

    expected_data_kind :
        type prévu par le registre.

    detected_data_kind :
        type réellement rencontré dans le PDF.

    payload :
        contrat Python validé correspondant au
        detected_data_kind.
    """

    expected_data_kind: Optional[
        DataKind
    ]

    detected_data_kind: DataKind

    payload: QuestionExtractionPayload

    method: str

    @property
    def matches_expected_data_kind(
        self,
    ) -> Optional[bool]:

        if self.expected_data_kind is None:
            return None

        return (
            self.expected_data_kind
            == self.detected_data_kind
        )


# =====================================================
# Distribution générique -> dictionnaire brut
# =====================================================

def _generic_distribution_payload(
    extraction: DeterministicQuestionExtraction,
) -> dict:
    """
    Construit un payload JSON-compatible depuis
    les lignes géométriques déjà validées.

    Aucun recalcul :
    - aucun effectif n'est déduit ;
    - aucun pourcentage n'est recalculé ;
    - aucun total n'est inventé.

    nb_votants reste donc None lorsque le PDF
    n'affiche pas explicitement de total.
    """

    distribution = extraction.distribution

    if distribution is None:
        raise ValueError(
            "Aucune distribution dans "
            "l'extraction déterministe."
        )

    return {
        "nb_votants": (
            distribution
            .diagnostics
            .explicit_total
        ),
        "items": [
            {
                "label": row.label,
                "nb_votants": (
                    row.nb_votants
                ),
                "pourcentage": (
                    row.pourcentage
                ),
            }
            for row in distribution.rows
        ],
    }


# =====================================================
# Adaptation selon le type réellement détecté
# =====================================================

def deterministic_extraction_to_typed_payload(
    extraction: DeterministicQuestionExtraction,
) -> DeterministicTypedPayload:
    """
    Transforme une extraction déterministe réussie
    en payload interne typé et validé.

    Important :
    la conversion est pilotée par
    detected_data_kind, jamais par
    expected_data_kind.

    Cela permet notamment :
        registre = distribution_1_5
        PDF réel = distribution_categories

    sans forcer les catégories vers une échelle 1..5.
    """

    if not isinstance(
        extraction,
        DeterministicQuestionExtraction,
    ):
        raise TypeError(
            "extraction doit être un "
            "DeterministicQuestionExtraction."
        )

    if not extraction.succeeded:
        raise ValueError(
            "Impossible d'adapter une extraction "
            "déterministe non réussie : "
            f"{extraction.status!r}."
        )

    detected_data_kind = (
        extraction.detected_data_kind
    )

    if detected_data_kind is None:
        raise ValueError(
            "Une extraction réussie doit fournir "
            "detected_data_kind."
        )

    distribution = extraction.distribution

    if distribution is None:
        raise ValueError(
            "Une extraction de distribution réussie "
            "doit contenir distribution."
        )

    if not distribution.reliable:
        raise ValueError(
            "Une distribution non fiable ne peut "
            "pas être convertie en payload typé."
        )

    # ---------------------------------------------
    # Échelle stricte 1 -> 5
    # ---------------------------------------------

    if detected_data_kind == "distribution_1_5":

        raw_payload = (
            distribution_1_to_5_payload(
                distribution
            )
        )

    # ---------------------------------------------
    # Catégories libres / Oui-Non
    # ---------------------------------------------

    elif detected_data_kind in {
        "distribution_categories",
        "distribution_yes_no",
    }:

        raw_payload = (
            _generic_distribution_payload(
                extraction
            )
        )

    # ---------------------------------------------
    # Type encore non pris en charge
    # ---------------------------------------------

    else:

        raise NotImplementedError(
            "Aucun adaptateur déterministe défini "
            "pour detected_data_kind="
            f"{detected_data_kind!r}."
        )

    # ---------------------------------------------
    # Passage par le parseur commun
    # ---------------------------------------------

    payload = parse_extraction_payload(
        detected_data_kind,
        raw_payload,
    )

    return DeterministicTypedPayload(
        expected_data_kind=(
            extraction.expected_data_kind
        ),
        detected_data_kind=(
            detected_data_kind
        ),
        payload=payload,
        method=extraction.method,
    )


# =====================================================
# Mastery objectives -> typed payload
# =====================================================

def mastery_layout_to_typed_payload(
    extraction: MasteryLayoutExtraction,
    *,
    expected_data_kind: Optional[
        DataKind
    ],
) -> DeterministicTypedPayload:
    """
    Convert a successful deterministic mastery-layout
    extraction into a validated internal typed payload.

    No business value is calculated here.
    """

    if not isinstance(
        extraction,
        MasteryLayoutExtraction,
    ):
        raise TypeError(
            "extraction must be a "
            "MasteryLayoutExtraction."
        )

    if not extraction.succeeded:
        raise ValueError(
            "Cannot adapt an unsuccessful "
            "mastery layout extraction: "
            f"{extraction.status!r}."
        )

    if extraction.raw_payload is None:
        raise ValueError(
            "A successful mastery extraction "
            "must contain raw_payload."
        )

    detected_data_kind: DataKind = (
        "maitrise_objectifs"
    )

    payload = parse_extraction_payload(
        detected_data_kind,
        extraction.raw_payload,
    )

    return DeterministicTypedPayload(
        expected_data_kind=(
            expected_data_kind
        ),
        detected_data_kind=(
            detected_data_kind
        ),
        payload=payload,
        method=extraction.method,
    )
