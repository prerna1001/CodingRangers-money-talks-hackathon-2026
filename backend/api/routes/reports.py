"""GET /api/reports/{run_id}/markdown, POST /api/reports/{run_id}/pdf
(plan sections 14.3, 15.2 -- board-ready report export).

PDF generation is optional-dependency graceful degradation, same pattern
as services/tavily_client.py and services/elevenlabs_client.py: if
`weasyprint` isn't installed, the endpoint returns a clear 501 pointing
at the markdown endpoint instead of crashing the request.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from api.routes.analyze import get_run_or_404

router = APIRouter()


@router.get("/reports/{run_id}/markdown")
def get_markdown_report(run_id: str) -> Response:
    state = get_run_or_404(run_id)
    markdown = state.get("report_markdown")
    if not markdown:
        raise HTTPException(status_code=404, detail=f"No report available for run {run_id}")
    return Response(content=markdown, media_type="text/markdown")


@router.get("/reports/{run_id}/board-update")
def get_board_update(run_id: str) -> dict:
    state = get_run_or_404(run_id)
    board_update = state.get("board_update")
    if not board_update:
        raise HTTPException(status_code=404, detail=f"No board update available for run {run_id}")
    return {"run_id": run_id, "board_update": board_update}


@router.post("/reports/{run_id}/pdf")
def get_pdf_report(run_id: str) -> Response:
    state = get_run_or_404(run_id)
    markdown = state.get("report_markdown")
    if not markdown:
        raise HTTPException(status_code=404, detail=f"No report available for run {run_id}")

    try:
        from weasyprint import HTML
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail=(
                "PDF export requires the 'weasyprint' package, which is not installed. "
                f"Use GET /api/reports/{run_id}/markdown instead."
            ),
        )

    escaped = markdown.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html_body = f"<html><body><pre style='font-family:sans-serif;white-space:pre-wrap'>{escaped}</pre></body></html>"
    pdf_bytes = HTML(string=html_body).write_pdf()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{run_id}.pdf"'},
    )
