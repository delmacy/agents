import os
# --- FORÇA UTF-8 ---
os.environ["PYTHONUTF8"] = "1"

# --- CARREGA .ENV EXPLICITAMENTE ---
from dotenv import load_dotenv
load_dotenv() # Carrega variáveis do arquivo .env para o os.environ

# Validação Crítica
if not os.getenv("DEEPSEEK_API_KEY"):
    print("❌ ERRO CRÍTICO: DEEPSEEK_API_KEY não encontrada no arquivo .env")
    exit(1)

import sys
import uuid
import json
import logging
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, List

# Imports internos
from src.crew import EmpresaSoftwareCrew
from src.state_manager import StateManager

# --- DUAL LOGGER PARA TERMINAL ---
class DualLogger:
    def __init__(self, filepath):
        self.terminal = sys.stdout
        self.log = open(filepath, "a", encoding="utf-8")
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()
    def flush(self):
        self.terminal.flush()
        self.log.flush()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PlanRequest(BaseModel):
    initial_requirements: Optional[str] = None

class ChatRequest(BaseModel):
    message: str

class StatusResponse(BaseModel):
    job_id: str
    status: str
    tasks: List[Dict]

# --- WORKFLOW ENGINE ---
def execute_factory_assembly_line(job_id: str):
    """Executa a linha de montagem: Planejamento -> Loop (Código -> Teste -> Correção)"""
    state_manager = StateManager()
    output_dir = f"output/{job_id}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Redireciona Logs
    sys.stdout = DualLogger(os.path.join(output_dir, "execution.log"))

    try:
        # 1. PLANEJAMENTO (Arquitetura + Lógica + Work Orders)
        print(f"🚀 [Job {job_id}] STARTING PLANNING PHASE...")
        state_manager.log_task(job_id, "Planning Phase", "EXECUTING", 1, "Defining Logic & Sprints")
        
        planning_crew = EmpresaSoftwareCrew(job_id)
        # Assume que o discovery já ocorreu no chat. O kickoff agora roda arquitetura e sprint planning.
        # Inputs podem ser vazios pois ele lê o histórico
        planning_crew.planning_crew().kickoff()
        
        state_manager.log_task(job_id, "Planning Phase", "SUCCESS", 1, "Work Orders Created")

        # 2. CICLO DE CONSTRUÇÃO E QUALIDADE
        max_retries = 3
        attempt = 1
        feedback = "" # Começa vazio

        while attempt <= max_retries:
            print(f"\n🔄 [Job {job_id}] BUILD CYCLE {attempt}/{max_retries}")
            
            # A. CODIFICAÇÃO (Inputs: Work Orders + Feedback)
            state_manager.log_task(job_id, f"Build Cycle {attempt}", "CODING", attempt, "Translating Logic...")
            coding_inputs = {"feedback": feedback}
            
            coding_crew = EmpresaSoftwareCrew(job_id)
            coding_crew.coding_crew().kickoff(inputs=coding_inputs)
            
            # B. QUALIDADE (Testes)
            print(f"🧪 [Job {job_id}] RUNNING QA...")
            state_manager.log_task(job_id, f"Build Cycle {attempt}", "TESTING", attempt, "Running Pytest...")
            
            qa_crew = EmpresaSoftwareCrew(job_id)
            qa_result = qa_crew.qa_crew().kickoff()
            qa_output = str(qa_result)

            # C. DECISÃO
            if "FAILED" in qa_output or "Error" in qa_output or "FAILURES" in qa_output:
                print(f"❌ [Job {job_id}] TESTS FAILED.")
                feedback = f"Previous code failed tests. FIX THESE ERRORS:\n{qa_output[-2000:]}" # Pega os ultimos erros
                state_manager.log_task(job_id, f"Build Cycle {attempt}", "FAILED", attempt, "Tests failed. Retrying...")
                attempt += 1
            else:
                print(f"✅ [Job {job_id}] TESTS PASSED! SOFTWARE READY.")
                state_manager.log_task(job_id, "Workflow", "SUCCESS", attempt, "All tests passed.")
                return

        # Se saiu do while, falhou
        state_manager.log_task(job_id, "Workflow", "FAILED", attempt, "Max retries exceeded.")

    except Exception as e:
        print(f"💀 CRITICAL ERROR: {e}")
        state_manager.log_task(job_id, "Workflow", "CRASHED", 0, str(e))

# --- ENDPOINTS ---

@app.post("/plan/start")
async def start_plan(req: PlanRequest):
    job_id = str(uuid.uuid4())
    manager = StateManager()
    manager.create_job(job_id)
    
    # Inicia com Fase de Descoberta (apenas chat, sem background task pesada ainda)
    manager.log_task(job_id, "Phase 1 (Discovery)", "PLANNING", 1, "Waiting for user input")
    
    # Se usuário mandou requisito inicial, já processa
    if req.initial_requirements:
         # Aqui poderíamos invocar o PM agente de forma síncrona ou assíncrona
         pass
         
    return {"job_id": job_id, "status": "PLANNING"}

@app.post("/plan/chat/{job_id}")
async def chat_pm(job_id: str, req: ChatRequest):
    """Recebe mensagem do usuário, salva no histórico e roda um debate síncrono entre agentes do planning crew.
    As respostas dos agentes são salvas e retornadas para o frontend."""
    state_manager = StateManager()

    # Salva mensagem do usuário
    state_manager.add_chat_message(job_id, sender="user", role="user", message=req.message)

    # Constrói histórico legível para passar como contexto
    history_msgs = state_manager.get_chat_history(job_id)
    history = "\n".join([f"{m['sender']}: {m['message']}" for m in history_msgs])

    crew_instance = EmpresaSoftwareCrew(job_id)

    # Agentes que participam do debate (phase planning)
    agents = [
        ("product_manager", crew_instance.product_manager_agent()),
        ("architect", crew_instance.architect_agent()),
        ("technical_designer", crew_instance.technical_designer_agent()),
        ("scrum_master", crew_instance.scrum_master_agent()),
    ]

    from crewai import Task
    responses = []

    for role, agent in agents:
        task = Task(
            description=f"Participate in a short debate about the user's message.\nConversation history:\n{history}\nAs {role}, provide a concise contribution to the debate.",
            expected_output="Response string",
            agent=agent
        )
        try:
            resp = task.execute_sync()
            text = str(resp)
        except Exception as e:
            text = f"[ERROR generating response: {e}]"

        # Salva resposta do agente no histórico de chat
        state_manager.add_chat_message(job_id, sender=role, role="agent", message=text)
        responses.append({"role": role, "message": text})

        # Atualiza histórico para o próximo agente
        history += f"\n{role}: {text}"

    return {"messages": state_manager.get_chat_history(job_id), "latest": responses}


@app.get("/plan/chat/{job_id}")
async def get_chat(job_id: str):
    """Retorna o histórico de chat para o frontend exibir."""
    state_manager = StateManager()
    return {"messages": state_manager.get_chat_history(job_id)}

@app.post("/plan/approve/{job_id}")
async def approve_plan(job_id: str):
    # Dispara a Thread de Background
    import threading
    thread = threading.Thread(target=execute_factory_assembly_line, args=(job_id,))
    thread.start()
    return {"status": "Build Started"}

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    state_manager = StateManager()
    logs = state_manager.get_job_status(job_id)
    
    if not logs:
        return {"job_id": job_id, "status": "PLANNING", "tasks": []}
    
    # Lógica de Status
    status = "IN_PROGRESS"
    latest = logs[0]
    
    if latest['task_name'] == "Workflow":
        status = latest['status'] # SUCCESS / FAILED
    elif latest['task_name'] == "Planning Phase" and latest['status'] == "EXECUTING":
        status = "PLANNING"
        
    return {"job_id": job_id, "status": status, "tasks": logs}

@app.get("/project-structure/{job_id}")
async def get_project_structure(job_id: str):
    path = f"output/{job_id}/system_architecture.json"
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {"modules": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)