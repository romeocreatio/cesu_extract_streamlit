from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple, Union

from utils.output_adapter_2026 import (
    OUTPUT_HEADERS_2026,
    OutputRow2026,
)
from utils.report_2026_orchestrator import (
    Report2026OrchestrationResult,
)

from utils.preformation_verbatim_synthesis_2026 import (
    PreformationVerbatimSynthesisInput2026,
    build_preformation_verbatim_synthesis_input_2026,
)

from utils.a_chaud_verbatim_synthesis_2026 import (
    VerbatimSynthesisInput2026,
    build_verbatim_synthesis_input_2026,
)

from utils.a_froid_verbatim_synthesis_2026 import (
    AFroidVerbatimSynthesisInput2026,
    build_a_froid_verbatim_synthesis_input_2026,
)

from utils.intervenants_synthesis_2026 import (
    IntervenantsAdaptationHorairesSynthesisSource2026,
    IntervenantsSynthesisInput2026,
    build_intervenants_synthesis_input_2026,
)


Number = Union[int, float]

ANALYSIS_SCHEMA_VERSION_2026 = "analysis_2026.v1"

SYNTHESIS_OUTPUT_HEADERS_2026 = (
    "Demande particulière de sujet à aborder",
    "Points forts",
    "Points faibles",
    (
        "Sujets non traité à reboucler avec formateur "
        "ou nouvelle formation ou attendu"
    ),
    "Evaluation formateurs",
    "Avec le recul ",
    "Problématiques remontées",
    "Adaptations de programme",
    "Synthese",
)


@dataclass(frozen=True)
class Report2026AnalysisMetadata:
    formation: str
    semestre: str
    report_url: str


@dataclass(frozen=True)
class Report2026SynthesisSources:
    preformation: PreformationVerbatimSynthesisInput2026
    a_chaud: VerbatimSynthesisInput2026
    a_froid: AFroidVerbatimSynthesisInput2026
    intervenants: IntervenantsSynthesisInput2026


@dataclass(frozen=True)
class Report2026AnalysisContract:
    schema_version: str
    metadata: Report2026AnalysisMetadata
    deterministic_output: OutputRow2026
    synthesis_sources: Report2026SynthesisSources
    issues: Tuple[str, ...]


def _collect_business_issues(
    report: Report2026OrchestrationResult,
) -> Tuple[str, ...]:
    collected = []

    groups = (
        (
            "preformation",
            report.preformation_model,
        ),
        (
            "a_chaud",
            report.a_chaud_model,
        ),
        (
            "a_froid",
            report.a_froid_model,
        ),
        (
            "intervenants",
            report.intervenants_model,
        ),
    )

    for prefix, model in groups:
        for issue in getattr(
            model,
            "issues",
            (),
        ):
            collected.append(
                f"{prefix}: {issue}"
            )

    return tuple(
        collected
    )


def _validate_deterministic_output(
    row: Mapping[str, Any],
) -> OutputRow2026:
    if not isinstance(
        row,
        Mapping,
    ):
        raise TypeError(
            "deterministic_output doit être un mapping."
        )

    actual_headers = tuple(
        row.keys()
    )

    if actual_headers != tuple(
        OUTPUT_HEADERS_2026
    ):
        raise ValueError(
            "deterministic_output doit contenir "
            "exactement les 22 en-têtes 2026 "
            "dans l'ordre attendu."
        )

    normalized: OutputRow2026 = {}

    for header in OUTPUT_HEADERS_2026:
        value = row[
            header
        ]

        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"La colonne {header!r} doit contenir "
                "une chaîne de caractères."
            )

        normalized[
            header
        ] = value

    for header in SYNTHESIS_OUTPUT_HEADERS_2026:
        if normalized[
            header
        ] != "":
            raise ValueError(
                "Le contrat Phase 1 ne doit pas "
                "déjà contenir de synthèse LLM : "
                f"{header!r}."
            )

    return normalized


def build_report_2026_analysis_contract(
    report: Report2026OrchestrationResult,
) -> Report2026AnalysisContract:
    """
    Construit le contrat JSON de Phase 1 depuis
    l'orchestration déterministe 2026.

    Aucun appel LLM.
    Aucune relecture du PDF.
    """

    if not isinstance(
        report,
        Report2026OrchestrationResult,
    ):
        raise TypeError(
            "report doit être un "
            "Report2026OrchestrationResult."
        )

    row = _validate_deterministic_output(
        report.row
    )

    metadata = Report2026AnalysisMetadata(
        formation=row[
            "Formation"
        ],
        semestre=row[
            "Semestre"
        ],
        report_url=row[
            "Lien du rapport qualité"
        ],
    )

    synthesis_sources = Report2026SynthesisSources(
        preformation=(
            build_preformation_verbatim_synthesis_input_2026(
                report.preformation_model
            )
        ),
        a_chaud=(
            build_verbatim_synthesis_input_2026(
                report.a_chaud_model
            )
        ),
        a_froid=(
            build_a_froid_verbatim_synthesis_input_2026(
                report.a_froid_model
            )
        ),
        intervenants=(
            build_intervenants_synthesis_input_2026(
                report.intervenants_model
            )
        ),
    )

    return Report2026AnalysisContract(
        schema_version=ANALYSIS_SCHEMA_VERSION_2026,
        metadata=metadata,
        deterministic_output=row,
        synthesis_sources=synthesis_sources,
        issues=_collect_business_issues(
            report
        ),
    )


def report_2026_analysis_to_dict(
    contract: Report2026AnalysisContract,
) -> Dict[str, Any]:
    if not isinstance(
        contract,
        Report2026AnalysisContract,
    ):
        raise TypeError(
            "contract doit être un "
            "Report2026AnalysisContract."
        )

    row = _validate_deterministic_output(
        contract.deterministic_output
    )

    if (
        contract.schema_version
        != ANALYSIS_SCHEMA_VERSION_2026
    ):
        raise ValueError(
            "Version de contrat 2026 invalide."
        )

    if not isinstance(
        contract.metadata,
        Report2026AnalysisMetadata,
    ):
        raise TypeError(
            "metadata invalide."
        )

    if not isinstance(
        contract.synthesis_sources,
        Report2026SynthesisSources,
    ):
        raise TypeError(
            "synthesis_sources invalide."
        )

    sources = contract.synthesis_sources

    if not isinstance(
        sources.preformation,
        PreformationVerbatimSynthesisInput2026,
    ):
        raise TypeError(
            "Source preformation invalide."
        )

    if not isinstance(
        sources.a_chaud,
        VerbatimSynthesisInput2026,
    ):
        raise TypeError(
            "Source A chaud invalide."
        )

    if not isinstance(
        sources.a_froid,
        AFroidVerbatimSynthesisInput2026,
    ):
        raise TypeError(
            "Source A froid invalide."
        )

    if not isinstance(
        sources.intervenants,
        IntervenantsSynthesisInput2026,
    ):
        raise TypeError(
            "Source intervenants invalide."
        )

    adaptation_horaires = []

    for item in (
        sources.intervenants.adaptation_horaires
    ):
        if not isinstance(
            item,
            IntervenantsAdaptationHorairesSynthesisSource2026,
        ):
            raise TypeError(
                "Source adaptation_horaires invalide."
            )

        adaptation_horaires.append(
            {
                "occurrence_id": item.occurrence_id,
                "oui_count": item.oui_count,
                "oui_percentage": item.oui_percentage,
                "non_count": item.non_count,
                "non_percentage": item.non_percentage,
            }
        )

    return {
        "schema_version": contract.schema_version,
        "metadata": {
            "formation": contract.metadata.formation,
            "semestre": contract.metadata.semestre,
            "report_url": contract.metadata.report_url,
        },
        "deterministic_output": {
            header: row[
                header
            ]
            for header in OUTPUT_HEADERS_2026
        },
        "synthesis_sources": {
            "preformation": {
                "sujets_a_aborder": list(
                    sources.preformation.sujets_a_aborder
                ),
            },
            "a_chaud": {
                "points_forts": list(
                    sources.a_chaud.points_forts
                ),
                "points_faibles": list(
                    sources.a_chaud.points_faibles
                ),
                "sujets_reboucler": list(
                    sources.a_chaud.sujets_reboucler
                ),
                "evaluation_formateurs": list(
                    sources.a_chaud.evaluation_formateurs
                ),
            },
            "a_froid": {
                "elements_utiles": list(
                    sources.a_froid.elements_utiles
                ),
            },
            "intervenants": {
                "conditions_materielles": list(
                    sources.intervenants.conditions_materielles
                ),
                "groupe_apprenants": list(
                    sources.intervenants.groupe_apprenants
                ),
                "organisation_generale": list(
                    sources.intervenants.organisation_generale
                ),
                "adaptation_horaires": adaptation_horaires,
                "explication_modification_programme": list(
                    sources.intervenants
                    .explication_modification_programme
                ),
            },
        },
        "issues": list(
            contract.issues
        ),
    }


def _expect_exact_keys(
    value: Mapping[str, Any],
    expected: Tuple[str, ...],
    *,
    label: str,
) -> None:
    actual_keys = set(
        value.keys()
    )

    expected_keys = set(
        expected
    )

    if actual_keys != expected_keys:
        missing = tuple(
            key
            for key in expected
            if key not in actual_keys
        )

        unexpected = tuple(
            key
            for key in value.keys()
            if key not in expected_keys
        )

        raise ValueError(
            f"{label} doit contenir exactement "
            "les clés attendues. "
            f"Manquantes : {missing!r}. "
            f"Inattendues : {unexpected!r}."
        )


def _expect_mapping(
    value: Any,
    *,
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(
        value,
        Mapping,
    ):
        raise TypeError(
            f"{label} doit être un objet JSON."
        )

    return value


def _expect_string(
    value: Any,
    *,
    label: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{label} doit être une chaîne."
        )

    return value


def _expect_string_tuple(
    value: Any,
    *,
    label: str,
) -> Tuple[str, ...]:
    if not isinstance(
        value,
        list,
    ):
        raise TypeError(
            f"{label} doit être une liste JSON."
        )

    result = []

    for index, item in enumerate(
        value
    ):
        if not isinstance(
            item,
            str,
        ):
            raise TypeError(
                f"{label}[{index}] doit être "
                "une chaîne."
            )

        result.append(
            item
        )

    return tuple(
        result
    )


def _expect_optional_number(
    value: Any,
    *,
    label: str,
) -> Optional[Number]:
    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError(
            f"{label} doit être un nombre ou null."
        )

    return value


def report_2026_analysis_from_dict(
    payload: Mapping[str, Any],
) -> Report2026AnalysisContract:
    """
    Reconstruit strictement le contrat Python depuis
    le JSON sauvegardé par la Phase 1.
    """

    payload = _expect_mapping(
        payload,
        label="payload",
    )

    _expect_exact_keys(
        payload,
        (
            "schema_version",
            "metadata",
            "deterministic_output",
            "synthesis_sources",
            "issues",
        ),
        label="payload",
    )

    schema_version = _expect_string(
        payload[
            "schema_version"
        ],
        label="schema_version",
    )

    if (
        schema_version
        != ANALYSIS_SCHEMA_VERSION_2026
    ):
        raise ValueError(
            "Version de contrat 2026 non supportée."
        )

    metadata_raw = _expect_mapping(
        payload[
            "metadata"
        ],
        label="metadata",
    )

    _expect_exact_keys(
        metadata_raw,
        (
            "formation",
            "semestre",
            "report_url",
        ),
        label="metadata",
    )

    metadata = Report2026AnalysisMetadata(
        formation=_expect_string(
            metadata_raw[
                "formation"
            ],
            label="metadata.formation",
        ),
        semestre=_expect_string(
            metadata_raw[
                "semestre"
            ],
            label="metadata.semestre",
        ),
        report_url=_expect_string(
            metadata_raw[
                "report_url"
            ],
            label="metadata.report_url",
        ),
    )

    deterministic_raw = _expect_mapping(
        payload[
            "deterministic_output"
        ],
        label="deterministic_output",
    )

    deterministic_output = (
        _validate_deterministic_output(
            deterministic_raw
        )
    )

    if (
        metadata.formation
        != deterministic_output[
            "Formation"
        ]
    ):
        raise ValueError(
            "metadata.formation ne correspond pas "
            "à deterministic_output."
        )

    if (
        metadata.semestre
        != deterministic_output[
            "Semestre"
        ]
    ):
        raise ValueError(
            "metadata.semestre ne correspond pas "
            "à deterministic_output."
        )

    if (
        metadata.report_url
        != deterministic_output[
            "Lien du rapport qualité"
        ]
    ):
        raise ValueError(
            "metadata.report_url ne correspond pas "
            "à deterministic_output."
        )

    sources_raw = _expect_mapping(
        payload[
            "synthesis_sources"
        ],
        label="synthesis_sources",
    )

    _expect_exact_keys(
        sources_raw,
        (
            "preformation",
            "a_chaud",
            "a_froid",
            "intervenants",
        ),
        label="synthesis_sources",
    )

    preformation_raw = _expect_mapping(
        sources_raw[
            "preformation"
        ],
        label="synthesis_sources.preformation",
    )

    _expect_exact_keys(
        preformation_raw,
        (
            "sujets_a_aborder",
        ),
        label="synthesis_sources.preformation",
    )

    preformation = (
        PreformationVerbatimSynthesisInput2026(
            sujets_a_aborder=_expect_string_tuple(
                preformation_raw[
                    "sujets_a_aborder"
                ],
                label=(
                    "synthesis_sources.preformation."
                    "sujets_a_aborder"
                ),
            ),
        )
    )

    a_chaud_raw = _expect_mapping(
        sources_raw[
            "a_chaud"
        ],
        label="synthesis_sources.a_chaud",
    )

    _expect_exact_keys(
        a_chaud_raw,
        (
            "points_forts",
            "points_faibles",
            "sujets_reboucler",
            "evaluation_formateurs",
        ),
        label="synthesis_sources.a_chaud",
    )

    a_chaud = VerbatimSynthesisInput2026(
        points_forts=_expect_string_tuple(
            a_chaud_raw[
                "points_forts"
            ],
            label=(
                "synthesis_sources.a_chaud."
                "points_forts"
            ),
        ),
        points_faibles=_expect_string_tuple(
            a_chaud_raw[
                "points_faibles"
            ],
            label=(
                "synthesis_sources.a_chaud."
                "points_faibles"
            ),
        ),
        sujets_reboucler=_expect_string_tuple(
            a_chaud_raw[
                "sujets_reboucler"
            ],
            label=(
                "synthesis_sources.a_chaud."
                "sujets_reboucler"
            ),
        ),
        evaluation_formateurs=_expect_string_tuple(
            a_chaud_raw[
                "evaluation_formateurs"
            ],
            label=(
                "synthesis_sources.a_chaud."
                "evaluation_formateurs"
            ),
        ),
    )

    a_froid_raw = _expect_mapping(
        sources_raw[
            "a_froid"
        ],
        label="synthesis_sources.a_froid",
    )

    _expect_exact_keys(
        a_froid_raw,
        (
            "elements_utiles",
        ),
        label="synthesis_sources.a_froid",
    )

    a_froid = AFroidVerbatimSynthesisInput2026(
        elements_utiles=_expect_string_tuple(
            a_froid_raw[
                "elements_utiles"
            ],
            label=(
                "synthesis_sources.a_froid."
                "elements_utiles"
            ),
        ),
    )

    intervenants_raw = _expect_mapping(
        sources_raw[
            "intervenants"
        ],
        label="synthesis_sources.intervenants",
    )

    _expect_exact_keys(
        intervenants_raw,
        (
            "conditions_materielles",
            "groupe_apprenants",
            "organisation_generale",
            "adaptation_horaires",
            "explication_modification_programme",
        ),
        label="synthesis_sources.intervenants",
    )

    adaptation_raw = intervenants_raw[
        "adaptation_horaires"
    ]

    if not isinstance(
        adaptation_raw,
        list,
    ):
        raise TypeError(
            "synthesis_sources.intervenants."
            "adaptation_horaires doit être une liste."
        )

    adaptation_horaires = []

    for index, item in enumerate(
        adaptation_raw
    ):
        item = _expect_mapping(
            item,
            label=(
                "synthesis_sources.intervenants."
                f"adaptation_horaires[{index}]"
            ),
        )

        _expect_exact_keys(
            item,
            (
                "occurrence_id",
                "oui_count",
                "oui_percentage",
                "non_count",
                "non_percentage",
            ),
            label=(
                "synthesis_sources.intervenants."
                f"adaptation_horaires[{index}]"
            ),
        )

        adaptation_horaires.append(
            IntervenantsAdaptationHorairesSynthesisSource2026(
                occurrence_id=_expect_string(
                    item[
                        "occurrence_id"
                    ],
                    label=(
                        "adaptation_horaires."
                        f"{index}.occurrence_id"
                    ),
                ),
                oui_count=_expect_optional_number(
                    item[
                        "oui_count"
                    ],
                    label=(
                        "adaptation_horaires."
                        f"{index}.oui_count"
                    ),
                ),
                oui_percentage=_expect_optional_number(
                    item[
                        "oui_percentage"
                    ],
                    label=(
                        "adaptation_horaires."
                        f"{index}.oui_percentage"
                    ),
                ),
                non_count=_expect_optional_number(
                    item[
                        "non_count"
                    ],
                    label=(
                        "adaptation_horaires."
                        f"{index}.non_count"
                    ),
                ),
                non_percentage=_expect_optional_number(
                    item[
                        "non_percentage"
                    ],
                    label=(
                        "adaptation_horaires."
                        f"{index}.non_percentage"
                    ),
                ),
            )
        )

    intervenants = IntervenantsSynthesisInput2026(
        conditions_materielles=_expect_string_tuple(
            intervenants_raw[
                "conditions_materielles"
            ],
            label=(
                "synthesis_sources.intervenants."
                "conditions_materielles"
            ),
        ),
        groupe_apprenants=_expect_string_tuple(
            intervenants_raw[
                "groupe_apprenants"
            ],
            label=(
                "synthesis_sources.intervenants."
                "groupe_apprenants"
            ),
        ),
        organisation_generale=_expect_string_tuple(
            intervenants_raw[
                "organisation_generale"
            ],
            label=(
                "synthesis_sources.intervenants."
                "organisation_generale"
            ),
        ),
        adaptation_horaires=tuple(
            adaptation_horaires
        ),
        explication_modification_programme=(
            _expect_string_tuple(
                intervenants_raw[
                    "explication_modification_programme"
                ],
                label=(
                    "synthesis_sources.intervenants."
                    "explication_modification_programme"
                ),
            )
        ),
    )

    issues = _expect_string_tuple(
        payload[
            "issues"
        ],
        label="issues",
    )

    return Report2026AnalysisContract(
        schema_version=schema_version,
        metadata=metadata,
        deterministic_output=deterministic_output,
        synthesis_sources=Report2026SynthesisSources(
            preformation=preformation,
            a_chaud=a_chaud,
            a_froid=a_froid,
            intervenants=intervenants,
        ),
        issues=issues,
    )


def report_2026_analysis_dumps(
    contract: Report2026AnalysisContract,
) -> str:
    return json.dumps(
        report_2026_analysis_to_dict(
            contract
        ),
        ensure_ascii=False,
        indent=2,
    )


def report_2026_analysis_loads(
    raw: str,
) -> Report2026AnalysisContract:
    if not isinstance(
        raw,
        str,
    ):
        raise TypeError(
            "raw doit être une chaîne JSON."
        )

    payload = json.loads(
        raw
    )

    return report_2026_analysis_from_dict(
        payload
    )
