import cv2
import os
import glob
import math

def extract_frames(video_path, output_folder="temp_frames", max_frames=6):
    """
    Smart frame sampling: extracts exactly `max_frames` frames.
    Always includes the very first and last valid frames (intros/outros).
    The remaining frames are sampled evenly from the video's duration.
    """
    os.makedirs(output_folder, exist_ok=True)
    
    # Clean up old frames first
    for f in glob.glob(os.path.join(output_folder, "*.jpg")):
        try:
            os.remove(f)
        except Exception:
            pass

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    if total_frames <= 0:
        cap.release()
        return []

    # Determine which frame indices to extract
    if total_frames <= max_frames:
        indices_to_extract = list(range(total_frames))
    else:
        # Always get first and last frame
        indices_to_extract = [0]
        
        # Sample the remaining ones evenly
        remaining = max_frames - 2
        if remaining > 0:
            step = (total_frames - 1) / (remaining + 1)
            for i in range(1, remaining + 1):
                indices_to_extract.append(int(math.floor(step * i)))
                
        indices_to_extract.append(total_frames - 1)
        
    # Deduplicate and sort
    indices_to_extract = sorted(list(set(indices_to_extract)))

    frames = []
    idx_to_grab_pos = 0
    current_frame_idx = 0

    while cap.isOpened() and idx_to_grab_pos < len(indices_to_extract):
        target_idx = indices_to_extract[idx_to_grab_pos]
        
        # Fast-forward to the target frame
        if current_frame_idx < target_idx:
            # For large jumps, set(cv2.CAP_PROP_POS_FRAMES) is faster than cap.read()
            # but can be inaccurate on some codecs. For small jumps, reading is better.
            jump = target_idx - current_frame_idx
            if jump > fps:
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
                current_frame_idx = target_idx
            else:
                for _ in range(jump):
                    cap.grab()
                    current_frame_idx += 1
                    
        ret, frame = cap.read()
        if not ret:
            break

        path = os.path.join(output_folder, f"frame_{target_idx}.jpg")
        cv2.imwrite(path, frame)
        frames.append(path)
        
        current_frame_idx += 1
        idx_to_grab_pos += 1

    cap.release()
    return frames
