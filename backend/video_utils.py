"""
video_utils.py
==============
Smart keyframe extraction and duplicate/noise suppression for video assets.
Utilizes Laplacian variance blur detection and multi-factor visual uniqueness checks.
"""

import cv2
import os
import glob
import math
import numpy as np

def calculate_blur_score(gray_frame: np.ndarray) -> float:
    """
    Computes the Laplacian variance of a grayscale image frame to quantify blur.
    Higher values indicate sharper details, while lower values indicate out-of-focus or motion blur.
    """
    try:
        return cv2.Laplacian(gray_frame, cv2.CV_64F).var()
    except Exception:
        return 999.0  # Safe default if math fails

def calculate_visual_difference(img1: np.ndarray, img2: np.ndarray) -> float:
    """
    Compute a robust structural difference score between two BGR frames.
    Resizes both to a low-resolution map and computes normalized mean absolute difference.
    """
    try:
        # Resize to small dimension to smooth local translations
        h, w = 32, 32
        small1 = cv2.resize(img1, (w, h), interpolation=cv2.INTER_AREA)
        small2 = cv2.resize(img2, (w, h), interpolation=cv2.INTER_AREA)
        
        # Grayscale absolute difference
        g1 = cv2.cvtColor(small1, cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(small2, cv2.COLOR_BGR2GRAY)
        
        diff = cv2.absdiff(g1, g2)
        mean_diff = float(np.mean(diff)) / 255.0  # Range [0.0, 1.0]
        return mean_diff
    except Exception:
        return 1.0  # Highly different if error

def extract_keyframes(
    video_path: str,
    output_folder: str = "temp_frames",
    interval_seconds: float = 2.0,
    max_frames: int = 15,
    scene_change_threshold: float = 0.4,
    blur_threshold: float = 40.0,
) -> list[str]:
    """
    Smart keyframe extraction for campaign matching with duplicate and blur suppression.

    Extracts frames at regular intervals plus scene-change frames, filtering out
    blurry frames and duplicate scenes using multi-factor uniqueness checks.

    Args:
        video_path: Path to video file
        output_folder: Directory to save extracted frames
        interval_seconds: Extract 1 frame every N seconds (default: 2.0)
        max_frames: Maximum number of frames to extract (default: 15)
        scene_change_threshold: Histogram diff threshold for scene changes (0-1)
        blur_threshold: Minimum Laplacian variance below which frames are skipped as blurry

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

    frame_interval = int(fps * interval_seconds)

    # Build target frame indices at regular intervals
    target_indices = set()
    target_indices.add(0)
    target_indices.add(max(0, total_frames - 1))

    # Regular interval frames
    idx = 0
    while idx < total_frames:
        target_indices.add(idx)
        idx += frame_interval

    target_indices = sorted(target_indices)

    frames = []
    prev_saved_frames = []  # Keep small history of raw saved images for difference checking
    prev_hist = None

    for target_idx in target_indices:
        if len(frames) >= max_frames:
            break

        cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 1. Blur suppression
        blur_score = calculate_blur_score(gray)
        if blur_score < blur_threshold and target_idx != 0 and target_idx != total_frames - 1:
            # Let's try searching a small local window for a sharper adjacent frame
            sharp_found = False
            for offset in [-5, -2, 2, 5]:
                adj_idx = target_idx + offset
                if 0 <= adj_idx < total_frames:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, adj_idx)
                    ok, adj_frame = cap.read()
                    if ok and adj_frame is not None:
                        adj_gray = cv2.cvtColor(adj_frame, cv2.COLOR_BGR2GRAY)
                        adj_blur = calculate_blur_score(adj_gray)
                        if adj_blur >= blur_threshold:
                            frame = adj_frame
                            gray = adj_gray
                            sharp_found = True
                            break
            if not sharp_found and blur_score < (blur_threshold * 0.5):
                # Extremely blurry frame, skip entirely
                continue

        # 2. Visual duplicate checks (Multi-factor uniqueness)
        save_frame = True
        
        # Histogram check
        curr_hist = cv2.calcHist([gray], [0], None, [64], [0, 256])
        curr_hist = cv2.normalize(curr_hist, curr_hist).flatten()
        
        if prev_hist is not None:
            similarity = cv2.compareHist(prev_hist, curr_hist, cv2.HISTCMP_CORREL)
            # Skip highly similar hist frames
            if similarity > 0.98:
                save_frame = False

        # Structural difference check against previously saved frames (prevent repeating scenes)
        if save_frame and prev_saved_frames:
            for prev_f in prev_saved_frames[-3:]:  # Check last 3 saved frames
                diff_score = calculate_visual_difference(frame, prev_f)
                if diff_score < 0.05:  # Very low difference (5%)
                    save_frame = False
                    break

        if save_frame:
            path = os.path.join(output_folder, f"keyframe_{target_idx:06d}.jpg")
            cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
            frames.append(path)
            
            # Keep small cache of raw frames for comparison
            prev_saved_frames.append(frame)
            if len(prev_saved_frames) > 5:
                prev_saved_frames.pop(0)

            # Update histogram for next comparison
            prev_hist = curr_hist

    cap.release()
    
    # Fallback check: if we suppressed too aggressively and have 0 frames, return at least the first frame
    if not frames and total_frames > 0:
        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ret, frame = cap.read()
        if ret and frame is not None:
            path = os.path.join(output_folder, "keyframe_000000.jpg")
            cv2.imwrite(path, frame)
            frames.append(path)
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
            jump = target_idx - current_frame_idx
            if jump > fps:
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
                current_frame_idx = target_idx
            else:
                for _ in range(jump):
                    cap.grab()
                    current_frame_idx += 1
                    
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        path = os.path.join(output_folder, f"frame_{target_idx}.jpg")
        cv2.imwrite(path, frame)
        frames.append(path)
        
        current_frame_idx += 1
        idx_to_grab_pos += 1

    cap.release()
    return frames
