import fitz

from finance_cli.itau import get_pdf_text
from itau_pdf.layout import _iter_pages, _iter_lines, _has_marker
from itau_pdf.metadata import _extract_issue_date


def annotate_pdf(pdf_path: str, output_path: str | None = None) -> None:
    """Annotate PDF with x split and block coordinates."""
    doc = fitz.open(pdf_path)
    text = get_pdf_text(pdf_path)
    issue_date = _extract_issue_date(text)
    start_marker = False
    for page in _iter_pages(doc):
        page_rect = page.pdf.rect
        page.pdf.draw_line(
            fitz.Point(page.x_split, page_rect.y0),
            fitz.Point(page.x_split, page_rect.y1),
            color=(0, 0.6, 0),
            width=0.5,
            # dashes="[3 3]"
        )
        page.pdf.insert_text(
            fitz.Point(page.x_split + 2, page_rect.y0 + 8),
            f"x_split={page.x_split:.2f}",
            fontsize=7,
            color=(0, 0.6, 0),
        )


        for line in _iter_lines(page):
            if not start_marker and _has_marker(line, "start"):
                start_marker = True
                continue
            if not start_marker:
                continue
            if _has_marker(line, "stop"):
                break
            if line.text.startswith("x_split="):
                continue

            color = (1, 0, 0) if line.x0 >= page.x_split else (0, 0, 1)
            rect = fitz.Rect(line.x0, line.y0, line.x1, line.y1)
            page.pdf.draw_rect(rect, color=color, width=0.5)
            label = f"{line.x0:.2f},{line.y0:.2f}"
            page.pdf.insert_text(
                fitz.Point(line.x0, max(line.y0 - 4, page_rect.y0 + 6)),
                label,
                fontsize=6,
                color=color,
            )
    doc.save(output_path or pdf_path[:-4] + ".annotated.pdf")
    doc.close()
