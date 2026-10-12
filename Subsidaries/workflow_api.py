"""Flask routes for the isolated local proposal-workflow demo."""

import os
import re
import secrets
import uuid
from io import BytesIO

from flask import Blueprint, current_app, jsonify, request, send_file, session

import proposals
import doc_generator
from proposal_ai import create_draft_from_scan
import workflow
from precedent_index import precedent_index
from workflow_config import ACTIVE_PROPOSAL_STATUSES, SIMILARITY_THRESHOLDS


workflow_api = Blueprint("workflow_api", __name__)


def _login_required():
    user = workflow.current_user()
    if not user:
        return None, (jsonify({"error": "Login required."}), 401)
    return user, None


def _visible_proposal(proposal_id, user):
    proposal = proposals.get_proposal(proposal_id)
    if not proposal or not workflow.can_view_proposal(proposal, user):
        return None
    return proposal


def _template_explanation(draft_text, precedent_text):
    stop_words = {"about", "after", "also", "and", "from", "have", "into", "more", "need", "north", "patrol", "police", "procurement", "that", "their", "this", "vehicles", "with", "zone", "for"}
    draft_terms = set(re.findall(r"[\w]+", draft_text.lower(), flags=re.UNICODE))
    precedent_terms = set(re.findall(r"[\w]+", precedent_text.lower(), flags=re.UNICODE))
    shared = sorted(term for term in draft_terms & precedent_terms if len(term) > 2 and term not in stop_words)
    if shared:
        return "Both proposal texts mention " + ", ".join(shared[:5]) + "."
    return "The proposal texts share no clear terms; review the cited record and its decision remark."


def _why_similar(draft_text, hit, generate):
    if generate:
        gateway = current_app.extensions.get("workflow_gateway")
        model = current_app.extensions.get("workflow_model")
        if gateway:
            try:
                response = gateway.call(
                    model,
                    [
                        {"role": "system", "content": "Compare only the two supplied proposal texts. State one or two concrete shared points. Do not infer facts, recommendations, or outcomes not present in those texts."},
                        {"role": "user", "content": "DRAFT TEXT:\n" + draft_text[:2000] + "\n\nPRECEDENT TEXT:\n" + hit["comparison_text"][:2000]},
                    ],
                    timeout=15,
                    options={"temperature": 0},
                )
                explanation = str(response.content or "").strip()
                if explanation:
                    return explanation[:600]
            except Exception as exc:
                current_app.logger.info("Similarity explanation fallback: %s", exc)
    return _template_explanation(draft_text, hit["comparison_text"])


def _similar_proposals(draft_text, filters=None, exclude_id=None):
    hits = precedent_index.search(draft_text, filters=filters, k=5, exclude_id=exclude_id)
    results = []
    for position, hit in enumerate(hits):
        metadata = hit["metadata"]
        result = {
            "id": hit["id"],
            "title": hit["title"],
            "status": metadata["status"],
            "outcome": metadata["outcome"],
            "outcome_detail": metadata["outcome_detail"],
            "cost": metadata["cost"],
            "decided_by": metadata["decided_by"],
            "decision_remark": metadata["decision_remark"] or "No decision remark recorded.",
            "similarity": max(0.0, min(1.0, float(hit["score"]))),
            "why_similar": _why_similar(draft_text, hit, position < 3),
            "keyword_only": hit["keyword_only"],
            "matched_terms": hit["matched_terms"],
        }
        results.append(result)

    rejected = next((
        result for result in results
        if result["status"].lower() == "rejected"
        and result["similarity"] >= SIMILARITY_THRESHOLDS["previously_rejected"]
    ), None)
    active = next((
        result for result in results
        if result["status"] in ACTIVE_PROPOSAL_STATUSES
        and result["similarity"] >= SIMILARITY_THRESHOLDS["possible_duplicate"]
    ), None)
    alerts = {
        "previously_rejected": ({"proposal_id": rejected["id"], "decision_remark": rejected["decision_remark"]} if rejected else None),
        "possible_duplicate": ({"proposal_id": active["id"], "title": active["title"], "status": active["status"], "decision_remark": active["decision_remark"]} if active else None),
    }
    return results, alerts


@workflow_api.get("/workflow")
def workflow_page():
    page = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflow.html")
    return send_file(page, mimetype="text/html")


@workflow_api.post("/api/workflow/login")
def login():
    data = request.get_json(silent=True) or {}
    user = workflow.authenticate(data.get("username"), data.get("password"))
    if not user:
        return jsonify({"error": "Invalid username or password."}), 401
    session.clear()
    session["workflow_user"] = user
    return jsonify({"user": user})


@workflow_api.post("/api/workflow/logout")
def logout():
    session.clear()
    return jsonify({"success": True})


@workflow_api.get("/api/workflow/me")
def me():
    user, error = _login_required()
    return error or jsonify({"user": user})


@workflow_api.get("/api/workflow/dashboard")
def dashboard():
    user, error = _login_required()
    if error:
        return error
    all_proposals = proposals.list_proposals(limit=500)
    visible = [p for p in all_proposals if workflow.can_view_proposal(p, user)]
    stats = proposals.get_proposal_stats()
    return jsonify({"user": user, "stats": stats, "proposals": visible})


@workflow_api.get("/api/workflow/proposals/<proposal_id>")
def proposal_detail(proposal_id):
    user, error = _login_required()
    if error:
        return error
    proposal = _visible_proposal(proposal_id, user)
    if not proposal:
        return jsonify({"error": "Proposal not found."}), 404
    return jsonify({"proposal": proposal})


@workflow_api.post("/api/proposals/similar")
def find_similar_proposals():
    user, error = _login_required()
    if error:
        return error
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    if not title and not description:
        return jsonify({"error": "Title or description is required."}), 400
    filters = {key: data[key] for key in ("category", "department") if data.get(key)}
    results, alerts = _similar_proposals(
        "\n".join(part for part in (title, description) if part),
        filters=filters,
        exclude_id=data.get("exclude_id"),
    )
    return jsonify({"results": results, "alerts": alerts, "thresholds": SIMILARITY_THRESHOLDS})


@workflow_api.get("/api/proposals/<proposal_id>/precedents")
def get_proposal_precedents(proposal_id):
    user, error = _login_required()
    if error:
        return error
    proposal = _visible_proposal(proposal_id, user)
    if not proposal:
        return jsonify({"error": "Proposal not found."}), 404
    draft_text = "\n".join((proposal.get("title", ""), proposal.get("description", ""), proposal.get("justification", "")))
    results, alerts = _similar_proposals(
        draft_text,
        exclude_id=proposal["id"],
    )
    return jsonify({"proposal_id": proposal["id"], "results": results, "alerts": alerts})


@workflow_api.post("/api/workflow/proposals")
def create_proposal():
    user, error = _login_required()
    if error:
        return error
    if user["role"] != "initiator":
        return jsonify({"error": "Only initiators can create proposals."}), 403
    data = request.get_json(silent=True) or {}
    required = ("title", "category", "department", "description", "justification")
    if any(not str(data.get(key, "")).strip() for key in required):
        return jsonify({"error": "Title, category, department, description and justification are required."}), 400
    try:
        cost = float(data.get("estimated_cost", 0) or 0)
        if cost < 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Estimated cost must be a non-negative number."}), 400
    proposal = proposals.create_proposal(
        title=str(data["title"]).strip(),
        category=str(data["category"]).strip(),
        department=str(data["department"]).strip(),
        description=str(data["description"]).strip(),
        justification=str(data["justification"]).strip(),
        estimated_cost=cost,
        priority=str(data.get("priority", "Medium")),
        created_by=user["name"],
        actor_role="Initiator",
    )
    return jsonify({"proposal": proposal}), 201


@workflow_api.put("/api/workflow/proposals/<proposal_id>")
def update_proposal(proposal_id):
    user, error = _login_required()
    if error:
        return error
    proposal = _visible_proposal(proposal_id, user)
    if not proposal:
        return jsonify({"error": "Proposal not found."}), 404
    if user["role"] != "initiator" or proposal["created_by"] != user["name"]:
        return jsonify({"error": "Only the owning initiator can edit this proposal."}), 403
    try:
        updated = proposals.update_proposal(
            proposal_id, request.get_json(silent=True) or {}, user["name"], "Initiator"
        )
        return jsonify({"proposal": updated})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@workflow_api.post("/api/workflow/proposals/<proposal_id>/transition")
def transition_proposal(proposal_id):
    user, error = _login_required()
    if error:
        return error
    proposal = _visible_proposal(proposal_id, user)
    if not proposal:
        return jsonify({"error": "Proposal not found."}), 404
    data = request.get_json(silent=True) or {}
    target = data.get("to_status")
    try:
        if target in ("Approved", "Rejected"):
            decision_type = "Approve" if target == "Approved" else "Reject"
            updated = proposals.record_decision(
                proposal_id,
                decision_type,
                user["name"],
                str(data.get("remark", "")).strip(),
                sanctioned_amount=data.get("sanctioned_amount"),
                role="Approving Authority" if user["role"] == "approver" else user["role"],
            )
        else:
            updated = proposals.transition_proposal(
                proposal_id, target, user["name"], user["role"], str(data.get("remark", "")).strip()
            )
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400
    event = {"Submitted": "submit", "Approved": "approve", "Rejected": "reject"}.get(target, "transition")
    workflow.notify_listeners(event, updated)
    return jsonify({"proposal": updated})


@workflow_api.post("/api/workflow/proposals/<proposal_id>/remarks")
def add_remark(proposal_id):
    user, error = _login_required()
    if error:
        return error
    proposal = _visible_proposal(proposal_id, user)
    if not proposal:
        return jsonify({"error": "Proposal not found."}), 404
    text = str((request.get_json(silent=True) or {}).get("remark", "")).strip()
    if not text:
        return jsonify({"error": "Decision remark is required."}), 400
    updated = proposals.add_remark(proposal_id, user["name"], user["role"], text)
    return jsonify({"proposal": updated})


@workflow_api.post("/api/workflow/proposal-ai/draft")
def ai_draft_from_scan():
    user, error = _login_required()
    if error:
        return error
    if user["role"] != "initiator":
        return jsonify({"error": "Only initiators can create proposal drafts."}), 403
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Choose a scanned PDF or image."}), 400
    extension = os.path.splitext(os.path.basename(uploaded.filename))[1].lower()
    if extension not in {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}:
        return jsonify({"error": "Only scanned PDFs and image files are supported."}), 415
    file_bytes = uploaded.read(16 * 1024 * 1024 + 1)
    if len(file_bytes) > 16 * 1024 * 1024:
        return jsonify({"error": "Scan file exceeds the 16 MB limit."}), 413
    try:
        drafted = create_draft_from_scan(
            uploaded.filename,
            file_bytes,
            current_app.extensions.get("workflow_gateway"),
            current_app.extensions.get("workflow_model"),
        )
        fields = drafted["draft"]
        proposal = proposals.create_proposal(
            title=fields["title"],
            category=fields["category"],
            department=fields["department"],
            description=fields["description"],
            justification=fields["justification"],
            estimated_cost=fields["estimated_cost"],
            priority=fields["priority"],
            created_by=user["name"],
            actor_role="Initiator",
        )
        source_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "proposal_sources")
        os.makedirs(source_dir, exist_ok=True)
        source_path = os.path.join(source_dir, proposal["id"] + extension)
        with open(source_path, "wb") as source_file:
            source_file.write(file_bytes)
        connection = proposals.get_db_connection()
        with connection:
            connection.execute(
                "INSERT INTO proposal_attachments (id, proposal_id, filename, file_path, file_size, uploaded_at) VALUES (?, ?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, proposal["id"], os.path.basename(uploaded.filename), source_path, len(file_bytes), proposal["created_at"]),
            )
        connection.close()
        proposal = proposals.get_proposal(proposal["id"])
        return jsonify({"proposal": proposal, "ai_drafted": drafted["ai_drafted"], "ocr_confidence": drafted["ocr_confidence"]}), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    except Exception as exc:
        current_app.logger.exception("AI scan draft failed")
        return jsonify({"error": f"Could not create a draft from this scan: {exc}"}), 500


@workflow_api.get("/api/workflow/proposals/<proposal_id>/verify")
def verify_audit_trail(proposal_id):
    user, error = _login_required()
    if error:
        return error
    if not _visible_proposal(proposal_id, user):
        return jsonify({"error": "Proposal not found."}), 404
    return jsonify(proposals.verify_audit_trail(proposal_id))


@workflow_api.get("/api/workflow/proposals/<proposal_id>/report.docx")
def download_proposal_report(proposal_id):
    user, error = _login_required()
    if error:
        return error
    proposal = _visible_proposal(proposal_id, user)
    if not proposal:
        return jsonify({"error": "Proposal not found."}), 404
    proposal["decision"] = proposal.get("latest_decision")
    report = doc_generator.generate_docx(
        proposal.get("title", "Proposal Report"),
        proposal=proposal,
    )
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", proposal.get("ref_no", proposal_id))[:80]
    return send_file(
        BytesIO(report),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=f"{safe_name}.docx",
    )


def init_workflow(app, gateway=None, model=None):
    app.secret_key = os.environ.get("IPMPRS_SECRET_KEY") or secrets.token_urlsafe(32)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.extensions["workflow_gateway"] = gateway
    app.extensions["workflow_model"] = model
    app.register_blueprint(workflow_api)
    return app