import os
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

CATEGORY_MAP = {
    "INC-AIT": {
        "name": "Integration Gateway & API Timeouts",
        "domain": "Enterprise Applications",
        "restricted": False,
        "default_team": "Enterprise Integration Team"
    },
    "INC-ALP": {
        "name": "Active Directory Account Lockout",
        "domain": "Identity & Access Management",
        "restricted": True,
        "default_team": "Identity & Access Support"
    },
    "INC-CES": {
        "name": "Expired TLS Certificates & Incomplete Chain",
        "domain": "Cloud & Infrastructure",
        "restricted": False,
        "default_team": "Cloud Infrastructure Ops"
    },
    "INC-DCP": {
        "name": "Intune Device Compliance & Conditional Access",
        "domain": "Hardware & Endpoint Security",
        "restricted": False,
        "default_team": "Modern Workplace Endpoint Team"
    },
    "INC-DRF": {
        "name": "Internal DNS Resolution Failure",
        "domain": "Network & Connectivity",
        "restricted": False,
        "default_team": "Core Network Operations"
    },
    "INC-EDE": {
        "name": "Endpoint Disk Encryption & BitLocker TPM",
        "domain": "Hardware & Endpoint Security",
        "restricted": True,
        "default_team": "Endpoint Security Operations"
    },
    "INC-LPD": {
        "name": "Laptop Performance Degradation & Startup Policy",
        "domain": "Hardware & Workplace Support",
        "restricted": False,
        "default_team": "Desktop Engineering"
    },
    "INC-OES": {
        "name": "Outlook Desktop & Exchange Sync Failure",
        "domain": "Collaboration & Email",
        "restricted": False,
        "default_team": "Microsoft 365 Operations"
    },
    "INC-PDQ": {
        "name": "Print Spooler Crash & Stuck Queue",
        "domain": "Hardware & Workplace Support",
        "restricted": False,
        "default_team": "Workplace Infrastructure Support"
    },
    "INC-SDA": {
        "name": "Shared Drive Access Denied & Group Membership",
        "domain": "Identity & Access Management",
        "restricted": True,
        "default_team": "Identity & Access Support"
    },
    "INC-SIB": {
        "name": "Software Center Deployment & Entitlement Block",
        "domain": "Enterprise Applications",
        "restricted": False,
        "default_team": "Client Platform Engineering"
    },
    "INC-SML": {
        "name": "SSO & MFA Prompt Authentication Loop",
        "domain": "Identity & Access Management",
        "restricted": True,
        "default_team": "Identity & Access Support"
    },
    "INC-VDA": {
        "name": "GlobalProtect VPN Immediate Disconnect",
        "domain": "Network & Connectivity",
        "restricted": False,
        "default_team": "Network Security & VPN Team"
    },
    "INC-WCI": {
        "name": "Corporate Wi-Fi 802.1X / RADIUS Failure",
        "domain": "Network & Connectivity",
        "restricted": False,
        "default_team": "Wireless Network Operations"
    }
}

def clean_record(row):
    rec_id = str(row['record_id'])
    prefix = "-".join(rec_id.split("-")[:2])
    cat_info = CATEGORY_MAP.get(prefix, {
        "name": "General IT Incident",
        "domain": "General IT",
        "restricted": False,
        "default_team": "IT Service Desk Tier 2"
    })
    
    t = row['ticket'] if isinstance(row['ticket'], dict) else {}
    diag = row['diagnostics'] if isinstance(row['diagnostics'], dict) else {}
    res = row['resolution'] if isinstance(row['resolution'], dict) else {}
    
    # Handle numpy arrays safely
    apps = list(t.get('applications', [])) if t.get('applications') is not None else []
    obs_errors = list(diag.get('observed_errors', [])) if diag.get('observed_errors') is not None else []
    res_steps = list(res.get('steps', [])) if res.get('steps') is not None else []
    
    # Extract agent questions from correspondence
    agent_questions = []
    corr = row.get('correspondence')
    if corr is not None:
        for turn in corr:
            if isinstance(turn, dict) and turn.get('role') == 'agent' and turn.get('event_type') in ['diagnostic_question', 'agent_question']:
                agent_questions.append(turn.get('message', ''))
                
    env = t.get('environment', {}) if isinstance(t.get('environment'), dict) else {}
    
    return {
        "record_id": rec_id,
        "category_code": prefix,
        "category_name": cat_info["name"],
        "domain": cat_info["domain"],
        "is_restricted": cat_info["restricted"],
        "assigned_team": cat_info["default_team"],
        "title": t.get("submitted_title", "").strip(),
        "description": t.get("submitted_description", "").strip(),
        "priority": t.get("priority", "medium").lower(),
        "applications": [str(a) for a in apps],
        "platform": env.get("platform", "workstation"),
        "os": env.get("os", "Windows 11"),
        "region": env.get("region", "global"),
        "observed_errors": [str(e) for e in obs_errors],
        "root_cause": str(row.get("root_cause", "")).strip(),
        "resolution_steps": [str(s) for s in res_steps],
        "agent_questions": agent_questions
    }

def generate_tricky_tests():
    """Generates synthetic test tickets covering Ambiguous (Ask), Unknown (Escalate), and Lookalikes."""
    return [
        {
            "test_id": "TEST-ASK-01",
            "title": "Cannot sign in after morning restart",
            "description": "I restarted my laptop this morning and now cannot access my company applications. The browser gives me an authentication failure and keeps redirecting. I am working from home.",
            "expected_decision": "ASK",
            "competing_causes": ["INC-SML (MFA Prompt Loop)", "INC-ALP (AD Account Lockout)"],
            "disambiguating_question": "Does the error message specifically indicate that your account is locked out, or are you receiving repeated authentication prompts in a continuous browser loop?",
            "expected_category": "Identity & Access Management",
            "note": "Ambiguous symptoms between MFA loop and Account Lockout"
        },
        {
            "test_id": "TEST-ASK-02",
            "title": "Network disconnected right after connection established",
            "description": "My connection drops immediately within 2 seconds of connecting. Cannot reach any internal intranet sites.",
            "expected_decision": "ASK",
            "competing_causes": ["INC-VDA (GlobalProtect VPN)", "INC-WCI (Corporate Wi-Fi)"],
            "disambiguating_question": "Are you connected to the in-office Corporate Wi-Fi network, or are you connecting remotely over the GlobalProtect VPN client?",
            "expected_category": "Network & Connectivity",
            "note": "Ambiguous between wireless RADIUS drops and VPN client certificate issues"
        },
        {
            "test_id": "TEST-ESC-01",
            "title": "Quantum DB cluster partition error in production zone 4",
            "description": "Production database node quantum-db-04 failed quorum sync with error QD-9941 raft state corrupt. Data pipeline halted.",
            "expected_decision": "ESCALATE",
            "competing_causes": [],
            "target_team": "Core Infrastructure Database Ops",
            "expected_category": "Out of Distribution / Unknown",
            "note": "Novel system not present in historical corpus of 745 workspace incidents"
        },
        {
            "test_id": "TEST-ESC-02",
            "title": "Need help with computer problem",
            "description": "Something stopped working today please fix it as soon as possible it is very urgent thank you.",
            "expected_decision": "ESCALATE",
            "competing_causes": [],
            "target_team": "IT Service Desk Tier 1",
            "expected_category": "Vague / Insufficient Detail",
            "note": "Extremely vague ticket with zero technical diagnostic details"
        },
        {
            "test_id": "TEST-LOOKALIKE-01",
            "title": "Certificate expired error when opening internal HR portal",
            "description": "Users get an SSL/TLS error NET::ERR_CERT_DATE_INVALID when navigating to internal HR benefits portal via Edge browser.",
            "expected_decision": "FIX",
            "expected_category_code": "INC-CES",
            "competing_causes": ["INC-VDA (Device Cert)", "INC-CES (Service TLS Cert)"],
            "distractor_to_avoid": "INC-VDA",
            "note": "Lookalike keyword 'certificate', but web service TLS rather than endpoint VPN cert"
        }
    ]

def main():
    base_dir = r"C:\Users\schan\.gemini\antigravity\scratch\it-ticket-assistant"
    parquet_path = os.path.join(base_dir, "data", "train.parquet")
    print(f"Loading parquet data from: {parquet_path}")
    df = pd.read_parquet(parquet_path)
    print(f"Total raw records: {len(df)}")
    
    cleaned = [clean_record(row) for _, row in df.iterrows()]
    
    # Save full clean corpus
    clean_corpus_path = os.path.join(base_dir, "data", "clean_corpus.json")
    with open(clean_corpus_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2)
    print(f"Saved clean corpus ({len(cleaned)} records) -> {clean_corpus_path}")
    
    # Stratified 70/30 split
    categories = [r['category_code'] for r in cleaned]
    train_records, test_records = train_test_split(
        cleaned,
        test_size=0.30,
        random_state=42,
        stratify=categories
    )
    
    train_path = os.path.join(base_dir, "data", "train_split.json")
    test_path = os.path.join(base_dir, "data", "test_split.json")
    with open(train_path, "w", encoding="utf-8") as f:
        json.dump(train_records, f, indent=2)
    with open(test_path, "w", encoding="utf-8") as f:
        json.dump(test_records, f, indent=2)
    print(f"Saved Train Split ({len(train_records)} records, 70%) -> {train_path}")
    print(f"Saved Test Split ({len(test_records)} records, 30%) -> {test_path}")
    
    # Save tricky tests
    tricky = generate_tricky_tests()
    tricky_path = os.path.join(base_dir, "data", "tricky_tests.json")
    with open(tricky_path, "w", encoding="utf-8") as f:
        json.dump(tricky, f, indent=2)
    print(f"Saved Tricky Test Cases ({len(tricky)} records) -> {tricky_path}")
    
    # Save taxonomy reference
    taxo_path = os.path.join(base_dir, "data", "taxonomy_map.json")
    with open(taxo_path, "w", encoding="utf-8") as f:
        json.dump(CATEGORY_MAP, f, indent=2)
    print(f"Saved Taxonomy Map -> {taxo_path}")

if __name__ == "__main__":
    main()
