from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from math import hypot
from pathlib import Path
from typing import Any, Optional

import cv2
from ultralytics import YOLO

# ==============================================================================
# VİDEO KAYNAĞI SEÇİMİ (Kullanmak istediğiniz kaynağın başındaki '#' işaretini kaldırın)
# ==============================================================================

# SEÇENEK 1: IP Webcam / IP Kamera (Simülasyon veya Telefon Kamerası)
VIDEO_SOURCE = "http://192.168.1.106:8080/video"

# SEÇENEK 2: USB Kamera / Harici Donanım Kamerası (Sisteme bağlı gerçek kamera)
#VIDEO_SOURCE = 0

# ==============================================================================

# Varsayılan model yolu
PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_WEIGHTS = PACKAGE_ROOT / "models" / "best.pt"

# --- 1. Veri Yapıları ve Şemalar ---

@dataclass
class InventoryEvent:
    """Paket C'nin okuyacağı tekil olay kaydı."""
    session_id: str
    track_id: int
    product_name: str
    action: str
    quantity_delta: int
    confidence: float
    frame_index: int
    timestamp_utc: str

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class SessionSummary:
    """Oturum sonunda üretilen toplu özet."""
    session_id: str
    source: str
    weights_path: str
    total_frames: int
    total_events: int
    output_dir: str
    started_at_utc: str
    finished_at_utc: str
    elapsed_seconds: float = 0.0
    processed_fps: float = 0.0
    event_counts: dict[str, int] = field(default_factory=dict)
    product_event_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class Detection:
    """Detector'dan gelen ham kutu."""
    class_id: int
    confidence: float
    bbox: tuple[float, float, float, float]

@dataclass
class TrackedDetection:
    """Track ID atanmış kutu."""
    track_id: int
    class_id: int
    confidence: float
    bbox: tuple[float, float, float, float]

@dataclass
class Track:
    """Takip sırasında bellekte tuttuğumuz nesne kaydı."""
    track_id: int
    class_id: int
    confidence: float
    bbox: tuple[float, float, float, float]
    misses: int = 0

@dataclass
class TrackState:
    """Her track için olay üretiminde lazım olan küçük durum hafızası."""
    product_name: str
    confirmed_side: int
    candidate_side: Optional[int]
    candidate_count: int
    last_frame_index: int
    last_confidence: float
    last_event_frame: int = -10_000

def utc_now_iso() -> str:
    """Tüm zaman damgalarını UTC ve ISO formatında döndürür."""
    return datetime.now(timezone.utc).isoformat()

def build_session_id(source: str) -> str:
    """Her çalıştırmaya benzersiz ama okunabilir bir oturum adı verir."""
    safe_source = Path(str(source)).stem or "camera"
    safe_source = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in safe_source)
    return f"{safe_source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

# --- 2. Ayarlar ---

@dataclass
class VisionConfig:
    """Paket B'nin tüm çalışma ayarlarını tek yerde toplar."""
    weights_path: Path = DEFAULT_WEIGHTS
    imgsz: int = 512
    conf: float = 0.25
    iou: float = 0.45
    max_det: int = 24
    vid_stride: int = 2
    device: str = "cpu"
    cpu_threads: int = 2
    tracker_mode: str = "simple"
    tracker_iou_threshold: float = 0.20
    tracker_max_misses: int = 6
    line_orientation: str = "horizontal"
    line_position: float = 0.55
    min_consecutive: int = 3
    max_idle_frames: int = 60
    event_cooldown_frames: int = 12
    min_box_area: int = 900
    min_event_conf: float = 0.35
    ignored_class_names: tuple[str, ...] = field(default_factory=tuple)
    show: bool = False
    save_video: bool = False
    tracker: str = "bytetrack.yaml"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["weights_path"] = str(self.weights_path)
        return data

    def validate(self) -> None:
        if not self.weights_path.exists():
            raise FileNotFoundError(f"Model bulunamadı: {self.weights_path}")
        if self.imgsz < 128:
            raise ValueError("imgsz en az 128 olmalıdır")
        if self.max_det < 1:
            raise ValueError("max_det en az 1 olmalıdır")
        if self.vid_stride < 1:
            raise ValueError("vid_stride en az 1 olmalıdır")
        if self.cpu_threads < 1:
            raise ValueError("cpu_threads en az 1 olmalıdır")
        if self.tracker_mode not in {"simple", "bytetrack"}:
            raise ValueError("tracker_mode 'simple' veya 'bytetrack' olmalıdır")
        if not 0.0 < self.line_position < 1.0:
            raise ValueError("line_position 0 ile 1 arasında olmalıdır")

# --- 3. Bileşenler ---

class SimpleTracker:
    """Hafif nesne takipçisi (IoU ve merkez mesafesi tabanlı)."""
    def __init__(self, iou_threshold: float = 0.25, max_misses: int = 8) -> None:
        self.iou_threshold = iou_threshold
        self.max_misses = max_misses
        self.next_track_id = 1
        self.tracks: dict[int, Track] = {}

    def update(self, detections: list[Detection]) -> list[TrackedDetection]:
        matches = self._match(detections)
        matched_detection_indexes = set()
        active_tracks: list[TrackedDetection] = []

        for track_id, detection_index in matches:
            detection = detections[detection_index]
            track = self.tracks[track_id]
            track.class_id = detection.class_id
            track.confidence = detection.confidence
            track.bbox = detection.bbox
            track.misses = 0
            matched_detection_indexes.add(detection_index)
            active_tracks.append(TrackedDetection(track_id, detection.class_id, detection.confidence, detection.bbox))

        unmatched_track_ids = set(self.tracks.keys()) - {track_id for track_id, _ in matches}
        for track_id in unmatched_track_ids:
            self.tracks[track_id].misses += 1

        for detection_index, detection in enumerate(detections):
            if detection_index in matched_detection_indexes:
                continue
            track_id = self.next_track_id
            self.next_track_id += 1
            self.tracks[track_id] = Track(track_id, detection.class_id, detection.confidence, detection.bbox)
            active_tracks.append(TrackedDetection(track_id, detection.class_id, detection.confidence, detection.bbox))

        stale_track_ids = [tid for tid, t in self.tracks.items() if t.misses > self.max_misses]
        for tid in stale_track_ids:
            del self.tracks[tid]

        return active_tracks

    def _match(self, detections: list[Detection]) -> list[tuple[int, int]]:
        candidates: list[tuple[float, int, int]] = []
        for track_id, track in self.tracks.items():
            for det_idx, det in enumerate(detections):
                if det.class_id != track.class_id:
                    continue
                iou = self._bbox_iou(track.bbox, det.bbox)
                c_score = self._center_score(track.bbox, det.bbox)
                score = max(iou, c_score)
                if score >= self.iou_threshold:
                    candidates.append((score, track_id, det_idx))

        candidates.sort(reverse=True, key=lambda x: x[0])
        used_tracks, used_dets = set(), set()
        matches = []
        for _, tid, det_idx in candidates:
            if tid in used_tracks or det_idx in used_dets:
                continue
            used_tracks.add(tid)
            used_dets.add(det_idx)
            matches.append((tid, det_idx))
        return matches

    @staticmethod
    def _bbox_iou(box_a, box_b):
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
        ia = iw * ih
        aa, ab = (ax2 - ax1) * (ay2 - ay1), (bx2 - bx1) * (by2 - by1)
        union = aa + ab - ia
        return ia / union if union > 0 else 0.0

    @staticmethod
    def _center_score(box_a, box_b):
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b
        acx, acy = (ax1 + ax2) / 2, (ay1 + ay2) / 2
        bcx, bcy = (bx1 + bx2) / 2, (by1 + by2) / 2
        dist = hypot(acx - bcx, acy - bcy)
        ref = max(ax2 - ax1, ay2 - ay1, bx2 - bx1, by2 - by1, 1.0)
        return max(0.0, 1.0 - (dist / (ref * 2.0)))

class LineCrossingCounter:
    """Sanal çizgi geçişi ile GIRIS/CIKIS tespiti yapar."""
    def __init__(self, *, session_id, line_orientation, line_position, min_consecutive, max_idle_frames, event_cooldown_frames):
        self.session_id = session_id
        self.line_orientation = line_orientation
        self.line_position = line_position
        self.min_consecutive = min_consecutive
        self.max_idle_frames = max_idle_frames
        self.event_cooldown_frames = event_cooldown_frames
        self.track_states: dict[int, TrackState] = {}

    def compute_side(self, cx, cy, width, height):
        if self.line_orientation == "horizontal":
            line_y = int(height * self.line_position)
            return 0 if cy < line_y else 1
        line_x = int(width * self.line_position)
        return 0 if cx < line_x else 1

    def register_detection(self, *, track_id, product_name, confidence, frame_index, side):
        if track_id not in self.track_states:
            self.track_states[track_id] = TrackState(product_name, side, None, 0, frame_index, confidence)
            return None

        state = self.track_states[track_id]
        state.last_frame_index, state.last_confidence, state.product_name = frame_index, confidence, product_name

        if side == state.confirmed_side:
            state.candidate_side, state.candidate_count = None, 0
            return None

        if state.candidate_side != side:
            state.candidate_side, state.candidate_count = side, 1
            return None

        state.candidate_count += 1
        if state.candidate_count < self.min_consecutive:
            return None
        if frame_index - state.last_event_frame < self.event_cooldown_frames:
            return None

        action = "GIRIS" if state.confirmed_side == 0 and side == 1 else "CIKIS"
        state.last_event_frame, state.confirmed_side, state.candidate_side, state.candidate_count = frame_index, side, None, 0
        
        return InventoryEvent(
            self.session_id, track_id, product_name, action,
            1 if action == "GIRIS" else -1, confidence, frame_index, utc_now_iso()
        )

    def prune_stale_tracks(self, frame_index, active_ids):
        stale_ids = [tid for tid, s in self.track_states.items() if frame_index - s.last_frame_index > self.max_idle_frames and tid not in active_ids]
        for tid in stale_ids:
            del self.track_states[tid]

class FridgeDetector:
    """YOLO modelini ve akışını yönetir."""
    def __init__(self, weights_path: str):
        path_obj = Path(weights_path)
        if path_obj.suffix == ".pt":
            import platform
            is_pi = "arm" in platform.machine().lower() or "aarch64" in platform.machine().lower()
            if not is_pi:
                onnx_path = path_obj.with_suffix(".onnx")
                if onnx_path.exists():
                    print(f"[MODEL] Otomatik .onnx modeli algılandı ve yüklendi: {onnx_path.name}")
                    weights_path = str(onnx_path)
        self.model = YOLO(weights_path)

    @property
    def class_names(self):
        return self.model.names

    def get_stream(self, source, config: VisionConfig):
        if config.tracker_mode == "bytetrack":
            return self.model.track(
                source=source, stream=True, persist=True, imgsz=config.imgsz,
                conf=config.conf, iou=config.iou, max_det=config.max_det,
                vid_stride=config.vid_stride, device=config.device,
                tracker=config.tracker, verbose=False
            )
        return self.model.predict(
            source=source, stream=True, imgsz=config.imgsz,
            conf=config.conf, iou=config.iou, max_det=config.max_det,
            vid_stride=config.vid_stride, device=config.device, 
            stream_buffer=False, verbose=False
        )

# --- 4. Ana Pipeline ---

class VisionPipeline:
    """Tüm bileşenleri birleştiren ana akış."""
    def __init__(self, config: VisionConfig):
        self.config = config
        self.config.validate()
        self._configure_runtime()
        self.detector = FridgeDetector(str(config.weights_path))
        self.visualize = config.show or config.save_video

    def _configure_runtime(self) -> None:
        """Donanım ve kütüphane seviyesinde optimizasyonlar."""
        cv2.setNumThreads(1)
        cv2.ocl.setUseOpenCL(False)
        try:
            import torch
            torch.set_num_threads(self.config.cpu_threads)
            if hasattr(torch, "set_num_interop_threads"):
                torch.set_num_interop_threads(1)
        except Exception:
            pass

    def run(self, source: int | str, output_dir: str | Path, frame_callback=None):
        session_id = build_session_id(str(source))
        started_at, started_perf = utc_now_iso(), time.perf_counter()
        
        # Her oturum için ayrı bir alt klasör oluştur
        output_path = Path(output_dir) / session_id
        output_path.mkdir(parents=True, exist_ok=True)

        counter = LineCrossingCounter(
            session_id=session_id, line_orientation=self.config.line_orientation,
            line_position=self.config.line_position, min_consecutive=self.config.min_consecutive,
            max_idle_frames=self.config.max_idle_frames, event_cooldown_frames=self.config.event_cooldown_frames
        )

        events, frame_index, video_writer = [], 0, None
        stream = self.detector.get_stream(source, self.config)
        tracker = SimpleTracker(self.config.tracker_iou_threshold, self.config.tracker_max_misses) if self.config.tracker_mode == "simple" else None

        try:
            for result in stream:
                try:
                    frame_index += 1
                    height, width = result.orig_shape
                    active_ids = set()
                    
                    tracked_objects = self._get_tracked(result, tracker)
                    for tracked in tracked_objects:
                        x1, y1, x2, y2 = tracked["bbox"]
                        side = counter.compute_side((x1+x2)/2, (y1+y2)/2, width, height)
                        p_name = self.detector.class_names.get(tracked["class_id"], str(tracked["class_id"]))
                        active_ids.add(tracked["track_id"])

                        event = counter.register_detection(
                            track_id=tracked["track_id"], product_name=p_name,
                            confidence=tracked["confidence"], frame_index=frame_index, side=side
                        )
                        if event:
                            e_dict = event.to_dict()
                            events.append(e_dict)
                            print(f"[EVENT] {e_dict['timestamp_utc']} - {e_dict['product_name']}: {e_dict['action']}")

                    counter.prune_stale_tracks(frame_index, active_ids)

                    if self.visualize or frame_callback:
                        frame = self._draw(result.orig_img.copy(), tracked_objects, len(events), width, height)
                        
                        if frame_callback:
                            should_continue = frame_callback(frame)
                            if should_continue is False:
                                break

                        if self.config.save_video:
                            if video_writer is None:
                                video_writer = cv2.VideoWriter(str(output_path/"annotated.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 20.0, (width, height))
                            video_writer.write(frame)
                        if self.config.show:
                            cv2.imshow("Vision Engine (Debug Mode)", frame)
                            if cv2.waitKey(1) & 0xFF == ord("q"): break
                except Exception as e:
                    print(f"[WARNING] Frame hatası: {e}"); break
        finally:
            if video_writer: video_writer.release()
            cv2.destroyAllWindows()

        return self._save_results(session_id, source, frame_index, events, started_at, started_perf, output_path)

    def _get_tracked(self, result, tracker):
        boxes = result.boxes
        if boxes is None: return []
        
        if self.config.tracker_mode == "bytetrack":
            if boxes.id is None: return []
            objs = [{"bbox": b.tolist(), "class_id": int(c), "track_id": int(i), "confidence": float(conf)}
                    for b, c, i, conf in zip(boxes.xyxy.cpu().numpy(), boxes.cls.cpu().numpy(), boxes.id.cpu().numpy(), boxes.conf.cpu().numpy())]
        else:
            dets = [Detection(int(c), float(conf), tuple(b.tolist()))
                    for b, c, conf in zip(boxes.xyxy.cpu().numpy(), boxes.cls.cpu().numpy(), boxes.conf.cpu().numpy())]
            dets = [d for d in dets if self.detector.class_names.get(d.class_id) not in self.config.ignored_class_names 
                    and d.confidence >= self.config.min_event_conf]
            tracked = tracker.update(dets) if tracker else []
            objs = [{"bbox": t.bbox, "class_id": t.class_id, "track_id": t.track_id, "confidence": t.confidence} for t in tracked]
            
        return [o for o in objs if self.detector.class_names.get(o["class_id"]) not in self.config.ignored_class_names 
                and o["confidence"] >= self.config.min_event_conf]

    def _draw(self, frame, tracked, count, w, h):
        # Çizgi çiz
        if self.config.line_orientation == "horizontal":
            y = int(h * self.config.line_position)
            cv2.line(frame, (0, y), (w, y), (0, 255, 255), 2)
        else:
            x = int(w * self.config.line_position)
            cv2.line(frame, (x, 0), (x, h), (0, 255, 255), 2)
        
        # Sayacı yaz
        cv2.putText(frame, f"Events: {count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (50, 255, 50), 2)
        
        # Kutuları çiz
        for t in tracked:
            x1, y1, x2, y2 = [int(v) for v in t["bbox"]]
            lbl = f"{self.detector.class_names.get(t['class_id'])} #{t['track_id']}"
            cv2.rectangle(frame, (x1, y1), (x2, y2), (40, 220, 40), 2)
            cv2.putText(frame, lbl, (x1, max(20, y1-8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 220, 40), 1)
        return frame

    def _save_results(self, sid, src, f_idx, evs, start_iso, start_perf, out_path):
        elapsed = max(0.001, time.perf_counter() - start_perf)
        summary = SessionSummary(sid, str(src), str(self.config.weights_path), f_idx, len(evs), str(out_path.resolve()), 
                                 start_iso, utc_now_iso(), round(elapsed, 4), round(f_idx/elapsed, 2),
                                 dict(Counter(e["action"] for e in evs)),
                                 dict(Counter(f"{e['product_name']}:{e['action']}" for e in evs)))
        
        (out_path/"events.json").write_text(json.dumps(evs, ensure_ascii=False, indent=2))
        (out_path/"summary.json").write_text(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
        (out_path/"config_used.json").write_text(json.dumps(self.config.to_dict(), ensure_ascii=False, indent=2))
        (out_path/"class_names.json").write_text(json.dumps(self.detector.class_names, ensure_ascii=False, indent=2))
        
        with (out_path/"events.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["session_id", "track_id", "product_name", "action", "quantity_delta", "confidence", "frame_index", "timestamp_utc"])
            w.writeheader(); w.writerows(evs)
            
        return {"session_id": sid, "total_events": len(evs), "total_frames": f_idx, "output_dir": str(out_path)}

# --- 5. CLI ve Main ---

def apply_profile(args):
    """Raspberry Pi 2GB RAM ve DJI Action 5 Pro gibi yüksek çözünürlüklü kameralar için optimizasyon."""
    if args.profile == "pi":
        # 2GB RAM için agresif optimizasyon
        args.imgsz = 320         # RAM kullanımını düşürmek için görsel boyutu küçültüldü
        args.vid_stride = 3      # Her 3 kareden birini işle (FPS kaybını önler)
        args.max_det = 15        # Bellek yükünü azaltmak için max tespit sayısı
        args.cpu_threads = 2     # Pi'nin aşırı ısınmasını ve kitlenmesini önler
        args.tracker_mode = "simple"
        args.tracker_iou_threshold = 0.20
        args.tracker_max_misses = 5
    elif args.profile == "quality":
        args.imgsz, args.vid_stride, args.max_det, args.cpu_threads = 640, 1, 30, 4

def main():
    parser = argparse.ArgumentParser(description="Vision Engine - Paket B")
    parser.add_argument("--source", default=None, help="Video kaynağı (0 veya URL)")
    parser.add_argument("--output-dir", default="output", help="Çıktı klasörü")
    parser.add_argument("--weights", default=None, help="Model (.pt) yolu")
    parser.add_argument("--profile", choices=["pi", "quality", "custom"], default="pi")
    parser.add_argument("--show", action="store_true", help="Debug Mode: Ekranda göster")
    args = parser.parse_args()

    apply_profile(args)
    src = args.source if args.source else VIDEO_SOURCE
    src = int(src) if str(src).isdigit() else src

    config = VisionConfig(show=args.show, imgsz=args.imgsz, vid_stride=args.vid_stride, tracker_mode=args.tracker_mode)
    if args.weights: config.weights_path = Path(args.weights)

    pipeline = VisionPipeline(config)
    res = pipeline.run(src, args.output_dir)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
