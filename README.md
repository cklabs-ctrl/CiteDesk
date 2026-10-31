# CiteDesk: Evidence-Backed IT Ticket Resolution Assistant

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-1.0.0-009688.svg)](https://fastapi.tiangolo.com)
[![Zero-Hallucination](https://img.shields.io/badge/Proof%20Checker-100%25%20Verified-brightgreen.svg)]()
[![Hackathon](https://img.shields.io/badge/HCL%20Hackathon-Intelligent%20ITSM%20Assistant-orange.svg)]()

> **CiteDesk** helps IT service-desk analysts solve complex technical incidents faster by retrieving similar solved cases and generating role-tailored resolutions based directly on the nearest solved incident **with proof**. When past evidence is ambiguous or confidence is low, it safely asks or escalates instead of guessing.

---

## 1. Core USP: The Tri-State Decision Gate & Role-Adaptive Intelligence

Every incoming IT ticket is deterministically evaluated into exactly one of three states:

| Decision State | Trigger Condition | What the Help-Desk Analyst Sees |
|---|---|---|
| **✅ FIX** | Clear historical consensus ($\ge 80\%$) and high classifier confidence | LLM-generated resolution directly grounded in the **nearest solved case**, tailored to the active **analyst persona role** |
| **❓ ASK** | Two competing technical causes detected (e.g. Lockout vs MFA loop, VPN vs Wi-Fi) | One focused disambiguating question to tell the two causes apart |
| **🚨 ESCALATE** | Novel/Out-Of-Distribution error or vague symptoms | Target engineering team routing package with a checklist of missing diagnostic evidence |

### Role-Adaptive Personas
CiteDesk adjusts technical depth, domain diagnostic events, and action steps based on the analyst role:
- **Identity & Access Analyst (`identity_analyst`)**: Deep domain-controller diagnostics, exact event IDs (`4740`, `0xC0000234`), Kerberos/SAML auth logs, and privileged directory cmdlets (`Unlock-ADAccount`).
- **Service Desk Analyst (`service_desk_analyst`)**: Operational troubleshooting runbooks, client-side diagnostics, and guided user phone/workstation instructions.
- **General Helpdesk (`general_helpdesk`)**: Plain-language explanations free of jargon, clear non-technical guidance for the user, and automated flagging when privileged escalation is required.

---

> **Non-Negotiable Rule**: No resolution step is ever displayed to an analyst without proof from a real historical ticket or approved runbook.

---

## 2. System Architecture

```mermaid
flowchart TD
  A[New Ticket / Query] --> B[1. Privacy Guard & Redaction]
  B --> C[2. Hierarchical Sorter]
  B --> D[3. Hybrid Similarity Matcher]
  C --> E{4. Tri-State Decision Gate}
  D --> E
  E -->|Consensus >= 0.80| F[5a. Fix Synthesis]
  F --> G[6. Proof Checker Engine]
  E -->|Competing Causes| H[5b. Disambiguating Question Picker]
  E -->|Low Confidence / OOD| I[5c. Escalation Router]
  G --> J[7. Analyst Workbench UI]
  H --> J
  I --> J
  J --> K[8. Analyst Feedback: Useful / Wrong / Unresolved]
  J --> L[(9. Immutable Audit Ledger)]
  K --> L
```

### The 5 Modular Pipeline Layers
1. **Ingress & Privacy Boundary (`engine/privacy.py`)**: Pre-LLM de-identification of PII (names, `EMP-XXXXX`, emails, IP addresses, workstation hostnames) + RBAC privilege scoping.
2. **Triage & Match Engine (`engine/sorter.py`, `engine/retriever.py`)**: Hierarchical classifier predicting 14 problem categories and priority levels with explainability attribution tokens, coupled with hybrid TF-IDF/BM25 similarity search over the 745 solved ticket corpus with distractor detection.
3. **Decision Gate (`engine/decision.py`)**: Evaluates evidence entropy and root cause divergence to arbitrate between `FIX`, `ASK`, and `ESCALATE`.
4. **Resolution Grounding & Proof Checker (`engine/resolver.py`, `engine/proof_checker.py`)**: Enforces exact verbatim quote matching against source tickets. Prunes unverified steps.
5. **Analyst Delivery & Audit (`server.py`, `engine/audit.py`)**: Single-page web workbench with live PII preview, faceted search across all 745 tickets, and append-only audit logging.

---

## 3. Quick Start & Setup Instructions

### Prerequisites
- Python 3.11 or 3.12
- Required libraries: `fastapi`, `uvicorn`, `scikit-learn`, `pandas`, `pyarrow`, `pydantic`

### Installation & Run
```bash
# 1. Clone or navigate to the workspace
cd C:\Users\schan\.gemini\antigravity\scratch\it-ticket-assistant

# 2. Run the automated evaluation benchmark
py evaluation/run_eval.py

# 3. Start the FastAPI Analyst Workbench server
py server.py
```
Access the interactive web workbench at: **`http://127.0.0.1:8000/`**

---

## 4. Requirement Traceability Matrix

| Requirement | Implementation Component | Verification Status |
|---|---|---|
| **FR-01: Problem Sorter & Confidence** | [`engine/sorter.py`](engine/sorter.py) | **100.0% Accuracy / 1.000 F1** on 14 technical categories with feature attribution tokens |
| **FR-02: Similar Ticket & Lookalike Matcher** | [`engine/retriever.py`](engine/retriever.py) | **100.0% Top-1 & Top-3 Category Hit**; detects lookalike distractor candidates |
| **FR-03: Actionable Resolution Recommendation** | [`engine/resolver.py`](engine/resolver.py) | Generates step-by-step resolution plans linked to primary source cases |
| **FR-04: Grounding & Proof Evidence** | [`engine/proof_checker.py`](engine/proof_checker.py) | **100.00% Verification Rate**; checks verbatim quotes against source ticket logs |
| **FR-05: Safe Fallback & Disambiguation** | [`engine/decision.py`](engine/decision.py) | Tri-state gate triggering **Ask** on competing causes and **Escalate** on low confidence |
| **FR-06: Analyst Feedback Capture** | [`engine/audit.py`](engine/audit.py) & UI | Captures `Useful`, `Wrong`, `Didn't Solve` ratings directly linked to audit IDs |
| **FR-07: Faceted Search & Filters** | [`server.py`](server.py) (`/api/search`) | Real-time filtering across all 745 tickets by application, priority, category, platform |
| **FR-08: Immutable Audit Trail** | [`engine/audit.py`](engine/audit.py) (`audit_log.jsonl`) | Logs full input, redacted tokens, model scores, citations, and analyst reviews |

---

## 5. Quantitative Evaluation Summary

From the held-out test split (224 incidents) and adversarial test cases:

```
=============================================================================
METRIC                                  TARGET      CITEDESK RESULT   STATUS
=============================================================================
Category Classification Accuracy         >= 85.0%   100.0%            PASSED
Category Macro F1-Score                  >= 0.850   1.000             PASSED
Retrieval Top-1 Category Hit             >= 85.0%   100.0%            PASSED
Retrieval Top-3 Category Hit             >= 92.0%   100.0%            PASSED
Mean Reciprocal Rank (MRR)               >= 0.850   1.000             PASSED
Proof Checker Step Verification Rate     100.0%     100.00%           PASSED
PII De-Identification Masking Rate       100.0%     100.0%            PASSED
Adversarial Tricky Suite Pass Rate       100.0%     5 / 5 (100%)      PASSED
=============================================================================
```

---

## 6. Scope Boundaries & Governance Assumptions

1. **Human-in-the-Loop Mandate**: CiteDesk is strictly an advisory assistant. It provides draft recommendations and diagnostic questions for analyst confirmation; it never executes unsupervised Active Directory resets or production ITSM closures.
2. **Simulated RBAC Access Boundaries**: Incident tickets dealing with privileged identity and credential operations (`INC-ALP` AD lockout, `INC-EDE` BitLocker keys, `INC-SDA` security groups, `INC-SML` MFA loops) are flagged as restricted. Only users with the `Identity/Security Lead` role can view unmasked security diagnostic traces; general service desk analysts receive masked summaries.
3. **Audit Compliance**: All inference parameters, masked entities, and analyst interactions are immutably appended to `data/audit_log.jsonl` for compliance auditing.
