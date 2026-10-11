# utils/a_chaud_verbatim_openai_2026.py

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Optional

from utils.llm_client import (
    call_llm_extract_json,
)


# =====================================================
# Injectable LLM contract
# =====================================================

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
# OpenAI adapter
# =====================================================

@dataclass
class AChaudVerbatimOpenAIGenerator2026:
    """
    Adapter between the generic verbatim synthesis
    layer and the existing CESU OpenAI client.

    It performs exactly one LLM call each time the
    generator is called.

    It does not:
    - build the synthesis prompt;
    - parse the final business result;
    - know Excel or Google Sheets;
    - modify source verbatims.
    """

    model_override: Optional[str] = None

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
                "mode": (
                    "a_chaud_verbatim_"
                    "synthesis_2026"
                ),
            },
            self.model_override,
        )

        if not isinstance(
            raw,
            dict,
        ):
            raise TypeError(
                "Le client LLM doit retourner "
                "un objet JSON/dict."
            )

        return json.dumps(
            raw,
            ensure_ascii=False,
        )


# =====================================================
# Public factory
# =====================================================

def make_a_chaud_verbatim_openai_generator_2026(
    *,
    model_override: Optional[str] = None,
    llm_call: LLMJsonCaller2026 = (
        call_llm_extract_json
    ),
) -> AChaudVerbatimOpenAIGenerator2026:
    """
    Build the injectable OpenAI generator.

    No network call occurs during construction.
    """

    return (
        AChaudVerbatimOpenAIGenerator2026(
            model_override=model_override,
            llm_call=llm_call,
        )
    )
