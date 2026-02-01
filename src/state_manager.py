import sqlite3
import os
from datetime import datetime
from threading import Lock

class StateManager:
    _instance = None
    _lock = Lock()
    DB_NAME = "crew_state.db"

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(StateManager, cls).__new__(cls)
                    cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        """Initialize the SQLite database and create the table if it doesn't exist."""
        conn = sqlite3.connect(self.DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                task_name TEXT NOT NULL,
                status TEXT NOT NULL,
                version INTEGER DEFAULT 1,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                details TEXT
            )
        ''')
        # Check if job_id column exists, if not add it (migration for existing DB)
        cursor.execute("PRAGMA table_info(task_log)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'job_id' not in columns:
            cursor.execute("ALTER TABLE task_log ADD COLUMN job_id TEXT DEFAULT 'legacy'")

        conn.commit()
        conn.close()

    def log_task(self, job_id: str, task_name: str, status: str, version: int = 1, details: str = ""):
        """Log a task status change to the database."""
        conn = sqlite3.connect(self.DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO task_log (job_id, task_name, status, version, timestamp, details)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (job_id, task_name, status, version, datetime.now(), details))
        conn.commit()
        conn.close()
        print(f"[StateManager] Job {job_id} - Task '{task_name}': {status} (v{version})")

    def get_job_status(self, job_id: str):
        """Get all logs for a specific job."""
        conn = sqlite3.connect(self.DB_NAME)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        cursor = conn.cursor()
        cursor.execute('''
            SELECT task_name, status, version, timestamp, details FROM task_log
            WHERE job_id = ?
            ORDER BY timestamp DESC
        ''', (job_id,))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
