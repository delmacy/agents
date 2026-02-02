import sqlite3
import threading
from datetime import datetime
from typing import List, Dict, Any

DB_FILE = "crew_state.db"
db_lock = threading.Lock()

class StateManager:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        """Inicializa o banco de dados SQLite com suporte a locks para evitar erros de concorrência."""
        with db_lock:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            # Tabela de Logs de Tarefas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS task_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    task_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    version INTEGER DEFAULT 1,
                    timestamp TEXT NOT NULL,
                    details TEXT
                )
            ''')
            conn.commit()
            conn.close()

    def create_job(self, job_id: str):
        """
        Cria um registro inicial para o Job.
        Isso resolve o erro 'AttributeError: create_job'.
        """
        self.log_task(
            job_id=job_id,
            task_name="System",
            status="CREATED",
            version=0,
            details="Job initialized in State Manager"
        )

    def log_task(self, job_id: str, task_name: str, status: str, version: int = 1, details: str = None):
        """Registra um passo da execução no banco de dados."""
        with db_lock:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute('''
                INSERT INTO task_logs (job_id, task_name, status, version, timestamp, details)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (job_id, task_name, status, version, timestamp, details))
            
            conn.commit()
            conn.close()

    def get_job_status(self, job_id: str) -> List[Dict[str, Any]]:
        """Recupera todos os logs de um job específico, ordenados do mais recente para o mais antigo."""
        with db_lock:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row # Para retornar dicionários
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM task_logs 
                WHERE job_id = ? 
                ORDER BY id DESC
            ''', (job_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Converte sqlite3.Row para dict padrão
            return [dict(row) for row in rows]