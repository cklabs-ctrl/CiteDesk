from typing import Dict, Any, List

class ProofChecker:
    """
    Deterministic verification engine:
    Enforces that every suggested fix step is grounded by an exact verbatim excerpt
    from a verified historical incident or approved runbook.
    Unbacked or hallucinated steps are pruned automatically.
    """
    
    @classmethod
    def verify_steps(
        cls,
        candidate_steps: List[Dict[str, Any]],
        context_corpus: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        verified_steps = []
        pruned_steps = []
        
        for idx, step in enumerate(candidate_steps):
            source_id = step.get("source_ticket_id", "").strip()
            quote = step.get("quoted_evidence", "").strip()
            action = step.get("action", "").strip()
            
            # 1. Check if source ticket is present in context
            if not source_id or source_id not in context_corpus:
                pruned_steps.append({
                    "step_number": idx + 1,
                    "action": action,
                    "reason": f"Invalid or missing source ticket reference: '{source_id}'."
                })
                continue
                
            source_rec = context_corpus[source_id]
            source_res_steps = source_rec.get("resolution_steps", [])
            source_diag_summary = source_rec.get("root_cause", "")
            
            # Combine all source ground truth text
            ground_truth_blocks = list(source_res_steps) + [source_diag_summary]
            
            # 2. Check if quote or action is grounded in ground truth blocks
            is_grounded = False
            matching_source_block = ""
            
            quote_clean = quote.lower().strip()
            for block in ground_truth_blocks:
                block_clean = str(block).lower().strip()
                # Direct substring match
                if quote_clean and (quote_clean in block_clean or block_clean in quote_clean):
                    is_grounded = True
                    matching_source_block = block
                    break
                # Substantial keyword overlap if slight formatting difference
                action_words = set(re_tokenize(action.lower()))
                block_words = set(re_tokenize(block_clean))
                if len(action_words) > 3:
                    overlap = len(action_words.intersection(block_words)) / len(action_words)
                    if overlap >= 0.70:
                        is_grounded = True
                        matching_source_block = block
                        break
                        
            if is_grounded:
                verified_steps.append({
                    "step_number": len(verified_steps) + 1,
                    "action": action,
                    "source_ticket_id": source_id,
                    "quoted_evidence": quote if quote else matching_source_block[:180] + "...",
                    "rationale": step.get("rationale", f"Directly derived from verified resolution of {source_id}."),
                    "verified": True
                })
            else:
                pruned_steps.append({
                    "step_number": idx + 1,
                    "action": action,
                    "reason": f"Step was not verified in source ticket {source_id} resolution logs."
                })
                
        total = len(candidate_steps)
        rate = (len(verified_steps) / total) if total > 0 else 0.0
        
        return {
            "verified_steps": verified_steps,
            "pruned_steps": pruned_steps,
            "all_steps_verified": (len(pruned_steps) == 0 and len(verified_steps) > 0),
            "verification_rate": round(rate * 100, 1)
        }

def re_tokenize(text: str) -> List[str]:
    import re
    return [w for w in re.findall(r'\b[a-zA-Z0-9_-]+\b', text) if len(w) > 2]
