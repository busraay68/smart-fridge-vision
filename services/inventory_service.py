from collections import Counter
import db
from detection import predict_image, format_detections


def detect_and_update(filepath, image_name):
    """Resmi YOLO modeliyle analiz edip envanteri günceller."""
    detections, img = predict_image(filepath)

    counts = Counter(d['class'] for d in detections)

    # inventory update
    for class_name, count in counts.items():
        db.update_inventory(class_name, count, source="detection")

    # detection log
    for det in detections:
        db.insert_detection(image_name, det['class'], det['confidence'])

    return counts, img


def add_item(class_name, quantity):
    db.update_inventory(class_name, quantity, source="manual")


def remove_item(class_name, quantity):
    db.update_inventory(class_name, -quantity, source="manual")


def get_inventory():
    return db.get_inventory()


def get_logs():
    return db.get_logs()