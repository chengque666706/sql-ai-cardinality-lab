"""Typeset the Chinese B/C experiment report and its measured evidence as PDF.

Input: reports/实验报告.md, results/query_summary.csv and figures/*.png.
Use {{QUERY_SUMMARY_TABLE}} to insert the live summary table and
<!-- pagebreak --> to request a deliberate page break.
"""
from __future__ import annotations

import argparse
import csv
import html
import os
import re
from collections import defaultdict
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, Image, KeepTogether, LongTable, PageBreak, Paragraph,
    SimpleDocTemplate, Spacer, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 44
TEXT_WIDTH = PAGE_WIDTH - 2 * MARGIN
BODY_FONT = "Chinese"
BOLD_FONT = "ChineseBold"


def configure_fonts() -> None:
    regular = Path(os.environ.get("CJK_FONT", "C:/Windows/Fonts/msyh.ttc"))
    bold = Path(os.environ.get("CJK_BOLD_FONT", "C:/Windows/Fonts/msyhbd.ttc"))
    for path in (regular, bold):
        if not path.is_file():
            raise FileNotFoundError(
                f"Chinese font not found: {path}. Set CJK_FONT and CJK_BOLD_FONT "
                "to local embeddable TrueType fonts with Simplified Chinese glyphs. "
                "Windows defaults use Microsoft YaHei; TTC files use font index 0."
            )
    pdfmetrics.registerFont(TTFont(BODY_FONT, str(regular), subfontIndex=0))
    pdfmetrics.registerFont(TTFont(BOLD_FONT, str(bold), subfontIndex=0))
    pdfmetrics.registerFontFamily(BODY_FONT, normal=BODY_FONT, bold=BOLD_FONT,
                                 italic=BODY_FONT, boldItalic=BOLD_FONT)


def styles() -> dict[str, ParagraphStyle]:
    common = dict(fontName=BODY_FONT, textColor=colors.black, wordWrap="CJK",
                  allowWidows=0, allowOrphans=0, splitLongWords=True)
    result = {
        "body": ParagraphStyle("Body", fontSize=10, leading=16, spaceAfter=6, **common),
        "title": ParagraphStyle("Title", fontSize=18, leading=26, spaceAfter=14, keepWithNext=True,
                                fontName=BOLD_FONT, textColor=colors.black, wordWrap="CJK"),
        "h2": ParagraphStyle("Heading2", fontSize=13.3, leading=20, spaceBefore=10,
                             spaceAfter=7, keepWithNext=True, fontName=BOLD_FONT,
                             textColor=colors.black, wordWrap="CJK"),
        "h3": ParagraphStyle("Heading3", fontSize=11, leading=17, spaceBefore=7,
                             spaceAfter=5, keepWithNext=True, fontName=BOLD_FONT,
                             textColor=colors.black, wordWrap="CJK"),
        "cell": ParagraphStyle("Cell", fontSize=8.3, leading=12.4, **common),
        "caption": ParagraphStyle("Caption", fontSize=8.5, leading=13, spaceAfter=8,
                                  alignment=TA_CENTER, **common),
        "code": ParagraphStyle("Code", fontSize=8, leading=11.5, leftIndent=8,
                               rightIndent=8, spaceAfter=1, **common),
        "note": ParagraphStyle("Note", fontSize=9, leading=14, leftIndent=10,
                               spaceAfter=6, **common),
        "reference": ParagraphStyle("Reference", fontSize=9, leading=14,
                                    spaceAfter=5, **common),
    }
    return result


def inline(text: str) -> str:
    """Render a restricted, safe subset of Markdown inside ReportLab paragraphs."""
    text = text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
    text = html.escape(text, quote=False)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r'<font size="9">\1</font>', text)
    return text


def table_flowable(rows: list[list[str]], sty: dict, widths: list[float] | None = None) -> LongTable:
    cols = max(len(row) for row in rows)
    normalized = [row + [""] * (cols - len(row)) for row in rows]
    if widths is None:
        sizes = [max(min(len(str(row[c])), 28) for row in normalized) for c in range(cols)]
        weights = [max(size, 7) for size in sizes]
        widths = [TEXT_WIDTH * weight / sum(weights) for weight in weights]
    body = [[Paragraph(("<b>" if r == 0 else "") + inline(str(cell)) + ("</b>" if r == 0 else ""), sty["cell"])
             for cell in row] for r, row in enumerate(normalized)]
    table = LongTable(body, colWidths=widths, repeatRows=1, hAlign="LEFT", spaceAfter=10)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#efefef")),
        ("LINEABOVE", (0, 0), (-1, 0), 0.7, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.45, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 0.65, colors.black),
        ("LINEBELOW", (0, 1), (-1, -2), 0.2, colors.HexColor("#d4d4d4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def number(value: str, decimals: int = 2) -> str:
    try:
        return f"{float(value):,.{decimals}f}"
    except (ValueError, TypeError):
        return str(value)


def summary_flowables(summary_path: Path, sty: dict) -> list:
    with summary_path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    if not rows:
        raise ValueError(f"Summary has no rows: {summary_path}")
    columns = list(rows[0])
    q_candidates = ["q_error", "median_q_error", "q_error_median", "root_q_error", "root_q_error_median"]
    time_candidates = ["execution_time_ms", "median_execution_time_ms", "execution_time_ms_median", "execution_ms_median", "median_ms"]
    qcol = next((x for x in q_candidates if x in columns), None)
    tcol = next((x for x in time_candidates if x in columns), None)
    if "phase" in columns and "query_id" in columns and qcol and tcol:
        grouped = defaultdict(dict)
        for row in rows:
            grouped[row["query_id"]][row["phase"]] = row
        phases = list(dict.fromkeys(row["phase"] for row in rows))
        preferred = ["baseline", "reanalyze_control", "extended"]
        phases = [p for p in preferred if p in phases] + [p for p in phases if p not in preferred]
        phase_names = {"baseline": "基线", "reanalyze_control": "重采样对照", "extended": "扩展统计"}
        header = ["查询"]
        for phase in phases:
            header.extend([phase_names.get(phase, phase) + " Q-error", phase_names.get(phase, phase) + " 时间/ms"])
        data = [header]
        for query_id in sorted(grouped):
            row = [query_id]
            for phase in phases:
                result = grouped[query_id].get(phase, {})
                row.extend([number(result.get(qcol, "-")), number(result.get(tcol, "-"))])
            data.append(row)
        widths = [44] + [(TEXT_WIDTH - 44) / (2 * len(phases))] * (2 * len(phases))
        return [table_flowable(data, sty, widths)]
    # Wide one-row-per-query summaries are split into narrow panels while keeping IDs.
    idcol = "query_id" if "query_id" in columns else columns[0]
    omit = {"title", "group", "source", "sql_sha256", "plan_file"}
    metrics = [c for c in columns if c != idcol and c not in omit]
    flowables = []
    for start in range(0, len(metrics), 5):
        panel = metrics[start:start + 5]
        data = [[idcol, *panel]] + [[row[idcol], *[number(row[c]) for c in panel]] for row in rows]
        flowables.append(table_flowable(data, sty))
    return flowables


def image_flowables(path: Path, caption: str, sty: dict) -> list:
    if not path.exists():
        raise FileNotFoundError(path)
    with PILImage.open(path) as img:
        width, height = img.size
    scale = min(TEXT_WIDTH / width, 315 / height)
    image = Image(str(path), width=width * scale, height=height * scale, hAlign="CENTER")
    return [KeepTogether([image, Spacer(1, 5), Paragraph(inline(caption), sty["caption"])])]


def parse_markdown(source: Path, summary: Path, sty: dict) -> tuple[list, set[Path], bool]:
    lines = source.read_text(encoding="utf-8-sig").splitlines()
    flowables, used_images = [], set()
    summary_used = False
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line == "<!-- pagebreak -->":
            flowables.append(PageBreak())
            index += 1
            continue
        if "{{QUERY_SUMMARY_TABLE}}" in line:
            flowables.extend(summary_flowables(summary, sty))
            summary_used = True
            index += 1
            continue
        if line.startswith("```"):
            index += 1
            code = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            for code_line in code:
                safe_line = html.escape(code_line).replace(" ", "&#160;") or "&#160;"
                flowables.append(Paragraph(safe_line, sty["code"]))
            flowables.append(Spacer(1, 6))
            index += 1
            continue
        image_match = re.fullmatch(r"!\[(.*?)\]\((.*?)\)", line)
        if image_match:
            caption, raw_path = image_match.groups()
            path = (source.parent / raw_path).resolve()
            if not path.exists():
                path = (ROOT / raw_path).resolve()
            used_images.add(path)
            flowables.extend(image_flowables(path, caption, sty))
            index += 1
            continue
        if line.startswith("|"):
            table_rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                values = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", cell) for cell in values):
                    table_rows.append(values)
                index += 1
            flowables.append(table_flowable(table_rows, sty))
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            level, content = heading.groups()
            key = "title" if len(level) == 1 else "h2" if len(level) == 2 else "h3"
            flowables.append(Paragraph(inline(content), sty[key]))
            index += 1
            continue
        if line in {"---", "***"}:
            flowables.append(HRFlowable(width="100%", thickness=0.4, color=colors.grey, spaceAfter=8))
            index += 1
            continue
        if line.startswith(">"):
            flowables.append(Paragraph(inline(line.lstrip("> ")), sty["note"]))
            index += 1
            continue
        list_match = re.match(r"^([-*]|\d+[.)、])\s+(.*)$", line)
        if list_match:
            marker, content = list_match.groups()
            marker = "•" if marker in {"-", "*"} else marker
            paragraph_style = sty["reference"] if "https://" in content else sty["body"]
            flowables.append(Paragraph(inline(marker + " " + content), paragraph_style))
            index += 1
            continue
        paragraph = [line]
        index += 1
        while index < len(lines) and lines[index].strip() and not re.match(r"^(#|\||```|!\[|>|[-*]\s|\d+[.)、]\s|<!--|\{\{)", lines[index].strip()):
            paragraph.append(lines[index].strip())
            index += 1
        flowables.append(Paragraph(inline(" ".join(paragraph)), sty["body"]))
    return flowables, used_images, summary_used


def decorate(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#c5c5c5"))
    canvas.setLineWidth(0.35)
    canvas.line(MARGIN, 38, PAGE_WIDTH - MARGIN, 38)
    canvas.setFont(BODY_FONT, 8)
    canvas.setFillColor(colors.HexColor("#505050"))
    canvas.drawString(MARGIN, 24, "SQL 与 AI 协同优化 | B、C 成员实验报告")
    canvas.drawRightString(PAGE_WIDTH - MARGIN, 24, f"第 {doc.page} 页")
    canvas.restoreState()


def validate_report_tables(source: Path, records: list[dict]) -> None:
    """Check the authored numerical tables against live machine-readable results."""
    results = {(r["phase"], r["query_id"]): r for r in records}
    table_kind = None
    checked = 0
    for raw_line in source.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            table_kind = None
            continue
        cells = [x.strip() for x in line.strip("|").split("|")]
        if cells[:3] == ["查询", "场景", "估计行数"]:
            table_kind = "tpch"
            continue
        if cells[:2] == ["查询", "基线 Q-error"]:
            table_kind = "qerror"
            continue
        if cells[:2] == ["查询", "仅 ANALYZE 中位耗时 ms"]:
            table_kind = "time"
            continue
        query = re.match(r"([TS]\d{2})", cells[0])
        if not table_kind or not query:
            continue
        qid = query.group(1)
        checks = []
        if table_kind == "tpch":
            row = results["baseline", qid]
            checks = [(cells[2], row["plan_rows"]), (cells[3], row["actual_rows"]), (cells[4], row["q_error"])]
        elif table_kind == "qerror":
            checks = [(cells[i + 1], results[phase, qid]["q_error"]) for i, phase in enumerate(("baseline", "reanalyze_control", "extended"))]
            checks.append((cells[4], results["baseline", qid]["actual_rows"]))
        elif table_kind == "time":
            checks = [(cells[i + 1], results[phase, qid]["execution_time_ms_median"]) for i, phase in enumerate(("reanalyze_control", "extended"))]
        for displayed, measured in checks:
            if abs(float(displayed.replace(",", "")) - float(measured)) > 0.000501:
                raise ValueError(f"Report/CSV mismatch for {qid}: {displayed} vs {measured}")
            checked += 1
    print(f"Validated {checked} displayed measurements against query_summary.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "reports" / "实验报告.md")
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "B和C成员实验报告.pdf")
    args = parser.parse_args()
    summary = ROOT / "results" / "query_summary.csv"
    # Validate the live result source even if the Markdown uses its own result tables.
    with summary.open(encoding="utf-8-sig", newline="") as file:
        summary_rows = list(csv.DictReader(file))
    if not summary_rows:
        raise ValueError("query_summary.csv contains no observations")
    validate_report_tables(args.source, summary_rows)
    configure_fonts()
    sty = styles()
    story, used_images, summary_used = parse_markdown(args.source, summary, sty)
    for path in sorted((ROOT / "figures").glob("*.png")):
        if path.resolve() not in used_images:
            story.extend(image_flowables(path, path.stem.replace("_", " "), sty))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(str(args.output), pagesize=A4, leftMargin=MARGIN,
                                 rightMargin=MARGIN, topMargin=39, bottomMargin=49,
                                 title="B和C成员实验报告：SQL与AI协同优化",
                                 author="数据库小组", pageCompression=1)
    document.build(story, onFirstPage=decorate, onLaterPages=decorate)
    print(f"PDF written: {args.output}")


if __name__ == "__main__":
    main()
