import json

from gtm_agents.flow import GTMFlow


flow = GTMFlow()
result = flow.kickoff(
    inputs={
        "topic": "AI-powered product discovery portal for consumer healthcare products",
        "geography": "United States",
        "target_customer": "Consumer healthcare brands and retail teams",
    }
)

research = json.loads(flow.state.research_notes)

with open("eight_question_run.json", "w", encoding="utf-8") as file:
    json.dump(
        {
            "result": result,
            "research": research,
            "source_checks": flow.state.source_checks,
            "analysis": flow.state.analysis_notes,
            "search_queries": flow.state.search_queries,
        },
        file,
        indent=2,
    )

print("STATUS:", result["status"])
print("RESEARCH RECORDS:", len(research))