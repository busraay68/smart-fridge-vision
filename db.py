import sqlite3
from datetime import datetime
import pandas as pd
import os

DB_FILE = "fridge.db"

# --- CONNECTION ---
def get_connection():
    os.makedirs(os.path.dirname(DB_FILE) or ".", exist_ok=True)
    return sqlite3.connect(DB_FILE, check_same_thread=False)

# --- TIME ---
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# --- TABLES ---
def create_tables():
    conn = get_connection()
    c = conn.cursor()

    # --- Inventory tablosu ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        class_name TEXT PRIMARY KEY,
        quantity INTEGER DEFAULT 0,
        expiry_date TEXT,
        image_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # --- Shopping List tablosu ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS shopping_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_name TEXT UNIQUE,
        quantity INTEGER DEFAULT 1,
        is_added INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # --- Inventory Logs tablosu ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS inventory_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_name TEXT,
        action TEXT,
        change_amount INTEGER DEFAULT 0,
        quantity_before INTEGER DEFAULT 0,
        quantity_after INTEGER DEFAULT 0,
        source TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # --- Detections tablosu ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_name TEXT,
        class_name TEXT,
        confidence REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # --- System Logs tablosu ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS system_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        log_type TEXT,
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # --- AI Confirmations tablosu ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS ai_confirmations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_name TEXT,
        ai_name TEXT,
        quantity_delta INTEGER,
        image_path TEXT,
        source_label TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # --- Contacts tablosu ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

# --- INVENTORY HELPERS ---
def ensure_item(class_name, expiry_date=None, image_path=None):
    if not expiry_date or expiry_date.strip() == "":
        import datetime
        expiry_date = (datetime.date.today() + datetime.timedelta(days=5)).strftime("%Y-%m-%d")
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    INSERT OR IGNORE INTO inventory (class_name, quantity, expiry_date, image_path, created_at, updated_at)
    VALUES (?, 0, ?, ?, ?, ?)
    """, (class_name, expiry_date, image_path, now(), now()))
    conn.commit()
    conn.close()

def get_quantity(class_name):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT quantity FROM inventory WHERE class_name = ?", (class_name,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def update_inventory(class_name, change_amount, expiry_date=None, image_path=None, source="manual"):
    if expiry_date and expiry_date.strip() == "":
        expiry_date = None
        
    ensure_item(class_name, expiry_date, image_path)
    old_qty = get_quantity(class_name)
    new_qty = max(0, old_qty + change_amount)
    action = "ADD" if change_amount > 0 else "REMOVE"

    conn = get_connection()
    c = conn.cursor()

    # inventory güncelle
    if change_amount > 0:
        if not expiry_date:
            import datetime
            expiry_date = (datetime.date.today() + datetime.timedelta(days=5)).strftime("%Y-%m-%d")
        
        sql = "UPDATE inventory SET quantity = ?, updated_at = ?, expiry_date = ?, created_at = ?"
        params = [new_qty, now(), expiry_date, now()]
        
        if image_path:
            sql += ", image_path = ?"
            params.append(image_path)
            
        sql += " WHERE class_name = ?"
        params.append(class_name)
    else:
        sql = "UPDATE inventory SET quantity = ?, updated_at = ?"
        params = [new_qty, now()]
        if expiry_date:
            sql += ", expiry_date = ?"
            params.append(expiry_date)
        if image_path:
            sql += ", image_path = ?"
            params.append(image_path)
            
        sql += " WHERE class_name = ?"
        params.append(class_name)
        
    c.execute(sql, tuple(params))

    # log ekle
    c.execute("""
    INSERT INTO inventory_logs
    (class_name, action, change_amount, quantity_before, quantity_after, source, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (class_name, action, change_amount, old_qty, new_qty, source, now()))

    conn.commit()
    conn.close()

# --- SHOPPING LIST HELPERS ---
def get_shopping_list():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM shopping_list", conn)
    conn.close()
    return df

def add_to_shopping_list(class_name, quantity=1):
    conn = get_connection()
    c = conn.cursor()
    # Eğer ürün zaten listede varsa miktarını artır, yoksa yeni ekle
    c.execute("SELECT id, quantity FROM shopping_list WHERE class_name = ?", (class_name,))
    row = c.fetchone()
    if row:
        new_qty = row[1] + quantity
        c.execute("UPDATE shopping_list SET quantity = ? WHERE id = ?", (new_qty, row[0]))
    else:
        c.execute("""
        INSERT INTO shopping_list (class_name, quantity, is_added, created_at)
        VALUES (?, ?, 0, ?)
        """, (class_name, quantity, now()))
    conn.commit()
    conn.close()

def remove_from_shopping_list(id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM shopping_list WHERE id = ?", (id,))
    conn.commit()
    conn.close()

# --- DETECTION ---
def insert_detection(image_name, class_name, confidence):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    INSERT INTO detections (image_name, class_name, confidence, created_at)
    VALUES (?, ?, ?, ?)
    """, (image_name, class_name, confidence, now()))
    conn.commit()
    conn.close()

# --- GETTERS ---
def get_inventory():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM inventory", conn)
    conn.close()
    return df

def get_logs(limit=50):
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM inventory_logs ORDER BY id DESC LIMIT ?",
        conn,
        params=(limit,)
    )
    conn.close()
    return df

def clear_all_data():
    """Tüm veritabanı tablolarını temizler."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM inventory")
    c.execute("DELETE FROM inventory_logs")
    c.execute("DELETE FROM detections")
    c.execute("DELETE FROM shopping_list")
    c.execute("DELETE FROM system_logs")
    conn.commit()
    conn.close()

def log_system_event(log_type, message):
    """Sistem olaylarını/hatalarını kaydeder."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    INSERT INTO system_logs (log_type, message, created_at)
    VALUES (?, ?, ?)
    """, (log_type, message, now()))
    conn.commit()
    conn.close()

def get_system_logs(limit=50):
    """En son sistem olay günlüklerini döndürür."""
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM system_logs ORDER BY id DESC LIMIT ?",
        conn,
        params=(limit,)
    )
    conn.close()
    return df

# --- AI CONFIRMATION HELPERS ---
def create_ai_confirmation(original_name, ai_name, quantity_delta, image_path, source_label):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    INSERT INTO ai_confirmations (original_name, ai_name, quantity_delta, image_path, source_label)
    VALUES (?, ?, ?, ?, ?)
    """, (original_name, ai_name, quantity_delta, image_path, source_label))
    conn.commit()
    conn.close()

def get_pending_confirmations():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    SELECT id, original_name, ai_name, quantity_delta, image_path, source_label 
    FROM ai_confirmations 
    WHERE status = 'pending'
    """)
    rows = c.fetchall()
    conn.close()
    
    confirmations = []
    for r in rows:
        confirmations.append({
            "id": r[0],
            "original_name": r[1],
            "ai_name": r[2],
            "quantity_delta": r[3],
            "image_path": r[4],
            "source_label": r[5]
        })
    return confirmations

def resolve_confirmation(conf_id, action):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT original_name, ai_name, quantity_delta, image_path, source_label FROM ai_confirmations WHERE id = ?", (conf_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
        
    original_name, ai_name, quantity_delta, image_path, source_label = row
    
    if action == "accept":
        # Revert old delta from inventory
        update_inventory(original_name, -quantity_delta, source="AI Correction Revert")
        # Add new correct delta to inventory
        update_inventory(ai_name, quantity_delta, image_path=image_path, source="AI Correction Apply")
        c.execute("UPDATE ai_confirmations SET status = 'confirmed' WHERE id = ?", (conf_id,))
    else:
        c.execute("UPDATE ai_confirmations SET status = 'rejected' WHERE id = ?", (conf_id,))
        
    conn.commit()
    conn.close()
    return True

def get_contacts():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, phone FROM contacts ORDER BY name ASC")
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "phone": r[2]} for r in rows]

def create_contact(name, phone):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO contacts (name, phone) VALUES (?, ?)", (name, phone))
    conn.commit()
    conn.close()

def delete_contact(contact_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    conn.commit()
    conn.close()

def update_contact(contact_id, name, phone):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE contacts SET name = ?, phone = ? WHERE id = ?", (name, phone, contact_id))
    conn.commit()
    conn.close()