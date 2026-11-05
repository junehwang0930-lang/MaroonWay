"""Small valid PDFs for fixtures; only explicit corruption tests use invalid bytes."""
import pymupdf


def write_pdf(path, text):
    # Serialize in memory so MuPDF never owns a filesystem handle to the fixture.
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((30, 40), text, fontsize=8)
        content = document.tobytes()
    path.write_bytes(content)
