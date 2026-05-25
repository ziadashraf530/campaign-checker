"""
temporal_engine.py
==================
Temporal consistency, spike suppression, and rolling confidence logic for video assets.

Ensures that campaign match verdicts on videos rely on sustained visual presence
rather than isolated frames triggering false-positive spikes.
"""

from __future__ import annotations
import numpy as np

class TemporalConsistencyEngine:
    """
    Applies smoothing and temporal validation to sequence predictions.
    """

    def __init__(self, window_size: int = 5, match_threshold: float = 0.70):
        self.window_size = window_size
        self.match_threshold = match_threshold

    def smooth_scores(self, scores: list[float] | np.ndarray) -> np.ndarray:
        """
        Applies a rolling weighted Gaussian-like filter to frame-level scores.
        """
        scores = np.array(scores, dtype=float)
        if len(scores) < 3:
            return scores  # Too short for robust smoothing

        smoothed = np.copy(scores)
        n = len(scores)
        w = self.window_size
        
        # Simple weighted window: [0.1, 0.2, 0.4, 0.2, 0.1] for size 5
        if w == 5:
            kernel = np.array([0.1, 0.2, 0.4, 0.2, 0.1])
        else:
            # Generate generic binomial-like symmetric kernel
            kernel = np.bartlett(w)
            kernel = kernel / kernel.sum()

        half_w = len(kernel) // 2

        for i in range(n):
            # Compute bounds for active window
            start = max(0, i - half_w)
            end = min(n, i + half_w + 1)
            
            # Extract active slice and kernel slice
            k_start = half_w - (i - start)
            k_end = k_start + (end - start)
            
            active_kernel = kernel[k_start:k_end]
            active_kernel = active_kernel / active_kernel.sum() # Re-normalize
            
            smoothed[i] = np.dot(scores[start:end], active_kernel)

        return smoothed

    def suppress_spikes(
        self,
        scores: list[float] | np.ndarray,
        margin: float = 0.18
    ) -> np.ndarray:
        """
        Suppresses isolated single-frame visual spikes that represent brief false alarms (e.g. flashes, brief brand overlap).
        If a frame score is significantly higher than both neighbors, it is heavily suppressed.
        """
        scores = np.array(scores, dtype=float)
        if len(scores) < 3:
            return scores

        suppressed = np.copy(scores)
        for i in range(1, len(scores) - 1):
            left_diff = scores[i] - scores[i - 1]
            right_diff = scores[i] - scores[i + 1]

            # If the current score spikes high compared to both immediate neighbors
            if left_diff > margin and right_diff > margin:
                # Suppress to the average of neighbors (prunes isolated flashes)
                neighbor_avg = (scores[i - 1] + scores[i + 1]) / 2.0
                suppressed[i] = neighbor_avg + 0.05 * (scores[i] - neighbor_avg)

        # Handle boundaries (edges) if they spike heavily compared to their sole neighbor
        if len(scores) >= 3:
            if scores[0] - scores[1] > margin * 1.5:
                suppressed[0] = scores[1] + 0.05 * (scores[0] - scores[1])
            if scores[-1] - scores[-2] > margin * 1.5:
                suppressed[-1] = scores[-2] + 0.05 * (scores[-1] - scores[-2])

        return suppressed

    def calculate_continuity(self, scores: list[float] | np.ndarray) -> dict:
        """
        Calculates frame sequence continuity parameters.
        Returns:
            longest_streak: absolute number of consecutive matched frames
            streak_ratio: ratio of longest streak to total video frames
            frame_continuity_score: weighted rating of streak coherence
        """
        scores = np.array(scores, dtype=float)
        n = len(scores)
        if n == 0:
            return {"longest_streak": 0, "streak_ratio": 0.0, "frame_continuity_score": 0.0}

        matches = scores >= self.match_threshold
        
        longest_streak = 0
        current_streak = 0
        total_streaks = []

        for is_match in matches:
            if is_match:
                current_streak += 1
                longest_streak = max(longest_streak, current_streak)
            else:
                if current_streak > 0:
                    total_streaks.append(current_streak)
                current_streak = 0
        if current_streak > 0:
            total_streaks.append(current_streak)

        streak_ratio = longest_streak / n

        # Frame continuity score is derived from streak lengths and their proportion
        # Long coherent streaks are favored over fragmented single frame hits
        if longest_streak > 0:
            frame_continuity_score = 0.6 * min(1.0, longest_streak / 4.0) + 0.4 * streak_ratio
        else:
            frame_continuity_score = 0.0

        return {
            "longest_streak": longest_streak,
            "streak_ratio": round(float(streak_ratio), 4),
            "frame_continuity_score": round(float(frame_continuity_score), 4),
        }

    def find_stable_segments(self, scores: list[float] | np.ndarray) -> list[dict]:
        """
        Identify consecutive index ranges where matching scores are sustained
        above the target threshold, indicating continuous product visual presence.
        
        Returns:
            List of dicts representing matching segments.
        """
        scores = np.array(scores, dtype=float)
        n = len(scores)
        segments = []
        
        if n == 0:
            return segments
            
        in_segment = False
        start_idx = -1
        
        for idx in range(n):
            is_match = scores[idx] >= self.match_threshold
            
            if is_match and not in_segment:
                in_segment = True
                start_idx = idx
            elif not is_match and in_segment:
                in_segment = False
                end_idx = idx - 1
                avg_score = float(np.mean(scores[start_idx:end_idx + 1]))
                segments.append({
                    "start_frame": start_idx,
                    "end_frame": end_idx,
                    "duration_frames": end_idx - start_idx + 1,
                    "average_score": round(avg_score, 4)
                })
                
        # Handle trailing segment
        if in_segment:
            end_idx = n - 1
            avg_score = float(np.mean(scores[start_idx:end_idx + 1]))
            segments.append({
                "start_frame": start_idx,
                "end_frame": end_idx,
                "duration_frames": end_idx - start_idx + 1,
                "average_score": round(avg_score, 4)
            })
            
        return segments

    def process_sequence(self, raw_scores: list[float]) -> dict:
        """
        Full temporal pipeline:
        1. Rolling smoothing
        2. Continuity evaluation
        3. Stable segment extraction
        4. Temporal strength calculation
        """
        if not raw_scores:
            return {
                "raw_scores": [],
                "smoothed_scores": [],
                "temporal_strength": 0.0,
                "frame_continuity_score": 0.0,
                "longest_streak": 0,
                "streak_ratio": 0.0,
                "stable_segments": [],
            }

        raw = np.array(raw_scores, dtype=float)
        
        # 1. Smooth curves
        smoothed = self.smooth_scores(raw)

        # 2. Calculate sequence continuity stats
        continuity = self.calculate_continuity(smoothed)
        
        # 3. Extract stable segments
        stable_segs = self.find_stable_segments(smoothed)

        # 4. Temporal Strength
        # Combines the mean of the top 3 smoothed frame scores with continuity weight
        sorted_smoothed = np.sort(smoothed)[::-1]
        top_k_frames = max(1, min(3, len(sorted_smoothed)))
        top_smoothed_mean = sorted_smoothed[:top_k_frames].mean()

        # Final temporal strength merges peak smoothed scores with continuity
        continuity_factor = continuity["frame_continuity_score"]
        temporal_strength = 0.8 * top_smoothed_mean + 0.2 * continuity_factor
        temporal_strength = min(1.0, max(0.0, temporal_strength))

        return {
            "raw_scores": [round(float(s), 4) for s in raw],
            "smoothed_scores": [round(float(s), 4) for s in smoothed],
            "temporal_strength": round(float(temporal_strength), 4),
            "frame_continuity_score": continuity["frame_continuity_score"],
            "longest_streak": continuity["longest_streak"],
            "streak_ratio": continuity["streak_ratio"],
            "stable_segments": stable_segs,
        }
