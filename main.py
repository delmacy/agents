import os
import sys
import time
import json
import uuid
from typing import List, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from src.crew import EmpresaSoftwareCrew
from src.state_manager import StateManager

# Load environment variables
load_dotenv()

app = FastAPI(title="Empresa de Agentes Factory Server")

class GenerateRequest(BaseModel):
    topic: str
    requirements: str

class GenerateResponse(BaseModel):
    job_id: str
    status: str

class TaskLog(BaseModel):
    task_name: str
    status: str
    version: int
    timestamp: str
    details: Optional[str] = None

class StatusResponse(BaseModel):
    job_id: str
    status: str
    tasks: List[TaskLog]

def executar_fluxo(inputs: dict, job_id: str):
    """
    Executes the crew with retry logic and validation loop in background.
    """
    state_manager = StateManager()
    output_dir = f"output/{job_id}"

    # Ensure output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    max_retries = 3
    version = 1

    state_manager.log_task(job_id, "Workflow", "STARTED", version, "Job started")

    while version <= max_retries:
        print(f"\n>>> [Job {job_id}] Starting Phase 1: Development & Validation (Version {version})")

        # Step 1: Run Coding & Validation
        try:
            # Instantiate crew with job_id context
            software_crew = EmpresaSoftwareCrew(job_id=job_id)
            initial_crew = software_crew.initial_crew()

            # Kickoff Phase 1
            result = initial_crew.kickoff(inputs=inputs)
            state_manager.log_task(job_id, "Phase 1 Crew", "COMPLETED", version, "Initial coding and validation run")

        except Exception as e:
            print(f"Error during Phase 1 execution: {e}")
            state_manager.log_task(job_id, "Phase 1 Crew", "FAILED", version, str(e))
            state_manager.log_task(job_id, "Workflow", "FAILED", version, f"Critical error: {str(e)}")
            return # Stop execution on critical error

        # Step 2: Check Validation Report
        report_path = os.path.join(output_dir, 'validation_report.json')
        missing = []
        is_valid = False
        feedback = ""

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
                    print(f"\n>>> [Job {job_id}] Validation Result: {'PASS' if is_valid else 'FAIL'}")
            except json.JSONDecodeError:
                print("Error reading validation report. Assuming failure.")
                is_valid = False
                feedback = "Validation report corrupted."

        # Step 3: Fork Logic
        if is_valid:
            print(f"\n>>> [Job {job_id}] Validation Passed. Proceeding to Phase 2: Infrastructure & QA")
            try:
                final_crew = software_crew.final_crew()
                # Run Phase 2
                final_result = final_crew.kickoff(inputs=inputs)
                state_manager.log_task(job_id, "Phase 2 Crew", "SUCCESS", version, "Infra and QA generated")
                state_manager.log_task(job_id, "Workflow", "SUCCESS", version, "Project Completed Successfully")
                return

            except Exception as e:
                 print(f"Error during Phase 2 execution: {e}")
                 state_manager.log_task(job_id, "Phase 2 Crew", "FAILED", version, str(e))
                 state_manager.log_task(job_id, "Workflow", "FAILED", version, f"Phase 2 error: {str(e)}")
                 return
        else:
            # Loop Back
            print(f"\n>>> [Job {job_id}] Validation Failed. Looping back for rework (Attempt {version}/{max_retries})")
            inputs['feedback'] = f"Previous attempt failed validation. Feedback: {feedback}. Missing: {missing}. Please fix these issues."
            version += 1
            state_manager.log_task(job_id, "Validation Gate", "RETRY_TRIGGERED", version, feedback)
            time.sleep(2)

    print(f"[Job {job_id}] Max retries reached. Validation failed.")
    state_manager.log_task(job_id, "Workflow", "FAILED", version, "Max retries reached")

@app.post("/generate", response_model=GenerateResponse)
async def generate_project(request: GenerateRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    inputs = {
        'topic': request.topic,
        'requirements': request.requirements
    }

    background_tasks.add_task(executar_fluxo, inputs, job_id)

    return GenerateResponse(job_id=job_id, status="started")

@app.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    state_manager = StateManager()
    logs = state_manager.get_job_status(job_id)

    if not logs:
        # If no logs found, check if directory exists (maybe just started and not logged yet?)
        if not os.path.exists(f"output/{job_id}"):
             raise HTTPException(status_code=404, detail="Job ID not found")
        current_status = "PENDING"
    else:
        # Determine overall status based on latest logs
        latest_log = logs[0]
        if latest_log['task_name'] == "Workflow":
             current_status = latest_log['status']
        else:
             current_status = "IN_PROGRESS"

    # Convert logs to Pydantic models (sqlite rows need dict access)
    # The get_job_status method already returns list of dicts if using sqlite3.Row or dict conversion in manager
    # Our implementation in state_manager.py converts to dicts.

    task_logs = []
    for log in logs:
        task_logs.append(TaskLog(
            task_name=log['task_name'],
            status=log['status'],
            version=log['version'],
            timestamp=str(log['timestamp']),
            details=str(log['details']) if log['details'] else None
        ))

    return StatusResponse(
        job_id=job_id,
        status=current_status,
        tasks=task_logs
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
