# app.py — Smart Fridge Ana Uygulama
from flask import Flask, render_template, request, redirect, url_for, jsonify
import db
from detection import predict_image, load_model, format_detections, compare_results
from PIL import Image
import os
from theme import get_theme
import google.generativeai as genai
from gemini_service import gemini_ile_tespit_et, API_KEY

genai.configure(api_key=API_KEY)

app = Flask(__name__)
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs("static/items_photos", exist_ok=True)

# DB tablosu
db.create_tables()

# YOLO Model başta yükle
model = load_model()

import platform

def get_system_status():
    is_pi = "arm" in platform.machine().lower() or "aarch64" in platform.machine().lower()
    if is_pi:
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp = float(f.read()) / 1000.0
            return f"Raspberry Pi OS ({temp:.1f}°C)"
        except:
            return "Raspberry Pi OS"
    return f"{platform.system()} ({platform.machine()})"

# Context processor ile tüm template'lerde tema erişilebilir
@app.context_processor
def inject_theme():
    import datetime
    def get_freshness(expiry_date, created_at):
        if not expiry_date:
            return {"percentage": 100, "status": "Taze", "color": "success"}
        try:
            exp_str = str(expiry_date).strip()
            if len(exp_str) > 10:
                exp_str = exp_str[:10]
            expiry = datetime.datetime.strptime(exp_str, "%Y-%m-%d").date()
            
            created_str = str(created_at).strip() if created_at else ""
            if created_str:
                if len(created_str) > 10:
                    created_str = created_str[:10]
                created = datetime.datetime.strptime(created_str, "%Y-%m-%d").date()
            else:
                created = datetime.date.today()
                
            today = datetime.date.today()
            total_days = (expiry - created).days
            remaining_days = (expiry - today).days
            
            if remaining_days <= 0:
                return {"percentage": 0, "status": "Bozulmuş", "color": "danger"}
            if total_days <= 0:
                return {"percentage": 100, "status": "Taze", "color": "success"}
                
            pct = min(100, max(0, int((remaining_days / total_days) * 100)))
            if pct > 60:
                return {"percentage": pct, "status": "Taze", "color": "success"}
            elif pct > 25:
                return {"percentage": pct, "status": "Kritik", "color": "warning"}
            else:
                return {"percentage": pct, "status": "Bozulmak Üzere", "color": "danger"}
        except Exception as e:
            return {"percentage": 100, "status": "Taze", "color": "success"}

    return dict(tema=get_theme('light'), system_status=get_system_status(), get_freshness=get_freshness)

# --- Launcher (Ana Sayfa) ---
@app.route("/")
def index():
    return render_template("index.html")

# --- İstatistikler (Eski Dashboard) ---
@app.route("/stats")
def stats():
    df = db.get_inventory()
    # Sadece stokta olanları baz al
    active_df = df[df["quantity"] > 0]
    total = active_df["quantity"].sum() if not active_df.empty else 0
    item_count = len(active_df) if not active_df.empty else 0
    return render_template("stats.html", total=total, item_count=item_count, inventory=df)

# --- Inventory ---
@app.route("/inventory", methods=["GET","POST"])
def inventory():
    df = db.get_inventory()
    if request.method=="POST":
        item = request.form["item"]
        qty = int(request.form["qty"])
        action = request.form["action"]
        expiry = request.form.get("expiry_date")
        db.update_inventory(item, qty if action=="add" else -qty, expiry_date=expiry)
        return redirect(url_for("inventory"))
    return render_template("inventory.html", inventory=df)

# --- Akıllı Göz (Ürün Tara) — Model + AI Karşılaştırma ---
@app.route("/scan", methods=["GET", "POST"])
def scan():
    uploaded_filename = None
    result_filename = None
    model_result = None
    gemini_result = None
    final_result = None
    source_info = None
    model_detections = []

    if request.method == "POST":
        file = request.files.get("image")
        if file and file.filename:
            # Dosyayı kaydet
            filename = file.filename
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            uploaded_filename = filename

            # ─── ADIM 1: YOLO Model Tespiti ───
            try:
                detections, img_rgb = predict_image(filepath)
                model_detections = detections

                # Sonuç resmini kaydet
                result_img = Image.fromarray(img_rgb)
                result_filename = "result_" + uploaded_filename
                result_img.save(os.path.join(UPLOAD_FOLDER, result_filename))

                # Model sonuçlarını formatla
                model_result = format_detections(detections)
                print(f"[MODEL] YOLO Tespiti: {model_result}")
            except Exception as e:
                print(f"[HATA] YOLO Model hatası: {e}")
                result_filename = uploaded_filename
                model_result = ""

            # ─── ADIM 2: Gemini AI Teyidi ───
            try:
                gemini_result = gemini_ile_tespit_et(filepath)
                print(f"[AI] Gemini Tespiti: {gemini_result}")
            except Exception as e:
                print(f"[HATA] Gemini AI hatası: {e}")
                gemini_result = ""

            # ─── ADIM 3: Karşılaştırma ve Karar ───
            final_result, source_info = compare_results(model_result, gemini_result)
            print(f"[KARAR] Sonuç: {final_result} | Kaynak: {source_info}")

    return render_template(
        "scan.html",
        uploaded_filename=uploaded_filename,
        result_filename=result_filename,
        model_result=model_result or "",
        gemini_result=gemini_result or "",
        final_result=final_result or "",
        source_info=source_info or "",
        model_detections=model_detections
    )

# --- Process AI Result (Envantere ekle) ---
@app.route("/process_ai", methods=["POST"])
def process_ai():
    final_result = request.form.get("final_result")
    source_info = request.form.get("source_info", "Bilinmiyor")
    uploaded_filename = request.form.get("uploaded_filename")

    if final_result:
        # Format: "Ürün Adı: Adet, Ürün Adı: Adet"
        items = final_result.split(",")
        for item in items:
            if ":" in item:
                name, qty = item.rsplit(":", 1)
                name = name.strip()
                try:
                    qty = int(qty.strip())

                    # Ürünün resmini kopyala (ilk kez eklenen ürünler için)
                    image_path = None
                    if uploaded_filename:
                        import shutil
                        ext = os.path.splitext(uploaded_filename)[1]
                        new_photo_name = f"{name.replace(' ', '_').lower()}{ext}"
                        new_photo_path = os.path.join("static/items_photos", new_photo_name)

                        if not os.path.exists(new_photo_path):
                            src_path = os.path.join(UPLOAD_FOLDER, uploaded_filename)
                            if os.path.exists(src_path):
                                shutil.copy(src_path, new_photo_path)

                        image_path = f"items_photos/{new_photo_name}"

                    db.update_inventory(name, qty, image_path=image_path, source=f"Scan ({source_info})")
                except Exception as e:
                    print(f"İşleme hatası ({name}): {e}")
                    continue
        return redirect(url_for("inventory"))
    return redirect(url_for("scan"))

# --- Vision Engine Olayları (Paket B Entegrasyonu) ---
import threading
import cv2
import sys
from flask import Response

TRANSLATIONS = {
    'apple': 'Elma',
    'banana': 'Muz',
    'beef': 'Kırmızı Et',
    'beetroot': 'Pancar',
    'blueberries': 'Yaban Mersini',
    'bread': 'Ekmek',
    'broccoli': 'Brokoli',
    'butter': 'Tereyağı',
    'cabbage': 'Lahana',
    'carrot': 'Havuç',
    'cauliflower': 'Karnabahar',
    'cheese': 'Peynir',
    'chicken': 'Tavuk',
    'chocolate': 'Çikolata',
    'corn': 'Mısır',
    'cucumber': 'Salatalık',
    'eggplant': 'Patlıcan',
    'eggs': 'Yumurta',
    'flour': 'Un',
    'garlic': 'Sarımsak',
    'ginger': 'Zencefil',
    'goat_cheese': 'Keçi Peyniri',
    'green_beans': 'Taze Fasulye',
    'ground_beef': 'Kıyma',
    'ham': 'Jambon',
    'heavy_cream': 'Krema',
    'jalapeno': 'Halapenyo',
    'lemon': 'Limon',
    'lettuce': 'Marul',
    'mayonnaise': 'Mayonez',
    'milk': 'Süt',
    'mushrooms': 'Mantar',
    'natural_yoghurt': 'Yoğurt',
    'okra': 'Bamya',
    'onion': 'Soğan',
    'orange': 'Portakal',
    'peas': 'Bezelye',
    'pepper': 'Biber',
    'potato': 'Patates',
    'radish': 'Turp',
    'shrimp': 'Karides',
    'spinach': 'Ispanak',
    'strawberries': 'Çilek',
    'sugar': 'Şeker',
    'sweet_potato': 'Tatlı Patates',
    'tomato': 'Domates',
    'turnip': 'Şalgam'
}

vision_thread = None
vision_running = False
latest_frame = None
live_events = []  # Canlı oturumda tespit edilen olaylar (bellekte)

def get_camera_source():
    if os.path.exists("camera_source.txt"):
        try:
            with open("camera_source.txt", "r", encoding="utf-8") as f:
                src = f.read().strip()
                if src:
                    return src
        except:
            pass
    video_source = "http://192.168.1.106:8080/video"
    try:
        with open("package-b-vision/vision_engine.py", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VIDEO_SOURCE") and "=" in line:
                    video_source = line.split("=")[1].strip().strip('"').strip("'")
                    break
    except:
        pass
    return video_source

def set_camera_source(source):
    try:
        with open("camera_source.txt", "w", encoding="utf-8") as f:
            f.write(source)
    except Exception as e:
        print(f"Error saving to camera_source.txt: {e}")

def run_vision_engine_thread():
    global vision_running, latest_frame, live_events
    print("[VISION THREAD] Thread başlatıldı...")
    
    # Video kaynağını oku
    video_source = get_camera_source()
    print(f"[VISION THREAD] Video kaynağı: {video_source}")

    try:
        sys.path.insert(0, os.path.abspath("package-b-vision"))
        import importlib
        import vision_engine as ve_mod
        importlib.reload(ve_mod)
        from vision_engine import VisionPipeline, VisionConfig
        print("[VISION THREAD] VisionPipeline import edildi.")

        from pathlib import Path
        import platform
        
        is_pi = "arm" in platform.machine().lower() or "aarch64" in platform.machine().lower()
        if is_pi:
            print("[VISION THREAD] Raspberry Pi algılandı! Donanım optimizasyonlu profil (pi) kullanılıyor...")
            config = VisionConfig(
                weights_path=Path("package-b-vision/models/best.pt"),
                tracker_mode="simple",
                imgsz=320,
                vid_stride=3,
                max_det=15,
                cpu_threads=2,
                min_consecutive=5,
                event_cooldown_frames=30,
                conf=0.35,
                show=False,
                save_video=False
            )
        else:
            config = VisionConfig(
                weights_path=Path("package-b-vision/models/best.pt"),
                tracker_mode="bytetrack",
                min_consecutive=5,          # Çizgi geçişi kararlılığı için ardışık kare sayısı (artırıldı)
                event_cooldown_frames=30,   # İki geçiş arası bekleme karesi (artırıldı, yakl. 1 saniye)
                conf=0.35,                  # Yalancı tespitleri engellemek için güven eşiği (yükseltildi)
                show=False,
                save_video=False
            )
        print("[VISION THREAD] Config oluşturuldu, pipeline başlatılıyor...")
        pipeline = VisionPipeline(config)
        print("[VISION THREAD] Pipeline hazır, kameraya bağlanılıyor...")
        # Threaded camera class to eliminate buffer latency
        import cv2
        import threading
        class ThreadedCamera:
            def __init__(self, src):
                self.cap = cv2.VideoCapture(src)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                self.ret = False
                self.frame = None
                self.running = True
                self.thread = threading.Thread(target=self._reader)
                self.thread.daemon = True
                self.thread.start()
                
            def _reader(self):
                while self.running:
                    ret, frame = self.cap.read()
                    if ret:
                        self.ret = ret
                        self.frame = frame
                    else:
                        _time.sleep(0.01)
                        
            def read(self):
                return self.ret, self.frame
                
            def release(self):
                self.running = False
                self.cap.release()

        def update_frame(frame):
            global latest_frame, vision_running
            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                latest_frame = buffer.tobytes()
            return vision_running

        def patched_run(source, output_dir, frame_callback=None):
            """pipeline.run'ı sarıp olayları canlı yakalayan wrapper."""
            global live_events
            
            from vision_engine import VisionConfig, build_session_id, LineCrossingCounter, SimpleTracker, utc_now_iso
            import time as _time
            from pathlib import Path as _Path
            from collections import Counter

            cam_source = int(source) if str(source).isdigit() else source

            session_id = build_session_id(str(source))
            started_at, started_perf = utc_now_iso(), _time.perf_counter()
            output_path = _Path(output_dir) / session_id
            output_path.mkdir(parents=True, exist_ok=True)

            counter = LineCrossingCounter(
                session_id=session_id, line_orientation=pipeline.config.line_orientation,
                line_position=pipeline.config.line_position, min_consecutive=pipeline.config.min_consecutive,
                max_idle_frames=pipeline.config.max_idle_frames, event_cooldown_frames=pipeline.config.event_cooldown_frames
            )

            events, frame_index = [], 0
            tracker = SimpleTracker(pipeline.config.tracker_iou_threshold, pipeline.config.tracker_max_misses) if pipeline.config.tracker_mode == "simple" else None

            # Caching state to draw on skipped frames and avoid flickering
            last_tracked_objects = []

            print(f"[VISION THREAD] ThreadedCamera başlatılıyor: {cam_source}")
            cam = ThreadedCamera(cam_source)
            _time.sleep(1.0) # Kameranın ısınması için bekle

            try:
                while vision_running:
                    ret, frame = cam.read()
                    if not ret or frame is None:
                        _time.sleep(0.01)
                        continue
                        
                    frame_index += 1
                    
                    # Raspberry Pi CPU yükünü azaltmak için frame skipping
                    # Ancak titremeyi engellemek için son tespitleri de çizerek gönderiyoruz!
                    if pipeline.config.vid_stride > 1 and (frame_index % pipeline.config.vid_stride) != 0:
                        if frame_callback:
                            height, width = frame.shape[:2]
                            annotated_frame = pipeline._draw(frame.copy(), last_tracked_objects, len(events), width, height)
                            should_continue = frame_callback(annotated_frame)
                            if should_continue is False:
                                break
                        continue
                    
                    results = pipeline.detector.model.predict(
                        frame, 
                        imgsz=pipeline.config.imgsz, 
                        conf=pipeline.config.conf, 
                        iou=pipeline.config.iou, 
                        device=pipeline.config.device, 
                        verbose=False
                    )
                    
                    if not results:
                        last_tracked_objects = []
                        if frame_callback:
                            should_continue = frame_callback(frame)
                            if should_continue is False:
                                break
                        continue
                        
                    result = results[0]
                    height, width = result.orig_shape
                    active_ids = set()
                    tracked_objects = pipeline._get_tracked(result, tracker)
                    last_tracked_objects = tracked_objects
                    
                    for tracked in tracked_objects:
                        x1, y1, x2, y2 = tracked["bbox"]
                        side = counter.compute_side((x1+x2)/2, (y1+y2)/2, width, height)
                        p_name = pipeline.detector.class_names.get(tracked["class_id"], str(tracked["class_id"]))
                        active_ids.add(tracked["track_id"])

                        event = counter.register_detection(
                            track_id=tracked["track_id"], product_name=p_name,
                            confidence=tracked["confidence"], frame_index=frame_index, side=side
                        )
                        if event:
                            tr_name = TRANSLATIONS.get(event.product_name.lower(), event.product_name)
                            event.product_name = tr_name
                            e_dict = event.to_dict()
                            
                            try:
                                cx1, cy1, cx2, cy2 = [int(v) for v in tracked["bbox"]]
                                h_img, w_img = frame.shape[:2]
                                cx1, cy1 = max(0, cx1), max(0, cy1)
                                cx2, cy2 = min(w_img, cx2), min(h_img, cy2)
                                
                                if cx2 > cx1 and cy2 > cy1:
                                    cropped = frame[cy1:cy2, cx1:cx2]
                                    safe_pname = tr_name.replace(' ', '_').lower()
                                    photo_rel_path = f"items_photos/{safe_pname}.jpg"
                                    photo_full_path = os.path.join("static", photo_rel_path)
                                    cv2.imwrite(photo_full_path, cropped)
                                    e_dict["image_path"] = photo_rel_path
                                else:
                                    e_dict["image_path"] = None
                            except Exception as img_err:
                                print(f"[VISION PHOTO] Resim kaydetme hatası: {img_err}")
                                e_dict["image_path"] = None

                            events.append(e_dict)
                            live_events.append(e_dict)
                            print(f"[EVENT] {e_dict['timestamp_utc']} - {e_dict['product_name']}: {e_dict['action']}")

                    counter.prune_stale_tracks(frame_index, active_ids)

                    annotated_frame = pipeline._draw(frame.copy(), tracked_objects, len(events), width, height)
                    if frame_callback:
                        should_continue = frame_callback(annotated_frame)
                        if should_continue is False:
                            break
            except Exception as loop_err:
                print(f"[VISION THREAD] Döngü hatası: {loop_err}")
            finally:
                cam.release()
                cv2.destroyAllWindows()

        patched_run(video_source, "package-b-vision/output", frame_callback=update_frame)
        print("[VISION THREAD] Pipeline.run() sona erdi.")
    except Exception as e:
        import traceback
        print(f"[VISION THREAD] HATA: {e}")
        traceback.print_exc()
    finally:
        vision_running = False
        print("[VISION THREAD] Thread sonlandırıldı.")

@app.route("/vision")
def vision_events():
    video_source = get_camera_source()
    
    # URL'den IP adresini ayıkla (http://IP:8080/video formatı için)
    camera_ip = ""
    if video_source.startswith("http://") and ":8080/video" in video_source:
        camera_ip = video_source.replace("http://", "").replace(":8080/video", "")
    else:
        camera_ip = video_source
        
    display_source = url_for('video_feed') if vision_running else video_source
    
    return render_template("vision.html", status={"total_events": len(live_events), "events": live_events}, is_running=vision_running, video_source=display_source, camera_ip=camera_ip)

@app.route('/video_feed')
def video_feed():
    def generate():
        global latest_frame, vision_running
        import numpy as np
        loading_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(loading_frame, "Sistem Baslatiliyor, Lutfen Bekleyin...", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        ret, buffer = cv2.imencode('.jpg', loading_frame)
        loading_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + loading_bytes + b'\r\n')
               
        while vision_running:
            if latest_frame is not None:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + latest_frame + b'\r\n')
            import time
            time.sleep(0.05)
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/api/save_camera_source", methods=["POST"])
def save_camera_source():
    data = request.json or {}
    source = data.get("source", "").strip()
    if not source:
        return jsonify({"status": "error", "message": "Boş kaynak girilemez."}), 400
        
    try:
        set_camera_source(source)
        return jsonify({"status": "success", "source": source})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/start_vision", methods=["POST"])
def start_vision():
    global vision_thread, vision_running, live_events
    if not vision_running:
        live_events = []  # Yeni oturumda eski olayları temizle
        vision_running = True
        vision_thread = threading.Thread(target=run_vision_engine_thread)
        vision_thread.daemon = True
        vision_thread.start()
        return {"status": "started"}
    return {"status": "already_running"}

@app.route("/api/stop_vision", methods=["POST"])
def stop_vision():
    global vision_running, vision_thread
    if vision_running:
        vision_running = False
        if vision_thread:
            vision_thread.join(timeout=5)
        return {"status": "stopped", "total_events": len(live_events)}
    return {"status": "not_running"}

ai_check_tasks = []

def async_verify_with_ai(events):
    global ai_check_tasks
    import time
    from gemini_service import gemini_ile_tespit_et
    
    current_tasks = []
    for i, ev in enumerate(events):
        task_id = f"task_{int(time.time() * 1000)}_{i}"
        task = {
            "id": task_id,
            "product_name": ev["original_name"],
            "image_path": ev["image_path"],
            "status": "pending",
            "ai_result": None
        }
        ai_check_tasks.insert(0, task)
        current_tasks.append((task, ev))
        
    ai_check_tasks = ai_check_tasks[:15]
    
    print(f"[AI VERIFY] {len(events)} adet olay icin teyit sureci baslatildi...")
    for task, ev in current_tasks:
        task["status"] = "checking"
        orig = ev["original_name"]
        delta = ev["quantity_delta"]
        img_path = ev["image_path"]
        src_lbl = ev["source_label"]
        
        full_path = os.path.join("static", img_path)
        if not os.path.exists(full_path):
            task["status"] = "failed"
            task["ai_result"] = "Dosya bulunamadi"
            continue
            
        try:
            ai_result = gemini_ile_tespit_et(full_path)
            print(f"[AI VERIFY] Gemini tespiti: {ai_result} (YOLO: {orig})")
            
            ai_name = None
            if ai_result and ":" in ai_result:
                parts = ai_result.split(",")
                first_part = parts[0]
                if ":" in first_part:
                    ai_name = first_part.split(":")[0].strip()
                    
            if ai_name:
                task["ai_result"] = ai_name
                if ai_name.lower().strip() != orig.lower().strip():
                    task["status"] = "discrepancy"
                    print(f"[AI VERIFY] Farklilik tespit edildi! YOLO: {orig} | AI: {ai_name}")
                    db.create_ai_confirmation(orig, ai_name, delta, img_path, src_lbl)
                else:
                    task["status"] = "verified"
            else:
                task["status"] = "failed"
                task["ai_result"] = "Format hatası"
        except Exception as ex:
            print(f"[AI VERIFY] Hata olustu: {ex}")
            task["status"] = "failed"
            task["ai_result"] = str(ex)

@app.route("/vision/sync", methods=["POST"])
def vision_sync_route():
    """Canlı oturumdaki olayları veritabanına senkronize eder."""
    global live_events
    synced = 0
    events_to_verify = []
    for event in live_events:
        product = event.get('product_name', 'Bilinmeyen')
        action = event.get('action', '')
        delta = event.get('quantity_delta', 0)
        confidence = event.get('confidence', 0)
        image_path = event.get('image_path', None)
        source_label = f"Vision Engine ({action} — güven: {confidence:.0%})"
        db.update_inventory(product, delta, image_path=image_path, source=source_label)
        synced += 1
        
        if image_path and not event.get("is_ai_verified", False):
            events_to_verify.append({
                "original_name": product,
                "quantity_delta": delta,
                "image_path": image_path,
                "source_label": source_label
            })
    
    if synced > 0:
        if events_to_verify:
            threading.Thread(target=async_verify_with_ai, args=(events_to_verify,)).start()
        live_events = []  # İşlendi, temizle
        return redirect(url_for("inventory"))
    return redirect(url_for("vision_events"))

@app.route("/api/vision_status")
def api_vision_status():
    """Canlı olay listesini JSON olarak döndürür."""
    return jsonify({
        "total_events": len(live_events),
        "events": live_events
    })

@app.route("/api/pending_confirmations")
def api_pending_confirmations():
    """Teyit bekleyen AI uyuşmazlık listesini döndürür."""
    confs = db.get_pending_confirmations()
    return jsonify(confs)

@app.route("/api/resolve_confirmation", methods=["POST"])
def api_resolve_confirmation():
    """AI teyidini onaylar veya reddeder."""
    data = request.json or {}
    conf_id = data.get("id")
    action = data.get("action")
    if not conf_id or not action:
        return jsonify({"status": "error", "message": "Eksik parametre."}), 400
        
    success = db.resolve_confirmation(conf_id, action)
    if success:
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Islem basarisiz."}), 500

@app.route("/api/ai_tasks")
def api_ai_tasks():
    global ai_check_tasks
    active_count = sum(1 for t in ai_check_tasks if t["status"] in ["pending", "checking"])
    return jsonify({
        "active_count": active_count,
        "tasks": ai_check_tasks
    })

@app.route("/api/capture_and_analyze", methods=["POST"])
def capture_and_analyze_route():
    global latest_frame, live_events
    if latest_frame is None:
        return jsonify({"status": "error", "message": "Canli yayin aktif degil."}), 400
        
    try:
        import uuid
        from gemini_service import gemini_ile_tespit_et
        
        filename = f"manual_{uuid.uuid4().hex[:8]}.jpg"
        rel_path = f"items_photos/{filename}"
        full_path = os.path.join("static", rel_path)
        
        with open(full_path, "wb") as f:
            f.write(latest_frame)
            
        print(f"[MANUAL CAPTURE] Goruntu kaydedildi: {full_path}")
        
        ai_result = gemini_ile_tespit_et(full_path)
        print(f"[MANUAL CAPTURE] Gemini sonucu: {ai_result}")
        
        detected_items = []
        if ai_result and "hata" not in ai_result.lower():
            parts = ai_result.split(",")
            for part in parts:
                if ":" in part:
                    pname, qty_str = part.split(":")
                    pname = pname.strip()
                    try:
                        qty = int(qty_str.strip())
                    except:
                        qty = 1
                    
                    e_dict = {
                        "action": "GIRIS",
                        "product_name": pname,
                        "quantity_delta": qty,
                        "confidence": 1.0,
                        "image_path": rel_path,
                        "is_ai_verified": True
                    }
                    live_events.append(e_dict)
                    detected_items.append(f"{qty} {pname}")
                    
        if detected_items:
            return jsonify({
                "status": "success",
                "message": f"Algilanan Urunler: {', '.join(detected_items)}",
                "items": detected_items
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Goruntuden herhangi bir yiyecek/icecek algilanamadi veya AI hatasi olustu."
            }), 400
            
    except Exception as e:
        print(f"[MANUAL CAPTURE] Hata: {e}")
        return jsonify({"status": "error", "message": f"Islem sirasinda hata olustu: {str(e)}"}), 500

# --- Recipes (Sayfa) ---
@app.route("/recipes")
def recipes():
    df = db.get_inventory()
    active_items = df[df["quantity"] > 0].to_dict(orient="records")
    return render_template("recipes.html", items=active_items)

# --- Recipes (API - Gecikmeli Yükleme) ---
@app.route("/api/suggest_recipes", methods=["GET", "POST"])
def suggest_recipes():
    available_items = []
    if request.method == "POST":
        data = request.json or {}
        available_items = data.get("items", [])
        
    if not available_items:
        df = db.get_inventory()
        available_items = df[df["quantity"] > 0]["class_name"].tolist()
    items_str = ", ".join(available_items)

    if not items_str:
        db.log_system_event("RECIPE_API", "Tarif önerisi istendi ama stokta malzeme yok.")
        return {"recipes": "<p class='text-muted'>Buzdolabınızda malzeme bulunamadı.</p>"}

    db.log_system_event("RECIPE_API", f"Tarif önerisi istendi. Kullanılan malzemeler: {items_str}")
    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        prompt = f"Elimde şu malzemeler var: {items_str}. Bu malzemeleri kullanarak yapılabilecek 3 harika yemek tarifi öner. Her tarif için kısa bir başlık ve kısa bir tarif yaz. Yanıtı SADECE saf HTML (div, h4, p, ul, li etiketleri) kullanarak ver. ```html blokları içine ALMA, doğrudan kodu yaz."
        response = model.generate_content(prompt)
        db.log_system_event("RECIPE_API", "Tarif önerisi başarıyla üretildi.")
        return {"recipes": response.text}
    except Exception as e:
        print(f"Tarif hatası: {e}")
        error_msg = str(e)
        db.log_system_event("RECIPE_API", f"Tarif oluşturma başarısız oldu. HATA DETAYI: {error_msg}")
        if "quota" in error_msg.lower() or "limit" in error_msg.lower() or "429" in error_msg:
            return {
                "recipes": (
                    "<div class='alert alert-warning border-warning border-opacity-25 bg-warning bg-opacity-10 text-warning p-4 rounded-4' style='background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.25); color: #fbbf24;'>"
                    "<h5 class='fw-bold mb-2'><i class='fas fa-exclamation-triangle me-2'></i>Yapay Zeka İstek Sınırı</h5>"
                    "<p class='m-0 small'>Gemini API ücretsiz sürüm kotasını (dakikada 5 istek) doldurdunuz. Lütfen yaklaşık 30 saniye bekledikten sonra tekrar deneyin.</p>"
                    "</div>"
                )
            }
        return {"recipes": f"<p class='text-danger'>Tarif önerisi alınamadı. Hata: {error_msg}</p>"}

# --- Admin Panel ---
@app.route("/admin")
def admin():
    logs_df = db.get_system_logs()
    return render_template("admin.html", system_logs=logs_df)

@app.route("/admin/clear_inventory", methods=["POST"])
def clear_inventory():
    db.clear_all_data()
    return redirect(url_for("admin"))

# --- WP Contacts ---
@app.route("/contacts", methods=["GET", "POST"])
def contacts():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            name = request.form.get("name")
            phone = request.form.get("phone")
            if name and phone:
                db.create_contact(name, phone)
        elif action == "delete":
            contact_id = request.form.get("id")
            if contact_id:
                db.delete_contact(int(contact_id))
        elif action == "update":
            contact_id = request.form.get("id")
            name = request.form.get("name")
            phone = request.form.get("phone")
            if contact_id and name and phone:
                db.update_contact(int(contact_id), name, phone)
        return redirect(url_for("contacts"))
        
    c_list = db.get_contacts()
    return render_template("contacts.html", contacts=c_list)

@app.route("/api/whatsapp/send", methods=["POST"])
def whatsapp_send():
    data = request.json or {}
    contact_id = data.get("contact_id")
    if not contact_id:
        return jsonify({"status": "error", "message": "Kisi secilmedi."}), 400
        
    contacts_list = db.get_contacts()
    contact = next((c for c in contacts_list if c["id"] == int(contact_id)), None)
    if not contact:
        return jsonify({"status": "error", "message": "Kisi bulunamadi."}), 404
        
    shop_list = db.get_shopping_list()
    if shop_list.empty:
        return jsonify({"status": "error", "message": "Alisveris listeniz bos."}), 400
        
    # Format text message
    message_lines = ["*Smart Fridge Alisveris Listesi:*"]
    for idx, row in shop_list.iterrows():
        message_lines.append(f"- {row['quantity']} adet {row['class_name']}")
        
    message = "\n".join(message_lines)
    
    import urllib.parse
    encoded_message = urllib.parse.quote(message)
    # Clean phone number (remove non-digits)
    phone_clean = "".join(filter(str.isdigit, contact["phone"]))
    # Default country code to +90 if starting with 5
    if len(phone_clean) == 10 and phone_clean.startswith("5"):
        phone_clean = "90" + phone_clean
        
    whatsapp_url = f"https://api.whatsapp.com/send?phone={phone_clean}&text={encoded_message}"
    
    db.log_system_event("WHATSAPP_SEND", f"Alisveris listesi {contact['name']} kisisine gonderilmek uzere URL olusturuldu.")
    return jsonify({"status": "success", "url": whatsapp_url})

# --- Shopping List ---
@app.route("/shopping", methods=["GET", "POST"])
def shopping():
    if request.method == "POST":
        if "item" in request.form:
            db.add_to_shopping_list(request.form["item"], int(request.form.get("qty", 1)))
        elif "delete" in request.form:
            db.remove_from_shopping_list(int(request.form["delete"]))
        return redirect(url_for("shopping"))

    shop_list = db.get_shopping_list()
    inventory_df = db.get_inventory()
    
    # Miktari 3'ten az olan urunleri filtrele (Azalan/Tukenen)
    declining_df = inventory_df[inventory_df["quantity"] < 3]
    
    # Alisveris listesinde zaten olanlari tavsiyelerden cikar
    already_added = set(shop_list["class_name"].tolist())
    recommendations = declining_df[~declining_df["class_name"].isin(already_added)]
    
    contacts_list = db.get_contacts()
    return render_template("shopping.html", shop_list=shop_list, recommendations=recommendations, contacts=contacts_list)

# --- Voice Command (API) ---
@app.route("/api/voice", methods=["POST"])
def voice_command():
    data = request.json
    text = data.get("text", "").lower()

    response_text = "Sizi anlayamadım."

    if "buzdolabında ne var" in text or "envanter" in text:
        df = db.get_inventory()
        items = df[df["quantity"] > 0]
        if not items.empty:
            items_list = ", ".join([f"{row['quantity']} adet {row['class_name']}" for _, row in items.iterrows()])
            response_text = f"Şu an buzdolabında şunlar var: {items_list}"
        else:
            response_text = "Buzdolabınız şu an boş görünüyor."

    return {"response": response_text}

# --- Logs ---
@app.route("/logs")
def logs():
    df = db.get_logs()
    return render_template("logs.html", logs=df)

if __name__=="__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)