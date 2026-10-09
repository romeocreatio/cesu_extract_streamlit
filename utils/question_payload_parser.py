# utils/question_payload_parser.py

from __future__ import annotations

from typing import (
    Any,
    Mapping,
    Optional,
    Sequence,
)

from utils.question_extraction_contracts import (
    Distribution1To5Level,
    Distribution1To5Result,
    DistributionCategoriesResult,
    DistributionCategoryItem,
    DistributionYesNoResult,
    MasteryLevelValue,
    MasteryLevels,
    MasteryObjectiveResult,
    MasteryObjectivesResult,
    Number,
    QuestionExtractionPayload,
    VerbatimsResult,
    validate_extraction_payload,
)
from utils.question_registry import DataKind


# =====================================================
# Helpers génériques
# =====================================================

def _require_mapping(
    value: object,
    field_name: str,
) -> Mapping[str, Any]:
    """
    Vérifie qu'une valeur JSON est un objet.
    """

    if not isinstance(
        value,
        Mapping,
    ):
        raise TypeError(
            f"{field_name} doit être "
            "un objet JSON."
        )

    return value


def _require_sequence(
    value: object,
    field_name: str,
) -> Sequence[Any]:
    """
    Vérifie qu'une valeur JSON est une liste.

    Les chaînes sont explicitement refusées.
    """

    if (
        not isinstance(
            value,
            Sequence,
        )
        or isinstance(
            value,
            (
                str,
                bytes,
                bytearray,
            ),
        )
    ):
        raise TypeError(
            f"{field_name} doit être "
            "une liste JSON."
        )

    return value


def _require_exact_keys(
    obj: Mapping[str, Any],
    *,
    required: set[str],
    optional: set[str],
    field_name: str,
) -> None:
    """
    Refuse les clés absentes et les clés inconnues.

    But :
    éviter qu'une dérive du LLM passe
    silencieusement dans le pipeline.
    """

    actual = set(
        obj.keys()
    )

    missing = (
        required
        - actual
    )

    extra = (
        actual
        - required
        - optional
    )

    if missing:
        raise ValueError(
            f"{field_name} : "
            "clés manquantes : "
            f"{sorted(missing)}"
        )

    if extra:
        raise ValueError(
            f"{field_name} : "
            "clés inattendues : "
            f"{sorted(extra)}"
        )


# =====================================================
# Conversion numérique stricte
# =====================================================

def _parse_optional_number(
    value: object,
    field_name: str,
    *,
    allow_percent_suffix: bool = False,
) -> Optional[Number]:
    """
    Convertit uniquement une valeur censée être
    numérique.

    Accepte :
    - int
    - float
    - "8"
    - "8.5"
    - "8,5"
    - éventuellement "72.5%" / "72,5%"

    Refuse :
    - bool
    - texte libre
    - chaîne vide

    Aucune conversion n'est appliquée aux verbatims.
    """

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        raise TypeError(
            f"{field_name} ne doit pas "
            "être un booléen."
        )

    if isinstance(
        value,
        (int, float),
    ):
        return value

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{field_name} doit être "
            "numérique ou None."
        )

    numeric_text = (
        value.strip()
    )

    if not numeric_text:
        raise ValueError(
            f"{field_name} est vide."
        )

    if numeric_text.endswith("%"):

        if not allow_percent_suffix:
            raise ValueError(
                f"{field_name} ne doit pas "
                "contenir de signe %."
            )

        numeric_text = (
            numeric_text[:-1]
            .strip()
        )

    numeric_text = (
        numeric_text.replace(
            ",",
            ".",
        )
    )

    try:
        number = float(
            numeric_text
        )

    except ValueError as exc:
        raise ValueError(
            f"{field_name} n'est pas "
            f"numérique : {value!r}"
        ) from exc

    # Conserver les entiers sous forme int
    # lorsqu'il n'y a aucune partie décimale.
    if number.is_integer():
        return int(number)

    return number


# =====================================================
# Distribution 1 -> 5
# =====================================================

def _parse_distribution_1_to_5(
    raw: object,
) -> Distribution1To5Result:

    obj = _require_mapping(
        raw,
        "distribution_1_5",
    )

    _require_exact_keys(
        obj,
        required={
            "nb_votants",
            "levels",
        },
        optional=set(),
        field_name=(
            "distribution_1_5"
        ),
    )

    levels_raw = (
        _require_sequence(
            obj["levels"],
            "distribution_1_5.levels",
        )
    )

    levels = []

    for index, level_raw in enumerate(
        levels_raw,
        start=1,
    ):

        level_obj = (
            _require_mapping(
                level_raw,
                (
                    "distribution_1_5."
                    f"levels[{index}]"
                ),
            )
        )

        _require_exact_keys(
            level_obj,
            required={
                "level",
                "nb_votants",
                "pourcentage",
            },
            optional=set(),
            field_name=(
                "distribution_1_5."
                f"levels[{index}]"
            ),
        )

        level_value = (
            _parse_optional_number(
                level_obj["level"],
                (
                    "distribution_1_5."
                    f"levels[{index}].level"
                ),
            )
        )

        if level_value not in (
            1,
            2,
            3,
            4,
            5,
        ):
            raise ValueError(
                "Niveau invalide dans "
                "distribution_1_5 : "
                f"{level_value!r}"
            )

        levels.append(
            Distribution1To5Level(
                level=level_value,
                nb_votants=(
                    _parse_optional_number(
                        level_obj[
                            "nb_votants"
                        ],
                        (
                            "distribution_1_5."
                            f"levels[{index}]."
                            "nb_votants"
                        ),
                    )
                ),
                pourcentage=(
                    _parse_optional_number(
                        level_obj[
                            "pourcentage"
                        ],
                        (
                            "distribution_1_5."
                            f"levels[{index}]."
                            "pourcentage"
                        ),
                        allow_percent_suffix=True,
                    )
                ),
            )
        )

    result = Distribution1To5Result(
        nb_votants=(
            _parse_optional_number(
                obj["nb_votants"],
                (
                    "distribution_1_5."
                    "nb_votants"
                ),
            )
        ),
        levels=tuple(
            levels
        ),
    )

    validate_extraction_payload(
        "distribution_1_5",
        result,
    )

    return result


# =====================================================
# Distribution catégorielle / Oui-Non
# =====================================================

def _parse_distribution_items(
    raw: object,
    *,
    field_name: str,
) -> tuple[
    DistributionCategoryItem,
    ...
]:
    """
    Parse les modalités d'une distribution
    catégorielle sans modifier les libellés source.
    """

    items_raw = _require_sequence(
        raw,
        f"{field_name}.items",
    )

    items = []

    for index, item_raw in enumerate(
        items_raw,
        start=1,
    ):

        item_field = (
            f"{field_name}.items[{index}]"
        )

        item_obj = _require_mapping(
            item_raw,
            item_field,
        )

        _require_exact_keys(
            item_obj,
            required={
                "label",
                "nb_votants",
                "pourcentage",
            },
            optional=set(),
            field_name=item_field,
        )

        label = item_obj["label"]

        if not isinstance(
            label,
            str,
        ):
            raise TypeError(
                f"{item_field}.label doit "
                "être une chaîne."
            )

        # IMPORTANT :
        # le libellé source est conservé
        # strictement tel qu'il est reçu.
        items.append(
            DistributionCategoryItem(
                label=label,
                nb_votants=(
                    _parse_optional_number(
                        item_obj[
                            "nb_votants"
                        ],
                        (
                            f"{item_field}."
                            "nb_votants"
                        ),
                    )
                ),
                pourcentage=(
                    _parse_optional_number(
                        item_obj[
                            "pourcentage"
                        ],
                        (
                            f"{item_field}."
                            "pourcentage"
                        ),
                        allow_percent_suffix=True,
                    )
                ),
            )
        )

    return tuple(items)


def _parse_distribution_categories(
    raw: object,
) -> DistributionCategoriesResult:
    """
    Parse une distribution à catégories libres.
    """

    field_name = (
        "distribution_categories"
    )

    obj = _require_mapping(
        raw,
        field_name,
    )

    _require_exact_keys(
        obj,
        required={
            "nb_votants",
            "items",
        },
        optional=set(),
        field_name=field_name,
    )

    result = DistributionCategoriesResult(
        nb_votants=(
            _parse_optional_number(
                obj["nb_votants"],
                (
                    "distribution_categories."
                    "nb_votants"
                ),
            )
        ),
        items=(
            _parse_distribution_items(
                obj["items"],
                field_name=field_name,
            )
        ),
    )

    validate_extraction_payload(
        "distribution_categories",
        result,
    )

    return result


def _parse_distribution_yes_no(
    raw: object,
) -> DistributionYesNoResult:
    """
    Parse une distribution strictement Oui / Non.

    La validation finale décide si les deux
    modalités correspondent réellement à Oui et Non.
    """

    field_name = (
        "distribution_yes_no"
    )

    obj = _require_mapping(
        raw,
        field_name,
    )

    _require_exact_keys(
        obj,
        required={
            "nb_votants",
            "items",
        },
        optional=set(),
        field_name=field_name,
    )

    result = DistributionYesNoResult(
        nb_votants=(
            _parse_optional_number(
                obj["nb_votants"],
                (
                    "distribution_yes_no."
                    "nb_votants"
                ),
            )
        ),
        items=(
            _parse_distribution_items(
                obj["items"],
                field_name=field_name,
            )
        ),
    )

    validate_extraction_payload(
        "distribution_yes_no",
        result,
    )

    return result



# =====================================================
# Verbatims
# =====================================================

def _parse_verbatims(
    raw: object,
) -> VerbatimsResult:

    obj = _require_mapping(
        raw,
        "verbatims",
    )

    _require_exact_keys(
        obj,
        required={
            "items",
        },
        optional=set(),
        field_name="verbatims",
    )

    items_raw = (
        _require_sequence(
            obj["items"],
            "verbatims.items",
        )
    )

    items = []

    for index, item in enumerate(
        items_raw,
        start=1,
    ):

        if not isinstance(
            item,
            str,
        ):
            raise TypeError(
                "verbatims.items"
                f"[{index}] doit être "
                "une chaîne."
            )

        # IMPORTANT :
        # aucune strip(), reformulation,
        # normalisation ou correction.
        items.append(
            item
        )

    result = VerbatimsResult(
        items=tuple(
            items
        )
    )

    validate_extraction_payload(
        "verbatims",
        result,
    )

    return result


# =====================================================
# Maîtrise des objectifs
# =====================================================

def _parse_mastery_level_value(
    raw: object,
    *,
    field_name: str,
) -> MasteryLevelValue:

    obj = _require_mapping(
        raw,
        field_name,
    )

    _require_exact_keys(
        obj,
        required={
            "nb_votants",
            "pourcentage",
        },
        optional=set(),
        field_name=field_name,
    )

    return MasteryLevelValue(
        nb_votants=(
            _parse_optional_number(
                obj["nb_votants"],
                f"{field_name}.nb_votants",
            )
        ),
        pourcentage=(
            _parse_optional_number(
                obj["pourcentage"],
                f"{field_name}.pourcentage",
                allow_percent_suffix=True,
            )
        ),
    )


def _parse_mastery_levels(
    raw: object,
    *,
    field_name: str,
) -> MasteryLevels:

    obj = _require_mapping(
        raw,
        field_name,
    )

    _require_exact_keys(
        obj,
        required={
            "totalement",
            "en_partie",
            "insuffisamment",
            "pas_du_tout",
        },
        optional=set(),
        field_name=field_name,
    )

    return MasteryLevels(
        totalement=(
            _parse_mastery_level_value(
                obj["totalement"],
                field_name=(
                    f"{field_name}.totalement"
                ),
            )
        ),
        en_partie=(
            _parse_mastery_level_value(
                obj["en_partie"],
                field_name=(
                    f"{field_name}.en_partie"
                ),
            )
        ),
        insuffisamment=(
            _parse_mastery_level_value(
                obj["insuffisamment"],
                field_name=(
                    f"{field_name}.insuffisamment"
                ),
            )
        ),
        pas_du_tout=(
            _parse_mastery_level_value(
                obj["pas_du_tout"],
                field_name=(
                    f"{field_name}.pas_du_tout"
                ),
            )
        ),
    )

def _parse_mastery_objectives(
    raw: object,
) -> MasteryObjectivesResult:

    obj = _require_mapping(
        raw,
        "maitrise_objectifs",
    )

    _require_exact_keys(
        obj,
        required={
            "mode",
            "par_objectif",
            (
                "note_globale_"
                "objectifs_preformation"
            ),
        },
        optional=set(),
        field_name=(
            "maitrise_objectifs"
        ),
    )

    mode = obj["mode"]

    if mode not in (
        None,
        "4_niveaux",
        "notes_sur_10",
    ):
        raise ValueError(
            "maitrise_objectifs.mode "
            f"invalide : {mode!r}"
        )

    objectives_raw = (
        _require_sequence(
            obj["par_objectif"],
            (
                "maitrise_objectifs."
                "par_objectif"
            ),
        )
    )

    objectives = []

    for index, objective_raw in enumerate(
        objectives_raw,
        start=1,
    ):

        field_name = (
            "maitrise_objectifs."
            f"par_objectif[{index}]"
        )

        objective_obj = (
            _require_mapping(
                objective_raw,
                field_name,
            )
        )

        _require_exact_keys(
            objective_obj,
            required={
                "objectif_label",
                "levels",
                "note_sur_10",
            },
            optional=set(),
            field_name=field_name,
        )

        objectif_label = (
            objective_obj[
                "objectif_label"
            ]
        )

        if not isinstance(
            objectif_label,
            str,
        ):
            raise TypeError(
                f"{field_name}."
                "objectif_label doit être "
                "une chaîne."
            )

        objectives.append(
            MasteryObjectiveResult(
                # Texte conservé tel quel.
                objectif_label=(
                    objectif_label
                ),
                levels=(
                    _parse_mastery_levels(
                        objective_obj[
                            "levels"
                        ],
                        field_name=(
                            f"{field_name}."
                            "levels"
                        ),
                    )
                ),
                note_sur_10=(
                    _parse_optional_number(
                        objective_obj[
                            "note_sur_10"
                        ],
                        (
                            f"{field_name}."
                            "note_sur_10"
                        ),
                    )
                ),
            )
        )

    result = (
        MasteryObjectivesResult(
            mode=mode,
            par_objectif=tuple(
                objectives
            ),
            note_globale_objectifs_preformation=(
                _parse_optional_number(
                    obj[
                        (
                            "note_globale_"
                            "objectifs_preformation"
                        )
                    ],
                    (
                        "maitrise_objectifs."
                        "note_globale_"
                        "objectifs_preformation"
                    ),
                )
            ),
        )
    )

    validate_extraction_payload(
        "maitrise_objectifs",
        result,
    )

    return result


# =====================================================
# Entrée publique
# =====================================================

def parse_extraction_payload(
    data_kind: DataKind,
    raw: object,
) -> QuestionExtractionPayload:
    """
    Transforme le JSON brut d'une tâche
    en contrat interne validé.

    Aucun appel LLM n'est effectué ici.
    """

    if data_kind == "distribution_1_5":
        return (
            _parse_distribution_1_to_5(
                raw
            )
        )

    if data_kind == "distribution_categories":
        return (
            _parse_distribution_categories(
                raw
            )
        )

    if data_kind == "distribution_yes_no":
        return (
            _parse_distribution_yes_no(
                raw
            )
        )

    if data_kind == "verbatims":
        return _parse_verbatims(
            raw
        )

    if data_kind == "maitrise_objectifs":
        return (
            _parse_mastery_objectives(
                raw
            )
        )

    raise NotImplementedError(
        "Aucun parseur défini pour "
        f"data_kind={data_kind!r}."
    )
