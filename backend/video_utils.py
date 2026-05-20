import cv2
import os
import glob
import math
import numpy as np


def extract_keyframes(
    video_path: str,
    output_folder: str = "temp_frames",
    interval_seconds: float = 2.0,
    max_frames: int = 15,
    scene_change_threshold: float = 0.4,
) -> list[str]:
    """
    Smart keyframe extraction for campaign matching.

    Extracts frames at regular intervals plus scene-change frames.
    Designed for visual campaign verification where diverse keyframes
    improve matching accuracy.

    Args:
        video_path: Path to video file
        output_folder: Directory to save extracted frames
        interval_seconds: Extract 1 frame every N seconds (default: 2.0)
        max_frames: Maximum number of frames to extract (default: 15)
        scene_change_threshold: Histogram diff threshold for scene changes (0-1)

    Returns:
        List of file paths to extracted keyframe images
    """
    os.makedirs(output_folder, exist_ok=True)

    # Clean up old keyframes
    for f in glob.glob(os.path.join(output_folder, "keyframe_*.jpg")):
        try:
            os.remove(f)
        except Exception:
            pass

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    if total_frames <= 0 or fps <= 0:
        cap.release()
        return []

    duration = total_frames / fps
    frame_interval = int(fps * interval_seconds)

    # Build target frame indices at regular intervals
    target_indices = set()
    # Always include first and last frame
    target_indices.add(0)
    target_indices.add(max(0, total_frames - 1))

    # Regular interval frames
    idx = 0
    while idx < total_frames:
        target_indices.add(idx)
        idx += frame_interval

    target_indices = sorted(target_indices)

    # Extract frames and optionally detect scene changes
    frames = []
    prev_hist = None

    for target_idx in target_indices:
        if len(frames) >= max_frames:
            break

        cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
        ret, frame = cap.read()
        if not ret:
            continue

        # Scene change detection via histogram comparison
        save_frame = True
        if prev_hist is not None and len(frames) > 2:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            curr_hist = cv2.calcHist([gray], [0], None, [64], [0, 256])
            curr_hist = cv2.normalize(curr_hist, curr_hist).flatten()
            similarity = cv2.compareHist(prev_hist, curr_hist, cv2.HISTCMP_CORREL)
            # Skip near-duplicate frames (very similar histogram)
            if similarity > 0.98:
                save_frame = False

        if save_frame:
            path = os.path.join(output_folder, f"keyframe_{target_idx:06d}.jpg")
            cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
            frames.append(path)

            # Update histogram for next comparison
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            prev_hist = cv2.calcHist([gray], [0], None, [64], [0, 256])
            prev_hist = cv2.normalize(prev_hist, prev_hist).flatten()

    cap.release()
    return frames


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
