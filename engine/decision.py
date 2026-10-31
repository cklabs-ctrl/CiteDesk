import os
import re
import json
from typing import Dict, Any, List, Optional

class DecisionGate:
    """
    Tri-State Decision Arbiter:
    Maps incoming ticket evidence to exactly one of three states:
      1. FIX: Clear consensus among similar tickets and high classifier confidence.
      2. ASK: Two competing root causes detected or Lookalike conflict; selects the optimal disambiguating question.
      3. ESCALATE: Low similarity, unknown failure mode, or vague ticket; routes to target team.
    """
    
    CONFIDENCE_FIX_FLOOR = 0.22
    CLASSIFIER_FIX_FLOOR = 0.28
    
    @classmethod
    def evaluate(
        cls,
        classification: Dict[str, Any],
        similar_tickets: List[Dict[str, Any]],
        raw_description: str,
        user_name: str = ""
    ) -> Dict[str, Any]:
        words = raw_description.split()
        
        # 1. Edge case: Extremely brief query (< 6 words)
        if len(words) < 6:
            return {
                "decision": "ESCALATE",
                "reason": "Ticket description is too brief or lacks actionable technical symptoms.",
                "confidence_score": 0.20,
                "target_team": "IT Service Desk Tier 1",
                "missing_information": [
                    "Specific error codes or message",
                    "Affected application name",
                    "Steps to reproduce"
                ]
            }
            
        if not similar_tickets:
            return {
                "decision": "ESCALATE",
                "reason": "No historical precedent found in incident corpus.",
                "confidence_score": 0.10,
                "target_team": classification.get("assigned_team", "Tier 2 Service Desk"),
                "missing_information": ["Diagnostic logs", "System event IDs"]
            }
            
        top_match = similar_tickets[0]
        top_score = top_match["similarity_score"]
        clf_conf = classification.get("category_confidence", 0.0)
        clf_code = classification.get("category_code")
        retrieved_code = top_match["category_code"]
        agrees_with_classifier = (retrieved_code == clf_code)
        
        # 2. Check for Out-Of-Distribution / Completely Unrecognized (ESCALATE)
        # When both similarity and classifier confidence are low, it's an unknown error or completely vague
        if top_score < 0.15 and clf_conf < 0.22:
            return {
                "decision": "ESCALATE",
                "reason": f"Low evidence confidence (Top similarity: {top_score:.2f}, Category certainty: {clf_conf:.2f}). No verified playbook exists.",
                "confidence_score": round((top_score + clf_conf) / 2, 3),
                "target_team": classification.get("assigned_team", "Tier 2 Service Desk"),
                "missing_information": [
                    "Host configuration logs",
                    "Observed application error stack trace",
                    "Network trace / packet capture"
                ]
            }
            
        # 3. Check for Competing Causes or Lookalike Conflicts (ASK)
        cand1 = similar_tickets[0]
        cand2 = similar_tickets[1] if len(similar_tickets) > 1 else None
        
        # Case A: Top-2 retrieved candidates have close scores from different categories
        is_retrieval_split = False
        if cand2 and cand1["category_code"] != cand2["category_code"]:
            diff = abs(cand1["similarity_score"] - cand2["similarity_score"])
            if diff <= 0.06 and cand1["similarity_score"] >= 0.12:
                is_retrieval_split = True
                
        # Case B: Conflict between Top Classifier prediction and Top Retriever match (Lookalike)
        is_lookalike_split = (not agrees_with_classifier and cand1["similarity_score"] >= 0.14 and clf_conf >= 0.15)
        
        # Case C: Classifier top-2 categories are in close contest with meaningful confidence
        top_cats = classification.get("top_categories", [])
        is_classifier_split = False
        if len(top_cats) >= 2 and clf_conf >= 0.20:
            cat_diff = abs(top_cats[0]["confidence"] - top_cats[1]["confidence"])
            if cat_diff <= 0.12:
                is_classifier_split = True
                
        if is_retrieval_split or is_lookalike_split or is_classifier_split:
            cand_alt = cand2 if (cand2 and cand2["category_code"] != cand1["category_code"]) else {
                "category_code": clf_code,
                "category_name": classification.get("category_name", clf_code),
                "record_id": "PREDICTED-CLF",
                "root_cause": f"System classifier predicts {classification.get('category_name')}",
                "agent_questions": []
            }
            question = cls._pick_disambiguating_question(cand1, cand_alt, user_name=user_name)
            return {
                "decision": "ASK",
                "reason": (
                    f"Ambiguous diagnosis: Multiple competing technical causes detected. "
                    f"Evidence points to '{cand1['category_name']}' ({cand1['similarity_score']:.2f}) "
                    f"while competing signals indicate '{cand_alt['category_name']}'."
                ),
                "confidence_score": round((top_score + clf_conf) / 2, 3),
                "competing_causes": [
                    {"category": cand1["category_name"], "historical_id": cand1["record_id"], "cause": cand1.get("root_cause", "")},
                    {"category": cand_alt["category_name"], "historical_id": cand_alt["record_id"], "cause": cand_alt.get("root_cause", "")}
                ],
                "disambiguating_question": question
            }
            
        # 4. High Consensus (FIX)
        if top_score >= cls.CONFIDENCE_FIX_FLOOR and agrees_with_classifier and clf_conf >= cls.CLASSIFIER_FIX_FLOOR:
            return {
                "decision": "FIX",
                "reason": (
                    f"Strong consensus: Nearest resolved case {top_match['record_id']} ({top_score:.2f}) "
                    f"aligns with predicted category '{classification.get('category_name')}' ({clf_conf:.2f})."
                ),
                "confidence_score": round(0.5 * top_score + 0.5 * clf_conf, 3),
                "target_team": classification.get("assigned_team", "Tier 2 Support")
            }
            
        # 5. Default Fallback -> ESCALATE
        return {
            "decision": "ESCALATE",
            "reason": f"Insufficient confidence in single root cause. Forwarding for Tier 2 manual triage.",
            "confidence_score": round(top_score, 3),
            "target_team": classification.get("assigned_team", "Tier 2 Service Desk"),
            "missing_information": ["Detailed error screenshots", "Recent system change history"]
        }

    @classmethod
    def _sanitize_and_personalize_question(cls, q: str, user_name: str = "") -> str:
        # 1. Strip trailing historical agent signatures/disclaimers
        cleaned = re.sub(r'\s*—\s*[A-Z][a-z]+\s+[A-Z][a-z]+.*$', '', q.strip())
        cleaned = re.sub(r'My name is [A-Z][a-z]+\s+[A-Z][a-z]+.*$', '', cleaned)
        
        # 2. Strip leading historical greetings like 'Hi Marcus,', 'Hi Marcus —', 'Hello Julia,'
        cleaned = re.sub(r'^(Hi|Hello|Dear|Hey)\s+[A-Z][a-zA-Z0-9_\'\-]*(\s+[A-Z][a-zA-Z0-9_\'\-]*)?(\s*,\s*|\s*—\s*|\s*-\s*)', '', cleaned, flags=re.IGNORECASE)
        
        # 3. Determine greeting based strictly on the current input user profile
        first_name = user_name.strip().split()[0] if user_name and user_name.strip().lower() != "user" else ""
        greeting = f"Hi {first_name}," if first_name else "Hello,"
        
        remainder = cleaned.strip()
        if remainder:
            first_word = remainder.split()[0]
            if first_word.lower() in {'thanks', 'please', 'could', 'can', 'would', 'do', 'does', 'are', 'is', 'we'}:
                remainder = remainder[0].lower() + remainder[1:]
                
        return f"{greeting} {remainder}"

    @classmethod
    def _pick_disambiguating_question(cls, cand1: Dict[str, Any], cand2: Dict[str, Any], user_name: str = "") -> str:
        for q in cand1.get("agent_questions", []):
            if len(q) > 20 and "?" in q:
                raw_q = q.split("?")[0].strip() + "?"
                return cls._sanitize_and_personalize_question(raw_q, user_name)
        for q in cand2.get("agent_questions", []):
            if len(q) > 20 and "?" in q:
                raw_q = q.split("?")[0].strip() + "?"
                return cls._sanitize_and_personalize_question(raw_q, user_name)
                
        c1, c2 = cand1.get("category_code"), cand2.get("category_code")
        pairs = {
            frozenset(["INC-ALP", "INC-SML"]): "Are you receiving an explicit 'Account Locked' error, or are you trapped in repeated browser MFA redirects?",
            frozenset(["INC-VDA", "INC-WCI"]): "Does this disconnect occur while connected over GlobalProtect VPN, or directly on the Corporate Wi-Fi network?",
            frozenset(["INC-CES", "INC-VDA"]): "Is the certificate error appearing in a web browser (SSL/TLS) or within the GlobalProtect VPN client?",
            frozenset(["INC-EDE", "INC-DCP"]): "Is BitLocker failing to encrypt the local drive, or is the device showing as Noncompliant in Intune Company Portal?",
            frozenset(["INC-LPD", "INC-OES"]): "Is the performance slowness affecting the entire Windows laptop, or specifically during Outlook Exchange mailbox sync?"
        }
        base_pair_q = pairs.get(
            frozenset([c1, c2]),
            f"Are your symptoms more closely related to '{cand1.get('category_name')}' or '{cand2.get('category_name')}'?"
        )
        first_name = user_name.strip().split()[0] if user_name and user_name.strip().lower() != "user" else ""
        if first_name:
            return f"Hi {first_name}, {base_pair_q[0].lower() + base_pair_q[1:]}"
        return base_pair_q
