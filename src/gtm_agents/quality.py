import re


def check_research_notes(notes: str) -> list[str]:
    """Return problems that should stop the analyst handoff."""
    urls = re.findall(r"https?://[^\s)\]]+", notes)
    problems = []

    if not urls:
        problems.append("Research output contains no source URLs.")

    if "market size" in notes.lower() and not urls:
        problems.append("A market-size statement has no source URL.")

    return problems