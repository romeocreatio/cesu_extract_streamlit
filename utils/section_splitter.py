# utils/section_splitter.py

from dataclasses import dataclass
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

from utils.pdf_reader import PdfReadResult


# =====================================================
# Structures de données
# =====================================================

@dataclass(frozen=True)
class SectionRule:
    """
    Règle utilisée pour reconnaître le début réel
    d'une section dans un rapport Digiforma.
    """

    key: str
    label: str
    titles: Tuple[str, ...]
    signatures: Tuple[str, ...]
    min_signatures: int


@dataclass
class ReportSection:
    """
    Section réellement détectée dans le PDF.
    """

    key: str
    label: str
    start_page: int
    end_page: int
    matched_signatures: List[str]

    @property
    def page_count(self) -> int:
        return self.end_page - self.start_page + 1


@dataclass
class SectionDetectionResult:
    """
    Résultat complet de la détection des sections.
    """

    sections: Dict[str, ReportSection]
    missing_sections: List[str]

    def get(self, key: str) -> Optional[ReportSection]:
        return self.sections.get(key)


# =====================================================
# Normalisation utilisée uniquement pour la détection
# =====================================================

def normalize_for_match(text: str) -> str:
    """
    Produit une version normalisée du texte uniquement
    pour rechercher des titres et des signatures.

    Le texte original du PDF n'est jamais modifié.
    """

    text = unicodedata.normalize("NFKD", text)

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )

    text = text.lower()

    # Uniformisation des apostrophes
    text = re.sub(r"[’'`´]", " ", text)

    # Ponctuation et séparateurs deviennent des espaces
    text = re.sub(r"[^a-z0-9]+", " ", text)

    # Suppression des espaces multiples
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def contains_tokens_in_order(
    text: str,
    expected: str,
) -> bool:
    """
    Vérifie que les mots d'une signature apparaissent
    dans le même ordre dans le texte, même si Digiforma
    insère d'autres éléments entre eux.

    Exemple :

    signature :
        "les conditions materielles etaient adaptees"

    texte :
        "les conditions 9 8 totalement
         materielles etaient 10 adaptees"

    => True
    """

    text_tokens = normalize_for_match(text).split()
    expected_tokens = normalize_for_match(expected).split()

    if not expected_tokens:
        return False

    expected_index = 0

    for token in text_tokens:

        if token == expected_tokens[expected_index]:
            expected_index += 1

            if expected_index == len(expected_tokens):
                return True

    return False


# =====================================================
# Règles métier 2026
# =====================================================

SECTION_RULES: Tuple[SectionRule, ...] = (

    SectionRule(
        key="pre_formation",
        label="Évaluation préformation",
        titles=(
            "ÉVALUATION PRÉFORMATION POUR LES APPRENANTS",
            "ÉVALUATION PRÉ-FORMATION POUR LES APPRENANTS",
        ),
        signatures=(
            "Comment avez vous eu connaissance de la formation",
            "Votre inscription à cette formation",
            "Souhaitiez-vous suivre cette formation",
        ),
        min_signatures=2,
    ),

    SectionRule(
        key="a_chaud",
        label="Évaluation à chaud",
        titles=(
            "ÉVALUATION À CHAUD POUR LES APPRENANTS",
        ),
        signatures=(
            "Pensez-vous que cette formation vous a été profitable",
            "Par rapport à l'idée que vous aviez du contenu, vous êtes plutôt",
            "Y a-t-il des thèmes indispensables qui n'ont pas été traités",
            "La formation vous a-t-elle apporté des connaissances",
            "L'accueil en formation a été",
            (
                "En début de session, est-ce que le programme "
                "et les objectifs de la formation ont été "
                "clairement annoncés"
            ),
        ),
        min_signatures=2,
    ),

    SectionRule(
        key="a_froid",
        label="Évaluation à froid",
        titles=(
            "ÉVALUATION À FROID POUR LES APPRENANTS",
        ),
        signatures=(
            (
                "Avez vous pu mettre en pratique les "
                "connaissances compétences acquises"
            ),
        ),
        min_signatures=1,
    ),

    SectionRule(
        key="intervenants",
        label="Questionnaire intervenants",
        titles=(
            "QUESTIONNAIRE POUR LES INTERVENANTS",
        ),
        signatures=(
            "Les conditions matérielles étaient adaptées",
            "Le groupe d'apprenant était-il adapté",
            (
                "L'organisation générale de la formation "
                "était-elle adaptée"
            ),
        ),
        min_signatures=2,
    ),
)


# =====================================================
# Helpers titres de sections
# =====================================================

def _normalized_rule_titles(
    rule: SectionRule,
) -> Tuple[str, ...]:
    """
    Retourne les titres normalisés d'une règle.
    """

    return tuple(
        normalize_for_match(title)
        for title in rule.titles
    )


def _page_contains_rule_title(
    page_text: str,
    rule: SectionRule,
) -> bool:
    """
    Vérifie si une page contient un des titres
    associés à une section.

    Deux méthodes sont utilisées :

    1. recherche directe du titre normalisé ;
    2. recherche des mots du titre dans le bon ordre.

    La seconde méthode permet de tolérer les valeurs
    ajoutées par Digiforma au milieu d'un titre.

    Exemple :

        ÉVALUATION PRÉFORMATION POUR LES 6.5
        / 10
        APPRENANTS

    doit tout de même correspondre à :

        ÉVALUATION PRÉFORMATION POUR LES APPRENANTS
    """

    normalized_page = normalize_for_match(
        page_text
    )

    for title in rule.titles:

        normalized_title = normalize_for_match(
            title
        )

        # Cas simple : titre présent tel quel.
        if normalized_title in normalized_page:
            return True

        # Cas Digiforma : score ou autre élément
        # inséré entre les mots du titre.
        if contains_tokens_in_order(
            page_text,
            title,
        ):
            return True

    return False

def _count_section_titles_on_page(
    page_text: str,
) -> int:
    """
    Compte le nombre de sections différentes dont
    le titre apparaît sur une page.

    Une page de synthèse Digiforma contient souvent
    plusieurs titres de sections :

        ÉVALUATION PRÉFORMATION
        ÉVALUATION À CHAUD
        ÉVALUATION À FROID
        QUESTIONNAIRE INTERVENANTS

    Elle ne doit pas être interprétée comme le début
    réel d'une de ces sections.
    """

    count = 0

    for rule in SECTION_RULES:

        if _page_contains_rule_title(
            page_text=page_text,
            rule=rule,
        ):
            count += 1

    return count


def _is_summary_like_page(
    page_text: str,
) -> bool:
    """
    Considère une page comme une page de synthèse
    lorsqu'elle contient les titres d'au moins
    deux sections différentes.

    Cette règle est volontairement conservatrice.
    """

    return (
        _count_section_titles_on_page(
            page_text
        )
        >= 2
    )


def _find_title_candidate_indexes(
    result: PdfReadResult,
    rule: SectionRule,
) -> List[int]:
    """
    Retourne tous les index de pages contenant
    le titre d'une section.

    Les index retournés sont basés sur 0.
    """

    candidates: List[int] = []

    for page_index, page in enumerate(
        result.pages
    ):

        if _page_contains_rule_title(
            page_text=page.text,
            rule=rule,
        ):
            candidates.append(page_index)

    return candidates


# =====================================================
# Fenêtre de confirmation
# =====================================================

def _build_confirmation_window(
    result: PdfReadResult,
    page_index: int,
    lookahead_pages: int = 1,
) -> str:
    """
    Construit une petite fenêtre de texte contenant
    la page candidate et éventuellement la page suivante.

    On ne regarde volontairement pas trop loin pour éviter
    qu'un titre présent dans la synthèse soit confirmé par
    la vraie section située plusieurs pages plus tard.
    """

    last_index = min(
        page_index + lookahead_pages,
        result.page_count - 1,
    )

    texts = [
        result.pages[index].text
        for index in range(
            page_index,
            last_index + 1,
        )
    ]

    return "\n".join(texts)


def _match_rule_signatures(
    text: str,
    rule: SectionRule,
) -> List[str]:
    """
    Retourne les signatures métier reconnues
    dans un texte.

    Le texte original n'est jamais modifié.
    """

    matched: List[str] = []

    for signature in rule.signatures:

        if contains_tokens_in_order(
            text,
            signature,
        ):
            matched.append(signature)

    return matched


# =====================================================
# Confirmation structurelle d'un titre
# =====================================================

def _has_earlier_summary_occurrence(
    result: PdfReadResult,
    rule: SectionRule,
    candidate_index: int,
    title_candidate_indexes: List[int],
) -> bool:
    """
    Vérifie si le même titre de section est déjà apparu
    auparavant sur une page ressemblant à une synthèse.

    Exemple Hemoc-DIV :

        page 1 :
            synthèse avec plusieurs titres de sections

        page 3 :
            vrai début de la préformation

    La présence du titre dans la synthèse puis une
    seconde fois sur une page dédiée constitue un
    signal structurel fort.

    Cette règle ne dépend ni du nom de la formation
    ni d'un numéro de page fixe.
    """

    for previous_index in title_candidate_indexes:

        if previous_index >= candidate_index:
            break

        if _is_summary_like_page(
            result.pages[
                previous_index
            ].text
        ):
            return True

    return False


# =====================================================
# Recherche d'un début de section
# =====================================================

def _find_section_start(
    result: PdfReadResult,
    rule: SectionRule,
) -> Optional[Tuple[int, List[str]]]:
    """
    Cherche le début réel d'une section.

    Deux niveaux de validation sont utilisés.

    Niveau 1 — confirmation métier
        Le titre est présent sur une page non synthétique
        et suffisamment de signatures métier sont trouvées
        sur cette page ou la suivante.

    Niveau 2 — confirmation structurelle
        Si les signatures classiques sont absentes ou trop
        éloignées, le titre peut tout de même être validé
        lorsqu'il réapparaît après une occurrence du même
        titre sur une page de synthèse.

    Le niveau 2 permet notamment de gérer des questionnaires
    2026 dont la structure diffère du questionnaire classique,
    sans coder de règle spécifique à une formation.
    """

    title_candidate_indexes = (
        _find_title_candidate_indexes(
            result=result,
            rule=rule,
        )
    )

    if not title_candidate_indexes:
        return None

    # -------------------------------------------------
    # 1. Confirmation métier classique
    # -------------------------------------------------

    for page_index in title_candidate_indexes:

        page = result.pages[
            page_index
        ]

        # Une page regroupant plusieurs titres de
        # sections est considérée comme une synthèse.
        if _is_summary_like_page(
            page.text
        ):
            continue

        window_text = _build_confirmation_window(
            result=result,
            page_index=page_index,
            lookahead_pages=1,
        )

        matched_signatures = (
            _match_rule_signatures(
                text=window_text,
                rule=rule,
            )
        )

        if (
            len(matched_signatures)
            >= rule.min_signatures
        ):
            return (
                page.number,
                matched_signatures,
            )

    # -------------------------------------------------
    # 2. Confirmation structurelle
    # -------------------------------------------------
    #
    # Certaines formations n'utilisent pas immédiatement
    # les questions classiques après le titre.
    #
    # On accepte alors un titre non synthétique seulement
    # si le même titre est déjà apparu auparavant sur une
    # vraie page de synthèse.
    #
    # Cela évite de simplement accepter n'importe quelle
    # occurrence isolée du titre.
    # -------------------------------------------------

    for page_index in title_candidate_indexes:

        page = result.pages[
            page_index
        ]

        if _is_summary_like_page(
            page.text
        ):
            continue

        if not _has_earlier_summary_occurrence(
            result=result,
            rule=rule,
            candidate_index=page_index,
            title_candidate_indexes=(
                title_candidate_indexes
            ),
        ):
            continue

        # On conserve les éventuelles signatures déjà
        # présentes, même si leur nombre est inférieur
        # au seuil classique.
        window_text = _build_confirmation_window(
            result=result,
            page_index=page_index,
            lookahead_pages=1,
        )

        matched_signatures = (
            _match_rule_signatures(
                text=window_text,
                rule=rule,
            )
        )

        return (
            page.number,
            matched_signatures,
        )

    return None


# =====================================================
# Détection globale
# =====================================================

def detect_sections(
    result: PdfReadResult,
) -> SectionDetectionResult:
    """
    Détecte les grandes sections du rapport.

    Étapes :
        1. recherche indépendante de chaque section ;
        2. exclusion des pages de synthèse ;
        3. validation métier ou structurelle ;
        4. validation de l'ordre logique ;
        5. calcul automatique des pages de fin.
    """

    starts: Dict[
        str,
        Tuple[int, List[str]],
    ] = {}

    missing_sections: List[str] = []

    # ---------------------------------------------
    # 1. Recherche des débuts
    # ---------------------------------------------

    for rule in SECTION_RULES:

        match = _find_section_start(
            result=result,
            rule=rule,
        )

        if match is None:
            missing_sections.append(
                rule.key
            )
        else:
            starts[
                rule.key
            ] = match

    # ---------------------------------------------
    # 2. Contrôle de l'ordre logique
    # ---------------------------------------------

    previous_start = 0

    for rule in SECTION_RULES:

        if rule.key not in starts:
            continue

        start_page, _ = starts[
            rule.key
        ]

        if start_page <= previous_start:
            raise ValueError(
                "Ordre incohérent des sections détectées : "
                f"{rule.key} commence page {start_page}."
            )

        previous_start = start_page

    # ---------------------------------------------
    # 3. Construction des plages
    # ---------------------------------------------

    detected_rules = [
        rule
        for rule in SECTION_RULES
        if rule.key in starts
    ]

    sections: Dict[
        str,
        ReportSection,
    ] = {}

    for index, rule in enumerate(
        detected_rules
    ):

        start_page, matched_signatures = (
            starts[
                rule.key
            ]
        )

        if index + 1 < len(
            detected_rules
        ):
            next_rule = (
                detected_rules[
                    index + 1
                ]
            )

            next_start_page, _ = (
                starts[
                    next_rule.key
                ]
            )

            end_page = (
                next_start_page - 1
            )

        else:
            end_page = (
                result.page_count
            )

        sections[
            rule.key
        ] = ReportSection(
            key=rule.key,
            label=rule.label,
            start_page=start_page,
            end_page=end_page,
            matched_signatures=(
                matched_signatures
            ),
        )

    return SectionDetectionResult(
        sections=sections,
        missing_sections=(
            missing_sections
        ),
    )