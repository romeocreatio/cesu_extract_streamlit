from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from utils.llm_client import (
    call_llm_extract_json,
)

from utils.report_2026_orchestrator import (
    Report2026OrchestrationResult,
)

from utils.output_adapter_2026 import (
    OutputRow2026,
    build_output_row_2026,
)

from utils.preformation_verbatim_openai_2026 import (
    make_preformation_verbatim_openai_generator_2026,
)
from utils.preformation_verbatim_synthesis_2026 import (
    PreformationVerbatimSynthesis2026,
    synthesize_preformation_verbatims_2026,
)

from utils.a_chaud_verbatim_openai_2026 import (
    make_a_chaud_verbatim_openai_generator_2026,
)
from utils.a_chaud_verbatim_synthesis_2026 import (
    VerbatimSynthesis2026,
    synthesize_a_chaud_verbatims_2026,
)

from utils.a_froid_verbatim_openai_2026 import (
    make_a_froid_verbatim_openai_generator_2026,
)
from utils.a_froid_verbatim_synthesis_2026 import (
    AFroidVerbatimSynthesis2026,
    synthesize_a_froid_verbatims_2026,
)

from utils.intervenants_openai_2026 import (
    make_intervenants_openai_generator_2026,
)
from utils.intervenants_synthesis_2026 import (
    IntervenantsSynthesis2026,
    synthesize_intervenants_2026,
)


# =====================================================
# Configuration 2026
# =====================================================

DEFAULT_SYNTHESIS_MODEL_2026 = "gpt-6-luna"


LLMJsonCaller2026 = Callable[
    [
        str,
        str,
        dict,
        Optional[str],
    ],
    dict,
]


# =====================================================
# Résultat
# =====================================================

@dataclass(frozen=True)
class Report2026SynthesisOrchestrationResult:
    """
    Résultat complet de la couche de synthèse 2026.

    Cette couche :
    - reçoit les business models déjà construits ;
    - produit uniquement les synthèses textuelles ;
    - choisit explicitement le modèle LLM 2026 ;
    - reconstruit la ligne finale de 22 colonnes.

    Elle ne :
    - lit aucun PDF ;
    - ne refait aucune extraction ;
    - ne recalcule aucune donnée métier ;
    - n'écrit ni Excel ni Google Sheets.
    """

    model: str

    preformation_synthesis: (
        PreformationVerbatimSynthesis2026
    )

    a_chaud_synthesis: (
        VerbatimSynthesis2026
    )

    a_froid_synthesis: (
        AFroidVerbatimSynthesis2026
    )

    intervenants_synthesis: (
        IntervenantsSynthesis2026
    )

    row: OutputRow2026


# =====================================================
# Orchestration des synthèses
# =====================================================

def orchestrate_report_2026_syntheses(
    report: Report2026OrchestrationResult,
    *,
    model_override: Optional[str] = None,
    llm_call: LLMJsonCaller2026 = (
        call_llm_extract_json
    ),
) -> Report2026SynthesisOrchestrationResult:
    """
    Produit toutes les synthèses textuelles d'un
    rapport standard 2026 déjà extrait.

    Le modèle par défaut est GPT-6 Luna.

    Un autre modèle ou un faux client peuvent être
    injectés explicitement pour les tests.
    """

    if not isinstance(
        report,
        Report2026OrchestrationResult,
    ):
        raise TypeError(
            "report doit être un "
            "Report2026OrchestrationResult."
        )

    if model_override is None:
        model = DEFAULT_SYNTHESIS_MODEL_2026
    else:
        if not isinstance(
            model_override,
            str,
        ):
            raise TypeError(
                "model_override doit être une chaîne "
                "ou None."
            )

        model = model_override.strip()

        if not model:
            raise ValueError(
                "model_override ne peut pas être vide."
            )

    if not callable(llm_call):
        raise TypeError(
            "llm_call doit être callable."
        )

    # -------------------------------------------------
    # Préformation
    # -------------------------------------------------

    preformation_generator = (
        make_preformation_verbatim_openai_generator_2026(
            model_override=model,
            llm_call=llm_call,
        )
    )

    preformation_synthesis = (
        synthesize_preformation_verbatims_2026(
            report.preformation_model,
            generator=preformation_generator,
        )
    )

    # -------------------------------------------------
    # À chaud
    # -------------------------------------------------

    a_chaud_generator = (
        make_a_chaud_verbatim_openai_generator_2026(
            model_override=model,
            llm_call=llm_call,
        )
    )

    a_chaud_synthesis = (
        synthesize_a_chaud_verbatims_2026(
            report.a_chaud_model,
            generator=a_chaud_generator,
        )
    )

    # -------------------------------------------------
    # À froid
    # -------------------------------------------------

    a_froid_generator = (
        make_a_froid_verbatim_openai_generator_2026(
            model_override=model,
            llm_call=llm_call,
        )
    )

    a_froid_synthesis = (
        synthesize_a_froid_verbatims_2026(
            report.a_froid_model,
            generator=a_froid_generator,
        )
    )

    # -------------------------------------------------
    # Intervenants
    # -------------------------------------------------

    intervenants_generator = (
        make_intervenants_openai_generator_2026(
            model_override=model,
            llm_call=llm_call,
        )
    )

    intervenants_synthesis = (
        synthesize_intervenants_2026(
            report.intervenants_model,
            generator=intervenants_generator,
        )
    )

    # -------------------------------------------------
    # Ligne finale
    # -------------------------------------------------

    row = build_output_row_2026(
        report.preformation_model,
        preformation_synthesis=(
            preformation_synthesis
        ),
        a_chaud_model=report.a_chaud_model,
        a_chaud_synthesis=(
            a_chaud_synthesis
        ),
        a_froid_model=report.a_froid_model,
        a_froid_synthesis=(
            a_froid_synthesis
        ),
        intervenants_synthesis=(
            intervenants_synthesis
        ),
    )

    return Report2026SynthesisOrchestrationResult(
        model=model,
        preformation_synthesis=(
            preformation_synthesis
        ),
        a_chaud_synthesis=(
            a_chaud_synthesis
        ),
        a_froid_synthesis=(
            a_froid_synthesis
        ),
        intervenants_synthesis=(
            intervenants_synthesis
        ),
        row=row,
    )
