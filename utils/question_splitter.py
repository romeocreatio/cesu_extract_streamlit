# utils/question_splitter.py

from dataclasses import dataclass
import re
from typing import List

from utils.pdf_reader import PdfReadResult
from utils.section_splitter import ReportSection


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


@dataclass
class _LineRecord:
    """
    Ligne interne utilisée pendant le découpage.
    """

    page_number: int
    text: str


# =====================================================
# Détection d'une question numérotée
# =====================================================

QUESTION_START_RE = re.compile(
    r"^\s*(\d{1,2})\.\s+(.+?)\s*$"
)


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
# Découpage principal
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

    Exemple valide :
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
        # extrait par Digiforma, comme 9 et 10 dans certains
        # rapports, sans revenir en arrière.
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