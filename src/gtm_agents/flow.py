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
from .search_client import fetch_candidates

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
                "For question 1, identify an established market category "
                "underlying the proposed solution and search for its market "
                "size or growth in the supplied geography. Avoid copying "
                "the entire proposed product description into the query. "
                "An adjacent category is a research lead, not an estimate "
                "of the proposed product's addressable market. "
                "Do not append a year unless the brief requests one. "
                "For question 2, focus on the supplied target customer's "
                "segments, buyers, and decision makers. "
                "Interpret all terminology using the supplied topic, "
                "geography, and target customer. "
                "Do not add an arbitrary historical year. Seek recent evidence "
                "unless the question explicitly requests a historical period. "
                "For question 3, include the operational problem addressed by "
                "the proposed product, not just general customer challenges. "
                "For questions 4 and 5, use the established software or product "
                "category to find actual vendors and official feature pages; "
                "do not require vendors to call themselves competitors. "
                "For question 6, search for vendor subscription prices, licence "
                "fees, pricing plans, or implementation fees. Avoid confusing "
                "software pricing with prices of goods sold by its users. "
                "For question 7, search for sales channels, partnerships, or "
                "industry networks that reach the target customer as a buyer "
                "of the proposed solution. "
                "For question 8, seek applicable rules or practical adoption "
                "barriers tied to the product's capabilities and geography; "
                "do not assume a dedicated AI law exists for the use case.\n\n"
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
        self.state.source_checks = []

        if len(self.state.search_queries) != len(brief.questions):
            raise ValueError("The search plan must contain one query per question.")

        for question, query in zip(brief.questions, self.state.search_queries):
            # Python makes one MCP call; the server controls HTTP retries.
            try:
                candidates = fetch_candidates(query)
            except Exception:
                candidates = [{
                    "status": "error",
                    "error": "Search connection or response processing failed.",
                }]

            errors = [
                item for item in candidates
                if item.get("status") == "error"
            ]
            if errors:
                findings.append({
                    "question": question,
                    "query": query,
                    "sources": [],
                    "unanswered": True,
                    "gap_reason": errors[0].get("error", "Search failed."),
                    "search_status": "search_failed",
                })
                continue

            # Preserve original tool fields rather than model-generated URLs.
            originals = []
            seen_urls = set()
            for item in candidates:
                url = item.get("url", "")
                if (
                    url.startswith(("https://", "http://"))
                    and url not in seen_urls
                ):
                    seen_urls.add(url)
                    originals.append(item)
                if len(originals) == 5:
                    break

            if not originals:
                findings.append({
                    "question": question,
                    "query": query,
                    "sources": [],
                    "unanswered": True,
                    "gap_reason": "Search returned no usable URL candidates.",
                    "search_status": "ok",
                })
                continue

            researcher = build_agents()["researcher"]
            task = Task(
                description=(
                    f"Topic: {brief.topic}\n"
                    f"Geography: {brief.geography}\n"
                    f"Target customer: {brief.target_customer}\n"
                    f"Research question: {question}\n\n"
                    f"Search candidates:\n{json.dumps(originals, indent=2)}\n\n"
                    "Assess every supplied candidate. Copy its URL exactly. "
                    "Classify it as direct, context, or irrelevant. "
                    "Direct means relevant to this question and brief; "
                    "context means useful adjacent information. "
                    "Exclude terminology matches with a different meaning. "
                    "For customer segments, assess buyers of the proposed "
                    "solution, not those buyers' own customers. "
                    "Pricing means fees for the proposed type of solution. "
                    "Channels means acquiring buyers of that solution. "
                    "Search snippets are leads, not verified findings. "
                    "Set unanswered=true pending page verification. "
                    "Do not invent sources or claim a search failure."
                ),
                expected_output=(
                    "A QuestionResearch object classifying all supplied "
                    "candidates and explaining remaining evidence gaps."
                ),
                output_pydantic=QuestionResearch,
                agent=researcher,
            )
            result = Crew(
                agents=[researcher], tasks=[task], verbose=True
            ).kickoff()

            if result.pydantic is None:
                raise ValueError(f"No structured research for: {question}")

            classified = {
                str(source.url): source
                for source in result.pydantic.sources
            }

            sources = []
            for original in originals:
                assessment = classified.get(original["url"])
                sources.append({
                    "title": original.get("title", ""),
                    "url": original["url"],
                    "snippet_or_note": original.get("snippet", ""),
                    # Unclassified candidates remain leads for the analyst.
                    "relevance": (
                        assessment.relevance if assessment else "context"
                    ),
                    "classification_status": (
                        "classified" if assessment else "not_classified"
                    ),
                })

            findings.append({
                "question": question,
                "query": query,
                "sources": sources,
                "unanswered": True,
                "gap_reason": result.pydantic.gap_reason,
                "search_status": "ok",
            })

            # Check all retained candidates, including ones the model omitted.
            for source in sources:
                if source["relevance"] == "irrelevant":
                    continue
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
                "text_excerpt": checks_by_url[url]["text_excerpt"][:4000],
            }
            for url in retained_urls
        ]

        task = Task(
            description=(
                f"Topic: {self.state.brief.topic}\n"
                f"Geography: {self.state.brief.geography}\n"
                f"Target customer: {self.state.brief.target_customer}\n\n"
                f"Research question: {research_result['question']}\n\n"
                f"Research notes:\n{json.dumps(analysis_findings, indent=2)}\n\n"
                f"Extracted page passages:\n{json.dumps(page_excerpts, indent=2)}\n\n"
                "Use a passage only if its text actually supports the specific question. "
                "A search snippet or page title alone is not evidence. "
                "Distinguish vendor claims, third-party commentary, and "
                "independently supported findings. Attribute claims to their "
                "source and retain material qualifications. "
                "If a passage says a product is discontinued, unavailable to "
                "new customers, or restricted, include that limitation whenever "
                "discussing its availability or pricing. "
                "For customer segments, identify organizations or people who "
                "would buy the proposed solution, not their end consumers. "
                "For acquisition channels, distinguish reaching those buyers "
                "from channels they use to sell their own goods. A retailer's "
                "omnichannel selling strategy does not by itself establish a "
                "sales channel for the proposed solution. "
                "Do not state current legal requirements or the absence of "
                "regulation as established fact based only on an undated or "
                "secondary article. Label such material as context requiring "
                "verification against current official sources. "
                "A failed search describes retrieval status, not the absence "
                "of evidence across all supplied passages. Preserve the failure "
                "notice while using relevant passages from other searches for "
                "clearly attributed partial findings. "
                "Assess each research question separately and concisely. "
                "Separate direct evidence from broader industry context. "
                "State clearly if the sources do "
                "not establish a market size for the proposed product. "
                "Preserve supported partial findings even when the question cannot "
                "be fully answered. An incomplete competitor list is not an empty "
                "finding. Treat research-note gap reasons and unanswered flags as "
                "preliminary; assess the supplied passages yourself. "
                "Consider all supplied passages for every question, regardless of "
                "which search originally found the source. A vendor page found for "
                "competitors may also support features or public pricing. "
                "Attribute vendor statements explicitly; do not treat claimed "
                "performance as independently validated. Distinguish adjacent "
                "enterprise or distributor offerings from products proven suitable "
                "for the target customer. "
                "Include a source URL beside each supported finding. "
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