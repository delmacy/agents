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
                task_name TEXT NOT NULL,
                status TEXT NOT NULL,
                version INTEGER DEFAULT 1,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                details TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def log_task(self, task_name: str, status: str, version: int = 1, details: str = ""):
        """Log a task status change to the database."""
        conn = sqlite3.connect(self.DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO task_log (task_name, status, version, timestamp, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (task_name, status, version, datetime.now(), details))
        conn.commit()
        conn.close()
        print(f"[StateManager] Logged task '{task_name}': {status} (v{version})")

    def get_latest_status(self, task_name: str):
        """Get the latest log entry for a specific task."""
        conn = sqlite3.connect(self.DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT status, version, details FROM task_log
            WHERE task_name = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (task_name,))
        row = cursor.fetchone()
        conn.close()
        return row if row else None
