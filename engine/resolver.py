from typing import Dict, Any, List, Optional
from .llm import LLMService

class FixResolver:
    """
    Synthesizes the resolution response based on the nearest solved case using LLMService,
    actively shaped by the assigned Model Role Persona.
    """
    
    @classmethod
    def build_resolution(
        cls,
        decision_info: Dict[str, Any],
        similar_tickets: List[Dict[str, Any]],
        ticket_title: str = "",
        ticket_desc: str = "",
        user_profile: Optional[Dict[str, Any]] = None,
        user_role: str = "service_desk_analyst",
        api_key: Optional[str] = None,
        llm_provider: str = "gemini",
        llm_model: Optional[str] = None
    ) -> Dict[str, Any]:
        decision_state = decision_info.get("decision", "FIX")
        top_ticket = similar_tickets[0] if similar_tickets else {}
        
        # Synthesize response via LLM based on the nearest solved case and active role persona
        llm_res = LLMService.generate_response(
            ticket_title=ticket_title or top_ticket.get("title", ""),
            ticket_desc=ticket_desc or top_ticket.get("description", ""),
            similar_tickets=similar_tickets,
            user_profile=user_profile,
            user_role=user_role,
            decision_state=decision_state,
            api_key=api_key,
            provider=llm_provider,
            model_name=llm_model
        )
        
        return {
            "has_fix": decision_state == "FIX",
            "user_facing_response": llm_res.get("user_facing_response", ""),
            "root_cause_explanation": llm_res.get("root_cause_explanation", top_ticket.get("root_cause", "")),
            "nearest_case_used": top_ticket.get("record_id", "INC-REF"),
            "persona_mode": llm_res.get("persona_mode", ""),
            "llm_trace": {
                "provider": llm_res.get("provider"),
                "model": llm_res.get("model"),
                "latency_ms": llm_res.get("latency_ms"),
                "is_live_llm": llm_res.get("is_live_llm"),
                "system_prompt": llm_res.get("system_prompt"),
                "prompt": llm_res.get("prompt"),
                "raw_response": llm_res.get("raw_response")
            }
        }
