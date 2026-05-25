"""
final_validation.py
===================
Quick final validation checks for Campaign Checker.

Usage:
  python final_validation.py
  python final_validation.py --pytest
  python final_validation.py --verify
  python final_validation.py --evaluate
  python final_validation.py --all
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from ocr_caption_engine import OcrCaptionEngine
from policy_engine import DecisionPolicy

ROOT_DIR = Path(__file__).resolve().parent


def _run_smoke_checks() -> list[str]:
    errors: list[str] = []

    # Decision policy: competitor conflict must stay in review
    tier, review_status = DecisionPolicy.assign_review_tier(
        confidence_pct=78,
        match_type="STRONG_MATCH",
        visual_signal={
            "logo_strength": 0.9,
            "product_focus": 0.85,
            "social_media_confidence": 0.8,
        },
        competitor_similarity=0.7,
        competitor_margin=0.05,
        competitor_review=False,
    )
    if tier != "REVIEW_REQUIRED" or review_status != "REVIEW":
        errors.append("DecisionPolicy conflict gating failed (expected REVIEW_REQUIRED/REVIEW).")

    # Decision policy: strong match should approve when no conflict
    tier, review_status = DecisionPolicy.assign_review_tier(
        confidence_pct=88,
        match_type="STRONG_MATCH",
        visual_signal={
            "logo_strength": 0.9,
            "product_focus": 0.85,
            "social_media_confidence": 0.8,
        },
        competitor_similarity=0.2,
        competitor_margin=0.2,
        competitor_review=False,
    )
    if tier != "VERIFIED_MATCH" or review_status != "APPROVED":
        errors.append("DecisionPolicy approval gating failed (expected VERIFIED_MATCH/APPROVED).")

    # OCR UI noise detection
    if not OcrCaptionEngine._is_ui_noise("1.2M"):
        errors.append("UI noise detection failed for 1.2M.")
    if not OcrCaptionEngine._is_ui_noise("١٫٢م"):
        errors.append("UI noise detection failed for Arabic-Indic ١٫٢م.")

    # OCR ignore-region filtering
    ignore_regions = [{"label": "right_ui", "box": [0.8, 0.0, 1.0, 1.0]}]
    if not OcrCaptionEngine._is_ignored_box([0.85, 0.2, 0.95, 0.3], ignore_regions):
        errors.append("Ignore-region filter failed to catch right_ui.")
    if OcrCaptionEngine._is_ignored_box([0.2, 0.2, 0.3, 0.3], ignore_regions):
        errors.append("Ignore-region filter incorrectly flagged a safe box.")

    # Region presets sanity check
    regions = OcrCaptionEngine._get_regions("tiktok")
    if not regions.get("include") or "ignore" not in regions:
        errors.append("Region presets missing include/ignore zones for tiktok.")

    return errors


def _run_command(args: list[str], label: str) -> bool:
    start = time.time()
    print(f"\n==> {label}")
    result = subprocess.run(args, cwd=ROOT_DIR, text=True, capture_output=True)
    duration = time.time() - start
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    if result.returncode != 0:
        print(f"{label} failed in {duration:.1f}s")
        return False
    print(f"{label} completed in {duration:.1f}s")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Final validation checks for Campaign Checker")
    parser.add_argument("--pytest", action="store_true", help="Run backend pytest suite")
    parser.add_argument("--verify", action="store_true", help="Run verify_siglip_engine.py")
    parser.add_argument("--evaluate", action="store_true", help="Run evaluate_engine.py")
    parser.add_argument("--all", action="store_true", help="Run smoke checks + pytest + verify + evaluate")
    parser.add_argument("--skip-smoke", action="store_true", help="Skip smoke checks")
    args = parser.parse_args()

    if args.all:
        args.pytest = True
        args.verify = True
        args.evaluate = True

    if not args.skip_smoke:
        print("Running smoke checks...")
        errors = _run_smoke_checks()
        if errors:
            print("\nSmoke checks failed:")
            for err in errors:
                print(f"- {err}")
            return 1
        print("Smoke checks passed.")

    if args.pytest:
        if not _run_command([sys.executable, "-m", "pytest"], "Pytest"):
            return 1

    if args.verify:
        if not _run_command([sys.executable, "verify_siglip_engine.py"], "SigLIP verification"):
            return 1

    if args.evaluate:
        if not _run_command([sys.executable, "evaluate_engine.py"], "Robustness evaluation"):
            return 1

    print("\nFinal validation completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
