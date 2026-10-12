"""Hybrid FTS5 and Ollama-embedding index for decided proposals."""

import os
import re
import sqlite3
from datetime import datetime

import numpy as np
import ollama
import workflow


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DEFAULT_DB_PATH = os.path.join(DATA_DIR, "precedents.db")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
EXCLUDED_STATUSES = {"draft", "withdrawn"}
FILTER_COLUMNS = {"department": "department", "category": "category", "outcome": "outcome"}


def reciprocal_rank_fusion(keyword_ids, vector_ids, k=60):
    scores = {}
    for ranked_ids in (keyword_ids, vector_ids):
        for rank, proposal_id in enumerate(ranked_ids, start=1):
            scores[proposal_id] = scores.get(proposal_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


class PrecedentIndex:
    def __init__(self, db_path=DEFAULT_DB_PATH, embedding_fn=None):
        self.db_path = db_path
        self.embed_model = os.environ.get("EMBED_MODEL", EMBED_MODEL)
        self.embedding_fn = embedding_fn or self._create_embedding
        self._initialize()

    def _connect(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        connection = self._connect()
        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS precedents (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    justification TEXT NOT NULL,
                    searchable_text TEXT NOT NULL,
                    decision_remark TEXT NOT NULL,
                    department TEXT,
                    category TEXT,
                    status TEXT,
                    outcome TEXT,
                    outcome_detail TEXT,
                    cost REAL,
                    decided_by TEXT,
                    decided_at TEXT,
                    revision INTEGER NOT NULL DEFAULT 0,
                    embedding BLOB,
                    updated_at TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS precedent_fts
                USING fts5(proposal_id UNINDEXED, searchable_text)
            """)
        connection.close()

    def _create_embedding(self, text):
        response = ollama.embeddings(model=self.embed_model, prompt=text[:1000])
        values = response.get("embedding") if isinstance(response, dict) else getattr(response, "embedding", None)
        if values is None:
            raise ValueError("Ollama returned no embedding vector.")
        vector = np.asarray(values, dtype=np.float32)
        norm = float(np.linalg.norm(vector))
        if vector.ndim != 1 or not vector.size or not np.isfinite(norm) or norm == 0:
            raise ValueError("Ollama returned an invalid embedding vector.")
        return vector / norm

    @staticmethod
    def _latest(proposal, plural_key, singular_key):
        value = proposal.get(singular_key)
        if value:
            return value
        values = proposal.get(plural_key) or []
        return values[0] if values else {}

    def upsert(self, proposal):
        proposal_id = str(proposal.get("id", ""))
        if not proposal_id:
            raise ValueError("Proposal ID is required for indexing.")

        connection = self._connect()
        status = str(proposal.get("status", ""))
        if status.strip().lower() in EXCLUDED_STATUSES:
            with connection:
                connection.execute("DELETE FROM precedent_fts WHERE proposal_id=?", (proposal_id,))
                connection.execute("DELETE FROM precedents WHERE id=?", (proposal_id,))
            connection.close()
            return False

        decision = self._latest(proposal, "decisions", "latest_decision")
        outcome = self._latest(proposal, "outcomes", "latest_outcome")
        history = proposal.get("history") or []
        title = str(proposal.get("title", ""))
        description = str(proposal.get("description", ""))
        justification = str(proposal.get("justification", ""))
        remarks = proposal.get("remarks") or []
        latest_remark = remarks[-1] if remarks else {}
        decision_remark = str(decision.get("reason") or latest_remark.get("text") or "")
        searchable_text = "\n".join((title, description, justification, decision_remark))
        embedding = None
        try:
            vector = self.embedding_fn(searchable_text[:1000])
            if vector is not None:
                normalized = np.asarray(vector, dtype=np.float32)
                norm = float(np.linalg.norm(normalized))
                if normalized.ndim == 1 and normalized.size and np.isfinite(norm) and norm:
                    embedding = (normalized / norm).astype(np.float32).tobytes()
        except Exception as exc:
            print(f"[PrecedentIndex] Embedding unavailable for {proposal_id}: {exc}")

        metadata = (
            proposal_id,
            title,
            description,
            justification,
            searchable_text,
            decision_remark,
            proposal.get("department"),
            proposal.get("category"),
            status,
            decision.get("decision_type") or outcome.get("implementation_status") or status,
            outcome.get("outcome_summary") or outcome.get("lessons_learned") or "",
            proposal.get("estimated_cost"),
            decision.get("decided_by") or latest_remark.get("author"),
            decision.get("timestamp") or latest_remark.get("timestamp"),
            len(history),
            embedding,
            datetime.utcnow().isoformat(),
        )
        with connection:
            connection.execute("""
                INSERT OR REPLACE INTO precedents (
                    id, title, description, justification, searchable_text,
                    decision_remark, department, category, status, outcome,
                    outcome_detail, cost, decided_by, decided_at, revision,
                    embedding, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, metadata)
            connection.execute("DELETE FROM precedent_fts WHERE proposal_id=?", (proposal_id,))
            connection.execute(
                "INSERT INTO precedent_fts(proposal_id, searchable_text) VALUES (?, ?)",
                (proposal_id, searchable_text),
            )
        connection.close()
        return True

    def reindex_all(self):
        import proposals

        summaries = proposals.list_proposals(limit=10000)
        indexed = 0
        for summary in summaries:
            proposal = proposals.get_proposal(summary["id"])
            if proposal and self.upsert(proposal):
                indexed += 1
        return indexed

    @staticmethod
    def _fts_query(query):
        terms = list(dict.fromkeys(re.findall(r"[\w]+", query, flags=re.UNICODE)))
        return " OR ".join('"' + term.replace('"', '""') + '"' for term in terms[:32]), terms

    def search(self, query, filters=None, k=5, exclude_id=None):
        fts_query, query_terms = self._fts_query(str(query or ""))
        if not fts_query:
            return []
        filters = filters or {}
        clauses = []
        parameters = []
        for name, column in FILTER_COLUMNS.items():
            value = filters.get(name)
            if value:
                clauses.append(f"LOWER(p.{column}) = LOWER(?)")
                parameters.append(str(value))
        if exclude_id:
            clauses.append("p.id <> ?")
            parameters.append(str(exclude_id))
        filter_sql = " AND " + " AND ".join(clauses) if clauses else ""

        connection = self._connect()
        keyword_rows = connection.execute(f"""
            SELECT p.id, bm25(precedent_fts) AS rank
            FROM precedent_fts
            JOIN precedents p ON p.id=precedent_fts.proposal_id
            WHERE precedent_fts MATCH ?{filter_sql}
            ORDER BY rank ASC
        """, [fts_query, *parameters]).fetchall()
        eligible = connection.execute(f"""
            SELECT p.* FROM precedents p WHERE 1=1{filter_sql}
        """, parameters).fetchall()

        keyword_ids = [row["id"] for row in keyword_rows]
        vector_ids = []
        query_vector = None
        try:
            query_vector = self.embedding_fn(str(query)[:1000])
            if query_vector is not None:
                query_vector = np.asarray(query_vector, dtype=np.float32)
                query_norm = float(np.linalg.norm(query_vector))
                if query_vector.ndim != 1 or not query_vector.size or not np.isfinite(query_norm) or not query_norm:
                    query_vector = None
                else:
                    query_vector = query_vector / query_norm
        except Exception as exc:
            print(f"[PrecedentIndex] Query embedding unavailable: {exc}")

        similarities = {}
        if query_vector is not None:
            for row in eligible:
                blob = row["embedding"]
                if not blob:
                    continue
                vector = np.frombuffer(blob, dtype=np.float32)
                if vector.shape == query_vector.shape:
                    similarities[row["id"]] = float(np.dot(query_vector, vector))
            vector_ids = [proposal_id for proposal_id, _ in sorted(similarities.items(), key=lambda item: (-item[1], item[0]))]

        fused = reciprocal_rank_fusion(keyword_ids, vector_ids)
        by_id = {row["id"]: dict(row) for row in eligible}
        max_score = 2.0 / 61.0
        output = []
        for proposal_id, raw_score in fused[:max(1, int(k))]:
            row = by_id.get(proposal_id)
            if not row:
                continue
            searchable_words = set(re.findall(r"[\w]+", row["searchable_text"].lower(), flags=re.UNICODE))
            matched_terms = [term for term in query_terms if term.lower() in searchable_words]
            keyword_only = not vector_ids
            metadata = {
                "department": row["department"],
                "category": row["category"],
                "status": row["status"],
                "outcome": row["outcome"],
                "outcome_detail": row["outcome_detail"],
                "cost": row["cost"],
                "decided_by": row["decided_by"],
                "decided_at": row["decided_at"],
                "revision": row["revision"],
                "decision_remark": row["decision_remark"],
            }
            output.append({
                "id": proposal_id,
                "title": row["title"],
                "comparison_text": row["searchable_text"],
                "metadata": metadata,
                "score": min(1.0, raw_score / max_score),
                "matched_terms": matched_terms,
                "keyword_only": keyword_only,
                "embedding_used": bool(vector_ids),
            })
        connection.close()
        return output


precedent_index = PrecedentIndex()


def _reindex_workflow_event(event, proposal):
    if event in {"submit", "approve", "reject"}:
        precedent_index.upsert(proposal)


workflow.register_listener(_reindex_workflow_event)