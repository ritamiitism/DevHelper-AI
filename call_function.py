from google.genai import types

from collections.abc import Callable

from functions.get_files_info import get_files_info, get_schema_get_files_info
from functions.get_file_content import get_file_content, get_schema_get_file_content
from functions.run_python_file import run_python_file, get_schema_run_python_file
from functions.write_file import write_file, get_schema_write_file

# The tool declarations we hand to the LLM so it can ask for them by name.
# The LLM only *describes* the call it wants; we're still the ones who run the code.
available_functions=types.Tool(
    function_declarations=[
        get_schema_get_files_info(),
        get_schema_get_file_content(),
        get_schema_run_python_file(),
        get_schema_write_file(),
    ],
)

# Function name -> the real Python function that does the work
function_map: dict[str, Callable[..., str]]={
    "get_files_info": get_files_info,
    "get_file_content": get_file_content,
    "run_python_file": run_python_file,
    "write_file": write_file,
}

# The sandbox the agent is allowed to touch. The LLM never sees this value:
# we inject it ourselves, so the model can't point the tools somewhere else.
WORKING_DIRECTORY="./calculator"


def call_function(function_call: types.FunctionCall, verbose: bool = False) -> types.Content:
    """Run the function the model asked for and wrap its result for the next request."""
    function_name=function_call.name or ""
    function_args=dict(function_call.args or {})

    if verbose:
        print(f" - Calling function: {function_name}({function_args})")
    else:
        print(f" - Calling function: {function_name}")

    # The model can ask for anything, so make sure it's a function we actually have
    if function_name not in function_map:
        return types.Content(
            role="tool",
            parts=[
                types.Part.from_function_response(
                    name=function_name,
                    response={"error": f"Unknown function: {function_name}"},
                ),
            ],
        )

    function_args["working_directory"]=WORKING_DIRECTORY

    # Call the function, passing the model's arguments as keyword arguments
    result=function_map[function_name](**function_args)

    return types.Content(
        role="tool",
        parts=[
            types.Part.from_function_response(
                name=function_name,
                response={"result": result},
            ),
        ],
    )
