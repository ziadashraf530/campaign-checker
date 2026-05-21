import sys
import os

# Add parent directory to sys.path if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rule_parser import parse_rules
from promo_detector import analyze_promotional_tone
from rule_evaluator import evaluate_compliance
from compliance_engine import ComplianceEngine

def test_rule_parser():
    rules_text = (
        "- must mention @Starbucks\n"
        "- must include #StarbucksPartner\n"
        "- no competitor mentions\n"
        "- avoid overly promotional wording\n"
        "- avoid sugar\n"
        "- no plastic straws\n"
        "- include seasonal holiday drink\n"
    )
    parsed = parse_rules(rules_text)
    
    # We expect 7 parsed rules
    print(f"Parsed {len(parsed)} rules:")
    for idx, rule in enumerate(parsed):
        print(f"  {idx+1}. Type: {rule.rule_type}, Target: {rule.target}, Raw: {rule.raw_text}")
    
    assert len(parsed) >= 6, "Expected at least 6 parsed rules"
    
    types = [r.rule_type for r in parsed]
    assert "required_mention" in types, "Should parse @Starbucks mention"
    assert "required_hashtag" in types, "Should parse #StarbucksPartner hashtag"
    assert "no_competitors" in types, "Should parse competitor avoidance"
    assert "avoid_promo" in types, "Should parse promotional tone check"
    assert "warning_term" in types, "Should parse 'avoid sugar' check"
    assert "forbidden_term" in types, "Should parse 'no plastic straws' check"
    print("test_rule_parser PASSED!")

def test_promo_detector():
    ad_caption = "BUY NOW and act fast! Get yours today, click the link! Hurry!"
    normal_caption = "Enjoying a quiet morning coffee walk in the park. #chill"
    
    ad_res = analyze_promotional_tone(ad_caption)
    normal_res = analyze_promotional_tone(normal_caption)
    
    assert ad_res["detected"] is True
    assert len(ad_res["matched_phrases"]) >= 3
    assert normal_res["detected"] is False
    print("test_promo_detector PASSED!")

def test_rule_evaluator():
    rules_text = (
        "- must mention @Starbucks\n"
        "- must include #StarbucksPartner\n"
        "- no competitor mentions\n"
        "- avoid overly promotional wording"
    )
    parsed = parse_rules(rules_text)
    
    # 1. 100% PASS Caption
    pass_caption = "Enjoying my delicious morning latte! Thank you @Starbucks #StarbucksPartner"
    res = evaluate_compliance(pass_caption, parsed)
    assert res["compliance_status"] == "PASS"
    assert res["score"] == 100
    
    # 2. PARTIAL Caption (Warning due to promo words)
    partial_caption = "Enjoying my delicious latte! Thank you @Starbucks #StarbucksPartner. Buy now!"
    res2 = evaluate_compliance(partial_caption, parsed)
    assert res2["compliance_status"] == "PARTIAL"
    assert res2["score"] == 90
    assert len(res2["warnings"]) == 1
    
    # 3. FAIL Caption (Missing mention and hashtag, has competitor dunkin)
    fail_caption = "Drinking Dunkin today instead of normal brands."
    res3 = evaluate_compliance(fail_caption, parsed)
    assert res3["compliance_status"] == "FAIL"
    # Deductions:
    # - Missing @Starbucks mention (-20)
    # - Missing #StarbucksPartner hashtag (-20)
    # - Competitor brand detected Dunkin (-20)
    # Total score = 100 - 60 = 40
    assert res3["score"] == 40
    assert len(res3["violations"]) == 3
    
    print("test_rule_evaluator PASSED!")

def test_compliance_engine():
    caption = "A quick coffee break at @Starbucks. #StarbucksPartner #morning"
    rules = "- must mention @Starbucks\n- must include #StarbucksPartner"
    
    # Using the current directory for output files
    current_dir = os.path.dirname(os.path.abspath(__file__))
    report = ComplianceEngine.analyze_compliance(caption, rules, debug=True, output_dir=current_dir)
    assert report["compliance_status"] == "PASS"
    assert report["score"] == 100
    
    parsed_rules_path = os.path.join(current_dir, "parsed_rules.json")
    violation_report_path = os.path.join(current_dir, "violation_report.json")
    compliance_debug_path = os.path.join(current_dir, "compliance_debug.json")
    
    # Check if files were written
    assert os.path.exists(parsed_rules_path), f"File {parsed_rules_path} does not exist"
    assert os.path.exists(violation_report_path), f"File {violation_report_path} does not exist"
    assert os.path.exists(compliance_debug_path), f"File {compliance_debug_path} does not exist"
    
    # Clean up files
    os.remove(parsed_rules_path)
    os.remove(violation_report_path)
    os.remove(compliance_debug_path)
    print("test_compliance_engine PASSED!")

if __name__ == "__main__":
    print("Running compliance tests...")
    test_rule_parser()
    test_promo_detector()
    test_rule_evaluator()
    test_compliance_engine()
    print("ALL COMPLIANCE TESTS PASSED!")
