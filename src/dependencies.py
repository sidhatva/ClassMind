"""
ClassMind AI - FastAPI Dependency Injection.
"""

from src.services.session_manager import SessionManager
from src.database import get_db_connection


def get_session_manager() -> SessionManager:
    return SessionManager.get_instance()


def get_database():
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()
