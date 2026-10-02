# Multi Agent Market Research and GTM Planner

This project implements a market research and go-to-market planning workflow in two ways: a Python CrewAI Flow and an n8n workflow, both accessible through a Streamlit interface. Users supply a topic, geography, and target customer. The prompts support different industries and markets; tested examples include consumer healthcare product discovery in the United States and inventory forecasting for independent retailers in India.

Both implementations use four agent roles: Head Planner, Research Agent, Market Analyst, and GTM Strategist. They share an MCP search service backed by SerpAPI. CrewAI execution tracing is integrated with Langfuse, and the Streamlit interface records run status and elapsed time for both implementations.

The application supports local development and an on-demand Azure demo.
Both CrewAI and n8n have completed end-to-end tests through the hosted
Streamlit interface.

The outputs are **provisional plans**. Search results are candidate leads; a successful search does not establish market size, buyer demand, competitor pricing, or regulatory conclusions. The agents label gaps and propose validation work when evidence is insufficient.

## Understanding the project

### What is agentic AI, and why use it here?

Traditional AI commonly performs a defined task, such as predicting
demand, classifying a document, or recommending a product. Generative
AI can create text and other content from a prompt. Agentic AI adds
the ability to pursue a goal through multiple steps, use tools, and
make decisions within defined boundaries. These approaches overlap:
an agent often uses generative AI as its reasoning component.

For example, a single chatbot could draft a GTM plan from its existing
knowledge. This project instead breaks the work into planning,
external research, evidence assessment, and strategy development.
Specialized agents handle these stages, with web search providing
information beyond the model's stored knowledge.

The use case is suitable for exploring agentic AI because research
questions vary with the user's brief, external information is needed,
and findings require interpretation before recommendations are made.

This implementation uses a controlled sequence with bounded tool
access. It is not an unrestricted autonomous system. Input screening,
usage limits, evidence checks, and human review remain important.

A simpler workflow with ordinary API calls could also implement this
use case. Multiple agents do not automatically improve accuracy:
their value must be assessed against additional cost, latency, and
operational complexity.

### Why CrewAI and n8n?

Implementing the workflow in both CrewAI and n8n was a capstone
requirement. It also provided an opportunity to compare a Python
approach with visual workflow automation.

Both implementations follow the same four-role sequence:
Head Planner, Research Agent, Market Analyst, and GTM Strategist.
Their internal logic and evidence handling differ, so this is a
comparison of two implementations rather than a controlled benchmark
of the frameworks themselves.

| Aspect | CrewAI | n8n |
| --- | --- | --- |
| What it is | A framework for building agents, tasks, and structured flows in code. | A visual workflow automation platform that combines application integrations, code, and AI nodes. |
| Main strength for this project | Flexibility to implement custom source checks, validation, logging, and Word export in Python. | A visible execution path and convenient integration with Google Docs and Drive. |
| Main tradeoff | Requires Python skills and responsibility for dependencies, deployment, and application behavior. | Complex branching, custom logic, and large prompts can become harder to maintain on a visual canvas. |
| Research in this implementation | Python retrieves MCP search candidates; model-based assessment and page checks process them. | The Research Agent calls the MCP search tool within the workflow. |
| Observability in this implementation | Langfuse traces plus application run logs. | n8n execution history plus application run logs; Langfuse tracing is not integrated. |
| Report delivery | Downloadable Word document. | Google Doc accessible through the returned link. |

Neither framework guarantees reliable research. Search quality,
source relevance, prompts, validation, and evaluation strongly
influence the final result.

### What other approaches could be considered?

The course also introduced AutoGen and Microsoft Foundry. These were
learning topics, not alternative implementations tested in this project.

| Option | Potential fit | Tradeoff or consideration |
| --- | --- | --- |
| AutoGen | Exploring conversational collaboration and coordination between agents. | AutoGen is now in maintenance mode; Microsoft recommends Microsoft Agent Framework for new projects. |
| Microsoft Agent Framework | Building custom agent orchestration with Microsoft's current agent development framework. | Would require a separate implementation and evaluation rather than a direct replacement of the existing workflows. |
| Microsoft Foundry Agent Service | Using a managed Azure service to build, host, and operate agents. | Requires evaluation of service costs, regional availability, identity, and deployment requirements. It is a platform/service, rather than an equivalent of the CrewAI library. |
| A simpler Python pipeline | Running a fixed sequence of search, analysis, and report-generation API calls. | Could reduce orchestration complexity, while requiring explicit implementation of state, retries, and integrations. |

The current demo runs Docker containers on an Azure virtual machine.
It does not use Microsoft Foundry Agent Service. Alternative approaches
are future evaluation options, not claims of equivalent performance.

## Architecture

| Stage | CrewAI | n8n |
| --- | --- | --- |
| Input | Streamlit brief form | Same Streamlit form, or editor Chat Trigger |
| Planning | Head Planner generates eight search queries | Head Planner, then Split Research Questions |
| Research | Python MCP client retrieves candidates; Research Agent classifies them | Research Agent calls MCP for eight items; Collect Research combines results |
| Assessment | Accessible source passages checked, then Market Analyst | Analyst Agent and Evidence Gate; search leads remain unverified |
| Strategy | GTM Strategist drafts provisional hypotheses | Strategy Agent and Format GTM Report |
| Output | On-screen results and downloadable Word report | Google Doc; Azure workflow adds Reader link sharing and returns the document ID |

The local MCP server in `mcp_server/server.py` exposes `search_market` using SerpAPI. CrewAI connects to `http://localhost:8000/mcp`; the n8n Docker container connects to `http://host.docker.internal:8000/mcp`. The server returns titles, URLs, and snippets, which must be checked before any claim is treated as verified.

The Streamlit **CrewAI** selection runs the Python Flow directly. The **n8n** selection calls the Chat Trigger URL over HTTP and shows a link to the Google Doc returned by the completed n8n run. These are two separate agent implementations sharing the research service.

## Project layout

```text
app.py                                 Streamlit interface
src/gtm_agents/                        Agents, Flow, models, source checks, logging, tracing
mcp_server/server.py                   Streamable HTTP MCP search tool
n8n/gtm_research_workflow.json         Main n8n workflow export
n8n/gtm_mcp_connection_test.json       MCP connection-test workflow
tests/                                 Connectivity, timing, research, and export scripts
pyproject.toml                         uv project dependencies
uv.lock                                Locked dependency resolution
.env.example                           Configuration template with placeholder values
Dockerfile                             Application and MCP container image
compose.yaml                           Base Docker services
compose.azure.yaml                     Azure n8n and HTTPS configuration
Caddyfile                              HTTPS reverse proxy configuration
n8n/gtm_research_workflow_azure.json   Azure workflow with report sharing
src/gtm_agents/report_export.py        CrewAI Word report generation
src/gtm_agents/search_client.py        Python MCP search client
src/gtm_agents/input_safety.py         Brief moderation screening
```

Generated reports and logs are stored locally and excluded from Git. The n8n exports reference credentials by name or ID; importers must configure their own OpenAI and Google Docs credentials and check the MCP endpoint for their environment. Submission reports and screenshots were packaged separately and are not included in this repository.

## Setup in WSL Ubuntu

Install `uv` and a Python version compatible with `pyproject.toml`. From the project root, install the locked dependencies:

```bash
uv sync --locked
test -e .env || cp .env.example .env
```

If `.env` already exists, keep it rather than overwriting it.

Fill in `OPENAI_API_KEY`, `SERPAPI_API_KEY`, and `DEMO_ACCESS_CODE`
in `.env`. Optionally set `DEMO_DAILY_RUN_LIMIT`; its default is five
attempts per UTC day across all visitors and both workflows.

The CrewAI model defaults to `openai/gpt-4o-mini`; optionally set
`OPENAI_MODEL_NAME` to change it. `MCP_SERVER_URL` defaults to
`http://localhost:8000/mcp` for local Python execution.

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

Open the local URL shown in the terminal and enter your demo access code.
Select CrewAI, enter a topic, geography, and target customer, then select
Create GTM plan. Keep the MCP server running throughout execution.
The brief is screened before research begins.

After a CrewAI run, inspect Tracing in Langfuse for `crewai-gtm-run`.
Its metadata includes the `run_id` recorded in `logs/runs.jsonl`.
Instrumentation captures CrewAI and OpenAI operations. The Python MCP
client performs search retrieval separately; do not assume every search
is represented by an automatically instrumented tool span.
Instrumented prompt and response content is configured to be redacted.

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

### Azure deployment verification — 2 October 2026

These are individual runs using the India inventory forecasting brief,
not averages or controlled framework benchmarks.

| Execution path | Recorded duration | Result |
| --- | ---: | --- |
| CrewAI through public Streamlit | 184.843 seconds | Completed; Word report downloaded and Langfuse trace visible |
| n8n through Azure editor | 241.568 seconds | Completed; populated Google Doc created |
| n8n through public Streamlit | 269.493 seconds | Document ID returned; populated report available |

A subsequent public Streamlit n8n run confirmed automatic Reader sharing:
the new report opened in Incognito without signing into Google or
manually changing its permissions.

Field validation was checked locally and on the hosted UI. Simulated
moderation tests confirmed that flagged briefs and screening failures
stop before allowance reservation. A live moderation request accepted
the sample legitimate business brief. These checks verify integration
behavior, not moderation accuracy across all topics.

### Observability coverage

| Capability | CrewAI | n8n |
| --- | --- | --- |
| Run ID, status, and elapsed time in application logs | Yes | Yes, for Streamlit-triggered runs |
| Agent and model tracing in Langfuse | Yes | Not integrated |
| Token usage | Captured by Langfuse for instrumented calls | Reported separately in n8n's execution view |
| Estimated model cost | Available in Langfuse for captured calls | Not currently measured |

One Azure n8n editor run reported approximately 33,306 tokens.
This figure came from n8n, not Langfuse.

The project demonstrates both orchestration approaches, but does not yet
provide a controlled cost comparison. Langfuse's CrewAI cost estimate
excludes search and hosting costs. Equivalent n8n cost tracking and
matched-run evaluation remain future enhancements.

These observations do not establish that one framework is inherently
faster, cheaper, or more reliable. A controlled comparison would require
matched briefs, models, research depth, and repeated runs.

## Limits and interpretation

- Search snippets and accessible pages are not automatically evidence for the specific product, customer, or price claim. Market size, segmentation, competitor pricing, and adoption assumptions remain open where no directly supporting passage was verified.
- The sample plans label survey counts, pilot durations, and performance targets as illustrative hypotheses. They are not independently established benchmarks.
- Some broad source leads in the n8n sample, especially under competitor pricing, do not directly answer the question. They need replacement or removal before the report is used as research evidence.
- The n8n workflow produces a Google Doc with plain text. The CrewAI Markdown output and n8n Google Doc are distinct artifacts from separate runs; they are not expected to have identical wording.
- Google OAuth test mode may require reconnecting after the test-user authorization expires. Secrets, `.env`, `.venv`, logs with sensitive data, and local credentials are excluded from the submission.

## Azure deployment

The demo runs on an Ubuntu 24.04 Azure VM using Docker Compose.

Public application:
https://hariunni74-gtm-demo.centralindia.cloudapp.azure.com

Availability is on demand. Contact the app owner to arrange access and
receive a demo access code.

### Services and access

| Service | Purpose | Access |
| --- | --- | --- |
| Streamlit | Brief entry, workflow selection, and results | Public HTTPS through Caddy; demo code required for submissions |
| MCP | Shared SerpAPI search service | Internal Docker network |
| n8n | Research workflow and Google Docs generation | Internal workflow endpoint; editor through an SSH tunnel |
| Caddy | HTTPS termination and reverse proxy | Public ports 80 and 443 |

`compose.yaml` defines the application and MCP service.
`compose.azure.yaml` adds n8n, Caddy, restart policies, and the internal
n8n Chat URL. `Caddyfile` configures the public hostname.

On Azure, both implementations reach MCP at `http://mcp:8000/mcp`.
Streamlit calls the published n8n Chat Trigger through
`http://n8n:5678/webhook/<chat-trigger-id>/chat`.

The n8n editor is bound to the VM's loopback interface. Enabling the
Chat Trigger does not expose port 5678 to the internet in this deployment.

### Configuration and persistent data

Create a private `.env` from `.env.example` and configure OpenAI,
SerpAPI, Langfuse, and demo access settings. Store the stable
`N8N_ENCRYPTION_KEY` in a separate private `.env.n8n`.

Keep both files out of Git and restrict their file permissions.
Configure OpenAI, Google Docs OAuth2, and Google Drive OAuth2 credentials
in the n8n editor; workflow JSON exports do not supply usable credentials.

The current editor tunnel uses this Google OAuth callback:

http://localhost:5679/rest/oauth2-credential/callback

Register the exact callback in the Google OAuth client's authorized
redirect URIs and keep the tunnel open during authorization.

Docker volumes persist application logs and the usage counter, n8n
data and credentials, and Caddy certificate data. Preserve these volumes
and securely back up the encryption key. Do not use `docker compose down -v`
when stopping the demo.

### Start the services

Run on the Azure VM from the project directory:

```bash
sudo docker build -t capstone-gtm:local .
sudo docker compose -f compose.yaml -f compose.azure.yaml up -d
sudo docker compose -f compose.yaml -f compose.azure.yaml ps
```

To access the editor, run on the laptop and keep the terminal open:

```bash
ssh -i ~/.ssh/capstone_azure_v2 \
  -N \
  -L 127.0.0.1:5679:127.0.0.1:5678 \
  -o ExitOnForwardFailure=yes \
  azureuser@20.235.98.2
```

Open `http://localhost:5679`. This tunnel is for administration;
visitors use the public Streamlit application.

### On-demand VM operation

Run these commands from a terminal authenticated to Azure:

```bash
# Start the demo VM.
az vm start \
  --resource-group rg-capstone-gtm-demo \
  --name vm-capstone-gtm

# Deallocate after use to stop VM compute billing.
az vm deallocate \
  --resource-group rg-capstone-gtm-demo \
  --name vm-capstone-gtm
```

Deallocation makes the demo unavailable. Disk and public IP charges
continue, and API usage is billed separately. Existing containers use
restart policies to resume after the VM starts.

## Demo access, privacy, and responsible use

The UI explains the two workflows before requesting an access code:

- **CrewAI:** Review results on screen and download a Word report.
- **n8n:** Open the generated Google Doc; download Word or PDF from
  Google Docs.

Use public or fictional business information. Briefs are processed by
external AI and search services. Do not enter personal data, credentials,
confidential documents, or company secrets.

The Azure n8n workflow shares each generated report with anyone holding
its link, with Reader permission and search discovery disabled. Reports
are stored in the app owner's Drive. This is link-based access, not
private delivery to an authenticated visitor.

### Submission controls

Before research starts, Streamlit:

1. Checks the demo access code.
2. Validates required fields, length limits, and unsupported control characters.
3. Screens the complete brief using OpenAI moderation.
4. Checks whether the product, geography, and customer fields are understandable.
5. Reserves an attempt from the shared daily allowance.
6. Starts the selected workflow.

The brief-quality check uses a small model call to identify unclear or
meaningless inputs and provide field-specific correction messages.
Rejected briefs and unavailable checks do not start research or consume
a research attempt. The quality-check call itself incurs model usage.
It assesses clarity, not market viability or factual accuracy, and can
make classification mistakes.

Flagged briefs are blocked. If moderation is unavailable or returns an
invalid response, research is also blocked. These cases do not reserve
a research attempt. Moderation is an automated screening layer and can
miss harmful content or flag legitimate requests; it does not guarantee
safe or accurate outputs.

Application scope screening: Before either workflow starts, the app checks whether the brief is understandable and within the demo’s supported scope. It excludes pornography, sexual-service offerings, and malicious activities such as fraud, credential theft, harassment, or exploitation. Legitimate sexual-health, education, prevention, and defensive cybersecurity research remains supported. Rejected briefs or unavailable screening do not start research or consume a demo attempt. Screening uses a model and may make mistakes; it does not guarantee detection of every prohibited request.

`DEMO_DAILY_RUN_LIMIT` defaults to five research attempts per UTC day,
shared across visitors and both implementations. Failed research attempts
count. The counter is stored in `logs/usage.sqlite3` on a persistent volume.

The access code is a shared demo gate, not individual user authentication.
These submission controls apply to the Streamlit entry point. Direct
editor executions bypass them; the n8n editor and endpoint remain private
in the Azure network configuration.

## Further enhancements

- Detailed n8n tracing and comparable model-cost measurements.
- Output screening and broader safety evaluations.
- Monthly API budget enforcement and concurrent-run controls.
- Stronger user authentication and private report delivery.
- Improved source retrieval, evidence coverage, and factual evaluation.

The repository currently has no license. A license decision is pending.
