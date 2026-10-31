import os
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

class AuditLedger:
    """
    Immutable, append-only audit trail logger (FR-08) and analyst feedback / human intervention recorder.
    """
    
    def __init__(self, log_path: str):
        self.log_path = log_path
        os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
        if not os.path.exists(self.log_path):
            with open(self.log_path, "w", encoding="utf-8") as f:
                pass
                
    def log_analysis(
        self,
        raw_title: str,
        redacted_title: str,
        redacted_desc: str,
        pii_detections: List[Dict[str, Any]],
        classification: Dict[str, Any],
        decision: Dict[str, Any],
        verified_steps: List[Dict[str, Any]],
        similar_tickets: List[Dict[str, Any]],
        user_role: str,
        rbac_info: Dict[str, Any],
        user_profile: Optional[Dict[str, Any]] = None,
        llm_trace: Optional[Dict[str, Any]] = None
    ) -> str:
        audit_id = f"AUD-{uuid.uuid4().hex[:10].upper()}"
        now = datetime.now(timezone.utc).isoformat()
        
        record = {
            "audit_id": audit_id,
            "timestamp": now,
            "user_role": user_role,
            "rbac": rbac_info,
            "user_profile": user_profile or {},
            "input": {
                "raw_title": raw_title,
                "redacted_title": redacted_title,
                "redacted_description": redacted_desc,
                "pii_detected_count": len(pii_detections),
                "pii_entities": [d.get("entity_type") for d in pii_detections]
            },
            "classification": {
                "category_code": classification.get("category_code"),
                "category_name": classification.get("category_name"),
                "confidence": classification.get("category_confidence"),
                "priority": classification.get("priority"),
                "assigned_team": classification.get("assigned_team")
            },
            "decision": {
                "state": decision.get("decision"),
                "confidence": decision.get("confidence_score"),
                "reason": decision.get("reason"),
                "disambiguating_question": decision.get("disambiguating_question"),
                "target_team": decision.get("target_team")
            },
            "evidence": {
                "top_similar_ids": [t["record_id"] for t in similar_tickets[:3]],
                "verified_steps_count": len(verified_steps),
                "citations": [s.get("source_ticket_id") for s in verified_steps]
            },
            "llm_trace": {
                "provider": llm_trace.get("provider") if llm_trace else "None",
                "model": llm_trace.get("model") if llm_trace else "None",
                "latency_ms": llm_trace.get("latency_ms") if llm_trace else 0,
                "is_live_llm": llm_trace.get("is_live_llm") if llm_trace else False
            },
            "human_intervention": {
                "approved": False,
                "status": "pending_analyst_review",
                "analyst_role": user_role,
                "overrides": None,
                "edited_steps": None,
                "analyst_notes": ""
            },
            "feedback": None
        }
        
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
            
        return audit_id

    def record_human_intervention(
        self,
        audit_id: str,
        action: str,  # 'approve', 'reject', 'override'
        analyst_notes: str = "",
        edited_steps: Optional[List[Dict[str, Any]]] = None,
        overrides: Optional[Dict[str, Any]] = None,
        edited_text: Optional[str] = None
    ) -> bool:
        """Records analyst modifications, category/priority overrides, and sign-offs."""
        if not os.path.exists(self.log_path):
            return False
            
        lines = []
        updated = False
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                if data.get("audit_id") == audit_id:
                    data["human_intervention"] = {
                        "approved": (action == "approve"),
                        "status": f"human_{action}d",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "analyst_notes": analyst_notes,
                        "edited_steps": edited_steps,
                        "edited_text": edited_text,
                        "overrides": overrides
                    }
                    updated = True
                lines.append(json.dumps(data))
                
        if updated:
            with open(self.log_path, "w", encoding="utf-8") as f:
                for l in lines:
                    f.write(l + "\n")
                    
        return updated
        
    def record_feedback(
        self,
        audit_id: str,
        rating: str,
        analyst_notes: str = "",
        resolution_action_taken: str = ""
    ) -> bool:
        if not os.path.exists(self.log_path):
            return False
            
        lines = []
        updated = False
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                if data.get("audit_id") == audit_id:
                    data["feedback"] = {
                        "rating": rating,
                        "notes": analyst_notes,
                        "action_taken": resolution_action_taken,
                        "reviewed_at": datetime.now(timezone.utc).isoformat()
                    }
                    updated = True
                lines.append(json.dumps(data))
                
        if updated:
            with open(self.log_path, "w", encoding="utf-8") as f:
                for l in lines:
                    f.write(l + "\n")
                    
        return updated
        
    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not os.path.exists(self.log_path):
            return []
        records = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records[::-1][:limit]
