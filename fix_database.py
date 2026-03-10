#!/usr/bin/env python
"""
Quick database fix script
"""
import sqlite3
import os

def add_missing_column():
    db_path = os.path.join('data', 'app.db')
    if not os.path.exists(db_path):
        print("Database not found")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(individuals)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'internal_predictions' not in columns:
            print("Adding internal_predictions column...")
            cursor.execute("ALTER TABLE individuals ADD COLUMN internal_predictions JSON")
            conn.commit()
            print("Column added successfully")
        else:
            print("Column already exists")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_missing_column()
