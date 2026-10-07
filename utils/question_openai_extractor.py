# utils/question_openai_extractor.py

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Callable,
    Dict,
    Optional,
)

from utils.llm_client import (
    call_llm_extract_json,
)
from utils.question_extraction_tasks import (
    QuestionExtractionTask,
)
from utils.question_prompt_builder import (
    build_question_task_prompt,
)


# =====================================================
# Contrat d'appel LLM injectable
# =====================================================

LLMJsonCaller = Callable[
    [
        str,
        str,
        dict,
        Optional[str],
    ],
    dict,
]


# =====================================================
# Extracteur OpenAI d'une tâche
# =====================================================

@dataclass
class QuestionOpenAIExtractor:
    """
    Adaptateur entre QuestionExtractionTask
    et utils.llm_client.call_llm_extract_json.

    Cette classe :
    - construit le prompt adapté au data_kind ;
    - transmet uniquement le texte du chunk ;
    - transmet les métadonnées de la tâche ;
    - retourne le JSON brut.

    Elle ne parse pas le résultat.
    Elle ne consolide pas les occurrences.

    Ces responsabilités restent dans :
    - question_payload_parser.py
    - question_result_consolidator.py
    """

    model_override: Optional[str] = None

    llm_call: LLMJsonCaller = (
        call_llm_extract_json
    )

    def __call__(
        self,
        task: QuestionExtractionTask,
    ) -> Dict[str, object]:
        """
        Extrait le JSON brut pour UNE tâche.
        """

        built = build_question_task_prompt(
            task
        )

        raw = self.llm_call(
            built.prompt_master,
            task.text,
            built.metadata,
            self.model_override,
        )

        if not isinstance(
            raw,
            dict,
        ):
            raise TypeError(
                "L'extracteur LLM doit retourner "
                "un objet JSON/dict pour "
                f"{task.task_id}. "
                f"Type reçu : "
                f"{type(raw).__name__}"
            )

        return raw


# =====================================================
# Factory publique
# =====================================================

def make_question_openai_extractor(
    *,
    model_override: Optional[str] = None,
    llm_call: LLMJsonCaller = (
        call_llm_extract_json
    ),
) -> QuestionOpenAIExtractor:
    """
    Construit un extracteur injectable.

    En production :

        extractor = (
            make_question_openai_extractor()
        )

    En test :

        extractor = (
            make_question_openai_extractor(
                llm_call=fake_llm_call
            )
        )

    Aucun appel réseau n'est effectué
    au moment de la construction.
    """

    return QuestionOpenAIExtractor(
        model_override=model_override,
        llm_call=llm_call,
    )
