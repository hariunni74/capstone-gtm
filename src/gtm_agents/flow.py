"""Coordinate the market research and GTM planning workflow.

The flow turns a user brief into eight research questions, gathers source
leads, checks accessible pages, analyzes evidence gaps, and drafts a
provisional strategy. Search results do not automatically verify claims.
"""
import json

from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel, Field

from .models import QuestionResearch, ResearchBrief, SearchPlan
from .planner import build_brief
from crewai import Crew, Task
from .agents import build_agents

from .source_check import check_source

class GTMState(BaseModel):
    topic: str = ""
    geography: str = ""
    target_customer: str = ""
    brief: ResearchBrief | None = None
    status: str = "new"
    research_notes: str = ""
    analysis_notes: str = ""
    strategy_notes: str = ""
    search_queries: list[str] = Field(default_factory=list)
    source_checks: list[dict] = Field(default_factory=list)


class GTMFlow(Flow[GTMState]):
    # Step 1: Build the brief and plan one search query per research question.
    @start()
    def prepare_brief(self) -> ResearchBrief:
        self.state.brief = build_brief(
            topic=self.state.topic,
            geography=self.state.geography,
            target_customer=self.state.target_customer,
        )
        planner = build_agents()["planner"]
        task = Task(
            description=(
                f"Topic: {self.state.brief.topic}\n"
                f"Geography: {self.state.brief.geography}\n"
                f"Target customer: {self.state.brief.target_customer}\n\n"
                "Write exactly eight concise web search queries, one for each "
                "question below and in the same order. Use terms a source would actually contain. "
                "Keep each query to roughly 5–10 words. "
                "For question 1, search for market size and growth in the "
                "supplied geography and product category. If no directly "
                "matching market estimate is available, seek a measurable "
                "adjacent market and clearly label it as context; do not "
                "present it as the proposed product's market size. "
                "For question 2, focus on the supplied target customer's "
                "segments, buyers, and decision makers. "
                "Interpret all terminology using the supplied topic, "
                "geography, and target customer. "
                "For competitor and pricing questions, seek actual vendors "
                "serving the stated use case and their public offerings. "
                "For regulation, focus on the supplied geography, industry, "
                "and proposed product capabilities.\n\n"
                + "\n".join(
                    f"{i}. {question}"
                    for i, question in enumerate(
                        self.state.brief.questions, start=1
                    )
                )
            ),
            expected_output="A SearchPlan with exactly eight queries in question order.",
            output_pydantic=SearchPlan,
            agent=planner,
        )

        plan_result = Crew(
            agents=[planner], tasks=[task], verbose=True
        ).kickoff()
        if plan_result.pydantic is None:
            raise ValueError("Head Planner did not return a valid SearchPlan.")

        self.state.search_queries = plan_result.pydantic.queries
        self.state.status = "brief_ready"
        return self.state.brief

    # Step 2: Research all eight questions and check the returned source pages.
    @listen(prepare_brief)
    def research_first_question(self, brief: ResearchBrief) -> dict:
        findings = []

        if len(self.state.search_queries) != len(brief.questions):
            raise ValueError("The search plan must contain one query per question.")

        for question, search_query in zip(
            brief.questions, self.state.search_queries
        ):
            researcher = build_agents()["researcher"]
            task = Task(
                description=(
                    f"Research question: {question}\n"
                    f"Use search_market once with this exact query: '{search_query}'. "
                    "Return a QuestionResearch object with at most three sources. "
                    "Copy titles and URLs from the tool result. Classify each as "
                    "direct, context, or irrelevant. "
                    f"Topic: {brief.topic}\n"
                    f"Geography: {brief.geography}\n"
                    f"Target customer: {brief.target_customer}\n"
                    "Classify a source as direct only when it addresses the "
                    "current research question for the supplied brief. "
                    "Classify it as context when it concerns a relevant "
                    "adjacent market, industry, or customer group. "
                    "Classify it as irrelevant when it concerns a different "
                    "use case or meaning of the same terminology. "
                    "Search results are leads, not verified evidence. If search_market "
                    "returns an error or times out, set search_status "
                    "to search_failed, leave sources empty, set unanswered to true, "
                    "and put the tool error in gap_reason. Do not say no sources exist. "
                    "Set unanswered to true unless a result directly answers the question, "
                    "and explain the gap. "
                ),
                expected_output="A QuestionResearch object with source candidates and gaps.",
                output_pydantic=QuestionResearch,
                agent=researcher,
            )
            result = Crew(
                agents=[researcher], tasks=[task], verbose=True
            ).kickoff()

            if result.pydantic is None:
                raise ValueError(f"No structured research for: {question}")

            finding = result.pydantic.model_dump(mode="json")

            if finding["search_status"] == "search_failed":
                if finding["sources"]:
                    finding["gap_reason"] = (
                        "Search was marked failed but returned candidates; "
                        "the contradictory result requires a retry."
                    )
                finding["sources"] = []
                finding["unanswered"] = True

            findings.append(finding)

            for source in finding["sources"][:3]:
                check = check_source(source["url"])
                check["question"] = question
                check["candidate_title"] = source["title"]
                self.state.source_checks.append(check)

        self.state.research_notes = json.dumps(findings, indent=2)
        self.state.status = "research_test_complete"
        return {
            "status": self.state.status,
            "question": "All research questions",
            "research_notes": self.state.research_notes,
            "source_checks": self.state.source_checks,
        }

    # Step 3: Assess relevant page passages and identify unanswered questions.
    @listen(research_first_question)
    def analyze_first_question(self, research_result: dict) -> dict:
        analyst = build_agents()["analyst"]

        analysis_findings = json.loads(research_result["research_notes"])
        checks_by_url = {
            check["url"]: check
            for check in research_result["source_checks"]
        }

        for finding in analysis_findings:
            finding["sources"] = [
                source for source in finding["sources"]
                if source["relevance"] != "irrelevant"
                and checks_by_url.get(source["url"], {}).get("accessible") is True
                and bool(checks_by_url.get(source["url"], {}).get("text_excerpt"))
            ]
            # A reachable URL does not verify the claim in a search snippet.
            finding["unanswered"] = True
            if not finding["sources"] and finding["search_status"] == "ok":
                finding["gap_reason"] = (
                    "No relevant, readable page passage was available for verification."
                )

        retained_urls = {
            source["url"]
            for finding in analysis_findings
            for source in finding["sources"]
        }

        page_excerpts = [
            {
                "url": url,
                "page_title": checks_by_url[url].get("page_title", ""),
                "text_excerpt": checks_by_url[url]["text_excerpt"][:1200],
            }
            for url in retained_urls
        ]

        task = Task(
            description=(
                f"Research question: {research_result['question']}\n\n"
                f"Research notes:\n{json.dumps(analysis_findings, indent=2)}\n\n"
                f"Extracted page passages:\n{json.dumps(page_excerpts, indent=2)}\n\n"
                "Use a passage only if its text actually supports the specific question. "
                "A search snippet or page title alone is not evidence. "
                "Assess each research question separately and concisely. Separate direct evidence from "
                "broader industry context. State clearly if the sources do "
                "not establish a market size for the proposed product. "
                "Cite only URLs present in the research notes; do not add facts. "
                "For any record with search_status=search_failed, report a search failure "
                "requiring retry; do not infer that evidence is unavailable. "
                "Never cite a source marked irrelevant as evidence or industry context. "
                "For a search_failed question, say the search needs retry; do not say that no sources exist. "
            ),
            expected_output=(
                "A brief assessment with supported findings, broader context, "
                "and unanswered questions."
            ),
            agent=analyst,
        )

        result = Crew(agents=[analyst], tasks=[task], verbose=True).kickoff()
        self.state.analysis_notes = result.raw
        self.state.status = "analysis_test_complete"

        return {
            "status": self.state.status,
            "question": research_result["question"],
            "analysis_notes": self.state.analysis_notes,
        }

    # Step 4: Draft strategy hypotheses and explain what still needs validation.
    @listen(analyze_first_question)
    def draft_provisional_strategy(self, analysis_result: dict) -> dict:
        strategist = build_agents()["strategist"]

        task = Task(
            description=(
                f"Topic: {self.state.brief.topic}\n"
                f"Geography: {self.state.brief.geography}\n"
                f"Target customer: {self.state.brief.target_customer}\n\n"
                f"Analyst assessment:\n{analysis_result['analysis_notes']}\n\n"
                "Draft a provisional GTM hypothesis: possible customer problem, "
                "positioning, and two ways to test demand. Label every recommendation "
                "as a hypothesis. List the evidence needed before making a launch "
                "or market-size claim. Cite only URLs in the analyst assessment. "
                "Any proposed sample size, pilot duration, percentage target, "
                "or success threshold is an illustrative planning suggestion, "
                "not an evidence-backed benchmark. Label such numbers explicitly "
                "as illustrative and explain that they require calibration. "
                "Do not claim that survey interest alone validates demand; "
                "distinguish stated interest from willingness to pay and "
                "observed adoption. "
            ),
            expected_output=(
                "A short provisional GTM hypothesis, validation steps, "
                "and evidence gaps."
            ),
            agent=strategist,
        )

        result = Crew(agents=[strategist], tasks=[task], verbose=True).kickoff()
        self.state.strategy_notes = result.raw
        self.state.status = "strategy_test_complete"

        return {
            "status": self.state.status,
            "strategy_notes": self.state.strategy_notes,
        }