"""
Database migration system for RANSHI_KUN
"""
import os
import json
from datetime import datetime
from flask import current_app
from app.extensions import db
from app.models import User, Individual, HistoryEntry, ProvisionalPeriod, ModelMeta

class Migration:
    """Base migration class"""
    def __init__(self, version, description):
        self.version = version
        self.description = description
        self.applied_at = None
    
    def up(self):
        """Apply migration"""
        raise NotImplementedError
    
    def down(self):
        """Rollback migration"""
        raise NotImplementedError

class Migration001_AddInternalPredictions(Migration):
    """Add internal_predictions column to Individual model"""
    def __init__(self):
        super().__init__(1, "Add internal_predictions column to Individual model")
    
    def up(self):
        """Add internal_predictions column"""
        try:
            # SQLiteの場合
            if 'sqlite' in current_app.config['SQLALCHEMY_DATABASE_URI']:
                db.engine.execute('ALTER TABLE individuals ADD COLUMN internal_predictions TEXT')
            # PostgreSQLの場合
            else:
                db.engine.execute('ALTER TABLE individuals ADD COLUMN internal_predictions JSON')
            db.session.commit()
            print(f"Migration {self.version}: {self.description} - Applied")
        except Exception as e:
            print(f"Migration {self.version} failed: {e}")
            db.session.rollback()
    
    def down(self):
        """Remove internal_predictions column"""
        try:
            if 'sqlite' in current_app.config['SQLALCHEMY_DATABASE_URI']:
                # SQLite doesn't support DROP COLUMN easily, so recreate table
                pass
            else:
                db.engine.execute('ALTER TABLE individuals DROP COLUMN internal_predictions')
            db.session.commit()
            print(f"Migration {self.version}: Rolled back")
        except Exception as e:
            print(f"Rollback failed: {e}")
            db.session.rollback()

class Migration002_AddUserIsActive(Migration):
    """Add is_active column to User model"""
    def __init__(self):
        super().__init__(2, "Add is_active column to User model")
    
    def up(self):
        """Add is_active column"""
        try:
            if 'sqlite' in current_app.config['SQLALCHEMY_DATABASE_URI']:
                db.engine.execute('ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1')
            else:
                db.engine.execute('ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE')
            db.session.commit()
            print(f"Migration {self.version}: {self.description} - Applied")
        except Exception as e:
            print(f"Migration {self.version} failed: {e}")
            db.session.rollback()
    
    def down(self):
        """Remove is_active column"""
        try:
            if 'sqlite' in current_app.config['SQLALCHEMY_DATABASE_URI']:
                pass  # SQLite limitation
            else:
                db.engine.execute('ALTER TABLE users DROP COLUMN is_active')
            db.session.commit()
            print(f"Migration {self.version}: Rolled back")
        except Exception as e:
            print(f"Rollback failed: {e}")
            db.session.rollback()

# Migration registry
MIGRATIONS = [
    Migration001_AddInternalPredictions(),
    Migration002_AddUserIsActive(),
]

class MigrationManager:
    """Migration management system"""
    
    def __init__(self):
        self.migrations_table = 'schema_migrations'
        self._ensure_migrations_table()
    
    def _ensure_migrations_table(self):
        """Create migrations tracking table if it doesn't exist"""
        try:
            db.engine.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.migrations_table} (
                    version INTEGER PRIMARY KEY,
                    description TEXT,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            db.session.commit()
        except Exception as e:
            print(f"Failed to create migrations table: {e}")
    
    def get_applied_migrations(self):
        """Get list of applied migration versions"""
        try:
            result = db.engine.execute(f'SELECT version FROM {self.migrations_table} ORDER BY version')
            return [row[0] for row in result]
        except Exception as e:
            print(f"Failed to get applied migrations: {e}")
            return []
    
    def apply_migration(self, migration):
        """Apply a single migration"""
        try:
            migration.up()
            # Record migration
            db.engine.execute(f'''
                INSERT INTO {self.migrations_table} (version, description, applied_at)
                VALUES (?, ?, ?)
            ''', (migration.version, migration.description, datetime.utcnow()))
            db.session.commit()
            return True
        except Exception as e:
            print(f"Failed to apply migration {migration.version}: {e}")
            db.session.rollback()
            return False
    
    def migrate(self):
        """Run all pending migrations"""
        applied = self.get_applied_migrations()
        pending = [m for m in MIGRATIONS if m.version not in applied]
        
        if not pending:
            print("No pending migrations")
            return
        
        print(f"Found {len(pending)} pending migrations")
        
        for migration in pending:
            if self.apply_migration(migration):
                print(f"[OK] Migration {migration.version} applied successfully")
            else:
                print(f"[FAIL] Migration {migration.version} failed")
                break
    
    def rollback(self, target_version):
        """Rollback to specific version"""
        applied = self.get_applied_migrations()
        to_rollback = [m for m in MIGRATIONS if m.version in applied and m.version > target_version]
        
        if not to_rollback:
            print(f"No migrations to rollback to version {target_version}")
            return
        
        for migration in reversed(to_rollback):
            try:
                migration.down()
                # Remove migration record
                db.engine.execute(f'DELETE FROM {self.migrations_table} WHERE version = ?', (migration.version,))
                db.session.commit()
                print(f"[OK] Migration {migration.version} rolled back")
            except Exception as e:
                print(f"[FAIL] Failed to rollback migration {migration.version}: {e}")
                break

# Global migration manager instance
migration_manager = MigrationManager()

def migrate():
    """Run database migrations"""
    with current_app.app_context():
        migration_manager.migrate()

def rollback(target_version):
    """Rollback database migrations"""
    with current_app.app_context():
        migration_manager.rollback(target_version)
