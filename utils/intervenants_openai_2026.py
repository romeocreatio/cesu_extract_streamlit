# utils/intervenants_openai_2026.py

from __future__ import annotations

import json

from dataclasses import dataclass
from typing import (
    Callable,
    Optional,
)

from utils.llm_client import (
    call_llm_extract_json,
)


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
# Générateur OpenAI injectable
# =====================================================

@dataclass
class IntervenantsOpenAIGenerator2026:
    """
    Adaptateur entre la synthèse intervenants 2026
    et le client LLM existant.

    Aucun appel réseau à l'instanciation.
    """

    model_override: Optional[str] = None

    llm_call: LLMJsonCaller2026 = (
        call_llm_extract_json
    )

    def __call__(
        self,
        prompt: str,
    ) -> str:
        """
        Exécute exactement un appel LLM.

        Le prompt contient déjà toutes les données
        source nécessaires.
        """

        if not isinstance(
            prompt,
            str,
        ):

            raise TypeError(
                "prompt doit être une chaîne."
            )

        if not prompt.strip():

            raise ValueError(
                "prompt ne peut pas être vide."
            )

        raw = self.llm_call(
            prompt,
            "",
            {
                "mode":
                    "intervenants_synthesis_2026"
            },
            self.model_override,
        )

        if not isinstance(
            raw,
            dict,
        ):

            raise TypeError(
                "Le client LLM doit retourner "
                "un dictionnaire JSON."
            )

        return json.dumps(
            raw,
            ensure_ascii=False,
        )


# =====================================================
# Factory publique
# =====================================================

def make_intervenants_openai_generator_2026(
    *,
    model_override: Optional[str] = None,
    llm_call: LLMJsonCaller2026 = (
        call_llm_extract_json
    ),
) -> IntervenantsOpenAIGenerator2026:
    """
    Construit le générateur OpenAI intervenants 2026.

    Le client LLM peut être remplacé par un faux
    client dans les tests.
    """

    if not callable(
        llm_call
    ):

        raise TypeError(
            "llm_call doit être callable."
        )

    return IntervenantsOpenAIGenerator2026(
        model_override=model_override,
        llm_call=llm_call,
    )
