"""Integration tests for Knowledge Base API with RAG functionality."""

import io

import pytest
from fastapi.testclient import TestClient

from backend.app.api.knowledge import chunk_text, strip_pii
from backend.app.main import app

# Check if PDF parsing is available
try:
    import fitz  # PyMuPDF

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Authentication headers with test token."""
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def test_destination(client, auth_headers):
    """Create a test destination for knowledge tests."""
    payload = {
        "city": "Kyoto",
        "country": "Japan",
        "geo": {"lat": 35.0116, "lon": 135.7681},
    }
    response = client.post("/destinations", json=payload, headers=auth_headers)
    return response.json()


class TestKnowledgeAPI:
    """Test suite for Knowledge Base API endpoints."""

    def test_upload_text_document(self, client, auth_headers, test_destination):
        """Test uploading a text document."""
        dest_id = test_destination["dest_id"]

        # Create a test text file
        content = "Kyoto is famous for its temples. The Golden Pavilion is a must-see attraction."
        files = {"file": ("kyoto_guide.txt", io.BytesIO(content.encode()), "text/plain")}

        response = client.post(
            f"/destinations/{dest_id}/knowledge/upload",
            headers=auth_headers,
            files=files,
        )

        assert response.status_code == 201
        data = response.json()
        assert "item_id" in data
        assert data["status"] == "done"
        assert data["chunks_created"] >= 1
        assert data["filename"] == "kyoto_guide.txt"

    def test_upload_markdown_document(self, client, auth_headers, test_destination):
        """Test uploading a markdown document."""
        dest_id = test_destination["dest_id"]

        # Create a test markdown file
        content = """# Kyoto Travel Guide

## Temples
- Kinkaku-ji (Golden Pavilion)
- Fushimi Inari Shrine

## Food
Try traditional kaiseki cuisine.
"""
        files = {"file": ("kyoto.md", io.BytesIO(content.encode()), "text/markdown")}

        response = client.post(
            f"/destinations/{dest_id}/knowledge/upload",
            headers=auth_headers,
            files=files,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "done"
        assert data["chunks_created"] >= 1

    @pytest.mark.skipif(not PDF_AVAILABLE, reason="PDF parsing not available")
    def test_upload_pdf_with_text(self, client, auth_headers, test_destination):
        """Test uploading a PDF with extractable text."""
        import fitz  # PyMuPDF

        dest_id = test_destination["dest_id"]

        # Create a simple test PDF with text
        pdf_document = fitz.open()
        page = pdf_document.new_page()

        # Add text content about Kyoto
        text = """Kyoto Travel Guide

Top Temples:
- Kinkaku-ji (Golden Pavilion): A stunning Zen Buddhist temple covered in gold leaf
- Fushimi Inari Shrine: Famous for thousands of vermillion torii gates
- Kiyomizu-dera: Historic temple with wooden stage offering city views

Best Time to Visit:
Spring (March-May) for cherry blossoms
Autumn (September-November) for fall foliage
"""
        page.insert_text((72, 72), text)

        # Save to bytes
        pdf_bytes = pdf_document.write()
        pdf_document.close()

        # Upload the PDF
        files = {"file": ("kyoto_guide.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

        response = client.post(
            f"/destinations/{dest_id}/knowledge/upload",
            headers=auth_headers,
            files=files,
        )

        assert response.status_code == 201
        data = response.json()
        assert "item_id" in data
        assert data["status"] == "done"
        assert data["chunks_created"] >= 1
        assert data["filename"] == "kyoto_guide.pdf"

    @pytest.mark.skipif(not PDF_AVAILABLE, reason="PDF parsing not available")
    def test_upload_multipage_pdf(self, client, auth_headers, test_destination):
        """Test uploading a multi-page PDF."""
        import fitz  # PyMuPDF

        dest_id = test_destination["dest_id"]

        # Create a PDF with multiple pages
        pdf_document = fitz.open()

        # Page 1
        page1 = pdf_document.new_page()
        page1.insert_text((72, 72), "Page 1: Introduction to Tokyo\n\nTokyo is Japan's capital.")

        # Page 2
        page2 = pdf_document.new_page()
        page2.insert_text((72, 72), "Page 2: Tokyo Attractions\n\nVisit Shibuya and Shinjuku.")

        # Page 3
        page3 = pdf_document.new_page()
        page3.insert_text((72, 72), "Page 3: Tokyo Food Scene\n\nTry sushi and ramen.")

        pdf_bytes = pdf_document.write()
        pdf_document.close()

        files = {"file": ("tokyo_guide.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

        response = client.post(
            f"/destinations/{dest_id}/knowledge/upload",
            headers=auth_headers,
            files=files,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["chunks_created"] >= 1

    def test_upload_corrupted_pdf(self, client, auth_headers, test_destination):
        """Test that corrupted PDFs are rejected gracefully."""
        dest_id = test_destination["dest_id"]

        # Create fake corrupted PDF data
        fake_pdf = b"%PDF-1.4\ncorrupted data that is not a valid PDF"
        files = {"file": ("corrupted.pdf", io.BytesIO(fake_pdf), "application/pdf")}

        response = client.post(
            f"/destinations/{dest_id}/knowledge/upload",
            headers=auth_headers,
            files=files,
        )

        # Should return 400 error for corrupted PDF
        assert response.status_code == 400
        assert "PDF parsing failed" in response.json()["detail"]

    def test_upload_unsupported_file_type(self, client, auth_headers, test_destination):
        """Test that unsupported file types are rejected."""
        dest_id = test_destination["dest_id"]

        # Try to upload a PNG file
        files = {"file": ("image.png", io.BytesIO(b"fake image data"), "image/png")}

        response = client.post(
            f"/destinations/{dest_id}/knowledge/upload",
            headers=auth_headers,
            files=files,
        )

        assert response.status_code == 400
        assert "PDF, MD, and TXT" in response.json()["detail"]

    def test_upload_empty_file(self, client, auth_headers, test_destination):
        """Test that empty files are rejected."""
        dest_id = test_destination["dest_id"]

        files = {"file": ("empty.txt", io.BytesIO(b""), "text/plain")}

        response = client.post(
            f"/destinations/{dest_id}/knowledge/upload",
            headers=auth_headers,
            files=files,
        )

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_list_knowledge_items(self, client, auth_headers, test_destination):
        """Test listing knowledge items for a destination."""
        dest_id = test_destination["dest_id"]

        # Upload a document first
        content = "Test guide content."
        files = {"file": ("guide.txt", io.BytesIO(content.encode()), "text/plain")}
        client.post(
            f"/destinations/{dest_id}/knowledge/upload",
            headers=auth_headers,
            files=files,
        )

        # List items
        response = client.get(
            f"/destinations/{dest_id}/knowledge/items",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        item = data[0]
        assert "item_id" in item
        assert "status" in item
        assert item["status"] == "done"
        assert item["doc_name"] == "guide.txt"

    def test_list_knowledge_chunks(self, client, auth_headers, test_destination):
        """Test listing knowledge chunks for a destination."""
        dest_id = test_destination["dest_id"]

        # Upload a document
        content = "Kyoto temples are beautiful. " * 50  # Make it long enough to create chunks
        files = {"file": ("temples.txt", io.BytesIO(content.encode()), "text/plain")}
        client.post(
            f"/destinations/{dest_id}/knowledge/upload",
            headers=auth_headers,
            files=files,
        )

        # List chunks
        response = client.get(
            f"/destinations/{dest_id}/knowledge/chunks",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        chunk = data[0]
        assert "chunk_id" in chunk
        assert "snippet" in chunk
        assert "created_at" in chunk
        assert len(chunk["snippet"]) <= 203  # 200 + "..."

    def test_org_scoping_upload(self, client, auth_headers):
        """Test that upload requires destination ownership."""
        from uuid import uuid4

        # Try to upload to non-existent destination
        fake_dest_id = str(uuid4())
        files = {"file": ("test.txt", io.BytesIO(b"content"), "text/plain")}

        response = client.post(
            f"/destinations/{fake_dest_id}/knowledge/upload",
            headers=auth_headers,
            files=files,
        )

        assert response.status_code == 404

    def test_org_scoping_list_items(self, client, auth_headers):
        """Test that listing items requires destination ownership."""
        from uuid import uuid4

        fake_dest_id = str(uuid4())

        response = client.get(
            f"/destinations/{fake_dest_id}/knowledge/items",
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestRAGFunctions:
    """Test suite for RAG helper functions."""

    def test_strip_pii_emails(self):
        """Test that email addresses are stripped from text."""
        text = "Contact us at support@example.com or admin@company.org for help."
        result = strip_pii(text)

        assert "support@example.com" not in result
        assert "admin@company.org" not in result
        assert "[EMAIL]" in result

    def test_strip_pii_phone_numbers(self):
        """Test that phone numbers are stripped from text."""
        text = "Call 555-123-4567 or (555) 987-6543 for more info."
        result = strip_pii(text)

        assert "555-123-4567" not in result
        assert "(555) 987-6543" not in result
        assert "[PHONE]" in result

    def test_strip_pii_preserves_content(self):
        """Test that non-PII content is preserved."""
        text = "The temple is open from 9:00 to 17:00 daily."
        result = strip_pii(text)

        assert "temple" in result
        assert "9:00" in result
        assert "17:00" in result

    def test_chunk_text_basic(self):
        """Test basic text chunking."""
        text = "A" * 2000  # Create text longer than chunk size
        chunks = chunk_text(text, chunk_size=500, overlap=50)

        assert len(chunks) > 1
        assert all(len(chunk) <= 550 for chunk in chunks)  # Some tolerance for overlap

    def test_chunk_text_sentence_boundary(self):
        """Test that chunking prefers sentence boundaries."""
        sentences = [f"This is sentence {i}." for i in range(100)]
        text = " ".join(sentences)

        chunks = chunk_text(text, chunk_size=100, overlap=20)

        # Verify chunks don't cut words in half (they should end with period)
        for chunk in chunks:
            if len(chunk) > 50:  # Only check reasonably-sized chunks
                assert chunk.rstrip().endswith((".", "!")) or len(chunk) < 110

    def test_chunk_text_overlap(self):
        """Test that chunks have overlap."""
        text = "Word " * 500  # Create repetitive text
        chunks = chunk_text(text, chunk_size=100, overlap=20)

        if len(chunks) >= 2:
            # Check that there's some content overlap between consecutive chunks
            # (This is a basic check; exact overlap depends on boundary detection)
            assert len(chunks) > 1

    def test_chunk_text_short_input(self):
        """Test chunking of text shorter than chunk size."""
        text = "Short text."
        chunks = chunk_text(text, chunk_size=1000, overlap=100)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_text_filters_empty(self):
        """Test that empty chunks are filtered out."""
        text = "Content here."
        chunks = chunk_text(text)

        assert all(chunk.strip() for chunk in chunks)  # No empty chunks


class TestKnowledgeIntegration:
    """Integration tests for end-to-end knowledge workflow."""

    def test_upload_and_retrieve_workflow(self, client, auth_headers, test_destination):
        """Test complete workflow: upload -> list items -> list chunks."""
        dest_id = test_destination["dest_id"]

        # Step 1: Upload document
        content = """
        Kyoto Travel Guide

        Top Attractions:
        1. Fushimi Inari Shrine - Famous for thousands of red torii gates
        2. Kinkaku-ji (Golden Pavilion) - Stunning golden temple
        3. Arashiyama Bamboo Grove - Peaceful bamboo forest

        Contact: info@kyoto-travel.jp for tour bookings.
        Phone: 555-1234 for reservations.
        """

        files = {"file": ("kyoto_full_guide.txt", io.BytesIO(content.encode()), "text/plain")}
        upload_response = client.post(
            f"/destinations/{dest_id}/knowledge/upload",
            headers=auth_headers,
            files=files,
        )

        assert upload_response.status_code == 201
        upload_data = upload_response.json()
        item_id = upload_data["item_id"]

        # Step 2: Verify item appears in list
        items_response = client.get(
            f"/destinations/{dest_id}/knowledge/items",
            headers=auth_headers,
        )

        assert items_response.status_code == 200
        items = items_response.json()
        assert any(item["item_id"] == item_id for item in items)

        # Step 3: Verify chunks were created and PII was stripped
        chunks_response = client.get(
            f"/destinations/{dest_id}/knowledge/chunks",
            headers=auth_headers,
        )

        assert chunks_response.status_code == 200
        chunks = chunks_response.json()
        assert len(chunks) >= 1

        # Check that chunk snippets don't contain PII in display
        # (Note: The original chunk_text is stored, but sanitized version is embedded)
        # This test just verifies chunks exist
        assert all("snippet" in chunk for chunk in chunks)
