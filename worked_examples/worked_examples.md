# CiteDesk: Evidence-Backed Worked Examples

This document demonstrates three full end-to-end worked examples representing the three triage states of the CiteDesk engine:
1. **Case 1: ✅ FIX** (High consensus, step-by-step resolution backed by citations)
2. **Case 2: ❓ ASK** (Ambiguous symptoms, disambiguating diagnostic question)
3. **Case 3: 🚨 ESCALATE** (Novel or out-of-distribution failure, routing package with missing evidence)

---

## Worked Example 1: ✅ FIX (AD Account Lockout)

### 1. Raw Incoming Ticket
```json
{
  "title": "AD account locked after password reset",
  "description": "I completed a corporate password reset through the Password Reset Portal on 2025-11-18 at approximately 07:45 UTC, but sign-in to the SSO Portal at https://sso.corplabs.com continued to fail with a locked-account error and my Active Directory account (username: mcarson) became locked again within minutes. I primarily authenticate from my iPhone (WORKSTATION-IPHONE-MC) at the Charlotte office, with previously saved credentials in the iOS Mail app and Safari browser, which prevented successful access to corporate resources including Outlook and SharePoint after the password change. My employee ID is EMP-20418 and I need access restored urgently.",
  "user_role": "identity_analyst"
}
```

### 2. Layer 1: Privacy Guard (PII De-Identification)
- **Masked Tokens**:
  - `EMP-20418` $\rightarrow$ `[EMP_ID_1]`
  - `WORKSTATION-IPHONE-MC` $\rightarrow$ `[HOSTNAME_1]`
  - `mcarson` $\rightarrow$ `[PERSON_1]`
  - `sso.corplabs.com` $\rightarrow$ `[FQDN_HOST_1]`
- **RBAC Check**:
  - Category `INC-ALP` involves privileged credentials.
  - Submitter Role `identity_analyst` $\rightarrow$ **Access Granted**.

### 3. Layer 2: Classification & Similarity Retrieval
- **Category**: `INC-ALP` (Active Directory Account Lockout) — **Confidence: 94.2%**
- **Priority**: `high` — **Confidence: 58.4%**
- **Attribution Tokens**: `["account locked", "password reset", "sso portal", "locked account", "mail app"]`
- **Top Similar Historical Ticket**: `INC-ALP-0001` (Cosine Similarity: **0.78**)
  - *Match Rationale*: Strong symptom overlap with historical incident `INC-ALP-0001` (same applications: Password Reset Portal, SSO Portal; matching lockout pattern).

### 4. Layer 3: Decision Gate Arbiter
- **Selected State**: **`FIX`**
- **Arbiter Reason**: Strong consensus: Nearest resolved case `INC-ALP-0001` (0.78) aligns with predicted category *Active Directory Account Lockout* (0.94).
- **Target Team**: Identity & Access Support

### 5. Layer 4: Role-Adaptive LLM Synthesis Grounded in Nearest Solved Case
The LLM response is grounded directly in the nearest solved case `INC-ALP-0001` and adapts its tone, depth, and action instructions according to the analyst's persona role:

#### Option A: Active Role = `identity_analyst` (Identity & Directory Specialist)
> **Identity Operations Diagnostic — Grounded in INC-ALP-0001**
> - **Domain Controller Diagnostic**: Checked DC-EAST-03 security event log. Verified Event ID `4740` with lockout status code `0xC0000234` triggered by Caller Computer Name `WORKSTATION-IPHONE-MC`.
> - **Directory Action**: Executed `Unlock-ADAccount -Identity "mcarson"`. Confirmed user object state returned to unlocked across East domain replicas.
> - **Token & Session Invalidation**: Revoked stale SAML/OAuth refresh tokens on the SSO Portal to prevent persistent re-auth failures.
> - **Remediation**: Re-enrolled user mobile profile via MDM, clearing cached Exchange ActiveSync credentials from Safari and iOS Mail.

#### Option B: Active Role = `service_desk_analyst` (Operational Support)
> **Service Desk Resolution Plan — Grounded in INC-ALP-0001**
> - **Root Cause**: Account lockout loop caused by stale mobile cached credentials retrying authentication against SSO after a corporate password reset.
> - **Action Taken**:
>   1. Validated identity in Active Directory and performed an account unlock.
>   2. Issued a fresh one-time password reset token for the Password Reset Portal.
>   3. Guided user to delete and re-add the corporate Exchange account on their iPhone and clear Safari cached credentials.
>   4. Revoked prior SSO sessions and confirmed successful sign-in.

#### Option C: Active Role = `general_helpdesk` (Plain Language / Frontline Tier 1)
> **Frontline Helpdesk Guidance — Grounded in INC-ALP-0001**
> - **Summary**: Your account is locked because an iPhone or browser is still trying to log in with an old password.
> - **How to Help the User**:
>   1. Inform the user that their account has been unlocked.
>   2. Advise the user to immediately remove and re-add their work email on their phone and clear saved passwords in their browser before trying to log in again.
>   3. Have them complete a fresh password reset and verify they can log into the SSO portal successfully.
> - *Privileged Escalation Note*: If the account re-locks immediately, escalate directly to the Identity Team.

### 6. Verbatim Proof Verification
Every technical assertion in the generated plan passed 100% verbatim verification against historical incident `INC-ALP-0001`:

| Step # | Action | Source Citation | Quoted Evidence from Historical Record | Proof Status |
|---|---|---|---|---|
| **1** | Review AD lockout evidence on DC-EAST-03 and unlock AD account | `INC-ALP-0001` | *"Reviewed Active Directory lockout evidence on DC-EAST-03... verified Event ID 4740 with lockout status 0xC0000234... and unlocked AD account"* | **Verified ✅** |
| **2** | Issue fresh password reset token and confirm completion | `INC-ALP-0001` | *"Issued a fresh password reset token to user and confirmed user successfully completed password reset flow in Password Reset Portal"* | **Verified ✅** |
| **3** | Remove and re-add corporate account on mobile device | `INC-ALP-0001` | *"Guided user to remove and re-add corporate account on iPhone and clear saved browser credentials in Safari so old password is not retried"* | **Verified ✅** |
| **4** | Revoke stale SSO sessions and tokens | `INC-ALP-0001` | *"Revoked stale SSO sessions and tokens associated with prior sign-in state on the SSO Portal"* | **Verified ✅** |
| **5** | Validate successful authentication and record device | `INC-ALP-0001` | *"Validated successful sign-in to SSO Portal after mobile credential cleanup and documented device as lockout source"* | **Verified ✅** |

---

## Worked Example 2: ❓ ASK (Ambiguous VPN vs. Wi-Fi Disconnect)

### 1. Raw Incoming Ticket
```json
{
  "title": "Network disconnected right after connection established",
  "description": "My network connection drops immediately within 2 seconds of connecting. Cannot tell if the disconnect is originating from GlobalProtect VPN or the Corporate Wi-Fi network.",
  "user_role": "service_desk_analyst"
}
```

### 2. Layer 1: Privacy Guard (PII De-Identification)
- No personal identifiers detected. Text passes directly to triage engine.

### 3. Layer 2: Classification & Similarity Retrieval
- **Classifier Top Candidates**:
  - `INC-WCI` (Corporate Wi-Fi RADIUS Failure): **31.3%**
  - `INC-VDA` (GlobalProtect VPN Immediate Disconnect): **20.7%**
- **Retrieved Top Candidates**:
  - 1st: `INC-WCI-0044` (Similarity: **0.192**) — RADIUS authentication certificate failure
  - 2nd: `INC-VDA-0012` (Similarity: **0.174**) — GlobalProtect client machine certificate expiration
- **Lookalike / Distractor Flag**: Both tickets share keywords (`connection`, `disconnect`, `network`), but have different technical root causes.

### 4. Layer 3: Decision Gate Arbiter
- **Selected State**: **`ASK`**
- **Arbiter Reason**: Ambiguous diagnosis: Multiple competing technical causes detected. Evidence points to *Corporate Wi-Fi 802.1X / RADIUS Failure* (0.19) while competing signals indicate *GlobalProtect VPN Immediate Disconnect* (0.17).

### 5. Layer 4: Question Picker Output
- **Disambiguating Question Presented to Analyst**:
  > *"Does this disconnect occur while connected over GlobalProtect VPN, or directly on the Corporate Wi-Fi network?"*
- **Competing Causes Displayed**:
  1. **GlobalProtect VPN**: Expired endpoint machine certificate causing GlobalProtect validation failure.
  2. **Corporate Wi-Fi**: RADIUS/WLC wireless authentication server certificate expired.

---

## Worked Example 3: 🚨 ESCALATE (Out-Of-Distribution / Novel Error)

### 1. Raw Incoming Ticket
```json
{
  "title": "Quantum DB cluster partition error in production zone 4",
  "description": "Production database node quantum-db-04 failed quorum sync with error QD-9941 raft state corrupt. Data pipeline halted.",
  "user_role": "service_desk_analyst"
}
```

### 2. Layer 1: Privacy Guard (PII De-Identification)
- `quantum-db-04` redacted as `[HOSTNAME_1]`.

### 3. Layer 2: Classification & Similarity Retrieval
- **Classifier Top Candidate**: `INC-DRF` — **Confidence: 12.8%** (Entropy high, flat distribution)
- **Retriever Top Match**: `INC-DRF-0013` — **Similarity: 0.176** (Purely spurious keyword matches on words like *production*)

### 4. Layer 3: Decision Gate Arbiter
- **Selected State**: **`ESCALATE`**
- **Arbiter Reason**: Low evidence confidence (Top similarity: 0.18, Category certainty: 0.13). No verified playbook exists in the 745 incident historical corpus.
- **Safety Guarantee**: The engine refuses to hallucinate database recovery commands.

### 5. Layer 4: Escalation Package
- **Recommended Target Team**: `Core Infrastructure Database Ops`
- **Missing Information Required for Specialist Review**:
  - Host configuration logs
  - Observed application error stack trace
  - Network trace / packet capture
- **Audit Action**: Recorded in audit log as `ESCALATE` for Tier 2/3 engineering dispatch.
