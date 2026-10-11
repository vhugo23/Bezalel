from concurrent.futures import ThreadPoolExecutor
import io
import logging
import time

from pypdf import PdfReader

from app.v2 import resume_pdf, sources

NAME = 'Jordan Rivera'
HEADINGS = ['SUMMARY', 'Experience:', 'Education', 'Technical Skills', 'PROJECTS']
BULLETS = [
    'Cut boot time from 9.2 s to 3.1 s by reordering driver initialisation and deferring non-critical '
    'peripherals until after the first control loop tick had completed successfully.',
    'Led a team of 4 engineers and mentored two interns through their first production release.',
    'Wrote the CAN bootloader used on 12,000+ units',
    'Reduced field failures by 37% with a hardware-in-the-loop test rig',
    'Built a logic analyser from an FPGA dev board, with a Rust host tool',
]
RESUME = f'''# {NAME}
Houston, TX | jordan@example.com | (555) 010-2030 | github.com/jrivera

{HEADINGS[0]}
Embedded engineer with 6 years of experience   shipping firmware for industrial robots.

{HEADINGS[1]}
**Senior Firmware Engineer**, Acme Robotics, 2021 to Present
• {BULLETS[0]}
- {BULLETS[1]}
* {BULLETS[2]}
– {BULLETS[3]}

## {HEADINGS[2]}
B.S. Electrical Engineering, University of Houston, 2019

{HEADINGS[3]}
C, C++, Python, Rust, FreeRTOS, Zephyr

{HEADINGS[4]}
•
{BULLETS[4]}
'''


def words(text):
    return ' '.join(text.split())


def extracted(data):
    """The upload path: backend/scripts/extract_pdf.py in its bounded subprocess."""
    return words(sources._pdf(data))


def pages(data):
    return PdfReader(io.BytesIO(data)).pages


def test_render_returns_pdf_bytes():
    data = resume_pdf.render('resume.pdf (revised)', RESUME)
    assert isinstance(data, bytes) and data.startswith(b'%PDF-') and len(data) > 5000
    assert PdfReader(io.BytesIO(data)).metadata.title == 'resume.pdf (revised)'


def test_round_trip_keeps_name_headings_and_bullets_in_order():
    data = resume_pdf.render('resume.pdf', RESUME)
    text = extracted(data)
    expected = [NAME, HEADINGS[0], HEADINGS[1], 'Senior Firmware Engineer, Acme Robotics', *BULLETS[:4],
        HEADINGS[2], 'University of Houston', HEADINGS[3], 'FreeRTOS, Zephyr', HEADINGS[4], BULLETS[4]]
    position = 0
    for part in expected:
        found = text.find(words(part), position)
        assert found >= 0, f'{part!r} is missing or out of order in the extracted text'
        position = found + len(words(part))
    assert text.count('•') == len(BULLETS)  # every marker style is drawn as the same bullet
    assert '#' not in text and '**' not in text
    # Machine-readable means text only: one page here, no images, no annotations or form fields.
    assert len(pages(data)) == 1
    assert all(not page.images and '/Annots' not in page for page in pages(data))


def test_layout_is_one_column_with_hanging_bullets():
    starts = []
    pages(resume_pdf.render('resume.pdf', RESUME))[0].extract_text(
        visitor_text=lambda text, cm, tm, font, size: text.strip() and starts.append((round(tm[4]), size, text.strip())))
    margin, indent = resume_pdf.MARGIN, resume_pdf.MARGIN + resume_pdf.INDENT
    assert {x for x, _, _ in starts} == {margin, indent}
    assert starts[0] == (margin, resume_pdf.NAME, NAME)
    # A wrapped bullet continues at the indent, not under the marker.
    assert [x for x, _, text in starts if text == '•'] == [margin] * len(BULLETS)
    assert sum(x == indent for x, _, _ in starts) > len(BULLETS)
    assert {text for _, size, text in starts if size == resume_pdf.HEADING} == set(HEADINGS)


def test_non_ascii_survives_the_round_trip():
    body = 'José Muñoz\nZoë led the naïve rewrite – “ship it” — it’s done\nRésumé café Ångström'
    text = extracted(resume_pdf.render('résumé.pdf', body))
    for part in ('José Muñoz', 'Zoë', 'naïve', '–', '“ship it”', 'it’s', 'Résumé café Ångström'):
        assert part in text
    # Decomposed accents (common in PDF-extracted text) are composed before drawing.
    assert 'José' not in extracted(resume_pdf.render('x', 'José Muñoz\nmore text here'))


def test_characters_the_font_lacks_are_replaced(caplog):
    body = 'Sam Lee \U0001F680\nShipped \U0001F4E7 mail\ttool\x07 \ud83d in 中文 and English \n\U0001F680'
    with caplog.at_level(logging.WARNING):
        data = resume_pdf.render('\U0001F680 resume\x00\n', body)
    assert not [record for record in caplog.records if 'missing' in record.getMessage()]
    assert extracted(data) == 'Sam Lee Shipped mail tool in ?? and English'


def test_full_length_body_flows_across_pages():
    line = 'Designed and shipped a telemetry pipeline handling 40k messages per second across 3 regions.\n'
    body = ''.join(('EXPERIENCE\n' if i % 12 == 0 else '') + ('' if i % 3 == 0 else '• ') + line for i in range(700))[:60000]
    assert len(body) == 60000
    started = time.perf_counter()
    data = resume_pdf.render('long.pdf', body)
    elapsed = time.perf_counter() - started
    assert data.startswith(b'%PDF-') and len(pages(data)) > 1
    assert elapsed < 20, f'rendering took {elapsed:.1f}s'
    assert 'telemetry pipeline' in pages(data)[-1].extract_text()


def test_awkward_input_does_not_raise():
    for body in ('', ' \n\t\n  ', '•', '# ', '---', 'x' * 3000, '\n'.join('a' * 300)):
        data = resume_pdf.render('', body)
        assert data.startswith(b'%PDF-') and len(pages(data)) >= 1
    assert pages(resume_pdf.render('Resume', ''))[0].extract_text().strip() == ''


def test_lines_are_classified():
    glyphs = set(range(0x20, 0x250)) | {0x2022}
    body = ('Ada Lovelace\nada@example.com\n\n\nWORK EXPERIENCE\nProjects:\n### A Markdown heading\nAWS, GCP, SQL\n'
        'Skills in C and Rust\n-5% defects\n- first\n  continued\n •second\nplain\n***\nEDUCATION')
    assert resume_pdf._blocks(body, glyphs) == [['name', 'Ada Lovelace'], ['text', 'ada@example.com'], ['gap', ''],
        ['heading', 'WORK EXPERIENCE'], ['heading', 'Projects:'], ['heading', 'A Markdown heading'],
        ['text', 'AWS, GCP, SQL'], ['text', 'Skills in C and Rust'], ['text', '-5% defects'],
        ['bullet', 'first continued'], ['bullet', 'second'], ['text', 'plain'], ['gap', ''], ['heading', 'EDUCATION']]


def test_concurrent_renders_are_independent():
    def job(index):
        return index, resume_pdf.render(f'resume {index}', RESUME.replace(NAME, f'Candidate Number{index}'))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(job, range(16)))
    for index, data in results:
        text = words(pages(data)[0].extract_text())
        assert text.startswith(f'Candidate Number{index} Houston')
        assert all(words(bullet) in text for bullet in BULLETS)
