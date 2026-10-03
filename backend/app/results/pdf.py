"""PDF rendering (WeasyPrint) in a dedicated, bounded thread pool so that bulk certificate jobs
never block the event loop or starve timing requests."""

from __future__ import annotations

import asyncio
import base64
import html
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from app.config import get_settings
from app.results.placements import ResultRow, format_time


@lru_cache
def pdf_executor() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=get_settings().pdf_workers, thread_name_prefix="pdf")


def _render_sync(html_doc: str) -> bytes:
    from weasyprint import HTML

    return HTML(string=html_doc).write_pdf()


async def render_pdf(html_doc: str) -> bytes:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(pdf_executor(), _render_sync, html_doc)


def _data_url(data: bytes | None, mime: str | None) -> str | None:
    if not data or not mime:
        return None
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def bib_html(
    bib_number: int, name: str, event_name: str, background: bytes | None, bg_mime: str | None
) -> str:
    bg = _data_url(background, bg_mime)
    bg_css = f"background: url('{bg}') no-repeat center / cover;" if bg else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
    @page {{ size: A5 landscape; margin: 0; }}
    body {{ margin:0; font-family: Helvetica, Arial, sans-serif; }}
    .page {{ width: 210mm; height: 148mm; position: relative; {bg_css} }}
    .event {{ position:absolute; top:10mm; left:0; right:0; text-align:center; font-size:16pt;
              font-weight:bold; }}
    .nr {{ position:absolute; top:34mm; left:0; right:0; text-align:center; font-size:110pt;
           font-weight:900; letter-spacing:2mm; }}
    .name {{ position:absolute; bottom:12mm; left:0; right:0; text-align:center; font-size:22pt; }}
    </style></head><body><div class="page">
    <div class="event">{html.escape(event_name)}</div>
    <div class="nr">{bib_number}</div>
    <div class="name">{html.escape(name)}</div>
    </div></body></html>"""


def certificate_html(
    row: ResultRow,
    competition_title: str,
    event_name: str,
    event_year: int,
    *,
    gender_scoring: bool,
    scheme: str,
    offset_lines: int = 0,
    background: bytes | None = None,
    bg_mime: str | None = None,
    print_background: bool = True,
) -> str:
    bg = _data_url(background, bg_mime) if print_background else None
    bg_css = f"background: url('{bg}') no-repeat center / 210mm 297mm;" if bg else ""
    offset_mm = offset_lines * 8
    lines = [f"Gesamtplatz {row.place_overall} von {row.total_overall}"]
    if gender_scoring and row.place_gender:
        label = {"f": "Frauen", "m": "Männer", "x": "Divers"}.get(row.gender, "")
        lines.append(f"Platz {row.place_gender} von {row.total_in_gender} ({label})")
    if scheme != "none" and row.place_age_class:
        lines.append(
            f"Altersklasse {row.age_class}: Platz {row.place_age_class} von {row.total_in_class}"
        )
    if row.extra.get("relay_place"):
        lines.append(f"Staffel-Platz: {row.extra['relay_place']} von {row.extra['relay_total']}")
        lines.append(f"Staffel-Gesamtzeit: {format_time(row.extra.get('relay_seconds'))}")
    lines_html = "".join(f"<div class='line'>{html.escape(line)}</div>" for line in lines)
    team = f"<div class='team'>{html.escape(row.team_name)}</div>" if row.team_name else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
    @page {{ size: A4 portrait; margin: 0; }}
    body {{ margin:0; font-family: Helvetica, Arial, sans-serif; }}
    .page {{ width:210mm; height:297mm; position:relative; page-break-after: always; {bg_css} }}
    .content {{ position:absolute; top:{90 + offset_mm}mm; left:20mm; right:20mm;
                text-align:center; }}
    .title {{ font-size:28pt; font-weight:bold; margin-bottom:6mm; }}
    .event {{ font-size:14pt; margin-bottom:12mm; }}
    .name {{ font-size:30pt; font-weight:bold; margin-bottom:4mm; }}
    .team {{ font-size:14pt; color:#444; margin-bottom:6mm; }}
    .comp {{ font-size:18pt; margin-bottom:4mm; }}
    .time {{ font-size:36pt; font-weight:bold; margin:6mm 0; }}
    .line {{ font-size:14pt; margin:2mm 0; }}
    </style></head><body><div class="page"><div class="content">
    <div class="title">Urkunde</div>
    <div class="event">{html.escape(event_name)} {event_year}</div>
    <div class="name">{html.escape(row.first_name)} {html.escape(row.last_name)}</div>
    {team}
    <div class="comp">{html.escape(competition_title)}</div>
    <div class="time">{format_time(row.finish_seconds)}</div>
    {lines_html}
    </div></div></body></html>"""


def combine_pages(pages: list[str]) -> str:
    """Merges several single-page documents (same stylesheet) into one multi-page document."""
    if not pages:
        return "<!doctype html><html><body></body></html>"
    head, _, _ = pages[0].partition("<body>")
    bodies = []
    for p in pages:
        _, _, rest = p.partition("<body>")
        body, _, _ = rest.rpartition("</body>")
        bodies.append(body)
    return head + "<body>" + "".join(bodies) + "</body></html>"
