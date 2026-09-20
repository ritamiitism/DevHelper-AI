import os
from config import MAX_CHARS
from google.genai import types


def get_schema_get_file_content():
    """
    The declaration we hand to the LLM so it knows this function exists.

    As with the others, working_directory is deliberately absent: we inject it ourselves.
    """
    return types.FunctionDeclaration(
        name="get_file_content",
        description=f"Reads a file relative to the working directory and returns its contents as a string, truncating the content at {MAX_CHARS} characters if the file is larger",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            required=["file_path"],
            properties={
                "file_path": types.Schema(
                    type=types.Type.STRING,
                    description="Path of the file to read, relative to the working directory",
                ),
            },
        ),
    )


def get_file_content(working_directory: str, file_path: str) -> str:
    abs_workig_dir=os.path.abspath(working_directory)
    abs_file_path=os.path.normpath(os.path.join(abs_workig_dir, file_path))

    # Make sure the target file lives inside the permitted working directory
    try:
        is_valid_target=os.path.commonpath([abs_workig_dir, abs_file_path])==abs_workig_dir
    except ValueError:
        # Raised when the two paths are on different drives, so it's definitely not valid
        is_valid_target=False

    if not is_valid_target:
        return f'Error: Cannot read "{file_path}" as it is outside the permitted working directory'

    if not os.path.isfile(abs_file_path):
        return f'Error: File not found or is not a regular file: "{file_path}"'

    # Only read up to MAX_CHARS so a huge file can't blow up our token budget
    try:
        with open(abs_file_path, 'r', encoding='utf-8') as f:
            content=f.read(MAX_CHARS)
            # If one more character comes back, the file was longer than the limit
            if f.read(1):
                content+=f'[...File "{file_path}" truncated at {MAX_CHARS} characters]'
        return content
    except (OSError, UnicodeDecodeError) as e:
        return f'Error: {e}'
