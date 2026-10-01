# Multi Agent Market Research and GTM Planner

This capstone compares two implementations of a market research and go to market planning workflow: a Python CrewAI Flow with a Streamlit interface, and a local n8n workflow. The sample brief concerns an AI powered product discovery portal for consumer healthcare products in the United States, serving consumer healthcare brands and retail teams. Both implementations use a four role sequence: Head Planner, Research Agent, Market Analyst, and GTM Strategist.

The outputs are **provisional plans**. Search results are candidate leads; a successful search does not establish market size, buyer demand, competitor pricing, or regulatory conclusions. The agents label gaps and propose validation work when evidence is insufficient.

## Architecture

| Stage | CrewAI | n8n |
| --- | --- | --- |
| Input | Streamlit form in `app.py` | Chat Trigger, optionally called by Streamlit |
| Planning | `GTMFlow.prepare_brief` and Head Planner | Head Planner, then Split Research Questions |
| Research | Research Agent calls `search_market` through MCP for eight questions | Research Agent calls the same MCP tool for eight items; Collect Research combines results |
| Assessment | Source fetch and passage extraction in `source_check.py`, then Market Analyst | Analyst Agent and Evidence Gate |
| Strategy | GTM Strategist | Strategy Agent and Format GTM Report |
| Output | Streamlit result and sample `outputs/gtm_report.md` | Google Docs Create and Update nodes produce a native document in Drive |

The local MCP server in `mcp_server/server.py` exposes `search_market` using SerpAPI. CrewAI connects to `http://localhost:8000/mcp`; the n8n Docker container connects to `http://host.docker.internal:8000/mcp`. The server returns titles, URLs, and snippets, which must be checked before any claim is treated as verified.

The Streamlit **CrewAI** selection runs the Python Flow directly. The **n8n** selection calls the Chat Trigger URL over HTTP and shows a link to the Google Doc returned by the completed n8n run. These are two separate agent implementations sharing the research service.

## Project layout

```text
app.py                    Streamlit interface
src/gtm_agents/           CrewAI agents, Flow, models, planner, source checks
mcp_server/server.py      Streamable HTTP MCP search tool
tests/                    Connectivity, timing, research, and export scripts
outputs/gtm_report.md     Saved CrewAI sample output
pyproject.toml            UV project dependencies
uv.lock                   Locked dependency resolution
.env.example              Required secret names, without values
```

The submission also contains the separately exported n8n workflow JSON, a populated Google Doc sample, and screenshots. The n8n JSON references credentials by name or ID; an importer must configure their own OpenAI and Google Docs credentials.

## Setup in WSL Ubuntu

1. Install Python 3.12 and `uv`. From the project root, run `uv sync` to install locked dependencies.
2. Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY` and `SERPAPI_API_KEY`. Keep `.env` private. The CrewAI model defaults to `openai/gpt-4o-mini`; set `OPENAI_MODEL_NAME` in `.env` if changing it.
3. Start the MCP server in one terminal:

   ```bash
   uv run python mcp_server/server.py
   ```

4. In a second terminal, check the MCP tool and start the UI:

   ```bash
   uv run python tests/check_mcp.py
   uv run streamlit run app.py
   ```

5. Open the local Streamlit URL shown in the terminal. Select **CrewAI**, enter a topic, geography, and target customer, then select **Create GTM plan**. The eight research calls and agent stages can take several minutes.

## n8n setup and optional Streamlit connection

Run local n8n in Docker and import the exported workflow JSON. Configure its OpenAI Chat Model credentials and Google Docs OAuth2 credential. Enable the Google Docs and Drive APIs in the OAuth project, authorize a Google test user if the consent screen is in testing, and select a Drive folder in the Create GTM Google Doc node. Keep the MCP server running in WSL. The n8n MCP Client uses `host.docker.internal:8000` because n8n runs in Docker.

Test the workflow in n8n with a Chat Trigger message such as:

```text
Topic: AI-powered product discovery portal for consumer healthcare products
Geography: United States
Target customer: Consumer healthcare brands and retail teams
```

To call this workflow from the Streamlit **n8n** selection, enable **Make Chat Publicly Available** on the n8n Chat Trigger, use its **Chat URL** (not the editor URL), save and publish the workflow, and add the URL to the local `.env` file:

```dotenv
N8N_CHAT_URL=http://localhost:5678/webhook/<your-chat-trigger-id>/chat
```

Copy the actual Chat URL from the node instead of typing an ID. The URL must be reachable from the WSL process running Streamlit. For a local demo, keep n8n bound to your machine. If you configure Basic Auth on the Chat Trigger, also put `N8N_CHAT_USERNAME` and `N8N_CHAT_PASSWORD` in `.env`. Restart Streamlit after changing `.env`.

Select **n8n** in Streamlit and submit the same brief. The app sends `action=sendMessage`, a new session ID, and the brief as `chatInput`. It waits up to ten minutes for the workflow to create and populate a Google Doc, then shows its link. One submission starts one new workflow execution and one new document. If the UI times out, inspect n8n **Executions** and Drive before trying again so you do not create duplicates.

## Testing and observed results

Useful local checks from the project root:

```bash
uv run python tests/check_serpapi.py
uv run python tests/time_serpapi.py
uv run python tests/check_mcp.py
uv run python tests/run_eight_questions.py
```

`tests/run_eight_questions.py` writes `eight_question_run.json` in the project root and makes paid model and SerpAPI calls. `tests/export_report.py` generates the saved Markdown report from a separate `eight_question_assessment.json` intermediate; that intermediate is not part of the minimal source archive. The supplied `outputs/gtm_report.md` is the sample artifact, so the export script is not a prerequisite for running the UI.

The saved CrewAI sample reports eight planned and searched questions, eight successful searches, and five candidate pages with readable passages. These counts describe search coverage and page access, not eight answered questions. A local n8n end to end test completed without errors in about five minutes and produced a populated Google Doc. Runtime and search outcomes will vary with network response, provider availability, and model output. The Streamlit to n8n HTTP integration is an optional extension; validate it locally before using its screenshot as evidence.

## Limits and interpretation

- Search snippets and accessible pages are not automatically evidence for the specific product, customer, or price claim. Market size, segmentation, competitor pricing, and adoption assumptions remain open where no directly supporting passage was verified.
- The sample plans label survey counts, pilot durations, and performance targets as illustrative hypotheses. They are not independently established benchmarks.
- Some broad source leads in the n8n sample, especially under competitor pricing, do not directly answer the question. They need replacement or removal before the report is used as research evidence.
- The n8n workflow produces a Google Doc with plain text. The CrewAI Markdown output and n8n Google Doc are distinct artifacts from separate runs; they are not expected to have identical wording.
- Google OAuth test mode may require reconnecting after the test-user authorization expires. Secrets, `.env`, `.venv`, logs with sensitive data, and local credentials are excluded from the submission.

## Submission evidence

Include the final n8n JSON export; the CrewAI UV project files; the populated Google Doc sample or its DOCX export; CrewAI Streamlit screenshots showing the brief, agent result, and evidence gaps; and this README. Add a screenshot of the successful n8n execution and the populated Google Doc if useful. If the optional Streamlit n8n call passes, capture that UI result as an additional screenshot and note that it triggers a fresh n8n execution.
