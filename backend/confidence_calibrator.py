"""
confidence_calibrator.py
========================
Calibrates campaign similarity matching scores to a real-world probability range [0, 1]
using a dynamic sigmoid (Platt scaling) function.
"""

from __future__ import annotations
import math
import numpy as np

class ConfidenceCalibrator:
    """
    Sigmoid-based calibrator that maps raw fused cosine similarity scores to [0, 1].
    
    Dynamically scales such that:
      - Score at possible_threshold -> exactly 0.50 (50% confidence)
      - Score at strong_threshold -> exactly 0.85 (85% confidence)
    """

    @staticmethod
    def calibrate(
        score: float | np.ndarray,
        strong_threshold: float,
        possible_threshold: float,
        min_possible: float = 0.40
    ) -> float | np.ndarray:
        """
        Calibrate a score or list of scores based on current thresholds.
        
        Args:
            score: Raw fused score (or array of scores) in range [0, 1].
            strong_threshold: Campaign-specific strong match threshold.
            possible_threshold: Campaign-specific possible/uncertain threshold.
            min_possible: Minimum bound below which confidence decays rapidly to 0.
            
        Returns:
            Calibrated confidence probability in range [0.0, 1.0].
        """
        # Handle numpy arrays or scalars
        is_array = isinstance(score, np.ndarray)
        scores = np.array([score]) if not is_array else score
        
        # Guard against zero division or illogical thresholds
        if strong_threshold <= possible_threshold:
            strong_threshold = possible_threshold + 0.15

        # Solve Platt sigmoid parameters:
        # P(x) = 1 / (1 + exp(-k * (x - x0)))
        # 1. P(possible_threshold) = 0.50  =>  x0 = possible_threshold
        # 2. P(strong_threshold) = 0.85    =>  1 / (1 + exp(-k * (strong - possible))) = 0.85
        #    1 + exp(-k * diff) = 1.17647
        #    exp(-k * diff) = 0.17647
        #    -k * diff = ln(0.17647) = -1.7346
        #    k = 1.7346 / diff
        
        diff = strong_threshold - possible_threshold
        x0 = possible_threshold
        
        # Calculate optimal k to align with thresholds
        k = 1.7346 / max(0.01, diff)
        
        # Sigmoid formula
        calibrated = 1.0 / (1.0 + np.exp(-k * (scores - x0)))
        
        # If score is way below the dynamic min_possible threshold, force a sharp decay to zero
        # to suppress ambient matches or very poor visuals
        decay_mask = scores < min_possible
        if np.any(decay_mask):
            # Sigmoid is already small, but let's scale it down to 0 smoothly
            calibrated[decay_mask] = calibrated[decay_mask] * (scores[decay_mask] / min_possible) ** 2
            
        # Hard clamps to absolute [0, 1] range
        calibrated = np.clip(calibrated, 0.0, 1.0)
        
        return calibrated if is_array else float(calibrated[0])

