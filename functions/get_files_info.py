import os
from google.genai import types


def get_schema_get_files_info():
    """
    The declaration we hand to the LLM so it knows this function exists.

    Notice that we don't mention the working_directory parameter here: we inject that
    ourselves "from the outside", so the agent can never see or change it.
    """
    return types.FunctionDeclaration(
        name="get_files_info",
        description="Lists files in a specified directory relative to the working directory, providing file size and directory status",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            required=["directory"],
            properties={
                "directory": types.Schema(
                    type=types.Type.STRING,
                    description='Directory path to list files from, relative to the working directory. Use "." for the working directory itself.',
                ),
            },
        ),
    )


def get_files_info(working_directory, directory=None):
    if directory is None:
        directory='.'
    abs_workig_dir=os.path.abspath(working_directory)
    abs_directory=os.path.normpath(os.path.join(abs_workig_dir, directory))

    # Make sure the target directory lives inside the permitted working directory
    try:
        is_valid_target=os.path.commonpath([abs_workig_dir, abs_directory])==abs_workig_dir
    except ValueError:
        # Raised when the two paths are on different drives, so it's definitely not valid
        is_valid_target=False

    if not is_valid_target:
        return f'Error: Cannot list "{directory}" as it is outside the permitted working directory'

    if not os.path.isdir(abs_directory):
        return f'Error: "{directory}" is not a directory'

    # Build a line of info for every item in the target directory
    try:
        files_info=[]
        for item in os.listdir(abs_directory):
            item_path=os.path.join(abs_directory, item)
            file_size=os.path.getsize(item_path)
            is_dir=os.path.isdir(item_path)
            files_info.append(f'- {item}: file_size={file_size} bytes, is_dir={is_dir}')
        return '\n'.join(files_info)
    except OSError as e:
        return f'Error: {e}'
