# detection.py — YOLO Model ile Nesne Tespiti
import numpy as np
import cv2
from PIL import Image
from pathlib import Path
from collections import Counter
from ultralytics import YOLO

# --- YOLO Model Yolu ---
MODEL_PATH = Path(__file__).resolve().parent / "package-b-vision" / "models" / "best.pt"

_model = None

def load_model():
    """YOLO modelini yükler ve döndürür."""
    global _model
    if _model is None:
        import platform
        is_pi = "arm" in platform.machine().lower() or "aarch64" in platform.machine().lower()
        onnx_path = MODEL_PATH.with_suffix(".onnx")
        if onnx_path.exists() and not is_pi:
            _model = YOLO(str(onnx_path), task="detect")
            print(f"[MODEL] YOLO ONNX modeli yüklendi: {onnx_path.name}")
        else:
            if not MODEL_PATH.exists():
                raise FileNotFoundError(f"YOLO model dosyası bulunamadı: {MODEL_PATH}")
            _model = YOLO(str(MODEL_PATH))
            print(f"[MODEL] YOLO PyTorch modeli yüklendi: {MODEL_PATH.name}")
    return _model


def predict_image(filepath, confidence=0.25):
    """
    Verilen dosya yolundaki görseli YOLO modeli ile analiz eder.

    Parametreler:
        filepath (str): Resim dosyasının yolu.
        confidence (float): Minimum güven eşiği (0-1 arası).

    Döndürür:
        detections (list[dict]): Tespit edilen nesnelerin listesi.
            Her nesne: {'class': str, 'confidence': float, 'bbox': (x1, y1, x2, y2)}
        img_rgb (numpy.ndarray): Kutuların çizildiği RGB görsel.
    """
    model = load_model()

    # YOLO inference
    results = model.predict(source=filepath, conf=confidence, verbose=False)
    result = results[0]
    img = result.orig_img.copy()

    detections = []
    if result.boxes is not None and len(result.boxes) > 0:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
            class_name = model.names.get(cls_id, str(cls_id))

            detections.append({
                'class': class_name,
                'confidence': conf,
                'bbox': (x1, y1, x2, y2)
            })

            # Kutuları çiz
            color = (40, 220, 40)
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            label = f"{class_name} {conf:.0%}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            cv2.rectangle(img, (x1, y1 - th - 10), (x1 + tw + 4, y1), color, -1)
            cv2.putText(img, label, (x1 + 2, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return detections, img_rgb


def format_detections(detections):
    """
    Tespit listesini 'Ürün Adı: Adet, ...' formatına çevirir.
    Gemini çıktısıyla aynı format.
    """
    if not detections:
        return ""
    counts = Counter(d['class'] for d in detections)
    return ", ".join(f"{name}: {count}" for name, count in counts.items())


def parse_result_string(result_str):
    """
    'Ürün Adı: Adet, Ürün Adı: Adet' formatındaki stringi dict'e çevirir.
    Döndürür: dict  → {'ürün_adı': adet, ...}
    """
    items = {}
    if not result_str:
        return items
    for part in result_str.split(","):
        part = part.strip()
        if ":" in part:
            name, qty = part.rsplit(":", 1)
            name = name.strip()
            try:
                qty = int(qty.strip())
            except ValueError:
                qty = 1
            items[name] = items.get(name, 0) + qty
    return items


def compare_results(model_result_str, gemini_result_str):
    """
    YOLO model sonuçlarını Gemini AI sonuçlarıyla karşılaştırır.

    Döndürür:
        final_result (str): Envantere eklenecek nihai sonuç stringi.
        source_info (str): Kaynağın neresi olduğunu belirten etiket.
    """
    model_items = parse_result_string(model_result_str)
    gemini_items = parse_result_string(gemini_result_str)

    # Hiçbiri bulamadıysa
    if not model_items and not gemini_items:
        return "", "❌ Hiçbir kaynak tespit yapamadı"

    # Sadece model bulduysa
    if model_items and not gemini_items:
        return model_result_str, "🎯 YOLO Model (AI yanıt vermedi)"

    # Sadece AI bulduysa
    if not model_items and gemini_items:
        return gemini_result_str, "🤖 Yapay Zeka (Model tespit edemedi)"

    # İkisi de bulduysa → karşılaştır
    # Normalize et: küçük harfle karşılaştır
    m_norm = {k.lower().strip(): v for k, v in model_items.items()}
    g_norm = {k.lower().strip(): v for k, v in gemini_items.items()}

    if m_norm == g_norm:
        return model_result_str, "🎯✅ YOLO Model (Yapay Zeka teyit etti — %100 uyum)"

    # Kısmi uyum kontrolü: aynı ürünler var mı?
    common_keys = set(m_norm.keys()) & set(g_norm.keys())
    if common_keys:
        # Aynı ürünlerin adetleri eşleşiyor mu?
        matching = sum(1 for k in common_keys if m_norm[k] == g_norm[k])
        total = max(len(m_norm), len(g_norm))
        match_pct = int(matching / total * 100) if total > 0 else 0

        if match_pct >= 50:
            return gemini_result_str, f"🤖 Yapay Zeka tercih edildi (Model ile %{match_pct} uyum)"
        else:
            return gemini_result_str, f"⚠️ Yapay Zeka (Model ile düşük uyum: %{match_pct})"
    else:
        # Tamamen farklı sonuçlar
        return gemini_result_str, "⚠️ Yapay Zeka (Model tamamen farklı sonuç verdi)"