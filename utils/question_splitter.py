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
        text=(
            "Pensez-vous que vous pourrez transférer les acquis de la formation "
            "dans votre pratique professionnelle"
        ),
    ),

    QuestionAnchor(
        key="elements_mise_en_pratique",
        text=(
            "Quels éléments allez-vous pouvoir mettre en pratique "
            "dans votre vie professionnelle"
        ),
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
        text=(
            "En quelques mots, quelles sont les appréciations "
            "que vous donneriez sur le-les intervenant-s"
        ),
    ),

    QuestionAnchor(
        key="conditions_materielles",
        text=(
            "Les conditions matérielles et l'organisation "
            "de la formation ont été"
        ),
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
        text=(
            "Donnez une note de 0 à 10 sur l'impression "
            "que vous laisse cette formation"
        ),
    ),

    QuestionAnchor(
        key="suggestions_complement",
        text="Vos suggestions de complément à cette formation",
    ),
)


# =====================================================
# Ancres métier connues — section À FROID
# =====================================================

A_FROID_ANCHORS: Tuple[QuestionAnchor, ...] = (

    QuestionAnchor(
        key="mise_en_pratique",
        text=(
            "Avez vous pu mettre en pratique les connaissances "
            "compétences acquises"
        ),
    ),

    QuestionAnchor(
        key="application_concrete",
        text=(
            "L'application concrète des connaissances "
            "compétences vous paraît elle"
        ),
    ),

    QuestionAnchor(
        key="maitrise_objectifs",
        text="À ce jour considérez vous maîtriser les objectifs du programme",
    ),

    QuestionAnchor(
        key="partage_collegues",
        text=(
            "Avez vous partagé les connaissances acquises lors de la formation "
            "avec vos collègues ou membres de votre équipe"
        ),
    ),

    QuestionAnchor(
        key="changements_positifs",
        text=(
            "Avez vous constaté des changements positifs dans les résultats "
            "de votre travail depuis la participation à la formation"
        ),
    ),

    QuestionAnchor(
        key="indicateurs_concrets",
        text=(
            "Pouvez vous identifier des indicateurs concrets qui démontrent "
            "l efficacité de la formation sur votre performance ou celle "
            "de votre équipe"
        ),
    ),

    QuestionAnchor(
        key="utilisation_quotidienne",
        text=(
            "Est ce que vous utilisez au quotidien dans votre environnement "
            "de travail les nouveaux savoirs compétences ou comportements "
            "acquis lors de la formation"
        ),
    ),

    QuestionAnchor(
        key="exemple_specifique",
        text=(
            "Pouvez vous citer un exemple spécifique où vous avez utilisé "
            "les compétences acquises pendant la formation pour résoudre "
            "un problème ou améliorer une situation dans votre environnement "
            "professionnel"
        ),
    ),

    QuestionAnchor(
        key="influence_pratique",
        text=(
            "Comment la formation a t elle influencé votre approche ou vos "
            "méthodes de travail dans votre rôle de professionnel"
        ),
    ),

    QuestionAnchor(
        key="elements_utiles",
        text=(
            "Quels sont avec le recul les éléments "
            "les plus utiles de la formation"
        ),
    ),

    QuestionAnchor(
        key="prolongements",
        text="Quels pourraient être les prolongements nécessaires à la formation",
    ),

    QuestionAnchor(
        key="autres_commentaires",
        text="Autres commentaires",
    ),

    QuestionAnchor(
        key="note_finale",
        text="Quelle note sur 10 donneriez vous à cette formation",
    ),
)


# =====================================================
# Ancres métier connues — section INTERVENANTS
# =====================================================

INTERVENANTS_ANCHORS: Tuple[QuestionAnchor, ...] = (

    QuestionAnchor(
        key="conditions_materielles",
        text="Les conditions matérielles étaient adaptées",
    ),

    QuestionAnchor(
        key="groupe_adapte",
        text=(
            "Le groupe d'apprenant était-il adapté "
            "taille niveau pré-requis"
        ),
    ),

    QuestionAnchor(
        key="organisation_generale",
        text="L'organisation générale de la formation était-elle adaptée",
    ),

    QuestionAnchor(
        key="commentaire_conditions",
        text="Commentaire sur les conditions matérielles",
    ),

    QuestionAnchor(
        key="commentaire_groupe",
        text="Commentaire sur le groupe d'apprenant",
    ),

    QuestionAnchor(
        key="commentaire_organisation",
        text="Commentaire sur l'organisation générale de la formation",
    ),

    QuestionAnchor(
        key="retards",
        text=(
            "Avez-vous eu des retards d'apprenant(s) "
            "au cours de cette session"
        ),
    ),

    QuestionAnchor(
        key="adaptation_horaires",
        text=(
            "As-tu eu à adapter les horaires de début fin de formation "
            "et les pauses aux besoins des apprenants"
        ),
    ),

    QuestionAnchor(
        key="precisions",
        text="Précisions à noter ici",
    ),

    QuestionAnchor(
        key="j7",
        text=(
            "As-tu pris connaissance avant formation du questionnaire J-7 "
            "des attentes des apprenants et de l'auto-évaluation "
            "de leur compétences"
        ),
    ),

    QuestionAnchor(
        key="synthese_questionnaire",
        text="As-tu bien noté ta synthèse en haut du questionnaire",
    ),

    QuestionAnchor(
        key="tour_table_fait",
        text=(
            "Et en début de formation le tour de table pour questionner "
            "les attentes a-t-il été fait"
        ),
    ),

    QuestionAnchor(
        key="synthese_tour_table",
        text=(
            "Quelle est ta synthèse de ce tour de table des attentes "
            "au regard des objectifs de la formation"
        ),
    ),

    QuestionAnchor(
        key="attentes_individuelles",
        text=(
            "Noter ici s'il y a des attentes individuelles spécifiques "
            "qui ressortent de ce tour de table"
        ),
    ),

    QuestionAnchor(
        key="attentes_programme",
        text=(
            "Est-ce que les attentes globales et individuelles "
            "correspondaient au programme prévu pour la formation"
        ),
    ),

    QuestionAnchor(
        key="modification_element",
        text=(
            "As-tu annulé ou modifié un élément pédagogique "
            "de la formation"
        ),
    ),

    QuestionAnchor(
        key="explication_modification",
        text=(
            "Merci d'expliquer quoi pourquoi comment s'est fait cette "
            "annulation modification adaptation d'une partie du programme"
        ),
    ),

    QuestionAnchor(
        key="contenu_non_prevu",
        text=(
            "As-tu traité un contenu non prévu-e au programme suite au "
            "besoin d'un apprenant ou du groupe ou une question"
        ),
    ),

    QuestionAnchor(
        key="contenu_non_prevu_detail",
        text="De quoi s'agissait-il",
    ),

    QuestionAnchor(
        key="handicap_signale",
        text=(
            "Est-ce qu'un(e) apprenant(e) t'a signalé être en situation "
            "de handicap temporaire"
        ),
    ),

    QuestionAnchor(
        key="adaptation_handicap",
        text=(
            "Si oui quelle(s) adaptation(s) lui a tu proposé "
            "au cours de la formation"
        ),
    ),

    QuestionAnchor(
        key="formation_complementaire",
        text=(
            "As-tu eu l'occasion de proposer à un(e) apprenant(e) "
            "une formation complémentaire pour renforcer certaines compétences"
        ),
    ),

    QuestionAnchor(
        key="formation_conseillee",
        text=(
            "Quelle formation as-tu conseillé en complément de celle-ci "
            "et Pourquoi"
        ),
    ),

    QuestionAnchor(
        key="commentaire_libre",
        text="Commentaire libre si besoin",
    ),

    QuestionAnchor(
        key="satisfaction_globale",
        text="Quel est ton taux de satisfaction global sur cette formation",
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
    prefix_words: int = 4,
) -> int | None:
    """
    Recherche le début réel d'une ancre à partir
    d'une position donnée.

    La ligne courante doit commencer comme le libellé
    attendu.

    La recherche complète tolère ensuite les éléments
    ajoutés par Digiforma entre les mots, par exemple
    une note, un pourcentage ou une modalité de réponse.

    window_lines :
        nombre de lignes utilisées pour reconstruire
        le libellé complet.

    prefix_words :
        nombre maximal de premiers mots utilisés pour
        confirmer que la ligne candidate correspond bien
        au début de la question.
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

        prefix_length = min(
            prefix_words,
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

        if contains_tokens_in_order(
            window_text,
            anchor.text,
        ):
            return index

    return None


# =====================================================
# Découpage générique par ancres métier
# =====================================================

def split_anchored_questions(
    result: PdfReadResult,
    section: ReportSection,
    anchors: Tuple[QuestionAnchor, ...] = A_CHAUD_ANCHORS,
    window_lines: int = 4,
    prefix_words: int = 4,
) -> List[AnchoredQuestionBlock]:
    """
    Découpe une section dont les questions ne sont pas
    nécessairement numérotées.

    Les ancres sont recherchées dans leur ordre métier.

    Une ancre absente n'empêche pas la recherche
    des suivantes.

    Les paramètres window_lines et prefix_words permettent
    d'adapter la détection aux différentes mises en page
    produites par Digiforma.
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
            window_lines=window_lines,
            prefix_words=prefix_words,
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


# =====================================================
# Découpage spécifique — section À FROID
# =====================================================

def split_a_froid_questions(
    result: PdfReadResult,
    section: ReportSection,
) -> List[AnchoredQuestionBlock]:
    """
    Découpe la section À FROID.

    Digiforma peut mélanger dans le texte extrait :
    - le libellé de la question ;
    - les modalités de réponse ;
    - les scores ;
    - les pourcentages.

    Certaines questions sont donc réparties sur de
    nombreuses lignes.

    Réglages validés sur les rapports AFGSU 1 et
    AFGSU 2 de 2026 :
        - préfixe de 3 mots ;
        - fenêtre maximale de 20 lignes.
    """

    return split_anchored_questions(
        result=result,
        section=section,
        anchors=A_FROID_ANCHORS,
        window_lines=20,
        prefix_words=3,
    )


# =====================================================
# Découpage spécifique — section INTERVENANTS
# =====================================================

def split_intervenants_questions(
    result: PdfReadResult,
    section: ReportSection,
) -> List[AnchoredQuestionBlock]:
    """
    Découpe la section INTERVENANTS.

    La section suit un questionnaire métier stable,
    mais Digiforma peut répartir les intitulés,
    modalités de réponse et résultats sur plusieurs
    lignes.

    Réglages validés sur les rapports AFGSU 1 et
    AFGSU 2 de 2026 :
        - préfixe de 3 mots ;
        - fenêtre maximale de 20 lignes.
    """

    return split_anchored_questions(
        result=result,
        section=section,
        anchors=INTERVENANTS_ANCHORS,
        window_lines=20,
        prefix_words=3,
    )