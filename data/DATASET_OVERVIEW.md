# Intelligent IT Ticket Analysis and Resolution Assistant - Synthetic Datasets

This dataset package is crafted specifically for the **HCLTech | Future Ready AI Engineer Hackathon: Intelligent IT Ticket Analysis and Resolution Assistant**.

It provides realistic enterprise ITSM synthetic datasets formatted in both **JSON** and **CSV** designed to satisfy all Functional Requirements (**FR-01 through FR-08**) and Evaluation Dimensions.

---

## 📁 File Manifest

| File | Format | Record Count | Description |
|---|---|---|---|
| [`taxonomy.json`](file:///C:/Users/schan/.gemini/antigravity/scratch/it-ticket-assistant/data/taxonomy.json) | JSON | 7 Categories | Standard enterprise ITSM taxonomy (Categories, Subcategories, Priorities, Assignment Groups, Environments) |
| [`kb_articles.json`](file:///C:/Users/schan/.gemini/antigravity/scratch/it-ticket-assistant/data/kb_articles.json) / [`.csv`](file:///C:/Users/schan/.gemini/antigravity/scratch/it-ticket-assistant/data/kb_articles.csv) | JSON & CSV | 15 Articles | Standard Approved Knowledge Base (Runbooks, symptoms, root causes, step-by-step resolution, and verbatim excerpts) |
| [`historical_tickets.json`](file:///C:/Users/schan/.gemini/antigravity/scratch/it-ticket-assistant/data/historical_tickets.json) / [`.csv`](file:///C:/Users/schan/.gemini/antigravity/scratch/it-ticket-assistant/data/historical_tickets.csv) | JSON & CSV | 30 Resolved Cases | Historical resolved incidents used for similarity matching, duplicate clustering, and resolution mining |
| [`incoming_test_tickets.json`](file:///C:/Users/schan/.gemini/antigravity/scratch/it-ticket-assistant/data/incoming_test_tickets.json) / [`.csv`](file:///C:/Users/schan/.gemini/antigravity/scratch/it-ticket-assistant/data/incoming_test_tickets.csv) | JSON & CSV | 20 Test Tickets | Test & evaluation dataset with ground truth labels (`is_duplicate`, `expected_category`, `expected_priority`, `expected_kb_id`, `should_fallback`) |
| [`generate_data.py`](file:///C:/Users/schan/.gemini/antigravity/scratch/it-ticket-assistant/data/generate_data.py) | Python | - | Python generator script to reproduce or expand the dataset |

---

## 🏷️ Standard ITSM Taxonomy

### Categories & Subcategories
1. **Identity & Access Management**
   - `MFA / 2FA`
   - `Active Directory`
   - `Application Access Request`
   - `Single Sign-On / SAML`
2. **Network & Connectivity**
   - `VPN`
   - `Wi-Fi & LAN`
   - `DNS / Routing`
   - `Firewall & Security Gateway`
3. **Enterprise Applications**
   - `SAP ERP`
   - `Salesforce CRM`
   - `Workday HRIS`
   - `Oracle EBS`
4. **Cloud & Infrastructure**
   - `AWS IAM / S3`
   - `Kubernetes / Containers`
   - `Azure Virtual Machines`
   - `Database & Storage`
5. **Collaboration & Email**
   - `Microsoft 365 / Outlook`
   - `Microsoft Teams`
   - `Slack & Zoom`
6. **Hardware & Workplace Support**
   - `Peripherals & Docks`
   - `Laptop Hardware Damage`
   - `OS / Blue Screen BSOD`
   - `Printing Services`
7. **Developer Tools & DevOps**
   - `GitLab / CI/CD`
   - `GitHub & Version Control`
   - `Docker & Container Runtime`
   - `Artifactory & Package Repo`

### Priority Tiers
- **P1 - Critical**: Outage affecting business-critical production processes or multiple users.
- **P2 - High**: Significant operational impact with no direct workaround.
- **P3 - Medium**: Standard operational degradation with known workaround.
- **P4 - Low**: Minor inquiry, cosmetic defect, or standard access provisioning.

---

## 🎯 Mapping to Hackathon Requirements

| Hackathon Requirement | Dataset Coverage |
|---|---|
| **FR-01: Ticket Classification** | Multi-class ground truth labels (`expected_category`, `expected_subcategory`, `expected_priority`, `expected_intent`) across 20 test tickets. |
| **FR-02: Duplicate Detection** | Duplicate clusters (e.g. Okta push `INC-1001` & `INC-1011` vs `TC-3001`; GlobalProtect `INC-1002`, `INC-1012` vs `TC-3002` & `TC-3020`). Distinguishes semantic similarity from superficial keyword overlap. |
| **FR-03 & FR-04: Resolution & Traceability** | Every historical ticket and KB article contains `root_cause`, `resolution_steps`, `linked_kb_id`, and exact verbatim `relevant_excerpt` for evidence citation. |
| **FR-05: Confidence & Fallback** | Dedicated edge cases: Vague ticket (`TC-3016`), Hardware physical damage (`TC-3017`), and Novel protocol error with no historical match (`TC-3018`) with `should_fallback: true`. |
| **FR-06: Analyst Feedback** | Historical records contain `resolution_useful_votes` for reinforcement / ranking. |
| **FR-07: Search & Filtering** | Structured metadata fields: `affected_service`, `environment` (`Production`, `Corporate`, `Staging`), `assignment_group`, and timestamps. |
| **FR-08: Audit Output** | Clean IDs and verifiable links (`ticket_id`, `kb_id`, `duplicate_of_ticket_id`) facilitating audit trace generation. |

---

## 🔍 Worked Evidence-Backed Examples

### Example 1: High Confidence Duplicate with KB Reference (VPN Failure)
- **Input Ticket (`TC-3002`)**:
  - *Title*: "GlobalProtect VPN stuck on 'Connecting' - Could not connect to gateway"
  - *Description*: "Cannot connect to company network from home today. The Palo Alto GlobalProtect client says 'Could not connect to gateway'. I am on home Wi-Fi and internet is working fine."
  - *Service*: `GlobalProtect` | *Environment*: `Production`
- **Assistant Predicted Classification**:
  - *Category*: `Network & Connectivity` | *Subcategory*: `VPN` | *Priority*: `P2 - High`
  - *Confidence Score*: `0.96`
- **Retrieved Similar Cases**:
  1. `INC-1002` (Similarity: 0.94) - "GlobalProtect VPN connection failed: Could not connect to gateway"
  2. `INC-1012` (Similarity: 0.88) - "Palo Alto GlobalProtect handshake error after Windows 11 feature update"
- **Recommended Resolution**:
  - Flush DNS cache (`ipconfig /flushdns`), delete the `%LOCALAPPDATA%\Palo Alto Networks\GlobalProtect\PanGPS` cache directory, and restart the `PanGPS` service.
- **Traceability & Evidence**:
  - *Source*: [`KB-2002`](file:///C:/Users/schan/.gemini/antigravity/scratch/it-ticket-assistant/data/kb_articles.json) & [`INC-1002`](file:///C:/Users/schan/.gemini/antigravity/scratch/it-ticket-assistant/data/historical_tickets.json)
  - *Excerpt*: "Flush DNS and restart PanGPS service, then delete the PanGPS cache folder under %LOCALAPPDATA% before reconnecting."
  - *Reasoning*: The symptoms match a known PanGPS DNS cache desynchronization resolved 18 times historically.

---

### Example 2: Critical Infrastructure Issue (Kubernetes Pod OOMKilled)
- **Input Ticket (`TC-3007`)**:
  - *Title*: "Auth pod crash looping with Exit Code 137 OOMKilled in prod"
  - *Description*: "The authentication microservice pod in k8s prod cluster keeps dying and restarting with CrashLoopBackOff. 'kubectl describe pod' indicates Reason: OOMKilled, Exit Code: 137."
  - *Service*: `EKS / GKE Clusters` | *Environment*: `Production`
- **Assistant Predicted Classification**:
  - *Category*: `Cloud & Infrastructure` | *Subcategory*: `Kubernetes / Containers` | *Priority*: `P1 - Critical`
  - *Confidence Score*: `0.98`
- **Retrieved Similar Cases**:
  1. `INC-1007` (Similarity: 0.95) - "Payment gateway service pod restarting with OOMKilled in production namespace"
  2. `INC-1020` (Similarity: 0.89) - "Production search microservice pod hitting memory limits and crashing"
- **Recommended Resolution**:
  - Increase the pod memory limit by 50-100% in Helm values (e.g. from 1Gi to 2Gi) and set JVM `-XX:MaxRAMPercentage=75.0` to avoid native memory exhaustion.
- **Traceability & Evidence**:
  - *Source*: [`KB-2007`](file:///C:/Users/schan/.gemini/antigravity/scratch/it-ticket-assistant/data/kb_articles.json) & [`INC-1007`](file:///C:/Users/schan/.gemini/antigravity/scratch/it-ticket-assistant/data/historical_tickets.json)
  - *Excerpt*: "Confirm Exit Code 137 via kubectl describe pod and increase container memory limit in Helm values or tune JVM MaxRAMPercentage."

---

### Example 3: Ambiguous / Low-Confidence Fallback (FR-05)
- **Input Ticket (`TC-3016`)**:
  - *Title*: "System not working properly please fix ASAP"
  - *Description*: "The application crashed with an error on screen. It was blue and had text. Can someone take a look? Urgent."
  - *Service*: `Unknown` | *Environment*: `Unknown`
- **Assistant Analysis & Fallback Behavior**:
  - *Predicted Category*: `Hardware & Workplace Support` (Tentative)
  - *Confidence Score*: `0.32` (Below confidence threshold of `0.65`)
  - *Fallback Triggered*: **YES** (`should_fallback = True`)
- **System Action**:
  - Flag ticket as **Low Confidence / Ambiguous**.
  - **Refrain** from recommending ungrounded technical runbooks.
  - Generate clarifying prompt for the user: *"Please provide: (1) The specific application or workstation name, (2) The exact error code or text displayed, and (3) A screenshot of the blue screen if possible."*
  - Route ticket to `Triage-Queue` for human analyst review.
