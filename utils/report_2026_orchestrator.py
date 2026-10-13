# utils/report_2026_orchestrator.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from utils.preformation_2026_pipeline import (
    Preformation2026PipelineResult,
    extract_preformation_2026,
)
from utils.business_model_2026 import (
    PreformationBusinessModel2026,
    build_preformation_business_model_2026,
)

from utils.a_chaud_2026_pipeline import (
    AChaud2026PipelineResult,
    extract_a_chaud_2026,
)
from utils.a_chaud_business_model_2026 import (
    AChaudBusinessModel2026,
    build_a_chaud_business_model_2026,
)

from utils.a_froid_2026_pipeline import (
    AFroid2026PipelineResult,
    extract_a_froid_2026,
)
from utils.a_froid_business_model_2026 import (
    AFroidBusinessModel2026,
    build_a_froid_business_model_2026,
)
from utils.progression_metric_extractor_2026 import (
    ProgressionMetricExtraction2026,
    extract_progression_metric_2026,
)

from utils.intervenants_2026_pipeline import (
    Intervenants2026PipelineResult,
    extract_intervenants_2026,
)
from utils.intervenants_business_model_2026 import (
    IntervenantsBusinessModel2026,
    build_intervenants_business_model_2026,
)

from utils.preformation_verbatim_synthesis_2026 import (
    PreformationVerbatimSynthesis2026,
)
from utils.a_chaud_verbatim_synthesis_2026 import (
    VerbatimSynthesis2026,
)
from utils.a_froid_verbatim_synthesis_2026 import (
    AFroidVerbatimSynthesis2026,
)
from utils.intervenants_synthesis_2026 import (
    IntervenantsSynthesis2026,
)

from utils.output_adapter_2026 import (
    OutputRow2026,
    build_output_row_2026,
)


@dataclass(
    frozen=True,
)
class Report2026OrchestrationResult:
    """
    Résultat complet et auditable du flux standard 2026.

    Cette couche assemble uniquement les briques déjà
    validées.

    Elle ne :
    - connaît aucun fournisseur LLM ;
    - n'appelle pas OpenAI ;
    - ne produit aucune synthèse textuelle ;
    - n'écrit ni Excel ni Google Sheets.
    """

    preformation_pipeline: Preformation2026PipelineResult
    preformation_model: PreformationBusinessModel2026

    a_chaud_pipeline: AChaud2026PipelineResult
    a_chaud_model: AChaudBusinessModel2026

    a_froid_pipeline: AFroid2026PipelineResult
    progression_extraction: ProgressionMetricExtraction2026
    a_froid_model: AFroidBusinessModel2026

    intervenants_pipeline: Intervenants2026PipelineResult
    intervenants_model: IntervenantsBusinessModel2026

    row: OutputRow2026


def orchestrate_report_2026(
    pdf_bytes: bytes,
    *,
    formation: str,
    semestre: str,
    report_url: str = "",
    preformation_synthesis: Optional[
        PreformationVerbatimSynthesis2026
    ] = None,
    a_chaud_synthesis: Optional[
        VerbatimSynthesis2026
    ] = None,
    a_froid_synthesis: Optional[
        AFroidVerbatimSynthesis2026
    ] = None,
    intervenants_synthesis: Optional[
        IntervenantsSynthesis2026
    ] = None,
    ocr_on_empty: bool = True,
    dpi: int = 300,
) -> Report2026OrchestrationResult:
    """
    Assemble le rapport qualité standard CESU 83 2026.

    Chaîne :

        PDF
        -> préformation
        -> à chaud
        -> à froid
        -> progression explicite
        -> intervenants
        -> business models
        -> synthèses déjà produites, si fournies
        -> adaptateur de sortie
        -> ligne finale 22 colonnes

    Aucun appel LLM n'est réalisé ici.
    """

    if not isinstance(
        pdf_bytes,
        bytes,
    ):
        raise TypeError(
            "pdf_bytes doit être de type bytes."
        )

    if not pdf_bytes:
        raise ValueError(
            "pdf_bytes ne doit pas être vide."
        )

    if not isinstance(
        formation,
        str,
    ):
        raise TypeError(
            "formation doit être une chaîne."
        )

    if not isinstance(
        semestre,
        str,
    ):
        raise TypeError(
            "semestre doit être une chaîne."
        )

    if not isinstance(
        report_url,
        str,
    ):
        raise TypeError(
            "report_url doit être une chaîne."
        )

    if not isinstance(
        ocr_on_empty,
        bool,
    ):
        raise TypeError(
            "ocr_on_empty doit être un booléen."
        )

    if (
        not isinstance(dpi, int)
        or isinstance(dpi, bool)
        or dpi <= 0
    ):
        raise ValueError(
            "dpi doit être un entier strictement positif."
        )

    # -------------------------------------------------
    # Préformation
    # -------------------------------------------------

    preformation_pipeline = (
        extract_preformation_2026(
            pdf_bytes,
            ocr_on_empty=ocr_on_empty,
            dpi=dpi,
        )
    )

    preformation_model = (
        build_preformation_business_model_2026(
            preformation_pipeline.occurrences,
            formation=formation,
            semestre=semestre,
            report_url=report_url,
        )
    )

    # -------------------------------------------------
    # À chaud
    # -------------------------------------------------

    a_chaud_pipeline = (
        extract_a_chaud_2026(
            pdf_bytes,
            ocr_on_empty=ocr_on_empty,
            dpi=dpi,
        )
    )

    a_chaud_model = (
        build_a_chaud_business_model_2026(
            a_chaud_pipeline.occurrences
        )
    )

    # -------------------------------------------------
    # À froid + progression
    # -------------------------------------------------

    a_froid_pipeline = (
        extract_a_froid_2026(
            pdf_bytes,
            ocr_on_empty=ocr_on_empty,
            dpi=dpi,
        )
    )

    progression_extraction = (
        extract_progression_metric_2026(
            a_froid_pipeline.pdf_result
        )
    )

    a_froid_model = (
        build_a_froid_business_model_2026(
            a_froid_pipeline.occurrences,
            progression_extraction=(
                progression_extraction
            ),
        )
    )

    # -------------------------------------------------
    # Intervenants
    # -------------------------------------------------

    intervenants_pipeline = (
        extract_intervenants_2026(
            pdf_bytes,
            ocr_on_empty=ocr_on_empty,
            dpi=dpi,
        )
    )

    intervenants_model = (
        build_intervenants_business_model_2026(
            intervenants_pipeline.occurrences
        )
    )

    # -------------------------------------------------
    # Sortie standard 22 colonnes
    #
    # Les synthèses sont seulement injectées.
    # Elles ne sont jamais produites ici.
    # -------------------------------------------------

    row = build_output_row_2026(
        preformation_model,
        preformation_synthesis=(
            preformation_synthesis
        ),
        a_chaud_model=a_chaud_model,
        a_chaud_synthesis=(
            a_chaud_synthesis
        ),
        a_froid_model=a_froid_model,
        a_froid_synthesis=(
            a_froid_synthesis
        ),
        intervenants_synthesis=(
            intervenants_synthesis
        ),
    )

    return Report2026OrchestrationResult(
        preformation_pipeline=(
            preformation_pipeline
        ),
        preformation_model=(
            preformation_model
        ),
        a_chaud_pipeline=(
            a_chaud_pipeline
        ),
        a_chaud_model=(
            a_chaud_model
        ),
        a_froid_pipeline=(
            a_froid_pipeline
        ),
        progression_extraction=(
            progression_extraction
        ),
        a_froid_model=(
            a_froid_model
        ),
        intervenants_pipeline=(
            intervenants_pipeline
        ),
        intervenants_model=(
            intervenants_model
        ),
        row=row,
    )
