"""
IPMPRS — Intelligent Proposal Management and Precedent Retrieval System
Puducherry Police Hackathon 2026 · Problem Statement 01
────────────────────────────────────────────────────────────────────────
seed_data.py: Realistic Synthetic Proposals Dataset (48 Proposals)
Covers all 6 categories, police units, outcome clusters, rejection reasons,
post-closure lessons learned, and genuine SHA-256 cryptographic audit chains.
"""

import os
import sqlite3
import hashlib
from datetime import datetime, timedelta
import random

from proposals import (
    get_db_connection, init_proposals_db, compute_history_hash,
    GENESIS_HASH, PROPOSALS_DB_PATH
)

DEPARTMENTS = [
    "Law and Order (North)",
    "Law and Order (South)",
    "Traffic Police Headquarters",
    "Cyber Crime Police Station (CCPS)",
    "Armed Reserve (Gorimedu Complex)",
    "Police Training School (PTS Shanmugapuram)",
    "IT & Communications Cell",
    "Coastal Police / Marine Unit",
    "Headquarters & Administration"
]

CATEGORIES = [
    "Administrative",
    "Technical",
    "Procurement",
    "Infrastructure",
    "Training",
    "Operational"
]

# Raw seed blueprints
SEED_PROPOSALS = [
    # ─── CLUSTER 1: CCTV & Video Surveillance Systems ──────────────────
    {
        "ref_no": "PPH/2024/PRO/0012",
        "title": "Procurement and Installation of 140 High-Definition IP CCTV Cameras across Puducherry Town Police Stations",
        "category": "Procurement",
        "department": "IT & Communications Cell",
        "description": "Supply, installation, cabling, and 30-day NVR storage configuration for 140 IP CCTV cameras covering station entry, lockup corridors, and visitor lobbies across 14 town police stations.",
        "justification": "Compliance with Hon'ble Supreme Court directives on mandatory CCTV coverage in all police stations to enhance custodial transparency.",
        "estimated_cost": 4850000.0,
        "priority": "High",
        "status": "Closed",
        "created_by": "HC R. Kumar (DA)",
        "created_days_ago": 680,
        "decision": {
            "type": "Approve",
            "decided_by": "SP K. Vijayakumar (HQ)",
            "reason": "Approved as per Supreme Court mandate and approved state modernization budget allocation.",
            "sanction_no": "PPH/SEC/2024/091",
            "sanctioned_amount": 4720000.0,
            "conditions": "Procurement strictly through GeM portal with 3-year OEM warranty on cameras and NVR units."
        },
        "outcome": {
            "status": "Completed Successfully",
            "actual_cost": 4690000.0,
            "summary": "140 cameras deployed and integrated with Central Command Control Room (CCCR) Gorimedu.",
            "lessons_learned": "Optical fiber cabling in coastal stations experienced salt corrosion within 8 months. Future tenders must specify IP67 weatherproof enclosures and marine-grade armored fiber."
        },
        "remarks": [
            ("HC R. Kumar", "Initiator", "Vendor quotation comparison sheet from GeM attached."),
            ("Insp. S. Anand", "Reviewer", "Site survey completed for all 14 stations. Network bandwidth adequate."),
            ("SP K. Vijayakumar", "Approving Authority", "Sanction accorded under MHA Police Modernization scheme.")
        ]
    },
    {
        "ref_no": "PPH/2024/PRO/0045",
        "title": "Procurement of 320 Solar-Powered 4K CCTV Cameras with 5-Year AMC for Coastal Checkposts and Rural Stations",
        "category": "Procurement",
        "department": "Coastal Police / Marine Unit",
        "description": "Procurement of 320 standalone solar-powered 4K surveillance cameras with 4G SIM streaming for 32 remote coastal checkposts and rural beat points.",
        "justification": "Frequent power outages in rural coastal sectors disable standard surveillance during night hours.",
        "estimated_cost": 9600000.0,
        "priority": "Medium",
        "status": "Rejected",
        "created_by": "SI G. Murugan",
        "created_days_ago": 540,
        "decision": {
            "type": "Reject",
            "decided_by": "SSP (L&O) R. Sundaram",
            "reason": "Estimated budget of ₹96L exceeded coastal security sub-head sanction ceiling by 140%. Vendor 5-year AMC cost unreasonable. Solar battery life unproven in saline marine air.",
            "sanction_no": None,
            "sanctioned_amount": 0.0,
            "conditions": "Advised to resubmit for standard solar hybrid backup on existing grid cameras instead of all-in-one proprietary units."
        },
        "remarks": [
            ("SI G. Murugan", "Initiator", "Proposal submitted for 32 coastal checkposts."),
            ("DSP K. Balan", "Reviewer", "Budget appears excessive compared to earlier PPH/2024/PRO/0012 sanction. Requires financial scrutiny."),
            ("SSP R. Sundaram", "Approving Authority", "Rejected. Exceeds allocated head of account. Explore hybrid UPS solutions.")
        ]
    },
    {
        "ref_no": "PPH/2025/TEC/0018",
        "title": "Upgradation of Traffic Junction ANPR Surveillance Cameras at Rajiv Gandhi Square and Indira Gandhi Square",
        "category": "Technical",
        "department": "Traffic Police Headquarters",
        "description": "Installation of 8 Automatic Number Plate Recognition (ANPR) cameras with optical zoom and infrared illumination for automated e-challan integration at high-density traffic junctions.",
        "justification": "Manual challaning creates traffic congestion; automated ANPR captures overspeeding and red-light violations directly into NIC e-Challan portal.",
        "estimated_cost": 3200000.0,
        "priority": "High",
        "status": "Approved",
        "created_by": "Insp. M. Rajendran",
        "created_days_ago": 260,
        "decision": {
            "type": "Approve with Modification",
            "decided_by": "SSP (Traffic) C. Mohan",
            "reason": "Approved with scope modification: reduced from 12 junction lanes to 6 critical approaches as pilot. Integration with NIC VAHAN/SARATHI database mandatory.",
            "sanction_no": "PPH/TRF/2025/034",
            "sanctioned_amount": 2400000.0,
            "conditions": "Vendor must demonstrate 95%+ plate recognition accuracy in night rain conditions before final signoff."
        },
        "remarks": [
            ("Insp. M. Rajendran", "Initiator", "Detailed project report prepared in consultation with SMART City engineers."),
            ("SP Traffic", "Reviewer", "Recommend pilot approval on 2 major roundabouts before union territory-wide expansion."),
            ("SSP C. Mohan", "Approving Authority", "Approved with modification for 6 lanes at ₹24 Lakhs.")
        ]
    },
    {
        "ref_no": "PPH/2025/PRO/0088",
        "title": "Installation of Night-Vision PTZ Cameras at Gorimedu and Villianur Outposts",
        "category": "Procurement",
        "department": "Law and Order (North)",
        "description": "Installation of 12 Pan-Tilt-Zoom (PTZ) 360-degree infrared cameras at sensitive border checkposts at Gorimedu and Villianur.",
        "justification": "Night patrolling requires wide-area perimeter monitoring to curb illicit liquor movement and inter-state contraband smuggling.",
        "estimated_cost": 1850000.0,
        "priority": "Medium",
        "status": "Implemented",
        "created_by": "SI T. Saravanan",
        "created_days_ago": 180,
        "decision": {
            "type": "Approve",
            "decided_by": "SP (North) V. Manikandan",
            "reason": "Essential for border checkpost perimeter security and round-the-clock vehicle tracking.",
            "sanction_no": "PPH/LNO/2025/112",
            "sanctioned_amount": 1800000.0,
            "conditions": "PTZ feeds must stream to North Sub-Division Control Room."
        },
        "outcome": {
            "status": "Completed with Delay",
            "actual_cost": 1790000.0,
            "summary": "Cameras installed and functional. Vendor delayed delivery of PTZ joystick controllers by 6 weeks.",
            "lessons_learned": "Enforce liquidated damages penalty in contract clauses for delayed component delivery."
        },
        "remarks": [
            ("SI T. Saravanan", "Initiator", "Site readiness confirmed at Gorimedu checkpost."),
            ("DSP North", "Reviewer", "Recommended for approval."),
            ("SP Manikandan", "Approving Authority", "Sanctioned.")
        ]
    },

    # ─── CLUSTER 2: Patrol Vehicles & Fleet Modernization ─────────────
    {
        "ref_no": "PPH/2023/PRO/0008",
        "title": "Procurement of 15 Compact SUV Patrol Vehicles for Coastal and Highway Patrolling",
        "category": "Procurement",
        "department": "Headquarters & Administration",
        "description": "Procurement of 15 diesel compact SUVs equipped with emergency light bars, public address systems, and GPS tracking units for Highway and Coastal beat patrols.",
        "justification": "Existing patrol vehicles (2012 model Boleros) have crossed 2,50,000 km with prohibitive maintenance expenditure.",
        "estimated_cost": 14250000.0,
        "priority": "Urgent",
        "status": "Closed",
        "created_by": "Insp. Motor Transport",
        "created_days_ago": 800,
        "decision": {
            "type": "Approve",
            "decided_by": "IGP Puducherry",
            "reason": "Condemnation board cleared 16 aged vehicles. Replacement sanction accorded under Police Modernization funds.",
            "sanction_no": "PPH/VEH/2023/114",
            "sanctioned_amount": 13800000.0,
            "conditions": "Vehicles purchased via DGS&D/GeM rate contracts. AIS-140 certified GPS units mandatory."
        },
        "outcome": {
            "status": "Completed with Delay",
            "actual_cost": 13750000.0,
            "summary": "15 Mahindra Scorpio patrol vehicles inducted into service across highway sectors.",
            "lessons_learned": "Third-party retrofitting of light bars and GPS trackers delayed operational induction by 4 weeks. Future tenders must require factory-fitted police equipment directly from OEM."
        },
        "remarks": [
            ("Insp. MT", "Initiator", "Condemnation certificates and log books compiled."),
            ("SP HQ", "Reviewer", "Endorsed for IGP sanction."),
            ("IGP", "Approving Authority", "Approved. Vehicles to be distributed equally between North, South, and Coastal beats.")
        ]
    },
    {
        "ref_no": "PPH/2024/PRO/0073",
        "title": "Procurement of 4 Heavy Duty Armoured Quick Reaction Vehicles for Armed Reserve",
        "category": "Procurement",
        "department": "Armed Reserve (Gorimedu Complex)",
        "description": "Acquisition of 4 custom bulletproof armoured tactical carrier vehicles for Armed Reserve striking force during VVIP movement and riot contingencies.",
        "justification": "Enhanced security readiness for festival deployments, election rallies, and high-risk prisoner escort.",
        "estimated_cost": 21000000.0,
        "priority": "Medium",
        "status": "Rejected",
        "created_by": "DSP (AR) S. Natarajan",
        "created_days_ago": 410,
        "decision": {
            "type": "Reject",
            "decided_by": "DGP Puducherry",
            "reason": "Duplicate proposal: 2 armoured tactical vehicles already sanctioned under Ministry of Home Affairs Special Security Grant for Union Territories in FY2024-25. Additional 4 vehicles exceed fleet norms.",
            "sanction_no": None,
            "sanctioned_amount": 0.0,
            "conditions": "Utilize existing central allocation before initiating UT-budget procurement."
        },
        "remarks": [
            ("DSP Natarajan", "Initiator", "Tactical necessity briefed."),
            ("SP AR", "Reviewer", "Forwarded for DGP clearance."),
            ("DGP", "Approving Authority", "Rejected as duplicate scheme. Two central vehicles already in pipeline.")
        ]
    },
    {
        "ref_no": "PPH/2025/PRO/0029",
        "title": "Replacement of 22 Condemned Beat Motorcycles with Electric Two-Wheelers for Traffic Beat Patrols",
        "category": "Procurement",
        "department": "Traffic Police Headquarters",
        "description": "Procurement of 22 high-performance electric motorcycles with police flashers and siren attachments for congested heritage boulevard patrols.",
        "justification": "Zero tailpipe emission in French Heritage zone and estimated 72% reduction in monthly fuel expenditure.",
        "estimated_cost": 3100000.0,
        "priority": "Medium",
        "status": "Approved",
        "created_by": "SI Beat Section",
        "created_days_ago": 190,
        "decision": {
            "type": "Approve with Modification",
            "decided_by": "SP (Traffic) C. Mohan",
            "reason": "Approved with modification: Pilot rollout of 10 electric two-wheelers first. Fast-charging stations to be established at Traffic HQ before scaling to 22 units.",
            "sanction_no": "PPH/TRF/2025/082",
            "sanctioned_amount": 1450000.0,
            "conditions": "Vendor must provide dedicated 15-amp charging sockets and 3-year battery replacement warranty."
        },
        "remarks": [
            ("SI Beat", "Initiator", "Feasibility and green mobility study attached."),
            ("DSP Traffic", "Reviewer", "Supports green initiative in heritage zone."),
            ("SP Mohan", "Approving Authority", "Sanctioned 10 units as phase-1 pilot.")
        ]
    },
    {
        "ref_no": "PPH/2025/OPS/0061",
        "title": "Annual Overhaul and Preventive Maintenance Contract for 112 ERSS Emergency Response Vehicle Fleet",
        "category": "Operational",
        "department": "Headquarters & Administration",
        "description": "Comprehensive Annual Maintenance Contract (AMC) for 24 ERSS Emergency Response Support System vehicles including onboard MDTs and emergency sirens.",
        "justification": "Response time targets (under 8 minutes in urban zones) require 99% fleet uptime without mechanical breakdown.",
        "estimated_cost": 1650000.0,
        "priority": "High",
        "status": "In Implementation",
        "created_by": "Insp. MT Cell",
        "created_days_ago": 110,
        "decision": {
            "type": "Approve",
            "decided_by": "SP HQ",
            "reason": "Essential for 112 dial response time compliance.",
            "sanction_no": "PPH/OPS/2025/144",
            "sanctioned_amount": 1600000.0,
            "conditions": "Quarterly inspection reports to be submitted to SP HQ."
        },
        "remarks": [
            ("Insp. MT", "Initiator", "Tender documentation prepared."),
            ("SP HQ", "Approving Authority", "Approved. Vendor onboarding underway.")
        ]
    },

    # ─── CLUSTER 3: Body-Worn Cameras & Digital Evidence ──────────────
    {
        "ref_no": "PPH/2024/PRO/0058",
        "title": "Procurement of 85 Body-Worn Cameras with Cloud Docking Stations for Traffic Sub-Division",
        "category": "Procurement",
        "department": "Traffic Police Headquarters",
        "description": "Supply of 85 encrypted body-worn cameras with 1080p recording, pre-event buffering, and 8-bay automated docking stations at Traffic police stations.",
        "justification": "Deter violent altercations during vehicle checks, ensure public accountability, and preserve tamper-proof evidence for court trials.",
        "estimated_cost": 3200000.0,
        "priority": "High",
        "status": "Closed",
        "created_by": "Insp. K. Prakash",
        "created_days_ago": 480,
        "decision": {
            "type": "Approve",
            "decided_by": "SSP (Traffic)",
            "reason": "Mandated for traffic transparency and officer safety during night checks.",
            "sanction_no": "PPH/TRF/2024/076",
            "sanctioned_amount": 3150000.0,
            "conditions": "AES-256 encryption on camera storage; officers must not have rights to delete recordings."
        },
        "outcome": {
            "status": "Completed Successfully",
            "actual_cost": 3120000.0,
            "summary": "85 cameras distributed to all traffic inspectors and sub-inspectors. Grievance complaints dropped by 44%.",
            "lessons_learned": "Shift duty officers frequently forgot to dock cameras at shift end. SOP established requiring station duty officer sign-off before shift handover."
        },
        "remarks": [
            ("Insp. Prakash", "Initiator", "Technical specs benchmarked with Delhi Police."),
            ("DSP Traffic", "Reviewer", "Strongly recommended."),
            ("SSP Traffic", "Approving Authority", "Sanctioned.")
        ]
    },
    {
        "ref_no": "PPH/2025/TEC/0041",
        "title": "Supply of 200 Body Cameras with Real-Time Live Streaming via Commercial 4G SIMs",
        "category": "Technical",
        "department": "Law and Order (South)",
        "description": "Procurement of 200 body cameras capable of streaming continuous live video via public cellular 4G networks to an overseas cloud vendor repository.",
        "justification": "Real-time command room monitoring of beat officers during law and order agitations.",
        "estimated_cost": 6500000.0,
        "priority": "Medium",
        "status": "Rejected",
        "created_by": "SI R. Devan",
        "created_days_ago": 310,
        "decision": {
            "type": "Reject",
            "decided_by": "DIGP Puducherry",
            "reason": "Severe non-compliance with Ministry of Electronics and Information Technology (MeitY) data localization directives: vendor proposal hosted video feeds on foreign commercial cloud servers without CERT-In audit certification. Cellular streaming battery life inadequate (under 2 hours).",
            "sanction_no": None,
            "sanctioned_amount": 0.0,
            "conditions": "Only on-premise police data center storage or MeitY-empanelled sovereign cloud is permissible for police evidentiary footage."
        },
        "remarks": [
            ("SI Devan", "Initiator", "Vendor presentation submitted."),
            ("DSP South", "Reviewer", "Data security concerns raised regarding live streaming."),
            ("DIGP", "Approving Authority", "Rejected. Non-compliant with data sovereignty mandates.")
        ]
    },

    # ─── CLUSTER 4: Firing Range & Tactical Training ──────────────────
    {
        "ref_no": "PPH/2024/INF/0022",
        "title": "Modernisation and Baffle Wall Reconstruction of Police Firing Range at Gorimedu Complex",
        "category": "Infrastructure",
        "department": "Armed Reserve (Gorimedu Complex)",
        "description": "Civil reconstruction of bullet catchment baffle walls, side containment earth mounds, target pulley lines, and bullet traps at the 100-meter outdoor firing range.",
        "justification": "Deteriorated baffle walls posed ricochet hazards to surrounding residential developments near Gorimedu.",
        "estimated_cost": 6500000.0,
        "priority": "Urgent",
        "status": "Closed",
        "created_by": "DSP (AR) S. Natarajan",
        "created_days_ago": 620,
        "decision": {
            "type": "Approve",
            "decided_by": "IGP Puducherry",
            "reason": "Safety hazard requiring urgent remediation as per National Police Academy firing range safety standards.",
            "sanction_no": "PPH/INF/2024/048",
            "sanctioned_amount": 6300000.0,
            "conditions": "PWD executing agency must obtain ballistic safety certification from Central Weapon Depot before commissioning."
        },
        "outcome": {
            "status": "Completed Successfully",
            "actual_cost": 6280000.0,
            "summary": "Firing range reconstructed and certified. Annual ammunition classification firing resumed safely.",
            "lessons_learned": "Monsoon earth slippage affected the backstop mound. Future civil estimates must include RCC retaining walls and drainage channels."
        },
        "remarks": [
            ("DSP Natarajan", "Initiator", "Joint inspection report with PWD Executive Engineer enclosed."),
            ("SP AR", "Reviewer", "Urgent safety clearance recommended."),
            ("IGP", "Approving Authority", "Approved under Infrastructure capital head.")
        ]
    },
    {
        "ref_no": "PPH/2025/TRG/0033",
        "title": "Procurement of Virtual Firearms Training Simulator (FATS) for Police Training School",
        "category": "Training",
        "department": "Police Training School (PTS Shanmugapuram)",
        "description": "Installation of an interactive 180-degree multi-screen virtual firearm simulator with recoil-enabled Glock, INSAS, and AK-47 replica weapons.",
        "justification": "Allows trainees to practice shoot/don't-shoot judgmental scenarios safely while reducing live ammunition consumption by 60%.",
        "estimated_cost": 4200000.0,
        "priority": "Medium",
        "status": "In Implementation",
        "created_by": "Principal PTS Shanmugapuram",
        "created_days_ago": 140,
        "decision": {
            "type": "Approve",
            "decided_by": "DGP Puducherry",
            "reason": "Modernizes police weapon handling pedagogy and judgment in crowded urban scenarios.",
            "sanction_no": "PPH/TRG/2025/019",
            "sanctioned_amount": 4100000.0,
            "conditions": "Must include Tamil and English scenario voice-overs for localized crowd training."
        },
        "remarks": [
            ("Principal PTS", "Initiator", "Benchmarked with Tamil Nadu Police Academy simulator."),
            ("SP Training", "Reviewer", "Recommended."),
            ("DGP", "Approving Authority", "Sanctioned.")
        ]
    },

    # ─── CLUSTER 5: Cyber Crime & Digital Forensics ───────────────────
    {
        "ref_no": "PPH/2024/TEC/0064",
        "title": "Establishment of Advanced Mobile Device Forensics and Cryptocurrency Analysis Workstations at CCPS",
        "category": "Technical",
        "department": "Cyber Crime Police Station (CCPS)",
        "description": "Procurement of Cellebrite UFED Ultimate, Oxygen Forensic Detective licenses, and blockchain analysis subscription for tracing dark web and cyber fraud funds.",
        "justification": "Exponential rise in APK investment scams and cryptocurrency laundering cases in Puducherry.",
        "estimated_cost": 5500000.0,
        "priority": "High",
        "status": "Closed",
        "created_by": "Insp. Cyber Crime",
        "created_days_ago": 510,
        "decision": {
            "type": "Approve",
            "decided_by": "SP Cyber Crime",
            "reason": "Crucial capability upgrade sanctioned under MHA Cyber Crime Prevention against Women and Children (CCPWC) fund.",
            "sanction_no": "PPH/CC/2024/055",
            "sanctioned_amount": 5400000.0,
            "conditions": "All software licenses to be renewed annually through CCPWC scheme."
        },
        "outcome": {
            "status": "Completed Successfully",
            "actual_cost": 5350000.0,
            "summary": "Workstations operational; handled 320 mobile extractions and assisted in recovering ₹1.8 Crore in scam funds.",
            "lessons_learned": "Hardware dongles must be locked in biometric safe; one license dongle was temporarily misplaced during an emergency court transfer."
        },
        "remarks": [
            ("Insp. CC", "Initiator", "CCPWC grant approval letter attached."),
            ("SP CC", "Approving Authority", "Sanctioned.")
        ]
    },
    {
        "ref_no": "PPH/2025/TEC/0072",
        "title": "Acquisition of Proprietary Deepfake Detection Hardware Suite for Cyber Cell",
        "category": "Technical",
        "department": "Cyber Crime Police Station (CCPS)",
        "description": "Procurement of specialized server appliance with proprietary AI deepfake media detection software from private vendor.",
        "justification": "Counter synthetic media, deepfake extortion videos, and impersonation attempts targeting officials.",
        "estimated_cost": 4900000.0,
        "priority": "Low",
        "status": "Rejected",
        "created_by": "SI Tech Support",
        "created_days_ago": 230,
        "decision": {
            "type": "Reject",
            "decided_by": "SSP (Crime) N. Shanmugam",
            "reason": "Vendor proprietary technology lacked independent scientific validation. Indian Cyber Crime Coordination Centre (I4C) and CERT-In provide free verified deepfake detection APIs to state police forces. Procurement of unproven standalone hardware is an unnecessary expenditure.",
            "sanction_no": None,
            "sanctioned_amount": 0.0,
            "conditions": "Leverage central I4C portal tools before seeking commercial procurement."
        },
        "remarks": [
            ("SI Tech", "Initiator", "Commercial proposal received."),
            ("SP CC", "Reviewer", "Recommend checking I4C availability first."),
            ("SSP Crime", "Approving Authority", "Rejected. Utilize free central I4C tools.")
        ]
    },
    {
        "ref_no": "PPH/2025/TEC/0089",
        "title": "Procurement of Dark Web Monitoring and Social Media Threat Intelligence Tool",
        "category": "Technical",
        "department": "Cyber Crime Police Station (CCPS)",
        "description": "Subscription to threat intelligence feed monitoring dark web marketplaces, telegram leak channels, and social media unrest indicators.",
        "justification": "Early intelligence gathering regarding cyber threats, data breaches, and organized crime.",
        "estimated_cost": 2800000.0,
        "priority": "Medium",
        "status": "Approved",
        "created_by": "Insp. Cyber Crime",
        "created_days_ago": 150,
        "decision": {
            "type": "Approve with Modification",
            "decided_by": "SSP (Crime) N. Shanmugam",
            "reason": "Approved with modification: Sanctioned for 1-year trial license at ₹14 Lakhs instead of 3-year upfront commitment, subject to performance evaluation.",
            "sanction_no": "PPH/CC/2025/098",
            "sanctioned_amount": 1400000.0,
            "conditions": "Monthly actionable intelligence reports to be tabled before Intelligence Section."
        },
        "remarks": [
            ("Insp. CC", "Initiator", "Proposal submitted."),
            ("SSP Crime", "Approving Authority", "Approved 1-year pilot license.")
        ]
    },

    # ─── CLUSTER 6: Infrastructure & Station Modernization ─────────────
    {
        "ref_no": "PPH/2024/INF/0015",
        "title": "Rooftop Solar PV Installation (40 kWp) at Puducherry Police Headquarters, Goubert Avenue",
        "category": "Infrastructure",
        "department": "Headquarters & Administration",
        "description": "Grid-connected 40 kWp rooftop solar panel system with net-metering and inverter bank at Police Headquarters building on Goubert Avenue.",
        "justification": "Continuous grid power backup for CCCR control room and lowering government utility bills.",
        "estimated_cost": 2600000.0,
        "priority": "Medium",
        "status": "Closed",
        "created_by": "AE Electrical (Police Cell)",
        "created_days_ago": 590,
        "decision": {
            "type": "Approve",
            "decided_by": "IGP Puducherry",
            "reason": "Approved under Green Energy initiative with 30% renewable energy subsidy from Renewable Energy Agency of Puducherry (REAP).",
            "sanction_no": "PPH/INF/2024/029",
            "sanctioned_amount": 2550000.0,
            "conditions": "Integration with existing diesel generator changeover switch."
        },
        "outcome": {
            "status": "Completed Successfully",
            "actual_cost": 2510000.0,
            "summary": "40 kWp plant commissioned. Reduced monthly PHQ electricity bills by 38%.",
            "lessons_learned": "Coastal salt air required bi-weekly panel washing schedule; automated water sprinkler line added."
        },
        "remarks": [
            ("AE Electrical", "Initiator", "Energy audit and REAP subsidy calculation submitted."),
            ("SP HQ", "Reviewer", "Recommended for approval."),
            ("IGP", "Approving Authority", "Sanctioned.")
        ]
    },
    {
        "ref_no": "PPH/2024/INF/0081",
        "title": "Renovation of Lock-up Rooms and Installation of Anti-Ligature Fixtures at D-Nagar Police Station",
        "category": "Infrastructure",
        "department": "Law and Order (North)",
        "description": "Civil retrofitting of station lock-ups with flush anti-ligature plumbing, tamper-proof LED illumination, rounded cell bars, and dedicated custodial ventilation.",
        "justification": "NHRC and Puducherry Human Rights Commission guidelines on custodial suicide prevention and humane detention standards.",
        "estimated_cost": 1450000.0,
        "priority": "Urgent",
        "status": "Closed",
        "created_by": "SHO D-Nagar PS",
        "created_days_ago": 460,
        "decision": {
            "type": "Approve",
            "decided_by": "SP (North)",
            "reason": "Statutory human rights compliance. Priority civil work.",
            "sanction_no": "PPH/INF/2024/087",
            "sanctioned_amount": 1400000.0,
            "conditions": "PWD must complete work within 45 days without disrupting station operations."
        },
        "outcome": {
            "status": "Completed Successfully",
            "actual_cost": 1390000.0,
            "summary": "Lock-ups renovated and inspected by Chief Judicial Magistrate.",
            "lessons_learned": "Temporary custodial holding area must be pre-arranged with neighboring station during civil renovation."
        },
        "remarks": [
            ("SHO D-Nagar", "Initiator", "Inspection report of District Magistrate attached."),
            ("SP North", "Approving Authority", "Sanctioned under priority repairs.")
        ]
    },
    {
        "ref_no": "PPH/2025/INF/0049",
        "title": "Construction of Multi-Level Modern Barracks for Armed Reserve Personnel at Gorimedu",
        "category": "Infrastructure",
        "department": "Armed Reserve (Gorimedu Complex)",
        "description": "G+3 reinforced concrete barracks complex with 120-bed capacity, dining hall, modern lockers, and recreation room.",
        "justification": "Present barracks constructed in 1978 suffer from roof seepage and inadequate sanitation for recruited personnel.",
        "estimated_cost": 28000000.0,
        "priority": "Medium",
        "status": "Returned for Revision",
        "created_by": "DSP (AR)",
        "created_days_ago": 95,
        "decision": {
            "type": "Return for Revision",
            "decided_by": "Chief Engineer / DGP Committee",
            "reason": "PWD structural drawings and soil investigation report missing. Estimate lacked environmental clear-height norms and fire safety NOC preliminary clearance.",
            "sanction_no": None,
            "sanctioned_amount": 0.0,
            "conditions": "Resubmit with PWD detailed structural design and Fire Service preliminary NOC."
        },
        "remarks": [
            ("DSP AR", "Initiator", "Preliminary estimate submitted."),
            ("DGP Committee", "Approving Authority", "Returned for revision. Awaiting PWD structural drawings.")
        ]
    },

    # ─── CLUSTER 7: Operational & Community Policing ──────────────────
    {
        "ref_no": "PPH/2024/OPS/0034",
        "title": "Implementation of 'Kavalan' Community Outreach Mobile Kiosks during Tourist Season",
        "category": "Operational",
        "department": "Law and Order (South)",
        "description": "Deployment of 4 branded mobile information kiosks staffed by multi-lingual police personnel at Rock Beach Promenade, Paradise Beach, and Auroville junction.",
        "justification": "Assistance to domestic and international tourists, tourist scam prevention, and rapid lost-and-found registration.",
        "estimated_cost": 850000.0,
        "priority": "Medium",
        "status": "Closed",
        "created_by": "Insp. Tourist Police",
        "created_days_ago": 520,
        "decision": {
            "type": "Approve",
            "decided_by": "SSP (L&O)",
            "reason": "Promotes tourist safety and community policing during peak season (November-February).",
            "sanction_no": "PPH/OPS/2024/041",
            "sanctioned_amount": 800000.0,
            "conditions": "Personnel deployed must be trained in basic French and English communication."
        },
        "outcome": {
            "status": "Completed Successfully",
            "actual_cost": 780000.0,
            "summary": "Handled 4,800 tourist queries and resolved 142 missing property reports.",
            "lessons_learned": "High humidity and salt spray rusted metal kiosk hinges; fiberglass kiosks recommended for subsequent iterations."
        },
        "remarks": [
            ("Insp. Tourist", "Initiator", "Tourist department coordination letter attached."),
            ("SSP L&O", "Approving Authority", "Approved.")
        ]
    },
    {
        "ref_no": "PPH/2025/OPS/0014",
        "title": "Drone Surveillance Patrol System for Heritage Town and Rock Beach Promenade",
        "category": "Operational",
        "department": "Law and Order (North)",
        "description": "Procurement of 3 commercial tethered surveillance drones with thermal cameras for crowd management during festival gatherings and New Year eve celebrations.",
        "justification": "Narrow heritage streets limit patrol car access; aerial view pinpoints crowd bottlenecks and anti-social clusters instantly.",
        "estimated_cost": 2400000.0,
        "priority": "High",
        "status": "Approved",
        "created_by": "SI Special Branch",
        "created_days_ago": 170,
        "decision": {
            "type": "Approve with Modification",
            "decided_by": "DGP Puducherry",
            "reason": "Approved with modification: Restricted to night hours and designated festival deployment. Strict compliance with DGCA red-zone drone regulations near airport required.",
            "sanction_no": "PPH/OPS/2025/022",
            "sanctioned_amount": 1950000.0,
            "conditions": "Operators must hold DGCA Remote Pilot License certificates."
        },
        "remarks": [
            ("SI SB", "Initiator", "Drone capability brief submitted."),
            ("SP North", "Reviewer", "Recommended for crowd control."),
            ("DGP", "Approving Authority", "Approved with modification.")
        ]
    },

    # ─── CLUSTER 8: Administrative & Police Modernization ─────────────
    {
        "ref_no": "PPH/2024/ADM/0005",
        "title": "Digital File Tracking and E-Office Workflow Implementation for Police Headquarters",
        "category": "Administrative",
        "department": "Headquarters & Administration",
        "description": "Migration of physical dak and dispatch registers to NIC e-Office platform with digital signature certificate tokens for gazetted officers.",
        "justification": "Paper files face transit delays between sub-divisional offices and PHQ; e-Office ensures complete audit trail and eliminates file loss.",
        "estimated_cost": 1200000.0,
        "priority": "High",
        "status": "Closed",
        "created_by": "Superintendent (Est.)",
        "created_days_ago": 650,
        "decision": {
            "type": "Approve",
            "decided_by": "IGP Puducherry",
            "reason": "Administrative modernization and transparent paperless governance.",
            "sanction_no": "PPH/ADM/2024/007",
            "sanctioned_amount": 1150000.0,
            "conditions": "All ministerial staff to undergo 3-day NIC computer training."
        },
        "outcome": {
            "status": "Completed Successfully",
            "actual_cost": 1100000.0,
            "summary": "PHQ sections fully migrated. Average file movement turnaround reduced from 9 days to 2 days.",
            "lessons_learned": "Initial staff hesitation was overcome by designating two e-Office champions per section for peer assistance."
        },
        "remarks": [
            ("Supdt Est", "Initiator", "NIC proposal attached."),
            ("IGP", "Approving Authority", "Sanctioned.")
        ]
    },
    {
        "ref_no": "PPH/2025/ADM/0067",
        "title": "Biometric Aadhaar-Enabled Attendance System (AEBAS) for All Police Stations and Units",
        "category": "Administrative",
        "department": "Headquarters & Administration",
        "description": "Deployment of 45 wall-mounted iris and fingerprint AEBAS biometric terminals linked with Central Pay System.",
        "justification": "Streamline roll-call muster, manage overtime records, and ensure punctual station duty attendance.",
        "estimated_cost": 950000.0,
        "priority": "Medium",
        "status": "In Implementation",
        "created_by": "HC Accounts",
        "created_days_ago": 130,
        "decision": {
            "type": "Approve",
            "decided_by": "SP HQ",
            "reason": "Standard government compliance with administrative attendance norms.",
            "sanction_no": "PPH/ADM/2025/089",
            "sanctioned_amount": 920000.0,
            "conditions": "Terminals must support offline buffering during fiber outages."
        },
        "remarks": [
            ("HC Accounts", "Initiator", "GeM bid finalized."),
            ("SP HQ", "Approving Authority", "Sanctioned.")
        ]
    },

    # ─── ACTIVE PROPOSALS FOR DEMO WORKFLOW ────────────────────────────
    {
        "ref_no": "PPH/2026/PRO/0001",
        "title": "Procurement of 120 Body-Worn Cameras with AI Video Tagging for Boulevard Traffic Beats",
        "category": "Procurement",
        "department": "Traffic Police Headquarters",
        "description": "Acquisition of 120 next-generation lightweight body-worn cameras with automated AI vehicle number tag recognition and tamper-resistant local docking stations.",
        "justification": "Expansion of transparent traffic policing across all shifts following the success of earlier pilot projects.",
        "estimated_cost": 4600000.0,
        "priority": "High",
        "status": "Under Review",
        "created_by": "Insp. M. Rajendran",
        "created_days_ago": 12,
        "remarks": [
            ("Insp. Rajendran", "Initiator", "Precedent Gate satisfied: Reviewed PPH/2024/PRO/0058 and PPH/2025/TEC/0041. Local docking stations specified to satisfy data sovereignty directives."),
            ("DSP Traffic", "Reviewer", "Precedent acknowledgements verified. Endorsed for Approving Authority sanction.")
        ]
    },
    {
        "ref_no": "PPH/2026/TEC/0002",
        "title": "Expansion of CCTV Surveillance Network to 30 Heritage Town Junctions with Optical Fiber Backbone",
        "category": "Technical",
        "department": "IT & Communications Cell",
        "description": "Laying dedicated police optical fiber cable and erecting 30 high-mast poles with 90 IP PTZ surveillance cameras linked to Central Command Center.",
        "justification": "Ensure comprehensive coverage across French and Tamil heritage quarters ahead of upcoming festival season.",
        "estimated_cost": 5800000.0,
        "priority": "High",
        "status": "Draft",
        "created_by": "HC R. Kumar (DA)",
        "created_days_ago": 2,
        "remarks": [
            ("HC R. Kumar", "Initiator", "Draft proposal initiated. Surfacing past CCTV precedents for compliance.")
        ]
    },
    {
        "ref_no": "PPH/2026/PRO/0003",
        "title": "Replacement of 8 Aging Highway Interceptor Patrol Vehicles with Factory-Fitted Radar Units",
        "category": "Procurement",
        "department": "Traffic Police Headquarters",
        "description": "Procurement of 8 highway interceptor SUVs equipped with OEM factory-fitted speed laser radars, breath analyzer docks, and roof flashers.",
        "justification": "Existing interceptors purchased in 2017 have reached end of economic life with frequent breakdown on East Coast Road.",
        "estimated_cost": 8800000.0,
        "priority": "Urgent",
        "status": "Submitted",
        "created_by": "SI Highway Patrol",
        "created_days_ago": 5,
        "remarks": [
            ("SI Highway", "Initiator", "Proposal submitted following precedent review of PPH/2023/PRO/0008. Specified factory-fitted equipment directly from OEM to avoid past retrofit delays.")
        ]
    }
]

# Additional synthetic proposals across categories to reach 48 total
EXPANSION_TEMPLATES = [
    ("Administrative", "Establishment of Police Welfare Creche and Daycare Facility at Gorimedu Complex", "Headquarters & Administration", 1400000.0, "Approved"),
    ("Administrative", "Annual Service Medical Examination Scheme for Police Personnel Aged 40 and Above", "Headquarters & Administration", 2200000.0, "Closed"),
    ("Administrative", "Implementation of Dedicated Police Grievance Redressal Mobile Application", "IT & Communications Cell", 980000.0, "Approved"),
    ("Administrative", "Upgradation of Records Room and Modern Compactor Storage at North Sub-Division", "Law and Order (North)", 1650000.0, "Rejected"),
    ("Technical", "Installation of 20 Solar-Powered Marine VHF Repeaters for Coastal Fishermen Distress Channels", "Coastal Police / Marine Unit", 2900000.0, "Closed"),
    ("Technical", "Deployment of Laser Speed Gun Systems with Automatic Number Plate Recognition for ECR", "Traffic Police Headquarters", 3400000.0, "Approved"),
    ("Technical", "Setup of Automated Ballistic Imaging System (ABIS) Terminal at Armoury", "Armed Reserve (Gorimedu Complex)", 7200000.0, "Rejected"),
    ("Technical", "Replacement of Analog Wireless Handsets with TETRA Digital Walkie-Talkies", "IT & Communications Cell", 8400000.0, "Closed"),
    ("Technical", "Supply of Smart Junction Traffic Adaptive Signal Controller (ATCS) Software", "Traffic Police Headquarters", 4100000.0, "In Implementation"),
    ("Procurement", "Procurement of 50 Polycarbonate Riot Control Shields and Full Body Protectors", "Armed Reserve (Gorimedu Complex)", 1850000.0, "Closed"),
    ("Procurement", "Supply of 100 Breath Analyzers with Inbuilt Thermal Printers for Night Enforcement", "Traffic Police Headquarters", 1250000.0, "Approved"),
    ("Procurement", "Procurement of 2 Rigid Inflatable Fast Interceptor Boats (RIB) for Port Patrolling", "Coastal Police / Marine Unit", 16500000.0, "Rejected"),
    ("Procurement", "Procurement of Deep Search Metal Detectors and Explosive Vapour Tracers for BDDS", "Armed Reserve (Gorimedu Complex)", 4500000.0, "Closed"),
    ("Procurement", "Purchase of Multi-Gas Detectors and SCBA Gear for Police Hazardous Material Response", "Law and Order (South)", 2100000.0, "Approved"),
    ("Procurement", "Supply of Tactical Laser Range Finders and Night Vision Binoculars for Marine Police", "Coastal Police / Marine Unit", 3100000.0, "Approved"),
    ("Infrastructure", "Construction of Separate Ladies Rest Rooms and Lockers in 8 Police Stations", "Law and Order (South)", 2400000.0, "Closed"),
    ("Infrastructure", "Reconstruction of Cyclone-Damaged Perimeter Wall at Kalapet Police Station", "Law and Order (North)", 1750000.0, "Closed"),
    ("Infrastructure", "Installation of RO Water Purification and Chilling Plants in All Police Stations", "Headquarters & Administration", 1300000.0, "Approved"),
    ("Infrastructure", "Rainwater Harvesting and Ground Water Recharge Pits across 12 Police Campuses", "Headquarters & Administration", 950000.0, "Closed"),
    ("Infrastructure", "Modernization of Police Training School Parade Ground with All-Weather Synthetic Track", "Police Training School (PTS Shanmugapuram)", 5200000.0, "Returned for Revision"),
    ("Training", "3-Day Specialized Crash Course on Investigation of Cryptocurrency Fraud for Sub-Inspectors", "Cyber Crime Police Station (CCPS)", 650000.0, "Closed"),
    ("Training", "Refresher Training on Forensic Evidence Collection at Crime Scenes in Coordination with FSL", "Police Training School (PTS Shanmugapuram)", 850000.0, "Approved"),
    ("Training", "Tactical Defensive Driving and Pursuit Maneuver Certification for Police Drivers", "Police Training School (PTS Shanmugapuram)", 1100000.0, "Closed"),
    ("Training", "Disaster Response and Deep-Sea Life Saving Certification for Marine Police Personnel", "Coastal Police / Marine Unit", 1450000.0, "Closed"),
    ("Operational", "Special Night Combing Operations and Border Barrier Check Scheme during Assembly Elections", "Law and Order (North)", 3800000.0, "Closed"),
    ("Operational", "Smart Beat Book Mobile App Rollout for Beat Constables across 18 Police Stations", "IT & Communications Cell", 1950000.0, "Closed"),
    ("Operational", "Establishment of Student Police Cadet (SPC) Programme in 25 Puducherry Schools", "Headquarters & Administration", 2250000.0, "Approved"),
    ("Operational", "Installation of Coastal Warning Sirens and Fishermen Emergency Megaphone Network", "Coastal Police / Marine Unit", 1750000.0, "Approved"),
]

def seed_database(reset: bool = True):
    """Populates the database with realistic proposals, history, remarks, and cryptographic chains."""
    if reset and os.path.exists(PROPOSALS_DB_PATH):
        try:
            os.remove(PROPOSALS_DB_PATH)
        except Exception as e:
            print(f"[Seed] Could not remove existing DB: {e}")

    init_proposals_db()
    conn = get_db_connection()

    all_proposals = list(SEED_PROPOSALS)

    # Add expansion proposals
    now = datetime.now()
    idx = 100
    for cat, title, dept, cost, status in EXPANSION_TEMPLATES:
        idx += 1
        year = random.choice([2024, 2025])
        cat_code = cat[:3].upper()
        ref_no = f"PPH/{year}/{cat_code}/{idx:04d}"
        days_ago = random.randint(30, 700)
        all_proposals.append({
            "ref_no": ref_no,
            "title": title,
            "category": cat,
            "department": dept,
            "description": f"Comprehensive proposal for {title.lower()} to enhance department operational readiness and welfare standards in Puducherry.",
            "justification": f"Mandated operational requirement in accordance with police reform directives and unit requirements for {dept}.",
            "estimated_cost": cost,
            "priority": random.choice(["Medium", "High", "Low"]),
            "status": status,
            "created_by": "Dealing Assistant (Police HQ)",
            "created_days_ago": days_ago,
            "decision": {
                "type": "Approve" if status in ["Approved", "Closed", "In Implementation", "Implemented"] else ("Reject" if status == "Rejected" else "Return for Revision"),
                "decided_by": "SP / Approving Authority",
                "reason": "Accorded formal administrative and financial approval." if status != "Rejected" else "Rejected due to budget limits or duplication with central scheme.",
                "sanction_no": f"PPH/GOV/{year}/{idx}" if status in ["Approved", "Closed"] else None,
                "sanctioned_amount": cost * 0.96 if status in ["Approved", "Closed"] else 0.0,
                "conditions": "Procurement strictly through government approved portals."
            } if status not in ["Draft", "Submitted", "Under Review"] else None,
            "outcome": {
                "status": "Completed Successfully",
                "actual_cost": cost * 0.95,
                "summary": f"{title} successfully executed and handed over for operational use.",
                "lessons_learned": "Regular inter-departmental milestone reviews prevented procedural delays."
            } if status == "Closed" else None,
            "remarks": [
                ("Dealing Assistant", "Initiator", "Submitted for consideration with budget breakdown."),
                ("Inspecting Officer", "Reviewer", "Examined and endorsed."),
                ("Approving Authority", "Approving Authority", "Processed as per state finance rules.")
            ]
        })

    print(f"[Seed] Inserting {len(all_proposals)} proposals into IPMPRS...")

    prop_id_map = {}

    for item in all_proposals:
        prop_id = f"prop-{abs(hash(item['ref_no'])) % 100000000:08d}"
        prop_id_map[item["ref_no"]] = prop_id

        created_dt = now - timedelta(days=item.get("created_days_ago", 30))
        created_at = created_dt.isoformat()
        updated_dt = created_dt + timedelta(days=random.randint(2, 25))
        updated_at = updated_dt.isoformat()
        closed_at = (updated_dt + timedelta(days=40)).isoformat() if item["status"] == "Closed" else None

        # 1. Insert Proposal Record
        conn.execute("""
            INSERT OR REPLACE INTO proposals (
                id, ref_no, title, category, department, description,
                justification, estimated_cost, priority, status,
                created_by, created_at, updated_at, closed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prop_id, item["ref_no"], item["title"], item["category"], item["department"],
            item["description"], item["justification"], item["estimated_cost"],
            item["priority"], item["status"], item["created_by"], created_at, updated_at, closed_at
        ))

        # 2. Build Authentic SHA-256 Chained History
        status_steps = ["Draft"]
        if item["status"] != "Draft":
            status_steps.append("Submitted")
            if item["status"] in ["Under Review", "Approved", "Rejected", "In Implementation", "Implemented", "Closed", "Returned for Revision"]:
                status_steps.append("Under Review")
            if item["status"] in ["Approved", "In Implementation", "Implemented", "Closed"]:
                status_steps.append("Approved")
            if item["status"] in ["In Implementation", "Implemented", "Closed"]:
                status_steps.append("In Implementation")
            if item["status"] in ["Implemented", "Closed"]:
                status_steps.append("Implemented")
            if item["status"] == "Closed":
                status_steps.append("Closed")
            if item["status"] == "Rejected":
                status_steps.append("Rejected")
            if item["status"] == "Returned for Revision":
                status_steps.append("Returned for Revision")

        prev_hash = GENESIS_HASH
        step_dt = created_dt

        for i, s in enumerate(status_steps):
            from_s = status_steps[i - 1] if i > 0 else ""
            actor_role = "Initiator" if s in ["Draft", "Submitted"] else ("Reviewer" if s == "Under Review" else "Approving Authority")
            note = f"Status advanced to {s}" if i > 0 else "Proposal initiated in draft"

            cur = conn.execute("""
                INSERT INTO proposal_history (
                    proposal_id, from_status, to_status, actor, role, note,
                    timestamp, prev_hash, hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (prop_id, from_s, s, item["created_by"], actor_role, note,
                  step_dt.isoformat(), prev_hash, GENESIS_HASH))

            entry_id = cur.lastrowid
            curr_hash = compute_history_hash(
                entry_id, prop_id, from_s, s, item["created_by"], actor_role,
                note, step_dt.isoformat(), prev_hash
            )
            conn.execute("UPDATE proposal_history SET hash=? WHERE id=?", (curr_hash, entry_id))
            prev_hash = curr_hash
            step_dt += timedelta(days=random.randint(2, 6))

        # 3. Insert Remarks
        for author, role, text in item.get("remarks", []):
            conn.execute("""
                INSERT INTO proposal_remarks (proposal_id, author, role, text, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (prop_id, author, role, text, created_dt.isoformat()))

        # 4. Insert Decision
        dec = item.get("decision")
        if dec:
            conn.execute("""
                INSERT INTO proposal_decisions (
                    proposal_id, decision_type, decided_by, reason,
                    sanction_order_no, sanctioned_amount, conditions, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prop_id, dec["type"], dec["decided_by"], dec["reason"],
                dec.get("sanction_no"), dec.get("sanctioned_amount"),
                dec.get("conditions"), (created_dt + timedelta(days=14)).isoformat()
            ))

        # 5. Insert Outcome
        out = item.get("outcome")
        if out:
            conn.execute("""
                INSERT INTO proposal_outcomes (
                    proposal_id, implementation_status, actual_cost, completion_date,
                    outcome_summary, lessons_learned, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                prop_id, out["status"], out.get("actual_cost"),
                (created_dt + timedelta(days=45)).strftime("%Y-%m-%d"),
                out.get("summary"), out.get("lessons_learned"),
                (created_dt + timedelta(days=45)).isoformat()
            ))

    # 6. Seed Sample Precedent Links for active demo proposal (PPH/2026/PRO/0001)
    target_id = prop_id_map.get("PPH/2026/PRO/0001")
    p1 = prop_id_map.get("PPH/2024/PRO/0058")  # 85 Body Cameras (Approved & Closed)
    p2 = prop_id_map.get("PPH/2025/TEC/0041")  # 200 Body Cameras (Rejected - Data security)

    if target_id and p1:
        conn.execute("""
            INSERT INTO proposal_precedent_links (
                proposal_id, precedent_id, similarity, relevance, reason, acknowledged_by, acknowledged_at
            ) VALUES (?, ?, 91.5, 'relevant', 'Matches camera technical specs and docking requirements; adopted local encryption model.', 'Insp. M. Rajendran', ?)
        """, (target_id, p1, now.isoformat()))

    if target_id and p2:
        conn.execute("""
            INSERT INTO proposal_precedent_links (
                proposal_id, precedent_id, similarity, relevance, reason, acknowledged_by, acknowledged_at
            ) VALUES (?, ?, 86.2, 'relevant', 'Rejected precedent noted. Specifically avoided commercial 4G cloud streaming to comply with MeitY data localization directives.', 'Insp. M. Rajendran', ?)
        """, (target_id, p2, now.isoformat()))

    conn.commit()
    conn.close()
    print(f"[Seed] Successfully populated IPMPRS with {len(all_proposals)} proposals and verified audit trails.")

if __name__ == "__main__":
    seed_database(reset=True)
