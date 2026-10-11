import asyncio
import io
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from app.v2 import sources
from app.v2.models import SourceExtraction


@pytest.mark.parametrize('url',[
    'http://github.com/owner/repo', 'https://github.com.evil.test/owner/repo',
    'https://user:password@github.com/owner/repo', 'https://github.com:443/owner/repo',
    'https://127.0.0.1/owner/repo', 'https://github.com/owner/repo?token=secret',
    'https://github.com/owner/repo/../../secret', 'https://github.com/owner/%2Frepo',
    'https://github.com/owner/..', 'https://github.com/owner/repo#section'])
def test_only_exact_public_repository_urls_are_importable(url):
    with pytest.raises(HTTPException): sources.github_path(url)


def test_valid_github_path_is_normalized_without_user_controlled_host():
    assert sources.github_path('https://github.com/octocat/Hello-World.git') == ('octocat', 'Hello-World')


def test_extracted_quotes_must_be_exact_and_offsets_are_computed_locally():
    body = 'Project notes. I wrote the parser and added regression tests.'
    draft = SourceExtraction(facts=[{'category': 'experience', 'quote': 'I wrote the parser'}])
    fact = sources.validate_quotes(draft, body)[0]
    assert body[fact['start']:fact['end']] == fact['quote']
    with pytest.raises(ValueError):
        sources.validate_quotes(SourceExtraction(facts=[{'category':'experience','quote':'I led 20 engineers'}]),body)
    with pytest.raises(ValueError):
        sources.validate_quotes(SourceExtraction(facts=draft.facts * 2),body)


def test_source_selection_cannot_cross_workspaces(monkeypatch):
    monkeypatch.setattr(sources.db, 'fetch', AsyncMock(return_value=[]))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(sources.selected('owner', ['another-owners-doc']))
    assert exc.value.status_code == 422


def test_pdf_parser_subprocess_reads_text_and_rejects_invalid_input():
    writer = PdfWriter()
    page = writer.add_blank_page(width=300,height=300)
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({
        NameObject('/F1'): DictionaryObject({NameObject('/Type'):NameObject('/Font'),
            NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})})})
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 12 Tf 20 200 Td (Synthetic resume: wrote a parser.) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(stream)
    buffer = io.BytesIO(); writer.write(buffer)
    assert 'Synthetic resume: wrote a parser.' in sources._pdf(buffer.getvalue())
    with pytest.raises(HTTPException): sources._pdf(b'%PDF-invalid')


def test_upload_rejects_oversized_or_mislabeled_files():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(sources.upload('owner','resume','resume.pdf',b'x' * (sources.MAX_BYTES + 1),'application/pdf'))
    assert exc.value.status_code == 413
    with pytest.raises(HTTPException):
        asyncio.run(sources.upload('owner','resume','resume.pdf',b'not a real pdf','application/pdf'))
