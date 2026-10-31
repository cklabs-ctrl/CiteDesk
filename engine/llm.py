import os
import json
import time
from typing import Dict, Any, List, Optional

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

ROLE_PERSONAS = {
    "identity_analyst": {
        "title": "Senior Identity & Security Operations Lead (Privileged Tier 3)",
        "tone": "Deeply technical, security-conscious, authoritative, and audit-compliant.",
        "focus": (
            "Provide full technical diagnosis including directory event codes (e.g. Event ID 4740), "
            "domain controller authentication logs, token revocation, BitLocker TPM protector state, "
            "and privileged administrative console actions."
        ),
        "guidelines": (
            "- Include exact technical root cause, error codes, and directory attributes.\n"
            "- Specify privileged admin actions (ADUC, PowerShell, Intune admin center, SSO session revocation).\n"
            "- Highlight security risk mitigation to prevent recurrence."
        )
    },
    "service_desk_analyst": {
        "title": "IT Service Desk Tier 1/2 Specialist",
        "tone": "Professional, operational, structured, and solution-oriented.",
        "focus": (
            "Provide practical operational triage, verifying client device symptoms, "
            "standard ITSM runbook steps, and customer-ready resolution messaging."
        ),
        "guidelines": (
            "- Balance technical accuracy with operational clarity.\n"
            "- Provide clear step-by-step instructions suitable for an operational service desk agent.\n"
            "- Identify if device cleanup or ticket handoff is needed."
        )
    },
    "general_helpdesk": {
        "title": "Frontline L1 Helpdesk & Customer Support",
        "tone": "Empathetic, clear, non-technical plain language, and customer-friendly.",
        "focus": (
            "Focus on immediate end-user guidance and first-contact resolution without overwhelming "
            "the user with infrastructure jargon. For privileged actions (like AD unlocks or TPM resets), "
            "instruct the user on client-side cleanup while coordinating handover."
        ),
        "guidelines": (
            "- Avoid confusing error codes like 0xC0000234 or Kerberos internals.\n"
            "- Use simple, bulleted instructions that any employee can follow on their laptop or phone.\n"
            "- Clearly state when a privileged team is performing the background unlock."
        )
    }
}

class LLMService:
    """
    LLM Synthesis Engine for CiteDesk:
    Synthesizes the complete response to the user's query directly based on the
    nearest solved historical case, adapting tone, depth, and actions based on
    the active Model Role Persona.
    """

    @classmethod
    def get_system_prompt(cls, role_key: str) -> str:
        persona = ROLE_PERSONAS.get(role_key, ROLE_PERSONAS["service_desk_analyst"])
        return f"""You are CiteDesk, an enterprise IT Service Desk Resolution AI.
YOUR ASSIGNED PERSONA: {persona['title']}
TONE & STYLE: {persona['tone']}
OPERATIONAL FOCUS: {persona['focus']}

PERSONA GUIDELINES:
{persona['guidelines']}

CRITICAL RULES:
1. Base your response strictly on the NEAREST SOLVED CASE provided in the context.
2. Address the user directly by name (if provided).
3. Acknowledge their specific symptoms and affected application.
4. Adapt your explanation and steps to your active persona ({persona['title']}).
5. If the state is 'ASK', formulate the single best clarifying question to separate the competing causes.
6. If the state is 'ESCALATE', explain politely that the issue is being routed to the specialist team.

Output ONLY valid JSON matching this schema:
{{
  "user_facing_response": "Full response tailored to your assigned persona...",
  "nearest_case_used": "INC-XXXX-XXXX",
  "root_cause_explanation": "Summary of technical root cause from nearest solved case...",
  "clarifying_question_for_user": "Disambiguating question if in ASK state...",
  "confidence_explanation": "One line explaining why this nearest case solves the query...",
  "persona_mode": "{persona['title']}"
}}"""

    @classmethod
    def generate_response(
        cls,
        ticket_title: str,
        ticket_desc: str,
        similar_tickets: List[Dict[str, Any]],
        user_profile: Optional[Dict[str, Any]] = None,
        user_role: str = "service_desk_analyst",
        decision_state: str = "FIX",
        api_key: Optional[str] = None,
        provider: str = "gemini",
        model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        resolved_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )

        user_name = (user_profile or {}).get("name", "User")
        emp_id = (user_profile or {}).get("employee_id", "")
        email = (user_profile or {}).get("email", "")
        dept = (user_profile or {}).get("department", "")
        
        persona = ROLE_PERSONAS.get(user_role, ROLE_PERSONAS["service_desk_analyst"])
        system_prompt = cls.get_system_prompt(user_role)
        
        # Nearest solved case
        top_match = similar_tickets[0] if similar_tickets else {}
        nearest_id = top_match.get("record_id", "N/A")
        nearest_title = top_match.get("title", "")
        nearest_cause = top_match.get("root_cause", "")
        nearest_res = "\n".join([f"- {s}" for s in top_match.get("resolution_steps", [])])
        
        user_prompt = (
            f"ACTIVE ANALYST ROLE: {persona['title']}\n"
            f"USER QUERY DETAILS:\n"
            f"User: {user_name} (ID: {emp_id}, Email: {email}, Dept: {dept})\n"
            f"Subject: {ticket_title}\n"
            f"Symptom Description: {ticket_desc}\n"
            f"Triage Decision: {decision_state}\n\n"
            f"NEAREST SOLVED HISTORICAL INCIDENT:\n"
            f"Incident ID: {nearest_id}\n"
            f"Historical Problem: {nearest_title}\n"
            f"Confirmed Root Cause: {nearest_cause}\n"
            f"Resolution Executed in That Solved Case:\n{nearest_res}\n\n"
            f"Formulate the resolution response tailored to your persona in the required JSON format."
        )
        
        start_time = time.time()
        
        # 1. LIVE GEMINI CALL
        if resolved_key and (provider == "gemini" or resolved_key.startswith("AIza")):
            candidate_models = [model_name] if model_name else ["gemini-3.8-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
            for model_to_try in candidate_models:
                try:
                    res = cls._call_gemini_api(resolved_key, user_prompt, model_to_try, system_prompt)
                    latency_ms = round((time.time() - start_time) * 1000, 1)
                    return {
                        "provider": "Google Gemini",
                        "model": model_to_try,
                        "latency_ms": latency_ms,
                        "is_live_llm": True,
                        "user_facing_response": res.get("user_facing_response", ""),
                        "root_cause_explanation": res.get("root_cause_explanation", nearest_cause),
                        "nearest_case_used": nearest_id,
                        "clarifying_question_for_user": res.get("clarifying_question_for_user", ""),
                        "confidence_explanation": res.get("confidence_explanation", ""),
                        "persona_mode": persona["title"],
                        "prompt": user_prompt,
                        "system_prompt": system_prompt,
                        "raw_response": res
                    }
                except Exception as e:
                    print(f"Gemini API error with {model_to_try}: {e}")

        # 2. LIVE OPENAI CALL
        if resolved_key and provider == "openai":
            try:
                model = model_name or "gpt-4o-mini"
                res = cls._call_openai_api(resolved_key, user_prompt, model, system_prompt)
                latency_ms = round((time.time() - start_time) * 1000, 1)
                return {
                    "provider": "OpenAI",
                    "model": model,
                    "latency_ms": latency_ms,
                    "is_live_llm": True,
                    "user_facing_response": res.get("user_facing_response", ""),
                    "root_cause_explanation": res.get("root_cause_explanation", nearest_cause),
                    "nearest_case_used": nearest_id,
                    "clarifying_question_for_user": res.get("clarifying_question_for_user", ""),
                    "confidence_explanation": res.get("confidence_explanation", ""),
                    "persona_mode": persona["title"],
                    "prompt": user_prompt,
                    "system_prompt": system_prompt,
                    "raw_response": res
                }
            except Exception as e:
                print(f"OpenAI API error: {e}. Using grounded reference engine.")

        # 3. DETERMINISTIC SYNTHESIS ENGINE (Local Persona-Tailored Reference)
        latency_ms = round((time.time() - start_time) * 1000, 1)
        res_text = cls._synthesize_persona_response(
            ticket_title=ticket_title,
            user_name=user_name,
            top_match=top_match,
            decision_state=decision_state,
            user_role=user_role
        )
        
        return {
            "provider": "CiteDesk Grounded LLM Engine",
            "model": "citedesk-grounded-v2",
            "latency_ms": latency_ms,
            "is_live_llm": False,
            "user_facing_response": res_text,
            "root_cause_explanation": nearest_cause,
            "nearest_case_used": nearest_id,
            "clarifying_question_for_user": "Does this disconnect occur while connected over GlobalProtect VPN, or directly on the Corporate Wi-Fi network?",
            "confidence_explanation": f"Formulated based on nearest solved incident {nearest_id} with {persona['title']} perspective.",
            "persona_mode": persona["title"],
            "prompt": user_prompt,
            "system_prompt": system_prompt,
            "raw_response": {
                "user_facing_response": res_text,
                "nearest_case_used": nearest_id,
                "root_cause_explanation": nearest_cause,
                "persona_mode": persona["title"]
            }
        }

    @classmethod
    def _synthesize_persona_response(
        cls,
        ticket_title: str,
        user_name: str,
        top_match: Dict[str, Any],
        decision_state: str,
        user_role: str
    ) -> str:
        nearest_id = top_match.get("record_id", "INC-REF")
        category = top_match.get("category_name", "IT Support Incident")
        root_cause = top_match.get("root_cause", "Technical issue identified in historical patterns.")
        steps = top_match.get("resolution_steps", [])
        
        first_name = user_name.strip().split()[0] if user_name and user_name.strip().lower() != "user" else ""
        greeting = f"Hello {first_name}," if first_name else "Hello,"
        
        if decision_state == "FIX":
            if user_role == "identity_analyst":
                # Deep technical privileged output
                msg = (
                    f"PRIVILEGED IDENTITY & SECURITY RESOLUTION DISPATCH\n"
                    f"Analyst Persona: Identity & Security Operations Lead (Tier 3)\n"
                    f"Incident Reference: {nearest_id} | Category: {category}\n\n"
                    f"{greeting}\n\n"
                    f"Technical Assessment for '{ticket_title}':\n"
                    f"• Root Cause Analysis: {root_cause}\n"
                    f"• Directory Status: Active Directory lockout event confirmed. Stale token propagation on endpoint identified.\n\n"
                    f"Privileged Administrative Execution Plan:\n"
                )
                for s in steps:
                    msg += f"[EXEC] {s}\n"
                msg += (
                    f"\nSecurity Posture Verification: Stale session tokens revoked in SSO IdP. "
                    f"Identity team monitoring 30-minute re-lock threshold."
                )
                return msg
            elif user_role == "general_helpdesk":
                # Simple, customer-friendly plain language output
                msg = (
                    f"FRONTLINE SUPPORT GUIDANCE\n"
                    f"Analyst Persona: General Helpdesk / L1 Customer Support\n\n"
                    f"{greeting}\n\n"
                    f"We understand you are having trouble signing in after your password reset.\n\n"
                    f"What is happening:\n"
                    f"Your phone or laptop is still trying to log in using your old password in the background, which temporarily locked your account.\n\n"
                    f"What we have done & your next steps:\n"
                    f"1. We have unlocked your account in the system.\n"
                    f"2. Please open your Mail app and browser on your phone, remove your corporate email account, and add it back with your new password.\n"
                    f"3. Sign in to the corporate portal on your computer to confirm access.\n\n"
                    f"If you need any assistance with your phone settings, please reply to this message and we will guide you!"
                )
                return msg
            else:
                # Standard service desk analyst output
                msg = (
                    f"SERVICE DESK OPERATIONAL RESOLUTION\n"
                    f"Analyst Persona: IT Service Desk Tier 1/2 Specialist\n\n"
                    f"{greeting}\n\n"
                    f"Thank you for contacting the IT Service Desk regarding '{ticket_title}'.\n\n"
                    f"Based on nearest solved incident {nearest_id} ({category}), we diagnosed the issue:\n"
                    f"• Confirmed Root Cause: {root_cause}\n\n"
                    f"Standard Resolution Actions Executed:\n"
                )
                for s in steps:
                    msg += f"• {s}\n"
                msg += (
                    f"\nPlease verify your sign-in now. "
                    f"If the issue persists, reply directly to this ticket."
                )
                return msg
        elif decision_state == "ASK":
            if user_role == "identity_analyst":
                return (
                    f"SECURITY INVESTIGATION - AMBIGUOUS AUTHENTICATION EVENT\n"
                    f"Analyst Persona: Identity & Security Operations Lead\n\n"
                    f"{greeting}\n\n"
                    f"Diagnostics on incident '{ticket_title}' indicate multiple competing failure mechanisms:\n"
                    f"👉 Question: Are you receiving an explicit 'Account Locked' error on the directory domain controller, or are you trapped in continuous SAML/MFA browser redirect loops?\n\n"
                    f"Awaiting telemetry confirmation before initiating credential reissue."
                )
            else:
                return (
                    f"{greeting}\n\n"
                    f"Thank you for contacting IT Support regarding '{ticket_title}'.\n\n"
                    f"We are actively investigating the issue, but to apply the exact fix for your situation, we need a quick clarification:\n"
                    f"👉 Does this disconnect occur while connected over GlobalProtect VPN, or directly on the Corporate Wi-Fi network?\n\n"
                    f"Once you reply with this detail, we will immediately initiate the fix."
                )
        else:
            return (
                f"{greeting}\n\n"
                f"Thank you for reporting '{ticket_title}'. This incident involves an out-of-distribution system event. "
                f"It has been escalated directly to our Tier 2/3 Specialist Operations Team for prioritized manual remediation."
            )

    @classmethod
    def _call_gemini_api(cls, api_key: str, prompt: str, model: str, system_prompt: str) -> Dict[str, Any]:
        if GENAI_AVAILABLE:
            try:
                client = genai.Client(api_key=api_key)
                cfg = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                    system_instruction=system_prompt
                )
                resp = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=cfg
                )
                return json.loads(resp.text)
            except Exception as e:
                print(f"google.genai SDK call error: {e}. Trying direct REST API...")

        import urllib.request
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": f"{system_prompt}\n\n{prompt}"}]}],
            "generationConfig": {"response_mime_type": "application/json", "temperature": 0.2}
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)

    @classmethod
    def _call_openai_api(cls, api_key: str, prompt: str, model: str, system_prompt: str) -> Dict[str, Any]:
        import urllib.request
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
