import os
import sys
import json
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Ensure project modules are importable
base_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, base_dir)

from engine.privacy import PrivacyGuard
from engine.sorter import TicketSorter
from engine.retriever import TicketRetriever
from engine.decision import DecisionGate
from engine.resolver import FixResolver
from engine.audit import AuditLedger
from engine.llm import LLMService

app = FastAPI(title="CiteDesk IT Ticket Resolution Assistant", version="2.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

train_corpus_path = os.path.join(base_dir, "data", "train_split.json")
full_corpus_path = os.path.join(base_dir, "data", "clean_corpus.json")
audit_log_path = os.path.join(base_dir, "data", "audit_log.jsonl")

print("Initializing CiteDesk AI Engine & Retrievers...")
sorter = TicketSorter(train_corpus_path)
retriever = TicketRetriever(train_corpus_path)
full_retriever = TicketRetriever(full_corpus_path)
audit_ledger = AuditLedger(audit_log_path)
print("CiteDesk Engine initialized successfully!")

# Request Models: strictly Employee Name, ID, Mail, Department
class UserProfile(BaseModel):
    name: Optional[str] = ""
    employee_id: Optional[str] = ""
    email: Optional[str] = ""
    department: Optional[str] = ""

class TicketAnalysisRequest(BaseModel):
    title: str
    description: str
    applications: Optional[List[str]] = []
    user_role: Optional[str] = "service_desk_analyst"
    user_profile: Optional[UserProfile] = None
    clarification_response: Optional[str] = None
    llm_provider: Optional[str] = "gemini"
    llm_model: Optional[str] = None
    api_key: Optional[str] = None

class HumanInterventionRequest(BaseModel):
    audit_id: str
    action: str  # 'approve', 'reject', 'override'
    analyst_notes: Optional[str] = ""
    overrides: Optional[Dict[str, Any]] = None
    edited_text: Optional[str] = None
    title: Optional[str] = ""
    description: Optional[str] = ""
    user_role: Optional[str] = "service_desk_analyst"
    user_profile: Optional[UserProfile] = None

class FeedbackRequest(BaseModel):
    audit_id: str
    rating: str  # 'useful', 'wrong', 'unresolved'
    notes: Optional[str] = ""
    action_taken: Optional[str] = ""

# API Endpoints
@app.post("/api/analyze")
async def analyze_ticket(req: TicketAnalysisRequest):
    user_dict = req.user_profile.dict() if req.user_profile else {}
    
    # Contextual info if provided
    user_ctx = ""
    if req.user_profile:
        p = req.user_profile
        parts = []
        if p.name: parts.append(f"User: {p.name}")
        if p.employee_id: parts.append(f"EMP-ID: {p.employee_id}")
        if p.email: parts.append(f"Email: {p.email}")
        if p.department: parts.append(f"Dept: {p.department}")
        if parts:
            user_ctx = f" [{' ,'.join(parts)}]"
            
    full_description = f"{req.description}{user_ctx}"
    if req.clarification_response:
        full_description += f"\n[User Follow-Up Clarification]: {req.clarification_response}"
        
    # 1. Privacy Filter (Internal Redaction)
    redacted_title, pii_title = PrivacyGuard.redact_text(req.title)
    redacted_desc, pii_desc = PrivacyGuard.redact_text(full_description)
    all_pii = pii_title + pii_desc
    
    # 2. Sorter & Classification (FR-01)
    classification = sorter.predict(redacted_title, redacted_desc, req.applications)
    
    # 3. RBAC Scoping Check based on active user role
    rbac_info = PrivacyGuard.check_rbac_permission(classification["category_code"], req.user_role)
    
    # 4. Similar Tickets Retrieval (FR-02)
    similar_tickets = retriever.search_similar(
        redacted_title,
        redacted_desc,
        req.applications,
        top_k=4
    )
    
    # 5. Decision Gate Arbiter (FR-05) - with personalized greeting from input profile
    emp_name = req.user_profile.name if req.user_profile and req.user_profile.name else ""
    decision = DecisionGate.evaluate(classification, similar_tickets, redacted_desc, user_name=emp_name)
    
    # 6. LLM Response Based on Nearest Solved Case & Active Role Persona
    resolution = FixResolver.build_resolution(
        decision_info=decision,
        similar_tickets=similar_tickets,
        ticket_title=redacted_title,
        ticket_desc=redacted_desc,
        user_profile=user_dict,
        user_role=req.user_role or "service_desk_analyst",
        api_key=req.api_key,
        llm_provider=req.llm_provider or "gemini",
        llm_model=req.llm_model
    )
    
    # 7. Audit Logging (FR-08)
    audit_id = audit_ledger.log_analysis(
        raw_title=req.title,
        redacted_title=redacted_title,
        redacted_desc=redacted_desc,
        pii_detections=all_pii,
        classification=classification,
        decision=decision,
        verified_steps=[],
        similar_tickets=similar_tickets,
        user_role=req.user_role,
        rbac_info=rbac_info,
        user_profile=user_dict,
        llm_trace=resolution.get("llm_trace")
    )
    
    return {
        "audit_id": audit_id,
        "rbac": rbac_info,
        "classification": classification,
        "decision": decision,
        "user_facing_response": resolution.get("user_facing_response", ""),
        "root_cause_explanation": resolution.get("root_cause_explanation", ""),
        "nearest_case_used": resolution.get("nearest_case_used", "INC-REF"),
        "persona_mode": resolution.get("persona_mode", ""),
        "similar_tickets": similar_tickets,
        "llm_trace": resolution.get("llm_trace")
    }

@app.post("/api/human-intervention")
async def human_intervention(req: HumanInterventionRequest):
    success = audit_ledger.record_human_intervention(
        audit_id=req.audit_id,
        action=req.action,
        analyst_notes=req.analyst_notes or "",
        overrides=req.overrides,
        edited_text=req.edited_text
    )
    if not success:
        raise HTTPException(status_code=404, detail="Audit record not found.")
        
    res_data = {
        "status": "success",
        "audit_id": req.audit_id,
        "action": req.action,
        "analyst_notes": req.analyst_notes
    }
    
    # If this is an override request, dynamically recompute nearest similar tickets and resolution if category was changed
    if req.action == "override" and req.overrides:
        cat_override = req.overrides.get("category")
        dec_override = req.overrides.get("decision", "FIX")
        user_dict = req.user_profile.dict() if req.user_profile else {}
        
        sim_tickets = full_retriever.search_similar(
            req.title or "IT Incident",
            req.description or "User reported issue",
            top_k=4,
            category_filter=cat_override
        )
        if not sim_tickets:
            sim_tickets = full_retriever.search_similar(
                req.title or "IT Incident",
                req.description or "User reported issue",
                top_k=4
            )
            
        mock_decision = {
            "decision": dec_override,
            "reason": f"Manual triage override applied by {req.user_role or 'analyst'}.",
            "confidence_score": 0.99,
            "target_team": "Tier 2/3 Specialist Operations" if dec_override == "ESCALATE" else "Service Desk Support"
        }
        
        synth = FixResolver.build_resolution(
            decision_info=mock_decision,
            similar_tickets=sim_tickets,
            ticket_title=req.title or "",
            ticket_desc=req.description or "",
            user_profile=user_dict,
            user_role=req.user_role or "service_desk_analyst"
        )
        
        res_data["recalculated"] = {
            "similar_tickets": sim_tickets,
            "user_facing_response": synth.get("user_facing_response", ""),
            "root_cause_explanation": synth.get("root_cause_explanation", ""),
            "nearest_case_used": synth.get("nearest_case_used", "INC-REF"),
            "persona_mode": synth.get("persona_mode", ""),
            "decision": mock_decision
        }
        
    return res_data

@app.post("/api/feedback")
async def record_feedback(fb: FeedbackRequest):
    success = audit_ledger.record_feedback(
        audit_id=fb.audit_id,
        rating=fb.rating,
        analyst_notes=fb.notes,
        resolution_action_taken=fb.action_taken
    )
    if not success:
        raise HTTPException(status_code=404, detail="Audit record not found.")
    return {"status": "success", "audit_id": fb.audit_id, "rating": fb.rating}

@app.get("/api/search")
async def search_corpus(
    query: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = 50
):
    results = full_retriever.filter_tickets(
        query=query,
        category=category,
        priority=priority,
        platform=platform,
        limit=limit
    )
    return {"total_returned": len(results), "tickets": results}

@app.get("/api/audit-logs")
async def get_audit_logs(limit: int = 40):
    logs = audit_ledger.get_recent_logs(limit)
    return {"count": len(logs), "logs": logs}

@app.get("/api/presets")
async def get_presets():
    return {
        "presets": [
            {
                "id": "preset_fix",
                "label": "Case 1: Fix (AD Account Lockout)",
                "state": "FIX",
                "title": "AD account locked after password reset",
                "description": "I completed a corporate password reset through the Password Reset Portal on 2025-11-18 at approximately 07:45 UTC, but sign-in to the SSO Portal at https://sso.corplabs.com continued to fail with a locked-account error and my Active Directory account became locked again within minutes. I primarily authenticate from my mobile phone at the Charlotte office, with previously saved credentials in the Mail app and Safari browser.",
                "apps": ["Password Reset Portal", "SSO Portal"],
                "role": "identity_analyst"
            },
            {
                "id": "preset_ask",
                "label": "Case 2: Ask (Ambiguous Network Disconnect)",
                "state": "ASK",
                "title": "Network disconnected right after connection established",
                "description": "My network connection drops immediately within 2 seconds of connecting. Cannot tell if the disconnect is originating from GlobalProtect VPN or the Corporate Wi-Fi network.",
                "apps": [],
                "role": "service_desk_analyst"
            },
            {
                "id": "preset_esc",
                "label": "Case 3: Escalate (Novel Quantum DB Error)",
                "state": "ESCALATE",
                "title": "Quantum DB cluster partition error in production zone 4",
                "description": "Production database node quantum-db-04 failed quorum sync with error QD-9941 raft state corrupt. Data pipeline halted.",
                "apps": [],
                "role": "service_desk_analyst"
            },
            {
                "id": "preset_rbac",
                "label": "Case 4: RBAC Policy Test (Privileged BitLocker)",
                "state": "FIX",
                "title": "BitLocker encryption recovery key locked on endpoint",
                "description": "TPM protector was not initialized on workstation LAPTOP-FIN-992. Employee cannot access encrypted volume.",
                "apps": ["Company Portal"],
                "role": "general_helpdesk"
            }
        ]
    }

# Frontend Web Interface
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CiteDesk | Evidence-Backed IT Resolution Assistant</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen antialiased flex flex-col font-sans select-none">
  
  <!-- Floating Toast Notification Container -->
  <div id="toast-container" class="fixed top-5 right-5 z-50 flex flex-col gap-2 max-w-sm pointer-events-none"></div>
  
  <!-- Navigation Header -->
  <header class="border-b border-slate-800 bg-slate-950/90 backdrop-blur sticky top-0 z-50 px-6 py-3 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center font-bold text-white shadow-lg shadow-sky-500/20">
        <i class="fa-solid fa-shield-halved text-lg"></i>
      </div>
      <div>
        <div class="flex items-center gap-2">
          <span class="font-bold tracking-tight text-white text-base">CiteDesk</span>
          <span class="text-[11px] px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/20 font-medium">HCL Hackathon · ITSM AI</span>
        </div>
        <p class="text-[11px] text-slate-400">Role-Adaptive LLM Resolution Grounded in Solved Cases</p>
      </div>
    </div>
    
    <div class="flex items-center gap-3 text-xs">
      <!-- LLM Provider & Key Pill -->
      <button onclick="toggleLLMModal()" class="px-3 py-1.5 rounded-lg border border-indigo-500/30 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 font-medium transition flex items-center gap-1.5">
        <i class="fa-solid fa-brain text-indigo-400"></i>
        <span id="llm-pill-status">LLM: Gemini / Grounded</span>
        <i class="fa-solid fa-gear text-[10px] text-slate-400 ml-1"></i>
      </button>

      <!-- Nav Tabs -->
      <div class="flex items-center gap-1 bg-slate-900 border border-slate-800 rounded-lg p-1">
        <button id="nav-workbench" onclick="switchTab('workbench')" class="px-3 py-1.5 rounded-md font-medium bg-sky-600 text-white transition"><i class="fa-solid fa-microchip mr-1.5"></i>Workbench</button>
        <button id="nav-search" onclick="switchTab('search')" class="px-3 py-1.5 rounded-md font-medium text-slate-400 hover:text-white transition"><i class="fa-solid fa-magnifying-glass mr-1.5"></i>745 Search</button>
        <button id="nav-audit" onclick="switchTab('audit')" class="px-3 py-1.5 rounded-md font-medium text-slate-400 hover:text-white transition"><i class="fa-solid fa-book-bookmark mr-1.5"></i>Audit Log</button>
      </div>
      
      <!-- Role Selector -->
      <div class="flex items-center gap-1.5 bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-800">
        <span class="text-slate-400">Model Role Persona:</span>
        <select id="user-role-select" onchange="handleRoleChange()" class="bg-transparent text-sky-400 font-semibold outline-none cursor-pointer">
          <option value="identity_analyst" class="bg-slate-900 text-white">Identity Analyst (Privileged Lead)</option>
          <option value="service_desk_analyst" class="bg-slate-900 text-white" selected>Service Desk Tier 1/2</option>
          <option value="general_helpdesk" class="bg-slate-900 text-white">General Helpdesk (L1 Support)</option>
        </select>
      </div>
    </div>
  </header>

  <!-- LLM Config & Trace Modal -->
  <div id="llm-modal" class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 hidden">
    <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 space-y-4 shadow-2xl">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div class="flex items-center gap-2">
          <i class="fa-solid fa-brain text-indigo-400 text-lg"></i>
          <h2 class="font-bold text-sm text-white">LLM Configuration & Response Trace</h2>
        </div>
        <button onclick="toggleLLMModal()" class="text-slate-400 hover:text-white"><i class="fa-solid fa-xmark"></i></button>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
        <div>
          <label class="block text-slate-400 mb-1 font-medium">LLM Model Provider</label>
          <select id="cfg-llm-provider" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white">
            <option value="gemini">Google Gemini (gemini-3.8-flash / gemini-2.0-flash)</option>
            <option value="openai">OpenAI (gpt-4o-mini)</option>
            <option value="builtin">CiteDesk Grounded Reference Engine (Offline)</option>
          </select>
        </div>
        <div>
          <label class="block text-slate-400 mb-1 font-medium">API Key (Google Gemini or OpenAI)</label>
          <input id="cfg-api-key" type="password" placeholder="Enter API Key (optional)" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white">
          <span class="text-[10px] text-slate-500 mt-1 block">Free keys available at aistudio.google.com</span>
        </div>
      </div>

      <div class="space-y-2 text-xs">
        <span class="font-semibold text-slate-300 block">LLM Inference Trace:</span>
        <div class="bg-slate-950 border border-slate-800 rounded-xl p-3 space-y-2 max-h-60 overflow-y-auto font-mono text-[11px]">
          <div class="flex justify-between text-slate-400">
            <span>Provider: <strong id="trace-provider" class="text-indigo-400">Grounded Engine</strong></span>
            <span>Latency: <strong id="trace-latency" class="text-sky-400">12ms</strong></span>
          </div>
          <div>
            <span class="text-slate-500 block uppercase font-bold text-[10px]">Active Prompt Passed to LLM:</span>
            <p id="trace-prompt" class="text-slate-300 whitespace-pre-wrap truncate">Prompt will appear after first run.</p>
          </div>
        </div>
      </div>

      <div class="flex justify-end gap-2 text-xs pt-2">
        <button onclick="saveLLMConfig()" class="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium">Save & Apply</button>
      </div>
    </div>
  </div>

  <!-- Main Container -->
  <main class="flex-1 max-w-7xl w-full mx-auto p-6 space-y-5">

    <!-- TAB 1: ANALYST WORKBENCH -->
    <div id="tab-workbench" class="space-y-5">
      
      <!-- Presets bar -->
      <div class="bg-slate-950 border border-slate-800/80 rounded-xl p-3 flex items-center justify-between flex-wrap gap-2 text-xs">
        <div class="flex items-center gap-2 text-slate-400">
          <i class="fa-solid fa-wand-magic-sparkles text-sky-400"></i>
          <span>Worked Example Presets:</span>
        </div>
        <div class="flex items-center gap-2 flex-wrap">
          <button onclick="loadPreset('preset_fix')" class="px-3 py-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 font-medium transition flex items-center gap-1.5">
            <i class="fa-solid fa-circle-check"></i> Case 1: Fix (AD Lockout)
          </button>
          <button onclick="loadPreset('preset_ask')" class="px-3 py-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 font-medium transition flex items-center gap-1.5">
            <i class="fa-solid fa-circle-question"></i> Case 2: Ask (VPN vs Wi-Fi)
          </button>
          <button onclick="loadPreset('preset_esc')" class="px-3 py-1.5 rounded-lg border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 font-medium transition flex items-center gap-1.5">
            <i class="fa-solid fa-triangle-exclamation"></i> Case 3: Escalate (OOD Error)
          </button>
          <button onclick="loadPreset('preset_rbac')" class="px-3 py-1.5 rounded-lg border border-purple-500/30 bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 font-medium transition flex items-center gap-1.5">
            <i class="fa-solid fa-lock"></i> Case 4: RBAC Policy Test
          </button>
        </div>
      </div>

      <!-- Grid Layout -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        <!-- Left: Incident & Optional Employee Info (5 cols) -->
        <div class="lg:col-span-5 space-y-4">
          
          <!-- Employee Details (ONLY 4 fields: Name, ID, Mail, Department) -->
          <div class="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3">
            <div class="flex items-center justify-between">
              <h3 class="font-semibold text-xs text-white flex items-center gap-2">
                <i class="fa-solid fa-user text-sky-400"></i> Employee Information
              </h3>
              <span class="text-[10px] text-slate-500">Only 4 fields</span>
            </div>

            <div class="grid grid-cols-2 gap-2.5 text-xs">
              <div>
                <label class="block text-slate-400 mb-1 text-[11px]">Employee Name</label>
                <input id="usr-name" type="text" class="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-white" placeholder="e.g. Monica Carson">
              </div>
              <div>
                <label class="block text-slate-400 mb-1 text-[11px]">Employee ID</label>
                <input id="usr-empid" type="text" class="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-white" placeholder="e.g. EMP-20418">
              </div>
              <div>
                <label class="block text-slate-400 mb-1 text-[11px]">Mail</label>
                <input id="usr-email" type="text" class="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-white" placeholder="e.g. monica@corplabs.com">
              </div>
              <div>
                <label class="block text-slate-400 mb-1 text-[11px]">Department</label>
                <input id="usr-dept" type="text" class="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-white" placeholder="e.g. Finance">
              </div>
            </div>
          </div>

          <!-- Incident Form -->
          <div class="bg-slate-950 border border-slate-800 rounded-xl p-5 space-y-4">
            <h2 class="font-semibold text-sm text-white flex items-center gap-2">
              <i class="fa-solid fa-ticket text-sky-400"></i> Incident Report
            </h2>

            <div class="space-y-3 text-xs">
              <div>
                <label class="block text-slate-400 mb-1 font-medium">Ticket Title</label>
                <input id="input-title" type="text" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-sky-500" placeholder="e.g. AD account locked after password reset">
              </div>

              <div>
                <label class="block text-slate-400 mb-1 font-medium">Symptom Description & Error Messages</label>
                <textarea id="input-desc" rows="6" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 text-xs leading-relaxed" placeholder="User reported symptoms, error codes, and timeline..."></textarea>
              </div>

              <div>
                <label class="block text-slate-400 mb-1 font-medium">Applications Affected</label>
                <input id="input-apps" type="text" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white placeholder-slate-500" placeholder="Password Reset Portal, SSO Portal">
              </div>

              <button onclick="analyzeCurrentTicket()" id="btn-analyze" class="w-full py-2.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs transition shadow-lg shadow-sky-600/20 flex items-center justify-center gap-2">
                <i class="fa-solid fa-wand-magic-sparkles"></i> Generate Response via LLM
              </button>
            </div>
          </div>

        </div>

        <!-- Right: Triage Decision & LLM Response (7 cols) -->
        <div class="lg:col-span-7 space-y-4">
          
          <!-- Placeholder before Run -->
          <div id="results-empty" class="bg-slate-950 border border-slate-800 rounded-xl p-12 text-center space-y-3">
            <div class="w-12 h-12 rounded-full bg-slate-900 text-slate-500 flex items-center justify-center mx-auto text-xl">
              <i class="fa-solid fa-robot"></i>
            </div>
            <h3 class="text-sm font-semibold text-slate-300">Awaiting Incident Submission</h3>
            <p class="text-xs text-slate-500 max-w-sm mx-auto">Click one of the Worked Example presets above or type a new incident to generate the LLM response shaped by your active role persona.</p>
          </div>

          <!-- Active Results Container -->
          <div id="results-container" class="space-y-4 hidden">
            
            <!-- Decision Banner -->
            <div id="decision-banner" class="border rounded-2xl p-5 space-y-3 shadow-xl transition-all">
              <div class="flex items-center justify-between flex-wrap gap-2">
                <div class="flex items-center gap-2.5">
                  <span id="state-badge" class="px-3 py-1 rounded-full text-xs font-bold tracking-wider uppercase"></span>
                  <span id="confidence-badge" class="text-xs font-mono font-medium text-slate-300"></span>
                </div>
                <div class="flex items-center gap-2 text-xs">
                  <span class="text-slate-400">Assigned Team:</span>
                  <span id="team-badge" class="font-medium text-sky-400"></span>
                </div>
              </div>

              <div class="space-y-1">
                <h3 id="category-heading" class="text-base font-bold text-white tracking-tight"></h3>
                <p id="decision-reason" class="text-xs leading-relaxed"></p>
              </div>

              <!-- Feature attribution tokens -->
              <div class="pt-2 border-t border-slate-800/60 flex items-center gap-1.5 flex-wrap text-[11px]">
                <span class="text-slate-400 font-medium">Attribution Signals:</span>
                <div id="attribution-tokens" class="flex flex-wrap gap-1"></div>
              </div>
            </div>

            <!-- PRIMARY CARD: LLM GENERATED RESPONSE TO USER QUERY -->
            <div id="llm-response-card" class="bg-gradient-to-b from-indigo-950/40 to-slate-950 border border-indigo-500/40 rounded-2xl p-5 space-y-3 shadow-xl">
              <div class="flex items-center justify-between flex-wrap gap-2 border-b border-indigo-500/20 pb-2.5">
                <div class="flex items-center gap-2">
                  <span class="w-7 h-7 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold text-xs">
                    <i class="fa-solid fa-comment-dots"></i>
                  </span>
                  <div>
                    <div class="flex items-center gap-2">
                      <h3 class="font-bold text-sm text-white">LLM Response to User Query</h3>
                      <span id="persona-badge" class="px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 font-mono text-[10px] border border-purple-500/30">Role Persona: Service Desk Tier 1/2</span>
                    </div>
                    <p class="text-[10px] text-indigo-300">Synthesized directly from nearest solved case & adapted to active role</p>
                  </div>
                </div>
                <div class="flex items-center gap-2 text-xs">
                  <span id="nearest-case-badge" class="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-mono text-[10px] border border-emerald-500/30">Nearest: INC-ALP-0001</span>
                  <button id="btn-edit-toggle" onclick="toggleEditDraft()" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-medium flex items-center gap-1 transition border border-slate-700">
                    <i class="fa-solid fa-pen-to-square"></i> <span id="btn-edit-label">Edit Draft</span>
                  </button>
                  <button onclick="copyLLMResponse()" class="px-2.5 py-1 rounded bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-200 text-[11px] font-medium flex items-center gap-1 transition">
                    <i class="fa-solid fa-copy"></i> Copy Reply
                  </button>
                </div>
              </div>

              <!-- Live Dispatched Watermark Banner -->
              <div id="dispatch-banner" class="hidden p-3 rounded-xl bg-emerald-950/70 border border-emerald-500/50 text-emerald-200 text-xs flex items-center justify-between">
                <div class="flex items-center gap-2.5">
                  <div class="w-7 h-7 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-sm">
                    <i class="fa-solid fa-circle-check"></i>
                  </div>
                  <div>
                    <span class="font-bold text-white">Approved & Dispatched by Human Reviewer</span>
                    <p class="text-[11px] text-emerald-300">Delivered to <strong id="dispatch-recipient" class="text-white">Employee</strong> · Role: <span id="dispatch-role">Analyst</span></p>
                  </div>
                </div>
                <div class="text-right">
                  <span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono text-[10px] uppercase font-bold border border-emerald-500/30">Delivered</span>
                  <p id="dispatch-timestamp" class="text-[10px] text-emerald-400/80 font-mono mt-0.5"></p>
                </div>
              </div>

              <!-- Live Rejection Notice Banner -->
              <div id="reject-banner" class="hidden p-3 rounded-xl bg-rose-950/70 border border-rose-500/50 text-rose-200 text-xs flex items-center justify-between">
                <div class="flex items-center gap-2.5">
                  <div class="w-7 h-7 rounded-lg bg-rose-500/20 text-rose-400 flex items-center justify-center font-bold text-sm">
                    <i class="fa-solid fa-ban"></i>
                  </div>
                  <div>
                    <span class="font-bold text-white">Ticket Rejected by Frontline Analyst</span>
                    <p id="reject-reason-text" class="text-[11px] text-rose-300">Escalated directly to Tier 3 Specialist Operations.</p>
                  </div>
                </div>
                <span class="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-mono text-[10px] uppercase font-bold border border-rose-500/30">Tier 3 Escalation</span>
              </div>

              <!-- User Response View Mode -->
              <div id="llm-user-reply-text" class="bg-slate-900/80 p-4 rounded-xl border border-slate-800 text-xs text-slate-200 leading-relaxed font-sans whitespace-pre-wrap">
                Generating LLM response...
              </div>

              <!-- User Response Edit Mode -->
              <div id="llm-user-reply-edit-container" class="hidden space-y-2">
                <textarea id="llm-user-reply-edit" rows="9" class="w-full bg-slate-950 border border-indigo-500/50 rounded-xl p-3 text-xs text-white font-sans leading-relaxed focus:outline-none focus:border-indigo-400"></textarea>
                <div class="flex items-center justify-between text-xs">
                  <span class="text-indigo-400 text-[11px]"><i class="fa-solid fa-pen-nib mr-1"></i>Edit the draft before approving and dispatching to employee</span>
                  <div class="flex items-center gap-2">
                    <button onclick="cancelEditDraft()" class="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 text-[11px]">Cancel</button>
                    <button onclick="saveEditDraft()" class="px-3.5 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-[11px] flex items-center gap-1"><i class="fa-solid fa-check"></i> Save Changes</button>
                  </div>
                </div>
              </div>

              <!-- Root Cause Analysis -->
              <div class="pt-1 text-[11px] text-slate-400">
                <span class="font-semibold text-slate-300 block mb-0.5"><i class="fa-solid fa-circle-info text-sky-400 mr-1"></i> Root Cause from Nearest Solved Incident:</span>
                <p id="llm-root-cause-text" class="text-slate-300 italic"></p>
              </div>

              <!-- Feedback Bar -->
              <div class="pt-3 border-t border-slate-800/80 flex items-center justify-between flex-wrap gap-3 text-xs">
                <span class="text-slate-400 text-[11px]">Was this response accurate?</span>
                <div class="flex items-center gap-2">
                  <button onclick="submitFeedback('useful')" class="px-2.5 py-1 rounded-lg border border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-xs font-medium transition flex items-center gap-1">
                    <i class="fa-solid fa-thumbs-up"></i> Useful
                  </button>
                  <button onclick="submitFeedback('wrong')" class="px-2.5 py-1 rounded-lg border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 text-xs font-medium transition flex items-center gap-1">
                    <i class="fa-solid fa-thumbs-down"></i> Wrong
                  </button>
                  <button onclick="submitFeedback('unresolved')" class="px-2.5 py-1 rounded-lg border border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 text-xs font-medium transition flex items-center gap-1">
                    <i class="fa-solid fa-question"></i> Didn't Solve
                  </button>
                </div>
              </div>
            </div>

            <!-- Branch B: ASK Disambiguating Question & Interactive User Dialog -->
            <div id="branch-ask" class="bg-slate-950 border border-amber-500/30 rounded-xl p-5 space-y-4 hidden">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-amber-400">
                  <i class="fa-solid fa-comments-question-check text-lg"></i>
                  <h3 class="font-semibold text-sm">Disambiguating Question Required</h3>
                </div>
                <span class="text-[11px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 font-mono">Employee Inquiry</span>
              </div>
              
              <div class="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4">
                <span class="text-[11px] font-bold text-amber-300 uppercase tracking-wider block mb-1">Recommended Question for Employee:</span>
                <p id="ask-question-text" class="text-sm font-semibold text-white leading-relaxed"></p>
              </div>

              <!-- Interactive User Clarification Form -->
              <div class="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3 text-xs">
                <div class="flex items-center justify-between">
                  <span class="font-semibold text-slate-200 flex items-center gap-1.5">
                    <i class="fa-solid fa-reply text-sky-400"></i> Interactive Employee Clarification
                  </span>
                  <span class="text-slate-500 text-[11px]">Select or type user response</span>
                </div>

                <!-- Quick response buttons -->
                <div class="flex items-center gap-2 flex-wrap">
                  <button onclick="setClarification('I am connected on Corporate Wi-Fi inside the office')" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-sky-300 text-[11px] border border-slate-700">"Connected on Wi-Fi"</button>
                  <button onclick="setClarification('I am using GlobalProtect VPN from home over home internet')" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-sky-300 text-[11px] border border-slate-700">"Using GlobalProtect VPN"</button>
                  <button onclick="setClarification('The browser displays error 0xC0000234 Account Locked Out')" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-sky-300 text-[11px] border border-slate-700">"Account Locked Error"</button>
                  <button onclick="setClarification('The browser is trapped in repeated Okta MFA prompt redirect loop')" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-sky-300 text-[11px] border border-slate-700">"Repeated MFA Loop"</button>
                </div>

                <div class="flex items-center gap-2">
                  <input id="user-clarification-input" type="text" placeholder="Enter user's clarifying response..." class="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white placeholder-slate-500">
                  <button onclick="submitUserClarification()" class="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold transition flex items-center gap-1.5">
                    <i class="fa-solid fa-paper-plane"></i> Re-Triage
                  </button>
                </div>
              </div>

              <div class="space-y-2">
                <span class="text-xs font-semibold text-slate-300">Competing Diagnoses Detected:</span>
                <div id="ask-competing-list" class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs"></div>
              </div>
            </div>

            <!-- Branch C: ESCALATE Routing Package -->
            <div id="branch-escalate" class="bg-slate-950 border border-rose-500/30 rounded-xl p-5 space-y-4 hidden">
              <div class="flex items-center gap-2 text-rose-400">
                <i class="fa-solid fa-shield-exclamation text-lg"></i>
                <h3 class="font-semibold text-sm">Escalation Package (Tier 2/3 Specialist Dispatch)</h3>
              </div>
              <div class="bg-rose-500/10 border border-rose-500/20 rounded-xl p-4 space-y-2">
                <div class="flex justify-between text-xs">
                  <span class="text-slate-400">Dispatch Target:</span>
                  <span id="esc-target-team" class="font-bold text-white"></span>
                </div>
                <p id="esc-reason-text" class="text-xs text-rose-200 leading-relaxed"></p>
              </div>
              <div class="space-y-2 text-xs">
                <span class="font-semibold text-slate-300">Missing Evidence Required Before Manual Remediation:</span>
                <ul id="esc-missing-items" class="list-disc list-inside space-y-1 text-slate-400"></ul>
              </div>
            </div>

            <!-- HUMAN INTERVENTION & ANALYST CONTROLS -->
            <div id="human-signoff-card" class="bg-slate-950 border border-indigo-500/40 rounded-xl p-4 space-y-3 shadow-lg transition-all">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <i class="fa-solid fa-user-gear text-indigo-400"></i>
                  <h3 class="font-semibold text-xs text-white">Human Analyst Sign-Off & Overrides</h3>
                </div>
                <div class="flex items-center gap-2">
                  <span id="review-status-badge" class="text-[10px] px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-300 font-mono border border-amber-500/30 flex items-center gap-1">
                    <i class="fa-solid fa-hourglass-half"></i> Pending Sign-Off
                  </span>
                  <span class="text-[10px] px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 font-mono">HITL Gate</span>
                </div>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-3 gap-2.5 text-xs">
                <div>
                  <label class="block text-slate-400 mb-1 text-[11px]">Category Override</label>
                  <select id="override-category" class="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-white">
                    <option value="">Keep AI Prediction</option>
                    <option value="INC-ALP">INC-ALP: AD Account Lockout</option>
                    <option value="INC-SML">INC-SML: SSO / MFA Loop</option>
                    <option value="INC-VDA">INC-VDA: GlobalProtect VPN</option>
                    <option value="INC-WCI">INC-WCI: Wi-Fi 802.1X / RADIUS</option>
                    <option value="INC-CES">INC-CES: Expired TLS Cert</option>
                    <option value="INC-DCP">INC-DCP: Intune Compliance</option>
                    <option value="INC-DRF">INC-DRF: DNS Resolution</option>
                    <option value="INC-EDE">INC-EDE: BitLocker TPM</option>
                    <option value="INC-LPD">INC-LPD: Laptop Slowness</option>
                    <option value="INC-OES">INC-OES: Outlook Exchange</option>
                    <option value="INC-PDQ">INC-PDQ: Print Spooler</option>
                    <option value="INC-SDA">INC-SDA: Shared Drive Access</option>
                    <option value="INC-SIB">INC-SIB: Software Center</option>
                    <option value="INC-AIT">INC-AIT: Integration Gateway</option>
                  </select>
                </div>
                <div>
                  <label class="block text-slate-400 mb-1 text-[11px]">Priority Override</label>
                  <select id="override-priority" class="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-white">
                    <option value="">Keep AI Priority</option>
                    <option value="high">High Priority</option>
                    <option value="medium">Medium Priority</option>
                    <option value="low">Low Priority</option>
                  </select>
                </div>
                <div>
                  <label class="block text-slate-400 mb-1 text-[11px]">Decision State Override</label>
                  <select id="override-decision" class="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-white">
                    <option value="">Keep AI Decision</option>
                    <option value="FIX">Force FIX (Generate Plan)</option>
                    <option value="ASK">Force ASK (Inquire User)</option>
                    <option value="ESCALATE">Force ESCALATE (Tier 3)</option>
                  </select>
                </div>
              </div>

              <!-- Analyst investigation notes -->
              <div>
                <label class="block text-slate-400 mb-1 text-[11px]">Analyst Notes & Actions</label>
                <input id="analyst-notes-input" type="text" placeholder="Add custom notes (e.g. Validated user identity via phone callback)..." class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500">
              </div>

              <!-- Human Action Buttons -->
              <div class="flex items-center justify-between pt-2 border-t border-slate-800 text-xs">
                <div class="flex items-center gap-2">
                  <button id="btn-approve" onclick="applyHumanAction('approve')" class="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition flex items-center gap-1.5 shadow-md shadow-emerald-900/30">
                    <i class="fa-solid fa-stamp"></i> Approve & Send to User
                  </button>
                  <button id="btn-reject" onclick="applyHumanAction('reject')" class="px-3.5 py-1.5 rounded-lg bg-rose-600/80 hover:bg-rose-600 text-white font-medium transition flex items-center gap-1.5 shadow-md shadow-rose-900/30">
                    <i class="fa-solid fa-ban"></i> Reject & Dispatch Tier 3
                  </button>
                </div>
                <button id="btn-apply-overrides" onclick="applyOverrides()" class="px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-900 hover:bg-slate-800 text-slate-300 transition flex items-center gap-1.5">
                  <i class="fa-solid fa-sliders"></i> Apply Overrides
                </button>
              </div>
            </div>

            <!-- Top Similar Tickets Accordion (Shows Nearest Solved Incident) -->
            <div class="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3">
              <div class="flex items-center justify-between">
                <h3 class="font-semibold text-xs text-white flex items-center gap-2">
                  <i class="fa-solid fa-clock-rotate-left text-sky-400"></i> Nearest Solved Incidents (Source Evidence)
                </h3>
                <span class="text-[11px] text-slate-500">745 Corpus Ranked</span>
              </div>
              <div id="similar-tickets-list" class="space-y-2"></div>
            </div>

          </div>
        </div>

      </div>

    </div>

    <!-- TAB 2: 745 TICKET SEARCH (FR-07) -->
    <div id="tab-search" class="space-y-4 hidden">
      <div class="bg-slate-950 border border-slate-800 rounded-xl p-5 space-y-4">
        <div class="flex items-center justify-between">
          <h2 class="font-semibold text-sm text-white flex items-center gap-2">
            <i class="fa-solid fa-filter text-sky-400"></i> ITSM Knowledge Explorer & Multi-Word Search (FR-07)
          </h2>
          <span id="search-total-badge" class="text-xs text-sky-400 font-mono">Loaded 745 Resolved Incidents</span>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
          <input id="search-query" onkeydown="handleSearchKey(event)" type="text" placeholder="Search keywords, error codes, apps (Press Enter)..." class="bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-white placeholder-slate-500">
          <select id="search-cat" onchange="executeSearch()" class="bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-white">
            <option value="">All Problem Types (14)</option>
            <option value="INC-ALP">INC-ALP: AD Account Lockout</option>
            <option value="INC-SML">INC-SML: SSO & MFA Prompt Loop</option>
            <option value="INC-VDA">INC-VDA: GlobalProtect VPN Disconnect</option>
            <option value="INC-WCI">INC-WCI: Wi-Fi 802.1X / RADIUS</option>
            <option value="INC-CES">INC-CES: Expired TLS Certificates</option>
            <option value="INC-DCP">INC-DCP: Intune Device Compliance</option>
            <option value="INC-DRF">INC-DRF: DNS Resolution Failure</option>
            <option value="INC-EDE">INC-EDE: BitLocker TPM Protector</option>
            <option value="INC-LPD">INC-LPD: Windows Laptop Slowness</option>
            <option value="INC-OES">INC-OES: Outlook Exchange Sync</option>
            <option value="INC-PDQ">INC-PDQ: Print Spooler Stuck Jobs</option>
            <option value="INC-SDA">INC-SDA: Shared Drive Access Denied</option>
            <option value="INC-SIB">INC-SIB: Software Center Blocked</option>
            <option value="INC-AIT">INC-AIT: Integration Gateway API</option>
          </select>
          <select id="search-priority" onchange="executeSearch()" class="bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-white">
            <option value="">All Priorities</option>
            <option value="high">High Priority</option>
            <option value="medium">Medium Priority</option>
            <option value="low">Low Priority</option>
          </select>
          <button onclick="executeSearch()" class="py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-semibold transition">
            <i class="fa-solid fa-magnifying-glass mr-1"></i> Search Corpus
          </button>
        </div>
      </div>

      <div class="bg-slate-950 border border-slate-800 rounded-xl p-4 overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="border-b border-slate-800 text-slate-400 uppercase text-[10px]">
            <tr>
              <th class="py-2.5 px-3">Ticket ID</th>
              <th class="py-2.5 px-3">Category</th>
              <th class="py-2.5 px-3">Priority</th>
              <th class="py-2.5 px-3">Title & Symptoms</th>
              <th class="py-2.5 px-3">Root Cause</th>
              <th class="py-2.5 px-3">Actions</th>
            </tr>
          </thead>
          <tbody id="search-results-tbody" class="divide-y divide-slate-800/60 text-slate-300">
            <tr><td colspan="6" class="py-6 text-center text-slate-500">Loading incidents...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- TAB 3: AUDIT LOG (FR-08) -->
    <div id="tab-audit" class="space-y-4 hidden">
      <div class="bg-slate-950 border border-slate-800 rounded-xl p-5 flex items-center justify-between">
        <div>
          <h2 class="font-semibold text-sm text-white flex items-center gap-2">
            <i class="fa-solid fa-book-bookmark text-sky-400"></i> Immutable Audit Ledger (FR-08)
          </h2>
          <p class="text-xs text-slate-400">Records every inference, masked token, LLM call, human intervention, and analyst review</p>
        </div>
        <button onclick="loadAuditLogs()" class="px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-900 hover:bg-slate-800 text-xs text-slate-200">
          <i class="fa-solid fa-rotate-right mr-1"></i> Refresh Logs
        </button>
      </div>

      <div class="space-y-3" id="audit-logs-container">
        <div class="py-6 text-center text-xs text-slate-500">Loading audit records...</div>
      </div>
    </div>

  </main>

  <script>
    let currentAuditId = null;
    let currentClassification = null;
    let currentDecision = null;
    let llmConfig = { provider: 'gemini', apiKey: '' };

    function switchTab(tab) {
      ['workbench', 'search', 'audit'].forEach(t => {
        document.getElementById(`tab-${t}`).classList.add('hidden');
        document.getElementById(`nav-${t}`).classList.remove('bg-sky-600', 'text-white');
        document.getElementById(`nav-${t}`).classList.add('text-slate-400');
      });
      document.getElementById(`tab-${tab}`).classList.remove('hidden');
      document.getElementById(`nav-${tab}`).classList.add('bg-sky-600', 'text-white');
      document.getElementById(`nav-${tab}`).classList.remove('text-slate-400');

      if (tab === 'search') executeSearch();
      if (tab === 'audit') loadAuditLogs();
    }

    function toggleLLMModal() {
      document.getElementById('llm-modal').classList.toggle('hidden');
    }

    function saveLLMConfig() {
      llmConfig.provider = document.getElementById('cfg-llm-provider').value;
      llmConfig.apiKey = document.getElementById('cfg-api-key').value.trim();
      document.getElementById('llm-pill-status').innerText = `LLM: ${llmConfig.provider.toUpperCase()}${llmConfig.apiKey ? ' (Key Active)' : ' (Grounded)'}`;
      toggleLLMModal();
    }

    function handleRoleChange() {
      const role = document.getElementById('user-role-select').value;
      const roleNames = {
        'identity_analyst': 'Role Persona: Identity Specialist (Privileged Lead)',
        'service_desk_analyst': 'Role Persona: Service Desk Tier 1/2',
        'general_helpdesk': 'Role Persona: General Helpdesk (L1 Support)'
      };
      const badge = document.getElementById('persona-badge');
      if (badge) {
        badge.innerText = roleNames[role] || 'Role Persona: Service Desk';
      }
      // If a ticket is currently loaded, re-analyze to reflect the updated role output immediately
      const title = document.getElementById('input-title').value.trim();
      const desc = document.getElementById('input-desc').value.trim();
      if (title && desc) {
        analyzeCurrentTicket();
      }
    }

    async function loadPreset(presetId) {
      const res = await fetch('/api/presets');
      const data = await res.json();
      const preset = data.presets.find(p => p.id === presetId);
      if (preset) {
        document.getElementById('input-title').value = preset.title;
        document.getElementById('input-desc').value = preset.description;
        document.getElementById('input-apps').value = (preset.apps || []).join(', ');
        document.getElementById('user-role-select').value = preset.role;

        // Clear user context so it is NOT shown or pre-populated for presets
        document.getElementById('usr-name').value = '';
        document.getElementById('usr-empid').value = '';
        document.getElementById('usr-email').value = '';
        document.getElementById('usr-dept').value = '';

        analyzeCurrentTicket();
      }
    }

    async function analyzeCurrentTicket(clarificationText = null) {
      const title = document.getElementById('input-title').value.trim();
      const desc = document.getElementById('input-desc').value.trim();
      const apps = document.getElementById('input-apps').value.split(',').map(s => s.trim()).filter(Boolean);
      const role = document.getElementById('user-role-select').value;

      // Only 4 employee fields: Name, ID, Mail, Department
      const userProfile = {
        name: document.getElementById('usr-name').value.trim(),
        employee_id: document.getElementById('usr-empid').value.trim(),
        email: document.getElementById('usr-email').value.trim(),
        department: document.getElementById('usr-dept').value.trim()
      };

      if (!title || !desc) {
        alert('Please enter a ticket title and description.');
        return;
      }

      document.getElementById('btn-analyze').innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Synthesizing via LLM...';

      try {
        const payload = {
          title,
          description: desc,
          applications: apps,
          user_role: role,
          user_profile: userProfile,
          clarification_response: clarificationText,
          llm_provider: llmConfig.provider,
          api_key: llmConfig.apiKey
        };

        const res = await fetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        renderResults(data);
      } catch (err) {
        alert('Error analyzing ticket: ' + err.message);
      } finally {
        document.getElementById('btn-analyze').innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Generate Response via LLM';
      }
    }

    function setClarification(text) {
      document.getElementById('user-clarification-input').value = text;
    }

    function submitUserClarification() {
      const val = document.getElementById('user-clarification-input').value.trim();
      if (!val) {
        alert('Please select or type a clarifying answer.');
        return;
      }
      analyzeCurrentTicket(val);
    }

    let currentTriageData = null;
    let isEditingDraft = false;

    function showToast(message, type = 'success') {
      const container = document.getElementById('toast-container');
      if (!container) return;
      const toast = document.createElement('div');
      const colors = {
        success: 'bg-emerald-950/95 border-emerald-500/60 text-emerald-100 shadow-emerald-950/50',
        warning: 'bg-amber-950/95 border-amber-500/60 text-amber-100 shadow-amber-950/50',
        error: 'bg-rose-950/95 border-rose-500/60 text-rose-100 shadow-rose-950/50',
        info: 'bg-indigo-950/95 border-indigo-500/60 text-indigo-100 shadow-indigo-950/50'
      };
      const icons = {
        success: 'fa-circle-check text-emerald-400',
        warning: 'fa-triangle-exclamation text-amber-400',
        error: 'fa-circle-xmark text-rose-400',
        info: 'fa-circle-info text-indigo-400'
      };
      toast.className = `flex items-center gap-2.5 px-4 py-3 rounded-xl border shadow-2xl backdrop-blur-md text-xs font-medium transition-all duration-300 transform translate-y-2 opacity-0 pointer-events-auto ${colors[type] || colors.info}`;
      toast.innerHTML = `<i class="fa-solid ${icons[type] || icons.info} text-sm"></i><span>${message}</span>`;
      container.appendChild(toast);
      requestAnimationFrame(() => {
        toast.classList.remove('translate-y-2', 'opacity-0');
      });
      setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
      }, 3500);
    }

    function toggleEditDraft() {
      const viewDiv = document.getElementById('llm-user-reply-text');
      const editContainer = document.getElementById('llm-user-reply-edit-container');
      const editTextarea = document.getElementById('llm-user-reply-edit');
      const btnLabel = document.getElementById('btn-edit-label');

      if (!isEditingDraft) {
        editTextarea.value = viewDiv.innerText;
        viewDiv.classList.add('hidden');
        editContainer.classList.remove('hidden');
        btnLabel.innerText = 'Close Editor';
        isEditingDraft = true;
      } else {
        cancelEditDraft();
      }
    }

    function saveEditDraft() {
      const viewDiv = document.getElementById('llm-user-reply-text');
      const editContainer = document.getElementById('llm-user-reply-edit-container');
      const editTextarea = document.getElementById('llm-user-reply-edit');
      const btnLabel = document.getElementById('btn-edit-label');

      viewDiv.innerText = editTextarea.value;
      viewDiv.classList.remove('hidden');
      editContainer.classList.add('hidden');
      btnLabel.innerText = 'Edit Draft';
      isEditingDraft = false;
      showToast('Analyst draft modifications saved.', 'info');
    }

    function cancelEditDraft() {
      const viewDiv = document.getElementById('llm-user-reply-text');
      const editContainer = document.getElementById('llm-user-reply-edit-container');
      const btnLabel = document.getElementById('btn-edit-label');

      viewDiv.classList.remove('hidden');
      editContainer.classList.add('hidden');
      btnLabel.innerText = 'Edit Draft';
      isEditingDraft = false;
    }

    function copyLLMResponse() {
      const text = document.getElementById('llm-user-reply-text').innerText;
      navigator.clipboard.writeText(text);
      showToast('Resolution text copied to clipboard!', 'success');
    }

    function renderResults(data) {
      currentTriageData = data;
      currentAuditId = data.audit_id;
      currentClassification = data.classification;
      currentDecision = data.decision;

      document.getElementById('results-empty').classList.add('hidden');
      document.getElementById('results-container').classList.remove('hidden');

      // Reset Draft Edit Mode
      cancelEditDraft();

      // Reset Sign-Off and Dispatch Banners
      document.getElementById('dispatch-banner').classList.add('hidden');
      document.getElementById('reject-banner').classList.add('hidden');

      const reviewBadge = document.getElementById('review-status-badge');
      reviewBadge.className = 'text-[10px] px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-300 font-mono border border-amber-500/30 flex items-center gap-1';
      reviewBadge.innerHTML = '<i class="fa-solid fa-hourglass-half"></i> Pending Sign-Off';

      const btnApprove = document.getElementById('btn-approve');
      btnApprove.disabled = false;
      btnApprove.className = 'px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition flex items-center gap-1.5 shadow-md shadow-emerald-900/30';
      btnApprove.innerHTML = '<i class="fa-solid fa-stamp"></i> Approve & Send to User';

      const btnReject = document.getElementById('btn-reject');
      btnReject.disabled = false;
      btnReject.className = 'px-3.5 py-1.5 rounded-lg bg-rose-600/80 hover:bg-rose-600 text-white font-medium transition flex items-center gap-1.5 shadow-md shadow-rose-900/30';
      btnReject.innerHTML = '<i class="fa-solid fa-ban"></i> Reject & Dispatch Tier 3';

      // Synchronize override dropdown defaults to active prediction
      const catSelect = document.getElementById('override-category');
      catSelect.options[0].text = `Keep AI Prediction (${data.classification.category_code})`;
      catSelect.value = '';

      const prioSelect = document.getElementById('override-priority');
      prioSelect.options[0].text = `Keep AI Priority (${data.classification.priority.toUpperCase()})`;
      prioSelect.value = '';

      const decSelect = document.getElementById('override-decision');
      decSelect.options[0].text = `Keep AI Decision (${data.decision.decision})`;
      decSelect.value = '';

      // 1. Decision Banner
      const dec = data.decision;
      const clf = data.classification;
      const banner = document.getElementById('decision-banner');
      const badge = document.getElementById('state-badge');

      document.getElementById('confidence-badge').innerText = `Confidence: ${(dec.confidence_score * 100).toFixed(1)}%`;
      document.getElementById('team-badge').innerText = clf.assigned_team;
      document.getElementById('category-heading').innerText = `${clf.category_code}: ${clf.category_name} (${clf.priority.toUpperCase()} Priority)`;
      document.getElementById('decision-reason').innerText = dec.reason;

      // Reset banner styles
      banner.className = 'border rounded-2xl p-5 space-y-3 shadow-xl transition-all ';
      ['branch-ask', 'branch-escalate'].forEach(b => document.getElementById(b).classList.add('hidden'));

      if (dec.decision === 'FIX') {
        banner.classList.add('bg-emerald-950/30', 'border-emerald-500/40');
        badge.className = 'px-3 py-1 rounded-full text-xs font-bold tracking-wider uppercase bg-emerald-500 text-slate-950';
        badge.innerHTML = '<i class="fa-solid fa-circle-check mr-1"></i> FIX';
        document.getElementById('llm-response-card').classList.remove('hidden');
      } else if (dec.decision === 'ASK') {
        banner.classList.add('bg-amber-950/30', 'border-amber-500/40');
        badge.className = 'px-3 py-1 rounded-full text-xs font-bold tracking-wider uppercase bg-amber-400 text-slate-950';
        badge.innerHTML = '<i class="fa-solid fa-circle-question mr-1"></i> ASK';
        document.getElementById('branch-ask').classList.remove('hidden');
        document.getElementById('ask-question-text').innerText = dec.disambiguating_question || 'Please ask the user for additional diagnostic details.';
      } else {
        banner.classList.add('bg-rose-950/30', 'border-rose-500/40');
        badge.className = 'px-3 py-1 rounded-full text-xs font-bold tracking-wider uppercase bg-rose-500 text-white';
        badge.innerHTML = '<i class="fa-solid fa-triangle-exclamation mr-1"></i> ESCALATE';
        document.getElementById('branch-escalate').classList.remove('hidden');
        document.getElementById('esc-target-team').innerText = dec.target_team || clf.assigned_team;
        document.getElementById('esc-reason-text').innerText = dec.reason;
        
        const missingList = document.getElementById('esc-missing-items');
        missingList.innerHTML = (dec.missing_information || ['Diagnostic error logs', 'Screenshots']).map(m => `<li>${m}</li>`).join('');
      }

      // 2. Render LLM Generated Response
      const userReply = data.user_facing_response || "Response generated.";
      document.getElementById('llm-user-reply-text').innerText = userReply;
      document.getElementById('llm-root-cause-text').innerText = data.root_cause_explanation || "Identified root cause pattern.";
      
      const nearestId = data.nearest_case_used || (data.similar_tickets && data.similar_tickets[0] ? data.similar_tickets[0].record_id : 'INC-REF');
      const nearestScore = (data.similar_tickets && data.similar_tickets[0]) ? (data.similar_tickets[0].similarity_score * 100).toFixed(1) : '94.0';
      document.getElementById('nearest-case-badge').innerText = `Nearest Solved: ${nearestId} (${nearestScore}% match)`;

      // Persona badge update
      const personaTitle = data.persona_mode || 'Service Desk Tier 1/2';
      document.getElementById('persona-badge').innerText = `Role Persona: ${personaTitle}`;

      if (data.llm_trace) {
        document.getElementById('trace-provider').innerText = data.llm_trace.provider || 'Grounded Engine';
        document.getElementById('trace-latency').innerText = `${data.llm_trace.latency_ms || 15}ms`;
        document.getElementById('trace-prompt').innerText = data.llm_trace.prompt || 'No prompt recorded.';
      }

      // Attribution tokens
      const attr = clf.attribution_tokens || [];
      document.getElementById('attribution-tokens').innerHTML = attr.map(t => 
        `<span class="px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 font-mono text-[10px]">${t}</span>`
      ).join('') || '<span class="text-slate-500">Standard taxonomy keywords</span>';

      // 3. Similar tickets (Nearest solved cases)
      renderSimilarTickets(data.similar_tickets);
    }

    async function applyHumanAction(action) {
      if (!currentAuditId) {
        showToast('Please analyze a ticket first or select a preset to review.', 'warning');
        return;
      }

      const notes = document.getElementById('analyst-notes-input').value.trim();
      const editedText = isEditingDraft ? document.getElementById('llm-user-reply-edit').value : document.getElementById('llm-user-reply-text').innerText;
      
      const empName = document.getElementById('usr-name').value.trim() || 'Employee';
      const empEmail = document.getElementById('usr-email').value.trim() || 'user@corplabs.com';
      const currentRole = document.getElementById('user-role-select').options[document.getElementById('user-role-select').selectedIndex].text;

      const payload = {
        audit_id: currentAuditId,
        action: action,
        analyst_notes: notes,
        edited_text: editedText,
        title: document.getElementById('input-title').value.trim(),
        description: document.getElementById('input-desc').value.trim(),
        user_role: document.getElementById('user-role-select').value,
        user_profile: {
          name: empName,
          employee_id: document.getElementById('usr-empid').value.trim(),
          email: empEmail,
          department: document.getElementById('usr-dept').value.trim()
        }
      };

      try {
        const res = await fetch('/api/human-intervention', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const d = await res.json();

        if (action === 'approve') {
          // Update status badge
          const reviewBadge = document.getElementById('review-status-badge');
          reviewBadge.className = 'text-[10px] px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-mono border border-emerald-500/40 flex items-center gap-1';
          reviewBadge.innerHTML = '<i class="fa-solid fa-circle-check"></i> Approved & Dispatched';

          // Disable approve button
          const btnApprove = document.getElementById('btn-approve');
          btnApprove.disabled = true;
          btnApprove.className = 'px-3.5 py-1.5 rounded-lg bg-emerald-700 text-emerald-200 cursor-not-allowed font-medium transition flex items-center gap-1.5 opacity-90';
          btnApprove.innerHTML = '<i class="fa-solid fa-check-double"></i> Dispatched to Employee ✓';

          // Show live dispatch banner inside LLM response card
          const banner = document.getElementById('dispatch-banner');
          document.getElementById('dispatch-recipient').innerText = `${empName} (${empEmail})`;
          document.getElementById('dispatch-role').innerText = currentRole;
          document.getElementById('dispatch-timestamp').innerText = new Date().toLocaleTimeString();
          banner.classList.remove('hidden');
          document.getElementById('reject-banner').classList.add('hidden');

          showToast(`Resolution approved! Dispatched to ${empName} (${empEmail})`, 'success');
        } else if (action === 'reject') {
          // Update status badge
          const reviewBadge = document.getElementById('review-status-badge');
          reviewBadge.className = 'text-[10px] px-2.5 py-0.5 rounded-full bg-rose-500/20 text-rose-300 font-mono border border-rose-500/40 flex items-center gap-1';
          reviewBadge.innerHTML = '<i class="fa-solid fa-ban"></i> Rejected & Escalated';

          // Show reject banner
          const rejBanner = document.getElementById('reject-banner');
          document.getElementById('reject-reason-text').innerText = notes ? `Analyst Reason: ${notes}` : 'Ticket rejected during frontline review. Escalated to Tier 3 Specialist Operations.';
          rejBanner.classList.remove('hidden');
          document.getElementById('dispatch-banner').classList.add('hidden');

          // Switch decision banner to ESCALATE
          const banner = document.getElementById('decision-banner');
          banner.className = 'border rounded-2xl p-5 space-y-3 shadow-xl transition-all bg-rose-950/30 border-rose-500/40';
          const badge = document.getElementById('state-badge');
          badge.className = 'px-3 py-1 rounded-full text-xs font-bold tracking-wider uppercase bg-rose-500 text-white';
          badge.innerHTML = '<i class="fa-solid fa-triangle-exclamation mr-1"></i> ESCALATE (Analyst Rejected)';

          showToast('Ticket rejected by analyst. Escalated directly to Tier 3 Engineering.', 'warning');
        }
      } catch (err) {
        showToast('Error recording human action: ' + err.message, 'error');
      }
    }

    async function applyOverrides() {
      if (!currentAuditId) {
        showToast('Please analyze a ticket first or select a preset to override.', 'warning');
        return;
      }

      const cat = document.getElementById('override-category').value;
      const prio = document.getElementById('override-priority').value;
      const dec = document.getElementById('override-decision').value;
      const notes = document.getElementById('analyst-notes-input').value.trim();

      const overrides = {};
      if (cat) overrides.category = cat;
      if (prio) overrides.priority = prio;
      if (dec) overrides.decision = dec;

      if (Object.keys(overrides).length === 0) {
        showToast('Please select at least one override dropdown option.', 'info');
        return;
      }

      const btn = document.getElementById('btn-apply-overrides');
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Applying...';

      const payload = {
        audit_id: currentAuditId,
        action: 'override',
        analyst_notes: notes || 'Analyst applied manual triage override.',
        overrides: overrides,
        title: document.getElementById('input-title').value.trim(),
        description: document.getElementById('input-desc').value.trim(),
        user_role: document.getElementById('user-role-select').value,
        user_profile: {
          name: document.getElementById('usr-name').value.trim(),
          employee_id: document.getElementById('usr-empid').value.trim(),
          email: document.getElementById('usr-email').value.trim(),
          department: document.getElementById('usr-dept').value.trim()
        }
      };

      try {
        const res = await fetch('/api/human-intervention', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();

        // 1. If backend recalculated resolution based on category override, update LLM response & matches
        if (data.recalculated) {
          const rec = data.recalculated;
          if (rec.user_facing_response) {
            document.getElementById('llm-user-reply-text').innerText = rec.user_facing_response;
          }
          if (rec.root_cause_explanation) {
            document.getElementById('llm-root-cause-text').innerText = rec.root_cause_explanation;
          }
          if (rec.nearest_case_used) {
            document.getElementById('nearest-case-badge').innerText = `Nearest Solved: ${rec.nearest_case_used} (Overridden)`;
          }
          if (rec.similar_tickets) {
            renderSimilarTickets(rec.similar_tickets);
          }
        }

        // 2. Update category heading
        if (cat) {
          const catLabel = document.getElementById('override-category').selectedOptions[0].text;
          document.getElementById('category-heading').innerHTML = `<span class="text-indigo-400 font-bold">[Analyst Override]</span> ${catLabel}`;
        }

        // 3. Update priority
        if (prio) {
          document.getElementById('confidence-badge').innerText = `Priority: ${prio.toUpperCase()} (Analyst Set)`;
        }

        // 4. Update Decision State if overridden
        if (dec) {
          const banner = document.getElementById('decision-banner');
          const badge = document.getElementById('state-badge');
          ['branch-ask', 'branch-escalate'].forEach(b => document.getElementById(b).classList.add('hidden'));

          if (dec === 'FIX') {
            banner.className = 'border rounded-2xl p-5 space-y-3 shadow-xl transition-all bg-emerald-950/30 border-emerald-500/40';
            badge.className = 'px-3 py-1 rounded-full text-xs font-bold tracking-wider uppercase bg-emerald-500 text-slate-950';
            badge.innerHTML = '<i class="fa-solid fa-circle-check mr-1"></i> FIX (Overridden)';
            document.getElementById('llm-response-card').classList.remove('hidden');
          } else if (dec === 'ASK') {
            banner.className = 'border rounded-2xl p-5 space-y-3 shadow-xl transition-all bg-amber-950/30 border-amber-500/40';
            badge.className = 'px-3 py-1 rounded-full text-xs font-bold tracking-wider uppercase bg-amber-400 text-slate-950';
            badge.innerHTML = '<i class="fa-solid fa-circle-question mr-1"></i> ASK (Overridden)';
            document.getElementById('branch-ask').classList.remove('hidden');
          } else if (dec === 'ESCALATE') {
            banner.className = 'border rounded-2xl p-5 space-y-3 shadow-xl transition-all bg-rose-950/30 border-rose-500/40';
            badge.className = 'px-3 py-1 rounded-full text-xs font-bold tracking-wider uppercase bg-rose-500 text-white';
            badge.innerHTML = '<i class="fa-solid fa-triangle-exclamation mr-1"></i> ESCALATE (Overridden)';
            document.getElementById('branch-escalate').classList.remove('hidden');
            document.getElementById('esc-target-team').innerText = 'Tier 2/3 Specialist Operations';
            document.getElementById('esc-reason-text').innerText = notes || 'Manual escalation override enforced by service desk analyst.';
          }
        }

        // 5. Update review status badge
        const reviewBadge = document.getElementById('review-status-badge');
        reviewBadge.className = 'text-[10px] px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 font-mono border border-indigo-500/40 flex items-center gap-1';
        reviewBadge.innerHTML = '<i class="fa-solid fa-sliders"></i> Triage Overridden';

        showToast('Overrides applied: Workbench re-grounded in real-time!', 'info');
      } catch (err) {
        showToast('Error applying overrides: ' + err.message, 'error');
      } finally {
        btn.innerHTML = '<i class="fa-solid fa-sliders"></i> Apply Overrides';
      }
    }

    function renderSimilarTickets(tickets) {
      const list = document.getElementById('similar-tickets-list');
      if (!tickets || tickets.length === 0) {
        list.innerHTML = '<p class="text-xs text-slate-500">No matches found.</p>';
        return;
      }

      list.innerHTML = tickets.map((t, idx) => `
        <div class="p-3 rounded-lg border ${idx === 0 ? 'border-emerald-500/40 bg-emerald-950/20' : 'border-slate-800/80 bg-slate-900/60'} hover:border-slate-700 transition space-y-1.5 text-xs">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              ${idx === 0 ? '<span class="px-2 py-0.5 rounded bg-emerald-500 text-slate-950 font-bold text-[10px] uppercase">Primary Nearest Match</span>' : ''}
              <span class="font-mono font-bold text-sky-400">${t.record_id}</span>
              <span class="text-slate-400">·</span>
              <span class="text-slate-300 font-medium">${t.category_name}</span>
            </div>
            <span class="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">${(t.similarity_score * 100).toFixed(1)}% Match</span>
          </div>
          <p class="text-[11px] text-slate-300">${t.title}</p>
          <p class="text-[11px] text-slate-400 italic">Root Cause: ${t.root_cause || '-'}</p>
          <div class="flex items-center justify-between text-[11px] text-slate-500 pt-1">
            <span>${t.match_rationale}</span>
            ${t.is_lookalike_distractor ? '<span class="text-rose-400 font-semibold"><i class="fa-solid fa-triangle-exclamation"></i> Lookalike Warning</span>' : ''}
          </div>
        </div>
      `).join('');
    }

    async function submitFeedback(rating) {
      if (!currentAuditId) return;
      try {
        await fetch('/api/feedback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ audit_id: currentAuditId, rating })
        });
        showToast(`Feedback recorded: Marked as [${rating.toUpperCase()}] in audit trail.`, 'success');
      } catch (err) {
        showToast('Feedback error: ' + err.message, 'error');
      }
    }

    function handleSearchKey(e) {
      if (e.key === 'Enter') {
        executeSearch();
      }
    }

    async function executeSearch() {
      const q = document.getElementById('search-query').value.trim();
      const cat = document.getElementById('search-cat').value;
      const prio = document.getElementById('search-priority').value;

      const tbody = document.getElementById('search-results-tbody');
      tbody.innerHTML = '<tr><td colspan="6" class="py-6 text-center text-slate-500"><i class="fa-solid fa-spinner fa-spin mr-2"></i>Searching 745 incidents...</td></tr>';

      const url = `/api/search?limit=50${q ? `&query=${encodeURIComponent(q)}` : ''}${cat ? `&category=${cat}` : ''}${prio ? `&priority=${prio}` : ''}`;
      const res = await fetch(url);
      const data = await res.json();

      document.getElementById('search-total-badge').innerText = `Returned ${data.total_returned} Tickets`;

      if (!data.tickets || data.tickets.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="py-6 text-center text-slate-500">No matching tickets found. Try broader keywords.</td></tr>';
        return;
      }

      tbody.innerHTML = data.tickets.map(t => `
        <tr class="hover:bg-slate-900/50 transition">
          <td class="py-2.5 px-3 font-mono font-bold text-sky-400">${t.record_id}</td>
          <td class="py-2.5 px-3"><span class="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-medium">${t.category_code}</span></td>
          <td class="py-2.5 px-3 uppercase text-[11px] font-semibold ${t.priority === 'high' ? 'text-rose-400' : 'text-slate-400'}">${t.priority}</td>
          <td class="py-2.5 px-3 max-w-xs truncate">${t.title}</td>
          <td class="py-2.5 px-3 max-w-sm truncate text-slate-400">${t.root_cause || '-'}</td>
          <td class="py-2.5 px-3">
            <button onclick="loadTicketIntoWorkbench('${t.record_id}')" class="px-2 py-1 rounded bg-sky-600/20 hover:bg-sky-600/40 text-sky-400 text-[11px] font-medium transition">Load Case</button>
          </td>
        </tr>
      `).join('');
    }

    async function loadTicketIntoWorkbench(ticketId) {
      const res = await fetch(`/api/search?query=${ticketId}&limit=1`);
      const data = await res.json();
      if (data.tickets && data.tickets.length > 0) {
        const t = data.tickets[0];
        document.getElementById('input-title').value = t.title;
        document.getElementById('input-desc').value = t.description;
        document.getElementById('input-apps').value = (t.applications || []).join(', ');

        // Clear user profile fields when opening previous cases
        document.getElementById('usr-name').value = '';
        document.getElementById('usr-empid').value = '';
        document.getElementById('usr-email').value = '';
        document.getElementById('usr-dept').value = '';

        switchTab('workbench');
        analyzeCurrentTicket();
      }
    }

    async function loadAuditLogs() {
      const container = document.getElementById('audit-logs-container');
      container.innerHTML = '<div class="py-6 text-center text-xs text-slate-500"><i class="fa-solid fa-spinner fa-spin mr-2"></i>Loading logs...</div>';
      
      const res = await fetch('/api/audit-logs');
      const data = await res.json();

      if (!data.logs || data.logs.length === 0) {
        container.innerHTML = '<div class="py-6 text-center text-xs text-slate-500">No audit records logged yet. Run a triage in the workbench to create records.</div>';
        return;
      }

      container.innerHTML = data.logs.map(log => `
        <div class="p-4 rounded-xl border border-slate-800 bg-slate-950 text-xs space-y-2.5">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="font-mono font-bold text-sky-400">${log.audit_id}</span>
              <span class="text-slate-500">·</span>
              <span class="text-slate-400">${new Date(log.timestamp).toLocaleString()}</span>
              <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase ${log.decision.state === 'FIX' ? 'bg-emerald-500/20 text-emerald-400' : (log.decision.state === 'ASK' ? 'bg-amber-500/20 text-amber-400' : 'bg-rose-500/20 text-rose-400')}">${log.decision.state}</span>
              ${log.human_intervention && log.human_intervention.approved ? '<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-[10px] font-bold"><i class="fa-solid fa-check-double mr-1"></i>Human Approved</span>' : ''}
            </div>
            ${log.feedback ? `<span class="px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 text-[11px]"><i class="fa-solid fa-thumbs-up mr-1"></i>Rated: ${log.feedback.rating}</span>` : '<span class="text-slate-500 text-[11px]">Unreviewed</span>'}
          </div>
          <p class="text-slate-300 font-medium">Input: "${log.input.redacted_title}"</p>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px] text-slate-400 pt-1 border-t border-slate-800/60">
            <div><span class="text-slate-500">Category:</span> ${log.classification.category_code}</div>
            <div><span class="text-slate-500">Confidence:</span> ${(log.classification.confidence * 100).toFixed(1)}%</div>
            <div><span class="text-slate-500">Role:</span> ${log.user_role}</div>
            <div><span class="text-slate-500">LLM Provider:</span> ${log.llm_trace ? log.llm_trace.provider : 'Grounded'}</div>
          </div>
          ${log.user_profile && log.user_profile.name ? `
            <div class="text-[11px] text-slate-500 bg-slate-900 p-2 rounded border border-slate-800/60">
              <span class="text-slate-400 font-medium">Employee:</span> ${log.user_profile.name} (${log.user_profile.employee_id || 'N/A'}) · Dept: ${log.user_profile.department || 'N/A'}
            </div>
          ` : ''}
          ${log.human_intervention && log.human_intervention.analyst_notes ? `
            <div class="text-[11px] text-indigo-300 bg-indigo-500/10 p-2 rounded border border-indigo-500/20">
              <span class="font-bold">Analyst Intervention Note:</span> ${log.human_intervention.analyst_notes}
            </div>
          ` : ''}
        </div>
      `).join('');
    }
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
