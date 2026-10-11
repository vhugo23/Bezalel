"""Plain, single-column PDF of a resume's text. Real text, no tables or images, so it stays machine-readable."""
from pathlib import Path
import re
import unicodedata

from fpdf import FPDF

FONTS = Path(__file__).resolve().parent / 'assets' / 'fonts'
MARGIN = 54  # points; 0.75 inch on US Letter
BODY, HEADING, NAME = 10.5, 12, 18  # font sizes in points
LEADING = 1.35  # line height as a multiple of the font size
INDENT = 14

# '-', '*' and dashes need a following space so '-5%' or '*note' stay text.  is Word's bullet after PDF extraction.
_BULLET = re.compile(r'(?:[-*–—] |[•·▪◦‣●○■] ?)(.*)')
_MD_HEADING = re.compile(r'#{1,6} (.+)')
_RULE = re.compile(r'[-_=*]{3,}')
_HEADING_WORDS = set('''summary objective profile experience employment history education skills projects
    certifications licenses awards honors publications languages interests activities leadership volunteer
    volunteering references coursework training achievements research contact professional work technical
    relevant additional core key selected personal academic career and &'''.split())


def _is_heading(line):
    text = line.rstrip(':').strip()
    if not text or len(text) > 40:
        return False
    all_caps = text == text.upper() and sum(c.isalpha() for c in text) >= 3 and not re.search(r'[\d,.@|]', text)
    return all_caps or all(word in _HEADING_WORDS for word in text.lower().split())


def _blocks(body, glyphs):
    """Classify each line as name, heading, bullet, text or gap. Returns [kind, text] pairs."""
    blocks, named = [], False
    for raw in body.splitlines():
        # Letters the font cannot draw become '?'; other missing characters (emoji, control codes) become spaces.
        line = ''.join(c if ord(c) in glyphs else '?' if c.isalnum() else ' '
            for c in unicodedata.normalize('NFC', raw))
        line = ' '.join(line.split())
        last = blocks[-1] if blocks else None
        if not line or _RULE.fullmatch(line):
            if last and last[0] != 'gap':
                blocks.append(['gap', ''])
            continue
        line = ' '.join(line.replace('**', '').split())
        markdown = _MD_HEADING.fullmatch(line)
        if markdown:
            line = markdown[1]
        bullet = _BULLET.fullmatch(line)
        if not named:
            blocks.append(['name', line])
            named = True
        elif bullet:
            blocks.append(['bullet', bullet[1].strip()])
        elif (markdown and len(line) <= 80) or _is_heading(line):
            blocks.append(['heading', line])
        elif last and last[0] == 'bullet' and (not last[1] or raw.startswith(('  ', '\t'))):
            # A marker alone on its line (common after PDF extraction) or an indented continuation line.
            last[1] = f'{last[1]} {line}'.strip()
        else:
            blocks.append(['text', line])
    return blocks


def _write(pdf, text, style='', size=BODY, indent=0):
    pdf.set_font('DejaVu', style, size)
    pdf.set_x(MARGIN + indent)
    pdf.multi_cell(0, size * LEADING, text, align='L', new_x='LMARGIN', new_y='NEXT')


def render(title: str, body: str) -> bytes:
    """Return PDF bytes for a resume body (at most 60,000 characters of plain text or light Markdown)."""
    # Everything is built per call, so concurrent calls share nothing but the read-only font files.
    pdf = FPDF(unit='pt', format='letter')
    pdf.set_margins(MARGIN, MARGIN)
    pdf.set_auto_page_break(True, MARGIN)
    pdf.c_margin = 0  # no cell padding, so text lines up with the margin and the heading rules
    pdf.add_font('DejaVu', '', FONTS / 'DejaVuSans.ttf')
    pdf.add_font('DejaVu', 'B', FONTS / 'DejaVuSans-Bold.ttf')
    glyphs = set.intersection(*(set(font.cmap) for font in pdf.fonts.values()))
    pdf.set_title(''.join(c for c in title if c.isprintable())[:200])
    pdf.set_draw_color(120)
    pdf.set_line_width(0.5)
    pdf.add_page()
    for kind, text in _blocks(body, glyphs):
        if kind == 'name':
            _write(pdf, text, 'B', NAME)
            pdf.ln(2)
        elif kind == 'heading':
            if pdf.will_page_break(4 * BODY * LEADING):  # keep a heading with the lines under it
                pdf.add_page()
            pdf.ln(6)
            _write(pdf, text, 'B', HEADING)
            pdf.line(MARGIN, pdf.get_y() + 1, pdf.w - MARGIN, pdf.get_y() + 1)
            pdf.ln(5)
        elif kind == 'bullet' and text:
            pdf.set_font('DejaVu', '', BODY)
            pdf.cell(INDENT, BODY * LEADING, '•')
            _write(pdf, text, indent=INDENT)  # wrapped lines start at the indent, not under the marker
        elif kind == 'text':
            _write(pdf, text)
        elif kind == 'gap':
            pdf.ln(BODY * 0.6)
    return bytes(pdf.output())
