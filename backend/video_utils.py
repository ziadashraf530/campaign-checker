import cv2
import os

def extract_frames(video_path, output_folder="temp_frames", interval=1):
    os.makedirs(output_folder, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = int(fps * interval)

    frames = []
    count = 0
    idx = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if count % frame_interval == 0:
            path = os.path.join(output_folder, f"frame_{idx}.jpg")
            cv2.imwrite(path, frame)
            frames.append(path)
            idx += 1

        count += 1

    cap.release()
    return frames
