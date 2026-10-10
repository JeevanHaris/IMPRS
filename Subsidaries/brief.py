"""
IPMPRS — Intelligent Proposal Management and Precedent Retrieval System
Puducherry Police Hackathon 2026 · Problem Statement 01
────────────────────────────────────────────────────────────────────────
brief.py: Decision Brief PDF Generator for Approving Authorities
Uses ReportLab to produce a clean, executive, one/two-page appraisal document
combining proposal details, Precedent Pulse, past outcomes, and officer remarks.
"""

import os
import io
from datetime import datetime
from typing import Dict, Any, List

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

import proposals
import precedents

# Theme palette matching official Puducherry Police executive styling
NAVY_PRIMARY   = colors.HexColor("#0f172a")  # Deep Slate Navy
NAVY_SECONDARY = colors.HexColor("#1e293b")
GOLD_ACCENT    = colors.HexColor("#b48608")  # Police Gold/Amber
BG_LIGHT       = colors.HexColor("#f8fafc")
BG_CARD        = colors.HexColor("#f1f5f9")
TEXT_DARK      = colors.HexColor("#0f172a")
TEXT_MUTED     = colors.HexColor("#475569")
BORDER_LIGHT   = colors.HexColor("#cbd5e1")

# Status badge colors
COLOR_APPROVED = colors.HexColor("#15803d")
COLOR_REJECTED = colors.HexColor("#b91c1c")
COLOR_MODIFIED = colors.HexColor("#b45309")
COLOR_CLOSED   = colors.HexColor("#475569")
COLOR_BLUE     = colors.HexColor("#1d4ed8")

def format_inr(val) -> str:
    if val is None or val == "":
        return "₹0"
    try:
        n = int(float(val))
        if n >= 10000000:
            return f"₹{n/10000000:.2f} Cr"
        elif n >= 100000:
            return f"₹{n/100000:.2f} Lakh"
        else:
            return f"₹{n:,}"
    except Exception:
        return str(val)

def generate_decision_brief_pdf(prop_id: str) -> bytes:
    """
    Generates a high-quality Decision Brief PDF in-memory and returns raw bytes.
    """
    prop = proposals.get_proposal(prop_id)
    if not prop:
        raise ValueError(f"Proposal with ID '{prop_id}' not found.")

    # Retrieve precedents and precedent pulse
    similar = precedents.search_precedents(
        query_text=f"{prop.get('title','')} {prop.get('description','')}",
        category=prop.get("category"),
        department=prop.get("department"),
        exclude_id=prop.get("id"),
        top_k=4
    )
    pulse = precedents.build_precedent_pulse(similar)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    style_header_top = ParagraphStyle(
        'HeaderTop',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=NAVY_PRIMARY,
        alignment=TA_CENTER
    )
    style_header_sub = ParagraphStyle(
        'HeaderSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=TEXT_MUTED,
        alignment=TA_CENTER
    )
    style_doc_title = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=GOLD_ACCENT,
        alignment=TA_CENTER,
        spaceAfter=6
    )
    style_sec_heading = ParagraphStyle(
        'SecHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=NAVY_PRIMARY,
        spaceBefore=8,
        spaceAfter=4
    )
    style_cell_label = ParagraphStyle(
        'CellLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=NAVY_SECONDARY
    )
    style_cell_val = ParagraphStyle(
        'CellVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=TEXT_DARK
    )
    style_pulse_text = ParagraphStyle(
        'PulseText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=12,
        textColor=NAVY_PRIMARY
    )
    style_remark_item = ParagraphStyle(
        'RemarkItem',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=TEXT_DARK
    )

    elements = []

    # 1. Header Banner
    elements.append(Paragraph("GOVERNMENT OF PUDUCHERRY · POLICE DEPARTMENT", style_header_top))
    elements.append(Paragraph("INTELLIGENT PROPOSAL MANAGEMENT & PRECEDENT RETRIEVAL SYSTEM (IPMPRS)", style_header_sub))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("EXECUTIVE DECISION BRIEF & PRECEDENT APPRAISAL", style_doc_title))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=GOLD_ACCENT, spaceBefore=2, spaceAfter=8))

    # 2. Meta Strip: Ref No, Date, Security Grading
    now_str = datetime.now().strftime("%d %b %Y, %H:%M")
    meta_table_data = [
        [
            Paragraph(f"<b>Ref No:</b> {prop.get('ref_no')}", style_cell_label),
            Paragraph(f"<b>Status:</b> {prop.get('status').upper()}", style_cell_label),
            Paragraph(f"<b>Generated:</b> {now_str}", style_cell_label),
            Paragraph("<b>Security:</b> CONFIDENTIAL / OFFICIAL RECORD", style_cell_label),
        ]
    ]
    meta_table = Table(meta_table_data, colWidths=[130, 110, 130, 150])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BG_CARD),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 8))

    # 3. Proposal Details Table
    elements.append(Paragraph("1. PROPOSAL OVERVIEW & FINANCIAL PARTICULARS", style_sec_heading))
    overview_data = [
        [
            Paragraph("<b>Subject / Title:</b>", style_cell_label),
            Paragraph(prop.get("title", ""), style_cell_val),
            Paragraph("<b>Priority:</b>", style_cell_label),
            Paragraph(prop.get("priority", "Medium"), style_cell_val),
        ],
        [
            Paragraph("<b>Category:</b>", style_cell_label),
            Paragraph(prop.get("category", ""), style_cell_val),
            Paragraph("<b>Requesting Unit:</b>", style_cell_label),
            Paragraph(prop.get("department", ""), style_cell_val),
        ],
        [
            Paragraph("<b>Estimated Outlay:</b>", style_cell_label),
            Paragraph(f"<b>{format_inr(prop.get('estimated_cost'))}</b> ({int(prop.get('estimated_cost',0)):,} INR)", style_cell_val),
            Paragraph("<b>Initiating Officer:</b>", style_cell_label),
            Paragraph(f"{prop.get('created_by', '')} ({prop.get('created_at','')[:10]})", style_cell_val),
        ],
        [
            Paragraph("<b>Justification:</b>", style_cell_label),
            Paragraph(prop.get("justification", ""), style_cell_val),
            Paragraph("<b>Description:</b>", style_cell_label),
            Paragraph(prop.get("description", "")[:280] + ("..." if len(prop.get("description","")) > 280 else ""), style_cell_val),
        ]
    ]
    t_overview = Table(overview_data, colWidths=[90, 180, 90, 160])
    t_overview.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
        ('BACKGROUND', (0, 0), (0, -1), BG_LIGHT),
        ('BACKGROUND', (2, 0), (2, -1), BG_LIGHT),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_overview)
    elements.append(Spacer(1, 8))

    # 4. Precedent Pulse Intelligence Box
    elements.append(Paragraph("2. PRECEDENT PULSE · HISTORICAL INTELLIGENCE SUMMARY", style_sec_heading))
    pulse_text = (
        f"<b>PRECEDENT PULSE:</b> {pulse.get('summary_line')}<br/>"
        f"<i>Automated hybrid search matched {len(similar)} past department proposals with similar scope. "
        f"Average historical turnaround: {pulse.get('avg_decision_days', 18)} days.</i>"
    )
    t_pulse = Table([[Paragraph(pulse_text, style_pulse_text)]], colWidths=[520])
    t_pulse.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#fefce8")),  # Warm amber highlight
        ('BOX', (0, 0), (-1, -1), 1, GOLD_ACCENT),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t_pulse)
    elements.append(Spacer(1, 8))

    # 5. Top Matched Precedents Table
    elements.append(Paragraph("3. TOP SURFACED PRECEDENTS & PAST OUTCOMES", style_sec_heading))
    prec_rows = [
        [
            Paragraph("<b>Ref No</b>", style_cell_label),
            Paragraph("<b>Title & Key Scope</b>", style_cell_label),
            Paragraph("<b>Match</b>", style_cell_label),
            Paragraph("<b>Outcome</b>", style_cell_label),
            Paragraph("<b>Decision Reason / Lessons Learned</b>", style_cell_label)
        ]
    ]

    for prec in similar:
        stat = prec.get("status", "Unknown")
        stat_color = COLOR_APPROVED if stat in ["Approved", "Implemented"] else (
            COLOR_REJECTED if stat == "Rejected" else (
                COLOR_MODIFIED if prec.get("decision_type") == "Approve with Modification" else COLOR_CLOSED
            )
        )
        outcome_markup = f"<font color='{stat_color.hexval()}'><b>{stat.upper()}</b></font>"

        reason_text = prec.get("explanation") or prec.get("decision_reason") or prec.get("lessons_learned") or "Precedent identified by lexical and semantic overlap."

        prec_rows.append([
            Paragraph(f"<b>{prec.get('ref_no')}</b>", style_cell_val),
            Paragraph(prec.get("title", "")[:85] + ("..." if len(prec.get("title","")) > 85 else ""), style_cell_val),
            Paragraph(f"<b>{prec.get('similarity', 0)}%</b>", style_cell_val),
            Paragraph(outcome_markup, style_cell_val),
            Paragraph(reason_text[:130] + ("..." if len(reason_text) > 130 else ""), style_cell_val)
        ])

    if len(prec_rows) == 1:
        prec_rows.append([
            Paragraph("—", style_cell_val),
            Paragraph("No past precedents identified in repository.", style_cell_val),
            Paragraph("0%", style_cell_val),
            Paragraph("—", style_cell_val),
            Paragraph("—", style_cell_val)
        ])

    t_prec = Table(prec_rows, colWidths=[80, 160, 45, 75, 160])
    t_prec.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BG_CARD),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_prec)
    elements.append(Spacer(1, 8))

    # 6. Officer Remarks so far
    elements.append(Paragraph("4. OFFICER REMARKS & OBSERVATIONS", style_sec_heading))
    remarks_list = prop.get("remarks", [])
    if remarks_list:
        rem_rows = []
        for r in remarks_list[-3:]:  # Last 3 remarks
            rem_rows.append([
                Paragraph(f"<b>{r.get('author')}</b><br/><i>{r.get('role')} ({r.get('timestamp','')[:10]})</i>", style_cell_label),
                Paragraph(r.get("text", ""), style_remark_item)
            ])
        t_rem = Table(rem_rows, colWidths=[130, 390])
        t_rem.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(t_rem)
    else:
        elements.append(Paragraph("<i>No officer remarks recorded yet.</i>", style_cell_val))

    elements.append(Spacer(1, 14))

    # 7. Signature & Endorsement Block
    endorse_data = [
        [
            Paragraph("<b>Scrutiny by Reviewing Officer</b><br/><br/><br/>____________________________<br/>DSP / Reviewing Officer<br/>Puducherry Police", style_cell_val),
            Paragraph("<b>Decision of Approving Authority</b><br/>[ &nbsp; ] Approved as Proposed<br/>[ &nbsp; ] Approved with Modification<br/>[ &nbsp; ] Rejected &nbsp;&nbsp; [ &nbsp; ] Returned<br/><br/>____________________________<br/>Superintendent of Police / SSP", style_cell_val),
        ]
    ]
    t_endorse = Table(endorse_data, colWidths=[260, 260])
    t_endorse.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
        ('BACKGROUND', (0, 0), (-1, -1), BG_LIGHT),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(KeepTogether(t_endorse))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
