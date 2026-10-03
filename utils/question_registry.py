# utils/question_registry.py

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Literal, Optional, Tuple


# =====================================================
# Types
# =====================================================

SectionKey = Literal[
    "pre_formation",
    "a_chaud",
    "a_froid",
    "intervenants",
    "resultats_evaluations",
]

DataKind = Literal[
    "distribution_1_5",
    "distribution_categories",
    "distribution_yes_no",
    "score_sur_10",
    "verbatims",
    "maitrise_objectifs",
    "texte",
    "structured",
    "report_metric",
]

MergeStrategy = Literal[
    "aggregate_distribution",
    "aggregate_objective_responses",
    "concat_verbatims",
    "concat_text",
    "structured_merge",
    "collect_occurrences",
]


# =====================================================
# Structure métier
# =====================================================

@dataclass(frozen=True)
class QuestionDefinition:
    """
    Définition stable d'une donnée métier 2026.

    business_key :
        identifiant interne stable du concept métier.

    section_key :
        section Digiforma dans laquelle la donnée
        est normalement recherchée.

    output_paths :
        chemins dans le JSON v2.2 actuel.

    data_kind :
        nature des données attendues.

    merge_strategy :
        stratégie qui sera utilisée plus tard lorsque
        plusieurs occurrences légitimes sont présentes.

    aliases :
        formulations connues de la question.
        Elles servent uniquement à la reconnaissance.
        Le texte original du PDF ne doit jamais être
        remplacé par ces aliases.

    source_keys :
        clés déjà produites par question_splitter.py
        pour les questions reconnues par ancre.

    occurrence_policy :
        toutes les occurrences sont conservées.
        Aucune occurrence n'est écrasée ici.
    """

    business_key: str
    section_key: SectionKey
    output_paths: Tuple[str, ...]
    data_kind: DataKind
    merge_strategy: MergeStrategy

    aliases: Tuple[str, ...] = ()
    source_keys: Tuple[str, ...] = ()

    description: str = ""

    occurrence_policy: Literal["collect_all"] = "collect_all"


# =====================================================
# Normalisation pour la reconnaissance
# =====================================================

_LEADING_NUMBER_RE = re.compile(
    r"^\s*\d{1,3}\s*[\.\)\-:]\s*"
)


def normalize_question_text(text: str) -> str:
    """
    Normalise uniquement pour comparer les libellés.

    Important :
    cette fonction ne doit jamais être utilisée
    pour modifier le texte source conservé dans
    les verbatims ou dans les occurrences.
    """

    if not text:
        return ""

    value = str(text).strip()

    # Exemple :
    # "27. Donnez..." -> "Donnez..."
    value = _LEADING_NUMBER_RE.sub("", value)

    value = (
        value.replace("’", "'")
        .replace("‘", "'")
        .replace("–", "-")
        .replace("—", "-")
        .replace("\u00a0", " ")
    )

    # Suppression des accents uniquement pour le matching.
    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        char
        for char in value
        if not unicodedata.combining(char)
    )

    value = value.lower()

    # Ponctuation -> espaces.
    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    value = re.sub(r"\s+", " ", value)

    return value.strip()


# =====================================================
# Registre métier 2026
# =====================================================

QUESTION_REGISTRY: Tuple[QuestionDefinition, ...] = (

    # -------------------------------------------------
    # PRÉFORMATION
    # -------------------------------------------------

    QuestionDefinition(
        business_key="pre_formation.volonte_suivi",
        section_key="pre_formation",
        output_paths=(
            "pre_formation.volonte_suivi_formation",
            "pre_formation.souhaitez_vous_suivre_distribution",
        ),
        data_kind="distribution_1_5",
        merge_strategy="aggregate_distribution",
        aliases=(
            "Souhaitiez-vous suivre cette formation ?",
        ),
        description=(
            "Volonté de suivre la formation et distribution "
            "des réponses sur l'échelle 1 à 5."
        ),
    ),

    QuestionDefinition(
        business_key="pre_formation.sujets_a_aborder",
        section_key="pre_formation",
        output_paths=(
            "pre_formation.demande_sujets_a_aborder",
        ),
        data_kind="verbatims",
        merge_strategy="concat_verbatims",
        aliases=(
            "Quels sont les sujets que vous aimeriez aborder au cours de la formation ?",
            (
                "Par rapport au sujet de la formation, quels thèmes ou sujets "
                "souhaitez vous revoir, apprendre, aborder ?"
            ),
        ),
        description=(
            "Sujets, thèmes ou attentes exprimés avant la formation."
        ),
    ),

    QuestionDefinition(
        business_key="pre_formation.maitrise_objectifs",
        section_key="pre_formation",
        output_paths=(
            "pre_formation.maitrise_objectifs_preformation",
        ),
        data_kind="maitrise_objectifs",
        merge_strategy="aggregate_objective_responses",
        aliases=(
            "À ce jour, considérez-vous maîtriser les objectifs du programme ?",
            "À ce jour, considérez-vous maîtriser les objectifs de la formation ?",
            "Considérez-vous maîtriser les objectifs du programme ?",
            "Considérez-vous maîtriser les objectifs de la formation ?",
        ),
        description=(
            "Auto-évaluation de la maîtrise des objectifs "
            "avant la formation."
        ),
    ),

    # -------------------------------------------------
    # À CHAUD
    # -------------------------------------------------

    QuestionDefinition(
        business_key="a_chaud.formation_profitable",
        section_key="a_chaud",
        output_paths=(
            "a_chaud.formation_profitable",
        ),
        data_kind="distribution_yes_no",
        merge_strategy="aggregate_distribution",
        aliases=(
            "Pensez-vous que cette formation vous a été profitable ?",
        ),
        source_keys=(
            "formation_profitable",
        ),
    ),

    QuestionDefinition(
        business_key="a_chaud.satisfaction_contenu",
        section_key="a_chaud",
        output_paths=(
            "a_chaud.satisfaction_contenu",
        ),
        data_kind="distribution_categories",
        merge_strategy="aggregate_distribution",
        aliases=(
            "Par rapport à l'idée que vous aviez du contenu, vous êtes plutôt ?",
        ),
        source_keys=(
            "satisfaction_contenu",
        ),
    ),

    QuestionDefinition(
        business_key="a_chaud.note_globale",
        section_key="a_chaud",
        output_paths=(
            "a_chaud.note_globale_a_chaud",
        ),
        data_kind="score_sur_10",
        merge_strategy="collect_occurrences",
        aliases=(
            "Donnez une note de 0 à 10 sur l'impression que vous laisse cette formation ?",
        ),
        source_keys=(
            "note_impression",
        ),
        description=(
            "Note générale à chaud. Si plusieurs occurrences "
            "existent, elles sont d'abord conservées séparément."
        ),
    ),

    QuestionDefinition(
        business_key="a_chaud.points_forts",
        section_key="a_chaud",
        output_paths=(
            "a_chaud.points_forts",
        ),
        data_kind="verbatims",
        merge_strategy="concat_verbatims",
        aliases=(
            "Quels sont les points forts de la formation ?",
        ),
        source_keys=(
            "points_forts",
        ),
    ),

    QuestionDefinition(
        business_key="a_chaud.points_a_ajuster",
        section_key="a_chaud",
        output_paths=(
            "a_chaud.points_a_ajuster",
        ),
        data_kind="verbatims",
        merge_strategy="concat_verbatims",
        aliases=(
            "Quels sont les points à ajuster sur cette formation ?",
        ),
        source_keys=(
            "points_ajuster",
        ),
    ),

    QuestionDefinition(
        business_key="a_chaud.suggestions_complement",
        section_key="a_chaud",
        output_paths=(
            "a_chaud.suggestions_complement_sur_formation",
        ),
        data_kind="verbatims",
        merge_strategy="concat_verbatims",
        aliases=(
            "Vos suggestions de complément à cette formation ?",
        ),
        source_keys=(
            "suggestions_complement",
        ),
    ),

    QuestionDefinition(
        business_key="a_chaud.appreciations_intervenants",
        section_key="a_chaud",
        output_paths=(
            "a_chaud.appreciations_intervenants",
        ),
        data_kind="verbatims",
        merge_strategy="concat_verbatims",
        aliases=(
            (
                "En quelques mots, quelles sont les appréciations "
                "que vous donneriez sur le-les intervenant-s ?"
            ),
        ),
        source_keys=(
            "appreciation_intervenants",
        ),
    ),

    QuestionDefinition(
        business_key="a_chaud.maitrise_objectifs",
        section_key="a_chaud",
        output_paths=(
            "a_chaud.maitrise_objectifs_a_chaud",
        ),
        data_kind="maitrise_objectifs",
        merge_strategy="aggregate_objective_responses",
        aliases=(
            "À ce jour, considérez-vous maîtriser les objectifs du programme ?",
            "À ce jour, considérez-vous maîtriser les objectifs de la formation ?",
            "Considérez-vous maîtriser les objectifs du programme ?",
            "Considérez-vous maîtriser les objectifs de la formation ?",
        ),
        source_keys=(
            "maitrise_objectifs",
        ),
    ),

    # -------------------------------------------------
    # À FROID
    # -------------------------------------------------

    QuestionDefinition(
        business_key="a_froid.note_globale",
        section_key="a_froid",
        output_paths=(
            "a_froid.note_sur_10",
        ),
        data_kind="score_sur_10",
        merge_strategy="collect_occurrences",
        aliases=(
            (
                "Quelle note sur 10 donneriez-vous à cette formation ? "
                "(0/10 = pas bon - 10/10 = au top)"
            ),
            "Quelle note sur 10 donneriez-vous à cette formation ?",
        ),
        source_keys=(
            "note_finale",
        ),
    ),

    QuestionDefinition(
        business_key="a_froid.maitrise_objectifs",
        section_key="a_froid",
        output_paths=(
            "a_froid.maitrise_objectifs_a_froid",
        ),
        data_kind="maitrise_objectifs",
        merge_strategy="aggregate_objective_responses",
        aliases=(
            "À ce jour, considérez-vous maîtriser les objectifs du programme ?",
            "À ce jour, considérez-vous maîtriser les objectifs de la formation ?",
            "Considérez-vous maîtriser les objectifs du programme ?",
            "Considérez-vous maîtriser les objectifs de la formation ?",
        ),
        source_keys=(
            "maitrise_objectifs",
        ),
    ),

    QuestionDefinition(
        business_key="a_froid.elements_utiles",
        section_key="a_froid",
        output_paths=(
            "a_froid.elements_les_plus_utiles",
        ),
        data_kind="verbatims",
        merge_strategy="concat_verbatims",
        aliases=(
            "Quels sont avec le recul les éléments les plus utiles de la formation ?",
        ),
        source_keys=(
            "elements_utiles",
        ),
    ),

    # -------------------------------------------------
    # INTERVENANTS
    # -------------------------------------------------

    QuestionDefinition(
        business_key="intervenants.commentaire_conditions_materielles",
        section_key="intervenants",
        output_paths=(
            "intervenants.commentaire_conditions_materielles",
        ),
        data_kind="texte",
        merge_strategy="concat_text",
        aliases=(
            "Commentaire sur les conditions matérielles",
        ),
        source_keys=(
            "commentaire_conditions",
        ),
    ),

    QuestionDefinition(
        business_key="intervenants.commentaire_groupe_apprenants",
        section_key="intervenants",
        output_paths=(
            "intervenants.commentaire_groupe_apprenants",
        ),
        data_kind="texte",
        merge_strategy="concat_text",
        aliases=(
            "Commentaire sur le groupe d'apprenant",
        ),
        source_keys=(
            "commentaire_groupe",
        ),
    ),

    QuestionDefinition(
        business_key="intervenants.commentaire_organisation_generale",
        section_key="intervenants",
        output_paths=(
            "intervenants.commentaire_organisation_generale",
        ),
        data_kind="texte",
        merge_strategy="concat_text",
        aliases=(
            "Commentaire sur l'organisation générale de la formation",
        ),
        source_keys=(
            "commentaire_organisation",
        ),
    ),

    QuestionDefinition(
        business_key="intervenants.adaptation_horaires",
        section_key="intervenants",
        output_paths=(
            "intervenants.adaptation_horaires",
        ),
        data_kind="structured",
        merge_strategy="structured_merge",
        aliases=(
            (
                "As-tu eu à adapter les horaires de début fin de formation "
                "et les pauses aux besoins des apprenants"
            ),
        ),
        source_keys=(
            "adaptation_horaires",
        ),
    ),

    QuestionDefinition(
        business_key="intervenants.precisions_a_noter",
        section_key="intervenants",
        output_paths=(
            "intervenants.precisions_a_noter",
        ),
        data_kind="texte",
        merge_strategy="concat_text",
        aliases=(
            "Précisions à noter ici",
        ),
        source_keys=(
            "precisions",
        ),
    ),

    QuestionDefinition(
        business_key="intervenants.explication_modification_programme",
        section_key="intervenants",
        output_paths=(
            "intervenants.explication_modification_programme",
        ),
        data_kind="texte",
        merge_strategy="concat_text",
        aliases=(
            (
                "Merci d'expliquer quoi pourquoi comment s'est fait cette "
                "annulation modification adaptation d'une partie du programme"
            ),
        ),
        source_keys=(
            "explication_modification",
        ),
    ),

    QuestionDefinition(
        business_key="intervenants.contenu_non_prevu",
        section_key="intervenants",
        output_paths=(
            "intervenants.contenu_non_prevu",
        ),
        data_kind="structured",
        merge_strategy="structured_merge",
        aliases=(
            (
                "As-tu traité un contenu non prévu-e au programme suite au "
                "besoin d'un apprenant ou du groupe ou une question"
            ),
            "De quoi s'agissait-il",
        ),
        source_keys=(
            "contenu_non_prevu",
            "contenu_non_prevu_detail",
        ),
    ),

    QuestionDefinition(
        business_key="intervenants.retards_apprenants",
        section_key="intervenants",
        output_paths=(
            "intervenants.retards_apprenants",
        ),
        data_kind="distribution_yes_no",
        merge_strategy="aggregate_distribution",
        aliases=(
            (
                "Avez-vous eu des retards d'apprenant(s) "
                "au cours de cette session"
            ),
        ),
        source_keys=(
            "retards",
        ),
    ),

    QuestionDefinition(
        business_key="intervenants.handicap_signale",
        section_key="intervenants",
        output_paths=(
            "intervenants.handicap_signale",
        ),
        data_kind="distribution_yes_no",
        merge_strategy="aggregate_distribution",
        aliases=(
            (
                "Est-ce qu'un(e) apprenant(e) t'a signalé être "
                "en situation de handicap temporaire"
            ),
        ),
        source_keys=(
            "handicap_signale",
        ),
    ),

    # -------------------------------------------------
    # RÉSULTATS / PROGRESSION
    # -------------------------------------------------

    QuestionDefinition(
        business_key="resultats.progression_competences",
        section_key="resultats_evaluations",
        output_paths=(
            "resultats_evaluations.progression_competences_plus_sur_10",
        ),
        data_kind="report_metric",
        merge_strategy="collect_occurrences",
        aliases=(
            "PROGRESSION DES COMPÉTENCES",
            "PROGRESSION DES COMPETENCES",
        ),
        description=(
            "Indicateur +X.XX/10 de progression des compétences. "
            "Ce n'est pas une question apprenant classique."
        ),
    ),
)


# =====================================================
# Accès au registre
# =====================================================

def get_question_definition(
    business_key: str,
) -> Optional[QuestionDefinition]:
    """
    Retourne une définition à partir de sa clé métier.
    """

    for definition in QUESTION_REGISTRY:
        if definition.business_key == business_key:
            return definition

    return None


def definitions_for_section(
    section_key: SectionKey,
) -> Tuple[QuestionDefinition, ...]:
    """
    Retourne toutes les définitions d'une section.
    """

    return tuple(
        definition
        for definition in QUESTION_REGISTRY
        if definition.section_key == section_key
    )


def find_by_source_key(
    section_key: SectionKey,
    source_key: str,
) -> Optional[QuestionDefinition]:
    """
    Recherche une définition à partir d'une clé déjà
    produite par question_splitter.py.
    """

    for definition in definitions_for_section(section_key):

        if source_key in definition.source_keys:
            return definition

    return None


def match_known_question(
    section_key: SectionKey,
    question_text: str,
) -> Optional[QuestionDefinition]:
    """
    Essaie de rattacher un libellé à une définition connue.

    Stratégie volontairement conservatrice :
    1. égalité après normalisation ;
    2. le libellé détecté commence par un alias connu.

    Pas de fuzzy matching.
    Pas d'IA.
    Une formulation non reconnue retourne None.
    """

    candidate = normalize_question_text(question_text)

    if not candidate:
        return None

    # 1. Correspondance exacte.
    for definition in definitions_for_section(section_key):

        for alias in definition.aliases:

            normalized_alias = normalize_question_text(alias)

            if candidate == normalized_alias:
                return definition

    # 2. Alias connu suivi d'un complément.
    for definition in definitions_for_section(section_key):

        for alias in definition.aliases:

            normalized_alias = normalize_question_text(alias)

            if not normalized_alias:
                continue

            if candidate.startswith(normalized_alias + " "):
                return definition

    return None


# =====================================================
# Validation interne
# =====================================================

def validate_registry() -> None:
    """
    Vérifie les incohérences déterministes du registre.

    Détecte :
    - business_key dupliquée ;
    - alias identique associé à deux concepts différents
      dans la même section ;
    - source_key identique associée à deux concepts
      différents dans la même section.
    """

    seen_business_keys: set[str] = set()

    seen_aliases: dict[
        tuple[str, str],
        str,
    ] = {}

    seen_source_keys: dict[
        tuple[str, str],
        str,
    ] = {}

    for definition in QUESTION_REGISTRY:

        if definition.business_key in seen_business_keys:
            raise ValueError(
                "business_key dupliquée : "
                f"{definition.business_key}"
            )

        seen_business_keys.add(
            definition.business_key
        )

        for alias in definition.aliases:

            normalized_alias = normalize_question_text(alias)

            key = (
                definition.section_key,
                normalized_alias,
            )

            previous = seen_aliases.get(key)

            if (
                previous is not None
                and previous != definition.business_key
            ):
                raise ValueError(
                    "Alias ambigu dans la section "
                    f"{definition.section_key!r} : "
                    f"{alias!r} -> "
                    f"{previous!r} / "
                    f"{definition.business_key!r}"
                )

            seen_aliases[key] = definition.business_key

        for source_key in definition.source_keys:

            key = (
                definition.section_key,
                source_key,
            )

            previous = seen_source_keys.get(key)

            if (
                previous is not None
                and previous != definition.business_key
            ):
                raise ValueError(
                    "source_key ambigu dans la section "
                    f"{definition.section_key!r} : "
                    f"{source_key!r} -> "
                    f"{previous!r} / "
                    f"{definition.business_key!r}"
                )

            seen_source_keys[key] = definition.business_key