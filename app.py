"""Display the research brief form and results.

CrewAI runs the Python workflow directly.
n8n receives the brief through its Chat Trigger URL and returns a
Google Docs document ID when the workflow completes.
"""
import os
import uuid
import httpx
import streamlit as st
import time
import hmac

from dotenv import load_dotenv
from gtm_agents.planner import build_brief
from gtm_agents.flow import GTMFlow
from gtm_agents.run_logging import log_run
from gtm_agents.observability import setup_observability

load_dotenv()

st.set_page_config(page_title="Market Research & GTM Planner", layout="wide")

st.title("Multi-Agent Market Research & GTM Planner")
st.caption("Compare n8n and CrewAI implementations using the same research brief.")

# Require a configured access code before allowing billable submissions.
expected_code = os.getenv("DEMO_ACCESS_CODE", "")

if not expected_code:
    st.error("Demo access is not configured. Contact the app owner.")
    st.stop()

entered_code = st.text_input(
    "Demo access code",
    type="password",
    key="demo_access_code",
)

if not entered_code:
    st.info("Enter the access code provided by the app owner, then press Enter.")
    st.stop()

if not hmac.compare_digest(
    entered_code.encode("utf-8"),
    expected_code.encode("utf-8"),
):
    st.error("Incorrect access code.")
    st.stop()

# Collect the same brief fields for either implementation.
with st.form("research_brief"):
    topic = st.text_area(
        "What product or market should we research?",
        placeholder="Example: AI-powered product discovery portal for consumer healthcare products",
        height=100,
    )
    geography = st.text_input("Target geography", placeholder="Example: United States",
    )
    audience = st.text_input(
        "Target customer",
        placeholder="Example: Consumer healthcare brands and retail product teams",
    )
    implementation = st.selectbox("Run with", ["CrewAI", "n8n"])
    submitted = st.form_submit_button("Create GTM plan", type="primary")

if submitted:
    if not topic.strip() or not geography.strip() or not audience.strip():
        st.error("Fill in the topic, geography, and target customer.")
    elif implementation == "CrewAI":
        run_id = str(uuid.uuid4())
        try:
            # Measure elapsed time across the complete CrewAI workflow.
            started_at = time.perf_counter()
            with st.spinner("Running the CrewAI research flow..."):
                # Create a fresh workflow so each submission has its own state.
                flow = GTMFlow()
                # Group this workflow's operations under one Langfuse trace.
                langfuse = setup_observability()
                try:
                    with langfuse.start_as_current_observation(
                        as_type="span",
                        name="crewai-gtm-run",
                        metadata={
                            "run_id": run_id,
                            "implementation": "CrewAI",
                        },
                    ):
                        result = flow.kickoff(inputs={
                            "topic": topic.strip(),
                            "geography": geography.strip(),
                            "target_customer": audience.strip(),
                        })
                finally:
                    # Export queued observations even if the workflow fails.
                    langfuse.flush()

            # Display elapsed time across the complete CrewAI workflow.
            elapsed_seconds = time.perf_counter() - started_at
            minutes, seconds = divmod(elapsed_seconds, 60)
            st.caption(
                f"Execution time: {int(minutes)} min {seconds:.1f} sec"
            )
            log_run(
                run_id=run_id,
                implementation="CrewAI",
                status="completed",
                elapsed_seconds=elapsed_seconds,
            )
            st.success(f"Flow status: {result['status']}")
            st.subheader("Provisional GTM strategy")
            st.markdown(result["strategy_notes"])

            with st.expander("Market Analyst assessment"):
                st.markdown(flow.state.analysis_notes)

            with st.expander("Research candidates and source checks"):
                st.code(flow.state.research_notes, language="json")
                st.json(flow.state.source_checks)
        except Exception as exc:
            log_run(
                run_id=run_id,
                implementation="CrewAI",
                status="failed",
                elapsed_seconds=time.perf_counter() - started_at,
                error_type=type(exc).__name__,
            )
            st.error(f"The CrewAI run failed: {exc}")
    else:
        chat_url = os.getenv("N8N_CHAT_URL", "").strip()
        if not chat_url:
            st.error("Set N8N_CHAT_URL to the Chat URL shown by the n8n Chat Trigger.")
        else:
            prompt = (
                f"Topic: {topic.strip()}\n"
                f"Geography: {geography.strip()}\n"
                f"Target customer: {audience.strip()}"
            )
            username = os.getenv("N8N_CHAT_USERNAME", "")
            password = os.getenv("N8N_CHAT_PASSWORD", "")
            auth = (username, password) if username and password else None
            run_id = str(uuid.uuid4())
            try:
                # Measure the time the UI waits for the n8n response.
                started_at = time.perf_counter()
                with st.spinner("Running n8n and creating the Google Doc. This may take several minutes..."):
                    with httpx.Client(timeout=httpx.Timeout(1200.0, connect=15.0)) as client:
                        # Send the brief to n8n with a new chat session ID.
                        response = client.post(
                            chat_url,
                            json={
                                "action": "sendMessage",
                                "sessionId": run_id,
                                "chatInput": prompt,
                            },
                            auth=auth,
                        )
                        response.raise_for_status()
                        result = response.json()

                # Display elapsed time for the n8n response.
                elapsed_seconds = time.perf_counter() - started_at
                minutes, seconds = divmod(elapsed_seconds, 60)
                st.caption(
                    f"Response time: {int(minutes)} min {seconds:.1f} sec"
                )

                if isinstance(result, list) and len(result) == 1:
                    result = result[0]
                if not isinstance(result, dict):
                    raise ValueError("n8n returned an unexpected response format.")
                if result.get("error"):
                    raise ValueError(str(result["error"]))

                # Use the returned document ID to build the Google Docs link.
                document_id = result.get("documentId") or result.get("id")
                if not document_id:
                    log_run(
                        run_id=run_id,
                        implementation="n8n",
                        status="response_without_document",
                        elapsed_seconds=elapsed_seconds,
                    )
                    st.warning("The request finished, but n8n did not return a document ID. Check Executions and Google Drive.")
                    st.json(result)
                else:
                    log_run(
                        run_id=run_id,
                        implementation="n8n",
                        status="document_returned",
                        elapsed_seconds=elapsed_seconds,
                    )
                    st.success("n8n completed and wrote the GTM report to Google Docs.")
                    st.link_button(
                        "Open GTM report in Google Docs",
                        f"https://docs.google.com/document/d/{document_id}/edit",
                    )
                    st.caption(f"Document ID: {document_id}")
            except (httpx.HTTPError, ValueError) as exc:
                log_run(
                    run_id=run_id,
                    implementation="n8n",
                    status=(
                        "timeout_completion_unknown"
                        if isinstance(exc, httpx.TimeoutException)
                        else "ui_request_failed"
                    ),
                    elapsed_seconds=time.perf_counter() - started_at,
                    error_type=type(exc).__name__,
                )
                st.error(f"Could not complete the n8n run: {exc}")
                st.info("Check the Chat URL, the workflow's published state, and the latest n8n execution.")
