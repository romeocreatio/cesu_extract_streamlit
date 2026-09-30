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
            "En début de session, est-ce que le programme et les objectifs de la formation ont été clairement annoncés",
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
            "Avez vous pu mettre en pratique les connaissances compétences acquises",
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
            "L'organisation générale de la formation était-elle adaptée",
        ),
        min_signatures=2,
    ),
)


# =====================================================
# Recherche d'un début de section
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
        for index in range(page_index, last_index + 1)
    ]

    return "\n".join(texts)


def _find_section_start(
    result: PdfReadResult,
    rule: SectionRule,
) -> Optional[Tuple[int, List[str]]]:
    """
    Cherche le premier titre candidat qui possède aussi
    suffisamment de signatures caractéristiques.

    Retour :
        (numéro_de_page, signatures_trouvées)

    ou None si aucune section fiable n'est détectée.
    """

    normalized_titles = [
        normalize_for_match(title)
        for title in rule.titles
    ]

    normalized_signatures = [
        (
            signature,
            normalize_for_match(signature),
        )
        for signature in rule.signatures
    ]

    for page_index, page in enumerate(result.pages):

        normalized_page = normalize_for_match(page.text)

        title_found = any(
            title in normalized_page
            for title in normalized_titles
        )

        if not title_found:
            continue

        window_text = _build_confirmation_window(
            result=result,
            page_index=page_index,
            lookahead_pages=1,
        )

        normalized_window = normalize_for_match(window_text)

        matched_signatures = [
            original_signature
            for original_signature, _ in normalized_signatures
            if contains_tokens_in_order(
                normalized_window,
                original_signature,
            )
        ]

        if len(matched_signatures) >= rule.min_signatures:
            return page.number, matched_signatures

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
    2. validation de leur ordre logique ;
    3. calcul automatique de leur page de fin.
    """

    starts: Dict[str, Tuple[int, List[str]]] = {}
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
            missing_sections.append(rule.key)
        else:
            starts[rule.key] = match

    # ---------------------------------------------
    # 2. Contrôle de l'ordre logique
    # ---------------------------------------------

    previous_start = 0

    for rule in SECTION_RULES:

        if rule.key not in starts:
            continue

        start_page, _ = starts[rule.key]

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

    sections: Dict[str, ReportSection] = {}

    for index, rule in enumerate(detected_rules):

        start_page, matched_signatures = starts[rule.key]

        if index + 1 < len(detected_rules):
            next_rule = detected_rules[index + 1]
            next_start_page, _ = starts[next_rule.key]

            end_page = next_start_page - 1
        else:
            end_page = result.page_count

        sections[rule.key] = ReportSection(
            key=rule.key,
            label=rule.label,
            start_page=start_page,
            end_page=end_page,
            matched_signatures=matched_signatures,
        )

    return SectionDetectionResult(
        sections=sections,
        missing_sections=missing_sections,
    )