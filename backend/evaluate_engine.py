"""
evaluate_engine.py
==================
Robustness Evaluation and Benchmark Suite.

Evaluates the SigLIP Campaign Matching Engine under simulated real-world conditions
including motion blur, low light, competitor distractors, cropping, and noisy frames.
Calculates Precision, Recall, FPR, and FNR to validate production readiness.
"""

import os
import shutil
import time
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageDraw

from siglip_engine import SigLIPEngine, ReferenceBank, CampaignMatcher
from hard_negative_engine import HardNegativeBank

EVAL_DIR = os.path.join(os.path.dirname(__file__), "eval_siglip_sandbox")

def create_base_image(color, draw_pattern=None, size=(300, 300)) -> Image.Image:
    """Create a high-quality base image with geometric shapes for robust vision matching."""
    arr = np.ones((size[1], size[0], 3), dtype=np.uint8) * np.array(color, dtype=np.uint8)
    # Inject baseline noise for texture
    noise = np.random.randint(0, 30, (size[1], size[0], 3), dtype=np.uint8)
    arr = np.clip(arr + noise, 0, 255)
    img = Image.fromarray(arr, "RGB")
    
    if draw_pattern:
        draw = ImageDraw.Draw(img)
        if draw_pattern == "blue_logo":
            draw.rectangle([50, 50, 250, 250], fill=(0, 0, 200))
            draw.ellipse([100, 100, 200, 200], fill=(255, 255, 255))
        elif draw_pattern == "red_logo":
            draw.polygon([(150, 50), (250, 250), (50, 250)], fill=(200, 0, 0))
        elif draw_pattern == "green_logo":
            draw.ellipse([50, 50, 250, 250], fill=(0, 180, 0))
            draw.rectangle([100, 100, 200, 200], fill=(255, 255, 255))
    return img

def apply_distortion(img: Image.Image, distortion_type: str) -> Image.Image:
    """Simulate realistic real-world visual degradation."""
    if distortion_type == "blurry":
        # Simulate heavy motion blur or out-of-focus capture
        return img.filter(ImageFilter.GaussianBlur(radius=6))
    elif distortion_type == "low_light":
        # Simulate dark, indoor, or night influencer shots (brightness down to 30%)
        enhancer = ImageEnhance.Brightness(img)
        dark_img = enhancer.enhance(0.30)
        # Add high-ISO sensor grain
        arr = np.array(dark_img, dtype=np.int16)
        grain = np.random.normal(0, 20, arr.shape).astype(np.int16)
        arr = np.clip(arr + grain, 0, 255).astype(np.uint8)
        return Image.fromarray(arr)
    elif distortion_type == "motion_blur":
        # Simulates lateral motion blur
        return img.filter(ImageFilter.BoxBlur((8, 1)))
    elif distortion_type == "cropped":
        # Simulate partial product visibility or extreme zoomed logos (50% crop)
        w, h = img.size
        cropped = img.crop((w // 4, h // 4, 3 * w // 4, 3 * h // 4))
        return cropped.resize((w, h), Image.Resampling.LANCZOS)
    elif distortion_type == "meme_edit":
        # High contrast + meme text/border overlay
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, img.width, 30], fill=(255, 255, 255))
        draw.rectangle([0, img.height - 30, img.width, img.height], fill=(255, 255, 255))
        return img
    return img

def setup_eval_environment():
    """Build evaluation campaign structure: positives, negatives, distractors."""
    if os.path.exists(EVAL_DIR):
        shutil.rmtree(EVAL_DIR)
    os.makedirs(EVAL_DIR)

    campaign_dir = os.path.join(EVAL_DIR, "starbucks_campaign")
    pos_dir = os.path.join(campaign_dir, "positive_refs")
    neg_dir = os.path.join(campaign_dir, "hard_negatives")
    
    os.makedirs(pos_dir)
    os.makedirs(neg_dir)

    # 1. POSITIVES (Starbucks Green/White themes)
    create_base_image((0, 100, 60), "green_logo").save(os.path.join(pos_dir, "starbucks_ref_1.png"))
    create_base_image((10, 110, 70), "green_logo").save(os.path.join(pos_dir, "starbucks_ref_2.png"))
    create_base_image((0, 80, 50), "green_logo").save(os.path.join(pos_dir, "starbucks_ref_3.png"))

    # 2. HARD NEGATIVES (Costa Cafe Red/Brown, Dunkin Purple/Orange)
    create_base_image((150, 0, 30), "red_logo").save(os.path.join(neg_dir, "costa_competitor.png"))
    create_base_image((255, 128, 0), "blue_logo").save(os.path.join(neg_dir, "dunkin_competitor.png"))

    # 3. TEST CASES (Positive Targets under Distortions)
    test_pos_dir = os.path.join(EVAL_DIR, "targets_positive")
    os.makedirs(test_pos_dir)
    
    base_pos = create_base_image((5, 95, 65), "green_logo")
    base_pos.save(os.path.join(test_pos_dir, "clean_pos.png"))
    apply_distortion(base_pos, "blurry").save(os.path.join(test_pos_dir, "blurry_pos.png"))
    apply_distortion(base_pos, "low_light").save(os.path.join(test_pos_dir, "low_light_pos.png"))
    apply_distortion(base_pos, "motion_blur").save(os.path.join(test_pos_dir, "motion_blur_pos.png"))
    apply_distortion(base_pos, "cropped").save(os.path.join(test_pos_dir, "cropped_pos.png"))
    apply_distortion(base_pos, "meme_edit").save(os.path.join(test_pos_dir, "meme_pos.png"))

    # 4. TEST CASES (Negative Targets / Competitors / Random noise)
    test_neg_dir = os.path.join(EVAL_DIR, "targets_negative")
    os.makedirs(test_neg_dir)

    # Competitor Costa clean and degraded
    base_neg_costa = create_base_image((160, 10, 40), "red_logo")
    base_neg_costa.save(os.path.join(test_neg_dir, "costa_clean.png"))
    apply_distortion(base_neg_costa, "blurry").save(os.path.join(test_neg_dir, "costa_blurry.png"))
    
    # Random generic non-campaign images
    create_base_image((128, 128, 128)).save(os.path.join(test_neg_dir, "generic_grey.png"))
    create_base_image((0, 0, 255), "blue_logo").save(os.path.join(test_neg_dir, "generic_blue.png"))

    return pos_dir, neg_dir, test_pos_dir, test_neg_dir

def run_evaluation():
    print("======================================================================")
    print("          STARTING SIGLIP ENGINE EVALUATION & BENCHMARK                ")
    print("======================================================================")
    
    pos_dir, neg_dir, test_pos, test_neg = setup_eval_environment()

    try:
        # Load banks
        pos_bank = ReferenceBank()
        pos_bank.build(pos_dir, force_rebuild=True)

        neg_bank = HardNegativeBank()
        neg_bank.build(neg_dir, force_rebuild=True)

        matcher = CampaignMatcher()
        pos_bank.hard_negative_bank = neg_bank
        
        # We need to manually inject competitor evaluations. 
        # We will modify `siglip_engine.py` shortly to support this natively,
        # but let's test evaluation flow by loading them.
        
        print("\nEvaluating POSITIVE test cases (Expected Match: True)...")
        pos_results = []
        for filename in os.listdir(test_pos):
            path = os.path.join(test_pos, filename)
            
            res = matcher.match_image(path, pos_bank)
            pos_results.append({
                "filename": filename,
                "score": res.score,
                "match": res.campaign_match,
                "match_type": res.match_type,
                "comp_sim": res.competitor_similarity,
                "margin": res.competitor_margin,
            })
            print(f"  [POS] {filename:<18} -> Score: {res.score:.3f} | Match: {res.campaign_match} ({res.match_type}) | CompSim: {res.competitor_similarity:.3f} | Margin: {res.competitor_margin:.3f}")

        print("\nEvaluating NEGATIVE/COMPETITOR test cases (Expected Match: False)...")
        neg_results = []
        for filename in os.listdir(test_neg):
            path = os.path.join(test_neg, filename)
            
            res = matcher.match_image(path, pos_bank)
            neg_results.append({
                "filename": filename,
                "score": res.score,
                "match": res.campaign_match,
                "match_type": res.match_type,
                "comp_sim": res.competitor_similarity,
                "margin": res.competitor_margin,
            })
            print(f"  [NEG] {filename:<18} -> Score: {res.score:.3f} | Match: {res.campaign_match} ({res.match_type}) | CompSim: {res.competitor_similarity:.3f} | Margin: {res.competitor_margin:.3f}")

        # Metrics calculation
        tp = sum(1 for r in pos_results if r["match"])
        fn = sum(1 for r in pos_results if not r["match"])
        fp = sum(1 for r in neg_results if r["match"])
        tn = sum(1 for r in neg_results if not r["match"])

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        fnr = fn / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        print("\n======================================================================")
        print("                        EVALUATION REPORT                             ")
        print("======================================================================")
        print(f"  True Positives  (TP): {tp:<4} | False Negatives (FN): {fn}")
        print(f"  False Positives (FP): {fp:<4} | True Negatives  (TN): {tn}")
        print("  ------------------------------------------------------------------")
        print(f"  Precision:            {precision:.4f} (Ability to suppress negatives)")
        print(f"  Recall:               {recall:.4f} (Robustness under noise/blur)")
        print(f"  F1-Score:             {f1:.4f}")
        print(f"  False Positive Rate:  {fpr:.4f}")
        print(f"  False Negative Rate:  {fnr:.4f}")
        print("======================================================================")

        assert precision >= 0.80, "Precision is too low (competitor rejection failed)"
        assert recall >= 0.80, "Recall is too low (robust matching under noise failed)"
        print("  [BENCHMARK] Robustness metrics exceed target criteria (>80%).")
        print("======================================================================")

    finally:
        if os.path.exists(EVAL_DIR):
            try:
                shutil.rmtree(EVAL_DIR)
                print("[Evaluation] Cleanup completed successfully.")
            except Exception as e:
                print(f"[Evaluation] Cleanup warning: {e}")

if __name__ == "__main__":
    run_evaluation()
