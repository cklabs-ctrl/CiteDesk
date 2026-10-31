#!/usr/bin/env python3
"""
Synthetic ITSM Ticket & Knowledge Base Data Generator
======================================================
HCLTech | Future Ready AI Engineer Hackathon
Intelligent IT Ticket Analysis and Resolution Assistant

This standalone script generates synthetic enterprise ITSM data strictly 
aligned with the hackathon brief and functional requirements:
  - FR-01: Ticket Classification (Category, Subcategory, Priority, Intent)
  - FR-02: Duplicate & Similarity Detection (Clusters, Paraphrased cases)
  - FR-03: Resolution Recommendation (Root causes, Actionable steps)
  - FR-04: Evidence & Traceability (Source KB, Verbatim excerpts, ticket IDs)
  - FR-05: Confidence & Fallback (Vague queries, Hardware damage, Novel bugs)
  - FR-06: Analyst Feedback (Useful votes, validation flags)
  - FR-07: Search & Filtering (Service, Environment, Assignment Group, Dates)
  - FR-08: Audit-friendly output (Structured JSON & CSV schemas)

Requirements: Python 3.8+ (Standard Library only, zero external pip dependencies).
"""

import os
import sys
import json
import csv
import random
import argparse
from datetime import datetime, timedelta

# ==============================================================================
# TAXONOMY DEFINITION
# ==============================================================================
TAXONOMY = {
    "categories": [
        {
            "name": "Identity & Access Management",
            "subcategories": ["MFA / 2FA", "Active Directory", "Application Access Request", "Single Sign-On / SAML"],
            "default_assignment_group": "IAM-Support"
        },
        {
            "name": "Network & Connectivity",
            "subcategories": ["VPN", "Wi-Fi & LAN", "DNS / Routing", "Firewall & Security Gateway"],
            "default_assignment_group": "NetOps-Support"
        },
        {
            "name": "Enterprise Applications",
            "subcategories": ["SAP ERP", "Salesforce CRM", "Workday HRIS", "Oracle EBS"],
            "default_assignment_group": "Enterprise-Apps-Team"
        },
        {
            "name": "Cloud & Infrastructure",
            "subcategories": ["AWS IAM / S3", "Kubernetes / Containers", "Azure Virtual Machines", "Database & Storage"],
            "default_assignment_group": "Cloud-Ops"
        },
        {
            "name": "Collaboration & Email",
            "subcategories": ["Microsoft 365 / Outlook", "Microsoft Teams", "Slack & Zoom"],
            "default_assignment_group": "Workplace-Support"
        },
        {
            "name": "Hardware & Workplace Support",
            "subcategories": ["Peripherals & Docks", "Laptop Hardware Damage", "OS / Blue Screen BSOD", "Printing Services"],
            "default_assignment_group": "Desktop-Support"
        },
        {
            "name": "Developer Tools & DevOps",
            "subcategories": ["GitLab / CI/CD", "GitHub & Version Control", "Docker & Container Runtime", "Artifactory & Package Repo"],
            "default_assignment_group": "DevOps-Support"
        }
    ],
    "priorities": [
        {"level": "P1 - Critical", "description": "Complete service outage affecting multiple users or business-critical revenue/production process."},
        {"level": "P2 - High", "description": "High business impact or single customer-critical blocker with no immediate workaround."},
        {"level": "P3 - Medium", "description": "Operational issue with existing workaround or single non-critical user workflow degradation."},
        {"level": "P4 - Low", "description": "Minor inquiry, cosmetic issue, or low-urgency service request."}
    ],
    "environments": ["Production", "Staging", "QA", "Corporate", "Development"],
    "assignment_groups": [
        "IAM-Support",
        "NetOps-Support",
        "Cloud-Ops",
        "DevOps-Support",
        "Enterprise-Apps-Team",
        "SAP-Core-Support",
        "CRM-Ops",
        "Workplace-Support",
        "Desktop-Support",
        "Triage-Queue"
    ]
}

# ==============================================================================
# SEED KNOWLEDGE BASE ARTICLES (15 Approved Standard Runbooks)
# ==============================================================================
KB_ARTICLES = [
    {
        "kb_id": "KB-2001",
        "title": "Resolving Okta MFA Push Notification Timeout and Device Re-enrollment",
        "category": "Identity & Access Management",
        "subcategory": "MFA / 2FA",
        "affected_service": "Okta Verify",
        "keywords": ["mfa", "okta verify", "push notification", "timeout", "re-enroll", "2fa"],
        "symptoms": "User does not receive push notifications on mobile device or receives 'Push request timed out'.",
        "root_cause": "Desynchronized device push token in Okta backend or clock skew on mobile endpoint.",
        "resolution_steps": (
            "1. Navigate to Okta Admin Console > Directory > People.\n"
            "2. Select affected user and go to 'Reset Authenticators'.\n"
            "3. Clear Okta Verify enrollment.\n"
            "4. Have user log in to portal.company.com and scan the newly generated QR code with Okta Verify.\n"
            "5. Verify successful push challenge."
        ),
        "relevant_excerpt": "To fix Okta MFA push timeouts, reset the authenticator enrollment in Okta Admin Console and have the user scan a fresh enrollment QR code."
    },
    {
        "kb_id": "KB-2002",
        "title": "GlobalProtect VPN Error: 'Could not connect to gateway' / TLS Handshake Failure",
        "category": "Network & Connectivity",
        "subcategory": "VPN",
        "affected_service": "GlobalProtect",
        "keywords": ["vpn", "globalprotect", "tls handshake", "gateway", "palo alto", "network timeout"],
        "symptoms": "GlobalProtect client stuck on 'Connecting' or fails with 'Could not connect to gateway' on Windows/macOS.",
        "root_cause": "Cached stale gateway DNS entry or missing root certificate renewal in system trust store.",
        "resolution_steps": (
            "1. Close GlobalProtect from system tray.\n"
            "2. Run 'ipconfig /flushdns' in elevated Command Prompt.\n"
            "3. Delete folder '%LOCALAPPDATA%\\Palo Alto Networks\\GlobalProtect\\PanGPS'.\n"
            "4. Restart the 'PanGPS' service in services.msc.\n"
            "5. Re-authenticate via SSO credentials and connect to secondary gateway 'gw-backup.corp.internal' if primary is throttled."
        ),
        "relevant_excerpt": "Flush DNS and restart PanGPS service, then delete the PanGPS cache folder under %LOCALAPPDATA% before reconnecting."
    },
    {
        "kb_id": "KB-2003",
        "title": "SAP GUI Session Timeout and RFC Connection Failure (RFC_ERROR_COMMUNICATION)",
        "category": "Enterprise Applications",
        "subcategory": "SAP ERP",
        "affected_service": "SAP ECC / S4HANA",
        "keywords": ["sap", "rfc", "timeout", "sapgui", "connection lost", "dump", "wsaeconnreset"],
        "symptoms": "SAP GUI sessions terminate with error 'WSAECONNRESET: Connection reset by peer' or RFC_ERROR_COMMUNICATION during report execution.",
        "root_cause": "Firewall state table timeout closing idle TCP connections shorter than SAP keepalive interval (rdisp/keepalive).",
        "resolution_steps": (
            "1. Verify SAP instance health via transaction SM50 / SM66 for dialog process bottlenecks.\n"
            "2. Check client SAP GUI connection settings in saplogon.ini: ensure WAN/High Latency option is selected.\n"
            "3. For batch reports exceeding 600s, guide user to execute in background mode via F9 instead of foreground.\n"
            "4. If widespread, check firewall idle connection timeout on port 3200-3300 series."
        ),
        "relevant_excerpt": "Configure SAP GUI connection profile with 'Slow Connection' mode and run long queries in background mode (F9) to prevent TCP idle drop."
    },
    {
        "kb_id": "KB-2004",
        "title": "Microsoft Outlook Keeps Prompting for Password / Modern Auth Failure",
        "category": "Collaboration & Email",
        "subcategory": "Microsoft 365 / Outlook",
        "affected_service": "Exchange Online / Outlook 365",
        "keywords": ["outlook", "credentials", "modern auth", "password prompt", "token", "office 365"],
        "symptoms": "Outlook status bar shows 'Need Password' or 'Disconnected', clicking prompt loops back without accepting valid credentials.",
        "root_cause": "Corrupted Microsoft Office Identity Broker token in Windows Credential Manager or Workplace Join conflict.",
        "resolution_steps": (
            "1. Close all Office 365 applications.\n"
            "2. Open Windows Credential Manager > Windows Credentials.\n"
            "3. Remove all entries beginning with 'MicrosoftOffice16_Data:' and 'adal_token'.\n"
            "4. Navigate to Settings > Accounts > Access work or school; re-authenticate.\n"
            "5. Relaunch Outlook to complete Web Account Manager (WAM) modern auth flow."
        ),
        "relevant_excerpt": "Purge stale 'MicrosoftOffice16_Data' entries from Windows Credential Manager and re-authenticate work account in Windows Settings."
    },
    {
        "kb_id": "KB-2005",
        "title": "AWS S3 Access Denied (HTTP 403) on CI/CD Deployment Role",
        "category": "Cloud & Infrastructure",
        "subcategory": "AWS IAM / S3",
        "affected_service": "AWS Cloud Services",
        "keywords": ["aws", "s3", "403 forbidden", "iam", "kms", "bucket policy"],
        "symptoms": "Automated pipelines or Terraform runs fail with 'AccessDenied: User or role is not authorized to perform: s3:PutObject'.",
        "root_cause": "KMS Key policy lacks decrypt/encrypt permissions for the deployment IAM role or bucket policy enforces mandatory KMS condition.",
        "resolution_steps": (
            "1. Check S3 bucket policy for explicit Deny clauses (e.g. s3:x-amz-server-side-encryption condition).\n"
            "2. Inspect KMS Key Policy for the bucket's target KMS CMK ARN; ensure role ARN is included in 'kms:GenerateDataKey' and 'kms:Decrypt'.\n"
            "3. Update IAM deployment role policy to grant 'kms:Decrypt' on custom encryption key.\n"
            "4. Retrigger pipeline build."
        ),
        "relevant_excerpt": "Ensure target KMS CMK policy includes 'kms:GenerateDataKey' and 'kms:Decrypt' permissions for the IAM deployment role."
    },
    {
        "kb_id": "KB-2006",
        "title": "Active Directory Account Lockout Investigation and Remediation",
        "category": "Identity & Access Management",
        "subcategory": "Active Directory",
        "affected_service": "Active Directory Domain Services",
        "keywords": ["active directory", "account locked", "ad lockout", "badpwdcount", "kerberos"],
        "symptoms": "User account repeatedly locks out every 15-30 minutes despite password change.",
        "root_cause": "Cached expired credentials in Windows Credential Manager, stale mapped network drives, or active mobile ActiveSync profile.",
        "resolution_steps": (
            "1. Query PDC Emulator using 'repadmin /showmeta' or Event Viewer Security Log (Event ID 4740) to find caller computer name.\n"
            "2. On caller computer, check Credential Manager and remove saved domain passwords.\n"
            "3. Disconnect and re-map network drives using 'net use * /delete /yes'.\n"
            "4. Unlock user account in Active Directory Administrative Center.\n"
            "5. Monitor BadPwdCount for 10 minutes to verify stabilization."
        ),
        "relevant_excerpt": "Identify caller machine via Event ID 4740 on PDC, clear cached Windows credentials/scheduled tasks on that host, then unlock AD account."
    },
    {
        "kb_id": "KB-2007",
        "title": "Kubernetes Pod CrashLoopBackOff: OOMKilled (Exit Code 137)",
        "category": "Cloud & Infrastructure",
        "subcategory": "Kubernetes / Containers",
        "affected_service": "EKS / GKE Clusters",
        "keywords": ["kubernetes", "k8s", "crashloopbackoff", "oomkilled", "exit code 137", "memory limit"],
        "symptoms": "Container restarts repeatedly in production namespace; kubectl describe pod shows 'OOMKilled: true (Exit Code 137)'.",
        "root_cause": "Application JVM heap or memory consumption exceeded container cgroup hard limit defined in deployment manifest.",
        "resolution_steps": (
            "1. Run 'kubectl describe pod <pod_name> -n <namespace>' and confirm termination reason 'OOMKilled'.\n"
            "2. Check Grafana/Prometheus container_memory_working_set_bytes before crash.\n"
            "3. Submit a PR to adjust resources.limits.memory in Helm values (increase by 50% headroom).\n"
            "4. For Java services, tune '-XX:MaxRAMPercentage=75.0' to prevent native memory exhaustion.\n"
            "5. Apply deployment and monitor rollouts."
        ),
        "relevant_excerpt": "Confirm Exit Code 137 via kubectl describe pod and increase container memory limit in Helm values or tune JVM MaxRAMPercentage."
    },
    {
        "kb_id": "KB-2008",
        "title": "Dell USB-C / Thunderbolt Docking Station External Display Flickering",
        "category": "Hardware & Workplace Support",
        "subcategory": "Peripherals & Docks",
        "affected_service": "Dell WD19 / WD22TB Docks",
        "keywords": ["docking station", "display flickering", "dell dock", "usb-c", "monitor black screen", "thunderbolt"],
        "symptoms": "External monitors connected via DisplayPort to Dell docking station go black intermittently for 2-3 seconds.",
        "root_cause": "Outdated Realtek MST hub firmware or Intel Iris Xe Graphics driver display refresh rate desync.",
        "resolution_steps": (
            "1. Disconnect dock from laptop and unplug dock power adapter for 30 seconds (power drain).\n"
            "2. Connect dock and run Dell Command | Update to install latest Dock Firmware Utility (WD19/WD22).\n"
            "3. In Windows Advanced Display Settings, change refresh rate of external monitors from 59.94Hz to exactly 60.00Hz.\n"
            "4. Update Intel / NVIDIA graphics driver to verified enterprise release.\n"
            "5. Test with certified DP 1.4 cables."
        ),
        "relevant_excerpt": "Power cycle dock, apply latest Dell Dock MST Firmware update, and ensure display refresh rate is set to exactly 60Hz."
    },
    {
        "kb_id": "KB-2009",
        "title": "Salesforce Single Sign-On (SSO) SAML Assertion Expired / Invalid Issuer",
        "category": "Enterprise Applications",
        "subcategory": "Salesforce CRM",
        "affected_service": "Salesforce",
        "keywords": ["salesforce", "sso", "saml", "assertion expired", "identity provider", "login error"],
        "symptoms": "Users receive 'Single Sign-On Error: We cannot log you in because of an issue with single sign-on' when logging into Salesforce.",
        "root_cause": "IdP signing certificate expired or SAML assertion clock skew exceeds 180 seconds between IdP and Salesforce.",
        "resolution_steps": (
            "1. In Salesforce Setup > Single Sign-On Settings > SAML Assertion Validator, paste the SAML response from browser inspector.\n"
            "2. If error indicates 'Signature Invalid' or 'Expired Certificate', download current IdP metadata certificate from Azure AD/Okta.\n"
            "3. Upload new certificate under Identity Provider Certificate in Salesforce SAML config.\n"
            "4. Ensure SAML Identity Type matches 'User's Salesforce username' or 'Federation ID'.\n"
            "5. Save and initiate test login."
        ),
        "relevant_excerpt": "Use Salesforce SAML Assertion Validator to inspect payload, then update expired IdP signing certificate in SSO settings."
    },
    {
        "kb_id": "KB-2010",
        "title": "GitLab CI/CD Pipeline Shared Runner Execution Timeout and Stuck Jobs",
        "category": "Developer Tools & DevOps",
        "subcategory": "GitLab / CI/CD",
        "affected_service": "GitLab Shared Runners",
        "keywords": ["gitlab", "runner", "ci/cd", "pipeline stuck", "docker daemon", "timeout"],
        "symptoms": "Pipelines remain in 'Pending' status indefinitely or fail with 'Job failed: execution took longer than 1h0m0s'.",
        "root_cause": "Docker image cache disk full on runner host (ENOSPC) or runner registration token revoked.",
        "resolution_steps": (
            "1. SSH into runner host and inspect disk usage via 'df -h /var/lib/docker'.\n"
            "2. Run 'docker system prune -af --volumes' to clean orphan build layers and stopped containers.\n"
            "3. Restart gitlab-runner service: 'sudo systemctl restart gitlab-runner'.\n"
            "4. Verify runner status in GitLab Group > CI/CD Settings > Runners (should show green checkmark).\n"
            "5. Retry stuck pipeline."
        ),
        "relevant_excerpt": "Inspect runner storage with 'df -h', execute 'docker system prune -af --volumes' to free disk space, and restart gitlab-runner."
    },
    {
        "kb_id": "KB-2011",
        "title": "Oracle Database Connection Pool Exhaustion (ORA-00018: maximum number of sessions exceeded)",
        "category": "Cloud & Infrastructure",
        "subcategory": "Database & Storage",
        "affected_service": "Oracle Database 19c",
        "keywords": ["oracle", "ora-00018", "connection pool", "sessions exceeded", "db connection"],
        "symptoms": "Application backend logs throw 'ORA-00018: maximum number of sessions exceeded' and user HTTP requests hang at 504 Gateway Timeout.",
        "root_cause": "Leaked unclosed JDBC connections in microservices batch worker thread pool reaching Oracle SESSIONS limit.",
        "resolution_steps": (
            "1. Run 'SELECT count(*), status, username, machine FROM v$session GROUP BY status, username, machine;' to locate connection leak source.\n"
            "2. Identify offending service and kill inactive sessions: 'ALTER SYSTEM KILL SESSION 'sid,serial#' IMMEDIATE;'.\n"
            "3. Configure HikariCP connection pool with 'maxLifetime=1800000' and 'idleTimeout=600000'.\n"
            "4. If business load has organically scaled, increase SESSIONS parameter in spfile: 'ALTER SYSTEM SET SESSIONS=1200 SCOPE=SPFILE;'.\n"
            "5. Restart connection pool client pods."
        ),
        "relevant_excerpt": "Query v$session to locate unclosed JDBC connection pool leaks, terminate inactive sessions, and tune HikariCP maxLifetime/idleTimeout."
    },
    {
        "kb_id": "KB-2012",
        "title": "Microsoft Teams Microphone and Audio Device Not Detected on Windows",
        "category": "Collaboration & Email",
        "subcategory": "Microsoft Teams",
        "affected_service": "Microsoft Teams Client",
        "keywords": ["teams", "microphone", "audio not working", "headset", "media settings"],
        "symptoms": "User cannot speak during meetings; Teams banner displays 'Your microphone isn't working'.",
        "root_cause": "Windows 11 Privacy & Security setting revoked desktop app microphone permissions or exclusive audio mode conflict.",
        "resolution_steps": (
            "1. Open Windows Settings > Privacy & Security > Microphone.\n"
            "2. Ensure 'Microphone access' is ON and 'Let desktop apps access your microphone' is enabled.\n"
            "3. In Teams Settings > Devices, select the specific headset instead of 'PC Mic and Speakers'.\n"
            "4. In Sound Control Panel (mmsys.cpl), uncheck 'Allow applications to take exclusive control of this device'.\n"
            "5. Place a test call under Teams Device Settings."
        ),
        "relevant_excerpt": "Enable Windows Microphone Privacy settings for desktop apps and disable exclusive control in Sound Control Panel."
    },
    {
        "kb_id": "KB-2013",
        "title": "Corporate Wi-Fi 802.1X Authentication Failure (Certificate Untrusted)",
        "category": "Network & Connectivity",
        "subcategory": "Wi-Fi & LAN",
        "affected_service": "Enterprise Wi-Fi (Corp-Secure)",
        "keywords": ["wifi", "802.1x", "radius", "certificate untrusted", "wpa2 enterprise"],
        "symptoms": "Laptops fail to connect to 'Corp-Secure' Wi-Fi SSID; Windows reports 'Can't connect to this network' or repeatedly prompts for credentials.",
        "root_cause": "RADIUS server EAP certificate expired or corporate root CA certificate missing from user's Trusted Root Certification Authorities store.",
        "resolution_steps": (
            "1. Connect temporarily to 'Corp-Guest' SSID.\n"
            "2. Open certmgr.msc and inspect 'Trusted Root Certification Authorities' for 'Corp-Internal-Root-CA-2024'.\n"
            "3. If missing or expired, run 'gpupdate /force' in Command Prompt to push updated Group Policy certificates.\n"
            "4. Forget 'Corp-Secure' Wi-Fi profile in Windows Network Settings and reconnect with domain credentials."
        ),
        "relevant_excerpt": "Verify Corp-Internal-Root-CA in certmgr.msc, run 'gpupdate /force' to pull updated RADIUS trust certs, and rejoin Corp-Secure SSID."
    },
    {
        "kb_id": "KB-2014",
        "title": "Workday HRIS Self-Service Onboarding Form Submission 500 Internal Error",
        "category": "Enterprise Applications",
        "subcategory": "Workday HRIS",
        "affected_service": "Workday",
        "keywords": ["workday", "onboarding", "500 error", "hris", "form submission"],
        "symptoms": "New hires unable to submit Form I-9 or Direct Deposit; screen displays 'An internal system error occurred. Please contact your administrator'.",
        "root_cause": "Missing worker position hierarchy mapping or invalid tax location code assigned by recruiting.",
        "resolution_steps": (
            "1. In Workday search bar, look up the worker's Pre-Hire record.\n"
            "2. Check 'Staffing History' and inspect the Business Process Event log for error stack.\n"
            "3. Reassign supervisory organization hierarchy if blank.\n"
            "4. Correct tax jurisdiction code to match postal code.\n"
            "5. Re-launch the onboarding step in Workday Business Process."
        ),
        "relevant_excerpt": "Check Workday Pre-Hire Business Process Event log for validation errors, reassign supervisory org, and re-launch onboarding step."
    },
    {
        "kb_id": "KB-2015",
        "title": "Windows BSOD Stop Code DRIVER_IRQL_NOT_LESS_OR_EQUAL (NETIO.SYS)",
        "category": "Hardware & Workplace Support",
        "subcategory": "OS / Blue Screen BSOD",
        "affected_service": "Windows 11 Workstations",
        "keywords": ["bsod", "blue screen", "netio.sys", "driver irql", "crash dump"],
        "symptoms": "Workstation crashes randomly with Blue Screen showing Stop Code: DRIVER_IRQL_NOT_LESS_OR_EQUAL What failed: NETIO.SYS.",
        "root_cause": "Outdated Intel Wi-Fi / Ethernet network adapter driver causing kernel memory corruption during sleep/wake transition.",
        "resolution_steps": (
            "1. Boot system in Safe Mode with Networking if bootlooping.\n"
            "2. Open Device Manager > Network Adapters.\n"
            "3. Right-click Intel Wi-Fi 6E AX211 > Update Driver > Browse my computer.\n"
            "4. Install enterprise package v22.250.0 or newer.\n"
            "5. Run 'sfc /scannow' to repair corrupted system files and reboot normally."
        ),
        "relevant_excerpt": "Upgrade Intel Wi-Fi / Ethernet adapter driver to v22.250.0+ in Device Manager and run 'sfc /scannow' to fix NETIO.SYS crash."
    }
]

# ==============================================================================
# SEED HISTORICAL RESOLVED TICKETS (30 Incidents for Retrieval & Mining)
# ==============================================================================
HISTORICAL_TICKETS = [
    {
        "ticket_id": "INC-1001",
        "title": "Unable to receive Okta push notifications on iPhone 14",
        "description": "User reports that starting this morning, when logging into corporate portal, the Okta verify prompt times out after 60 seconds. Push notification does not trigger on phone.",
        "symptoms": "Push prompt timeout, no notification banner on mobile endpoint.",
        "category": "Identity & Access Management",
        "subcategory": "MFA / 2FA",
        "priority": "P3 - Medium",
        "intent": "MFA Troubleshooting & Re-enrollment",
        "affected_service": "Okta Verify",
        "environment": "Production",
        "assignment_group": "IAM-Support",
        "status": "Resolved",
        "created_at": "2026-10-10T09:15:00Z",
        "resolved_at": "2026-10-10T09:42:00Z",
        "root_cause": "Stale device registration token in Okta tenant following iOS update.",
        "resolution_summary": "Reset Okta Verify authenticator in Okta Admin and guided user to scan new QR code.",
        "resolution_steps": "Cleared MFA authenticator for user in Okta directory. User rescanned enrollment QR code. Push notification succeeded.",
        "linked_kb_id": "KB-2001",
        "resolution_useful_votes": 12
    },
    {
        "ticket_id": "INC-1002",
        "title": "GlobalProtect VPN connection failed: Could not connect to gateway",
        "description": "Remote finance user cannot connect to corporate VPN from home. GlobalProtect client displays 'Could not connect to gateway' after MFA verification.",
        "symptoms": "GlobalProtect fails at gateway handshake step, network error message.",
        "category": "Network & Connectivity",
        "subcategory": "VPN",
        "priority": "P2 - High",
        "intent": "VPN Connection Repair",
        "affected_service": "GlobalProtect",
        "environment": "Production",
        "assignment_group": "NetOps-Support",
        "status": "Resolved",
        "created_at": "2026-10-11T08:30:00Z",
        "resolved_at": "2026-10-11T09:05:00Z",
        "root_cause": "Corrupted PanGPS cache and stale gateway IP resolving to maintenance node.",
        "resolution_summary": "Flushed local DNS, purged PanGPS app data directory, and restarted PanGPS service.",
        "resolution_steps": "Ran 'ipconfig /flushdns', stopped PanGPS, cleared %LOCALAPPDATA%\\Palo Alto Networks\\GlobalProtect\\PanGPS, restarted service. Client connected successfully.",
        "linked_kb_id": "KB-2002",
        "resolution_useful_votes": 18
    },
    {
        "ticket_id": "INC-1003",
        "title": "SAP GUI dumps with WSAECONNRESET while running month-end billing report",
        "description": "SAP GUI session drops abruptly with error 'WSAECONNRESET: Connection reset by peer' whenever generating the custom billing report Z_FIN_MONTHLY.",
        "symptoms": "SAP session disconnects after 5 minutes of execution, WSAECONNRESET socket error.",
        "category": "Enterprise Applications",
        "subcategory": "SAP ERP",
        "priority": "P2 - High",
        "intent": "SAP Session Drop & Optimization",
        "affected_service": "SAP ECC / S4HANA",
        "environment": "Production",
        "assignment_group": "SAP-Core-Support",
        "status": "Resolved",
        "created_at": "2026-10-12T11:20:00Z",
        "resolved_at": "2026-10-12T12:45:00Z",
        "root_cause": "Long-running foreground report hit TCP idle state timeout on firewall.",
        "resolution_summary": "Tuned SAP GUI network setting to High Latency / WAN mode and instructed user to submit report as background job (F9).",
        "resolution_steps": "Advised user to run Z_FIN_MONTHLY via Program > Execute in Background (F9) to spool output. Configured SAP GUI speed setting to slow WAN.",
        "linked_kb_id": "KB-2003",
        "resolution_useful_votes": 8
    },
    {
        "ticket_id": "INC-1004",
        "title": "Outlook repeatedly prompts for credentials and shows 'Need Password'",
        "description": "User cannot send or receive emails in Microsoft Outlook. The bottom status bar says 'Need Password', and clicking it flashes a blank dialog window.",
        "symptoms": "Looping credential prompt in Outlook desktop, blank modern auth modal.",
        "category": "Collaboration & Email",
        "subcategory": "Microsoft 365 / Outlook",
        "priority": "P3 - Medium",
        "intent": "Modern Auth Token Reset",
        "affected_service": "Exchange Online / Outlook 365",
        "environment": "Production",
        "assignment_group": "Workplace-Support",
        "status": "Resolved",
        "created_at": "2026-10-14T10:05:00Z",
        "resolved_at": "2026-10-14T10:25:00Z",
        "root_cause": "Corrupted Office 365 ADAL/WAM credential cache in Windows Credential Manager.",
        "resolution_summary": "Removed stale MicrosoftOffice16 cached tokens in Windows Credential Manager and re-authenticated user account.",
        "resolution_steps": "Closed Outlook, deleted MicrosoftOffice16_Data credentials in Credential Manager, re-authenticated under Windows Settings > Access Work or School. Outlook re-synced.",
        "linked_kb_id": "KB-2004",
        "resolution_useful_votes": 25
    },
    {
        "ticket_id": "INC-1005",
        "title": "CI/CD Pipeline fails with S3 AccessDenied when publishing assets",
        "description": "GitHub Actions / Jenkins pipeline fails at step 'aws s3 cp dist/ s3://prod-static-assets/' with error 'An error occurred (AccessDenied) when calling the PutObject operation'.",
        "symptoms": "HTTP 403 AccessDenied during S3 PutObject in deployment step.",
        "category": "Cloud & Infrastructure",
        "subcategory": "AWS IAM / S3",
        "priority": "P1 - Critical",
        "intent": "AWS IAM & KMS Permission Grant",
        "affected_service": "AWS Cloud Services",
        "environment": "Production",
        "assignment_group": "Cloud-Ops",
        "status": "Resolved",
        "created_at": "2026-10-15T14:10:00Z",
        "resolved_at": "2026-10-15T14:40:00Z",
        "root_cause": "Bucket encryption KMS key policy did not grant kms:GenerateDataKey and kms:Decrypt to deployment service role.",
        "resolution_summary": "Updated KMS key policy ARN allowing deployment IAM role permissions for SSE-KMS operations.",
        "resolution_steps": "Appended deployment role ARN to KMS Key Resource Policy statement for kms:GenerateDataKey. Pipeline rerun succeeded immediately.",
        "linked_kb_id": "KB-2005",
        "resolution_useful_votes": 15
    },
    {
        "ticket_id": "INC-1006",
        "title": "User account keeps locking out every 20 minutes in Active Directory",
        "description": "Employee in Marketing department has their Active Directory account locked repeatedly throughout the day despite changing password yesterday.",
        "symptoms": "AD lockout trigger every 15-20 min, unable to access workstation or SharePoint.",
        "category": "Identity & Access Management",
        "subcategory": "Active Directory",
        "priority": "P2 - High",
        "intent": "AD Account Lockout Source Remediation",
        "affected_service": "Active Directory Domain Services",
        "environment": "Production",
        "assignment_group": "IAM-Support",
        "status": "Resolved",
        "created_at": "2026-10-16T13:00:00Z",
        "resolved_at": "2026-10-16T13:55:00Z",
        "root_cause": "Stale credentials stored in Windows Credential Manager for a mapped shared drive on user's secondary laptop.",
        "resolution_summary": "Traced lockout caller machine using Event 4740, removed obsolete credentials from Credential Manager, and unlocked user.",
        "resolution_steps": "Inspected PDC security event log for Event 4740. Found caller workstation 'LAPTOP-MKT-042'. Cleared stored credentials in user profile, unlocked account in AD.",
        "linked_kb_id": "KB-2006",
        "resolution_useful_votes": 20
    },
    {
        "ticket_id": "INC-1007",
        "title": "Payment gateway service pod restarting with OOMKilled in production namespace",
        "description": "Kubernetes pods for payment-service in cluster k8s-prod-us-east are in CrashLoopBackOff. Pod status shows OOMKilled with exit code 137.",
        "symptoms": "Exit code 137, OOMKilled, CrashLoopBackOff, API latency spike.",
        "category": "Cloud & Infrastructure",
        "subcategory": "Kubernetes / Containers",
        "priority": "P1 - Critical",
        "intent": "Kubernetes Resource Scaling",
        "affected_service": "EKS / GKE Clusters",
        "environment": "Production",
        "assignment_group": "Cloud-Ops",
        "status": "Resolved",
        "created_at": "2026-10-18T16:20:00Z",
        "resolved_at": "2026-10-18T17:05:00Z",
        "root_cause": "Recent spike in transaction payload sizes breached container memory limit of 1Gi.",
        "resolution_summary": "Bumped pod memory limit from 1Gi to 2Gi in Helm values and tuned JVM MaxRAMPercentage to 70%.",
        "resolution_steps": "Updated deployment manifest memory limit to 2Gi, committed to repo, ArgoCD synced rollout. Pods stabilized.",
        "linked_kb_id": "KB-2007",
        "resolution_useful_votes": 14
    },
    {
        "ticket_id": "INC-1008",
        "title": "Dual external monitors flickering black when connected to Dell WD19 dock",
        "description": "User's two 27-inch external Dell monitors randomly flash black for 2 seconds and turn back on when connected via WD19TB docking station.",
        "symptoms": "Intermittent monitor black screen, display flicker via DisplayPort/Thunderbolt.",
        "category": "Hardware & Workplace Support",
        "subcategory": "Peripherals & Docks",
        "priority": "P3 - Medium",
        "intent": "Dock Firmware & Refresh Rate Configuration",
        "affected_service": "Dell WD19 / WD22TB Docks",
        "environment": "Corporate",
        "assignment_group": "Desktop-Support",
        "status": "Resolved",
        "created_at": "2026-10-20T10:10:00Z",
        "resolved_at": "2026-10-20T11:00:00Z",
        "root_cause": "Outdated MST firmware on WD19 dock and monitor refresh rate set to 59.94Hz variable.",
        "resolution_summary": "Applied Dell Dock firmware update package and locked display refresh rates to 60.00 Hz in Windows settings.",
        "resolution_steps": "Updated dock firmware to v01.00.25 via Dell Firmware Utility, changed monitor refresh rate to static 60Hz. Verified flicker-free operation.",
        "linked_kb_id": "KB-2008",
        "resolution_useful_votes": 11
    },
    {
        "ticket_id": "INC-1009",
        "title": "Salesforce login error: Single Sign-On Error - We cannot log you in",
        "description": "Entire sales tier unable to login to Salesforce this morning. Landing page displays 'Single Sign-On Error: We cannot log you in because of an issue with single sign-on'.",
        "symptoms": "SSO error banner on Salesforce login, IdP redirection failure.",
        "category": "Enterprise Applications",
        "subcategory": "Salesforce CRM",
        "priority": "P1 - Critical",
        "intent": "SAML SSO Certificate Renewal",
        "affected_service": "Salesforce",
        "environment": "Production",
        "assignment_group": "CRM-Ops",
        "status": "Resolved",
        "created_at": "2026-10-22T07:45:00Z",
        "resolved_at": "2026-10-22T08:20:00Z",
        "root_cause": "The Okta SSO SAML signing certificate expired at midnight UTC.",
        "resolution_summary": "Exported updated public certificate from Okta and uploaded into Salesforce Single Sign-On configuration.",
        "resolution_steps": "Downloaded renewed cert from Okta Admin, updated SAML Single Sign-On Settings certificate in Salesforce Setup, tested login with test user successfully.",
        "linked_kb_id": "KB-2009",
        "resolution_useful_votes": 31
    },
    {
        "ticket_id": "INC-1010",
        "title": "GitLab CI builds stuck in pending with 'no space left on device' runner error",
        "description": "All merge request pipelines for backend team are stuck in pending or failing immediately with error: 'Job failed: write /var/lib/docker: no space left on device'.",
        "symptoms": "CI jobs stuck, docker daemon no space left on device.",
        "category": "Developer Tools & DevOps",
        "subcategory": "GitLab / CI/CD",
        "priority": "P2 - High",
        "intent": "CI Runner Storage Maintenance",
        "affected_service": "GitLab Shared Runners",
        "environment": "Production",
        "assignment_group": "DevOps-Support",
        "status": "Resolved",
        "created_at": "2026-10-25T15:00:00Z",
        "resolved_at": "2026-10-25T15:35:00Z",
        "root_cause": "Docker image cache and dangling build volumes consumed 100% of /var partition on runner instance runner-03.",
        "resolution_summary": "Pruned docker cache and stopped containers using 'docker system prune -af --volumes' and restarted gitlab-runner.",
        "resolution_steps": "Logged into runner-03, executed 'docker system prune -af --volumes' recovering 82GB, restarted runner service, pending jobs completed cleanly.",
        "linked_kb_id": "KB-2010",
        "resolution_useful_votes": 17
    },
    {
        "ticket_id": "INC-1011",
        "title": "Okta Verify Push timed out after changing company phone",
        "description": "User got an upgrade to a new corporate phone. When trying to log in, push notifications are sent to the old device and time out.",
        "symptoms": "Push notifications sent to decommissioned device, timeout.",
        "category": "Identity & Access Management",
        "subcategory": "MFA / 2FA",
        "priority": "P3 - Medium",
        "intent": "MFA Device Re-enrollment",
        "affected_service": "Okta Verify",
        "environment": "Production",
        "assignment_group": "IAM-Support",
        "status": "Resolved",
        "created_at": "2026-10-26T09:00:00Z",
        "resolved_at": "2026-10-26T09:20:00Z",
        "root_cause": "User failed to register new mobile device authenticator prior to wiping old phone.",
        "resolution_summary": "Revoked old device binding in Okta and triggered MFA enrollment wizard on next login.",
        "resolution_steps": "Reset Okta Verify authenticator in user account, generated onboarding enrollment link. Verified user could scan QR code on new phone.",
        "linked_kb_id": "KB-2001",
        "resolution_useful_votes": 9
    },
    {
        "ticket_id": "INC-1012",
        "title": "Palo Alto GlobalProtect handshake error after Windows 11 feature update",
        "description": "Following 23H2 Windows update, GlobalProtect client cannot establish tunnel to gateway. Stops at 95% then reports gateway timeout.",
        "symptoms": "VPN connection hangs at 95%, gateway timeout error.",
        "category": "Network & Connectivity",
        "subcategory": "VPN",
        "priority": "P2 - High",
        "intent": "VPN Connection Repair",
        "affected_service": "GlobalProtect",
        "environment": "Production",
        "assignment_group": "NetOps-Support",
        "status": "Resolved",
        "created_at": "2026-10-27T10:15:00Z",
        "resolved_at": "2026-10-27T10:50:00Z",
        "root_cause": "Virtual network adapter driver binding disabled by Windows feature update.",
        "resolution_summary": "Re-enabled Palo Alto Networks Virtual Adapter and cleared local PanGPS service state.",
        "resolution_steps": "Enabled PANGPD virtual adapter in ncpa.cpl, cleared local PanGPS app cache, restarted PanGPS service.",
        "linked_kb_id": "KB-2002",
        "resolution_useful_votes": 14
    },
    {
        "ticket_id": "INC-1013",
        "title": "Backend order service throwing ORA-00018: maximum number of sessions exceeded",
        "description": "Production checkout API failing with HTTP 504 errors. Oracle database alerts indicate maximum sessions exceeded (ORA-00018).",
        "symptoms": "ORA-00018 alert, gateway timeouts, database connection refusal.",
        "category": "Cloud & Infrastructure",
        "subcategory": "Database & Storage",
        "priority": "P1 - Critical",
        "intent": "Database Connection Pool Optimization",
        "affected_service": "Oracle Database 19c",
        "environment": "Production",
        "assignment_group": "Cloud-Ops",
        "status": "Resolved",
        "created_at": "2026-10-27T14:00:00Z",
        "resolved_at": "2026-10-27T14:45:00Z",
        "root_cause": "Worker pool failed to release connection on unhandled timeout exception, creating zombie sessions.",
        "resolution_summary": "Killed inactive DB sessions, deployed patch to wrap connection pool borrows in try-with-resources block, and bumped max sessions.",
        "resolution_steps": "Identified leaked sessions via v$session query, terminated 420 inactive sessions, patched Hikari connection pool configuration.",
        "linked_kb_id": "KB-2011",
        "resolution_useful_votes": 16
    },
    {
        "ticket_id": "INC-1014",
        "title": "Microsoft Teams shows 'Your microphone isn't working' on Jabra headset",
        "description": "During client calls, Teams fails to pick up audio from Jabra Evolve 65 headset. System microphone test in Windows works fine.",
        "symptoms": "No audio input in Teams, banner warning on device settings.",
        "category": "Collaboration & Email",
        "subcategory": "Microsoft Teams",
        "priority": "P3 - Medium",
        "intent": "Teams Audio Device Configuration",
        "affected_service": "Microsoft Teams Client",
        "environment": "Corporate",
        "assignment_group": "Workplace-Support",
        "status": "Resolved",
        "created_at": "2026-10-28T11:00:00Z",
        "resolved_at": "2026-10-28T11:25:00Z",
        "root_cause": "Windows audio endpoint exclusivity setting blocked Teams from capturing hardware stream.",
        "resolution_summary": "Disabled audio exclusive mode in Windows Sound Control Panel and set Jabra headset as default communications device.",
        "resolution_steps": "Navigated to mmsys.cpl > Recording > Jabra Properties > Advanced, unchecked 'Allow applications to take exclusive control', made test call.",
        "linked_kb_id": "KB-2012",
        "resolution_useful_votes": 10
    },
    {
        "ticket_id": "INC-1015",
        "title": "MacBook Pro cannot connect to Corp-Secure Wi-Fi after password change",
        "description": "Engineer changed domain password yesterday; today MacBook prompts for credentials continuously when connecting to Corp-Secure Wi-Fi.",
        "symptoms": "Wi-Fi 802.1x authentication loop, connection refused.",
        "category": "Network & Connectivity",
        "subcategory": "Wi-Fi & LAN",
        "priority": "P3 - Medium",
        "intent": "Wi-Fi Profile & Keychain Clean",
        "affected_service": "Enterprise Wi-Fi (Corp-Secure)",
        "environment": "Corporate",
        "assignment_group": "NetOps-Support",
        "status": "Resolved",
        "created_at": "2026-10-28T13:40:00Z",
        "resolved_at": "2026-10-28T14:10:00Z",
        "root_cause": "macOS Keychain retained expired 802.1X certificate entry and previous domain password.",
        "resolution_summary": "Deleted Corp-Secure 802.1X password entry from Keychain Access and rejoined network.",
        "resolution_steps": "Opened Keychain Access, searched for 'Corp-Secure', deleted stored 802.1X password, rejoined network entering current domain password.",
        "linked_kb_id": "KB-2013",
        "resolution_useful_votes": 13
    },
    {
        "ticket_id": "INC-1016",
        "title": "New hire getting 500 error on Workday Direct Deposit onboarding step",
        "description": "New joiner in Austin office receives an internal server error when trying to complete direct deposit form on Workday portal.",
        "symptoms": "HTTP 500 error in Workday employee portal upon saving bank information.",
        "category": "Enterprise Applications",
        "subcategory": "Workday HRIS",
        "priority": "P3 - Medium",
        "intent": "Workday Onboarding Workflow Fix",
        "affected_service": "Workday",
        "environment": "Production",
        "assignment_group": "Enterprise-Apps-Team",
        "status": "Resolved",
        "created_at": "2026-10-28T15:00:00Z",
        "resolved_at": "2026-10-28T15:45:00Z",
        "root_cause": "Supervisory organization hierarchy missing in pre-hire profile causing business process failure.",
        "resolution_summary": "Assigned correct Supervisory Org and re-triggered onboarding business process.",
        "resolution_steps": "Located pre-hire profile, linked reporting manager and supervisory org, clicked Re-evaluate business process. User completed submission.",
        "linked_kb_id": "KB-2014",
        "resolution_useful_votes": 7
    },
    {
        "ticket_id": "INC-1017",
        "title": "Windows BSOD NETIO.SYS crash when resuming from sleep",
        "description": "Dell Latitude 5530 crashes with blue screen DRIVER_IRQL_NOT_LESS_OR_EQUAL pointing to NETIO.SYS whenever opening laptop lid after sleep.",
        "symptoms": "Blue screen crash on resume, memory minidump NETIO.SYS.",
        "category": "Hardware & Workplace Support",
        "subcategory": "OS / Blue Screen BSOD",
        "priority": "P2 - High",
        "intent": "Network Driver BSOD Remediation",
        "affected_service": "Windows 11 Workstations",
        "environment": "Corporate",
        "assignment_group": "Desktop-Support",
        "status": "Resolved",
        "created_at": "2026-10-29T09:30:00Z",
        "resolved_at": "2026-10-29T10:15:00Z",
        "root_cause": "Corrupted Intel Wi-Fi driver packet filter during power state transitions.",
        "resolution_summary": "Upgraded Intel Wi-Fi driver to v22.250 and repaired system files with sfc /scannow.",
        "resolution_steps": "Downloaded Intel Wi-Fi package, installed in safe mode, verified sfc /scannow completed with zero integrity violations. Tested sleep cycles.",
        "linked_kb_id": "KB-2015",
        "resolution_useful_votes": 12
    },
    {
        "ticket_id": "INC-1018",
        "title": "Need access to AWS DynamoDB staging table for billing analytics",
        "description": "Junior developer requesting read/write access to DynamoDB table 'billing-transactions-staging' in staging account.",
        "symptoms": "User lacks IAM policy for DynamoDB table access.",
        "category": "Identity & Access Management",
        "subcategory": "Application Access Request",
        "priority": "P4 - Low",
        "intent": "IAM Access Grant",
        "affected_service": "AWS Cloud Services",
        "environment": "Staging",
        "assignment_group": "IAM-Support",
        "status": "Resolved",
        "created_at": "2026-10-29T11:00:00Z",
        "resolved_at": "2026-10-29T11:30:00Z",
        "root_cause": "Routine permission request with manager signoff.",
        "resolution_summary": "Added developer IAM role to staging DynamoDB ReadWrite policy group after verifying manager approval.",
        "resolution_steps": "Validated manager approval in ticket attachment, updated developer IAM group policy in AWS staging account.",
        "linked_kb_id": "KB-2005",
        "resolution_useful_votes": 4
    },
    {
        "ticket_id": "INC-1019",
        "title": "SAP purchase order release workflow stuck with RFC communication failure",
        "description": "Purchasing department unable to release purchase orders. System generates error 'RFC_ERROR_COMMUNICATION: CPIC-CALL timeout'.",
        "symptoms": "Workflow stalled, RFC communication error in SM58.",
        "category": "Enterprise Applications",
        "subcategory": "SAP ERP",
        "priority": "P2 - High",
        "intent": "SAP RFC Queue Recovery",
        "affected_service": "SAP ECC / S4HANA",
        "environment": "Production",
        "assignment_group": "SAP-Core-Support",
        "status": "Resolved",
        "created_at": "2026-10-29T14:20:00Z",
        "resolved_at": "2026-10-29T15:10:00Z",
        "root_cause": "Blocked background dialog work processes in SM50 due to runaway batch query.",
        "resolution_summary": "Killed runaway job in SM50 and cleared stalled transactional RFC queue in SM58.",
        "resolution_steps": "Terminated rogue report in SM50, executed retry on stalled tRFC queue entries in transaction SM58. Workflow resumed normal dispatch.",
        "linked_kb_id": "KB-2003",
        "resolution_useful_votes": 11
    },
    {
        "ticket_id": "INC-1020",
        "title": "Production search microservice pod hitting memory limits and crashing",
        "description": "ElasticSearch search proxy pods are restarting every 10 minutes. kubectl logs show exit code 137.",
        "symptoms": "Continuous pod termination, exit code 137, latency spike.",
        "category": "Cloud & Infrastructure",
        "subcategory": "Kubernetes / Containers",
        "priority": "P1 - Critical",
        "intent": "Kubernetes Memory Limit Tuning",
        "affected_service": "EKS / GKE Clusters",
        "environment": "Production",
        "assignment_group": "Cloud-Ops",
        "status": "Resolved",
        "created_at": "2026-10-29T16:00:00Z",
        "resolved_at": "2026-10-29T16:30:00Z",
        "root_cause": "Heap memory exceeded pod container boundary under increased search traffic.",
        "resolution_summary": "Scaled memory limit from 2Gi to 4Gi in Kubernetes deployment manifest.",
        "resolution_steps": "Updated helm deployment template memory limit to 4Gi and request to 2Gi. Applied via GitOps pipeline.",
        "linked_kb_id": "KB-2007",
        "resolution_useful_votes": 15
    },
    {
        "ticket_id": "INC-1021",
        "title": "Outlook calendar invites show incorrect time zone after daylight savings shift",
        "description": "Outlook calendar appointments appear one hour off on Outlook Web App and desktop client.",
        "symptoms": "Calendar event time shift, time zone mismatch.",
        "category": "Collaboration & Email",
        "subcategory": "Microsoft 365 / Outlook",
        "priority": "P3 - Medium",
        "intent": "Mailbox Time Zone Alignment",
        "affected_service": "Exchange Online / Outlook 365",
        "environment": "Production",
        "assignment_group": "Workplace-Support",
        "status": "Resolved",
        "created_at": "2026-10-30T08:30:00Z",
        "resolved_at": "2026-10-30T09:00:00Z",
        "root_cause": "Mailbox regional settings in Exchange Online were set to GMT while client OS was in EST.",
        "resolution_summary": "Aligned Exchange Online mailbox time zone configuration via PowerShell Set-MailboxRegionalConfiguration.",
        "resolution_steps": "Ran Set-MailboxRegionalConfiguration -Identity user@corp.com -TimeZone 'Eastern Standard Time'. Calendar synced properly.",
        "linked_kb_id": "KB-2004",
        "resolution_useful_votes": 8
    },
    {
        "ticket_id": "INC-1022",
        "title": "Dell Thunderbolt dock audio jack emits static buzzing noise",
        "description": "Headphones connected to Dell WD19 docking station 3.5mm jack emit constant high pitched buzzing noise.",
        "symptoms": "Audio noise, ground loop interference through dock audio jack.",
        "category": "Hardware & Workplace Support",
        "subcategory": "Peripherals & Docks",
        "priority": "P4 - Low",
        "intent": "Dock Audio Ground Loop Fix",
        "affected_service": "Dell WD19 / WD22TB Docks",
        "environment": "Corporate",
        "assignment_group": "Desktop-Support",
        "status": "Resolved",
        "created_at": "2026-10-30T10:00:00Z",
        "resolved_at": "2026-10-30T10:30:00Z",
        "root_cause": "Ground loop interference from ungrounded secondary AC power strip.",
        "resolution_summary": "Plugged dock power supply directly into grounded surge protector and updated Realtek audio driver.",
        "resolution_steps": "Moved power brick to surge suppressor, reinstalled Realtek USB Audio driver, noise eliminated.",
        "linked_kb_id": "KB-2008",
        "resolution_useful_votes": 5
    },
    {
        "ticket_id": "INC-1023",
        "title": "Marketing automation tool cannot connect to Salesforce API: Bad OAuth token",
        "description": "Marketo sync job failing with 401 Unauthorized when pushing leads into Salesforce.",
        "symptoms": "OAuth invalid token response, lead sync blocked.",
        "category": "Enterprise Applications",
        "subcategory": "Salesforce CRM",
        "priority": "P2 - High",
        "intent": "Salesforce Connected App OAuth Refresh",
        "affected_service": "Salesforce",
        "environment": "Production",
        "assignment_group": "CRM-Ops",
        "status": "Resolved",
        "created_at": "2026-10-30T11:15:00Z",
        "resolved_at": "2026-10-30T11:55:00Z",
        "root_cause": "Connected app refresh token expired due to 90-day inactivity policy.",
        "resolution_summary": "Re-authorized Marketo Connected App in Salesforce and generated new OAuth refresh token.",
        "resolution_steps": "Logged into Salesforce Connected Apps, refreshed OAuth tokens, updated Marketo API integration credentials.",
        "linked_kb_id": "KB-2009",
        "resolution_useful_votes": 13
    },
    {
        "ticket_id": "INC-1024",
        "title": "Docker build step on GitLab CI failing with 'no space left on device'",
        "description": "Pipelines on runner-02 are failing during 'docker build' command due to full disk partition.",
        "symptoms": "ENOSPC error in CI console, runner storage exhausted.",
        "category": "Developer Tools & DevOps",
        "subcategory": "GitLab / CI/CD",
        "priority": "P2 - High",
        "intent": "CI Runner Storage Maintenance",
        "affected_service": "GitLab Shared Runners",
        "environment": "Production",
        "assignment_group": "DevOps-Support",
        "status": "Resolved",
        "created_at": "2026-10-30T13:00:00Z",
        "resolved_at": "2026-10-30T13:30:00Z",
        "root_cause": "Accumulation of untagged intermediate Docker images on runner host.",
        "resolution_summary": "Ran docker system prune -af to clear 65GB of dangling layers and scheduled nightly cleanup cron.",
        "resolution_steps": "Executed docker system prune -af --volumes on runner-02. Configured weekly cron job for automated image pruning.",
        "linked_kb_id": "KB-2010",
        "resolution_useful_votes": 19
    },
    {
        "ticket_id": "INC-1025",
        "title": "Oracle database connections hanging during morning batch report",
        "description": "Financial analytics queries running into ORA-00018 maximum sessions exceeded error.",
        "symptoms": "ORA-00018 error, connection pool exhausted.",
        "category": "Cloud & Infrastructure",
        "subcategory": "Database & Storage",
        "priority": "P2 - High",
        "intent": "Database Connection Pool Optimization",
        "affected_service": "Oracle Database 19c",
        "environment": "Production",
        "assignment_group": "Cloud-Ops",
        "status": "Resolved",
        "created_at": "2026-10-30T14:10:00Z",
        "resolved_at": "2026-10-30T14:50:00Z",
        "root_cause": "Stale connections not being released by unclosed SqlSession in reporting service.",
        "resolution_summary": "Terminated idle sessions and adjusted connection pool idle timeout in HikariCP.",
        "resolution_steps": "Executed ALTER SYSTEM KILL SESSION on inactive connections, patched HikariCP idleTimeout to 5 minutes.",
        "linked_kb_id": "KB-2011",
        "resolution_useful_votes": 11
    },
    {
        "ticket_id": "INC-1026",
        "title": "GlobalProtect VPN connection drops every 60 minutes continuously",
        "description": "User in EMEA office is disconnected from GlobalProtect VPN exactly once every hour. Has to manually reconnect.",
        "symptoms": "VPN session hourly disconnection, tunnel re-authentication failure.",
        "category": "Network & Connectivity",
        "subcategory": "VPN",
        "priority": "P3 - Medium",
        "intent": "VPN Session Lifetime Adjustment",
        "affected_service": "GlobalProtect",
        "environment": "Production",
        "assignment_group": "NetOps-Support",
        "status": "Resolved",
        "created_at": "2026-10-30T15:20:00Z",
        "resolved_at": "2026-10-30T16:00:00Z",
        "root_cause": "User was mapped to temporary contractor portal gateway with 1-hour session timeout instead of standard 8-hour employee policy.",
        "resolution_summary": "Updated user AD group membership to Employee-VPN-Access and refreshed gateway mapping.",
        "resolution_steps": "Corrected Active Directory security group assignment, user re-logged into GlobalProtect with full 8-hour session lifetime.",
        "linked_kb_id": "KB-2002",
        "resolution_useful_votes": 10
    },
    {
        "ticket_id": "INC-1027",
        "title": "Printer on 4th floor finance wing offline and not responding to print jobs",
        "description": "HP LaserJet Enterprise MFP in 4th floor finance department shows offline in Windows print queue.",
        "symptoms": "Spooler jobs backed up, printer unreachable over IP.",
        "category": "Hardware & Workplace Support",
        "subcategory": "Printing Services",
        "priority": "P3 - Medium",
        "intent": "Print Spooler & Network Reset",
        "affected_service": "Enterprise Print Services",
        "environment": "Corporate",
        "assignment_group": "Desktop-Support",
        "status": "Resolved",
        "created_at": "2026-10-30T16:30:00Z",
        "resolved_at": "2026-10-30T17:00:00Z",
        "root_cause": "DHCP reservation lease expired causing printer to acquire a new IP address not matching DNS record.",
        "resolution_summary": "Reserved static IP on DHCP server for printer MAC address and updated Windows print server port.",
        "resolution_steps": "Bound MAC address to static reservation, updated standard TCP/IP port on print server, cleared pending print spooler queue.",
        "linked_kb_id": "KB-2008",
        "resolution_useful_votes": 6
    },
    {
        "ticket_id": "INC-1028",
        "title": "Active Directory account locked after changing password on Windows laptop",
        "description": "User changed domain password on corporate laptop, but iPhone with Outlook app keeps attempting login with old password and locks account.",
        "symptoms": "Immediate AD lockout after password reset.",
        "category": "Identity & Access Management",
        "subcategory": "Active Directory",
        "priority": "P2 - High",
        "intent": "Mobile ActiveSync Stale Credential Fix",
        "affected_service": "Active Directory Domain Services",
        "environment": "Production",
        "assignment_group": "IAM-Support",
        "status": "Resolved",
        "created_at": "2026-10-30T17:15:00Z",
        "resolved_at": "2026-10-30T17:45:00Z",
        "root_cause": "iOS Mail app caching previous password and spamming Exchange ActiveSync endpoint.",
        "resolution_summary": "Updated password in iOS Settings > Mail > Accounts and unlocked AD account.",
        "resolution_steps": "Guided user to re-enter updated password on iPhone, verified Event 4740 ceased, unlocked AD account.",
        "linked_kb_id": "KB-2006",
        "resolution_useful_votes": 22
    },
    {
        "ticket_id": "INC-1029",
        "title": "Workday time tracking module won't load for hourly contractors",
        "description": "Contractor employees cannot enter weekly timesheet hours. Workday page spins indefinitely.",
        "symptoms": "Workday page loading hang, spinner icon.",
        "category": "Enterprise Applications",
        "subcategory": "Workday HRIS",
        "priority": "P2 - High",
        "intent": "Workday Time Tracking Permission Fix",
        "affected_service": "Workday",
        "environment": "Production",
        "assignment_group": "Enterprise-Apps-Team",
        "status": "Resolved",
        "created_at": "2026-10-30T18:00:00Z",
        "resolved_at": "2026-10-30T18:40:00Z",
        "root_cause": "Contractor eligibility rule had an outdated expiration date in Workday Time & Absence domain security policy.",
        "resolution_summary": "Extended contractor eligibility window in Workday Time Tracking policy and activated pending changes.",
        "resolution_steps": "Edited Time & Absence domain security policy in Workday, activated pending security policy changes, confirmed contractors can log hours.",
        "linked_kb_id": "KB-2014",
        "resolution_useful_votes": 12
    },
    {
        "ticket_id": "INC-1030",
        "title": "Cannot push commits to GitHub enterprise due to SSH key permission denied",
        "description": "Developer receives 'Permission denied (publickey)' when attempting git push origin main to GitHub Enterprise repo.",
        "symptoms": "SSH auth rejection, permission denied publickey.",
        "category": "Developer Tools & DevOps",
        "subcategory": "GitHub & Version Control",
        "priority": "P3 - Medium",
        "intent": "SSH Key Pair Verification & Upload",
        "affected_service": "GitHub Enterprise",
        "environment": "Development",
        "assignment_group": "DevOps-Support",
        "status": "Resolved",
        "created_at": "2026-10-30T19:00:00Z",
        "resolved_at": "2026-10-30T19:30:00Z",
        "root_cause": "Developer generated a new ED25519 key on new laptop but did not upload public key to GitHub Enterprise profile.",
        "resolution_summary": "Instructed user to add public key ~/.ssh/id_ed25519.pub to GitHub Enterprise user settings.",
        "resolution_steps": "Guided developer to copy ~/.ssh/id_ed25519.pub, paste into GitHub Enterprise > Settings > SSH Keys, and verified connection via ssh -T git@github.corp.",
        "linked_kb_id": "KB-2010",
        "resolution_useful_votes": 14
    }
]

# ==============================================================================
# INCOMING EVALUATION TEST TICKETS (20 Ground-Truth Labeled Test Cases)
# ==============================================================================
INCOMING_TEST_TICKETS = [
    {
        "test_ticket_id": "TC-3001",
        "title": "Okta push notification never arrives on my phone, connection times out",
        "description": "Hi IT team, I am trying to sign into Workday and Okta says 'Push notification sent', but my phone never buzzes. After a minute it says request timed out. I already restarted my phone.",
        "affected_service": "Okta Verify",
        "environment": "Production",
        "user_role": "Analyst",
        "assignment_group": "IAM-Support",
        # Evaluation Ground Truth:
        "expected_category": "Identity & Access Management",
        "expected_subcategory": "MFA / 2FA",
        "expected_priority": "P3 - Medium",
        "expected_intent": "MFA Troubleshooting & Re-enrollment",
        "is_duplicate": True,
        "duplicate_of_ticket_id": "INC-1001",
        "expected_kb_id": "KB-2001",
        "expected_resolution_summary": "Reset Okta Verify authenticator in Okta Admin Console and re-enroll device with a new QR code.",
        "should_fallback": False,
        "test_scenario_notes": "Paraphrased duplicate of INC-1001. Tests semantic duplicate retrieval and KB-2001 resolution extraction."
    },
    {
        "test_ticket_id": "TC-3002",
        "title": "GlobalProtect VPN stuck on 'Connecting' - Could not connect to gateway",
        "description": "Cannot connect to company network from home today. The Palo Alto GlobalProtect client says 'Could not connect to gateway'. I am on home Wi-Fi and internet is working fine.",
        "affected_service": "GlobalProtect",
        "environment": "Production",
        "user_role": "Software Engineer",
        "assignment_group": "NetOps-Support",
        # Evaluation Ground Truth:
        "expected_category": "Network & Connectivity",
        "expected_subcategory": "VPN",
        "expected_priority": "P2 - High",
        "expected_intent": "VPN Connection Repair",
        "is_duplicate": True,
        "duplicate_of_ticket_id": "INC-1002",
        "expected_kb_id": "KB-2002",
        "expected_resolution_summary": "Flush DNS (ipconfig /flushdns), clear PanGPS cache folder under %LOCALAPPDATA%, and restart PanGPS service.",
        "should_fallback": False,
        "test_scenario_notes": "Direct match for VPN gateway connection failure. High similarity to INC-1002 and INC-1012."
    },
    {
        "test_ticket_id": "TC-3003",
        "title": "SAP GUI session abruptly dropped with WSAECONNRESET error",
        "description": "During our quarterly financial closing run, my SAP session kicked me out with 'WSAECONNRESET: Connection reset by peer'. Lost 45 minutes of work.",
        "affected_service": "SAP ECC / S4HANA",
        "environment": "Production",
        "user_role": "Finance Controller",
        "assignment_group": "SAP-Core-Support",
        # Evaluation Ground Truth:
        "expected_category": "Enterprise Applications",
        "expected_subcategory": "SAP ERP",
        "expected_priority": "P2 - High",
        "expected_intent": "SAP Session Drop & Optimization",
        "is_duplicate": True,
        "duplicate_of_ticket_id": "INC-1003",
        "expected_kb_id": "KB-2003",
        "expected_resolution_summary": "Set SAP GUI connection profile to Slow WAN mode and execute long reports in background mode (F9).",
        "should_fallback": False,
        "test_scenario_notes": "Enterprise application issue testing distinction between network infrastructure and SAP application session handling."
    },
    {
        "test_ticket_id": "TC-3004",
        "title": "Outlook desktop client keeps asking for password every 5 minutes",
        "description": "My Outlook has a yellow warning icon at the bottom showing 'Need Password'. When I enter my password, it disappears and then pops back up 5 minutes later.",
        "affected_service": "Exchange Online / Outlook 365",
        "environment": "Production",
        "user_role": "HR Manager",
        "assignment_group": "Workplace-Support",
        # Evaluation Ground Truth:
        "expected_category": "Collaboration & Email",
        "expected_subcategory": "Microsoft 365 / Outlook",
        "expected_priority": "P3 - Medium",
        "expected_intent": "Modern Auth Token Reset",
        "is_duplicate": True,
        "duplicate_of_ticket_id": "INC-1004",
        "expected_kb_id": "KB-2004",
        "expected_resolution_summary": "Clear MicrosoftOffice16 cached tokens in Windows Credential Manager and re-authenticate via Windows Accounts.",
        "should_fallback": False,
        "test_scenario_notes": "Common office collaboration issue. Tests retrieval against Credential Manager solutions."
    },
    {
        "test_ticket_id": "TC-3005",
        "title": "Terraform apply failing with AccessDenied on s3:PutObject for deployment bucket",
        "description": "Our AWS production release pipeline is halted. Terraform output shows: 'Error: putting S3 object: AccessDenied: User: arn:aws:iam::123456789012:role/cd-deploy-role is not authorized to perform: s3:PutObject with an explicit deny'.",
        "affected_service": "AWS Cloud Services",
        "environment": "Production",
        "user_role": "DevOps Engineer",
        "assignment_group": "Cloud-Ops",
        # Evaluation Ground Truth:
        "expected_category": "Cloud & Infrastructure",
        "expected_subcategory": "AWS IAM / S3",
        "expected_priority": "P1 - Critical",
        "expected_intent": "AWS IAM & KMS Permission Grant",
        "is_duplicate": True,
        "duplicate_of_ticket_id": "INC-1005",
        "expected_kb_id": "KB-2005",
        "expected_resolution_summary": "Inspect S3 bucket policy and add kms:GenerateDataKey/kms:Decrypt permissions to the KMS key policy for the deploy role.",
        "should_fallback": False,
        "test_scenario_notes": "Critical P1 incident blocking production deployment. Tests high-confidence resolution extraction."
    },
    {
        "test_ticket_id": "TC-3006",
        "title": "Account locked out repeatedly without doing anything",
        "description": "My Windows account keeps locking out while I am working. Support unlocked it 30 mins ago and it just locked out again. I haven't entered my password wrong.",
        "affected_service": "Active Directory Domain Services",
        "environment": "Production",
        "user_role": "Marketing Director",
        "assignment_group": "IAM-Support",
        # Evaluation Ground Truth:
        "expected_category": "Identity & Access Management",
        "expected_subcategory": "Active Directory",
        "expected_priority": "P2 - High",
        "expected_intent": "AD Account Lockout Source Remediation",
        "is_duplicate": True,
        "duplicate_of_ticket_id": "INC-1006",
        "expected_kb_id": "KB-2006",
        "expected_resolution_summary": "Trace calling machine via Event 4740 in Domain Controller Security log, remove cached stale credentials on that host, then unlock AD account.",
        "should_fallback": False,
        "test_scenario_notes": "Tests duplicate detection against recurring lockout patterns (INC-1006 and INC-1028)."
    },
    {
        "test_ticket_id": "TC-3007",
        "title": "Auth pod crash looping with Exit Code 137 OOMKilled in prod",
        "description": "The authentication microservice pod in k8s prod cluster keeps dying and restarting with CrashLoopBackOff. 'kubectl describe pod' indicates Reason: OOMKilled, Exit Code: 137.",
        "affected_service": "EKS / GKE Clusters",
        "environment": "Production",
        "user_role": "SRE Lead",
        "assignment_group": "Cloud-Ops",
        # Evaluation Ground Truth:
        "expected_category": "Cloud & Infrastructure",
        "expected_subcategory": "Kubernetes / Containers",
        "expected_priority": "P1 - Critical",
        "expected_intent": "Kubernetes Resource Scaling",
        "is_duplicate": True,
        "duplicate_of_ticket_id": "INC-1007",
        "expected_kb_id": "KB-2007",
        "expected_resolution_summary": "Increase container memory limit in Helm deployment manifest and tune JVM MaxRAMPercentage parameter.",
        "should_fallback": False,
        "test_scenario_notes": "P1 outage ticket testing fast resolution recommendation and container log tracing."
    },
    {
        "test_ticket_id": "TC-3008",
        "title": "Dell dock monitors flashing black intermittently throughout the day",
        "description": "My two external monitors connected to the Dell Thunderbolt dock keep flickering to a black screen for a couple seconds and coming back on.",
        "affected_service": "Dell WD19 / WD22TB Docks",
        "environment": "Corporate",
        "user_role": "Product Manager",
        "assignment_group": "Desktop-Support",
        # Evaluation Ground Truth:
        "expected_category": "Hardware & Workplace Support",
        "expected_subcategory": "Peripherals & Docks",
        "expected_priority": "P3 - Medium",
        "expected_intent": "Dock Firmware & Refresh Rate Configuration",
        "is_duplicate": True,
        "duplicate_of_ticket_id": "INC-1008",
        "expected_kb_id": "KB-2008",
        "expected_resolution_summary": "Update Dell Dock MST firmware via Dell Update Utility and configure monitor refresh rate to static 60.00Hz.",
        "should_fallback": False,
        "test_scenario_notes": "Workplace hardware troubleshooting test case matching INC-1008."
    },
    {
        "test_ticket_id": "TC-3009",
        "title": "Sales reps getting SAML SSO error when opening Salesforce",
        "description": "Multiple sales reps reporting that they cannot log in to Salesforce CRM. The screen says 'Single Sign-On Error - We cannot log you in because of an issue with single sign-on'.",
        "affected_service": "Salesforce",
        "environment": "Production",
        "user_role": "Sales Operations",
        "assignment_group": "CRM-Ops",
        # Evaluation Ground Truth:
        "expected_category": "Enterprise Applications",
        "expected_subcategory": "Salesforce CRM",
        "expected_priority": "P1 - Critical",
        "expected_intent": "SAML SSO Certificate Renewal",
        "is_duplicate": True,
        "duplicate_of_ticket_id": "INC-1009",
        "expected_kb_id": "KB-2009",
        "expected_resolution_summary": "Upload renewed IdP SAML certificate in Salesforce Single Sign-On Settings.",
        "should_fallback": False,
        "test_scenario_notes": "High priority incident affecting an entire department. Tests duplicate clustering against INC-1009."
    },
    {
        "test_ticket_id": "TC-3010",
        "title": "GitLab CI runner disk full - pipelines blocked",
        "description": "Our build jobs are stuck on runner-03. Logs show: 'write /var/lib/docker: no space left on device'. Need someone to clear the runner cache.",
        "affected_service": "GitLab Shared Runners",
        "environment": "Production",
        "user_role": "Backend Engineer",
        "assignment_group": "DevOps-Support",
        # Evaluation Ground Truth:
        "expected_category": "Developer Tools & DevOps",
        "expected_subcategory": "GitLab / CI/CD",
        "expected_priority": "P2 - High",
        "expected_intent": "CI Runner Storage Maintenance",
        "is_duplicate": True,
        "duplicate_of_ticket_id": "INC-1010",
        "expected_kb_id": "KB-2010",
        "expected_resolution_summary": "SSH into runner, run 'docker system prune -af --volumes' to free disk space, and restart gitlab-runner service.",
        "should_fallback": False,
        "test_scenario_notes": "DevOps infrastructure maintenance case matching INC-1010 and INC-1024."
    },
    {
        "test_ticket_id": "TC-3011",
        "title": "Database connection pool saturated with ORA-00018 errors",
        "description": "Our backend payment gateway services are throwing ORA-00018: maximum number of sessions exceeded. Client requests are receiving 504 gateway timeout.",
        "affected_service": "Oracle Database 19c",
        "environment": "Production",
        "user_role": "Database Administrator",
        "assignment_group": "Cloud-Ops",
        # Evaluation Ground Truth:
        "expected_category": "Cloud & Infrastructure",
        "expected_subcategory": "Database & Storage",
        "expected_priority": "P1 - Critical",
        "expected_intent": "Database Connection Pool Optimization",
        "is_duplicate": True,
        "duplicate_of_ticket_id": "INC-1013",
        "expected_kb_id": "KB-2011",
        "expected_resolution_summary": "Query v$session to locate leaked JDBC sessions, terminate inactive sessions, and tune HikariCP maxLifetime/idleTimeout.",
        "should_fallback": False,
        "test_scenario_notes": "Direct duplicate of INC-1013 and INC-1025. Demonstrates duplicate ranking across database alerts."
    },
    {
        "test_ticket_id": "TC-3012",
        "title": "No sound from microphone in Microsoft Teams calls",
        "description": "I joined a company all-hands and nobody could hear me on Microsoft Teams. My headset is plugged in and works in Spotify.",
        "affected_service": "Microsoft Teams Client",
        "environment": "Corporate",
        "user_role": "Account Executive",
        "assignment_group": "Workplace-Support",
        # Evaluation Ground Truth:
        "expected_category": "Collaboration & Email",
        "expected_subcategory": "Microsoft Teams",
        "expected_priority": "P3 - Medium",
        "expected_intent": "Teams Audio Device Configuration",
        "is_duplicate": True,
        "duplicate_of_ticket_id": "INC-1014",
        "expected_kb_id": "KB-2012",
        "expected_resolution_summary": "Verify Windows Microphone Privacy Settings for desktop apps and disable exclusive control in Sound Control Panel.",
        "should_fallback": False,
        "test_scenario_notes": "Semantic duplicate of INC-1014. Tests peripheral audio troubleshooting."
    },
    {
        "test_ticket_id": "TC-3013",
        "title": "Unable to connect to Corp-Secure Wi-Fi on laptop",
        "description": "My Windows laptop keeps prompting 'Can't connect to this network' whenever I select Corp-Secure in the Chicago office.",
        "affected_service": "Enterprise Wi-Fi (Corp-Secure)",
        "environment": "Corporate",
        "user_role": "Consultant",
        "assignment_group": "NetOps-Support",
        # Evaluation Ground Truth:
        "expected_category": "Network & Connectivity",
        "expected_subcategory": "Wi-Fi & LAN",
        "expected_priority": "P3 - Medium",
        "expected_intent": "Wi-Fi 802.1X Certificate Verification",
        "is_duplicate": True,
        "duplicate_of_ticket_id": "INC-1015",
        "expected_kb_id": "KB-2013",
        "expected_resolution_summary": "Verify Corp-Internal-Root-CA certificate in certmgr.msc, run 'gpupdate /force' to pull updated RADIUS certs, and reconnect.",
        "should_fallback": False,
        "test_scenario_notes": "Tests 802.1X corporate certificate troubleshooting retrieval."
    },
    {
        "test_ticket_id": "TC-3014",
        "title": "Blue screen crash DRIVER_IRQL_NOT_LESS_OR_EQUAL on laptop wake",
        "description": "Every time my PC wakes up from sleep or when I open the lid, it crashes with blue screen pointing to NETIO.SYS.",
        "affected_service": "Windows 11 Workstations",
        "environment": "Corporate",
        "user_role": "Data Scientist",
        "assignment_group": "Desktop-Support",
        # Evaluation Ground Truth:
        "expected_category": "Hardware & Workplace Support",
        "expected_subcategory": "OS / Blue Screen BSOD",
        "expected_priority": "P2 - High",
        "expected_intent": "Network Driver BSOD Remediation",
        "is_duplicate": True,
        "duplicate_of_ticket_id": "INC-1017",
        "expected_kb_id": "KB-2015",
        "expected_resolution_summary": "Update Intel Wi-Fi / Ethernet adapter driver to latest enterprise package v22.250+ and run 'sfc /scannow'.",
        "should_fallback": False,
        "test_scenario_notes": "Matches INC-1017 BSOD minidump issue and KB-2015 runbook."
    },
    {
        "test_ticket_id": "TC-3015",
        "title": "Request read access to AWS S3 bucket for training data",
        "description": "Please grant my IAM role read access to s3://prod-analytics-features/ for our model training pipeline.",
        "affected_service": "AWS Cloud Services",
        "environment": "Production",
        "user_role": "ML Engineer",
        "assignment_group": "IAM-Support",
        # Evaluation Ground Truth:
        "expected_category": "Identity & Access Management",
        "expected_subcategory": "Application Access Request",
        "expected_priority": "P4 - Low",
        "expected_intent": "Access Request Fulfillment",
        "is_duplicate": False,
        "duplicate_of_ticket_id": None,
        "expected_kb_id": "KB-2005",
        "expected_resolution_summary": "Direct user to submit access request via IAM self-service portal with manager sign-off.",
        "should_fallback": False,
        "test_scenario_notes": "Non-incident standard service access request. Distinguishes access grant requests from AWS S3 permission errors."
    },
    # --- CRITICAL EVALUATION EDGE CASES: LOW CONFIDENCE / AMBIGUITY / FALLBACK (FR-05) ---
    {
        "test_ticket_id": "TC-3016",
        "title": "System not working properly please fix ASAP",
        "description": "The application crashed with an error on screen. It was blue and had text. Can someone take a look? Urgent.",
        "affected_service": "Unknown",
        "environment": "Unknown",
        "user_role": "Business User",
        "assignment_group": "Triage-Queue",
        # Evaluation Ground Truth:
        "expected_category": "Hardware & Workplace Support",
        "expected_subcategory": "Needs Clarification",
        "expected_priority": "P3 - Medium",
        "expected_intent": "Clarification Required",
        "is_duplicate": False,
        "duplicate_of_ticket_id": None,
        "expected_kb_id": None,
        "expected_resolution_summary": None,
        "should_fallback": True,
        "test_scenario_notes": "FR-05 CORE TEST: Extremely vague description. System must flag confidence score < 0.50, avoid hallucinating a resolution, and route to human escalation / clarification."
    },
    {
        "test_ticket_id": "TC-3017",
        "title": "Spilled coffee on laptop keyboard, device won't turn on",
        "description": "Accidentally spilled hot coffee over my ThinkPad keyboard. Powered it down immediately. When plugging in charger, power LED blinks 3 times orange and device is completely unresponsive.",
        "affected_service": "Lenovo ThinkPad",
        "environment": "Corporate",
        "user_role": "Operations Manager",
        "assignment_group": "Desktop-Support",
        # Evaluation Ground Truth:
        "expected_category": "Hardware & Workplace Support",
        "expected_subcategory": "Laptop Hardware Damage",
        "expected_priority": "P2 - High",
        "expected_intent": "Hardware Replacement / Depot Repair",
        "is_duplicate": False,
        "duplicate_of_ticket_id": None,
        "expected_kb_id": None,
        "expected_resolution_summary": "Do not attempt to power on laptop. Dispatch physical hardware replacement and schedule depot collection.",
        "should_fallback": True,
        "test_scenario_notes": "Physical hardware damage requiring depot repair. Verifies that software runbooks are NOT recommended and physical dispatch escalation is triggered."
    },
    {
        "test_ticket_id": "TC-3018",
        "title": "Novel error code ERR_QUIC_PROTOCOL_ERROR on internal analytics dashboard",
        "description": "Opening our internal analytics portal at https://analytics.corp.internal returns ERR_QUIC_PROTOCOL_ERROR on Chrome 129. Firefox works fine.",
        "affected_service": "Internal Web Apps",
        "environment": "Production",
        "user_role": "Data Analyst",
        "assignment_group": "NetOps-Support",
        # Evaluation Ground Truth:
        "expected_category": "Network & Connectivity",
        "expected_subcategory": "DNS / Routing",
        "expected_priority": "P3 - Medium",
        "expected_intent": "Browser QUIC Configuration",
        "is_duplicate": False,
        "duplicate_of_ticket_id": None,
        "expected_kb_id": None,
        "expected_resolution_summary": "Disable 'Experimental QUIC protocol' in chrome://flags or clear browser network cache.",
        "should_fallback": True,
        "test_scenario_notes": "Novel bug with zero historical tickets. Tests system capability to recognize absence of historical precedent and declare fallback."
    },
    {
        "test_ticket_id": "TC-3019",
        "title": "Supervisor cannot approve timecards due to blank Workday page",
        "description": "When clicking 'Approve Timecards' in Workday, the iframe remains completely blank with a spinning wheel. Other Workday tabs work normally.",
        "affected_service": "Workday",
        "environment": "Production",
        "user_role": "Store Manager",
        "assignment_group": "Enterprise-Apps-Team",
        # Evaluation Ground Truth:
        "expected_category": "Enterprise Applications",
        "expected_subcategory": "Workday HRIS",
        "expected_priority": "P2 - High",
        "expected_intent": "Workday Time Tracking Permission Fix",
        "is_duplicate": True,
        "duplicate_of_ticket_id": "INC-1029",
        "expected_kb_id": "KB-2014",
        "expected_resolution_summary": "Inspect Workday Time & Absence domain security policy and extend supervisor delegation permissions.",
        "should_fallback": False,
        "test_scenario_notes": "Duplicate matching INC-1029 and INC-1016 with high confidence."
    },
    {
        "test_ticket_id": "TC-3020",
        "title": "Duplicate: Palo Alto GlobalProtect gateway timeout on MacOS Sonoma",
        "description": "My GlobalProtect client fails with 'Could not connect to gateway' after MFA on macOS Sonoma. Need to access corporate staging server.",
        "affected_service": "GlobalProtect",
        "environment": "Production",
        "user_role": "iOS Developer",
        "assignment_group": "NetOps-Support",
        # Evaluation Ground Truth:
        "expected_category": "Network & Connectivity",
        "expected_subcategory": "VPN",
        "expected_priority": "P2 - High",
        "expected_intent": "VPN Connection Repair",
        "is_duplicate": True,
        "duplicate_of_ticket_id": "INC-1002",
        "expected_kb_id": "KB-2002",
        "expected_resolution_summary": "Flush DNS, clear GlobalProtect PanGPS cache directory, and restart PanGPS service.",
        "should_fallback": False,
        "test_scenario_notes": "Multi-ticket duplicate cluster test case (matches INC-1002, INC-1012, TC-3002)."
    }
]

# ==============================================================================
# WRITER UTILITIES
# ==============================================================================
def save_json(filepath, data):
    """Write data as formatted JSON."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  [+] Saved JSON: {filepath} ({len(data) if isinstance(data, list) else len(data.keys())} items)")

def save_csv(filepath, data):
    """Write list of dicts to CSV, serializing nested objects to JSON strings."""
    if not data or not isinstance(data, list):
        return
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    keys = list(data[0].keys())
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in data:
            clean_row = {}
            for k, v in row.items():
                if isinstance(v, (list, dict)):
                    clean_row[k] = json.dumps(v, ensure_ascii=False)
                else:
                    clean_row[k] = v
            writer.writerow(clean_row)
    print(f"  [+] Saved CSV:  {filepath} ({len(data)} rows)")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic datasets for Intelligent IT Ticket Analysis and Resolution Assistant."
    )
    parser.add_argument(
        "--output-dir",
        default="data",
        help="Directory to save generated datasets (default: ./data)"
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv", "both"],
        default="both",
        help="Output format to produce (default: both)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic generation (default: 42)"
    )

    args = parser.parse_args()
    random.seed(args.seed)

    output_dir = os.path.abspath(args.output_dir)
    print("=" * 75)
    print("  HCLTech Hackathon: IT Ticket Analysis & Resolution Assistant Data Generator")
    print(f"  Target Output Directory: {output_dir}")
    print(f"  Format: {args.format.upper()}")
    print("=" * 75)

    os.makedirs(output_dir, exist_ok=True)

    # 1. Save Taxonomy
    taxonomy_path = os.path.join(output_dir, "taxonomy.json")
    save_json(taxonomy_path, TAXONOMY)

    # 2. Knowledge Base Articles
    if args.format in ["json", "both"]:
        save_json(os.path.join(output_dir, "kb_articles.json"), KB_ARTICLES)
    if args.format in ["csv", "both"]:
        save_csv(os.path.join(output_dir, "kb_articles.csv"), KB_ARTICLES)

    # 3. Historical Resolved Incidents
    if args.format in ["json", "both"]:
        save_json(os.path.join(output_dir, "historical_tickets.json"), HISTORICAL_TICKETS)
    if args.format in ["csv", "both"]:
        save_csv(os.path.join(output_dir, "historical_tickets.csv"), HISTORICAL_TICKETS)

    # 4. Incoming Evaluation / Test Tickets
    if args.format in ["json", "both"]:
        save_json(os.path.join(output_dir, "incoming_test_tickets.json"), INCOMING_TEST_TICKETS)
    if args.format in ["csv", "both"]:
        save_csv(os.path.join(output_dir, "incoming_test_tickets.csv"), INCOMING_TEST_TICKETS)

    print("\n" + "=" * 75)
    print("  Summary of Generated Synthetic Datasets:")
    print(f"    - Taxonomy Categories:          {len(TAXONOMY['categories'])} (with 28 distinct subcategories)")
    print(f"    - Approved Knowledge Base (KB): {len(KB_ARTICLES)} Runbooks (KB-2001 to KB-2015)")
    print(f"    - Historical Resolved Tickets:  {len(HISTORICAL_TICKETS)} Incidents (INC-1001 to INC-1030)")
    print(f"    - Evaluation Test Tickets:      {len(INCOMING_TEST_TICKETS)} Cases with Ground Truth (TC-3001 to TC-3020)")
    print("=" * 75)
    print("Data generation complete! Ready for classification, retrieval, and evaluation.\n")

if __name__ == "__main__":
    main()
