import sqlite3

def fix_db():
    conn = sqlite3.connect('fridge.db')
    c = conn.cursor()
    
    # Inventory tablosuna image_path ekle
    try:
        c.execute('ALTER TABLE inventory ADD COLUMN image_path TEXT')
        print("image_path kolonu eklendi.")
    except sqlite3.OperationalError:
        print("image_path kolonu zaten var.")
        
    # Shopping List tablosunu kontrol et/oluştur
    c.execute("""
    CREATE TABLE IF NOT EXISTS shopping_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_name TEXT UNIQUE,
        quantity INTEGER DEFAULT 1,
        is_added INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    print("Alışveriş listesi tablosu kontrol edildi.")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    fix_db()
