"""PDF rendering (reportlab, pure Python: installs with pip and needs no system libraries).

`render_certificate` draws a certificate from the issued version's data and `render_receipt` a payment receipt from the CRM's
finance record. Small helpers (`safe_text`, `wrap`) are shared so both draw with the same fonts and rules.

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


def _money(value) -> str:
    """'Rs. 15,000.00': the standard fonts have no rupee sign."""
    return f"Rs. {float(value):,.2f}"


def render_receipt(data: dict) -> bytes:
    """One portrait A4 page for a payment the CRM verified.

    `data`: branch_name, receipt_number, receipt_date (date), amount, student_name, student_code, admission_code, course_title,
    invoice_numbers (list), fee_total, verified_paid, balance, as_of (date). The CRM holds the original receipt; this copy says so.
    """
    buffer = BytesIO()
    width, height = A4
    pdf = canvas.Canvas(buffer, pagesize=(width, height), pageCompression=None)
    number = safe_text(data["receipt_number"])
    student = safe_text(data["student_name"])
    pdf.setTitle(f"Receipt {number}")
    pdf.setAuthor(PUBLIC_NAME)
    pdf.setSubject(f"{student}: {safe_text(data['course_title'])}")

    left, right = 56, width - 56
    usable = right - left

    pdf.setFillColor(NAVY)
    pdf.rect(0, height - 96, width, 96, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(left, height - 52, PUBLIC_NAME)
    pdf.setFont("Helvetica", 11)
    pdf.drawString(left, height - 72, safe_text(data["branch_name"]))
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawRightString(right, height - 52, "PAYMENT RECEIPT")
    pdf.setFont("Helvetica", 10)
    pdf.drawRightString(right, height - 72, f"Receipt {number}")

    y = height - 140

    def pair(label: str, value: str, y_at: float, x: float = left, size: float = 12) -> None:
        pdf.setFont("Helvetica", 9)
        pdf.setFillColor(GREY)
        pdf.drawString(x, y_at, label.upper())
        pdf.setFont("Helvetica-Bold", size)
        pdf.setFillColor(colors.black)
        pdf.drawString(x, y_at - 16, value)

    pair("Received from", student, y)
    pair("Student ID", safe_text(data["student_code"]), y, x=left + usable * 0.62)
    y -= 50
    pair("Course", safe_text(data["course_title"])[:70], y)
    pair("Admission", safe_text(data["admission_code"]), y, x=left + usable * 0.62)
    y -= 50
    pair("Receipt date", _long_date(data["receipt_date"]), y)
    invoices = ", ".join(safe_text(i) for i in data.get("invoice_numbers") or []) or "-"
    pair("Invoice", invoices[:40], y, x=left + usable * 0.62)

    # the amount
    y -= 70
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1)
    pdf.rect(left, y - 14, usable, 52)
    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(GREY)
    pdf.drawString(left + 14, y + 20, "AMOUNT RECEIVED")
    pdf.setFont("Helvetica-Bold", 22)
    pdf.setFillColor(NAVY)
    pdf.drawRightString(right - 14, y + 4, _money(data["amount"]))

    # the account after this payment, as the CRM reports it
    y -= 58
    pdf.setFont("Helvetica-Bold", 11)
    pdf.setFillColor(colors.black)
    pdf.drawString(left, y, "Fee position for this course")
    pdf.setStrokeColor(colors.HexColor("#cfd5df"))
    pdf.line(left, y - 6, right, y - 6)
    y -= 26
    for label, value in (("Course fee", data["fee_total"]), ("Verified payments to date", data["verified_paid"]), ("Balance", data["balance"])):
        pdf.setFont("Helvetica", 11)
        pdf.setFillColor(GREY)
        pdf.drawString(left, y, label)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.setFillColor(colors.black)
        pdf.drawRightString(right, y, _money(value))
        y -= 22
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(GREY)
    pdf.drawString(left, y - 2, f"As reported by the finance record on {_long_date(data['as_of'])}.")

    # footer
    note = ("This is a copy of a receipt the finance team has already verified, produced by the Nipuna LMS from that record. "
            "The original receipt is held by the branch. A payment that is still waiting for verification is not listed here.")
    line_y = 92
    pdf.setStrokeColor(colors.HexColor("#cfd5df"))
    pdf.line(left, line_y + 28, right, line_y + 28)
    pdf.setFont("Helvetica", 8.5)
    pdf.setFillColor(GREY)
    for line in wrap(note, "Helvetica", 8.5, usable):
        pdf.drawString(left, line_y + 12, line)
        line_y -= 11

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
