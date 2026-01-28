import sqlite3
from adorable_cli.db.migrations import MigrationManager

def test_migration_init(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    manager = MigrationManager(db_path=db_path)
    
    # Initial state: no file
    assert not db_path.exists()
    
    # Check version (creates table)
    version = manager.get_version()
    assert version == 0
    assert db_path.exists()
    
    # Migrate
    manager.migrate()
    assert manager.get_version() == 1
    
    # Check table content
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM _adorable_meta WHERE key='version'")
    assert cursor.fetchone()[0] == '1'
    conn.close()
