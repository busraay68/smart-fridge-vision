import cv2
import os
import numpy as np

# --- Frame fark hesaplama ---
def frame_fark(img1, img2):
    g1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(g1, g2)
    return np.mean(diff)

# --- Video işleme ---
video_path = "data/videos/video3.mp4"
output_folder = "data/videos/video3"

os.makedirs(output_folder, exist_ok=True)

cap = cv2.VideoCapture(video_path)

prev_frame = None
count = 0
frame_id = 0

# AYARLAR
frame_aralik = 15     # her 15 framede kontrol
fark_esik = 25       # fark threshold

while True:
    ret, frame = cap.read()
    if not ret:
        break

    if frame_id % frame_aralik == 0:
        if prev_frame is None:
            cv2.imwrite(f"{output_folder}/frame_{count}.jpg", frame)
            prev_frame = frame
            count += 1
        else:
            fark = frame_fark(prev_frame, frame)

            if fark > fark_esik:
                cv2.imwrite(f"{output_folder}/frame_{count}.jpg", frame)
                prev_frame = frame
                count += 1

    frame_id += 1

cap.release()

print(f"Toplam kaydedilen foto: {count}")