"""
IPMPRS — Intelligent Proposal Management and Precedent Retrieval System
Puducherry Police Hackathon 2026 · Problem Statement 01
────────────────────────────────────────────────────────────────────────
Flask backend — Proposal Management, Precedent Engine, Audit Trail & RAG
"""

import os
import sys
import uuid
import time
import json
import io
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# Suppress HuggingFace symlinks warning on Windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import ollama
except ImportError:
    print("[ERROR] ollama not installed. Run: pip install ollama")
    exit(1)

# ─── Multi-Model & Knowledge Architecture ───────────────────────────
from gateway import ModelGateway, GatewayError, ModelNotFoundError
from router import ModelRouter
from ingestion import IngestionPipeline
from knowledge_base import KnowledgeBase, chunk_document
from memory_store import MemoryStore
from multimodal import ocr_any

# ─── IPMPRS Domain Modules ──────────────────────────────────────────
import proposals
import precedents
import brief
import seed_data
import doc_generator

# ─── App Setup ──────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)  # Allow all origins for local development

DEFAULT_MODEL = os.environ.get("ARIA_MODEL", "llama3.2")

POLICE_SYSTEM_PROMPT = (
    "You are IPMPRS, an intelligent proposal management and precedent analysis assistant "
    "for the Puducherry Police Department. You help police officers search, evaluate, "
    "and cross-reference administrative, technical, procurement, infrastructure, "
    "training, and operational proposals against historical precedents, sanctions, "
    "rejection reasons, and post-closure lessons learned."
)

# ─── Initialize Core Components ─────────────────────────────────────
gateway            = ModelGateway(default_model=DEFAULT_MODEL, keep_alive="5m")
router             = ModelRouter(default_model=DEFAULT_MODEL)
knowledge_base     = KnowledgeBase()
ingestion_pipeline = IngestionPipeline()
memory_store       = MemoryStore()

AVAILABLE_MODELS = [
    {"id": "llama3.2", "name": "Llama 3.2 3B", "description": "Default police reasoning & analysis model", "tasks": ["reasoning", "general"]},
    {"id": "qwen3:4b", "name": "Qwen 3 4B",    "description": "Technical specifications specialist",       "tasks": ["code", "technical"]},
    {"id": "phi3",     "name": "Phi-3 Mini",   "description": "Fast local fallback model",                 "tasks": ["general"]},
]

# Ensure sample data exists on first startup
try:
    stats = proposals.get_proposal_stats()
    if stats.get("total_proposals", 0) == 0:
        print("[IPMPRS] Empty database detected. Seeding initial proposals...")
        seed_data.seed_database(reset=False)
except Exception as e:
    print(f"[IPMPRS] Database check warning: {e}")

# ════════════════════════════════════════════════════════════════════
#   STATIC FILES & UI SERVING
# ════════════════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def index_route():
    return send_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"), mimetype="text/html")

@app.route("/index.html", methods=["GET"])
def index_html():
    return send_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"), mimetype="text/html")

@app.route("/cmpdi.css", methods=["GET"])
def serve_css():
    return send_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cmpdi.css"), mimetype="text/css")

@app.route("/cmpdi.js", methods=["GET"])
def serve_js():
    return send_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cmpdi.js"), mimetype="application/javascript")

@app.route("/hf_20260405_171521_25968ba2-b594-4b32-aab7-f6b69398a6fa.mp4", methods=["GET"])
def serve_bg_video():
    video_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hf_20260405_171521_25968ba2-b594-4b32-aab7-f6b69398a6fa.mp4")
    if os.path.exists(video_path):
        return send_file(video_path, mimetype="video/mp4")
    return ("", 404)

@app.route("/enchance_the_video_quality_int.mp4", methods=["GET"])
def serve_bg_video_enchance():
    video_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "enchance_the_video_quality_int.mp4")
    if os.path.exists(video_path):
        return send_file(video_path, mimetype="video/mp4")
    return ("", 404)

# ════════════════════════════════════════════════════════════════════
#   CORE SYSTEM & HEALTH ENDPOINTS
# ════════════════════════════════════════════════════════════════════

@app.route("/api/health", methods=["GET"])
def health():
    available = gateway.is_available()
    prop_stats = proposals.get_proposal_stats()
    return jsonify({
        "status": "healthy" if available else "ollama_offline_mode",
        "service": "IPMPRS — Puducherry Police Proposal Management System",
        "ollama_running": available,
        "default_model": DEFAULT_MODEL,
        "total_proposals": prop_stats.get("total_proposals", 0),
        "gateway_stats": gateway.stats() if available else {}
    })

@app.route("/api/models", methods=["GET"])
def models():
    pulled_names = set(gateway.list_available()) if gateway.is_available() else set()
    result = []
    for m in AVAILABLE_MODELS:
        entry = dict(m)
        entry["pulled"] = any(m["id"] in name for name in pulled_names) if pulled_names else False
        result.append(entry)
    return jsonify({
        "models": result,
        "routing_table": router.get_routing_table()
    })

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])
    if not messages:
        return jsonify({"error": "No messages provided."}), 400

    query = messages[-1].get("content", "")
    if not gateway.is_available():
        # Offline rule-based precedent retrieval response
        precs = precedents.search_precedents(query, top_k=3)
        pulse = precedents.build_precedent_pulse(precs)
        prec_lines = [f"• {p['ref_no']} ({p['status']}): {p['title']} — {p.get('explanation','')}" for p in precs]
        answer = (
            f"**IPMPRS Precedent Advisory (Offline Mode):**\n\n"
            f"{pulse['summary_line']}\n\n"
            + ("\n".join(prec_lines) if prec_lines else "No direct matching past proposals found.")
        )
        return jsonify({
            "message": {"role": "assistant", "content": answer},
            "model": "rule_based_precedent_engine",
            "offline": True
        })

    try:
        reply = gateway.generate(
            prompt=query,
            system_prompt=POLICE_SYSTEM_PROMPT,
            max_tokens=600
        )
        return jsonify({
            "message": {"role": "assistant", "content": reply},
            "model": DEFAULT_MODEL
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ════════════════════════════════════════════════════════════════════
#   IPMPRS PROPOSAL MANAGEMENT ENDPOINTS
# ════════════════════════════════════════════════════════════════════

@app.route("/api/proposals", methods=["POST"])
def api_create_proposal():
    """Create a new proposal in Draft status."""
    data = request.get_json(silent=True) or {}
    required = ["title", "category", "department", "description", "justification"]
    for r in required:
        if not data.get(r):
            return jsonify({"error": f"Field '{r}' is required."}), 400

    try:
        cost = float(data.get("estimated_cost", 0.0))
    except (ValueError, TypeError):
        cost = 0.0

    prop = proposals.create_proposal(
        title=data["title"].strip(),
        category=data["category"].strip(),
        department=data["department"].strip(),
        description=data["description"].strip(),
        justification=data["justification"].strip(),
        estimated_cost=cost,
        priority=data.get("priority", "Medium"),
        created_by=data.get("created_by", "Dealing Assistant"),
        actor_role=data.get("role", "Initiator")
    )

    # Automatically surface and link top matching precedents for the Precedent Gate
    precs = precedents.search_precedents(
        query_text=f"{prop['title']} {prop['description']}",
        category=prop["category"],
        department=prop["department"],
        exclude_id=prop["id"],
        top_k=4,
        gateway=gateway
    )
    for p in precs:
        proposals.link_precedent(prop["id"], p["id"], p["similarity"])

    # Re-fetch proposal with linked precedents
    full_prop = proposals.get_proposal(prop["id"])
    return jsonify({"success": True, "proposal": full_prop}), 201

@app.route("/api/proposals", methods=["GET"])
def api_list_proposals():
    """List proposals with optional filters: status, category, department, search."""
    status = request.args.get("status")
    category = request.args.get("category")
    department = request.args.get("department")
    search = request.args.get("search")
    limit = int(request.args.get("limit", 100))

    items = proposals.list_proposals(
        status=status,
        category=category,
        department=department,
        search=search,
        limit=limit
    )
    return jsonify({"proposals": items, "count": len(items)})

@app.route("/api/proposals/<prop_id>", methods=["GET"])
def api_get_proposal(prop_id):
    """Get full proposal record with history, remarks, decisions, outcomes, precedent links."""
    prop = proposals.get_proposal(prop_id)
    if not prop:
        return jsonify({"error": "Proposal not found."}), 404

    # Calculate live Precedent Pulse for this proposal
    linked_ids = [l["precedent_id"] for l in prop.get("precedent_links", [])]
    if linked_ids:
        # Fetch precedent proposals
        precs = []
        for lid in linked_ids:
            p_obj = proposals.get_proposal(lid)
            if p_obj:
                precs.append(p_obj)
        prop["precedent_pulse"] = precedents.build_precedent_pulse(precs)
    else:
        # Search live top 3
        similar = precedents.search_precedents(
            query_text=f"{prop.get('title','')} {prop.get('description','')}",
            category=prop.get("category"),
            department=prop.get("department"),
            exclude_id=prop.get("id"),
            top_k=4,
            gateway=gateway
        )
        prop["precedent_pulse"] = precedents.build_precedent_pulse(similar)

    return jsonify({"proposal": prop})

@app.route("/api/proposals/<prop_id>", methods=["PUT"])
def api_update_proposal(prop_id):
    """Edit proposal details (only permitted in Draft or Returned for Revision status)."""
    data = request.get_json(silent=True) or {}
    actor = data.get("actor", "Dealing Assistant")
    role = data.get("role", "Initiator")

    try:
        updated = proposals.update_proposal(prop_id, data, actor=actor, role=role)
        return jsonify({"success": True, "proposal": updated})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/proposals/<prop_id>/transition", methods=["POST"])
def api_transition_proposal(prop_id):
    """Advance proposal to next status. Enforces state machine rules and Precedent Gate."""
    data = request.get_json(silent=True) or {}
    to_status = data.get("to_status")
    actor = data.get("actor", "Authorized Officer")
    role = data.get("role", "Initiator")
    note = data.get("note", "")

    if not to_status:
        return jsonify({"error": "Target status 'to_status' is required."}), 400

    try:
        updated = proposals.transition_proposal(
            prop_id=prop_id,
            to_status=to_status,
            actor=actor,
            role=role,
            note=note
        )
        return jsonify({"success": True, "proposal": updated})
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/proposals/<prop_id>/remarks", methods=["POST"])
def api_add_remark(prop_id):
    """Add an officer observation or remark."""
    data = request.get_json(silent=True) or {}
    author = data.get("author", "Officer")
    role = data.get("role", "Reviewer")
    text = data.get("text", "").strip()

    if not text:
        return jsonify({"error": "Remark text cannot be empty."}), 400

    try:
        updated = proposals.add_remark(prop_id, author, role, text)
        return jsonify({"success": True, "proposal": updated})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/proposals/<prop_id>/decision", methods=["POST"])
def api_record_decision(prop_id):
    """Record formal decision and sanction details (auto-drives state transition)."""
    data = request.get_json(silent=True) or {}
    decision_type = data.get("decision_type")
    decided_by = data.get("decided_by", "SP / Approving Authority")
    reason = data.get("reason", "").strip()
    sanction_order_no = data.get("sanction_order_no")
    sanctioned_amount = data.get("sanctioned_amount")
    conditions = data.get("conditions")
    role = data.get("role", "Approving Authority")

    if not decision_type or not reason:
        return jsonify({"error": "Both 'decision_type' and 'reason' are required."}), 400

    try:
        amt = float(sanctioned_amount) if sanctioned_amount is not None and sanctioned_amount != "" else None
    except ValueError:
        amt = None

    try:
        updated = proposals.record_decision(
            prop_id=prop_id,
            decision_type=decision_type,
            decided_by=decided_by,
            reason=reason,
            sanction_order_no=sanction_order_no,
            sanctioned_amount=amt,
            conditions=conditions,
            role=role
        )
        return jsonify({"success": True, "proposal": updated})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/proposals/<prop_id>/outcome", methods=["POST"])
def api_record_outcome(prop_id):
    """Record implementation outcome and lessons learned."""
    data = request.get_json(silent=True) or {}
    impl_status = data.get("implementation_status", "Completed Successfully")
    actual_cost = data.get("actual_cost")
    completion_date = data.get("completion_date")
    summary = data.get("outcome_summary", "")
    lessons = data.get("lessons_learned", "")
    actor = data.get("actor", "Reviewing Officer")
    role = data.get("role", "Reviewer")

    try:
        cost = float(actual_cost) if actual_cost is not None and actual_cost != "" else None
    except ValueError:
        cost = None

    try:
        updated = proposals.record_outcome(
            prop_id=prop_id,
            implementation_status=impl_status,
            actual_cost=cost,
            completion_date=completion_date,
            outcome_summary=summary,
            lessons_learned=lessons,
            actor=actor,
            role=role
        )
        return jsonify({"success": True, "proposal": updated})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ════════════════════════════════════════════════════════════════════
#   PRECEDENT RETRIEVAL & PRECEDENT GATE ENDPOINTS
# ════════════════════════════════════════════════════════════════════

@app.route("/api/precedents/search", methods=["POST"])
def api_search_precedents():
    """
    Live precedent search called while drafting title and description.
    Returns similar past proposals, match scores, duplicate flags,
    and explainability statements.
    """
    data = request.get_json(silent=True) or {}
    query = data.get("query", "").strip()
    category = data.get("category")
    department = data.get("department")
    exclude_id = data.get("exclude_id")
    top_k = int(data.get("top_k", 5))

    if not query:
        return jsonify({"precedents": [], "pulse": {}})

    results = precedents.search_precedents(
        query_text=query,
        category=category,
        department=department,
        exclude_id=exclude_id,
        top_k=top_k,
        gateway=gateway
    )
    pulse = precedents.build_precedent_pulse(results)
    duplicate_warning = any(r.get("is_duplicate", False) for r in results)

    return jsonify({
        "precedents": results,
        "pulse": pulse,
        "duplicate_warning": duplicate_warning
    })

@app.route("/api/proposals/<prop_id>/precedents", methods=["GET"])
def api_get_proposal_precedents(prop_id):
    """Retrieve precedents, acknowledgements, and pulse for a proposal."""
    prop = proposals.get_proposal(prop_id)
    if not prop:
        return jsonify({"error": "Proposal not found."}), 404

    links = prop.get("precedent_links", [])
    # Search live top 5 precedents
    similar = precedents.search_precedents(
        query_text=f"{prop.get('title','')} {prop.get('description','')}",
        category=prop.get("category"),
        department=prop.get("department"),
        exclude_id=prop.get("id"),
        top_k=5,
        gateway=gateway
    )
    pulse = precedents.build_precedent_pulse(similar)

    return jsonify({
        "links": links,
        "precedents": similar,
        "pulse": pulse
    })

@app.route("/api/proposals/<prop_id>/precedents/ack", methods=["POST"])
def api_acknowledge_precedent(prop_id):
    """
    Initiator marks precedent as 'relevant' or 'not_relevant' with a mandatory reason.
    Satisfies the Precedent Gate before Draft -> Submitted transition.
    """
    data = request.get_json(silent=True) or {}
    precedent_id = data.get("precedent_id")
    relevance = data.get("relevance")
    reason = data.get("reason", "").strip()
    actor = data.get("actor", "Initiator")

    if not precedent_id or not relevance or not reason:
        return jsonify({"error": "precedent_id, relevance ('relevant'|'not_relevant'), and reason are all required."}), 400

    try:
        updated = proposals.acknowledge_precedent(
            prop_id=prop_id,
            precedent_id=precedent_id,
            relevance=relevance,
            reason=reason,
            actor=actor
        )
        return jsonify({"success": True, "proposal": updated})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/proposals/<prop_id>/brief", methods=["GET"])
def api_download_brief(prop_id):
    """Download the official Decision Brief PDF for approving authorities."""
    prop = proposals.get_proposal(prop_id)
    if not prop:
        return jsonify({"error": "Proposal not found."}), 404

    try:
        pdf_bytes = brief.generate_decision_brief_pdf(prop_id)
        clean_ref = prop.get("ref_no", "proposal").replace("/", "_")
        filename = f"Decision_Brief_{clean_ref}.pdf"
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": f"Failed to generate brief PDF: {str(e)}"}), 500

@app.route("/api/proposals/<prop_id>/audit/verify", methods=["GET"])
def api_verify_audit_trail(prop_id):
    """Verifies the SHA-256 cryptographic chain of custody for a proposal."""
    result = proposals.verify_audit_trail(prop_id)
    return jsonify(result)

@app.route("/api/proposals/stats", methods=["GET"])
def api_get_proposal_stats():
    """Aggregated metrics and distributions for the Command Dashboard."""
    stats = proposals.get_proposal_stats()
    return jsonify(stats)

@app.route("/api/proposals/seed", methods=["POST"])
def api_seed_database():
    """Reset and re-seed the proposals database with 50+ realistic proposals."""
    try:
        seed_data.seed_database(reset=True)
        stats = proposals.get_proposal_stats()
        return jsonify({"success": True, "message": "Database reseeded successfully.", "stats": stats})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ════════════════════════════════════════════════════════════════════
#   ARCHIVE & DOCUMENT REPOSITORY ENDPOINTS
# ════════════════════════════════════════════════════════════════════

@app.route("/api/ingest", methods=["POST"])
def ingest_document():
    """Upload past order, circular, or tender into the Archive."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "No file selected."}), 400

    allowed = {".pdf", ".docx", ".xlsx", ".xls", ".csv", ".txt", ".md", ".png", ".jpg", ".jpeg"}
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in allowed:
        return jsonify({"error": f"Unsupported file type: {ext}"}), 415

    file_bytes = f.read()
    try:
        doc = ingestion_pipeline.ingest(f.filename, file_bytes)
        if not doc.success:
            return jsonify({"error": f"Ingestion failed: {doc.error}"}), 422

        if request.form.get("department"):
            doc.metadata["department"] = request.form.get("department")
        if request.form.get("category"):
            doc.metadata["category"] = request.form.get("category")

        knowledge_base.add_document(doc.to_summary_dict())
        chunks = chunk_document(doc)
        chunks_added = knowledge_base.add_chunks(doc.doc_id, chunks, gateway=gateway)
        knowledge_base.mark_indexed(doc.doc_id)

        return jsonify({
            "success": True,
            "doc_id": doc.doc_id,
            "filename": doc.filename,
            "page_count": doc.page_count,
            "char_count": doc.char_count,
            "chunks_indexed": chunks_added
        })
    except Exception as e:
        return jsonify({"error": f"Ingestion error: {str(e)}"}), 500

@app.route("/api/documents", methods=["GET"])
def list_documents():
    """List documents in the past proposals archive."""
    docs = knowledge_base.list_documents()
    stats = knowledge_base.stats()
    return jsonify({"documents": docs, "stats": stats})

@app.route("/api/documents/<doc_id>", methods=["DELETE"])
def delete_document(doc_id):
    """Delete document from archive."""
    success = knowledge_base.delete_document(doc_id)
    if success:
        return jsonify({"success": True, "doc_id": doc_id})
    return jsonify({"error": "Document not found."}), 404

@app.route("/api/kb/stats", methods=["GET"])
def kb_stats():
    return jsonify(knowledge_base.stats())

@app.route("/api/query", methods=["POST"])
def precedent_query():
    """
    Precedent Search: hybrid search over past proposals & archived police records.
    """
    data = request.get_json(silent=True) or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "Query cannot be empty."}), 400

    # 1. Search Proposals Precedent Store
    precs = precedents.search_precedents(query, top_k=6, gateway=gateway)
    pulse = precedents.build_precedent_pulse(precs)

    # 2. Search Ingested Documents Store
    doc_chunks = knowledge_base.hybrid_search(query, gateway=gateway, top_k=4)

    # 3. Synthesize structured answer if Gateway online
    answer = ""
    if gateway.is_available():
        context = "\n".join([
            f"Precedent {p['ref_no']}: {p['title']} (Status: {p['status']}, Outlay: {p.get('estimated_cost')}) - Reason: {p.get('decision_reason', 'N/A')}"
            for p in precs[:4]
        ])
        prompt = (
            f"You are a police proposal precedent analyst. Answer this officer query: '{query}'\n"
            f"Relevant historical precedents:\n{context}\n\n"
            f"Provide a clear, authoritative summary citing the specific past proposals, their outcomes, and key lessons."
        )
        try:
            answer = gateway.generate(prompt=prompt, system_prompt=POLICE_SYSTEM_PROMPT, max_tokens=350)
        except Exception:
            answer = pulse["summary_line"]
    else:
        answer = f"**Precedent Intelligence Summary:**\n{pulse['summary_line']}"

    return jsonify({
        "query": query,
        "answer": answer,
        "pulse": pulse,
        "precedents": precs,
        "archive_chunks": doc_chunks,
        "offline": not gateway.is_available()
    })

# ════════════════════════════════════════════════════════════════════
#   IMAGE OCR ENDPOINT
# ════════════════════════════════════════════════════════════════════

@app.route("/api/ocr", methods=["POST"])
def api_ocr():
    """
    Perform OCR on an uploaded image or scanned PDF.
    Returns extracted text, confidence score, and page count.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "No file selected."}), 400

    allowed_ocr = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".gif", ".webp", ".pdf"}
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in allowed_ocr:
        return jsonify({"error": f"File type '{ext}' not supported for OCR. Supported: PNG, JPG, BMP, TIFF, WEBP, PDF"}), 415

    file_bytes = f.read()
    try:
        result = ocr_any(f.filename, file_bytes)
        if not result.success:
            return jsonify({"error": result.error or "OCR produced no text."}), 422

        return jsonify({
            "success": True,
            "text": result.text,
            "page_texts": result.page_texts,
            "page_count": len(result.page_texts),
            "confidence": result.confidence,
            "ocr_engine": result.ocr_engine,
            "char_count": len(result.text),
        })
    except Exception as e:
        return jsonify({"error": f"OCR error: {str(e)}"}), 500


# ════════════════════════════════════════════════════════════════════
#   MEMORY & KNOWLEDGE BASE ENDPOINTS
# ════════════════════════════════════════════════════════════════════

@app.route("/api/memory/upload", methods=["POST"])
def memory_upload():
    """Upload a document into the persistent Memory/Knowledge Base."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "No file selected."}), 400

    allowed = {".pdf", ".docx", ".txt", ".md", ".csv", ".xlsx", ".xls",
               ".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in allowed:
        return jsonify({"error": f"Unsupported type: {ext}"}), 415

    file_bytes = f.read()
    try:
        doc = ingestion_pipeline.ingest(f.filename, file_bytes)
        if not doc.success:
            return jsonify({"error": f"Extraction failed: {doc.error}"}), 422

        saved = memory_store.save_document(f.filename, file_bytes, doc.raw_text)
        return jsonify({"success": True, "document": saved}), 201
    except Exception as e:
        return jsonify({"error": f"Memory upload error: {str(e)}"}), 500


@app.route("/api/memory/documents", methods=["GET"])
def memory_list():
    """List all documents stored in memory."""
    docs = memory_store.list_documents()
    total_chars = sum(d.get("char_count", 0) for d in docs)
    return jsonify({
        "documents": docs,
        "count": len(docs),
        "total_chars": total_chars,
    })


@app.route("/api/memory/documents/<doc_id>", methods=["DELETE"])
def memory_delete(doc_id):
    """Delete a document from memory."""
    success = memory_store.delete_document(doc_id)
    if success:
        return jsonify({"success": True})
    return jsonify({"error": "Document not found."}), 404


@app.route("/api/memory/clear", methods=["POST"])
def memory_clear():
    """Clear all documents from memory."""
    count = memory_store.clear_documents()
    return jsonify({"success": True, "deleted": count})


@app.route("/api/memory/search", methods=["POST"])
def memory_search():
    """Search memory documents for relevant context."""
    data = request.get_json(silent=True) or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "Query is required."}), 400

    results = memory_store.get_relevant_context(query, top_k=5, min_score=0.04)
    return jsonify({"results": results, "count": len(results)})


# ════════════════════════════════════════════════════════════════════
#   DOCUMENT GENERATION ENDPOINTS
# ════════════════════════════════════════════════════════════════════

@app.route("/api/generate/docx", methods=["POST"])
def api_generate_docx():
    """Generate a DOCX report from a proposal or free-form prompt."""
    data = request.get_json(silent=True) or {}
    prop_id  = data.get("prop_id")
    title    = data.get("title", "Police Report")
    content  = data.get("content", "")
    template = data.get("template", "standard")  # standard | brief | letter

    # If prop_id provided, fetch proposal data
    prop_data = None
    if prop_id:
        prop_data = proposals.get_proposal(prop_id)
        if not prop_data:
            return jsonify({"error": "Proposal not found."}), 404

    try:
        docx_bytes = doc_generator.generate_docx(
            title=title,
            content=content,
            proposal=prop_data,
            template=template,
            gateway=gateway if gateway.is_available() else None,
            system_prompt=POLICE_SYSTEM_PROMPT,
        )
        safe_title = title.replace(" ", "_")[:40]
        filename = f"{safe_title}.docx"
        return send_file(
            io.BytesIO(docx_bytes),
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": f"DOCX generation failed: {str(e)}"}), 500


@app.route("/api/generate/pdf", methods=["POST"])
def api_generate_pdf():
    """Generate a PDF report from a proposal or free-form prompt."""
    data = request.get_json(silent=True) or {}
    prop_id  = data.get("prop_id")
    title    = data.get("title", "Police Report")
    content  = data.get("content", "")

    prop_data = None
    if prop_id:
        prop_data = proposals.get_proposal(prop_id)
        if not prop_data:
            return jsonify({"error": "Proposal not found."}), 404

    try:
        if prop_id and prop_data:
            pdf_bytes = brief.generate_decision_brief_pdf(prop_id)
        else:
            pdf_bytes = doc_generator.generate_pdf(
                title=title,
                content=content,
                proposal=prop_data,
                gateway=gateway if gateway.is_available() else None,
                system_prompt=POLICE_SYSTEM_PROMPT,
            )
        safe_title = title.replace(" ", "_")[:40]
        filename = f"{safe_title}.pdf"
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": f"PDF generation failed: {str(e)}"}), 500


# ════════════════════════════════════════════════════════════════════
#   STARTUP & BANNER
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    ollama_status = "RUNNING" if gateway.is_available() else "OFFLINE (Using Rule/BM25 Fallback)"
    p_stats = proposals.get_proposal_stats()

    print(f"""
+-------------------------------------------------------------------+
|  IPMPRS — Puducherry Police Hackathon 2026                        |
|  Intelligent Proposal Management and Precedent Retrieval System   |
+-------------------------------------------------------------------+
|  Server URL:    http://localhost:{port:<37} |
|  Ollama Status: {ollama_status:<49} |
|  Default Model: {DEFAULT_MODEL:<49} |
+-------------------------------------------------------------------+
|  Proposal Database:                                               |
|    Total Proposals:   {p_stats['total_proposals']:<43} |
|    Under Review:      {p_stats['under_review']:<43} |
|    Approved:          {p_stats['approved']:<43} |
|    Rejected:          {p_stats['rejected']:<43} |
|    Avg Turnaround:    {str(p_stats['avg_decision_days']) + ' days':<43} |
+-------------------------------------------------------------------+
|  Core Endpoints Ready:                                            |
|    POST /api/proposals           -> Create proposal draft         |
|    GET  /api/proposals           -> List proposals with filters   |
|    POST /api/precedents/search   -> Live precedent match          |
|    POST /api/proposals/:id/ack   -> Precedent Gate verification   |
|    GET  /api/proposals/:id/brief -> Download Decision Brief (PDF) |
|    GET  /api/proposals/:id/verify-> Verify SHA-256 audit chain    |
+-------------------------------------------------------------------+
""")
    app.run(host="0.0.0.0", port=port, debug=False)