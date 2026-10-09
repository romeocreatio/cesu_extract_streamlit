# utils/question_extraction_contracts.py

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import (
    Literal,
    Optional,
    Tuple,
    Union,
)

from utils.question_registry import (
    DataKind,
    normalize_question_text,
)


# =====================================================
# Types communs
# =====================================================

Number = Union[int, float]

ScaleLevel = Literal[
    1,
    2,
    3,
    4,
    5,
]

MasteryMode = Literal[
    "4_niveaux",
    "notes_sur_10",
]


# =====================================================
# Distribution 1 -> 5
# =====================================================

@dataclass(frozen=True)
class Distribution1To5Level:
    """
    Une modalité de réponse de l'échelle 1 à 5.

    nb_votants et pourcentage peuvent être absents
    lorsque la source ne permet pas de les déterminer.
    """

    level: ScaleLevel
    nb_votants: Optional[Number]
    pourcentage: Optional[Number]


@dataclass(frozen=True)
class Distribution1To5Result:
    """
    Résultat interne pour data_kind=distribution_1_5.

    Le futur adaptateur JSON 2026 pourra produire :
    - volonte_suivi_formation
    - souhaitez_vous_suivre_distribution

    sans demander au LLM de connaître les colonnes
    ou chemins de sortie.
    """

    nb_votants: Optional[Number]

    levels: Tuple[
        Distribution1To5Level,
        ...
    ]


# =====================================================
# Distribution catégorielle / Oui-Non
# =====================================================

@dataclass(frozen=True)
class DistributionCategoryItem:
    """
    Une modalité d'une distribution catégorielle.

    Le libellé est conservé tel qu'il apparaît
    dans la source.
    """

    label: str

    nb_votants: Optional[Number]
    pourcentage: Optional[Number]


@dataclass(frozen=True)
class DistributionCategoriesResult:
    """
    Distribution comportant des catégories libres.

    Exemple réel 2026 :
        Oui, beaucoup
        Oui, un peu
        Non, pas vraiment
        Non, pas du tout
    """

    nb_votants: Optional[Number]

    items: Tuple[
        DistributionCategoryItem,
        ...
    ]


@dataclass(frozen=True)
class DistributionYesNoResult:
    """
    Distribution strictement binaire Oui / Non.

    Les libellés source sont conservés dans items.
    """

    nb_votants: Optional[Number]

    items: Tuple[
        DistributionCategoryItem,
        ...
    ]



# =====================================================
# Verbatims
# =====================================================

@dataclass(frozen=True)
class VerbatimsResult:
    """
    Verbatims extraits exactement de la source.

    Aucun résumé ni reformulation ne doit être fait.
    Le dédoublonnage lié au chevauchement des chunks
    sera traité plus tard lors de la consolidation.
    """

    items: Tuple[str, ...]


# =====================================================
# Maîtrise des objectifs
# =====================================================

@dataclass(frozen=True)
class MasteryLevelValue:
    """
    Valeurs source associées à UNE modalité
    de maîtrise.

    Exemple réel :

        Totalement 11 4 %

    devient :

        nb_votants = 11
        pourcentage = 4

    Aucune valeur manquante ne doit être
    calculée ou déduite.
    """

    nb_votants: Optional[Number]
    pourcentage: Optional[Number]


@dataclass(frozen=True)
class MasteryLevels:
    """
    Distribution de maîtrise sur les quatre
    modalités Digiforma.

    Chaque modalité conserve séparément :
    - l'effectif explicitement affiché ;
    - le pourcentage explicitement affiché.
    """

    totalement: MasteryLevelValue
    en_partie: MasteryLevelValue
    insuffisamment: MasteryLevelValue
    pas_du_tout: MasteryLevelValue

@dataclass(frozen=True)
class MasteryObjectiveResult:
    """
    Résultat pour un objectif individuel.
    """

    objectif_label: str

    levels: MasteryLevels

    note_sur_10: Optional[Number]


@dataclass(frozen=True)
class MasteryObjectivesResult:
    """
    Résultat interne pour data_kind=maitrise_objectifs.

    Structure alignée sur le schéma 2026 :
    - mode
    - par_objectif
    - note_globale_objectifs_preformation
    """

    mode: Optional[MasteryMode]

    par_objectif: Tuple[
        MasteryObjectiveResult,
        ...
    ]

    note_globale_objectifs_preformation: (
        Optional[Number]
    )


# =====================================================
# Union des résultats actuellement supportés
# =====================================================

QuestionExtractionPayload = Union[
    Distribution1To5Result,
    DistributionCategoriesResult,
    DistributionYesNoResult,
    VerbatimsResult,
    MasteryObjectivesResult,
]


SUPPORTED_DATA_KINDS: Tuple[
    DataKind,
    ...
] = (
    "distribution_1_5",
    "distribution_categories",
    "distribution_yes_no",
    "verbatims",
    "maitrise_objectifs",
)


# =====================================================
# Helpers numériques
# =====================================================

def _is_number(
    value: object,
) -> bool:
    """
    bool est volontairement refusé même s'il hérite
    de int en Python.
    """

    return (
        isinstance(
            value,
            (int, float),
        )
        and not isinstance(
            value,
            bool,
        )
    )


def _validate_optional_number(
    value: Optional[Number],
    field_name: str,
    *,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
) -> None:
    """
    Validation générique des valeurs numériques.
    """

    if value is None:
        return

    if not _is_number(value):
        raise TypeError(
            f"{field_name} doit être numérique "
            "ou None."
        )

    numeric = float(value)

    if not math.isfinite(numeric):
        raise ValueError(
            f"{field_name} doit être fini."
        )

    if (
        minimum is not None
        and numeric < minimum
    ):
        raise ValueError(
            f"{field_name} doit être >= "
            f"{minimum}."
        )

    if (
        maximum is not None
        and numeric > maximum
    ):
        raise ValueError(
            f"{field_name} doit être <= "
            f"{maximum}."
        )


# =====================================================
# Validation distribution 1 -> 5
# =====================================================

def validate_distribution_1_to_5(
    result: Distribution1To5Result,
) -> None:
    """
    Contrôle le contrat de distribution.

    Les cinq niveaux doivent exister exactement
    une fois chacun.
    """

    _validate_optional_number(
        result.nb_votants,
        "nb_votants",
        minimum=0,
    )

    if len(result.levels) != 5:
        raise ValueError(
            "Une distribution 1-5 doit contenir "
            "exactement 5 niveaux."
        )

    actual_levels = [
        level.level
        for level in result.levels
    ]

    if actual_levels != [
        1,
        2,
        3,
        4,
        5,
    ]:
        raise ValueError(
            "Les niveaux doivent être ordonnés "
            "exactement [1, 2, 3, 4, 5]. "
            f"Reçu : {actual_levels}"
        )

    for level in result.levels:

        _validate_optional_number(
            level.nb_votants,
            (
                f"level_{level.level}."
                "nb_votants"
            ),
            minimum=0,
        )

        _validate_optional_number(
            level.pourcentage,
            (
                f"level_{level.level}."
                "pourcentage"
            ),
            minimum=0,
            maximum=100,
        )


# =====================================================
# Validation distributions catégorielles
# =====================================================

def _validate_distribution_items(
    items: Tuple[
        DistributionCategoryItem,
        ...
    ],
    *,
    field_name: str,
) -> None:
    """
    Validation commune des modalités catégorielles.

    Aucun recalcul de pourcentage ou d'effectif.
    """

    if len(items) < 2:
        raise ValueError(
            f"{field_name} doit contenir "
            "au moins deux modalités."
        )

    normalized_labels = []

    for index, item in enumerate(
        items,
        start=1,
    ):

        if not isinstance(
            item.label,
            str,
        ):
            raise TypeError(
                f"{field_name}.items[{index}]."
                "label doit être une chaîne."
            )

        if not item.label.strip():
            raise ValueError(
                f"{field_name}.items[{index}]."
                "label est vide."
            )

        normalized_labels.append(
            normalize_question_text(
                item.label
            )
        )

        _validate_optional_number(
            item.nb_votants,
            (
                f"{field_name}.items[{index}]."
                "nb_votants"
            ),
            minimum=0,
        )

        _validate_optional_number(
            item.pourcentage,
            (
                f"{field_name}.items[{index}]."
                "pourcentage"
            ),
            minimum=0,
            maximum=100,
        )

    if (
        len(set(normalized_labels))
        != len(normalized_labels)
    ):
        raise ValueError(
            f"{field_name} contient "
            "des libellés dupliqués."
        )


def validate_distribution_categories(
    result: DistributionCategoriesResult,
) -> None:
    """
    Validation structurelle d'une distribution
    catégorielle libre.
    """

    _validate_optional_number(
        result.nb_votants,
        "distribution_categories.nb_votants",
        minimum=0,
    )

    _validate_distribution_items(
        result.items,
        field_name="distribution_categories",
    )


def validate_distribution_yes_no(
    result: DistributionYesNoResult,
) -> None:
    """
    Validation d'une distribution strictement
    composée de Oui et Non.
    """

    _validate_optional_number(
        result.nb_votants,
        "distribution_yes_no.nb_votants",
        minimum=0,
    )

    _validate_distribution_items(
        result.items,
        field_name="distribution_yes_no",
    )

    normalized_labels = {
        normalize_question_text(
            item.label
        )
        for item in result.items
    }

    if normalized_labels != {
        "oui",
        "non",
    }:
        raise ValueError(
            "distribution_yes_no doit contenir "
            "exactement les modalités Oui et Non."
        )



# =====================================================
# Validation verbatims
# =====================================================

def validate_verbatims(
    result: VerbatimsResult,
) -> None:
    """
    Les verbatims doivent rester des chaînes
    non vides.

    Aucun nettoyage du contenu n'est effectué ici.
    """

    for index, item in enumerate(
        result.items,
        start=1,
    ):

        if not isinstance(item, str):
            raise TypeError(
                "Verbatim "
                f"{index} doit être une chaîne."
            )

        if not item.strip():
            raise ValueError(
                "Verbatim "
                f"{index} est vide."
            )


# =====================================================
# Validation maîtrise des objectifs
# =====================================================

def _validate_mastery_level_value(
    value: MasteryLevelValue,
    field_name: str,
) -> None:
    """
    Valide une modalité de maîtrise sans
    calculer ni compléter aucune donnée.
    """

    if not isinstance(
        value,
        MasteryLevelValue,
    ):
        raise TypeError(
            f"{field_name} doit être "
            "un MasteryLevelValue."
        )

    _validate_optional_number(
        value.nb_votants,
        f"{field_name}.nb_votants",
        minimum=0,
    )

    _validate_optional_number(
        value.pourcentage,
        f"{field_name}.pourcentage",
        minimum=0,
        maximum=100,
    )


def validate_mastery_objectives(
    result: MasteryObjectivesResult,
) -> None:
    """
    Validation du contrat de maîtrise.

    Pour chaque objectif, les effectifs et
    pourcentages des quatre modalités sont
    conservés séparément.
    """

    if result.mode not in (
        None,
        "4_niveaux",
        "notes_sur_10",
    ):
        raise ValueError(
            "mode invalide pour "
            "maitrise_objectifs."
        )

    _validate_optional_number(
        result.note_globale_objectifs_preformation,
        (
            "note_globale_"
            "objectifs_preformation"
        ),
        minimum=0,
        maximum=10,
    )

    for index, objective in enumerate(
        result.par_objectif,
        start=1,
    ):

        if not isinstance(
            objective.objectif_label,
            str,
        ):
            raise TypeError(
                "objectif_label doit être "
                "une chaîne."
            )

        if not objective.objectif_label.strip():
            raise ValueError(
                "objectif_label vide pour "
                f"l'objectif {index}."
            )

        _validate_mastery_level_value(
            objective.levels.totalement,
            f"objectif_{index}.levels.totalement",
        )

        _validate_mastery_level_value(
            objective.levels.en_partie,
            f"objectif_{index}.levels.en_partie",
        )

        _validate_mastery_level_value(
            objective.levels.insuffisamment,
            f"objectif_{index}.levels.insuffisamment",
        )

        _validate_mastery_level_value(
            objective.levels.pas_du_tout,
            f"objectif_{index}.levels.pas_du_tout",
        )

        _validate_optional_number(
            objective.note_sur_10,
            (
                f"objectif_{index}."
                "note_sur_10"
            ),
            minimum=0,
            maximum=10,
        )

# =====================================================
# Validation selon data_kind
# =====================================================

def validate_extraction_payload(
    data_kind: DataKind,
    payload: QuestionExtractionPayload,
) -> None:
    """
    Vérifie que le résultat correspond bien
    au data_kind demandé.

    Pour l'instant seuls les trois contrats
    nécessaires à la préformation 2026 sont
    implémentés.
    """

    if data_kind == "distribution_1_5":

        if not isinstance(
            payload,
            Distribution1To5Result,
        ):
            raise TypeError(
                "distribution_1_5 attend "
                "Distribution1To5Result."
            )

        validate_distribution_1_to_5(
            payload
        )

        return

    if data_kind == "distribution_categories":

        if not isinstance(
            payload,
            DistributionCategoriesResult,
        ):
            raise TypeError(
                "distribution_categories attend "
                "DistributionCategoriesResult."
            )

        validate_distribution_categories(
            payload
        )

        return

    if data_kind == "distribution_yes_no":

        if not isinstance(
            payload,
            DistributionYesNoResult,
        ):
            raise TypeError(
                "distribution_yes_no attend "
                "DistributionYesNoResult."
            )

        validate_distribution_yes_no(
            payload
        )

        return

    if data_kind == "verbatims":

        if not isinstance(
            payload,
            VerbatimsResult,
        ):
            raise TypeError(
                "verbatims attend "
                "VerbatimsResult."
            )

        validate_verbatims(
            payload
        )

        return

    if data_kind == "maitrise_objectifs":

        if not isinstance(
            payload,
            MasteryObjectivesResult,
        ):
            raise TypeError(
                "maitrise_objectifs attend "
                "MasteryObjectivesResult."
            )

        validate_mastery_objectives(
            payload
        )

        return

    raise NotImplementedError(
        "Aucun contrat d'extraction n'est "
        "encore défini pour data_kind="
        f"{data_kind!r}."
    )
