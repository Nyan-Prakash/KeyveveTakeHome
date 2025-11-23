"""Knowledge Base page for RAG document management."""

import httpx
import streamlit as st
from auth import auth

# Configuration
API_BASE_URL = "http://localhost:8000"

# Require authentication
auth.require_auth()


def main():
    """Knowledge Base management page."""
    # Show auth status in sidebar
    auth.show_auth_sidebar()
    
    st.title("Knowledge Base")
    st.markdown("Upload and manage documents for RAG-enhanced planning")

    # Select destination
    try:
        response = httpx.get(
            f"{API_BASE_URL}/destinations",
            headers=auth.get_auth_headers(),
            timeout=10.0,
        )
        response.raise_for_status()
        destinations = response.json()

        if not destinations:
            st.warning("No destinations found. Please create a destination first.")
            if st.button("Go to Destinations"):
                st.switch_page("pages/01_Destinations.py")
            return

        # Destination selector
        dest_options = {f"{d['city']}, {d['country']}": d for d in destinations}
        selected_dest_name = st.selectbox(
            "Select Destination",
            options=list(dest_options.keys()),
            index=0,
        )
        selected_dest = dest_options[selected_dest_name]
        dest_id = selected_dest["dest_id"]

        st.divider()

        # Upload section
        st.subheader("📤 Upload Document")
        st.caption(
            "Upload PDF, Markdown, or text files to enhance planning with local knowledge"
        )

        uploaded_file = st.file_uploader(
            "Choose a file",
            type=["pdf", "md", "txt"],
            help="Supported formats: PDF, Markdown (.md), Text (.txt)",
        )

        if uploaded_file:
            if st.button("Upload & Process", type="primary"):
                with st.spinner("Uploading and processing document (this may take a minute for large files)..."):
                    try:
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue())}

                        # Get auth headers but remove Content-Type for file upload
                        headers = auth.get_auth_headers()
                        if "Content-Type" in headers:
                            del headers["Content-Type"]

                        # Use longer timeout for embedding generation (5 minutes)
                        upload_response = httpx.post(
                            f"{API_BASE_URL}/destinations/{dest_id}/knowledge/upload",
                            headers=headers,
                            files=files,
                            timeout=300.0,  # 5 minutes for large documents
                        )
                        upload_response.raise_for_status()
                        result = upload_response.json()

                        # Show detailed results
                        st.success(
                            f"✅ Document uploaded successfully!\n\n"
                            f"- **Chunks created:** {result.get('chunks_created', 'N/A')}\n"
                            f"- **Embeddings generated:** {result.get('embeddings_created', 'N/A')}\n"
                            f"- **Embeddings failed:** {result.get('embeddings_failed', 0)}"
                        )
                        st.rerun()

                    except httpx.TimeoutException:
                        st.error(
                            "⏱️ Upload timed out. The document may be too large or the OpenAI API is slow. "
                            "Try uploading a smaller document or try again later."
                        )
                    except httpx.HTTPError as e:
                        if hasattr(e, 'response') and e.response:
                            try:
                                error_detail = e.response.json().get("detail", str(e))
                            except Exception:
                                error_detail = e.response.text or str(e)
                            st.error(f"❌ Upload failed: {error_detail}")
                        else:
                            st.error(f"❌ Upload failed: {e}")
                    except Exception as e:
                        st.error(f"❌ Unexpected error: {e}")

        st.divider()

        # Knowledge items list
        st.subheader("📚 Uploaded Documents")

        try:
            items_response = httpx.get(
                f"{API_BASE_URL}/destinations/{dest_id}/knowledge/items",
                headers=auth.get_auth_headers(),
                timeout=10.0,
            )
            items_response.raise_for_status()
            items = items_response.json()

            if not items:
                st.info(
                    "No documents uploaded yet. Upload a guide or notes to get started!"
                )
            else:
                for item in items:
                    status_icon = "✅" if item["status"] == "done" else "⏳"
                    doc_name = item.get("doc_name", "Untitled")

                    with st.expander(f"{status_icon} {doc_name}", expanded=False):
                        st.write(f"**Status:** {item['status']}")
                        st.write(f"**Uploaded:** {item['created_at'][:10]}")
                        st.caption(f"Item ID: {item['item_id']}")

        except httpx.HTTPError as e:
            st.error(f"Failed to load documents: {e}")

        st.divider()

        # Chunks preview
        st.subheader("🧩 Knowledge Chunks")
        st.caption("Preview of text chunks used for RAG retrieval")

        try:
            chunks_response = httpx.get(
                f"{API_BASE_URL}/destinations/{dest_id}/knowledge/chunks",
                headers=auth.get_auth_headers(),
                timeout=10.0,
            )
            chunks_response.raise_for_status()
            chunks = chunks_response.json()

            if not chunks:
                st.info("No chunks available. Upload documents to see chunks here.")
            else:
                # Show chunk count
                st.metric("Total Chunks", len(chunks))

                # Display chunks in a table-like format
                for i, chunk in enumerate(chunks[:20], 1):  # Show first 20
                    with st.container():
                        col1, col2 = st.columns([4, 1])

                        with col1:
                            st.markdown(f"**Chunk {i}:** {chunk['snippet']}")

                        with col2:
                            doc_name = chunk.get("doc_name", "Unknown")
                            st.caption(f"From: {doc_name}")
                            st.caption(f"Date: {chunk['created_at'][:10]}")

                        st.divider()

                if len(chunks) > 20:
                    st.caption(f"Showing 20 of {len(chunks)} chunks")

        except httpx.HTTPError as e:
            st.error(f"Failed to load chunks: {e}")

    except httpx.HTTPError as e:
        st.error(f"Failed to load destinations: {e}")


if __name__ == "__main__":
    main()
