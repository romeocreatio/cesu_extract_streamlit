# utils/question_detector.py

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence, Tuple

from utils.pdf_reader import PdfReadResult
from utils.section_splitter import (
    ReportSection,
    contains_tokens_in_order,
    normalize_for_match,
)


# =====================================================
# Types
# =====================================================

DetectionMethod = Literal[
    "profile_prompt_tokens",
]

ConfidenceLevel = Literal[
    "high",
]


# =====================================================
# Structures publiques
# =====================================================

@dataclass(frozen=True)
class QuestionPattern:
    """
    Formulation connue d'une question de questionnaire.

    Important :
    pattern_id est uniquement un identifiant structurel.

    Ce n'est PAS une business_key.
    Le mapping métier sera réalisé dans une autre brique.
    """

    pattern_id: str

    # Une même question peut avoir plusieurs formulations.
    texts: Tuple[str, ...]

    # Nombre de premiers mots utilisés pour vérifier
    # que nous sommes bien au début plausible de la question.
    prefix_words: int = 3

    # Nombre maximal de lignes dans lesquelles
    # le libellé peut être éclaté par Digiforma.
    window_lines: int = 6


@dataclass(frozen=True)
class QuestionCandidate:
    """
    Début probable d'une question dans le PDF.

    Cette structure ne contient volontairement
    aucune donnée métier.
    """

    candidate_id: str
    section_key: str

    pattern_id: str
    occurrence_index: int

    start_page: int
    start_line: int
    source_order: int

    # Texte réellement extrait du PDF autour
    # du début de la question.
    source_text: str

    # Formulation du profil qui a permis
    # la reconnaissance.
    matched_prompt: str

    detection_method: DetectionMethod
    confidence: ConfidenceLevel


# =====================================================
# Structures internes
# =====================================================

@dataclass(frozen=True)
class _LineRecord:
    """
    Ligne source de la section.
    """

    record_index: int
    page_number: int
    line_number: int
    text: str


@dataclass(frozen=True)
class _RawMatch:
    """
    Match interne avant création des candidats.
    """

    record_index: int
    pattern_order: int
    pattern: QuestionPattern
    matched_prompt: str


# =====================================================
# Profil PRÉFORMATION 2026
# =====================================================
#
# Il s'agit de formulations structurelles observées
# dans les questionnaires CESU/Digiforma 2026.
#
# Ce profil contient aussi des questions qui ne seront
# peut-être jamais exportées dans le Google Sheet.
#
# C'est volontaire :
# elles servent à trouver les vraies frontières entre
# les blocs du questionnaire.
#
# Les business_key restent dans question_registry.py.
# =====================================================

PRE_FORMATION_PATTERNS_2026: Tuple[
    QuestionPattern,
    ...,
] = (

    # -------------------------------------------------
    # Identification / contexte
    # -------------------------------------------------

    QuestionPattern(
        pattern_id="identite",
        texts=(
            "Merci de noter vos nom et prénom",
        ),
        prefix_words=2,
    ),

    QuestionPattern(
        pattern_id="fonction_exercee",
        texts=(
            "Fonction exercée",
            # Certains PDF coupent graphiquement le mot.
            "Fonction e xercée",
        ),
        prefix_words=1,
    ),

    QuestionPattern(
        pattern_id="profession",
        texts=(
            "Quelle est votre profession",
        ),
        prefix_words=3,
    ),

    QuestionPattern(
        pattern_id="anciennete_profession",
        texts=(
            "Depuis combien de temps exercez-vous cette profession",
            "Depuis combien de temps exercez-vous la profession d'ARM",
        ),
        prefix_words=3,
    ),

    QuestionPattern(
        pattern_id="service_travail",
        texts=(
            "Dans quel service travaillez-vous",
            "Dans quels service et établissement travaillez-vous",
            "Dans quel service et établissement travaillez-vous",
        ),
        prefix_words=3,
    ),

    # -------------------------------------------------
    # Origine de l'inscription
    # -------------------------------------------------

    QuestionPattern(
        pattern_id="source_formation",
        texts=(
            "Comment avez vous eu connaissance de la formation",
            "Comment avez-vous eu connaissance de cette formation",
        ),
        prefix_words=3,
    ),

    QuestionPattern(
        pattern_id="inscription_formation",
        texts=(
            "Votre inscription à cette formation",
        ),
        prefix_words=2,
    ),

    QuestionPattern(
        pattern_id="souhait_suivre",
        texts=(
            "Souhaitiez-vous suivre cette formation",
        ),
        prefix_words=2,
    ),

    QuestionPattern(
        pattern_id="fiche_presentation",
        texts=(
            (
                "Avez-vous eu accès à la fiche de présentation "
                "de la formation"
            ),
        ),
        prefix_words=3,
    ),

    # -------------------------------------------------
    # Rapport à la formation
    # -------------------------------------------------

    QuestionPattern(
        pattern_id="confiance_apprentissage",
        texts=(
            (
                "En général, quand vous commencez une formation, "
                "comment vous sentez vous par rapport à vos capacités "
                "à acquérir des compétences connaissances "
                "complémentaires ou nouvelles"
            ),
            (
                "En général, quand vous commencez une formation, "
                "comment vous sentez-vous par rapport à vos capacités "
                "à acquérir des connaissances ou des compétences "
                "complémentaires ou nouvelles"
            ),
        ),
        prefix_words=4,
        window_lines=6,
    ),

    QuestionPattern(
        pattern_id="sentiment_formation_continue",
        texts=(
            (
                "En général, lorsque vous participez à une formation "
                "continue, vous avez le sentiment"
            ),
            (
                "En général quand vous participez à une formation "
                "continue, vous avez le sentiment"
            ),
        ),
        prefix_words=4,
        window_lines=4,
    ),

    QuestionPattern(
        pattern_id="experiences_anterieures",
        texts=(
            (
                "En matière de formation continue, comment est-ce "
                "que vous pourriez qualifier vos expériences antérieures"
            ),
        ),
        prefix_words=4,
        window_lines=4,
    ),

    QuestionPattern(
        pattern_id="attentes_formation",
        texts=(
            "Qu'attendez-vous de la formation d'aujourd'hui",
        ),
        prefix_words=2,
    ),

    # -------------------------------------------------
    # Auto-évaluation des objectifs
    # -------------------------------------------------

    QuestionPattern(
        pattern_id="maitrise_objectifs",
        texts=(
            (
                "À ce jour, considérez-vous maîtriser "
                "les objectifs du programme"
            ),
            (
                "À ce jour, considérez-vous maîtriser "
                "les objectifs de la formation"
            ),
            (
                "Considérez-vous maîtriser les objectifs "
                "du programme"
            ),
            (
                "Considérez-vous maîtriser les objectifs "
                "de la formation"
            ),
        ),
        prefix_words=3,
        window_lines=5,
    ),

    # -------------------------------------------------
    # Evaluation detaillee des competences
    #
    # Question structurelle volontairement non mappee.
    # Elle sert uniquement de frontiere pour terminer
    # correctement le bloc maitrise_objectifs.
    # -------------------------------------------------

    QuestionPattern(
        pattern_id="evaluation_competences_detaillee",
        texts=(
            "Evaluez vos competences",
            "Evaluer vos competences",
        ),
        prefix_words=3,
        window_lines=2,
    ),

    # -------------------------------------------------
    # Attentes / sujets
    # -------------------------------------------------

    QuestionPattern(
        pattern_id="sujets_a_aborder",
        texts=(
            (
                "Quels sont les sujets que vous aimeriez "
                "aborder au cours de la formation"
            ),
            (
                "Par rapport au sujet de la formation, "
                "quels thèmes ou sujets souhaitez vous revoir, "
                "apprendre, aborder"
            ),
        ),
        prefix_words=3,
        window_lines=4,
    ),

    # -------------------------------------------------
    # Handicap / adaptation
    # -------------------------------------------------

    QuestionPattern(
        pattern_id="handicap_signalement",
        texts=(
            (
                "Souhaitez-vous signaler une situation de handicap "
                "qui nécessiterait une adaptation de la formation"
            ),
            (
                "Particularités à signaler au CESU concernant "
                "un handicap dont vous êtes atteint et que vous "
                "souhaitez signaler"
            ),
        ),
        prefix_words=3,
        window_lines=5,
    ),

    QuestionPattern(
        pattern_id="besoin_adaptation",
        texts=(
            (
                "Le cas échéant, quel est votre besoin "
                "en adaptation de la formation"
            ),
        ),
        prefix_words=3,
        window_lines=4,
    ),

    # -------------------------------------------------
    # Questions particulières E-Learning
    # -------------------------------------------------

    QuestionPattern(
        pattern_id="nom_elearning",
        texts=(
            (
                "Quel est le nom du e-learning "
                "qui débute ce jour pour vous"
            ),
        ),
        prefix_words=3,
    ),

    QuestionPattern(
        pattern_id="degre_motivation",
        texts=(
            (
                "Quel est votre degré de motivation "
                "concernant cette formation"
            ),
        ),
        prefix_words=3,
        window_lines=6,
    ),

    QuestionPattern(
        pattern_id="impact_travail",
        texts=(
            (
                "Quel impact doit avoir cette formation "
                "sur votre travail"
            ),
        ),
        prefix_words=2,
        window_lines=5,
    ),

    QuestionPattern(
        pattern_id="motivations_formation",
        texts=(
            (
                "Quelles sont vos motivations "
                "pour cette formation"
            ),
        ),
        prefix_words=3,
        window_lines=4,
    ),

    # -------------------------------------------------
    # Questions particulières à certaines formations
    # -------------------------------------------------

    QuestionPattern(
        pattern_id="perception_defunts",
        texts=(
            (
                "Quelle est ma perception du contact "
                "avec les défunts"
            ),
        ),
        prefix_words=3,
    ),

    QuestionPattern(
        pattern_id="perception_familles_defunts",
        texts=(
            (
                "Quelle est ma perception du contact "
                "avec les familles des défunts"
            ),
        ),
        prefix_words=3,
    ),
)


# =====================================================
# Accès aux profils
# =====================================================

def patterns_for_section(
    section_key: str,
) -> Tuple[QuestionPattern, ...]:
    """
    Retourne le profil structurel disponible
    pour une section.

    Pour l'instant, seule la préformation 2026
    est activée dans cette nouvelle brique.
    """

    if section_key == "pre_formation":
        return PRE_FORMATION_PATTERNS_2026

    return ()


# =====================================================
# Construction des lignes de section
# =====================================================

def _section_line_records(
    result: PdfReadResult,
    section: ReportSection,
) -> List[_LineRecord]:
    """
    Transforme une section en lignes ordonnées.

    Les lignes vides sont ignorées.
    Le texte source n'est pas normalisé.
    """

    records: List[_LineRecord] = []

    record_index = 0

    for page in result.pages[
        section.start_page - 1 : section.end_page
    ]:

        for line_number, line in enumerate(
            page.text.splitlines(),
            start=1,
        ):

            clean = line.strip()

            if not clean:
                continue

            records.append(
                _LineRecord(
                    record_index=record_index,
                    page_number=page.number,
                    line_number=line_number,
                    text=clean,
                )
            )

            record_index += 1

    return records


# =====================================================
# Helpers de matching
# =====================================================

def _tokens_in_order(
    text_tokens: Sequence[str],
    expected_tokens: Sequence[str],
) -> bool:
    """
    Vérifie que expected_tokens apparaît dans le même ordre
    dans text_tokens.

    Des tokens supplémentaires sont autorisés.
    """

    if not expected_tokens:
        return False

    expected_index = 0

    for token in text_tokens:

        if token == expected_tokens[expected_index]:

            expected_index += 1

            if expected_index == len(expected_tokens):
                return True

    return False


def _line_contains_prompt_prefix(
    line_text: str,
    prompt_text: str,
    prefix_words: int,
) -> bool:
    """
    Vérifie que les premiers mots caractéristiques
    du prompt sont présents dans la ligne candidate.

    Ils peuvent apparaître après un petit morceau de texte
    provenant de la mise en page PDF.

    Cela permet par exemple de gérer une question qui
    commence sur la même ligne que la fin du bloc précédent.
    """

    line_tokens = normalize_for_match(
        line_text
    ).split()

    prompt_tokens = normalize_for_match(
        prompt_text
    ).split()

    if not line_tokens or not prompt_tokens:
        return False

    count = min(
        prefix_words,
        len(prompt_tokens),
    )

    prefix = prompt_tokens[:count]

    return _tokens_in_order(
        text_tokens=line_tokens,
        expected_tokens=prefix,
    )


def _window_text(
    records: Sequence[_LineRecord],
    start_index: int,
    window_lines: int,
) -> str:
    """
    Construit une fenêtre de lignes à partir
    d'une position candidate.
    """

    stop_index = min(
        start_index + window_lines,
        len(records),
    )

    return "\n".join(
        record.text
        for record in records[
            start_index:stop_index
        ]
    )


def _matches_prompt_at(
    records: Sequence[_LineRecord],
    start_index: int,
    prompt_text: str,
    prefix_words: int,
    window_lines: int,
) -> bool:
    """
    Vérifie qu'un prompt commence probablement
    à start_index.

    Double contrôle :
        1. son préfixe caractéristique doit apparaître
           sur la ligne de départ ;
        2. l'ensemble du prompt doit être retrouvé
           dans les lignes suivantes, dans le bon ordre.

    Les nombres, pourcentages et scores insérés
    par Digiforma sont donc tolérés.
    """

    record = records[start_index]

    if not _line_contains_prompt_prefix(
        line_text=record.text,
        prompt_text=prompt_text,
        prefix_words=prefix_words,
    ):
        return False

    window = _window_text(
        records=records,
        start_index=start_index,
        window_lines=window_lines,
    )

    return contains_tokens_in_order(
        window,
        prompt_text,
    )


def _capture_source_text(
    records: Sequence[_LineRecord],
    start_index: int,
    prompt_text: str,
    window_lines: int,
) -> str:
    """
    Conserve le plus petit ensemble de lignes permettant
    de retrouver tout le prompt.

    Le texte retourné reste le texte source extrait du PDF.
    """

    max_stop = min(
        start_index + window_lines,
        len(records),
    )

    for stop_index in range(
        start_index + 1,
        max_stop + 1,
    ):

        text = "\n".join(
            record.text
            for record in records[
                start_index:stop_index
            ]
        )

        if contains_tokens_in_order(
            text,
            prompt_text,
        ):
            return text

    return records[start_index].text

def _is_strictly_more_specific_prompt(
    generic_prompt: str,
    specific_prompt: str,
) -> bool:
    """
    Détermine si specific_prompt est une version
    strictement plus précise de generic_prompt.

    Exemple :

        "Quelle est ma perception du contact avec les défunts"

    est contenu, dans le même ordre, dans :

        "Quelle est ma perception du contact avec
         les familles des défunts"

    Le second prompt est donc plus spécifique.

    Cette logique sert uniquement à résoudre
    les conflits lorsque deux patterns différents
    démarrent exactement sur la même ligne source.
    """

    generic_tokens = normalize_for_match(
        generic_prompt
    ).split()

    specific_tokens = normalize_for_match(
        specific_prompt
    ).split()

    if not generic_tokens:
        return False

    if len(specific_tokens) <= len(generic_tokens):
        return False

    return _tokens_in_order(
        text_tokens=specific_tokens,
        expected_tokens=generic_tokens,
    )


# =====================================================
# Détection brute
# =====================================================

def _find_raw_matches(
    records: Sequence[_LineRecord],
    patterns: Sequence[QuestionPattern],
) -> List[_RawMatch]:
    """
    Recherche toutes les occurrences de tous
    les prompts du profil.

    Aucun arrêt après la première occurrence :
    une question peut apparaître 0..N fois.

    Si plusieurs patterns différents correspondent
    exactement au même emplacement source, le pattern
    strictement plus spécifique est privilégié.

    Cela évite par exemple que :

        "contact avec les familles des défunts"

    soit aussi détecté comme :

        "contact avec les défunts"

    Les occurrences situées à des positions différentes
    restent toujours conservées.
    """

    matches: List[_RawMatch] = []

    seen: set[
        tuple[int, str]
    ] = set()

    for pattern_order, pattern in enumerate(
        patterns
    ):

        for record_index in range(
            len(records)
        ):

            matched_prompt: Optional[str] = None

            for prompt_text in pattern.texts:

                if _matches_prompt_at(
                    records=records,
                    start_index=record_index,
                    prompt_text=prompt_text,
                    prefix_words=pattern.prefix_words,
                    window_lines=pattern.window_lines,
                ):
                    matched_prompt = prompt_text
                    break

            if matched_prompt is None:
                continue

            dedupe_key = (
                record_index,
                pattern.pattern_id,
            )

            if dedupe_key in seen:
                continue

            seen.add(dedupe_key)

            matches.append(
                _RawMatch(
                    record_index=record_index,
                    pattern_order=pattern_order,
                    pattern=pattern,
                    matched_prompt=matched_prompt,
                )
            )

    # -------------------------------------------------
    # Résolution des chevauchements au même emplacement
    # -------------------------------------------------
    #
    # Uniquement lorsqu'un autre pattern :
    # - commence exactement sur la même ligne ;
    # - est différent ;
    # - possède un prompt strictement plus spécifique.
    #
    # Les occurrences situées ailleurs dans le document
    # ne sont jamais supprimées.
    # -------------------------------------------------

    filtered_matches: List[
        _RawMatch
    ] = []

    for match in matches:

        shadowed_by_more_specific = False

        for other in matches:

            if other is match:
                continue

            if (
                other.record_index
                != match.record_index
            ):
                continue

            if (
                other.pattern.pattern_id
                == match.pattern.pattern_id
            ):
                continue

            if _is_strictly_more_specific_prompt(
                generic_prompt=(
                    match.matched_prompt
                ),
                specific_prompt=(
                    other.matched_prompt
                ),
            ):
                shadowed_by_more_specific = True
                break

        if not shadowed_by_more_specific:
            filtered_matches.append(
                match
            )

    filtered_matches.sort(
        key=lambda match: (
            match.record_index,
            match.pattern_order,
        )
    )

    return filtered_matches


# =====================================================
# Point d'entrée public
# =====================================================

def detect_question_candidates(
    result: PdfReadResult,
    section: ReportSection,
    patterns: Optional[
        Sequence[QuestionPattern]
    ] = None,
) -> List[QuestionCandidate]:
    """
    Détecte les débuts probables de questions
    dans une section.

    Cette fonction :
        - ne réalise aucun mapping métier ;
        - n'appelle aucune IA ;
        - ne supprime aucune occurrence répétée ;
        - ne dépend d'aucun numéro de page fixe ;
        - conserve l'ordre réel du PDF.

    Si patterns n'est pas fourni, le profil correspondant
    à la section est utilisé.
    """

    selected_patterns = tuple(
        patterns
        if patterns is not None
        else patterns_for_section(
            section.key
        )
    )

    if not selected_patterns:
        return []

    records = _section_line_records(
        result=result,
        section=section,
    )

    if not records:
        return []

    raw_matches = _find_raw_matches(
        records=records,
        patterns=selected_patterns,
    )

    candidates: List[
        QuestionCandidate
    ] = []

    occurrence_counts: dict[
        str,
        int,
    ] = {}

    for source_order, match in enumerate(
        raw_matches,
        start=1,
    ):

        pattern_id = (
            match.pattern.pattern_id
        )

        occurrence_counts[
            pattern_id
        ] = (
            occurrence_counts.get(
                pattern_id,
                0,
            )
            + 1
        )

        occurrence_index = (
            occurrence_counts[
                pattern_id
            ]
        )

        record = records[
            match.record_index
        ]

        source_text = (
            _capture_source_text(
                records=records,
                start_index=(
                    match.record_index
                ),
                prompt_text=(
                    match.matched_prompt
                ),
                window_lines=(
                    match.pattern.window_lines
                ),
            )
        )

        candidates.append(
            QuestionCandidate(
                candidate_id=(
                    f"{section.key}:"
                    f"candidate_{source_order:03d}"
                ),
                section_key=section.key,
                pattern_id=pattern_id,
                occurrence_index=(
                    occurrence_index
                ),
                start_page=(
                    record.page_number
                ),
                start_line=(
                    record.line_number
                ),
                source_order=(
                    source_order
                ),
                source_text=(
                    source_text
                ),
                matched_prompt=(
                    match.matched_prompt
                ),
                detection_method=(
                    "profile_prompt_tokens"
                ),
                confidence="high",
            )
        )

    return candidates
