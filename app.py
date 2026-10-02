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
from gtm_agents.usage_limits import reserve_run, remaining_runs
from gtm_agents.report_export import build_word_report
from gtm_agents.input_safety import (
    SafetyCheckUnavailable,
    check_brief_safety,
)
from gtm_agents.brief_quality import (
    BriefCheckUnavailable,
    check_brief_quality,
)

load_dotenv()

st.set_page_config(page_title="Market Research & GTM Planner", layout="wide")

st.title("Market Research & GTM Planner")
st.caption("An Agentic AI portfolio demo for research and strategy planning")

st.markdown(
    "Explore a product idea, its potential customers, competitors, and "
    "go-to-market options. Enter a product or market, geography, and target "
    "customer to generate a **provisional research and strategy report**."
)

with st.expander("How to use this demo", expanded=True):
    st.markdown(
        """
1. **Request access:** Contact the app owner through the LinkedIn post or
   message that brought you here to receive a demo access code.
2. **Describe your idea:** Enter the product or market, target geography,
   and the customers who would buy it.
3. **Choose a workflow:**
   - **CrewAI:** Python agents research and assess your brief. Review the
     results on screen and download a Word report.
   - **n8n:** An automated agent workflow creates a Google Doc.
     Open the report link, then use **File → Download** for Word or PDF.
4. **Submit once and wait:** Recent Azure tests took approximately
   3–5 minutes. Timing varies; keep the page open while it runs.
5. **Review critically:** Check sources, evidence gaps, and assumptions
   before using the output for a business decision.
"""
    )

st.warning(
    "Use public or fictional business information only. Do not enter "
    "personal data, passwords, confidential documents, or company secrets. "
    "Your brief is processed by external AI and search services. "
    "n8n reports are stored in the app owner's Google Drive and are "
    "readable by anyone holding their report link."
)

st.info(
    "This is an experimental portfolio demo. Outputs may contain errors "
    "or incomplete evidence and require human review. The daily run "
    "allowance is shared across all visitors; failed runs also count."
)

st.caption(
    "Explore a genuine business idea, research a market, and build "
    "a provisional go-to-market plan."
)

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

# Show the shared allowance before visitors submit a brief.
try:
    daily_limit = int(os.getenv("DEMO_DAILY_RUN_LIMIT", "5"))
    attempts_remaining = remaining_runs(daily_limit)
except Exception:
    st.error("Could not check demo availability. Please try again later.")
    st.stop()

allowance_notice = st.empty()
allowance_notice.info(
    f"Demo availability: {attempts_remaining} of {daily_limit} "
    "research attempts remaining today."
)
st.caption(
    "Shared across all visitors. Resets daily at 00:00 UTC "
    "(5:30 AM India time). Failed research attempts also count."
)

if attempts_remaining == 0:
    st.warning("Today's demo allowance is exhausted. Please return after the reset.")


# Track processing separately for each visitor's browser session.
st.session_state.setdefault("research_busy", False)

def mark_research_busy():
    """Accept one submission while this session is idle."""
    if st.session_state.research_busy:
        return

    st.session_state.research_busy = True
    st.session_state.submission_requested = True
    st.session_state.research_messages = []
    st.session_state.pop("last_research_result", None)


def research_message(kind, text):
    """Keep processing messages available after the interface redraws."""
    st.session_state.setdefault("research_messages", []).append(
        (kind, str(text))
    )
    getattr(st, kind)(text)

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
    submitted = st.form_submit_button(
        "Create GTM plan",
        type="primary",
        disabled=(
            attempts_remaining == 0
            or st.session_state.research_busy
        ),
        on_click=mark_research_busy,
    )

# Consume the callback's request once; ignored repeat clicks start no work.
submitted = st.session_state.pop("submission_requested", False)


def process_research_submission():
    global topic, geography, audience
    try:
        # Validate both workflows' inputs before reserving a demo attempt.
        if submitted:
            topic = topic.strip()
            geography = geography.strip()
            audience = audience.strip()

            input_rules = [
                ("Product or market", topic, 10, 1000),
                ("Target geography", geography, 2, 100),
                ("Target customer", audience, 5, 300),
            ]

            validation_errors = []
            for label, value, minimum, maximum in input_rules:
                if not minimum <= len(value) <= maximum:
                    validation_errors.append(
                        f"{label} must contain {minimum}–{maximum} characters."
                    )

                # Allow normal whitespace, but reject hidden control characters.
                if any(
                    ord(character) < 32 and character not in "\n\r\t"
                    for character in value
                ):
                    validation_errors.append(
                        f"{label} contains unsupported control characters."
                    )

            if validation_errors:
                for message in validation_errors:
                    research_message("error", message)
                return

        # Screen validated inputs before starting research or consuming an attempt.
        if submitted:
            try:
                with st.spinner("Checking the research brief..."):
                    flagged = check_brief_safety(topic, geography, audience)
            except SafetyCheckUnavailable:
                research_message("error",
                    "We couldn't complete the safety check. "
                    "No research was started and no demo attempt was used. "
                    "Please try again later."
                )
                return

            if flagged:
                research_message("warning",
                    "This brief was flagged by automated safety screening. "
                    "No research was started and no demo attempt was used. "
                    "If your request is legitimate business research, contact "
                    "the app owner for review."
                )
                return

        # Require an understandable brief before consuming a research attempt.
        if submitted:
            try:
                with st.spinner("Checking that your brief is clear..."):
                    decision = check_brief_quality(topic, geography, audience)
            except BriefCheckUnavailable:
                research_message("error",
                    "We couldn't check the brief right now. "
                    "No research was started and no demo attempt was used. "
                    "Please try again later."
                )
                return
            # Enforce demo scope for both workflows before reserving an attempt.
            if not decision.scope_allowed:
                research_message("warning",
                    "This brief is outside the demo's supported scope, "
                    "or its intended use needs clarification."
                )
                research_message("info",
                    "The demo does not support pornography, sexual-service "
                    "offerings, or activities intended to enable fraud, "
                    "cyber abuse, harassment, exploitation, or deliberate harm. "
                    "Legitimate health, education, prevention, and defensive "
                    "security research is supported."
                )
                research_message("caption",
                    "No research was started and no demo attempt was used. "
                    "If your request has a legitimate purpose, clarify it "
                    "or contact the app owner for review."
                )
                return

            corrections = []

            if not decision.topic_clear:
                corrections.append(
                    "Product or market: describe what you want to research. "
                    "Example: AI-powered inventory forecasting software."
                )
            if not decision.geography_clear:
                corrections.append(
                    "Target geography: enter a recognizable location or region. "
                    "Examples: India, United States, Europe, or Global."
                )
            if not decision.customer_clear:
                corrections.append(
                    "Target customer: describe who would buy or use the solution. "
                    "Example: independent retailers and inventory managers."
                )

            if corrections:
                research_message("warning", "Please clarify your brief before starting research.")
                for correction in corrections:
                    research_message("error", correction)
                research_message("caption",
                    "No research was started and no demo attempt was used. "
                    "Automated checks can make mistakes; contact the app owner "
                    "if a clear business brief keeps being rejected."
                )
                return

        # Reserve an allowance before starting either implementation.
        if submitted and topic.strip() and geography.strip() and audience.strip():
            # Missing n8n configuration should not consume an attempt.
            if implementation == "n8n" and not os.getenv("N8N_CHAT_URL", "").strip():
                research_message("error", "Configure N8N_CHAT_URL before running n8n.")
                return

            run_id = str(uuid.uuid4())

            try:
                daily_limit = int(os.getenv("DEMO_DAILY_RUN_LIMIT", "5"))
                allowed = reserve_run(run_id, daily_limit)
            except (ValueError, OSError, RuntimeError) as exc:
                research_message("error", "Could not check the demo allowance. Contact the app owner.")
                return
            except Exception:
                # Block execution if the usage database is unavailable.
                research_message("error", "Could not check the demo allowance. Contact the app owner.")
                return

            if not allowed:
                research_message("warning", "The demo's daily run allowance has been reached.")
                return
            # Refresh the indicator after this submission reserves an attempt.
            allowance_notice.info(
                f"Demo availability: {remaining_runs(daily_limit)} of {daily_limit} "
                "research attempts remaining today."
            )

        if submitted:
            if not topic.strip() or not geography.strip() or not audience.strip():
                research_message("error", "Fill in the topic, geography, and target customer.")
            elif implementation == "CrewAI":
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
                    research_message("caption",
                        f"Execution time: {int(minutes)} min {seconds:.1f} sec"
                    )
                    log_run(
                        run_id=run_id,
                        implementation="CrewAI",
                        status="completed",
                        elapsed_seconds=elapsed_seconds,
                    )
                    research_message("success", f"Flow status: {result['status']}")
                    # Preserve the completed report when the interface redraws.
                    st.session_state.last_research_result = {
                        "implementation": "CrewAI",
                        "run_id": run_id,
                        "status": result["status"],
                        "elapsed_seconds": elapsed_seconds,
                        "strategy": result["strategy_notes"],
                        "analysis": flow.state.analysis_notes,
                        "research_notes": flow.state.research_notes,
                        "source_checks": flow.state.source_checks,
                        "word_report": None,
                    }
                    st.subheader("Provisional GTM strategy")
                    st.markdown(result["strategy_notes"])

                    with st.expander("Market Analyst assessment"):
                        st.markdown(flow.state.analysis_notes)

                    with st.expander("Research candidates and source checks"):
                        st.code(flow.state.research_notes, language="json")
                        st.json(flow.state.source_checks)

                    # Export the completed result as word doc; no new research calls are made.
                    try:
                        word_report = build_word_report(
                            brief={
                                "topic": topic.strip(),
                                "geography": geography.strip(),
                                "target_customer": audience.strip(),
                            },
                            strategy=result["strategy_notes"],
                            analysis=flow.state.analysis_notes,
                            research_notes=flow.state.research_notes,
                            source_checks=flow.state.source_checks,
                            run_id=run_id,
                            elapsed_seconds=elapsed_seconds,
                        )
                    except Exception:
                        # An export failure does not make the research run a failure.
                        research_message("warning",
                            "Research completed, but the Word export could not "
                            "be generated. You can still copy the results above."
                        )
                    else:
                        st.session_state.last_research_result["word_report"] = word_report
                        st.download_button(
                            label="Download Word report",
                            data=word_report,
                            file_name=f"gtm_report_{run_id}.docx",
                            mime=(
                                "application/vnd.openxmlformats-officedocument."
                                "wordprocessingml.document"
                            ),
                            on_click="ignore",
                        )

                except Exception as exc:
                    log_run(
                        run_id=run_id,
                        implementation="CrewAI",
                        status="failed",
                        elapsed_seconds=time.perf_counter() - started_at,
                        error_type=type(exc).__name__,
                    )
                    research_message("error", f"The CrewAI run failed: {exc}")
            else:
                chat_url = os.getenv("N8N_CHAT_URL", "").strip()
                if not chat_url:
                    research_message("error", "Set N8N_CHAT_URL to the Chat URL shown by the n8n Chat Trigger.")
                else:
                    prompt = (
                        f"Topic: {topic.strip()}\n"
                        f"Geography: {geography.strip()}\n"
                        f"Target customer: {audience.strip()}"
                    )
                    username = os.getenv("N8N_CHAT_USERNAME", "")
                    password = os.getenv("N8N_CHAT_PASSWORD", "")
                    auth = (username, password) if username and password else None
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
                        research_message("caption",
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
                            research_message("warning", "The request finished, but n8n did not return a document ID. Check Executions and Google Drive.")
                            st.json(result)
                        else:
                            log_run(
                                run_id=run_id,
                                implementation="n8n",
                                status="document_returned",
                                elapsed_seconds=elapsed_seconds,
                            )
                            research_message("success", "n8n completed and wrote the GTM report to Google Docs.")
                            st.session_state.last_research_result = {
                                "implementation": "n8n",
                                "run_id": run_id,
                                "elapsed_seconds": elapsed_seconds,
                                "document_id": document_id,
                            }
                            st.link_button(
                                "Open GTM report in Google Docs",
                                f"https://docs.google.com/document/d/{document_id}/edit",
                            )
                            research_message("caption", f"Document ID: {document_id}")
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
                        research_message("error", f"Could not complete the n8n run: {exc}")
                        research_message("info", "Check the Chat URL, the workflow's published state, and the latest n8n execution.")

    except Exception:
        research_message("error", "An unexpected error interrupted processing. Check the execution before retrying.")
    finally:
        st.session_state.research_busy = False
    # Validation stops also release the busy flag via finally.

if submitted:
    try:
        process_research_submission()
    finally:
        st.rerun()

# Restore the previous outcome without starting another workflow.
for kind, text in st.session_state.get("research_messages", []):
    getattr(st, kind)(text)

saved = st.session_state.get("last_research_result")

if saved:
    if saved["implementation"] == "CrewAI":
        st.subheader("Provisional GTM strategy")
        st.markdown(saved["strategy"])

        with st.expander("Market Analyst assessment"):
            st.markdown(saved["analysis"])

        with st.expander("Research candidates and source checks"):
            st.code(saved["research_notes"], language="json")
            st.json(saved["source_checks"])

        if saved["word_report"] is not None:
            st.download_button(
                label="Download Word report",
                data=saved["word_report"],
                file_name=f"gtm_report_{saved['run_id']}.docx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                ),
                on_click="ignore",
            )
    else:
        document_id = saved["document_id"]
        st.link_button(
            "Open GTM report in Google Docs",
            f"https://docs.google.com/document/d/{document_id}/edit",
        )
        st.caption(f"Document ID: {document_id}")
