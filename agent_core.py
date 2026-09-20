"""Reusable agent loop shared by the CLI (main.py) and Streamlit UI (app.py)."""
import os
import time
from dataclasses import dataclass, field
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
import call_function as call_function_module
from prompts import system_prompt

load_dotenv()

MODEL = "gemini-3.5-flash-lite"
MAX_ITERATIONS = 20
MAX_MODEL_ATTEMPTS = 6
RETRYABLE_CODES = (429, 503)
RETRY_WAIT_SECONDS = 20


def generate_response(client, messages, verbose: bool = False):
    """Ask Gemini for its next step, waiting out rate limits/overloads."""
    for attempt in range(1, MAX_MODEL_ATTEMPTS + 1):
        try:
            return client.models.generate_content(
                model=MODEL,
                contents=messages,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0,
                    tools=[call_function_module.available_functions],
                ),
            )
        except errors.APIError as e:
            if e.code not in RETRYABLE_CODES or attempt == MAX_MODEL_ATTEMPTS:
                raise
            if verbose:
                print(f"Model unavailable ({e.code}), retrying in {RETRY_WAIT_SECONDS}s (attempt {attempt}/{MAX_MODEL_ATTEMPTS})")
            time.sleep(RETRY_WAIT_SECONDS)


@dataclass
class AgentEvent:
    kind: str  # "status" | "function_call" | "function_result"
    message: str


@dataclass
class AgentResult:
    final_text: str
    iterations_used: int
    prompt_tokens: int = 0
    response_tokens: int = 0
    events: list[AgentEvent] = field(default_factory=list)
    writes: list[dict] = field(default_factory=list)
    hit_max_iterations: bool = False


def run_agent(
    user_prompt: str,
    working_directory: str | None = None,
    verbose: bool = False,
    on_event=None,
) -> AgentResult:
    """Run agent loop against working_directory, return AgentResult."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key is None:
        raise RuntimeError("GEMINI_API_KEY is not set")
    prev = call_function_module.WORKING_DIRECTORY
    if working_directory is not None:
        call_function_module.set_working_directory(working_directory)
    active = call_function_module.WORKING_DIRECTORY
    events: list[AgentEvent] = []
    writes: list[dict] = []

    def emit_and_record(kind: str, message: str):
        events.append(AgentEvent(kind=kind, message=message))
        if verbose:
            print(message)
        if on_event is not None:
            try:
                on_event(AgentEvent(kind=kind, message=message))
            except Exception:
                pass

    try:
        client = genai.Client(api_key=api_key)
        messages = [types.Content(role="user", parts=[types.Part(text=user_prompt)])]
        prompt_toks = 0
        resp_toks = 0
        for iteration in range(1, MAX_ITERATIONS + 1):
            emit_and_record("status", f"Iteration {iteration}/{MAX_ITERATIONS}: asking Gemini...")
            response = generate_response(client, messages, verbose=verbose)
            if response.usage_metadata is None:
                raise RuntimeError("Response is missing usage metadata")
            prompt_toks += response.usage_metadata.prompt_token_count or 0
            resp_toks += response.usage_metadata.candidates_token_count or 0
            for candidate in response.candidates or []:
                if candidate.content is not None:
                    messages.append(candidate.content)
            if not response.function_calls:
                return AgentResult(
                    final_text=response.text or "",
                    iterations_used=iteration,
                    prompt_tokens=prompt_toks,
                    response_tokens=resp_toks,
                    events=events,
                    writes=writes,
                )
            response_parts = []
            for function_call in response.function_calls:
                fname = function_call.name or ""
                fargs = dict(function_call.args or {})
                emit_and_record("function_call", f"Calling {fname}({fargs}) in '{active}'")
                result_message = call_function_module.call_function(function_call, verbose=verbose)
                function_response = result_message.parts[0].function_response.response
                if not function_response:
                    raise Exception("Empty function response returned to the LLM")
                value = function_response.get("result")
                emit_and_record("function_result", f"{fname} -> {str(value)[:2000]}")
                if fname == "write_file" and value and not str(value).startswith("Error"):
                    writes.append({"file_path": fargs.get("file_path", ""), "result": value})
                response_parts.extend(result_message.parts)
            messages.append(types.Content(role="user", parts=response_parts))
        return AgentResult(
            final_text="Maximum iterations reached without a final response",
            iterations_used=MAX_ITERATIONS,
            prompt_tokens=prompt_toks,
            response_tokens=resp_toks,
            events=events,
            writes=writes,
            hit_max_iterations=True,
        )
    finally:
        call_function_module.set_working_directory(prev)

