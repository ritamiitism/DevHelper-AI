import os
import sys
import time
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
import argparse
from call_function import available_functions, call_function
from prompts import system_prompt
load_dotenv()

MODEL = "gemini-3.5-flash-lite"
MAX_ITERATIONS=20
MAX_MODEL_ATTEMPTS=6
RETRYABLE_CODES=(429, 503)
RETRY_WAIT_SECONDS=20


def generate_response(client, messages, verbose: bool = False):
    """Ask the model for its next step, waiting out rate limits and overloads.

    A free tier key only allows a few requests per minute, while an agent needs
    several per task, so a 429 here is expected rather than fatal.
    """
    for attempt in range(1, MAX_MODEL_ATTEMPTS+1):
        try:
            return client.models.generate_content(
                model=MODEL,
                contents=messages,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0,
                    tools=[available_functions],
                ),
            )
        except errors.APIError as e:
            if e.code not in RETRYABLE_CODES or attempt==MAX_MODEL_ATTEMPTS:
                raise
            if verbose:
                print(f"Model unavailable ({e.code}), retrying in {RETRY_WAIT_SECONDS}s (attempt {attempt}/{MAX_MODEL_ATTEMPTS})")
            time.sleep(RETRY_WAIT_SECONDS)


def main():

    api_key=os.environ.get("GEMINI_API_KEY")
    if api_key is None:
        raise RuntimeError("GEMINI_API_KEY is not set")

    parser = argparse.ArgumentParser(description="Chatbot")
    parser.add_argument("user_prompt", type=str, help="User prompt")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()

    client= genai.Client(api_key=api_key)

    messages=[types.Content(role="user", parts=[types.Part(text=args.user_prompt)])]

    if args.verbose:
        print(f"User prompt: {args.user_prompt}")

    # The agent loop: keep calling the model until it stops asking for functions
    for _ in range(MAX_ITERATIONS):
        response=generate_response(client, messages, verbose=args.verbose)

        if response.usage_metadata is None:
            raise RuntimeError("Response is missing usage metadata")

        if args.verbose:
            print(f"Prompt tokens: {response.usage_metadata.prompt_token_count}")
            print(f"Response tokens: {response.usage_metadata.candidates_token_count}")

        # The model's own turn (including the function calls it asked for) goes into the
        # history first, so it stays aware of everything it has said so far
        for candidate in response.candidates or []:
            if candidate.content is not None:
                messages.append(candidate.content)

        # No function calls means this is a final response for the user
        if not response.function_calls:
            print(response.text)
            return

        # Run each requested function and feed the results back as the next turn
        response_parts=[]
        for function_call in response.function_calls:
            result_message=call_function(function_call, verbose=args.verbose)
            function_response=result_message.parts[0].function_response.response
            if not function_response:
                raise Exception("Empty function response returned to the LLM")
            if args.verbose:
                value=function_response.get("result")
                print(f"-> {value if value is not None else function_response}")
            response_parts.extend(result_message.parts)

        messages.append(types.Content(role="user", parts=response_parts))

    print("Maximum iterations reached without a final response")
    sys.exit(1)

    


if __name__ == "__main__":
    main()


