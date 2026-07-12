import io
from datetime import datetime
from typing import Optional


def export_report_docx(
    report_text: str,
    officer_name: str,
    badge_number: str,
    incident_id: Optional[str] = None,
    call_type: Optional[str] = None,
    location: Optional[str] = None,
    report_type: Optional[str] = None,
) -> bytes:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT

    doc = Document()

    style = doc.styles['Normal']
    font = style.font
    font.name = 'Times New Roman'
    font.size = Pt(12)
    font.color.rgb = RGBColor(0, 0, 0)

    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1.25)
        section.right_margin = Inches(1.25)

    header_table = doc.add_table(rows=1, cols=1)
    header_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = header_table.cell(0, 0)
    cell_para = cell.paragraphs[0]
    cell_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = cell_para.add_run("CHRONOS NARRATIVE ENGINE")
    run.bold = True
    run.font.size = Pt(16)
    run.font.color.rgb = RGBColor(30, 58, 138)

    sub_para = cell.add_paragraph()
    sub_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub_para.add_run("Law Enforcement Report Generation System")
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(100, 116, 139)

    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    borders = OxmlElement('w:tcBorders')
    for edge in ('top', 'bottom'):
        element = OxmlElement(f'w:{edge}')
        element.set(qn('w:val'), 'single')
        element.set(qn('w:sz'), '12')
        element.set(qn('w:color'), '1E3A8A')
        element.set(qn('w:space'), '0')
        borders.append(element)
    for edge in ('left', 'right'):
        element = OxmlElement(f'w:{edge}')
        element.set(qn('w:val'), 'none')
        element.set(qn('w:sz'), '0')
        element.set(qn('w:color'), 'auto')
        element.set(qn('w:space'), '0')
        borders.append(element)
    tcPr.append(borders)

    doc.add_paragraph()

    info_table = doc.add_table(rows=4, cols=2)
    info_table.style = 'Table Grid'
    info_table.alignment = WD_TABLE_ALIGNMENT.LEFT

    now = datetime.now()
    display_type = report_type or call_type or "Incident Report"
    info_data = [
        ("Officer:", officer_name),
        ("Badge Number:", badge_number),
        ("Incident ID:", incident_id or f"INC-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"),
        ("Report Type:", display_type),
    ]

    for i, (label, value) in enumerate(info_data):
        label_cell = info_table.cell(i, 0)
        value_cell = info_table.cell(i, 1)
        label_para = label_cell.paragraphs[0]
        run = label_para.add_run(label)
        run.bold = True
        run.font.size = Pt(10)
        run.font.name = 'Times New Roman'
        value_para = value_cell.paragraphs[0]
        run = value_para.add_run(value)
        run.font.size = Pt(10)
        run.font.name = 'Times New Roman'

    if call_type or location:
        extra_table = doc.add_table(rows=1, cols=2)
        extra_table.style = 'Table Grid'
        c1 = extra_table.cell(0, 0)
        c2 = extra_table.cell(0, 1)
        p1 = c1.paragraphs[0]
        r1 = p1.add_run("Call Type: ")
        r1.bold = True
        r1.font.size = Pt(10)
        r1.font.name = 'Times New Roman'
        r1b = p1.add_run(call_type or "N/A")
        r1b.font.size = Pt(10)
        r1b.font.name = 'Times New Roman'
        p2 = c2.paragraphs[0]
        r2 = p2.add_run("Location: ")
        r2.bold = True
        r2.font.size = Pt(10)
        r2.font.name = 'Times New Roman'
        r2b = p2.add_run(location or "N/A")
        r2b.font.size = Pt(10)
        r2b.font.name = 'Times New Roman'

    doc.add_paragraph()

    hr = doc.add_paragraph()
    hr.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = hr.add_run("─" * 60)
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(100, 116, 139)

    doc.add_paragraph()

    narrative_heading = doc.add_paragraph()
    narrative_heading.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = narrative_heading.add_run("INCIDENT NARRATIVE")
    run.bold = True
    run.font.size = Pt(13)
    run.font.color.rgb = RGBColor(30, 58, 138)

    for para_text in report_text.split('\n'):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.line_spacing = Pt(18)
        run = p.add_run(para_text)
        run.font.size = Pt(12)
        run.font.name = 'Times New Roman'

    doc.add_paragraph()
    doc.add_paragraph()

    footer_hr = doc.add_paragraph()
    footer_hr.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer_hr.add_run("─" * 60)
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(100, 116, 139)

    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer.add_run("Generated by Chronos Narrative Engine")
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(100, 116, 139)
    run.italic = True

    footer2 = doc.add_paragraph()
    footer2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer2.add_run(f"Timestamp: {now.strftime('%Y-%m-%d %H:%M:%S')} | Officer: {officer_name} | Badge #{badge_number}")
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(100, 116, 139)
    run.italic = True

    footer3 = doc.add_paragraph()
    footer3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer3.add_run("This report was AI-generated and has been reviewed by the officer of record.")
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(100, 116, 139)
    run.italic = True

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


def export_report_pdf(
    report_text: str,
    officer_name: str,
    badge_number: str,
    incident_id: Optional[str] = None,
    call_type: Optional[str] = None,
    location: Optional[str] = None,
    report_type: Optional[str] = None,
) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    buf = io.BytesIO()
    now = datetime.now()

    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'ChronosTitle',
        parent=styles['Title'],
        fontSize=18,
        textColor=HexColor('#1E3A8A'),
        spaceAfter=2,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    )

    subtitle_style = ParagraphStyle(
        'ChronosSubtitle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=HexColor('#64748B'),
        alignment=TA_CENTER,
        spaceAfter=12,
        fontName='Helvetica',
    )

    section_style = ParagraphStyle(
        'SectionHead',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=HexColor('#1E3A8A'),
        fontName='Helvetica-Bold',
        spaceBefore=16,
        spaceAfter=8,
    )

    body_style = ParagraphStyle(
        'ReportBody',
        parent=styles['Normal'],
        fontSize=11,
        leading=16,
        fontName='Times-Roman',
        spaceAfter=6,
    )

    info_label_style = ParagraphStyle(
        'InfoLabel',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica-Bold',
    )

    info_value_style = ParagraphStyle(
        'InfoValue',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica',
    )

    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=HexColor('#64748B'),
        alignment=TA_CENTER,
        fontName='Helvetica-Oblique',
    )

    elements = []

    elements.append(Paragraph("CHRONOS NARRATIVE ENGINE", title_style))
    elements.append(Paragraph("Law Enforcement Report Assistance Program", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=2, color=HexColor('#1E3A8A'), spaceAfter=12))

    inc_id = incident_id or f"INC-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"
    display_type = report_type or call_type or "Incident Report"

    info_data = [
        ["Officer:", officer_name, "Incident ID:", inc_id],
        ["Badge #:", badge_number, "Date:", now.strftime("%B %d, %Y")],
        ["Report Type:", display_type, "Location:", location or "N/A"],
    ]

    info_table = Table(info_data, colWidths=[1.1*inch, 2.2*inch, 1.1*inch, 2.2*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTNAME', (3, 0), (3, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#334155')),
        ('TEXTCOLOR', (2, 0), (2, -1), HexColor('#334155')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#CBD5E1')),
        ('BACKGROUND', (0, 0), (0, -1), HexColor('#F1F5F9')),
        ('BACKGROUND', (2, 0), (2, -1), HexColor('#F1F5F9')),
    ]))

    elements.append(info_table)
    elements.append(Spacer(1, 16))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=HexColor('#94A3B8'), spaceAfter=12))

    elements.append(Paragraph("INCIDENT NARRATIVE", section_style))

    for para_text in report_text.split('\n'):
        if para_text.strip():
            elements.append(Paragraph(para_text.replace('<', '&lt;').replace('>', '&gt;'), body_style))
        else:
            elements.append(Spacer(1, 6))

    elements.append(Spacer(1, 24))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=HexColor('#94A3B8'), spaceAfter=12))
    elements.append(Paragraph("Generated by Chronos Narrative Engine", footer_style))
    elements.append(Paragraph(
        f"Timestamp: {now.strftime('%Y-%m-%d %H:%M:%S')} | Officer: {officer_name} | Badge #{badge_number}",
        footer_style
    ))
    elements.append(Paragraph(
        "This report was AI-generated and has been reviewed by the officer of record.",
        footer_style
    ))

    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()


def export_compliance_docx(officer_name: str, badge_number: str) -> bytes:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from compliance_content import COMPLIANCE_SECTIONS

    doc = Document()
    now = datetime.now()

    style = doc.styles['Normal']
    font = style.font
    font.name = 'Times New Roman'
    font.size = Pt(11)

    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1.25)
        section.right_margin = Inches(1.25)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("ARTIFICIAL INTELLIGENCE\nSAFEGUARDS & GUARDRAILS CERTIFICATION")
    run.bold = True
    run.font.size = Pt(16)
    run.font.color.rgb = RGBColor(30, 58, 138)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub.add_run("Chronos Narrative Engine — Law Enforcement Report Generation System")
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(100, 116, 139)

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = meta.add_run(f"Officer: {officer_name} | Badge #{badge_number} | Date: {now.strftime('%B %d, %Y')}")
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(100, 116, 139)

    doc.add_paragraph()
    hr = doc.add_paragraph()
    hr.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = hr.add_run("─" * 60)
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(100, 116, 139)

    doc.add_paragraph()

    intro = doc.add_paragraph()
    run = intro.add_run(
        "This document certifies that the Chronos Narrative Engine operates under the following "
        "AI safeguards, guardrails, and compliance controls. All AI-generated content produced "
        "by this system is subject to mandatory human review before submission to any records "
        "management system."
    )
    run.font.size = Pt(11)
    run.font.name = 'Times New Roman'

    for heading, items in COMPLIANCE_SECTIONS:
        plain_heading = heading.replace("&amp;", "&").replace("&mdash;", "-")
        h = doc.add_paragraph()
        run = h.add_run(plain_heading)
        run.bold = True
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(30, 58, 138)
        for item in items:
            plain_item = item.replace("&amp;", "&").replace("&mdash;", "-").replace("&bull;", "*")
            p = doc.add_paragraph(style='List Bullet')
            run = p.add_run(plain_item)
            run.font.size = Pt(10)
            run.font.name = 'Times New Roman'

    doc.add_paragraph()
    hr2 = doc.add_paragraph()
    hr2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = hr2.add_run("─" * 60)
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(100, 116, 139)

    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer.add_run(f"Generated by Chronos Narrative Engine | {now.strftime('%Y-%m-%d %H:%M:%S')}")
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(100, 116, 139)
    run.italic = True

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


def export_compliance_pdf(officer_name: str, badge_number: str) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Spacer, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_CENTER
    from compliance_content import COMPLIANCE_SECTIONS

    buf = io.BytesIO()
    now = datetime.now()

    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'ComplianceTitle', parent=styles['Title'], fontSize=16,
        textColor=HexColor('#1E3A8A'), alignment=TA_CENTER,
        fontName='Helvetica-Bold', spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        'ComplianceSubtitle', parent=styles['Normal'], fontSize=9,
        textColor=HexColor('#64748B'), alignment=TA_CENTER, spaceAfter=4,
    )
    meta_style = ParagraphStyle(
        'ComplianceMeta', parent=styles['Normal'], fontSize=10,
        textColor=HexColor('#64748B'), alignment=TA_CENTER, spaceAfter=12,
    )
    section_style = ParagraphStyle(
        'ComplianceSection', parent=styles['Heading2'], fontSize=12,
        textColor=HexColor('#1E3A8A'), fontName='Helvetica-Bold',
        spaceBefore=14, spaceAfter=6,
    )
    body_style = ParagraphStyle(
        'ComplianceBody', parent=styles['Normal'], fontSize=10,
        leading=14, fontName='Times-Roman', spaceAfter=4,
    )
    bullet_style = ParagraphStyle(
        'ComplianceBullet', parent=styles['Normal'], fontSize=10,
        leading=14, fontName='Times-Roman', leftIndent=20, spaceAfter=3, bulletIndent=8,
    )
    footer_style = ParagraphStyle(
        'ComplianceFooter', parent=styles['Normal'], fontSize=8,
        textColor=HexColor('#64748B'), alignment=TA_CENTER, fontName='Helvetica-Oblique',
    )

    elements = []
    elements.append(Paragraph("ARTIFICIAL INTELLIGENCE<br/>SAFEGUARDS &amp; GUARDRAILS CERTIFICATION", title_style))
    elements.append(Paragraph("Chronos Narrative Engine — Law Enforcement Report Generation System", subtitle_style))
    elements.append(Paragraph(f"Officer: {officer_name} | Badge #{badge_number} | Date: {now.strftime('%B %d, %Y')}", meta_style))
    elements.append(HRFlowable(width="100%", thickness=2, color=HexColor('#1E3A8A'), spaceAfter=12))
    elements.append(Paragraph(
        "This document certifies that the Chronos Narrative Engine operates under the following "
        "AI safeguards, guardrails, and compliance controls. All AI-generated content produced "
        "by this system is subject to mandatory human review before submission to any records "
        "management system.",
        body_style
    ))

    for heading, items in COMPLIANCE_SECTIONS:
        elements.append(Paragraph(heading, section_style))
        for item in items:
            safe = item.replace('<', '&lt;').replace('>', '&gt;')
            elements.append(Paragraph(f"* {safe}", bullet_style))

    elements.append(Spacer(1, 24))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=HexColor('#94A3B8'), spaceAfter=12))
    elements.append(Paragraph(f"Generated by Chronos Narrative Engine | {now.strftime('%Y-%m-%d %H:%M:%S')}", footer_style))
    elements.append(Paragraph("This document certifies compliance with the AI safeguards described above.", footer_style))

    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()
