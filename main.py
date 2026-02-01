import os
import sys
import time
import json
import uuid
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from src.crew import EmpresaSoftwareCrew
from src.state_manager import StateManager

# Load environment variables
load_dotenv()

app = FastAPI(title="Empresa de Agentes Factory Server (Full-Chain)")

# --- Models ---
class PlanStartRequest(BaseModel):
    initial_requirements: Optional[str] = None

class PlanStartResponse(BaseModel):
    job_id: str
    status: str
    message: str

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    history: List[Dict[str, str]]

class ApproveRequest(BaseModel):
    feedback: Optional[str] = None

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

# --- Workflow Logic ---

def execute_multistage_build(job_id: str):
    """
    Executes Phase 2 to 5 (Leadership -> Build -> Sandbox -> QA -> Audit)
    """
    state_manager = StateManager()
    output_dir = f"output/{job_id}"

    # Ensure output directory exists (should exist from Discovery, but safety check)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    max_retries = 3
    version = 1
    feedback = ""

    state_manager.log_task(job_id, "Workflow", "STARTED_BUILD", version, "Build phases started")

    while version <= max_retries:
        print(f"\n>>> [Job {job_id}] Starting Build Cycle (Version {version})")

        software_crew = EmpresaSoftwareCrew(job_id=job_id)

        # Phase 2: Design (Leadership)
        try:
            print(f">>> [Job {job_id}] Phase 2: Leadership/Design")
            leadership_crew = software_crew.leadership_crew()
            # Input is the final_plan.json. CrewAI needs inputs dict.
            leadership_crew.kickoff(inputs={'stage': 'design', 'job_id': job_id})
            state_manager.log_task(job_id, "Phase 2 (Design)", "COMPLETED", version, "Blueprint generated")
        except Exception as e:
            print(f"Error Phase 2: {e}")
            state_manager.log_task(job_id, "Phase 2 (Design)", "FAILED", version, str(e))
            state_manager.log_task(job_id, "Workflow", "FAILED", version, "Phase 2 failed")
            return

        # Phase 3: Build & Validation (Development)
        try:
            print(f">>> [Job {job_id}] Phase 3: Development (Feedback: {feedback})")
            development_crew = software_crew.development_crew()
            development_crew.kickoff(inputs={
                'stage': 'development',
                'job_id': job_id,
                'feedback': feedback if version > 1 else 'None'
            })
            state_manager.log_task(job_id, "Phase 3 (Build)", "COMPLETED", version, "Code implemented")
        except Exception as e:
            print(f"Error Phase 3: {e}")
            state_manager.log_task(job_id, "Phase 3 (Build)", "FAILED", version, str(e))
            state_manager.log_task(job_id, "Workflow", "FAILED", version, "Phase 3 failed")
            return

        # Check Validation Report
        report_path = os.path.join(output_dir, 'validation_report.json')
        is_valid = False
        current_feedback = ""
        missing = []

        if os.path.exists(report_path):
            try:
                with open(report_path, 'r') as f:
                    report = json.load(f)
                    is_valid = report.get('is_valid', False)
                    current_feedback = report.get('feedback', '')
                    missing = report.get('missing_features', [])
            except:
                current_feedback = "Corrupted validation report"
        else:
            current_feedback = "Missing validation report"

        if not is_valid:
            print(f">>> [Job {job_id}] Validation Failed. Looping.")
            feedback = f"Previous attempt failed. Feedback: {current_feedback}. Missing: {missing}."
            state_manager.log_task(job_id, "Validation Gate", "RETRY_TRIGGERED", version, feedback)
            version += 1
            continue # Retry loop

        # Phase 4: Sandbox & QA (Execution)
        print(f">>> [Job {job_id}] Phase 4: Sandbox & QA")
        try:
            execution_crew = software_crew.execution_crew()
            execution_crew.kickoff(inputs={'stage': 'execution', 'job_id': job_id})
            state_manager.log_task(job_id, "Phase 4 (QA)", "COMPLETED", version, "Sandbox tests ran")
        except Exception as e:
             print(f"Error Phase 4: {e}")
             state_manager.log_task(job_id, "Phase 4 (QA)", "FAILED", version, str(e))
             state_manager.log_task(job_id, "Workflow", "FAILED", version, "Phase 4 failed")
             return

        # Phase 5: Technical Audit (Tech Lead)
        print(f">>> [Job {job_id}] Phase 5: Audit")
        try:
            audit_crew = software_crew.audit_crew()
            audit_crew.kickoff(inputs={'stage': 'audit', 'job_id': job_id})

            # Check Audit Report
            audit_path = os.path.join(output_dir, 'audit_report.json')
            audit_status = "UNKNOWN"
            audit_blockers = []
            if os.path.exists(audit_path):
                 try:
                     with open(audit_path, 'r') as f:
                         audit_report = json.load(f)
                         audit_status = audit_report.get('status', 'REJECTED')
                         audit_blockers = audit_report.get('blockers', [])
                         audit_rec = audit_report.get('recommendation', '')
                 except:
                     audit_status = "CORRUPTED"

            if audit_status != "APPROVED":
                 print(f">>> [Job {job_id}] Audit Failed. Looping.")
                 feedback = f"Audit Failed. Blockers: {audit_blockers}. Recommendation: {audit_rec}"
                 state_manager.log_task(job_id, "Audit Gate", "RETRY_TRIGGERED", version, feedback)
                 version += 1
                 continue # Loop back to rebuild

            state_manager.log_task(job_id, "Phase 5 (Audit)", "APPROVED", version, "Ready for delivery")

        except Exception as e:
             print(f"Error Phase 5: {e}")
             state_manager.log_task(job_id, "Phase 5 (Audit)", "FAILED", version, str(e))
             state_manager.log_task(job_id, "Workflow", "FAILED", version, "Phase 5 failed")
             return

        # Final Success
        print(f">>> [Job {job_id}] Workflow Complete")
        state_manager.log_task(job_id, "Workflow", "SUCCESS", version, "Delivery Ready")
        return

    state_manager.log_task(job_id, "Workflow", "FAILED", version, "Max retries reached")


# --- Endpoints ---

@app.post("/plan/start", response_model=PlanStartResponse)
async def start_planning(request: PlanStartRequest):
    job_id = str(uuid.uuid4())
    output_dir = f"output/{job_id}"
    os.makedirs(output_dir, exist_ok=True)

    state_manager = StateManager()
    state_manager.log_task(job_id, "Phase 1 (Discovery)", "STARTED", 1, "Planning session initialized")

    # If initial requirements provided, save them (maybe as a pseudo-chat or just file)
    if request.initial_requirements:
        with open(f"{output_dir}/initial_requirements.txt", "w") as f:
            f.write(request.initial_requirements)
        state_manager.save_chat_message(job_id, "user", request.initial_requirements)

    return PlanStartResponse(job_id=job_id, status="planning", message="Job started. Use /plan/chat/{job_id} to refine requirements.")

@app.post("/plan/chat/{job_id}", response_model=ChatResponse)
async def chat_planning(job_id: str, request: ChatRequest):
    output_dir = f"output/{job_id}"
    if not os.path.exists(output_dir):
        raise HTTPException(status_code=404, detail="Job ID not found")

    state_manager = StateManager()
    state_manager.save_chat_message(job_id, "user", request.message)

    # Invoke Product Manager Agent
    software_crew = EmpresaSoftwareCrew(job_id=job_id)
    history = state_manager.get_chat_history(job_id)
    history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])

    inputs = {
        "conversation_history": history_str,
        "current_message": request.message
    }

    try:
        discovery_crew = software_crew.discovery_crew()
        result = discovery_crew.kickoff(inputs=inputs)
        response_text = str(result)
        state_manager.save_chat_message(job_id, "assistant", response_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    updated_history = state_manager.get_chat_history(job_id)
    history_list = [{"role": row['role'], "content": row['content']} for row in updated_history]

    return ChatResponse(response=response_text, history=history_list)

@app.post("/plan/approve/{job_id}")
async def approve_plan(job_id: str, request: ApproveRequest, background_tasks: BackgroundTasks):
    output_dir = f"output/{job_id}"
    if not os.path.exists(output_dir):
        raise HTTPException(status_code=404, detail="Job ID not found")

    state_manager = StateManager()

    # If fast path requirements provided in feedback
    if request.feedback:
        # Treat as final requirements
        with open(f"{output_dir}/final_plan.json", "w") as f:
            json.dump({"requirements": request.feedback, "approved": True}, f)
        state_manager.save_chat_message(job_id, "user", f"APPROVED with feedback: {request.feedback}")
    else:
        state_manager.save_chat_message(job_id, "user", "APPROVED")

    # Trigger Background Execution
    background_tasks.add_task(execute_multistage_build, job_id)

    return {"status": "build_started", "message": "Plan approved. Build pipeline initiated."}

@app.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    state_manager = StateManager()
    logs = state_manager.get_job_status(job_id)

    if not logs:
        if not os.path.exists(f"output/{job_id}"):
             raise HTTPException(status_code=404, detail="Job ID not found")
        current_status = "PLANNING"
    else:
        latest_log = logs[0]
        if latest_log['task_name'] == "Workflow":
             current_status = latest_log['status']
        else:
             current_status = "IN_PROGRESS"

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
