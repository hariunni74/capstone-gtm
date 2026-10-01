import json
from pathlib import Path


data = json.loads(Path("eight_question_assessment.json").read_text(encoding="utf-8"))
checks = {item["url"]: item for item in data["source_checks"]}
research = data["research"]

lines = [
    "# Multi-Agent Market Research and GTM Report",
    "",
    "**Topic:** AI-powered product discovery portal for consumer healthcare products  ",
    "**Geography:** United States  ",
    "**Target customer:** Consumer healthcare brands and retail teams  ",
    "**Implementation:** CrewAI Flow with MCP and SerpAPI  ",
    "**Model:** gpt-4o-mini baseline",
    "",
    "## Research coverage",
    "",
    f"- Questions planned and researched: **{len(research)}**",
    f"- Successful searches: **{sum(r['search_status'] == 'ok' for r in research)}**",
    f"- Candidate pages with readable passages: **{sum(bool(c.get('text_excerpt')) for c in data['source_checks'])}**",
    "- A successful search is not the same as an answered research question.",
    "- Search results are candidate leads. A reachable page and extracted passage "
    "do not automatically establish that a claim is true.",
    "",
    "| # | Research question | Search | Evidence gap |",
    "|---|---|---|---|",
]

for number, item in enumerate(research, 1):
    question = item["question"].replace("|", "\\|")
    gap = item["gap_reason"].replace("|", "\\|").replace("\n", " ")
    if not gap and number == 4:
        gap = "Candidate marked direct, but its page was blocked; no claim verified."
    lines.append(
        f"| {number} | {question} | {item['search_status']} | {gap or 'See source audit'} |"
    )

lines.extend([
    "",
    "## Source audit",
    "",
    "| Question | Candidate source | Access | Readable passage |",
    "|---|---|---|---|",
])

for number, item in enumerate(research, 1):
    for source in item["sources"]:
        check = checks.get(source["url"], {})
        if check.get("accessible"):
            access = "Accessible"
        else:
            access = check.get("access_status", "Not checked")
        passage = "Yes" if check.get("text_excerpt") else "No"
        title = source["title"].replace("|", "\\|").replace("[", "").replace("]", "")
        lines.append(
            f"| {number} | [{title}]({source['url']}) "
            f"({source['relevance']}) | {access} | {passage} |"
        )

lines.extend([
    "",
    "## Analyst assessment",
    "",
    data["analysis"],
    "",
    "## Provisional GTM strategy",
    "",
    data["strategy"],
    "",
    "## Interpretation",
    "",
    "The strategy contains hypotheses for validation. Survey and pilot sizes are "
    "illustrative proposals. The cited adjacent-market sources do not establish "
    "the proposed portal's market size or prove product demand.",
    "",
])

output = Path("outputs/gtm_report.md")
output.parent.mkdir(exist_ok=True)
output.write_text("\n".join(lines), encoding="utf-8")
print(f"Report created: {output} ({output.stat().st_size} bytes)")