"""Reset or populate the synthetic IPMPRS demo dataset."""

import argparse

import precedent_index
import proposals
import seed_data


def seed_patrol_scenarios():
    scenarios = [
        {
            "title": "Procurement of 12 Patrol Vehicles for North Zone Operations",
            "description": "Procure twelve police patrol vehicles with GPS tracking, emergency light bars, and public address systems for North Zone response coverage.",
            "justification": "The current fleet has high maintenance costs and insufficient availability for round-the-clock patrol coverage.",
            "estimated_cost": 28600000,
            "decision_type": "Reject",
            "remark": "Rejected on cost: the estimate exceeds the approved vehicle modernization ceiling. Resubmit with a reduced fleet and three comparable GeM quotations.",
        },
        {
            "title": "Procurement of 10 Patrol Vehicles for North Zone Response",
            "description": "Replace aging North Zone patrol vehicles with GPS-enabled SUVs and factory-fitted emergency equipment.",
            "justification": "Improve patrol availability and reduce repeat workshop expenditure across North Zone stations.",
            "estimated_cost": 18400000,
            "decision_type": "Approve with Modification",
            "remark": "Approved with changes: begin with six vehicles in the highest-call stations and retain the existing maintenance contract for the pilot year.",
        },
        {
            "title": "Procurement of 14 Patrol Cars for North Zone",
            "description": "Purchase patrol cars with GPS and emergency equipment to expand North Zone vehicle coverage.",
            "justification": "Improve response time while a fleet replacement proposal is under review.",
            "estimated_cost": 22100000,
            "decision_type": None,
            "remark": "Reviewer requests a revised cost comparison before the proposal proceeds to financial approval.",
        },
    ]
    for scenario in scenarios:
        matches = proposals.list_proposals(search=scenario["title"], limit=20)
        if any(item["title"] == scenario["title"] for item in matches):
            continue
        proposal = proposals.create_proposal(
            title=scenario["title"],
            category="Procurement",
            department="Headquarters & Administration",
            description=scenario["description"],
            justification=scenario["justification"],
            estimated_cost=scenario["estimated_cost"],
            created_by="Insp. Operations",
            actor_role="Initiator",
        )
        proposals.transition_proposal(proposal["id"], "Submitted", "Insp. Operations", "Initiator", "Submitted for patrol fleet review.")
        proposals.transition_proposal(proposal["id"], "Under Review", "DSP Review", "Reviewer", "Patrol fleet review started.")
        if scenario["decision_type"]:
            proposals.record_decision(
                proposal["id"], scenario["decision_type"], "SP Approver", scenario["remark"],
                role="Approving Authority",
            )
        else:
            proposals.add_remark(proposal["id"], "DSP Review", "Reviewer", scenario["remark"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="replace the current demo database")
    args = parser.parse_args()
    seed_data.seed_database(reset=args.reset)
    seed_patrol_scenarios()
    print(f"[Seed] Reindexed {precedent_index.precedent_index.reindex_all()} decided proposals.")


if __name__ == "__main__":
    main()