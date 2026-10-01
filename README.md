# Multi Agent Market Research and GTM Planner

This project implements a market research and go-to-market planning workflow in two ways: a Python CrewAI Flow and an n8n workflow, both accessible through a Streamlit interface. Users supply a topic, geography, and target customer. The prompts support different industries and markets; tested examples include consumer healthcare product discovery in the United States and inventory forecasting for independent retailers in India.

Both implementations use four agent roles: Head Planner, Research Agent, Market Analyst, and GTM Strategist. They share an MCP search service backed by SerpAPI. CrewAI execution tracing is integrated with Langfuse, and the Streamlit interface records run status and elapsed time for both implementations.

The application currently runs locally. Public deployment is planned.

The outputs are **provisional plans**. Search results are candidate leads; a successful search does not establish market size, buyer demand, competitor pricing, or regulatory conclusions. The agents label gaps and propose validation work when evidence is insufficient.

## Architecture

| Stage | CrewAI | n8n |
| --- | --- | --- |
| Input | Streamlit form in `app.py` | Chat Trigger, optionally called by Streamlit |
| Planning | `GTMFlow.prepare_brief` and Head Planner | Head Planner, then Split Research Questions |
| Research | Research Agent calls `search_market` through MCP for eight questions | Research Agent calls the same MCP tool for eight items; Collect Research combines results |
| Assessment | Source fetch and passage extraction in `source_check.py`, then Market Analyst | Analyst Agent and Evidence Gate |
| Strategy | GTM Strategist | Strategy Agent and Format GTM Report |
| Output | Streamlit result; optional local Markdown export | Google Docs Create and Update nodes produce a native document in Drive |

The local MCP server in `mcp_server/server.py` exposes `search_market` using SerpAPI. CrewAI connects to `http://localhost:8000/mcp`; the n8n Docker container connects to `http://host.docker.internal:8000/mcp`. The server returns titles, URLs, and snippets, which must be checked before any claim is treated as verified.

The Streamlit **CrewAI** selection runs the Python Flow directly. The **n8n** selection calls the Chat Trigger URL over HTTP and shows a link to the Google Doc returned by the completed n8n run. These are two separate agent implementations sharing the research service.

## Project layout

```text
app.py                              Streamlit interface
src/gtm_agents/                     Agents, Flow, models, source checks, logging, tracing
mcp_server/server.py                Streamable HTTP MCP search tool
n8n/gtm_research_workflow.json      Main n8n workflow export
n8n/gtm_mcp_connection_test.json    MCP connection-test workflow
tests/                              Connectivity, timing, research, and export scripts
pyproject.toml                      uv project dependencies
uv.lock                             Locked dependency resolution
.env.example                        Configuration template with placeholder values
```

Generated reports and logs are stored locally and excluded from Git. The n8n exports reference credentials by name or ID; importers must configure their own OpenAI and Google Docs credentials and check the MCP endpoint for their environment. Submission reports and screenshots were packaged separately and are not included in this repository.

## Setup in WSL Ubuntu

Install `uv` and a Python version compatible with `pyproject.toml`. From the project root, install the locked dependencies:

```bash
uv sync --locked
test -e .env || cp .env.example .env
```

If `.env` already exists, keep it rather than overwriting it.

Fill in `OPENAI_API_KEY` and `SERPAPI_API_KEY` in `.env`. The CrewAI model defaults to `openai/gpt-4o-mini`; optionally set `OPENAI_MODEL_NAME` to change it.

### Langfuse configuration

The current CrewAI UI integration initializes Langfuse tracing. Create a Langfuse project and add its credentials to `.env`:

```dotenv
LANGFUSE_PUBLIC_KEY=your_langfuse_public_key
LANGFUSE_SECRET_KEY=your_langfuse_secret_key
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

Use the base URL for your project's region. Keep `.env` private; commit only the placeholder template `.env.example`.

### Start the application

In one terminal, start the MCP search server:

```bash
uv run python mcp_server/server.py
```

In a second terminal, check connectivity:

```bash
uv run python tests/check_mcp.py
```

Then start Streamlit:

```bash
uv run streamlit run app.py
```

Open the local URL shown in the terminal. Select **CrewAI**, enter a topic, geography, and target customer, then select **Create GTM plan**. Keep the MCP server running throughout execution.

After a run, inspect **Tracing** in Langfuse for `crewai-gtm-run`. Its metadata includes the same `run_id` recorded in `logs/runs.jsonl`. Child observations capture agent operations, MCP tool calls, and OpenAI model calls. Instrumented prompt and response content is configured to be redacted.

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
N8N_CHAT_URL=http://localhost:5678/webhook/your-chat-trigger-id/chat
```

Copy the actual Chat URL from the node instead of typing an ID. The URL must be reachable from the WSL process running Streamlit. For a local demo, keep n8n bound to your machine. If you configure Basic Auth on the Chat Trigger, also put `N8N_CHAT_USERNAME` and `N8N_CHAT_PASSWORD` in `.env`. Restart Streamlit after changing `.env`.

Select **n8n** in Streamlit and submit the same brief. The app sends `action=sendMessage`, a new session ID, and the brief as `chatInput`. The app uses a 20-minute HTTP timeout while waiting for n8n to create and populate a Google Doc, then displays the returned document link. This timeout applies to the UI request; it does not cancel the n8n execution. One submission starts a new workflow execution and normally creates one new document. If the UI times out, inspect n8n **Executions** and Google Drive before retrying to avoid duplicate runs.

## Testing and observed results

Run connectivity and search checks from the project root:

```bash
uv run python tests/check_serpapi.py
uv run python tests/time_serpapi.py
uv run python tests/check_mcp.py
```

These checks contact external services and may consume search quota.

For a full CrewAI research run:

```bash
uv run python tests/run_eight_questions.py
```

This script makes billable model calls, consumes search quota, and writes `eight_question_run.json` locally. Generated research files, logs, and the `outputs/` directory are excluded from Git.

`tests/export_report.py` requires a separately generated `eight_question_assessment.json` intermediate. It is not required to run the Streamlit interface.

### Recorded runs

The following are individual observations, not controlled benchmarks or averages.

| Implementation | Test | Recorded duration | Result |
| --- | --- | --- | --- |
| CrewAI through Streamlit | India inventory forecasting; local run log | 2 min 24.8 sec | Completed |
| CrewAI through Streamlit | India inventory forecasting; Langfuse trace | 2 min 29.7 sec | Trace and child observations captured |
| n8n editor chat | India inventory forecasting; generic prompts | 4 min 28 sec | Google Doc created; Q2 and Q6 search timeouts disclosed |

The n8n run completed despite two failed searches. Successful workflow completion does not mean all research questions were answered.

### Observability and cost

The recorded Langfuse run contained one parent trace and 54 child observations, including 19 model calls and eight MCP search calls.

| Metric | Recorded value |
| --- | ---: |
| Input tokens | 17,048 |
| Output tokens | 2,535 |
| Total tokens | 19,583 |
| Langfuse-calculated LLM cost | USD 0.00408 |

The cost covers captured OpenAI model calls only. It excludes SerpAPI, hosting, and other operating costs, and is not an invoice reconciliation. Comparable n8n token and cost measurements have not yet been collected.

The Streamlit interface records run IDs, implementation, status, elapsed seconds, and error type in `logs/runs.jsonl`. CrewAI traces include the matching run ID. The n8n UI timing measures the HTTP response wait; detailed n8n tracing is not yet integrated.

Model, evidence depth, network conditions, and provider response times differ between implementations. These runs therefore do not establish that one framework is inherently faster, cheaper, or more reliable.

## Limits and interpretation

- Search snippets and accessible pages are not automatically evidence for the specific product, customer, or price claim. Market size, segmentation, competitor pricing, and adoption assumptions remain open where no directly supporting passage was verified.
- The sample plans label survey counts, pilot durations, and performance targets as illustrative hypotheses. They are not independently established benchmarks.
- Some broad source leads in the n8n sample, especially under competitor pricing, do not directly answer the question. They need replacement or removal before the report is used as research evidence.
- The n8n workflow produces a Google Doc with plain text. The CrewAI Markdown output and n8n Google Doc are distinct artifacts from separate runs; they are not expected to have identical wording.
- Google OAuth test mode may require reconnecting after the test-user authorization expires. Secrets, `.env`, `.venv`, logs with sensitive data, and local credentials are excluded from the submission.

## Deployment status and roadmap

The project currently runs locally in WSL Ubuntu, with n8n running in Docker. No public application deployment is available yet.

Planned work before sharing a hosted demo:

- Add access controls and usage limits to manage billable executions.
- Configure hosted secrets and service endpoints.
- Package the Streamlit app and MCP service for Azure deployment.
- Protect the n8n editor and workflow endpoint.
- Verify report generation and tracing in the hosted environment.
- Add detailed n8n observability and collect comparable token and cost measurements.

The repository currently has no license. A license decision is pending before public release.
