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
from utils.question_payload_parser import (
    parse_extraction_payload,
)
from utils.question_hybrid_extractor import (
    RecoverableExtractionError,
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
        Extrait le JSON brut pour une seule tache.

        Une indisponibilite du lecteur IA,
        une absence de prompt specialise ou
        une reponse IA non conforme devient
        une erreur recuperable.
        """

        try:
            built = build_question_task_prompt(
                task
            )

        except NotImplementedError as exc:

            raise RecoverableExtractionError(
                "Fallback IA non disponible pour "
                f"{task.task_id}: "
                f"{exc}"
            ) from exc

        try:
            raw = self.llm_call(
                built.prompt_master,
                task.text,
                built.metadata,
                self.model_override,
            )

        except Exception as exc:

            raise RecoverableExtractionError(
                "Fallback IA indisponible pour "
                f"{task.task_id}: "
                f"{type(exc).__name__}: "
                f"{exc}"
            ) from exc

        if not isinstance(
            raw,
            dict,
        ):
            raise RecoverableExtractionError(
                "Fallback IA non conforme pour "
                f"{task.task_id}: "
                "un objet JSON/dict etait attendu, "
                f"type recu={type(raw).__name__}."
            )

        # Validation par le meme parseur type
        # utilise par l'executeur du moteur.
        try:
            parse_extraction_payload(
                data_kind=task.data_kind,
                raw=raw,
            )

        except (
            TypeError,
            ValueError,
        ) as exc:

            raise RecoverableExtractionError(
                "Fallback IA invalide pour "
                f"{task.task_id}: "
                f"{type(exc).__name__}: "
                f"{exc}"
            ) from exc

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
