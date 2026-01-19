import sqlite3
from pathlib import Path
from adorable_cli.settings import settings

class MigrationManager:
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or settings.mem_db_path

    def _get_connection(self):
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.db_path)

    def init_meta_table(self, conn):
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _adorable_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()

    def get_version(self) -> int:
        conn = self._get_connection()
        try:
            self.init_meta_table(conn)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM _adorable_meta WHERE key='version'")
            row = cursor.fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()

    def set_version(self, version: int):
        conn = self._get_connection()
        try:
            self.init_meta_table(conn)
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO _adorable_meta (key, value) VALUES ('version', ?)", (str(version),))
            conn.commit()
        finally:
            conn.close()

    def migrate(self):
        """Run migrations."""
        current_version = self.get_version()
        print(f"Current DB version: {current_version}")
        
        # Example migration logic
        # if current_version < 1:
        #     apply_v1()
        #     self.set_version(1)
        
        # For now, just setting version to 1 as initial state if 0
        if current_version < 1:
            print("Migrating to version 1...")
            # No actual schema changes needed for now as we rely on Agno
            self.set_version(1)
            print("Migration complete.")
        else:
            print("Database is up to date.")

def run_migrations():
    manager = MigrationManager()
    manager.migrate()
