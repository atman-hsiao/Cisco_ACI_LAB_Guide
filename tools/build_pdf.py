from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, Image, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "Cisco_ACI_LAB_Guide.md"
OUT = ROOT / "output" / "pdf" / "Cisco_ACI_LAB_Guide.pdf"
ASSETS = ROOT / "output" / "assets"


def register_fonts():
    regular = Path("C:/Windows/Fonts/msjh.ttc")
    bold = Path("C:/Windows/Fonts/msjhbd.ttc")
    if regular.exists():
        pdfmetrics.registerFont(TTFont("CJK", str(regular)))
        pdfmetrics.registerFont(TTFont("CJK-Bold", str(bold if bold.exists() else regular)))
        return "CJK", "CJK-Bold"
    return "Helvetica", "Helvetica-Bold"


REGULAR, BOLD = register_fonts()


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(REGULAR, 8)
    canvas.setFillColor(colors.HexColor("#475569"))
    canvas.drawRightString(7.7 * inch, 0.42 * inch, f"Page {doc.page}")
    canvas.restoreState()


def clean(text):
    text = re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    return text.replace("&", "&amp;") if "<font" not in text and "<b>" not in text else text


def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("CJKNormal", parent=styles["BodyText"], fontName=REGULAR, fontSize=9.5, leading=14, spaceAfter=5, textColor=colors.black)
    title = ParagraphStyle("CJKTitle", parent=normal, fontName=BOLD, fontSize=25, leading=31, alignment=TA_CENTER, spaceAfter=18)
    h1 = ParagraphStyle("CJKH1", parent=normal, fontName=BOLD, fontSize=17, leading=22, spaceAfter=9, textColor=colors.black)
    h2 = ParagraphStyle("CJKH2", parent=normal, fontName=BOLD, fontSize=12.5, leading=17, spaceBefore=8, spaceAfter=5)
    code_style = ParagraphStyle("Code", parent=normal, fontName="Courier", fontSize=7.5, leading=10, leftIndent=10, spaceAfter=7)
    doc = BaseDocTemplate(str(OUT), pagesize=letter, rightMargin=.68*inch, leftMargin=.68*inch, topMargin=.65*inch, bottomMargin=.65*inch, title="Cisco ACI LAB Guide")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates(PageTemplate(id="main", frames=[frame], onPage=footer))
    story = []
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    i = 0
    code = False
    code_lines = []
    mermaid_count = 0
    first_h1 = True
    chapter_count = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            if code:
                story.append(Paragraph("<br/>".join(x.replace("&", "&amp;").replace("<", "&lt;") for x in code_lines), code_style))
                code = False
                code_lines = []
            elif line == "```mermaid":
                i += 1
                while i < len(lines) and not lines[i].startswith("```"):
                    i += 1
                path = ASSETS / ("physical_topology.png" if mermaid_count == 0 else "tenant_topology.png")
                mermaid_count += 1
                story.append(Image(str(path), width=6.9*inch, height=4.31*inch if mermaid_count == 1 else 3.1*inch))
                story.append(Spacer(1, 8))
            else:
                code = True
            i += 1
            continue
        if code:
            code_lines.append(line)
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[-:| ]+\|$", lines[i+1]):
            rows = [[Paragraph(clean(x.strip()), normal) for x in line.strip("|").split("|")]]
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([Paragraph(clean(x.strip()), normal) for x in lines[i].strip("|").split("|")])
                i += 1
            widths = [doc.width / len(rows[0])] * len(rows[0])
            table = Table(rows, colWidths=widths, repeatRows=1, hAlign="CENTER")
            commands = [
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1F4E78")),
                ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                ("FONTNAME", (0,0), (-1,0), BOLD),
                ("GRID", (0,0), (-1,-1), .4, colors.HexColor("#D9D9D9")),
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
                ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ]
            for r in range(2, len(rows), 2):
                commands.append(("BACKGROUND", (0,r), (-1,r), colors.HexColor("#EAF2F8")))
            table.setStyle(TableStyle(commands))
            story.extend([table, Spacer(1, 9)])
            continue
        if line.startswith("# "):
            if first_h1:
                story.append(Paragraph(line[2:], title))
                story.append(Paragraph("ACI 初學者實體環境操作手冊與章節式自動化工具", ParagraphStyle("sub", parent=normal, alignment=TA_CENTER, fontSize=12, spaceAfter=18)))
                first_h1 = False
            else:
                if chapter_count > 0:
                    story.append(PageBreak())
                story.append(Paragraph(line[2:], h1))
                chapter_count += 1
        elif line.startswith("## "):
            story.append(Paragraph(line[3:], h2))
        elif re.match(r"^\d+\. ", line):
            story.append(Paragraph(clean(line), ParagraphStyle("num", parent=normal, leftIndent=14, firstLineIndent=-10)))
        elif line.startswith("- "):
            story.append(Paragraph("• " + clean(line[2:]), ParagraphStyle("bullet", parent=normal, leftIndent=14, firstLineIndent=-10)))
        elif line.startswith("> "):
            story.append(Paragraph(clean(line[2:]), ParagraphStyle("warn", parent=normal, fontName=BOLD, leftIndent=16, rightIndent=16, spaceBefore=5, spaceAfter=8)))
        elif line.strip():
            story.append(Paragraph(clean(line), normal))
        i += 1
    doc.build(story)
    print(OUT)


if __name__ == "__main__":
    build()
