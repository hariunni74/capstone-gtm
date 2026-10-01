import json

from crewai import Crew, Task

from gtm_agents.agents import build_agents
from gtm_agents.models import QuestionResearch
from gtm_agents.source_check import check_source


with open("eight_question_run.json", encoding="utf-8") as file:
    run = json.load(file)

for index, finding in enumerate(run["research"]):
    if finding["search_status"] != "search_failed":
        continue

    question = finding["question"]
    query = run["search_queries"][index]
    print(f"Retrying question {index + 1}: {query}", flush=True)

    researcher = build_agents()["researcher"]
    task = Task(
        description=(
            f"Research question: {question}\n"
            f"Use search_market once with this exact query: '{query}'. "
            "Return a QuestionResearch object with at most three sources. "
            "Copy titles and URLs from the tool result. Classify each as "
            "direct, context, or irrelevant. Search results are leads, not "
            "verified evidence. If the tool returns an error or times out, "
            "set search_status to search_failed, leave sources empty, and "
            "explain the failure in gap_reason. Set unanswered to true unless "
            "a source directly answers the question."
        ),
        expected_output="A QuestionResearch object with source candidates and gaps.",
        output_pydantic=QuestionResearch,
        agent=researcher,
    )
    result = Crew(agents=[researcher], tasks=[task], verbose=False).kickoff()
    if result.pydantic is None:
        print(f"Question {index + 1}: no structured result", flush=True)
        continue

    replacement = result.pydantic.model_dump(mode="json")
    if replacement["search_status"] == "search_failed":
        replacement["sources"] = []
        replacement["unanswered"] = True
    else:
        for source in replacement["sources"][:3]:
            check = check_source(source["url"])
            check["question"] = question
            check["candidate_title"] = source["title"]
            run["source_checks"].append(check)

    run["research"][index] = replacement
    print(f"Question {index + 1}: {replacement['search_status']}", flush=True)

# The old analysis and strategy belong to the earlier research snapshot.
retry_output = {
    "research": run["research"],
    "source_checks": run["source_checks"],
    "search_queries": run["search_queries"],
}
with open("eight_question_retried.json", "w", encoding="utf-8") as file:
    json.dump(retry_output, file, indent=2)

print(
    "Successful searches:",
    sum(item["search_status"] == "ok" for item in retry_output["research"]),
    "of",
    len(retry_output["research"]),
)