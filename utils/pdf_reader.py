# utils/pdf_reader.py

from dataclasses import dataclass
from io import BytesIO
from typing import List, Tuple

import pdfplumber


# =====================================================
# OCR optionnel
# =====================================================

try:
    from pdf2image import convert_from_bytes
    import pytesseract

    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False


# =====================================================
# Structures de données
# =====================================================

@dataclass
class PdfPage:
    """
    Représente une page du PDF après lecture.
    """
    number: int
    text: str
    used_ocr: bool = False


@dataclass
class PdfReadResult:
    """
    Résultat complet de la lecture d'un PDF.
    """
    pages: List[PdfPage]
    full_text: str
    used_ocr: bool

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def char_count(self) -> int:
        return len(self.full_text)

    @property
    def ocr_pages(self) -> List[int]:
        return [
            page.number
            for page in self.pages
            if page.used_ocr
        ]


# =====================================================
# Helpers internes
# =====================================================

def _meaningful_char_count(text: str) -> int:
    """
    Compte les caractères réellement utiles d'un texte
    en ignorant les espaces et retours à la ligne.

    Utilisé uniquement pour décider si une page semble
    suffisamment vide pour nécessiter un OCR.
    """
    return len("".join(text.split()))


def _ocr_single_page(
    file_bytes: bytes,
    page_number: int,
    dpi: int,
) -> str:
    """
    OCR d'une seule page du PDF.

    page_number est basé sur la numérotation humaine :
    première page = 1.
    """
    images = convert_from_bytes(
        file_bytes,
        dpi=dpi,
        first_page=page_number,
        last_page=page_number,
    )

    if not images:
        return ""

    return pytesseract.image_to_string(
        images[0],
        lang="fra",
    ) or ""


# =====================================================
# Lecteur principal 2026
# =====================================================

def read_pdf(
    file_bytes: bytes,
    ocr_on_empty: bool = True,
    dpi: int = 300,
    min_text_chars: int = 20,
) -> PdfReadResult:
    """
    Lit un PDF page par page.

    Principes :
    - extraction principale avec pdfplumber ;
    - layout=False pour éviter les milliers d'espaces
      artificiels générés par la mise en page PDF ;
    - conservation du numéro et du texte de chaque page ;
    - OCR uniquement sur les pages quasi vides ;
    - aucune correction ou reformulation du contenu.

    Retourne un PdfReadResult contenant :
    - toutes les pages ;
    - le texte complet ;
    - le nombre de pages ;
    - le nombre de caractères ;
    - les informations relatives à l'OCR.
    """

    if not file_bytes:
        raise ValueError("Le fichier PDF est vide.")

    pages: List[PdfPage] = []

    with pdfplumber.open(BytesIO(file_bytes)) as pdf:

        if not pdf.pages:
            raise ValueError("Le PDF ne contient aucune page.")

        for page_number, page in enumerate(pdf.pages, start=1):

            # Extraction texte compacte.
            text = page.extract_text(
                x_tolerance=2,
                y_tolerance=1,
                layout=False,
            ) or ""

            page_used_ocr = False

            # Si la page est quasiment vide,
            # tentative OCR uniquement pour cette page.
            if (
                ocr_on_empty
                and OCR_AVAILABLE
                and _meaningful_char_count(text) < min_text_chars
            ):
                ocr_text = _ocr_single_page(
                    file_bytes=file_bytes,
                    page_number=page_number,
                    dpi=dpi,
                )

                # On ne remplace le texte pdfplumber que
                # si l'OCR récupère réellement plus de contenu.
                if (
                    _meaningful_char_count(ocr_text)
                    > _meaningful_char_count(text)
                ):
                    text = ocr_text
                    page_used_ocr = True

            pages.append(
                PdfPage(
                    number=page_number,
                    text=text,
                    used_ocr=page_used_ocr,
                )
            )

    full_text = "\n".join(
        page.text
        for page in pages
    ).strip()

    return PdfReadResult(
        pages=pages,
        full_text=full_text,
        used_ocr=any(page.used_ocr for page in pages),
    )


# =====================================================
# Compatibilité temporaire avec streamlit_app.py
# =====================================================

def read_pdf_all_text(
    file_bytes: bytes,
    ocr_on_empty: bool = True,
    dpi: int = 300,
) -> Tuple[str, List[str], bool]:
    """
    Adaptateur temporaire pour le code existant.

    Il utilise le nouveau lecteur read_pdf().
    Il ne s'agit donc pas d'un second mode de lecture.

    À supprimer lorsque streamlit_app.py utilisera
    directement PdfReadResult.
    """

    result = read_pdf(
        file_bytes=file_bytes,
        ocr_on_empty=ocr_on_empty,
        dpi=dpi,
    )

    return (
        result.full_text,
        [page.text for page in result.pages],
        result.used_ocr,
    )