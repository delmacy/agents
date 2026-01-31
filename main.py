import os
import sys
import time
import json
from dotenv import load_dotenv
from src.crew import EmpresaSoftwareCrew
from src.state_manager import StateManager

# Load environment variables
load_dotenv()

def executar_fluxo(inputs):
    """
    Executes the crew with retry logic and validation loop.
    """
    state_manager = StateManager()
    max_retries = 3
    version = 1

    # Ensure output directory exists
    if not os.path.exists('output'):
        os.makedirs('output')

    while version <= max_retries:
        print(f"\n>>> Starting Phase 1: Development & Validation (Version {version})")

        # Step 1: Run Coding & Validation
        try:
            software_crew = EmpresaSoftwareCrew()
            initial_crew = software_crew.initial_crew()

            # Kickoff Phase 1
            result = initial_crew.kickoff(inputs=inputs)
            state_manager.log_task("Phase 1 Crew", "COMPLETED", version, "Initial coding and validation run")

        except Exception as e:
            print(f"Error during Phase 1 execution: {e}")
            state_manager.log_task("Phase 1 Crew", "FAILED", version, str(e))
            raise e

        # Step 2: Check Validation Report
        report_path = os.path.join('output', 'validation_report.json')
        missing = []
        if not os.path.exists(report_path):
            print("Validation report not found. Assuming failure.")
            is_valid = False
            feedback = "Validation report missing."
        else:
            try:
                with open(report_path, 'r') as f:
                    report = json.load(f)
                    is_valid = report.get('is_valid', False)
                    feedback = report.get('feedback', '')
                    missing = report.get('missing_features', [])
                    print(f"\n>>> Validation Result: {'PASS' if is_valid else 'FAIL'}")
                    print(f"Feedback: {feedback}")
                    if missing:
                        print(f"Missing Features: {missing}")
            except json.JSONDecodeError:
                print("Error reading validation report. Assuming failure.")
                is_valid = False
                feedback = "Validation report corrupted."

        # Step 3: Fork Logic
        if is_valid:
            print("\n>>> Validation Passed. Proceeding to Phase 2: Infrastructure & QA")
            try:
                final_crew = software_crew.final_crew()
                # Run Phase 2
                # We can reuse the inputs. The context from previous tasks (coding_task)
                # might be lost if we don't pass the previous output,
                # but CrewAI sequential processes usually share context if in same crew.
                # Since we split crews, we rely on the agents reading the files from output/
                # or we pass the previous result as input context if needed.
                # The tasks.yaml defines context=[coding_task], which works within a single crew.
                # Splitting crews breaks this automatic context context passing *in memory*.
                # However, the DevOps and QA agents are instructed to "Analyze the code generated...".
                # Since they have FileReadTool (or implicit file access via prompts), they should be fine reading 'output/'.
                # Let's ensure they have the right tools. DevOps agent has FileWriteTool, but maybe needs Read access?
                # The prompt said "DevOps agent must mandatory read the code...".
                # In `src/crew.py`, devops_agent only has `FileWriterTool`.
                # We should probably add `FileReadTool` or `DirectoryReadTool` to DevOps/QA agents
                # or rely on them "knowing" what to do or reading the result string passed as input?
                # Actually, standard CrewAI 'context' parameter passes the *string output* of the previous task.
                # Since we broke the chain, we might want to manually pass the code content or file paths.
                # But let's try running it. If they need to read files, they need the tool.
                # I will add DirectoryReadTool to DevOps and QA agents in a fix step if needed,
                # but for now, let's assume they might hallucinate or infer from prompt if they don't have read access.
                # WAIT. The prompt explicitly said: "Context: The DevOps agent must mandatory read the code...".
                # And I only gave `FileWriterTool`. I should fix this in `src/crew.py` before running.

                final_result = final_crew.kickoff(inputs=inputs)
                state_manager.log_task("Phase 2 Crew", "SUCCESS", version, "Infra and QA generated")

                print("\n################################################")
                print("## Project Completed Successfully")
                print("################################################\n")
                return final_result

            except Exception as e:
                 print(f"Error during Phase 2 execution: {e}")
                 state_manager.log_task("Phase 2 Crew", "FAILED", version, str(e))
                 raise e
        else:
            # Loop Back
            print(f"\n>>> Validation Failed. Looping back for rework (Attempt {version}/{max_retries})")
            inputs['feedback'] = f"Previous attempt failed validation. Feedback: {feedback}. Missing: {missing}. Please fix these issues."
            version += 1
            state_manager.log_task("Validation Gate", "RETRY_TRIGGERED", version, feedback)
            time.sleep(2)

    print("Max retries reached. Validation failed.")
    sys.exit(1)

def main():
    print("Welcome to EmpresaSoftwareCrew - Phase 2")

    # Define inputs
    inputs = {
        'topic': 'Controle de Aportes Financeiros',
        'requirements': (
            "Create a simple FastAPI microservice to manage financial contributions (aportes). "
            "It should allow registering a contribution with amount, user_id, and date. "
            "It should also allow retrieving contributions by user_id. "
            "Use SQLite for persistence. "
            "Ensure the code is modular, uses Pydantic for validation, and follows best practices."
        )
    }

    try:
        executar_fluxo(inputs)
    except Exception as e:
        sys.exit(1)

if __name__ == "__main__":
    main()
