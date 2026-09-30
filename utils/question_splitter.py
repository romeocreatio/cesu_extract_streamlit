# utils/question_splitter.py

from dataclasses import dataclass
import re
from typing import List, Tuple

from utils.pdf_reader import PdfReadResult
from utils.section_splitter import (
    ReportSection,
    contains_tokens_in_order,
    normalize_for_match,
)


# =====================================================
# Structures de données
# =====================================================

@dataclass
class QuestionBlock:
    """
    Bloc correspondant à une question numérotée
    et à tout son contenu jusqu'à la question suivante.
    """

    number: int
    title: str
    start_page: int
    end_page: int
    text: str

    @property
    def page_count(self) -> int:
        return self.end_page - self.start_page + 1

    @property
    def char_count(self) -> int:
        return len(self.text)


@dataclass(frozen=True)
class QuestionAnchor:
    """
    Ancre métier permettant de reconnaître une question
    lorsqu'elle n'est pas numérotée dans le PDF.
    """

    key: str
    text: str


@dataclass
class AnchoredQuestionBlock:
    """
    Bloc correspondant à une question reconnue
    grâce à son libellé métier.
    """

    key: str
    title: str
    start_page: int
    end_page: int
    text: str

    @property
    def page_count(self) -> int:
        return self.end_page - self.start_page + 1

    @property
    def char_count(self) -> int:
        return len(self.text)


@dataclass
class _LineRecord:
    """
    Ligne interne utilisée pendant le découpage.
    """

    page_number: int
    text: str


# =====================================================
# Ancres métier connues — section À CHAUD
# =====================================================

A_CHAUD_ANCHORS: Tuple[QuestionAnchor, ...] = (

    QuestionAnchor(
        key="formation_profitable",
        text="Pensez-vous que cette formation vous a été profitable",
    ),

    QuestionAnchor(
        key="satisfaction_contenu",
        text="Par rapport à l'idée que vous aviez du contenu, vous êtes plutôt",
    ),

    QuestionAnchor(
        key="themes_non_traites",
        text="Y a-t-il des thèmes indispensables qui n'ont pas été traités",
    ),

    QuestionAnchor(
        key="apport_connaissances",
        text="La formation vous a-t-elle apporté des connaissances",
    ),

    QuestionAnchor(
        key="maitrise_objectifs",
        text="À ce jour, considérez-vous maîtriser les objectifs du programme",
    ),

    QuestionAnchor(
        key="transfert_pratique",
        text="Pensez-vous que vous pourrez transférer les acquis de la formation dans votre pratique professionnelle",
    ),

    QuestionAnchor(
        key="elements_mise_en_pratique",
        text="Quels éléments allez-vous pouvoir mettre en pratique dans votre vie professionnelle",
    ),

    QuestionAnchor(
        key="niveau_formation",
        text="Le niveau de formation vous a paru",
    ),

    QuestionAnchor(
        key="echanges_professionnels",
        text="Durant la formation, les échanges professionnels vous ont semblé",
    ),

    QuestionAnchor(
        key="ambiance",
        text="Vous avez trouvé que l'ambiance de la formation était",
    ),

    QuestionAnchor(
        key="enchaînement_sujets",
        text="L'enchaînement des sujets a été en général",
    ),

    QuestionAnchor(
        key="duree_formation",
        text="La durée de la formation est à votre avis",
    ),

    QuestionAnchor(
        key="ennui",
        text="Durant la formation, vous êtes-vous ennuyé",
    ),

    QuestionAnchor(
        key="accueil",
        text="L'accueil en formation a été",
    ),

    QuestionAnchor(
        key="appreciation_intervenants",
        text="En quelques mots, quelles sont les appréciations que vous donneriez sur le-les intervenant-s",
    ),

    QuestionAnchor(
        key="conditions_materielles",
        text="Les conditions matérielles et l'organisation de la formation ont été",
    ),

    QuestionAnchor(
        key="points_forts",
        text="Quels sont les points forts de la formation",
    ),

    QuestionAnchor(
        key="points_ajuster",
        text="Quels sont les points à ajuster sur cette formation",
    ),

    QuestionAnchor(
        key="recommandation",
        text="Est-ce que vous recommanderiez cette formation à un-e collègue",
    ),

    QuestionAnchor(
        key="note_impression",
        text="Donnez une note de 0 à 10 sur l'impression que vous laisse cette formation",
    ),

    QuestionAnchor(
        key="suggestions_complement",
        text="Vos suggestions de complément à cette formation",
    ),
)


# =====================================================
# Détection d'une question numérotée
# =====================================================

QUESTION_START_RE = re.compile(
    r"^\s*(\d{1,2})\.\s+(.+?)\s*$"
)


# =====================================================
# Transformation d'une section en lignes
# =====================================================

def _section_lines(
    result: PdfReadResult,
    section: ReportSection,
) -> List[_LineRecord]:
    """
    Transforme une section en lignes tout en conservant
    le numéro de page d'origine.
    """

    records: List[_LineRecord] = []

    for page in result.pages[
        section.start_page - 1 : section.end_page
    ]:

        for line in page.text.splitlines():

            records.append(
                _LineRecord(
                    page_number=page.number,
                    text=line,
                )
            )

    return records


# =====================================================
# Découpage des questions numérotées
# =====================================================

def split_numbered_questions(
    result: PdfReadResult,
    section: ReportSection,
    first_question_number: int = 1,
) -> List[QuestionBlock]:
    """
    Découpe une section contenant des questions numérotées.

    Les numéros doivent progresser dans l'ordre croissant,
    mais certains numéros peuvent être absents du texte
    extrait par Digiforma.

    Exemple :
        1. ...
        2. ...
        3. ...
        6. ...

    Un numéro inférieur ou égal au dernier numéro déjà
    détecté est ignoré.
    """

    records = _section_lines(
        result=result,
        section=section,
    )

    starts = []

    last_number = first_question_number - 1

    for index, record in enumerate(records):

        match = QUESTION_START_RE.match(record.text)

        if not match:
            continue

        number = int(match.group(1))

        # On conserve uniquement une progression croissante.
        # Cela permet de tolérer des numéros absents du texte
        # extrait par Digiforma.
        if number <= last_number:
            continue

        title = match.group(2).strip()

        starts.append(
            (
                index,
                number,
                title,
                record.page_number,
            )
        )

        last_number = number

    if not starts:
        return []

    blocks: List[QuestionBlock] = []

    for position, (
        start_index,
        number,
        title,
        start_page,
    ) in enumerate(starts):

        if position + 1 < len(starts):
            end_index = starts[position + 1][0]
        else:
            end_index = len(records)

        block_records = records[
            start_index:end_index
        ]

        text = "\n".join(
            record.text
            for record in block_records
        ).strip()

        end_page = (
            block_records[-1].page_number
            if block_records
            else start_page
        )

        blocks.append(
            QuestionBlock(
                number=number,
                title=title,
                start_page=start_page,
                end_page=end_page,
                text=text,
            )
        )

    return blocks


# =====================================================
# Recherche d'une ancre métier
# =====================================================

def _find_anchor_start(
    records: List[_LineRecord],
    anchor: QuestionAnchor,
    start_index: int,
    window_lines: int = 4,
) -> int | None:
    """
    Recherche le début réel d'une ancre à partir
    d'une position donnée.

    La ligne courante doit commencer comme le libellé
    attendu.

    La recherche complète tolère ensuite les éléments
    ajoutés par Digiforma entre les mots, par exemple
    une note comme 9.8 ou 10.0.
    """

    expected_normalized = normalize_for_match(
        anchor.text
    )

    expected_words = expected_normalized.split()

    for index in range(start_index, len(records)):

        current_normalized = normalize_for_match(
            records[index].text
        )

        current_words = current_normalized.split()

        if not current_words:
            continue

        # On vérifie uniquement le début de la ligne.
        # Les nombres éventuellement insérés plus loin
        # par Digiforma ne doivent pas empêcher
        # la reconnaissance de la question.
        prefix_length = min(
            4,
            len(current_words),
            len(expected_words),
        )

        if prefix_length < 2:
            continue

        if (
            current_words[:prefix_length]
            != expected_words[:prefix_length]
        ):
            continue

        end_index = min(
            index + window_lines,
            len(records),
        )

        window_text = "\n".join(
            record.text
            for record in records[index:end_index]
        )

        # Validation complète de l'ancre :
        # les mots doivent apparaître dans le bon ordre,
        # même si Digiforma intercale des scores.
        if contains_tokens_in_order(
            window_text,
            anchor.text,
        ):
            return index

    return None

# =====================================================
# Découpage par ancres métier
# =====================================================

def split_anchored_questions(
    result: PdfReadResult,
    section: ReportSection,
    anchors: Tuple[QuestionAnchor, ...] = A_CHAUD_ANCHORS,
) -> List[AnchoredQuestionBlock]:
    """
    Découpe une section dont les questions ne sont pas
    nécessairement numérotées.

    Les ancres sont recherchées dans leur ordre métier.

    Une ancre absente n'empêche pas la recherche
    des suivantes.
    """

    records = _section_lines(
        result=result,
        section=section,
    )

    starts = []

    search_from = 0

    for anchor in anchors:

        index = _find_anchor_start(
            records=records,
            anchor=anchor,
            start_index=search_from,
        )

        if index is None:
            continue

        starts.append(
            (
                index,
                anchor,
                records[index].page_number,
            )
        )

        # La recherche de l'ancre suivante commence
        # après l'ancre déjà trouvée.
        search_from = index + 1

    if not starts:
        return []

    blocks: List[AnchoredQuestionBlock] = []

    for position, (
        start_index,
        anchor,
        start_page,
    ) in enumerate(starts):

        if position + 1 < len(starts):
            end_index = starts[position + 1][0]
        else:
            end_index = len(records)

        block_records = records[
            start_index:end_index
        ]

        text = "\n".join(
            record.text
            for record in block_records
        ).strip()

        end_page = (
            block_records[-1].page_number
            if block_records
            else start_page
        )

        blocks.append(
            AnchoredQuestionBlock(
                key=anchor.key,
                title=anchor.text,
                start_page=start_page,
                end_page=end_page,
                text=text,
            )
        )

    return blocks
