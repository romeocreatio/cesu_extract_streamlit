# utils/score_layout_extractor.py

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import (
    Literal,
    Optional,
    Tuple,
)

from utils.question_layout_context import (
    QuestionLayoutContext,
)


ScoreStatus = Literal[
    "success",
    "not_detected",
    "unreliable",
]


_NUMBER_RE = re.compile(
    r"^\d+(?:[.,]\d+)?$"
)


@dataclass(frozen=True)
class ScoreLayoutExtraction:
    """
    Extraction déterministe d'une note affichée
    sous la forme graphique :

        9.4
         /
        10

    La relation géométrique avec '/ 10' permet
    d'éviter de confondre la note avec le texte
    '0 à 10' présent dans la question.
    """

    status: ScoreStatus

    note_sur_10: Optional[
        float | int
    ]

    issues: Tuple[
        str,
        ...,
    ] = ()

    method: str = (
        "pymupdf_score_fraction_layout"
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
            "note_sur_10": self.note_sur_10,
        }


def _parse_number(
    text: str,
) -> Optional[
    float | int
]:
    value = text.strip()

    if not _NUMBER_RE.fullmatch(
        value
    ):
        return None

    number = float(
        value.replace(",", ".")
    )

    if number.is_integer():
        return int(number)

    return number


def extract_score_layout(
    context: QuestionLayoutContext,
) -> ScoreLayoutExtraction:
    """
    Recherche une structure verticale fiable :

        numérateur
            /
        dénominateur 10

    Contraintes :
    - même page ;
    - numérateur entre 0 et 10 ;
    - numérateur immédiatement au-dessus du slash ;
    - dénominateur 10 sous le slash ;
    - les trois éléments sont dans la même zone
      horizontale.

    Aucun score n'est calculé ou reconstruit.
    """

    if not isinstance(
        context,
        QuestionLayoutContext,
    ):
        raise TypeError(
            "context doit être un "
            "QuestionLayoutContext."
        )

    candidates = []

    for slash_line in context.lines:

        slash_words = [
            word
            for word in slash_line.words
            if word.text.strip() == "/"
        ]

        for slash_word in slash_words:

            # -------------------------------------
            # Numérateur :
            # juste au-dessus du slash.
            # -------------------------------------

            numerator_candidates = []

            for line in context.lines:

                if (
                    line.page_number
                    != slash_line.page_number
                ):
                    continue

                y_gap = (
                    slash_line.y
                    - line.y
                )

                if (
                    y_gap < 0
                    or y_gap > 10
                ):
                    continue

                for word in line.words:

                    number = _parse_number(
                        word.text
                    )

                    if number is None:
                        continue

                    if not (
                        0 <= float(number) <= 10
                    ):
                        continue

                    x_gap = abs(
                        word.x0
                        - slash_word.x0
                    )

                    if x_gap > 45:
                        continue

                    numerator_candidates.append(
                        (
                            y_gap,
                            x_gap,
                            word,
                            number,
                        )
                    )

            if not numerator_candidates:
                continue

            numerator_candidates.sort(
                key=lambda item: (
                    item[0],
                    item[1],
                )
            )

            (
                _,
                _,
                numerator_word,
                numerator_value,
            ) = numerator_candidates[0]

            # -------------------------------------
            # Dénominateur :
            # "10" sous le slash et aligné.
            # -------------------------------------

            denominator_candidates = []

            for line in context.lines:

                if (
                    line.page_number
                    != slash_line.page_number
                ):
                    continue

                y_gap = (
                    line.y
                    - slash_line.y
                )

                if (
                    y_gap <= 0
                    or y_gap > 30
                ):
                    continue

                for word in line.words:

                    if word.text.strip() != "10":
                        continue

                    slash_x_gap = abs(
                        word.x0
                        - slash_word.x0
                    )

                    numerator_x_gap = abs(
                        word.x0
                        - numerator_word.x0
                    )

                    if slash_x_gap > 45:
                        continue

                    if numerator_x_gap > 20:
                        continue

                    denominator_candidates.append(
                        (
                            y_gap,
                            slash_x_gap,
                            numerator_x_gap,
                            word,
                        )
                    )

            if not denominator_candidates:
                continue

            denominator_candidates.sort(
                key=lambda item: (
                    item[0],
                    item[1],
                    item[2],
                )
            )

            denominator_word = (
                denominator_candidates[0][3]
            )

            candidates.append(
                (
                    numerator_value,
                    slash_line.page_number,
                    numerator_word.x0,
                    numerator_word.y0,
                    slash_word.x0,
                    slash_word.y0,
                    denominator_word.x0,
                    denominator_word.y0,
                )
            )

    # ---------------------------------------------
    # Aucun triplet fiable
    # ---------------------------------------------

    if not candidates:
        return ScoreLayoutExtraction(
            status="not_detected",
            note_sur_10=None,
            issues=(
                "score_fraction_not_found",
            ),
        )

    # ---------------------------------------------
    # Plusieurs triplets différents :
    # ne rien deviner.
    # ---------------------------------------------

    unique_values = {
        candidate[0]
        for candidate in candidates
    }

    if len(unique_values) != 1:
        return ScoreLayoutExtraction(
            status="unreliable",
            note_sur_10=None,
            issues=(
                "multiple_score_values_detected",
            ),
        )

    return ScoreLayoutExtraction(
        status="success",
        note_sur_10=candidates[0][0],
        issues=(),
    )
