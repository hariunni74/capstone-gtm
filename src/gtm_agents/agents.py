import os

from crewai import Agent, LLM
from dotenv import load_dotenv
from crewai.mcp import MCPServerHTTP

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL_NAME", "openai/gpt-4o-mini")


def build_agents() -> dict[str, Agent]:
    llm = LLM(model=MODEL, temperature=0)

    return {
        "planner": Agent(
            role="Head Planner",
            goal="Turn the user's topic into a focused market research plan.",
            backstory="You coordinate research and define what the team must answer.",
            llm=llm,
            allow_delegation=False,
            verbose=True,
        ),
        "researcher": Agent(
            role="Research Agent",
            goal="Find relevant, attributable evidence for the research questions.",
            backstory="You search for sources and record what each source actually supports.",
            llm=llm,
            mcps=[MCPServerHTTP(url="http://localhost:8000/mcp", streamable=True)],
            allow_delegation=False,
            max_iter=1,
            verbose=True,
        ),
        "analyst": Agent(
            role="Market Analyst",
            goal="Assess market direction, customers, competitors, and evidence gaps.",
            backstory="You distinguish supported findings from assumptions.",
            llm=llm,
            allow_delegation=False,
            verbose=True,
        ),
        "strategist": Agent(
            role="GTM Strategist",
            goal="Recommend positioning, channels, and an actionable launch plan.",
            backstory="You base recommendations on the analyst's supported findings.",
            llm=llm,
            allow_delegation=False,
            verbose=True,
        ),
    }