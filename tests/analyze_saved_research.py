import json

from gtm_agents.flow import GTMFlow
from gtm_agents.planner import build_brief


with open("eight_question_retried.json", encoding="utf-8") as file:
    saved = json.load(file)

flow = GTMFlow()
flow.state.brief = build_brief(
    topic="AI-powered product discovery portal for consumer healthcare products",
    geography="United States",
    target_customer="Consumer healthcare brands and retail teams",
)

assessment = flow.analyze_first_question({
    "question": "All eight research questions",
    "research_notes": json.dumps(saved["research"]),
    "source_checks": saved["source_checks"],
})
strategy = flow.draft_provisional_strategy(assessment)

with open("eight_question_assessment.json", "w", encoding="utf-8") as file:
    json.dump({
        "research": saved["research"],
        "source_checks": saved["source_checks"],
        "analysis": assessment["analysis_notes"],
        "strategy": strategy["strategy_notes"],
        "status": strategy["status"],
    }, file, indent=2)

print("STATUS:", strategy["status"])
print("RESEARCH RECORDS:", len(saved["research"]))