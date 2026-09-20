import os
import subprocess
from google.genai import types


def get_schema_run_python_file():
    """
    The declaration we hand to the LLM so it knows this function exists.

    As with the others, working_directory is deliberately absent: we inject it ourselves.
    """
    return types.FunctionDeclaration(
        name="run_python_file",
        description="Runs a Python file relative to the working directory in a subprocess with a 30 second timeout, optionally passing command-line arguments, and returns the exit code along with any STDOUT and STDERR",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            required=["file_path"],
            properties={
                "file_path": types.Schema(
                    type=types.Type.STRING,
                    description="Path of the Python file to execute, relative to the working directory",
                ),
                "args": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                    description="Optional list of command-line arguments to pass to the Python file",
                ),
            },
        ),
    )


def run_python_file(
    working_directory: str, file_path: str, args: list[str] | None = None
) -> str:
    try:
        abs_workig_dir=os.path.abspath(working_directory)
        abs_file_path=os.path.normpath(os.path.join(abs_workig_dir, file_path))

        # Make sure the target file lives inside the permitted working directory
        try:
            is_valid_target=os.path.commonpath([abs_workig_dir, abs_file_path])==abs_workig_dir
        except ValueError:
            # Raised when the two paths are on different drives, so it's definitely not valid
            is_valid_target=False

        if not is_valid_target:
            return f'Error: Cannot execute "{file_path}" as it is outside the permitted working directory'

        if not os.path.isfile(abs_file_path):
            return f'Error: "{file_path}" does not exist or is not a regular file'

        if not file_path.endswith('.py'):
            return f'Error: "{file_path}" is not a Python file'

        command=['python', abs_file_path]
        if args:
            command.extend(args)

        # 30 second timeout so the agent can't hang forever on runaway code
        completed_process=subprocess.run(
            command,
            cwd=abs_workig_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )

        output=[]
        if completed_process.returncode!=0:
            output.append(f"Process exited with code {completed_process.returncode}")
        if not completed_process.stdout and not completed_process.stderr:
            output.append("No output produced")
        else:
            if completed_process.stdout:
                output.append(f"STDOUT: {completed_process.stdout}")
            if completed_process.stderr:
                output.append(f"STDERR: {completed_process.stderr}")
        return '\n'.join(output)
    except Exception as e:
        return f"Error: executing Python file: {e}"
