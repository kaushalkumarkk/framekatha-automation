from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def call_sheet_pdf(project, approved):
    output = BytesIO()
    doc = SimpleDocTemplate(output, title=f"Call sheet - {project.name}")
    styles = getSampleStyleSheet()

    def text(value):
        return Paragraph(escape(str(value or "Not provided")), styles["BodyText"])

    story = [
        Paragraph("FRAME KATHA STUDIO", styles["Title"]),
        Paragraph("Production call sheet", styles["Heading1"]),
    ]
    for label, value in [
        ("Project", project.name),
        ("Client", project.client_name),
        ("Shoot date", project.shoot_date),
        ("Call time (Asia/Kolkata)", project.call_time),
        ("Location", project.location),
        ("Cinematographer", project.cinematographer),
    ]:
        story.append(text(f"{label}: {value or 'Not provided'}"))
        story.append(Spacer(1, 0.08 * inch))
    rows = [[text("Approved talent"), text("Contact"), text("Skills")]]
    for _selection, talent in approved:
        rows.append(
            [text(talent.name), text(talent.phone or talent.email), text(", ".join(talent.skills))]
        )
    table = Table(rows, colWidths=[1.7 * inch, 2.2 * inch, 2.4 * inch], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8ebee")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.extend([Spacer(1, 0.2 * inch), table])
    doc.build(story)
    return output.getvalue()
