# vision_sync.py — Paket B (Vision Engine) çıktılarını Flask uygulamasıyla senkronize eder
import json
from pathlib import Path
from datetime import datetime
import db

# Paket B çıktı klasörü
VISION_OUTPUT = Path(__file__).resolve().parent / "package-b-vision" / "output"

# Hangi oturumların zaten işlendiğini takip eder (uygulama çalıştığı sürece)
_processed_sessions = set()


def get_all_session_dirs():
    """Tüm oturum klasörlerini bulur (tarih sıralı, en yeni en üstte)."""
    dirs = []

    # Ana output klasöründe doğrudan events.json varsa (eski format)
    if (VISION_OUTPUT / "events.json").exists():
        dirs.append(VISION_OUTPUT)

    # Alt klasörlerdeki oturumlar (yeni format)
    if VISION_OUTPUT.exists():
        for d in VISION_OUTPUT.iterdir():
            if d.is_dir() and (d / "events.json").exists():
                dirs.append(d)

    # En yeni en üstte
    dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return dirs


def get_latest_session_dir():
    """En son oturum klasörünü döndürür."""
    dirs = get_all_session_dirs()
    return dirs[0] if dirs else None


def read_events(session_dir=None):
    """Belirtilen oturumdaki events.json'ı okur."""
    if session_dir is None:
        session_dir = get_latest_session_dir()
    if session_dir is None:
        return []

    events_file = Path(session_dir) / "events.json"
    if not events_file.exists():
        return []

    with open(events_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def read_summary(session_dir=None):
    """Belirtilen oturumdaki summary.json'ı okur."""
    if session_dir is None:
        session_dir = get_latest_session_dir()
    if session_dir is None:
        return {}

    summary_file = Path(session_dir) / "summary.json"
    if not summary_file.exists():
        return {}

    with open(summary_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def sync_events_to_db(session_dir=None):
    """
    Vision Engine olaylarını veritabanıyla senkronize eder.
    Her GIRIS → stok +1, her CIKIS → stok -1.

    Döndürür:
        synced_count (int): Senkronize edilen olay sayısı.
        events (list): İşlenen olayların listesi.
        session_id (str): İşlenen oturum kimliği.
    """
    if session_dir is None:
        session_dir = get_latest_session_dir()
    if session_dir is None:
        return 0, [], "yok"

    events = read_events(session_dir)
    summary = read_summary(session_dir)
    session_id = summary.get("session_id", Path(session_dir).name)

    # Zaten işlenmişse atla
    if session_id in _processed_sessions:
        return 0, events, session_id

    synced = 0
    for event in events:
        product = event.get('product_name', 'Bilinmeyen')
        action = event.get('action', '')
        delta = event.get('quantity_delta', 0)
        confidence = event.get('confidence', 0)

        # Veritabanına yaz
        source_label = f"Vision Engine ({action} — güven: {confidence:.0%})"
        db.update_inventory(product, delta, source=source_label)
        synced += 1

    _processed_sessions.add(session_id)
    return synced, events, session_id


def get_vision_status():
    """
    Vision Engine'in mevcut durumunu döndürür.
    Frontend'de göstermek için.
    """
    session_dir = get_latest_session_dir()
    if not session_dir:
        return {
            "active": False,
            "session_id": None,
            "total_events": 0,
            "total_frames": 0,
            "events": [],
            "summary": {}
        }

    events = read_events(session_dir)
    summary = read_summary(session_dir)

    return {
        "active": True,
        "session_id": summary.get("session_id", "bilinmiyor"),
        "total_events": len(events),
        "total_frames": summary.get("total_frames", 0),
        "elapsed_seconds": summary.get("elapsed_seconds", 0),
        "processed_fps": summary.get("processed_fps", 0),
        "event_counts": summary.get("event_counts", {}),
        "product_event_counts": summary.get("product_event_counts", {}),
        "events": events,
        "summary": summary
    }
