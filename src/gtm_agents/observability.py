"""Configure tracing for CrewAI operations and OpenAI model calls."""

from threading import Lock

from dotenv import load_dotenv
from langfuse import get_client
from openinference.instrumentation import TraceConfig
from openinference.instrumentation.crewai import CrewAIInstrumentor
from openinference.instrumentation.openai import OpenAIInstrumentor

_setup_lock = Lock()
_initialized = False


def setup_observability():
    """Initialize tracing once per process and return the Langfuse client."""
    global _initialized

    with _setup_lock:
        # Load credentials before initializing the tracing client.
        load_dotenv()
        client = get_client()

        if not _initialized:
            # Omit prompt and response content from instrumented spans.
            config = TraceConfig(
                hide_inputs=True,
                hide_outputs=True,
                hide_input_messages=True,
                hide_output_messages=True,
                hide_llm_tools=True,
            )

            # Capture agent operations and underlying OpenAI requests.
            CrewAIInstrumentor().instrument(config=config)
            OpenAIInstrumentor().instrument(config=config)
            _initialized = True

    return client