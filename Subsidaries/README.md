# IPMPRS — Intelligent Proposal Management and Precedent Retrieval System
### Puducherry Police Hackathon 2026 · Problem Statement 01

> **An intelligent, end-to-end proposal management system that guides police proposals from draft creation to post-closure learning, with a precedent-first workflow and cryptographic audit trails.**

---

## 1. Executive Summary & Problem Solved

A police department handles an unrelenting influx of administrative, technical, procurement, infrastructure, training, and operational proposals. Traditionally, proposals and sanction orders remain dispersed across physical files, disconnected Word documents, and individual officers' memory.

This causes five major administrative failures:
1. **Repeated Work:** Proposals rejected years earlier are repeatedly drafted because nobody remembers the reason for rejection.
2. **Inconsistent Decisions:** Similar proposals receive disparate outcomes because approving authorities lack immediate sight of past precedents.
3. **Sluggish Decisions:** Reviewers spend weeks manually scouring files and telephoning colleagues before making a recommendation.
4. **Lost Lessons:** Post-sanction realities (vendor delays, cabling corrosion, cost overruns) never reach the next officer drafting a similar scheme.
5. **Weak Traceability:** Lack of tamper-evident accountability regarding who observed what and when.

**IPMPRS solves this with a Precedent-First Workflow** where historical intelligence is embedded directly into the drafting and decision loop.

---

## 2. Key Architecture & Differentiators

| Innovation | Implementation |
|---|---|
| **Live Precedent Panel** | Debounced real-time retrieval surfaces top 3–5 matching past proposals with outcome badges (`Approved`, `Rejected`, `Modified`, `Implemented`, `Closed`) as the officer types the title and description. |
| **Explainable Similarity & Duplicate Warnings** | Quantified match percentage, matched keywords, and a 1-line institutional explanation citing the past decision or outcome. Triggers an automatic high-visibility warning banner when similarity exceeds **85%**. |
| **Mandatory Precedent Gate** | A proposal **cannot be submitted** until the initiator marks each surfaced precedent as *Relevant* or *Not Relevant* with a mandatory reason. Turns search into an enforceable administrative process. |
| **Precedent Pulse** | Instant quantitative summary line computed over matched proposals via plain SQL (e.g. *5 similar proposals identified: 2 approved, 2 rejected (budget limits), 1 modified. Average time to decision: 18 days*). |
| **Decision Brief (PDF)** | Generates a clean, official one/two-page PDF appraisal for the Approving Authority (SP/SSP/DGP) using ReportLab with proposal particulars, Precedent Pulse, top precedents, officer remarks, and endorsement blocks. |
| **Closed-Loop Outcome & Lessons Learned** | When a proposal closes, actual costs and operational lessons learned (e.g. marine salt air corrosion, GPS retrofit delays) are indexed so future proposals automatically inherit those lessons. |
| **Tamper-Evident SHA-256 Audit Trail** | Every lifecycle transition is cryptographically chained to the previous block hash (`prev_hash` + `hash`). An interactive **Verify Trail** feature mathematically re-verifies the entire chain of custody on demand. |

---

## 3. Strict State Machine & Role Enforcements

```
Draft  ──(Initiator: Precedent Gate)──>  Submitted  ──(Reviewer)──>  Under Review
                                                                     │       │
                                             (Return for Revision) ┌─┘       └─┐ (Approver: Decision)
                                                                   ▼           ▼
                                                       Returned for Revision   Approved / Rejected
                                                                   │           │
                                                       (Resubmit) ─┘           └─> In Implementation
                                                                                   │ (Initiator)
                                                                                   ▼
                                                                               Implemented
                                                                                   │ (Reviewer / Approver)
                                                                                   ▼
                                                                                 Closed
```

### Role Matrix
- **Initiator (Dealing Assistant / Clerk):** Drafts proposals, reviews Precedent Gate, resubmits revised drafts, marks works implemented.
- **Reviewer (Inspector / DSP level):** Scrutinizes submitted proposals, adds official observations, returns for revision, moves approved works to implementation, records closures.
- **Approving Authority (SP / SSP / DGP):** Reviews Decision Brief, accords formal financial sanctions (`Approve`, `Approve with Modification`, `Reject`, `Return for Revision`).
- **Auditor (Internal Audit):** Read-only supervisory access with one-click cryptographic hash chain verification.

---

## 4. Technology Stack

- **Backend:** Python 3.11, Flask, SQLite (`data/proposals.db`), FAISS, ReportLab (PDF generator).
- **Search & Precedents:** Hybrid lexical (BM25 token hit) + vector similarity (FAISS with Ollama `nomic-embed-text`), with full graceful fallback to BM25 when offline.
- **Frontend:** Vanilla HTML5, CSS3 Luxury Minimalist Glassmorphism (`cmpdi.css`), JavaScript ES6+ (`cmpdi.js`), Chart.js.
- **On-Premise / Sovereign:** Runs 100% locally with zero external cloud dependencies.

---

## 5. Quick Start Instructions

### Prerequisites
- Python 3.10+
- (Optional) [Ollama](https://ollama.com) running locally with `llama3.2`, `llama3.2-vision:11b`, and `nomic-embed-text`. Image OCR uses Llama 3.2 Vision; scanned-PDF OCR still requires Tesseract and Poppler.

### Setup & Run
```bash
# 1. Install dependencies
pip install -r requirements.txt

# Pull the Llama 3.2 vision model used for image OCR
ollama pull llama3.2-vision:11b

# 2. Start the IPMPRS Server
python server.py
# (Or run start.bat on Windows)
```

Set `ARIA_VISION_MODEL` to use a different Ollama vision model tag. The separate `llama3.2:latest` text model cannot accept images; use `llama3.2-vision:11b` for image OCR. Llama 3.2 Vision is 11B parameters; a 4B Llama 3.2 vision model is not available. Image OCR does not require Tesseract.

### Accessing the Platform
Open `http://localhost:5000` or `index.html` directly in your browser.

---

## 6. Verification & Demo Flow for Judges

1. **Role Switcher (Header):** Switch between `Initiator`, `Reviewer`, `Approving Authority`, and `Auditor` to observe permission enforcement.
2. **Dashboard:** View live metrics across 50+ pre-seeded proposals, Category/Status charts, and the Closed-Loop Lessons Learned feed.
3. **Live Precedent Panel:** Click **+ New Proposal** and type:
   - Subject: `Procurement of 140 High-Definition IP CCTV Cameras for Town Stations`
   - Notice the instant live match (>90%), the duplicate alert, the "why it matched" explanation, and the Precedent Gate checklist.
4. **Precedent Gate:** Mark precedents as *Relevant* with a reason to unlock the *Submit Proposal* button.
5. **Decision Brief:** In Proposal Detail view, click **Decision Brief (PDF)** to download the generated executive brief.
6. **Audit Trail Verification:** Click the **Cryptographic Audit Trail** tab and click **Re-verify Hash Chain** to confirm mathematical integrity.
