import os
from google.genai import types


def get_schema_write_file():
    """
    The declaration we hand to the LLM so it knows this function exists.

    As with the others, working_directory is deliberately absent: we inject it ourselves.
    """
    return types.FunctionDeclaration(
        name="write_file",
        description="Writes and overwrites a file relative to the working directory with the provided content, creating any missing parent directories, and returns the number of characters written",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            required=["file_path", "content"],
            properties={
                "file_path": types.Schema(
                    type=types.Type.STRING,
                    description="Path of the file to write, relative to the working directory",
                ),
                "content": types.Schema(
                    type=types.Type.STRING,
                    description="The content to write into the file, as a single string",
                ),
            },
        ),
    )


def write_file(working_directory: str, file_path: str, content: str) -> str:
    abs_workig_dir=os.path.abspath(working_directory)
    abs_file_path=os.path.normpath(os.path.join(abs_workig_dir, file_path))

    # Make sure the target file lives inside the permitted working directory
    try:
        is_valid_target=os.path.commonpath([abs_workig_dir, abs_file_path])==abs_workig_dir
    except ValueError:
        # Raised when the two paths are on different drives, so it's definitely not valid
        is_valid_target=False

    if not is_valid_target:
        return f'Error: Cannot write to "{file_path}" as it is outside the permitted working directory'

    if os.path.isdir(abs_file_path):
        return f'Error: Cannot write to "{file_path}" as it is a directory'

    # Create any missing parent directories, then overwrite the file's contents
    try:
        os.makedirs(os.path.dirname(abs_file_path), exist_ok=True)
        with open(abs_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except OSError as e:
        return f'Error: {e}'

    return f'Successfully wrote to "{file_path}" ({len(content)} characters written)'
