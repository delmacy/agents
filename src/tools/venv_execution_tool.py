import os
import subprocess
import sys
from typing import Optional, Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

class VenvExecutionToolInput(BaseModel):
    command: str = Field(..., description="The command to run in the virtual environment (e.g., 'pip install -r requirements.txt' or 'python test_main.py').")

class VenvExecutionTool(BaseTool):
    name: str = "venv_execution_tool"
    description: str = "Executes commands inside a specific virtual environment for a job. Handles venv creation if missing."
    job_id: str = Field(..., description="The ID of the job to target the specific venv.")

    def _run(self, command: str) -> str:
        venv_dir = os.path.abspath(os.path.join("output", self.job_id, "venv"))

        # Determine python executable path
        if sys.platform == "win32":
            python_executable = os.path.join(venv_dir, "Scripts", "python.exe")
            pip_executable = os.path.join(venv_dir, "Scripts", "pip.exe")
        else:
            python_executable = os.path.join(venv_dir, "bin", "python")
            pip_executable = os.path.join(venv_dir, "bin", "pip")

        # Create venv if it doesn't exist
        if not os.path.exists(venv_dir):
            try:
                subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
                print(f"Created venv at {venv_dir}")
            except subprocess.CalledProcessError as e:
                return f"Failed to create venv: {e}"

        # Split command to handle arguments
        cmd_parts = command.split()
        if not cmd_parts:
             return "Empty command provided."

        base_cmd = cmd_parts[0]
        args = cmd_parts[1:]

        # Map 'python' and 'pip' to venv executables
        if base_cmd == "python":
            final_cmd = [python_executable] + args
        elif base_cmd == "pip":
            final_cmd = [pip_executable] + args
        else:
            # For other commands (e.g., pytest), we typically run them via python -m or direct path if installed in venv bin
            # Best practice: use 'python -m pytest' if possible, or assume it's in bin
            if sys.platform == "win32":
                executable = os.path.join(venv_dir, "Scripts", base_cmd + ".exe")
            else:
                executable = os.path.join(venv_dir, "bin", base_cmd)

            if os.path.exists(executable):
                 final_cmd = [executable] + args
            else:
                 # Fallback: try running it, but usually this fails if not in PATH.
                 # We prefer strict venv usage.
                 return f"Command '{base_cmd}' not found in venv. Try using 'python -m {base_cmd}'."

        try:
            # Run command
            # We must be careful about cwd. Typically tests run from output/{job_id}
            cwd = os.path.join("output", self.job_id)

            result = subprocess.run(
                final_cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False
            )

            output = f"Stdout:\n{result.stdout}\nStderr:\n{result.stderr}"
            if result.returncode != 0:
                 return f"Command failed with return code {result.returncode}:\n{output}"
            return f"Command executed successfully:\n{output}"

        except Exception as e:
            return f"Error executing command: {e}"
