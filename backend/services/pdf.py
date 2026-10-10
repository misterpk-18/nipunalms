"""PDF rendering (reportlab, pure Python: installs with pip and needs no system libraries).

`render_certificate` draws a certificate from the issued version's data. Small helpers (`safe_text`, `wrap`) are shared so other
documents (the receipt PDFs of UX phase U11) draw with the same fonts and rules.

The standard PDF fonts only hold Latin-1 text. A character outside it (for example a name written in Telugu script) cannot be
drawn with them, so `safe_text` replaces it with "?" instead of printing an empty box; the register still holds the true name.
"""
from datetime import date
from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

NAVY = colors.HexColor("#1b2a4a")
BLUE = colors.HexColor("#2f5fb3")
GREY = colors.HexColor("#5b6472")
GOLD = colors.HexColor("#b08d3c")

PUBLIC_NAME = "Nipuna Technologies"


def safe_text(value: str | None) -> str:
    """The text with anything the standard fonts cannot draw (outside Latin-1) replaced by "?"."""
    return (value or "").encode("latin-1", "replace").decode("latin-1")


def wrap(text: str, font: str, size: float, max_width: float) -> list[str]:
    """Break text into lines no wider than max_width (words are never split unless one word is wider than the line)."""
    lines: list[str] = []
    line = ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if stringWidth(candidate, font, size) <= max_width:
            line = candidate
            continue
        if line:
            lines.append(line)
        while stringWidth(word, font, size) > max_width and len(word) > 1:  # a single over-long word: cut it
            cut = len(word)
            while cut > 1 and stringWidth(word[:cut], font, size) > max_width:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        line = word
    if line:
        lines.append(line)
    return lines


def _fit(text: str, font: str, size: float, max_width: float, minimum: float = 14) -> float:
    """The largest font size (down to `minimum`) at which the text fits on one line."""
    while size > minimum and stringWidth(text, font, size) > max_width:
        size -= 1
    return size


def _centred(pdf: canvas.Canvas, x: float, y: float, text: str, font: str, size: float, color=colors.black) -> None:
    pdf.setFillColor(color)
    pdf.setFont(font, size)
    pdf.drawCentredString(x, y, text)


def _long_date(value: date | None) -> str:
    return f"{value.day} {value:%B %Y}" if value else ""


def render_certificate(data: dict) -> bytes:
    """One landscape A4 page for an issued certificate.

    `data`: holder_name, course_title, certificate_type, certificate_number, version, issue_date, branch_name, verify_url (or None).
    """
    buffer = BytesIO()
    width, height = landscape(A4)
    pdf = canvas.Canvas(buffer, pagesize=(width, height), pageCompression=None)
    holder = safe_text(data["holder_name"])
    course = safe_text(data["course_title"])
    number = safe_text(data["certificate_number"])
    pdf.setTitle(f"{data['certificate_type']} {number}")
    pdf.setAuthor(PUBLIC_NAME)
    pdf.setSubject(f"{holder}: {course}")

    # frame
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(3)
    pdf.rect(28, 28, width - 56, height - 56)
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1)
    pdf.rect(38, 38, width - 76, height - 76)

    centre = width / 2
    usable = width - 160
    internship = data["certificate_type"] == "Internship Certificate"

    _centred(pdf, centre, height - 100, PUBLIC_NAME.upper(), "Helvetica-Bold", 14, BLUE)
    _centred(pdf, centre, height - 150, "Certificate of Internship" if internship else "Certificate of Completion", "Times-Bold", 38, NAVY)
    _centred(pdf, centre, height - 190, "This is to certify that", "Helvetica", 13, GREY)

    name_size = _fit(holder, "Times-BoldItalic", 34, usable)
    _centred(pdf, centre, height - 240, holder, "Times-BoldItalic", name_size, NAVY)
    pdf.setStrokeColor(GOLD)
    name_width = min(stringWidth(holder, "Times-BoldItalic", name_size) + 40, usable)
    pdf.line(centre - name_width / 2, height - 250, centre + name_width / 2, height - 250)

    _centred(pdf, centre, height - 282, "has completed an internship connected with the course" if internship else "has successfully completed the course",
             "Helvetica", 13, GREY)
    y = height - 318
    for line in wrap(course, "Helvetica-Bold", 22, usable)[:2]:
        _centred(pdf, centre, y, line, "Helvetica-Bold", 22, NAVY)
        y -= 28
    branch = safe_text(data["branch_name"])
    _centred(pdf, centre, y - 4, f"at {PUBLIC_NAME}, {branch}", "Helvetica", 13, GREY)

    # footer: issue date (left), number (centre-left), QR (right)
    footer_y = 96
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(80, footer_y + 18, _long_date(data["issue_date"]))
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(GREY)
    pdf.drawString(80, footer_y + 5, "Date of issue")

    version = f" (version {data['version']})" if data["version"] > 1 else ""
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(260, footer_y + 18, f"{number}{version}")
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(GREY)
    pdf.drawString(260, footer_y + 5, "Certificate number")

    verify_url = data.get("verify_url")
    if verify_url:
        size = 74
        widget = QrCodeWidget(verify_url)
        left, bottom, right, top = widget.getBounds()
        drawing = Drawing(size, size, transform=[size / (right - left), 0, 0, size / (top - bottom), 0, 0])
        drawing.add(widget)
        renderPDF.draw(drawing, pdf, width - 80 - size, footer_y - 10)
        pdf.setFont("Helvetica", 8)
        pdf.setFillColor(GREY)
        pdf.drawRightString(width - 90 - size, footer_y + 5, "Verify this certificate:")
        pdf.drawRightString(width - 90 - size, footer_y - 6, safe_text(verify_url))
    else:
        pdf.setFont("Helvetica", 8)
        pdf.setFillColor(GREY)
        pdf.drawRightString(width - 80, footer_y + 5, f"Verify this number on the Nipuna LMS certificate verification page: /verify/{number}")

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
