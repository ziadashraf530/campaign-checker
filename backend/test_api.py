import os
import requests
from PIL import Image
import numpy as np

# Define sandbox directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SANDBOX_DIR = os.path.join(BASE_DIR, "test_api_sandbox")
REF_DIR = os.path.join(SANDBOX_DIR, "campaign_blue_refs")
TARGET_DIR = os.path.join(SANDBOX_DIR, "targets")

def create_color_image(color, path, size=(300, 300)):
    """Generate an image with distinct geometric features for visual campaign matching."""
    arr = np.ones((size[1], size[0], 3), dtype=np.uint8) * np.array(color, dtype=np.uint8)
    # Add random noise
    noise = np.random.randint(0, 100, (size[1], size[0], 3), dtype=np.uint8)
    arr = np.clip(arr + noise, 0, 255)
    
    img = Image.fromarray(arr, "RGB")
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    # Draw a distinct pattern based on color
    if color[2] > color[0]: # Blue-ish
        draw.rectangle([50, 50, 250, 250], fill=(0, 0, 200))
        draw.ellipse([100, 100, 200, 200], fill=(255, 255, 255))
    elif color[0] > color[2]: # Red-ish
        draw.polygon([(150, 50), (250, 250), (50, 250)], fill=(200, 0, 0))
    else: # Purple/Other
        draw.rectangle([50, 100, 250, 200], fill=(128, 0, 128))
        draw.ellipse([50, 50, 150, 150], fill=(255, 255, 255))
    img.save(path)

def setup_sandbox():
    os.makedirs(REF_DIR, exist_ok=True)
    os.makedirs(TARGET_DIR, exist_ok=True)
    
    # Campaign A (Blue theme) references
    create_color_image((0, 0, 255), os.path.join(REF_DIR, "blue_1.png"))
    create_color_image((10, 20, 240), os.path.join(REF_DIR, "blue_2.png"))
    create_color_image((30, 10, 220), os.path.join(REF_DIR, "blue_3.png"))
    create_color_image((0, 50, 255), os.path.join(REF_DIR, "blue_4.png"))
    
    # Target image that matches (Blue theme)
    create_color_image((15, 15, 230), os.path.join(TARGET_DIR, "target_blue_pos.png"))
    # Target image that does NOT match (Red theme)
    create_color_image((255, 0, 0), os.path.join(TARGET_DIR, "target_red_neg.png"))
    
    print(f"Sandbox created successfully at:\n  References: {REF_DIR}\n  Targets: {TARGET_DIR}")

def run_api_test():
    url = "http://127.0.0.1:8001/campaign-match/"
    payload = {
        "reference_path": REF_DIR.replace("\\", "/"),
        "target_path": TARGET_DIR.replace("\\", "/"),
        "campaign_name": "blue_latte_promo",
        "debug": True,
        "caption": "Best morning brew ever ☕ Try Starbucks today! #StarbucksPartner @Starbucks",
        "rules": "- must mention @Starbucks\n- must include #StarbucksPartner\n- no competitor mentions\n- avoid overly promotional wording"
    }

    try:
        print("Sending match request to API...")
        res = requests.post(url, json=payload)
        data = res.json()
        if "error" in data:
            print(f"API Error: {data['error']}")
        else:
            print("\nAPI Match Report Summary:")
            summary = data.get("summary", {})
            print(f"  Campaign: {summary.get('campaign_name')}")
            print(f"  Total Targets: {summary.get('num_targets')}")
            print(f"  Matches: {summary.get('matches')}")
            print(f"  Strong Matches: {summary.get('strong_matches')}")
            print(f"  Possible Matches: {summary.get('possible_matches')}")
            print(f"  Rejections: {summary.get('rejections')}")
            
            results = data.get("results", [])
            print(f"\nDetailed Results ({len(results)} posts):")
            for r in results:
                print(f"\n- File: {r['filename']}")
                print(f"  Visual Match: {r['campaign_match']} ({r['match_type']}, Conf: {r['confidence_pct']}%)")
                print(f"  Compliance Verdict: {r.get('compliance_status')}")
                print(f"  Compliance Score: {r.get('compliance_score')}%")
                if "violations" in r:
                    print(f"    Violations: {r['violations']}")
                    print(f"    Warnings: {r['warnings']}")
                    print(f"    Passed Rules: {r['passed_rules']}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    setup_sandbox()
    run_api_test()
