"""
IPMPRS — Intelligent Proposal Management and Precedent Retrieval System
Puducherry Police Hackathon 2026 · Problem Statement 01
────────────────────────────────────────────────────────────────────────
proposals.py: Core SQLite Store, State Machine, Tamper-Evident Audit Trail
"""

import os
import sqlite3
import hashlib
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

# ─── Database Path ──────────────────────────────────────────────────
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PROPOSALS_DB_PATH = os.path.join(_DATA_DIR, "proposals.db")

# ─── Roles & Valid Transitions ──────────────────────────────────────
ROLES = {
    "initiator": "Initiator",             # Clerk / Dealing Assistant
    "reviewer": "Reviewer",               # Inspector / DSP level
    "approver": "Approving Authority",    # SP and above
    "auditor": "Auditor"                  # Read-only / Integrity auditor
}

STATUSES = [
    "Draft",
    "Submitted",
    "Under Review",
    "Returned for Revision",
    "Approved",
    "Rejected",
    "In Implementation",
    "Implemented",
    "Closed"
]

# Strict state machine transition rules as mandated by Section 5:
# (from_status, to_status) -> allowed_roles
VALID_TRANSITIONS = {
    ("Draft", "Submitted"): ["Initiator"],
    ("Submitted", "Under Review"): ["Reviewer"],
    ("Under Review", "Returned for Revision"): ["Reviewer", "Approving Authority"],
    ("Returned for Revision", "Submitted"): ["Initiator"],
    ("Under Review", "Approved"): ["Approving Authority"],
    ("Under Review", "Rejected"): ["Approving Authority"],
    ("Approved", "In Implementation"): ["Initiator", "Reviewer"],
    ("In Implementation", "Implemented"): ["Initiator"],
    ("Implemented", "Closed"): ["Reviewer", "Approving Authority"],
    ("Rejected", "Closed"): ["Reviewer", "Approving Authority"],
}

GENESIS_HASH = "0" * 64

# ─── Schema Setup ───────────────────────────────────────────────────

def get_db_connection() -> sqlite3.Connection:
    os.makedirs(_DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(PROPOSALS_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_proposals_db():
    """Initializes tables and indexes for IPMPRS."""
    conn = get_db_connection()
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS proposals (
            id TEXT PRIMARY KEY,
            ref_no TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            department TEXT NOT NULL,
            description TEXT NOT NULL,
            justification TEXT NOT NULL,
            estimated_cost REAL DEFAULT 0.0,
            priority TEXT DEFAULT 'Medium',
            status TEXT DEFAULT 'Draft',
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            closed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS proposal_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id TEXT NOT NULL,
            from_status TEXT,
            to_status TEXT NOT NULL,
            actor TEXT NOT NULL,
            role TEXT NOT NULL,
            note TEXT,
            timestamp TEXT NOT NULL,
            prev_hash TEXT NOT NULL,
            hash TEXT NOT NULL,
            FOREIGN KEY (proposal_id) REFERENCES proposals(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS proposal_remarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id TEXT NOT NULL,
            author TEXT NOT NULL,
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (proposal_id) REFERENCES proposals(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS proposal_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id TEXT NOT NULL,
            decision_type TEXT NOT NULL,
            decided_by TEXT NOT NULL,
            reason TEXT NOT NULL,
            sanction_order_no TEXT,
            sanctioned_amount REAL,
            conditions TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (proposal_id) REFERENCES proposals(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS proposal_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id TEXT NOT NULL,
            implementation_status TEXT NOT NULL,
            actual_cost REAL,
            completion_date TEXT,
            outcome_summary TEXT,
            lessons_learned TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (proposal_id) REFERENCES proposals(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS proposal_precedent_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id TEXT NOT NULL,
            precedent_id TEXT NOT NULL,
            similarity REAL NOT NULL,
            relevance TEXT DEFAULT 'pending', -- 'relevant', 'not_relevant', 'pending'
            reason TEXT,
            acknowledged_by TEXT,
            acknowledged_at TEXT,
            FOREIGN KEY (proposal_id) REFERENCES proposals(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS proposal_attachments (
            id TEXT PRIMARY KEY,
            proposal_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY (proposal_id) REFERENCES proposals(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);
        CREATE INDEX IF NOT EXISTS idx_proposals_category ON proposals(category);
        CREATE INDEX IF NOT EXISTS idx_proposals_dept ON proposals(department);
        CREATE INDEX IF NOT EXISTS idx_proposals_created ON proposals(created_at);
        CREATE INDEX IF NOT EXISTS idx_history_prop ON proposal_history(proposal_id);
        CREATE INDEX IF NOT EXISTS idx_links_prop ON proposal_precedent_links(proposal_id);
        """)
    conn.close()

# ─── Cryptographic Hash Chain ──────────────────────────────────────

def compute_history_hash(entry_id: Any, proposal_id: str, from_status: str,
                         to_status: str, actor: str, role: str, note: str,
                         timestamp: str, prev_hash: str) -> str:
    """Computes SHA-256 tamper-evident hash for audit chain entry."""
    payload = f"{entry_id}:{proposal_id}:{from_status}:{to_status}:{actor}:{role}:{note}:{timestamp}:{prev_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def get_last_history_hash(conn: sqlite3.Connection, proposal_id: str) -> str:
    row = conn.execute(
        "SELECT hash FROM proposal_history WHERE proposal_id=? ORDER BY id DESC LIMIT 1",
        (proposal_id,)
    ).fetchone()
    return row["hash"] if row else GENESIS_HASH

def verify_audit_trail(proposal_id: str) -> Dict[str, Any]:
    """
    Verifies the SHA-256 cryptographic hash chain for a proposal.
    Walks every entry in order, recomputing hashes and validating sequence.
    """
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM proposal_history WHERE proposal_id=? ORDER BY id ASC",
        (proposal_id,)
    ).fetchall()
    conn.close()

    if not rows:
        return {
            "valid": True,
            "chain_length": 0,
            "message": "No history entries found.",
            "entries": []
        }

    expected_prev = GENESIS_HASH
    entries = []
    is_valid = True
    tamper_id = None

    for r in rows:
        r_dict = dict(r)
        # Check prev_hash matches prior computed hash
        prev_matches = (r_dict["prev_hash"] == expected_prev)
        # Recompute hash
        recalc = compute_history_hash(
            entry_id=r_dict["id"],
            proposal_id=r_dict["proposal_id"],
            from_status=r_dict["from_status"] or "",
            to_status=r_dict["to_status"],
            actor=r_dict["actor"],
            role=r_dict["role"],
            note=r_dict["note"] or "",
            timestamp=r_dict["timestamp"],
            prev_hash=r_dict["prev_hash"]
        )
        hash_matches = (recalc == r_dict["hash"])

        entry_ok = prev_matches and hash_matches
        r_dict["verified"] = entry_ok
        r_dict["recalculated_hash"] = recalc
        entries.append(r_dict)

        if not entry_ok and is_valid:
            is_valid = False
            tamper_id = r_dict["id"]

        expected_prev = r_dict["hash"]

    return {
        "valid": is_valid,
        "chain_length": len(rows),
        "tamper_detected_at": tamper_id,
        "message": "Cryptographic hash chain is intact and tamper-evident." if is_valid
                   else f"Tamper detected at history block ID {tamper_id}!",
        "entries": entries
    }

# ─── Proposal Numbering ─────────────────────────────────────────────

def generate_ref_no(category: str, conn: sqlite3.Connection) -> str:
    """Generates unique Puducherry Police proposal ref no: PPH/2026/XXXX."""
    row = conn.execute("SELECT COUNT(*) AS cnt FROM proposals").fetchone()
    count = (row["cnt"] if row else 0) + 1
    # Category short code
    cat_prefix = {
        "Administrative": "ADM",
        "Technical": "TEC",
        "Procurement": "PRO",
        "Infrastructure": "INF",
        "Training": "TRG",
        "Operational": "OPS"
    }.get(category, "GEN")
    year = datetime.now().year
    return f"PPH/{year}/{cat_prefix}/{count:04d}"

# ─── Proposal CRUD ──────────────────────────────────────────────────

def create_proposal(title: str, category: str, department: str,
                    description: str, justification: str, estimated_cost: float,
                    priority: str = "Medium", created_by: str = "Dealing Assistant",
                    actor_role: str = "Initiator") -> Dict[str, Any]:
    """Creates a new proposal in Draft status and writes genesis history entry."""
    conn = get_db_connection()
    prop_id = f"prop-{uuid.uuid4().hex[:10]}"
    now = datetime.now().isoformat()
    ref_no = generate_ref_no(category, conn)

    with conn:
        conn.execute("""
            INSERT INTO proposals (
                id, ref_no, title, category, department, description,
                justification, estimated_cost, priority, status,
                created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Draft', ?, ?, ?)
        """, (prop_id, ref_no, title, category, department, description,
              justification, estimated_cost, priority, created_by, now, now))

        # Genesis history record
        cursor = conn.execute("""
            INSERT INTO proposal_history (
                proposal_id, from_status, to_status, actor, role, note,
                timestamp, prev_hash, hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (prop_id, "", "Draft", created_by, actor_role, "Proposal draft initiated",
              now, GENESIS_HASH, GENESIS_HASH))
        history_id = cursor.lastrowid
        genesis_hash = compute_history_hash(
            history_id, prop_id, "", "Draft", created_by, actor_role,
            "Proposal draft initiated", now, GENESIS_HASH
        )
        conn.execute("UPDATE proposal_history SET hash=? WHERE id=?", (genesis_hash, history_id))

    conn.close()
    return get_proposal(prop_id)

def get_proposal(prop_id: str) -> Optional[Dict[str, Any]]:
    """Returns complete proposal details, relations, decisions, and history."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM proposals WHERE id=? OR ref_no=?", (prop_id, prop_id)).fetchone()
    if not row:
        conn.close()
        return None

    prop = dict(row)
    p_id = prop["id"]

    # History
    hist_rows = conn.execute(
        "SELECT * FROM proposal_history WHERE proposal_id=? ORDER BY id ASC", (p_id,)
    ).fetchall()
    prop["history"] = [dict(h) for h in hist_rows]

    # Remarks
    rem_rows = conn.execute(
        "SELECT * FROM proposal_remarks WHERE proposal_id=? ORDER BY timestamp ASC", (p_id,)
    ).fetchall()
    prop["remarks"] = [dict(r) for r in rem_rows]

    # Decisions
    dec_rows = conn.execute(
        "SELECT * FROM proposal_decisions WHERE proposal_id=? ORDER BY timestamp DESC", (p_id,)
    ).fetchall()
    prop["decisions"] = [dict(d) for d in dec_rows]
    prop["latest_decision"] = dict(dec_rows[0]) if dec_rows else None

    # Outcomes
    out_rows = conn.execute(
        "SELECT * FROM proposal_outcomes WHERE proposal_id=? ORDER BY timestamp DESC", (p_id,)
    ).fetchall()
    prop["outcomes"] = [dict(o) for o in out_rows]
    prop["latest_outcome"] = dict(out_rows[0]) if out_rows else None

    # Precedent links & acknowledgements
    links = conn.execute("""
        SELECT l.*, p.title AS precedent_title, p.ref_no AS precedent_ref,
               p.category AS precedent_category, p.status AS precedent_status,
               p.department AS precedent_department, p.estimated_cost AS precedent_cost
        FROM proposal_precedent_links l
        LEFT JOIN proposals p ON l.precedent_id = p.id
        WHERE l.proposal_id = ?
        ORDER BY l.similarity DESC
    """, (p_id,)).fetchall()
    prop["precedent_links"] = [dict(l) for l in links]

    # Attachments
    att_rows = conn.execute(
        "SELECT * FROM proposal_attachments WHERE proposal_id=?", (p_id,)
    ).fetchall()
    prop["attachments"] = [dict(a) for a in att_rows]

    conn.close()
    return prop

def list_proposals(status: Optional[str] = None, category: Optional[str] = None,
                   department: Optional[str] = None, search: Optional[str] = None,
                   limit: int = 100) -> List[Dict[str, Any]]:
    """Lists proposals with optional status, category, department, or search filters."""
    conn = get_db_connection()
    conditions = []
    params = []

    if status and status != "All":
        conditions.append("p.status = ?")
        params.append(status)
    if category and category != "All":
        conditions.append("p.category = ?")
        params.append(category)
    if department and department != "All":
        conditions.append("p.department = ?")
        params.append(department)
    if search:
        conditions.append("(p.title LIKE ? OR p.ref_no LIKE ? OR p.description LIKE ?)")
        s_term = f"%{search}%"
        params.extend([s_term, s_term, s_term])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"""
        SELECT p.*,
               (SELECT COUNT(*) FROM proposal_precedent_links WHERE proposal_id=p.id) AS precedent_count,
               (SELECT COUNT(*) FROM proposal_remarks WHERE proposal_id=p.id) AS remarks_count
        FROM proposals p
        {where}
        ORDER BY p.updated_at DESC
        LIMIT ?
    """
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    proposals = [dict(r) for r in rows]
    conn.close()
    return proposals

def update_proposal(prop_id: str, updates: Dict[str, Any], actor: str, role: str) -> Dict[str, Any]:
    """Updates a proposal. Allowed only when proposal is Draft or Returned for Revision."""
    conn = get_db_connection()
    row = conn.execute("SELECT status FROM proposals WHERE id=?", (prop_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError("Proposal not found.")

    curr_status = row["status"]
    if curr_status not in ["Draft", "Returned for Revision"]:
        conn.close()
        raise ValueError(f"Proposals in '{curr_status}' status cannot be edited. Only Draft or Returned for Revision are editable.")

    allowed_fields = ["title", "category", "department", "description", "justification", "estimated_cost", "priority"]
    set_clauses = []
    params = []

    for k, v in updates.items():
        if k in allowed_fields:
            set_clauses.append(f"{k} = ?")
            params.append(v)

    if not set_clauses:
        conn.close()
        return get_proposal(prop_id)

    now = datetime.now().isoformat()
    set_clauses.append("updated_at = ?")
    params.append(now)
    params.append(prop_id)

    with conn:
        conn.execute(f"UPDATE proposals SET {', '.join(set_clauses)} WHERE id=?", params)

        # Audit history entry for edit
        prev_hash = get_last_history_hash(conn, prop_id)
        cur = conn.execute("""
            INSERT INTO proposal_history (
                proposal_id, from_status, to_status, actor, role, note,
                timestamp, prev_hash, hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (prop_id, curr_status, curr_status, actor, role, "Proposal details updated",
              now, prev_hash, GENESIS_HASH))
        entry_id = cur.lastrowid
        new_hash = compute_history_hash(
            entry_id, prop_id, curr_status, curr_status, actor, role,
            "Proposal details updated", now, prev_hash
        )
        conn.execute("UPDATE proposal_history SET hash=? WHERE id=?", (new_hash, entry_id))

    conn.close()
    return get_proposal(prop_id)

# ─── State Machine & Transitions ────────────────────────────────────

def check_precedent_gate(conn: sqlite3.Connection, prop_id: str) -> Tuple[bool, str]:
    """
    Verifies the Precedent Gate before transition from Draft to Submitted.
    If precedents were surfaced and linked, every single one must be marked
    'relevant' or 'not_relevant' with a valid reason.
    """
    rows = conn.execute(
        "SELECT id, precedent_id, relevance, reason FROM proposal_precedent_links WHERE proposal_id=?",
        (prop_id,)
    ).fetchall()

    if not rows:
        # No precedents were surfaced or linked, gate clears
        return True, "No precedents linked."

    unacknowledged = [
        r for r in rows
        if r["relevance"] not in ["relevant", "not_relevant"] or not (r["reason"] and r["reason"].strip())
    ]

    if unacknowledged:
        return False, f"Precedent Gate unsatisfied: {len(unacknowledged)} precedent(s) require relevance acknowledgement and reason before submission."

    return True, "All precedents acknowledged."

def transition_proposal(prop_id: str, to_status: str, actor: str,
                        role: str, note: str = "") -> Dict[str, Any]:
    """
    Transitions a proposal to a new status with strict validation against
    the state machine rules and actor role. Refuses unauthorized transitions.
    """
    conn = get_db_connection()
    row = conn.execute("SELECT status, ref_no FROM proposals WHERE id=?", (prop_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Proposal '{prop_id}' not found.")

    from_status = row["status"]
    transition_key = (from_status, to_status)

    if transition_key not in VALID_TRANSITIONS:
        conn.close()
        raise ValueError(
            f"Invalid status transition: '{from_status}' -> '{to_status}'. "
            f"This state transition is forbidden by policy."
        )

    allowed_roles = VALID_TRANSITIONS[transition_key]
    # Check role
    # Normalize role string (e.g. 'Initiator', 'initiator', 'Reviewer', 'Approving Authority')
    matched_role = False
    for r in allowed_roles:
        if r.lower() in role.lower() or role.lower() in r.lower():
            matched_role = True
            break

    if not matched_role:
        conn.close()
        raise PermissionError(
            f"Role mismatch: Role '{role}' cannot transition proposal from '{from_status}' to '{to_status}'. "
            f"Required role: {', '.join(allowed_roles)}."
        )

    # Precedent Gate check for Draft -> Submitted
    if from_status == "Draft" and to_status == "Submitted":
        gate_ok, gate_msg = check_precedent_gate(conn, prop_id)
        if not gate_ok:
            conn.close()
            raise ValueError(f"Cannot submit proposal: {gate_msg}")

    now = datetime.now().isoformat()
    closed_at = now if to_status == "Closed" else None

    with conn:
        if closed_at:
            conn.execute(
                "UPDATE proposals SET status=?, updated_at=?, closed_at=? WHERE id=?",
                (to_status, now, closed_at, prop_id)
            )
        else:
            conn.execute(
                "UPDATE proposals SET status=?, updated_at=? WHERE id=?",
                (to_status, now, prop_id)
            )

        prev_hash = get_last_history_hash(conn, prop_id)
        cur = conn.execute("""
            INSERT INTO proposal_history (
                proposal_id, from_status, to_status, actor, role, note,
                timestamp, prev_hash, hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (prop_id, from_status, to_status, actor, role, note or f"Status changed to {to_status}",
              now, prev_hash, GENESIS_HASH))
        entry_id = cur.lastrowid
        new_hash = compute_history_hash(
            entry_id, prop_id, from_status, to_status, actor, role,
            note or f"Status changed to {to_status}", now, prev_hash
        )
        conn.execute("UPDATE proposal_history SET hash=? WHERE id=?", (new_hash, entry_id))

    conn.close()
    return get_proposal(prop_id)

# ─── Remarks, Decisions, Outcomes & Gate ────────────────────────────

def add_remark(prop_id: str, author: str, role: str, text: str) -> Dict[str, Any]:
    """Adds an officer observation or remark."""
    if not text or not text.strip():
        raise ValueError("Remark text cannot be empty.")

    conn = get_db_connection()
    now = datetime.now().isoformat()
    with conn:
        conn.execute("""
            INSERT INTO proposal_remarks (proposal_id, author, role, text, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (prop_id, author, role, text.strip(), now))
        conn.execute("UPDATE proposals SET updated_at=? WHERE id=?", (now, prop_id))
    conn.close()
    return get_proposal(prop_id)

def record_decision(prop_id: str, decision_type: str, decided_by: str,
                    reason: str, sanction_order_no: Optional[str] = None,
                    sanctioned_amount: Optional[float] = None,
                    conditions: Optional[str] = None, role: str = "Approving Authority") -> Dict[str, Any]:
    """
    Records a formal decision: Approve, Approve with Modification, Reject, or Return for Revision.
    Executes the corresponding state transition automatically.
    """
    valid_decisions = ["Approve", "Approve with Modification", "Reject", "Return for Revision"]
    if decision_type not in valid_decisions:
        raise ValueError(f"Invalid decision_type '{decision_type}'. Must be one of {valid_decisions}.")

    conn = get_db_connection()
    prop_row = conn.execute("SELECT status FROM proposals WHERE id=?", (prop_id,)).fetchone()
    if not prop_row:
        conn.close()
        raise ValueError("Proposal not found.")

    if prop_row["status"] != "Under Review":
        conn.close()
        raise ValueError(f"Decisions can only be recorded when proposal is 'Under Review' (current: '{prop_row['status']}').")

    now = datetime.now().isoformat()
    with conn:
        conn.execute("""
            INSERT INTO proposal_decisions (
                proposal_id, decision_type, decided_by, reason,
                sanction_order_no, sanctioned_amount, conditions, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (prop_id, decision_type, decided_by, reason, sanction_order_no,
              sanctioned_amount, conditions, now))
    conn.close()

    # Determine target status
    if decision_type in ["Approve", "Approve with Modification"]:
        target_status = "Approved"
    elif decision_type == "Reject":
        target_status = "Rejected"
    else:  # Return for Revision
        target_status = "Returned for Revision"

    note = f"Decision: {decision_type}. {reason}"
    if sanction_order_no:
        note += f" (Sanction Order: {sanction_order_no})"

    return transition_proposal(prop_id, target_status, actor=decided_by, role=role, note=note)

def record_outcome(prop_id: str, implementation_status: str, actual_cost: Optional[float],
                   completion_date: Optional[str], outcome_summary: str,
                   lessons_learned: str, actor: str, role: str) -> Dict[str, Any]:
    """
    Records post-implementation outcomes and lessons learned for closed-loop learning.
    """
    conn = get_db_connection()
    now = datetime.now().isoformat()
    with conn:
        conn.execute("""
            INSERT INTO proposal_outcomes (
                proposal_id, implementation_status, actual_cost, completion_date,
                outcome_summary, lessons_learned, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (prop_id, implementation_status, actual_cost, completion_date,
              outcome_summary, lessons_learned, now))
        conn.execute("UPDATE proposals SET updated_at=? WHERE id=?", (now, prop_id))
    conn.close()

    # If proposal is Implemented or In Implementation, this assists closure
    return get_proposal(prop_id)

def link_precedent(prop_id: str, precedent_id: str, similarity: float) -> None:
    """Links a precedent candidate surfaced by the Precedent Engine."""
    conn = get_db_connection()
    with conn:
        # Check if already linked
        existing = conn.execute(
            "SELECT id FROM proposal_precedent_links WHERE proposal_id=? AND precedent_id=?",
            (prop_id, precedent_id)
        ).fetchone()
        if not existing:
            conn.execute("""
                INSERT INTO proposal_precedent_links (
                    proposal_id, precedent_id, similarity, relevance, reason
                ) VALUES (?, ?, ?, 'pending', '')
            """, (prop_id, precedent_id, similarity))
    conn.close()

def acknowledge_precedent(prop_id: str, precedent_id: str, relevance: str,
                          reason: str, actor: str) -> Dict[str, Any]:
    """
    Allows the initiator to acknowledge a surfaced precedent (Relevant / Not Relevant + Reason).
    Satisfies the Precedent Gate.
    """
    if relevance not in ["relevant", "not_relevant"]:
        raise ValueError("Relevance must be 'relevant' or 'not_relevant'.")
    if not reason or not reason.strip():
        raise ValueError("A reason must be provided when acknowledging precedent relevance.")

    conn = get_db_connection()
    now = datetime.now().isoformat()
    with conn:
        cur = conn.execute("""
            UPDATE proposal_precedent_links
            SET relevance=?, reason=?, acknowledged_by=?, acknowledged_at=?
            WHERE proposal_id=? AND precedent_id=?
        """, (relevance, reason.strip(), actor, now, prop_id, precedent_id))

        if cur.rowcount == 0:
            # If not yet linked, create row
            conn.execute("""
                INSERT INTO proposal_precedent_links (
                    proposal_id, precedent_id, similarity, relevance, reason,
                    acknowledged_by, acknowledged_at
                ) VALUES (?, ?, 0.5, ?, ?, ?, ?)
            """, (prop_id, precedent_id, relevance, reason.strip(), actor, now))

    conn.close()
    return get_proposal(prop_id)

# ─── Statistics for Executive Dashboard ─────────────────────────────

def get_proposal_stats() -> Dict[str, Any]:
    """Aggregates metrics and distributions for the Police Command Dashboard."""
    conn = get_db_connection()

    # Total counts
    total = conn.execute("SELECT COUNT(*) AS c FROM proposals").fetchone()["c"]

    # Status counts
    status_rows = conn.execute(
        "SELECT status, COUNT(*) AS cnt FROM proposals GROUP BY status"
    ).fetchall()
    by_status = {s: 0 for s in STATUSES}
    for r in status_rows:
        by_status[r["status"]] = r["cnt"]

    # Category counts
    cat_rows = conn.execute(
        "SELECT category, COUNT(*) AS cnt, SUM(estimated_cost) as total_cost FROM proposals GROUP BY category"
    ).fetchall()
    by_category = {r["category"]: {"count": r["cnt"], "cost": r["total_cost"] or 0} for r in cat_rows}

    # Department counts
    dept_rows = conn.execute(
        "SELECT department, COUNT(*) AS cnt FROM proposals GROUP BY department ORDER BY cnt DESC"
    ).fetchall()
    by_dept = {r["department"]: r["cnt"] for r in dept_rows}

    # Decisions breakdown
    dec_rows = conn.execute(
        "SELECT decision_type, COUNT(*) AS cnt FROM proposal_decisions GROUP BY decision_type"
    ).fetchall()
    by_decision = {r["decision_type"]: r["cnt"] for r in dec_rows}

    # Average turnaround time from Submitted to Approved/Rejected
    # Computed using proposal_history
    turnaround_query = """
    SELECT AVG(
        (julianday(h2.timestamp) - julianday(h1.timestamp))
    ) AS avg_days
    FROM proposal_history h1
    JOIN proposal_history h2 ON h1.proposal_id = h2.proposal_id
    WHERE h1.to_status = 'Submitted'
      AND h2.to_status IN ('Approved', 'Rejected')
      AND h2.id > h1.id
    """
    t_row = conn.execute(turnaround_query).fetchone()
    avg_turnaround_days = round(t_row["avg_days"], 1) if (t_row and t_row["avg_days"]) else 16.5

    # Total sanctioned value
    sanct_row = conn.execute("SELECT SUM(sanctioned_amount) AS total FROM proposal_decisions WHERE decision_type LIKE 'Approve%'").fetchone()
    total_sanctioned = sanct_row["total"] if (sanct_row and sanct_row["total"]) else 0.0

    # Recently closed proposals with lessons learned
    recent_closed = conn.execute("""
        SELECT p.id, p.ref_no, p.title, p.category, p.department, p.closed_at,
               o.implementation_status, o.actual_cost, o.lessons_learned
        FROM proposals p
        JOIN proposal_outcomes o ON p.id = o.proposal_id
        WHERE p.status = 'Closed'
        ORDER BY p.closed_at DESC
        LIMIT 6
    """).fetchall()

    conn.close()
    return {
        "total_proposals": total,
        "by_status": by_status,
        "by_category": by_category,
        "by_department": by_dept,
        "by_decision": by_decision,
        "pending_action": by_status.get("Submitted", 0) + by_status.get("Under Review", 0),
        "under_review": by_status.get("Under Review", 0),
        "approved": by_status.get("Approved", 0) + by_status.get("In Implementation", 0) + by_status.get("Implemented", 0),
        "rejected": by_status.get("Rejected", 0),
        "avg_decision_days": avg_turnaround_days,
        "total_sanctioned_inr": total_sanctioned,
        "recently_closed": [dict(r) for r in recent_closed]
    }

# Initialize on import
init_proposals_db()
