#!/usr/bin/env python3
"""
Script to add 'SKIPPED' value to assessmentstatus enum type.

Run this script to fix the enum issue:
    python scripts/add_skipped_enum.py

Or run the SQL directly in your database:
    ALTER TYPE assessmentstatus ADD VALUE 'SKIPPED';
"""

import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.core.config import settings

def add_skipped_enum():
    """Add 'SKIPPED' value to assessmentstatus enum."""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # Check if enum type exists
        result = conn.execute(text("""
            SELECT 1 FROM pg_type WHERE typname = 'assessmentstatus'
        """))
        
        if not result.fetchone():
            print("Error: assessmentstatus enum type not found in database.")
            return False
        
        # Check if 'SKIPPED' already exists
        result = conn.execute(text("""
            SELECT 1 FROM pg_enum 
            WHERE enumlabel = 'SKIPPED' 
            AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'assessmentstatus')
        """))
        
        if result.fetchone():
            print("'SKIPPED' value already exists in assessmentstatus enum.")
            return True
        
        # Check existing values to determine case
        result = conn.execute(text("""
            SELECT enumlabel FROM pg_enum 
            WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'assessmentstatus')
            ORDER BY enumsortorder
            LIMIT 3
        """))
        
        existing_values = [row[0] for row in result]
        uses_uppercase = any(v.isupper() for v in existing_values) if existing_values else True
        
        value_to_add = 'SKIPPED' if uses_uppercase else 'skipped'
        
        print(f"Adding '{value_to_add}' to assessmentstatus enum...")
        
        try:
            # ALTER TYPE ADD VALUE cannot be run inside a transaction
            # We need to commit first
            conn.commit()
            
            # Now add the value
            conn.execute(text(f"ALTER TYPE assessmentstatus ADD VALUE '{value_to_add}'"))
            conn.commit()
            
            print(f"Successfully added '{value_to_add}' to assessmentstatus enum!")
            return True
        except Exception as e:
            print(f"Error adding enum value: {e}")
            print(f"\nPlease run this SQL command manually in your database:")
            print(f"ALTER TYPE assessmentstatus ADD VALUE '{value_to_add}';")
            return False

if __name__ == "__main__":
    success = add_skipped_enum()
    sys.exit(0 if success else 1)
