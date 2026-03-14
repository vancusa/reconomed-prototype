from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from decouple import config
import os

# Database URL - will use local PostgreSQL for now, easy to switch later
DATABASE_URL = config('DATABASE_URL', default='sqlite:///./reconomed.db')

# Create engine - sqlite for development, postgresql for production
if DATABASE_URL.startswith('sqlite'):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create tables
def create_tables():
    Base.metadata.create_all(bind=engine)
    _migrate_consultation_columns()

def _migrate_consultation_columns():
    """Add new columns to consultations table if they don't exist (SQLite migration)."""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)

    if 'consultations' not in inspector.get_table_names():
        return

    existing_cols = {col['name'] for col in inspector.get_columns('consultations')}
    new_columns = {
        'pinned_files': "ALTER TABLE consultations ADD COLUMN pinned_files JSON DEFAULT '[]'",
        'discharge_text': "ALTER TABLE consultations ADD COLUMN discharge_text TEXT",
        'amended_at': "ALTER TABLE consultations ADD COLUMN amended_at DATETIME",
        'amendment_history': "ALTER TABLE consultations ADD COLUMN amendment_history JSON DEFAULT '[]'",
    }

    with engine.begin() as conn:
        for col_name, ddl in new_columns.items():
            if col_name not in existing_cols:
                conn.execute(text(ddl))

        # Migrate old status values
        conn.execute(text("UPDATE consultations SET status='scheduled' WHERE status='draft'"))
        conn.execute(text("UPDATE consultations SET status='completed' WHERE status='discharged'"))