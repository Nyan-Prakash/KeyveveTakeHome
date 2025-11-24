"""PDF parsing utilities with OCR support for knowledge base ingestion."""

import io
from typing import Literal

try:
    import fitz  # PyMuPDF
    from PIL import Image
    import pytesseract

    PDF_PARSING_AVAILABLE = True
except ImportError:
    PDF_PARSING_AVAILABLE = False


class PDFParsingError(Exception):
    """Raised when PDF parsing fails."""

    pass


def extract_text_from_pdf(
    content_bytes: bytes,
    use_ocr: bool = True,
    ocr_threshold: int = 50,
    ocr_dpi_scale: float = 2.0,
) -> str:
    """Extract text from PDF with optional OCR support.

    Implements a three-tier extraction strategy:
    1. Native text extraction (fast, works for digital PDFs)
    2. OCR fallback for pages with minimal text (scanned pages)
    3. Extraction and OCR of embedded images

    Args:
        content_bytes: PDF file content as bytes
        use_ocr: Enable OCR for images and low-text pages (default: True)
        ocr_threshold: Minimum characters before triggering OCR (default: 50)
        ocr_dpi_scale: DPI scaling factor for OCR quality (default: 2.0 = 144dpi)

    Returns:
        Extracted text content with page markers

    Raises:
        PDFParsingError: If PDF parsing fails or dependencies are missing
        ValueError: If content_bytes is empty or invalid

    Example:
        >>> with open("travel_guide.pdf", "rb") as f:
        ...     content_bytes = f.read()
        >>> text = extract_text_from_pdf(content_bytes, use_ocr=True)
        >>> print(text)
        --- Page 1 ---
        Rio de Janeiro Travel Guide
        ...
    """
    if not PDF_PARSING_AVAILABLE:
        raise PDFParsingError(
            "PDF parsing dependencies not installed. "
            "Install with: pip install pymupdf pytesseract pillow"
        )

    if not content_bytes:
        raise ValueError("Empty PDF content provided")

    text_content = []

    try:
        # Open PDF from bytes
        pdf_document = fitz.open(stream=content_bytes, filetype="pdf")

        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]

            # Step 1: Native text extraction (fast)
            text = page.get_text("text")
            original_text_len = len(text.strip())

            # Step 2: OCR fallback for low-text pages (scanned documents)
            if use_ocr and original_text_len < ocr_threshold:
                try:
                    # Convert page to image with higher resolution for better OCR
                    pix = page.get_pixmap(matrix=fitz.Matrix(ocr_dpi_scale, ocr_dpi_scale))
                    img_bytes = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_bytes))

                    # Perform OCR on the entire page
                    ocr_text = pytesseract.image_to_string(img, config="--psm 1")

                    # Use OCR text if it found more content
                    if len(ocr_text.strip()) > original_text_len:
                        text = ocr_text
                        text += "\n[OCR extracted]"

                except Exception as ocr_error:
                    # Log but don't fail - native text might still be useful
                    print(
                        f"Warning: Page {page_num + 1} OCR failed: {ocr_error}. "
                        f"Using native text extraction."
                    )

            # Step 3: Extract and OCR embedded images
            if use_ocr:
                image_list = page.get_images()
                for img_index, img in enumerate(image_list):
                    try:
                        xref = img[0]
                        base_image = pdf_document.extract_image(xref)
                        image_bytes = base_image["image"]
                        image = Image.open(io.BytesIO(image_bytes))

                        # OCR the embedded image
                        img_text = pytesseract.image_to_string(
                            image, config="--psm 3"  # Automatic page segmentation
                        )

                        if img_text.strip():
                            text += f"\n\n[Image {img_index + 1} content]:\n{img_text.strip()}"

                    except Exception as img_error:
                        # Log but continue processing other images
                        print(
                            f"Warning: Failed to OCR image {img_index} on page {page_num + 1}: {img_error}"
                        )
                        continue

            # Add page content if any text was extracted
            if text.strip():
                text_content.append(f"--- Page {page_num + 1} ---\n{text.strip()}")

        pdf_document.close()

        # Verify we extracted at least some content
        if not text_content:
            raise PDFParsingError(
                "No text could be extracted from PDF. "
                "The document may be empty, corrupted, or consist entirely of unsupported content."
            )

        return "\n\n".join(text_content)

    except fitz.FileDataError as e:
        raise PDFParsingError(f"Invalid or corrupted PDF file: {str(e)}") from e
    except Exception as e:
        if isinstance(e, (PDFParsingError, ValueError)):
            raise
        raise PDFParsingError(f"Failed to extract text from PDF: {str(e)}") from e


def check_pdf_dependencies() -> dict[str, bool]:
    """Check availability of PDF parsing dependencies.

    Returns:
        Dictionary with dependency availability status:
        - pymupdf: PDF parsing library
        - pytesseract: OCR engine wrapper
        - pillow: Image processing
        - tesseract: System OCR engine (runtime check)
    """
    deps = {
        "pymupdf": False,
        "pytesseract": False,
        "pillow": False,
        "tesseract": False,
    }

    try:
        import fitz  # noqa: F401

        deps["pymupdf"] = True
    except ImportError:
        pass

    try:
        import pytesseract  # noqa: F401

        deps["pytesseract"] = True

        # Check if Tesseract executable is available
        try:
            pytesseract.get_tesseract_version()
            deps["tesseract"] = True
        except Exception:
            pass
    except ImportError:
        pass

    try:
        from PIL import Image  # noqa: F401

        deps["pillow"] = True
    except ImportError:
        pass

    return deps


def get_pdf_info(content_bytes: bytes) -> dict[str, any]:
    """Extract metadata from PDF without full text extraction.

    Args:
        content_bytes: PDF file content as bytes

    Returns:
        Dictionary with PDF metadata:
        - page_count: Number of pages
        - title: Document title (if available)
        - author: Document author (if available)
        - has_text: Whether PDF contains extractable text

    Raises:
        PDFParsingError: If PDF parsing fails
    """
    if not PDF_PARSING_AVAILABLE:
        raise PDFParsingError("PDF parsing dependencies not installed")

    try:
        pdf_document = fitz.open(stream=content_bytes, filetype="pdf")

        metadata = pdf_document.metadata or {}
        page_count = pdf_document.page_count

        # Check if first page has extractable text
        has_text = False
        if page_count > 0:
            first_page_text = pdf_document[0].get_text("text")
            has_text = len(first_page_text.strip()) > 10

        pdf_document.close()

        return {
            "page_count": page_count,
            "title": metadata.get("title"),
            "author": metadata.get("author"),
            "has_text": has_text,
        }

    except Exception as e:
        raise PDFParsingError(f"Failed to extract PDF metadata: {str(e)}") from e
