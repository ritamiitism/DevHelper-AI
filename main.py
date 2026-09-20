import sys
import argparse
from dotenv import load_dotenv
from agent_core import run_agent
load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Chatbot")
    parser.add_argument("user_prompt", type=str, help="User prompt")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()
    if args.verbose:
        print(f"User prompt: {args.user_prompt}")
    try:
        result = run_agent(args.user_prompt, verbose=args.verbose)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    if args.verbose:
        print(f"Prompt tokens: {result.prompt_tokens}")
        print(f"Response tokens: {result.response_tokens}")
    print(result.final_text)
    if result.hit_max_iterations:
        sys.exit(1)


if __name__ == "__main__":
    main()

