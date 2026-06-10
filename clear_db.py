import sqlite3
import os
import sys

# Add package-b-vision path
sys.path.append(os.path.abspath("package-b-vision"))
from ultralytics import YOLO

DB_FILE = "fridge.db"

def main():
    print("--- MODEL CLASSES ---")
    try:
        model = YOLO("package-b-vision/models/best.pt")
        print("Model classes:", model.names)
    except Exception as e:
        print("Failed to load model classes:", e)

    print("\n--- DATABASE BEFORE CLEARING ---")
    if not os.path.exists(DB_FILE):
        print("Database file does not exist.")
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    tables = ["inventory", "inventory_logs", "shopping_list", "detections"]
    for t in tables:
        try:
            c.execute(f"SELECT COUNT(*) FROM {t}")
            count = c.fetchone()[0]
            print(f"Table '{t}': {count} rows")
            c.execute(f"SELECT * FROM {t} LIMIT 5")
            rows = c.fetchall()
            if rows:
                print(f"Sample from '{t}':")
                for r in rows:
                    print("  ", r)
        except Exception as e:
            print(f"Failed to query table '{t}':", e)

    print("\n--- CLEARING TABLES ---")
    for t in tables:
        try:
            c.execute(f"DELETE FROM {t}")
            print(f"Table '{t}' cleared.")
        except Exception as e:
            print(f"Failed to clear table '{t}':", e)

    conn.commit()
    conn.close()
    print("Database tables cleared successfully!")

if __name__ == "__main__":
    main()
