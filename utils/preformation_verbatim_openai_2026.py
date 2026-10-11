from __future__ import annotations

import json

from dataclasses import dataclass
from typing import Callable, Optional

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
# Generateur OpenAI injectable
# =====================================================

@dataclass
class PreformationVerbatimOpenAIGenerator2026:
    """
    Adaptateur entre la couche de synthese
    preformation 2026 et le client LLM existant.

    Aucun appel reseau n'est effectue a
    l'instanciation.

    L'appel OpenAI n'a lieu que lorsque
    __call__ est execute.
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
        Execute exactement un appel LLM.

        Le prompt contient deja les verbatims
        et les instructions de synthese.

        full_text reste volontairement vide :
        aucune extraction PDF n'est demandee ici.
        """

        if not isinstance(
            prompt,
            str,
        ):
            raise TypeError(
                "prompt doit etre une chaine."
            )

        if not prompt.strip():
            raise ValueError(
                "prompt ne peut pas etre vide."
            )

        raw = self.llm_call(
            prompt,
            "",
            {
                "mode":
                    "preformation_verbatim_synthesis_2026"
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

def make_preformation_verbatim_openai_generator_2026(
    *,
    model_override: Optional[str] = None,
    llm_call: LLMJsonCaller2026 = (
        call_llm_extract_json
    ),
) -> PreformationVerbatimOpenAIGenerator2026:
    """
    Construit le generateur OpenAI preformation 2026.

    Permet d'injecter un faux client lors des tests.
    """

    if not callable(
        llm_call
    ):
        raise TypeError(
            "llm_call doit etre callable."
        )

    return (
        PreformationVerbatimOpenAIGenerator2026(
            model_override=model_override,
            llm_call=llm_call,
        )
    )
