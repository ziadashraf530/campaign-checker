"""
history_api.py
==============
REST endpoint controller for persistent analysis audits.
Exposes routes to retrieve list logs, single session details, delete runs,
apply reviewer override notes, and export PDF/HTML reports.
"""

import io
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from analysis_store import AnalysisStore
from report_exporter import ReportExporter

router = APIRouter(prefix="/analysis-history", tags=["Analysis History"])

class OverrideRequest(BaseModel):
    review_status: str       # APPROVED, REJECTED, BORDERLINE, NEEDS_REVIEW, HIGH_RISK
    reviewer_notes: str
    reviewed_by: str

@router.get("/")
def list_history(
    status: Optional[str] = Query(None, description="Filter by review status"),
    campaign: Optional[str] = Query(None, description="Filter by campaign name"),
    sort: str = Query("desc", description="Sort order by timestamp ('asc' or 'desc')")
):
    """Lists saved verification runs, with sort and status filter criteria."""
    sessions = AnalysisStore.list_sessions()
    
    # Apply filters
    if status:
        sessions = [s for s in sessions if s.get("review_status") == status]
    if campaign:
        sessions = [s for s in sessions if s.get("campaign_name") == campaign]
        
    # Sort by ISO timestamp
    reverse = (sort == "desc")
    sessions.sort(key=lambda s: s.get("timestamp", ""), reverse=reverse)
    
    return sessions

@router.get("/{analysis_id}")
def get_session(analysis_id: str):
    """Retrieves detailed metrics for a specific verification ID."""
    session = AnalysisStore.get_session(analysis_id)
    if not session:
        raise HTTPException(status_code=404, detail="Analysis session not found.")
    return session

@router.delete("/{analysis_id}")
def delete_session(analysis_id: str):
    """Deletes a session from the history database."""
    success = AnalysisStore.delete_session(analysis_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found or deletion failed.")
    return {"status": "success", "message": f"Session {analysis_id} deleted."}

@router.post("/{analysis_id}/override")
def override_session(analysis_id: str, req: OverrideRequest):
    """Applies QA analyst overrides, annotations, and signing metadata."""
    updated = AnalysisStore.update_review_override(
        analysis_id=analysis_id,
        review_status=req.review_status,
        notes=req.reviewer_notes,
        reviewer=req.reviewed_by
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Session not found.")
    return updated

@router.get("/{analysis_id}/export/{export_format}")
def export_report(analysis_id: str, export_format: str):
    """
    Downloads structural reports on the fly.
    Supports JSON audits, printable HTML dashboards, and PDF files.
    """
    session = AnalysisStore.get_session(analysis_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
        
    export_format = export_format.lower()
    
    if export_format == "json":
        json_str = ReportExporter.export_json(session)
        return Response(
            content=json_str,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=report_{analysis_id}.json"}
        )
        
    elif export_format == "html":
        html_str = ReportExporter.export_html(session)
        return HTMLResponse(content=html_str)
        
    elif export_format == "pdf":
        pdf_bytes = ReportExporter.export_pdf(session)
        # Determine if binary PDF (%PDF) or fallback raw string
        if pdf_bytes.startswith(b"\x25\x50\x44\x46"):
            media_type = "application/pdf"
            filename = f"report_{analysis_id}.pdf"
        else:
            media_type = "text/plain"
            filename = f"report_{analysis_id}.txt"
            
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    else:
        raise HTTPException(status_code=400, detail="Invalid format. Use json, html, or pdf.")
