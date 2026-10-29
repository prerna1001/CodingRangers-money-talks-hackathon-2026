"""GET /api/reports/{run_id}/markdown, POST /api/reports/{run_id}/pdf
(plan sections 14.3, 15.2 -- board-ready report export).

PDF generation is optional-dependency graceful degradation, same pattern
as services/tavily_client.py and services/elevenlabs_client.py: if
`weasyprint` isn't installed, the endpoint returns a clear 501 pointing
at the markdown endpoint instead of crashing the request.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

import auth0_setup
from api.routes.analyze import get_run_or_404
from services.pitch_deck import PALETTES as PITCH_THEMES
from services.pitch_deck import build_pitch_deck
from services.powerbi_export import build_powerbi_zip

router = APIRouter()


@router.get("/reports/{run_id}/markdown")
def get_markdown_report(
    run_id: str, user_id: str = Depends(auth0_setup.get_current_user_id)
) -> Response:
    state = get_run_or_404(run_id, user_id=user_id)
    markdown = state.get("report_markdown")
    if not markdown:
        raise HTTPException(status_code=404, detail=f"No report available for run {run_id}")
    return Response(content=markdown, media_type="text/markdown")


@router.get("/reports/{run_id}/board-update")
def get_board_update(
    run_id: str, user_id: str = Depends(auth0_setup.get_current_user_id)
) -> dict:
    state = get_run_or_404(run_id, user_id=user_id)
    board_update = state.get("board_update")
    if not board_update:
        raise HTTPException(status_code=404, detail=f"No board update available for run {run_id}")
    return {"run_id": run_id, "board_update": board_update}


@router.get("/runs/{run_id}/powerbi")
def get_powerbi_package(
    run_id: str, user_id: str = Depends(auth0_setup.get_current_user_id)
) -> Response:
    """Zip of the run's tables, Power Query scripts and theme for loading
    into Power BI Desktop (services/powerbi_export.py)."""
    state = get_run_or_404(run_id, user_id=user_id)
    return Response(
        content=build_powerbi_zip(state),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="ledgerlight_{run_id}_powerbi.zip"'},
    )


@router.get("/runs/{run_id}/pitch-deck")
def get_pitch_deck(
    run_id: str,
    theme: str = "finance",
    user_id: str = Depends(auth0_setup.get_current_user_id),
) -> Response:
    """Seven-slide PowerPoint pitch deck for the run, in the corporate navy
    ("finance") or executive dark ("dark") theme (services/pitch_deck.py)."""
    if theme not in PITCH_THEMES:
        raise HTTPException(status_code=422, detail=f"theme must be one of: {', '.join(PITCH_THEMES)}")
    state = get_run_or_404(run_id, user_id=user_id)
    return Response(
        content=build_pitch_deck(state, theme),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="ledgerlight_{run_id}_pitch_{theme}.pptx"'},
    )


@router.post("/reports/{run_id}/pdf")
def get_pdf_report(
    run_id: str, user_id: str = Depends(auth0_setup.get_current_user_id)
) -> Response:
    state = get_run_or_404(run_id, user_id=user_id)
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
