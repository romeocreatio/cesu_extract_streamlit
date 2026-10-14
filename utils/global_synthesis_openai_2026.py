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


@dataclass
class GlobalSynthesisOpenAIGenerator2026:
    """
    Adaptateur OpenAI de la synthèse globale 2026.

    Aucun appel réseau à l'instanciation.
    """

    model_override: Optional[
        str
    ] = None

    llm_call: LLMJsonCaller2026 = (
        call_llm_extract_json
    )

    def __call__(
        self,
        prompt: str,
    ) -> str:

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
                    "global_synthesis_2026"
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


def make_global_synthesis_openai_generator_2026(
    *,
    model_override: Optional[
        str
    ] = None,
    llm_call: LLMJsonCaller2026 = (
        call_llm_extract_json
    ),
) -> GlobalSynthesisOpenAIGenerator2026:

    if not callable(
        llm_call
    ):
        raise TypeError(
            "llm_call doit être callable."
        )

    return GlobalSynthesisOpenAIGenerator2026(
        model_override=model_override,
        llm_call=llm_call,
    )
