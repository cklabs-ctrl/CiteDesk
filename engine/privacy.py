import re
from typing import Dict, Any, List, Tuple

class PrivacyGuard:
    """
    Handles PII de-identification and role-based access control (RBAC) boundaries.
    Ensures sensitive corporate tokens and personal data never leave the security perimeter unmasked.
    """
    
    # Regex patterns for corporate ITSM PII
    PATTERNS = [
        ("EMP_ID", re.compile(r'\bEMP[-_]?\d{4,7}\b', re.IGNORECASE)),
        ("EMAIL", re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')),
        ("IP_ADDRESS", re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b')),
        ("HOSTNAME", re.compile(r'\b(?:WORKSTATION|DESKTOP|LAPTOP|SRV|DC|PS)[A-Za-z0-9_-]+\b', re.IGNORECASE)),
        ("FQDN_HOST", re.compile(r'\b[a-zA-Z0-9-]+\.(?:corplabs|internal|local)\b', re.IGNORECASE)),
        ("PHONE", re.compile(r'\b(?:\+?1[-.]?)?\(?[2-9]\d{2}\)?[-.]?\d{3}[-.]?\d{4}\b')),
    ]
    
    # Typical name recognition patterns in tickets (e.g., "Monica Carson", "mcarson", "jane.doe")
    NAME_PATTERNS = [
        re.compile(r'\b(?:Hi|Hello|Dear|User|CN=)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'),
        re.compile(r'\b(?:username|user):\s*([a-z0-9._]+)\b', re.IGNORECASE)
    ]
    
    @classmethod
    def redact_text(cls, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        if not text:
            return "", []
            
        redacted = text
        detections = []
        entity_counters: Dict[str, int] = {}
        
        # 1. Custom entity replacements with index tracking
        for entity_type, regex in cls.PATTERNS:
            matches = list(regex.finditer(redacted))
            # Reverse order to preserve match spans
            for m in reversed(matches):
                val = m.group(0)
                entity_counters[entity_type] = entity_counters.get(entity_type, 0) + 1
                token = f"[{entity_type}_{entity_counters[entity_type]}]"
                detections.append({
                    "entity_type": entity_type,
                    "original_snippet": val,
                    "replacement_token": token
                })
                redacted = redacted[:m.start()] + token + redacted[m.end():]
                
        # 2. Redact identifiable names & account handles
        for regex in cls.NAME_PATTERNS:
            matches = list(regex.finditer(redacted))
            for m in reversed(matches):
                if m.groups():
                    val = m.group(1)
                    if len(val) > 2 and not val.isupper() and val not in ["The", "And", "For", "This", "That"]:
                        entity_counters["PERSON"] = entity_counters.get("PERSON", 0) + 1
                        token = f"[PERSON_{entity_counters['PERSON']}]"
                        detections.append({
                            "entity_type": "PERSON_NAME",
                            "original_snippet": val,
                            "replacement_token": token
                        })
                        redacted = redacted[:m.start(1)] + token + redacted[m.end(1):]
                        
        return redacted, detections

    @classmethod
    def check_rbac_permission(cls, category_code: str, user_role: str) -> Dict[str, Any]:
        """
        Enforces simulated RBAC scoping:
        Account lockouts (ALP), BitLocker keys (EDE), Shared Drive (SDA), MFA loops (SML)
        require 'identity_analyst', 'security_lead', or 'admin' roles.
        """
        restricted_prefixes = ["INC-ALP", "INC-EDE", "INC-SDA", "INC-SML"]
        is_restricted = category_code in restricted_prefixes
        
        allowed_roles = ["identity_analyst", "security_lead", "admin", "service_desk_lead"]
        has_access = not is_restricted or (user_role.lower() in allowed_roles)
        
        return {
            "is_restricted": is_restricted,
            "has_access": has_access,
            "required_role": "Identity/Security Lead" if is_restricted else "General Service Desk",
            "current_role": user_role,
            "warning": None if has_access else f"Access Restricted: Ticket involves privileged credentials or identity operations. Role '{user_role}' cannot view unmasked security traces."
        }
