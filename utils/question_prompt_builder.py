# utils/question_prompt_builder.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from utils.question_extraction_tasks import (
    QuestionExtractionTask,
)
from utils.question_registry import (
    DataKind,
)


PROMPT_VERSION = "question-task-v1"


# =====================================================
# Prompt prêt pour llm_client
# =====================================================

@dataclass(frozen=True)
class QuestionTaskPrompt:
    """
    Prompt spécialisé pour UNE tâche d'extraction.

    prompt_master contient les placeholders compris
    par utils.llm_client.call_llm_extract_json :

        {{PDF_METADATA}}
        {{PDF_TEXT}}

    Aucun appel LLM n'est effectué ici.
    """

    task_id: str
    data_kind: DataKind

    prompt_version: str

    prompt_master: str

    metadata: Dict[
        str,
        object,
    ]


# =====================================================
# Règles communes
# =====================================================

COMMON_RULES = """
RÈGLES ABSOLUES

1. Travaille uniquement à partir du TEXTE SOURCE fourni.

2. N'invente aucune donnée.

3. N'utilise aucune connaissance extérieure.

4. Ne complète pas une valeur manquante par déduction.

5. Si une donnée n'est pas explicitement présente,
   utilise null lorsque le schéma l'autorise.

6. Respecte exactement le schéma JSON demandé.

7. N'ajoute aucune clé supplémentaire.

8. Ne renvoie aucun commentaire, aucune explication
   et aucun Markdown.

9. Le texte libre doit rester strictement fidèle
   à la source :
   - aucune reformulation ;
   - aucune correction ;
   - aucune modification de ponctuation.

10. Cette tâche ne concerne qu'un seul chunk.
    N'essaie pas de reconstituer des données situées
    en dehors du TEXTE SOURCE.
""".strip()


# =====================================================
# Distribution 1 -> 5
# =====================================================

DISTRIBUTION_PROMPT = """
OBJECTIF

Extraire une distribution sur une échelle de 1 à 5.

RÈGLES SPÉCIFIQUES

- Retourne toujours exactement les niveaux
  1, 2, 3, 4 et 5 dans cet ordre.

- Pour chaque niveau :
  - nb_votants = nombre explicitement présent ;
  - pourcentage = pourcentage explicitement présent.

- Si l'une de ces valeurs n'est pas explicitement
  disponible, utilise null.

- Ne calcule pas un nombre de votants à partir
  d'un pourcentage.

- Ne calcule pas un pourcentage à partir
  d'un nombre de votants.

- nb_votants au niveau racine correspond uniquement
  au nombre total de répondants explicitement indiqué.

SCHÉMA JSON EXACT

{
  "nb_votants": null,
  "levels": [
    {
      "level": 1,
      "nb_votants": null,
      "pourcentage": null
    },
    {
      "level": 2,
      "nb_votants": null,
      "pourcentage": null
    },
    {
      "level": 3,
      "nb_votants": null,
      "pourcentage": null
    },
    {
      "level": 4,
      "nb_votants": null,
      "pourcentage": null
    },
    {
      "level": 5,
      "nb_votants": null,
      "pourcentage": null
    }
  ]
}
""".strip()


# =====================================================
# Verbatims
# =====================================================

VERBATIMS_PROMPT = """
OBJECTIF

Extraire uniquement les réponses libres des
apprenants correspondant à la question ciblée.

RÈGLES SPÉCIFIQUES

- Chaque item doit être copié exactement depuis
  le TEXTE SOURCE.

- Conserve l'ordre d'apparition dans la source.

- Conserve les doublons lorsqu'ils apparaissent
  réellement plusieurs fois dans le TEXTE SOURCE.

- Ne résume pas.

- Ne reformule pas.

- Ne corrige pas l'orthographe.

- Ne modifie pas les virgules, points,
  apostrophes ou autres signes de ponctuation.

- N'inclus pas :
  - le titre de la question ;
  - les titres de pages ;
  - les intitulés de graphiques ;
  - les modalités de réponse ;
  - les nombres ou pourcentages qui ne sont pas
    eux-mêmes des réponses libres.

- Si aucun verbatim n'est présent dans ce chunk,
  retourne une liste vide.

SCHÉMA JSON EXACT

{
  "items": [
    "verbatim exact 1",
    "verbatim exact 2"
  ]
}
""".strip()


# =====================================================
# Maîtrise des objectifs
# =====================================================

MASTERY_PROMPT = """
OBJECTIF

Extraire les résultats d'auto-évaluation de maîtrise
des objectifs de formation présents dans le
TEXTE SOURCE.

Deux présentations sont possibles :

- "4_niveaux"
- "notes_sur_10"

RÈGLES SPÉCIFIQUES

- Utilise "4_niveaux" uniquement lorsque la source
  présente clairement les quatre modalités :
  totalement, en partie, insuffisamment,
  pas du tout.

- Utilise "notes_sur_10" uniquement lorsque la source
  présente clairement des notes sur 10.

- Si le mode ne peut pas être déterminé de façon
  fiable, utilise null.

- objectif_label doit reprendre exactement le texte
  de l'objectif visible dans la source.

- Pour chaque objectif visible dans ce chunk,
  crée un objet dans par_objectif.

- Ne crée jamais un objectif absent du chunk.

- Pour le mode "4_niveaux" :
  renseigne uniquement les valeurs explicitement
  présentes dans les quatre niveaux et mets
  note_sur_10 à null si elle n'est pas présente.

- Pour le mode "notes_sur_10" :
  renseigne note_sur_10 uniquement lorsqu'elle est
  explicitement présente.
  Les quatre niveaux restent à null s'ils ne sont
  pas présents.

- note_globale_objectifs_preformation correspond
  uniquement à une note globale explicitement
  affichée dans la source.

- Ne calcule aucune moyenne.

- Ne transforme pas des pourcentages en effectifs.

SCHÉMA JSON EXACT

{
  "mode": null,
  "par_objectif": [
    {
      "objectif_label": "texte exact de l'objectif",
      "levels": {
        "totalement": null,
        "en_partie": null,
        "insuffisamment": null,
        "pas_du_tout": null
      },
      "note_sur_10": null
    }
  ],
  "note_globale_objectifs_preformation": null
}
""".strip()


# =====================================================
# Sélection du prompt métier
# =====================================================

def _instructions_for_data_kind(
    data_kind: DataKind,
) -> str:

    if data_kind == "distribution_1_5":
        return DISTRIBUTION_PROMPT

    if data_kind == "verbatims":
        return VERBATIMS_PROMPT

    if data_kind == "maitrise_objectifs":
        return MASTERY_PROMPT

    raise NotImplementedError(
        "Aucun prompt spécialisé pour "
        f"data_kind={data_kind!r}."
    )


# =====================================================
# Métadonnées
# =====================================================

def _build_metadata(
    task: QuestionExtractionTask,
) -> Dict[str, object]:
    """
    Métadonnées destinées à contextualiser
    l'extraction sans modifier le texte source.
    """

    return {
        "prompt_version": (
            PROMPT_VERSION
        ),
        "task_id": (
            task.task_id
        ),
        "occurrence_id": (
            task.occurrence_id
        ),
        "section_key": (
            task.section_key
        ),
        "business_key": (
            task.business_key
        ),
        "business_occurrence_index": (
            task.business_occurrence_index
        ),
        "data_kind": (
            task.data_kind
        ),
        "merge_strategy": (
            task.merge_strategy
        ),
        "matched_prompt": (
            task.matched_prompt
        ),
        "block_start_page": (
            task.block_start_page
        ),
        "block_end_page": (
            task.block_end_page
        ),
        "chunk_index": (
            task.chunk_index
        ),
        "chunk_count": (
            task.chunk_count
        ),
    }


# =====================================================
# Construction publique
# =====================================================

def build_question_task_prompt(
    task: QuestionExtractionTask,
) -> QuestionTaskPrompt:
    """
    Construit le prompt spécialisé d'une tâche.

    Aucun appel OpenAI.
    """

    if not task.text:
        raise ValueError(
            "Impossible de construire un prompt "
            "pour une tâche sans texte : "
            f"{task.task_id}"
        )

    specific_instructions = (
        _instructions_for_data_kind(
            task.data_kind
        )
    )

    prompt_master = f"""
EXTRACTION DOCUMENTAIRE STRICTE

QUESTION MÉTIER CIBLÉE
{{{{PDF_METADATA}}}}

{COMMON_RULES}

{specific_instructions}

TEXTE SOURCE À ANALYSER
--- DÉBUT DU TEXTE SOURCE ---
{{{{PDF_TEXT}}}}
--- FIN DU TEXTE SOURCE ---

Renvoie maintenant uniquement l'objet JSON demandé.
""".strip()

    return QuestionTaskPrompt(
        task_id=task.task_id,
        data_kind=task.data_kind,
        prompt_version=(
            PROMPT_VERSION
        ),
        prompt_master=(
            prompt_master
        ),
        metadata=(
            _build_metadata(
                task
            )
        ),
    )
