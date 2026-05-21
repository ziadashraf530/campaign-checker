"""
report_exporter.py
==================
Generates high-fidelity compliance reports and QA audits in JSON, HTML, and PDF formats.
Integrates visual verdicts, OCR texts, policy violations, temporal timelines, and analyst overrides.
"""

import json
from datetime import datetime

class ReportExporter:
    """
    Export manager for generating structured audits, premium printable HTML pages, and PDF reports.
    """

    @staticmethod
    def export_json(session: dict) -> str:
        """Returns the audit session as a clean, formatted JSON string."""
        return json.dumps(session, indent=2, ensure_ascii=False)

    @staticmethod
    def export_html(session: dict) -> str:
        """
        Generates a premium, single-page, responsive HTML dashboard report.
        Styled with dark/light hybrid typography optimized for browser rendering and print-to-PDF.
        """
        timestamp = session.get("timestamp", "")
        try:
            formatted_date = datetime.fromisoformat(timestamp.replace("Z", "")).strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            formatted_date = timestamp

        # Dynamic badges
        match_type = session.get("match_type", "NO_MATCH")
        match_class = "none"
        match_label = "No Match"
        if match_type == "STRONG_MATCH":
            match_class = "strong"
            match_label = "Strong Match"
        elif match_type == "PROBABLE_STRONG_MATCH":
            match_class = "probable"
            match_label = "Probable Match"
        elif match_type == "POSSIBLE_MATCH":
            match_class = "possible"
            match_label = "Possible Match"

        comp_status = session.get("compliance_status", "NOT_EVALUATED")
        comp_class = comp_status.lower()

        rev_status = session.get("review_status", "NEEDS_REVIEW")
        rev_class = rev_status.lower().replace("_", "-")

        # HTML construction
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Campaign Verification Report - {session.get('filename')}</title>
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: #141b2d;
            --border-color: #263354;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --primary: #6366f1;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --info: #06b6d4;
        }}
        @media print {{
            body {{
                background: #ffffff !important;
                color: #000000 !important;
            }}
            .card {{
                background: #ffffff !important;
                border: 1px solid #cccccc !important;
                color: #000000 !important;
            }}
            .text-muted {{ color: #555555 !important; }}
            .no-print {{ display: none !important; }}
        }}
        body {{
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            margin: 0;
            padding: 30px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header-left h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 800;
            background: linear-gradient(135deg, #a5b4fc, #6366f1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .header-left p {{
            margin: 5px 0 0 0;
            color: var(--text-muted);
            font-size: 14px;
        }}
        .badges-container {{
            display: flex;
            gap: 10px;
        }}
        .badge {{
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .badge.strong {{ background: rgba(16, 185, 129, 0.2); color: var(--success); border: 1px solid var(--success); }}
        .badge.probable {{ background: rgba(16, 185, 129, 0.15); color: var(--success); border: 1px solid #34d399; }}
        .badge.possible {{ background: rgba(245, 158, 11, 0.2); color: var(--warning); border: 1px solid var(--warning); }}
        .badge.none {{ background: rgba(239, 68, 68, 0.2); color: var(--danger); border: 1px solid var(--danger); }}

        .badge-compliance {{
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 700;
        }}
        .badge-compliance.pass {{ background: rgba(16, 185, 129, 0.15); color: var(--success); }}
        .badge-compliance.partial {{ background: rgba(245, 158, 11, 0.15); color: var(--warning); }}
        .badge-compliance.fail {{ background: rgba(239, 68, 68, 0.15); color: var(--danger); }}
        .badge-compliance.not_evaluated {{ background: rgba(156, 163, 175, 0.15); color: var(--text-muted); }}

        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        .card h2 {{
            margin-top: 0;
            font-size: 18px;
            font-weight: 700;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
            margin-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .info-row {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 12px;
            font-size: 14px;
        }}
        .info-row span:first-child {{
            color: var(--text-muted);
        }}
        .info-row span:last-child {{
            font-weight: 600;
        }}
        .rules-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .rule-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            border-radius: 6px;
            margin-bottom: 8px;
            font-size: 13.5px;
        }}
        .rule-item.passed {{ background: rgba(16, 185, 129, 0.08); border-left: 4px solid var(--success); }}
        .rule-item.violated {{ background: rgba(239, 68, 68, 0.08); border-left: 4px solid var(--danger); }}
        .rule-item.warned {{ background: rgba(245, 158, 11, 0.08); border-left: 4px solid var(--warning); }}
        
        .ocr-box {{
            background: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            padding: 15px;
            max-height: 150px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 13px;
            border: 1px solid var(--border-color);
        }}
        .override-box {{
            border: 1px dashed var(--primary);
            background: rgba(99, 102, 241, 0.05);
        }}
        .override-badge {{
            padding: 4px 10px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 11px;
            text-transform: uppercase;
        }}
        .override-badge.approved {{ background: var(--success); color: white; }}
        .override-badge.rejected {{ background: var(--danger); color: white; }}
        .override-badge.borderline {{ background: var(--warning); color: black; }}
        .override-badge.needs-review {{ background: var(--info); color: white; }}
        .override-badge.high-risk {{ background: #ff4500; color: white; }}

        .action-bar {{
            display: flex;
            justify-content: flex-end;
            margin-bottom: 20px;
        }}
        .btn {{
            background: var(--primary);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            text-decoration: none;
            font-size: 14px;
            transition: opacity 0.2s;
        }}
        .btn:hover {{
            opacity: 0.9;
        }}
        .reasoning-list {{
            padding-left: 20px;
            margin: 0;
            font-size: 14px;
        }}
        .reasoning-list li {{
            margin-bottom: 8px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="action-bar no-print">
            <button class="btn" onclick="window.print()"><i class="fa-solid fa-print"></i> Print / Save as PDF</button>
        </div>
        
        <header>
            <div class="header-left">
                <h1>QA VERIFICATION REPORT</h1>
                <p>Generated on {formatted_date} | Run ID: {session.get('analysis_id')}</p>
            </div>
            <div class="badges-container">
                <div class="badge {match_class}">{match_label}</div>
            </div>
        </header>

        <div class="grid">
            <!-- Media Details -->
            <div class="card">
                <h2>Media Information</h2>
                <div class="info-row">
                    <span>Filename</span>
                    <span>{session.get('filename')}</span>
                </div>
                <div class="info-row">
                    <span>Campaign Name</span>
                    <span>{session.get('campaign_name')}</span>
                </div>
                <div class="info-row">
                    <span>File Path</span>
                    <span>{session.get('file')}</span>
                </div>
                <div class="info-row">
                    <span>Visual Similarity</span>
                    <span>{session.get('top_similarity', 0.0):.4f}</span>
                </div>
                <div class="info-row">
                    <span>Calibrated Confidence</span>
                    <span>{session.get('confidence_pct', 0.0):.1f}%</span>
                </div>
                <div class="info-row">
                    <span>Best Reference</span>
                    <span>{session.get('best_reference', 'N/A')}</span>
                </div>
            </div>

            <!-- Pipeline Versions -->
            <div class="card">
                <h2>System Trace Audits</h2>
                <div class="info-row">
                    <span>SigLIP Model Version</span>
                    <span>{session.get('model_version')}</span>
                </div>
                <div class="info-row">
                    <span>OCR Version</span>
                    <span>{session.get('ocr_version')}</span>
                </div>
                <div class="info-row">
                    <span>Policy Configuration</span>
                    <span>{session.get('policy_version')}</span>
                </div>
                <div class="info-row">
                    <span>Adapt Threshold Code</span>
                    <span>{session.get('threshold_version')}</span>
                </div>
                <div class="info-row">
                    <span>Processing Latency</span>
                    <span>{session.get('processing_time_ms', 0.0):.1f} ms</span>
                </div>
                <div class="info-row">
                    <span>Decision Ambiguity Index</span>
                    <span>{session.get('ambiguity_score', 0.0):.4f}</span>
                </div>
            </div>
        </div>

        <div class="grid">
            <!-- Caption & OCR Rules -->
            <div class="card" style="grid-column: span 2;">
                <h2>Compliance Framework Evaluation <span class="badge-compliance {comp_class}">Score: {session.get('compliance_score', 100)}/100 ({comp_status})</span></h2>
                
                <h3 style="font-size: 15px; margin-bottom: 10px;">Rule Verification Breakdowns:</h3>
                <ul class="rules-list">
        """

        # Generate rule items HTML
        passed_rules = session.get("passed_rules", [])
        violations = session.get("violations", [])
        warnings = session.get("warnings", [])

        for rule in passed_rules:
            html += f"""
                    <li class="rule-item passed">
                        <span>{rule}</span>
                        <strong style="color: var(--success);">PASSED</strong>
                    </li>
            """
        for rule in violations:
            html += f"""
                    <li class="rule-item violated">
                        <span>{rule}</span>
                        <strong style="color: var(--danger);">CRITICAL VIOLATION</strong>
                    </li>
            """
        for rule in warnings:
            html += f"""
                    <li class="rule-item warned">
                        <span>{rule}</span>
                        <strong style="color: var(--warning);">WARNING</strong>
                    </li>
            """

        if not passed_rules and not violations and not warnings:
            html += """
                    <li style="color: var(--text-muted); font-size: 14px;">No textual brief rules evaluated for this media session.</li>
            """

        # Append OCR blocks & annotations
        ocr_lines = session.get("ocr_text", [])
        ocr_merged = " | ".join(ocr_lines) if ocr_lines else "No on-screen OCR text extracted."

        html += f"""
                </ul>
                
                <h3 style="font-size: 15px; margin: 20px 0 10px 0;">Transcribed On-Screen Overlay OCR Content:</h3>
                <div class="ocr-box">{ocr_merged}</div>
            </div>
        </div>

        <div class="grid">
            <!-- Analyst Annotations -->
            <div class="card override-box" style="grid-column: span 2;">
                <h2>QA Analyst Overrides & Audit Log <span class="override-badge {rev_class}">{rev_status.replace('_', ' ')}</span></h2>
                <div class="info-row">
                    <span>Reviewing Officer</span>
                    <span>{session.get('reviewed_by') or 'Pending Review'}</span>
                </div>
                <div class="info-row" style="margin-bottom: 20px;">
                    <span>Override Notes</span>
                    <span style="font-style: italic; font-weight: normal; color: { 'var(--text-main)' if session.get('reviewer_notes') else 'var(--text-muted)' };">
                        {session.get('reviewer_notes') or 'No review annotations submitted yet.'}
                    </span>
                </div>
            </div>
        </div>
        
        <div class="card" style="margin-top: 30px; border: 1px solid var(--border-color); background: transparent;">
            <h2>Diagnostic Reasoning Audit Trail</h2>
            <ul class="reasoning-list">
        """

        reasoning_list = session.get("reasoning", [])
        for reason in reasoning_list:
            html += f"<li>{reason}</li>"
        
        if not reasoning_list:
            html += "<li>No critical diagnostics generated. Media matches visual requirements with zero compliance infractions.</li>"

        html += """
            </ul>
        </div>
    </div>
</body>
</html>
"""
        return html

    @staticmethod
    def export_pdf(session: dict) -> bytes:
        """
        Generates a native PDF report using reportlab.
        If reportlab is missing, falls back cleanly to a beautifully structured text/ASCII format.
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from io import BytesIO

            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
            story = []

            styles = getSampleStyleSheet()
            
            # Custom styles
            title_style = ParagraphStyle(
                'DocTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#6366F1'),
                spaceAfter=15
            )
            section_style = ParagraphStyle(
                'SectionTitle',
                parent=styles['Heading2'],
                fontSize=14,
                textColor=colors.HexColor('#1E293B'),
                spaceBefore=12,
                spaceAfter=6
            )
            body_style = ParagraphStyle(
                'BodyTextCustom',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#334155'),
                spaceAfter=8
            )
            meta_style = ParagraphStyle(
                'MetaCustom',
                parent=styles['Normal'],
                fontSize=9,
                textColor=colors.HexColor('#64748B'),
                spaceAfter=4
            )

            # Header
            story.append(Paragraph("QA Verification Report", title_style))
            story.append(Paragraph(f"Run ID: {session.get('analysis_id')} | Generated: {session.get('timestamp')}", meta_style))
            story.append(Spacer(1, 15))

            # Summary Table
            data = [
                [Paragraph("<b>Campaign Target File</b>", body_style), Paragraph(session.get("filename", ""), body_style)],
                [Paragraph("<b>Campaign Brief</b>", body_style), Paragraph(session.get("campaign_name", ""), body_style)],
                [Paragraph("<b>Visual Match Verdict</b>", body_style), Paragraph(session.get("match_type", ""), body_style)],
                [Paragraph("<b>Calibrated Confidence</b>", body_style), Paragraph(f"{session.get('confidence_pct', 0.0):.1f}%", body_style)],
                [Paragraph("<b>Compliance Score</b>", body_style), Paragraph(f"{session.get('compliance_score', 100)}/100 ({session.get('compliance_status')})", body_style)],
                [Paragraph("<b>Review Queue Status</b>", body_style), Paragraph(session.get("review_status", ""), body_style)],
                [Paragraph("<b>Reviewer Notes</b>", body_style), Paragraph(session.get("reviewer_notes", "N/A"), body_style)],
                [Paragraph("<b>Reviewed By</b>", body_style), Paragraph(session.get("reviewed_by", "Pending"), body_style)]
            ]
            
            t = Table(data, colWidths=[150, 350])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#F8FAFC')),
                ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#0F172A')),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ]))
            story.append(t)
            story.append(Spacer(1, 15))

            # Rules Evaluation Section
            story.append(Paragraph("Compliance Verification Brief Rules Details", section_style))
            
            passed = session.get("passed_rules", [])
            viols = session.get("violations", [])
            warns = session.get("warnings", [])

            for rule in passed:
                story.append(Paragraph(f"• [PASSED] {rule}", body_style))
            for rule in viols:
                story.append(Paragraph(f"• [VIOLATED] {rule}", body_style))
            for rule in warns:
                story.append(Paragraph(f"• [WARNING] {rule}", body_style))
            
            if not passed and not viols and not warns:
                story.append(Paragraph("No text rules verified.", body_style))
                
            story.append(Spacer(1, 15))

            # System Trace Metadata
            story.append(Paragraph("System Execution Trace Metadata", section_style))
            version_data = [
                [Paragraph("<b>SigLIP Model</b>", body_style), Paragraph(session.get("model_version", ""), body_style)],
                [Paragraph("<b>OCR Engine</b>", body_style), Paragraph(session.get("ocr_version", ""), body_style)],
                [Paragraph("<b>Policy Evaluator</b>", body_style), Paragraph(session.get("policy_version", ""), body_style)],
                [Paragraph("<b>Decision Ambiguity</b>", body_style), Paragraph(f"{session.get('ambiguity_score', 0.0):.4f}", body_style)]
            ]
            t_ver = Table(version_data, colWidths=[150, 350])
            t_ver.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
                ('TOPPADDING', (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(t_ver)

            doc.build(story)
            pdf_bytes = buffer.getvalue()
            buffer.close()
            return pdf_bytes

        except Exception as e:
            # Clean structured ASCII fallback report if reportlab is not present
            fallback_text = f"""
======================================================================
QA VERIFICATION REPORT - PERSISTENT CAMPAIGN MATCH
======================================================================
Run ID: {session.get('analysis_id')}
Timestamp: {session.get('timestamp')}
======================================================================

MEDIA DETAIL STATS:
----------------------------------
Filename: {session.get('filename')}
Campaign Brief: {session.get('campaign_name')}
Visual Match Verdict: {session.get('match_type')}
Confidence: {session.get('confidence_pct', 0.0):.1f}%
Visual Similarity: {session.get('top_similarity', 0.0):.4f}
Decision Ambiguity Index: {session.get('ambiguity_score', 0.0):.4f}

COMPLIANCE EVALUATION BRIEF:
----------------------------------
Compliance Score: {session.get('compliance_score', 100)}/100
Status: {session.get('compliance_status')}

PASSED RULES:
{chr(10).join('- ' + r for r in session.get('passed_rules', [])) or 'None'}

VIOLATIONS:
{chr(10).join('- ' + r for r in session.get('violations', [])) or 'None'}

WARNINGS:
{chr(10).join('- ' + r for r in session.get('warnings', [])) or 'None'}

QA OVERRIDES:
----------------------------------
Review Queue Status: {session.get('review_status')}
Reviewed By: {session.get('reviewed_by') or 'Pending Review'}
Reviewer Notes: {session.get('reviewer_notes') or 'N/A'}

SYSTEM TRACES:
----------------------------------
SigLIP Version: {session.get('model_version')}
OCR Version: {session.get('ocr_version')}
Policy Config: {session.get('policy_version')}
Adapt Thresholds: {session.get('threshold_version')}

======================================================================
Generated locally in Campaign QA Workstation.
            """
            return fallback_text.encode('utf-8')
