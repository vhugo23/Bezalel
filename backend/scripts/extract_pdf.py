"""Bounded PDF-to-text subprocess. No network, filesystem output or OCR."""
import io
import json
import os
import sys

if os.name != 'nt':
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))

def main():
    import pypdf.filters as filters
    from pypdf import PdfReader
    # Smaller than pypdf's defaults; intake resumes should have small streams.
    filters.ZLIB_MAX_OUTPUT_LENGTH = 2_000_000
    filters.LZW_MAX_OUTPUT_LENGTH = 2_000_000
    filters.JBIG2_MAX_OUTPUT_LENGTH = 2_000_000
    data = sys.stdin.buffer.read(3_000_001)
    if len(data) > 3_000_000 or not data.startswith(b'%PDF-'):
        raise ValueError('Invalid PDF')
    reader = PdfReader(io.BytesIO(data), strict=True, root_object_recovery_limit=1000)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= 20:
        raise ValueError('Encrypted PDF or page limit')
    chunks = []
    for page in reader.pages:
        content = page.get_contents()
        if content and len(content.get_data()) > 2_000_000:
            raise ValueError('PDF content limit')
        chunks.append(page.extract_text() or '')
        if sum(map(len, chunks)) > 60000:
            raise ValueError('Text limit')
    print(json.dumps({'body': '\n\n'.join(chunks)}))

try:
    main()
except Exception:
    print(json.dumps({'error': 'Could not read this PDF. Use a text PDF of at most 20 pages, or paste the text.'}))
    raise SystemExit(1)
