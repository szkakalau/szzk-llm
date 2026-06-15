# Verify D16 classification results
import json
from collections import Counter

with open("error_analysis/classified_errors.json", encoding="utf-8") as f:
    data = json.load(f)

with_dc = [e for e in data if "deep_classification" in e]
print(f"Total: {len(data)}, Classified: {len(with_dc)}")

# Category breakdown
cats = Counter(e["deep_classification"]["category"] for e in with_dc)
print(f"Categories: {dict(cats)}")

# Difficulty
diffs = Counter(e["deep_classification"]["difficulty"] for e in with_dc)
print(f"Difficulty: {dict(diffs)}")

# Sub-category
subs = Counter(e["deep_classification"]["sub_category"] for e in with_dc)
print(f"Sub-categories: {dict(subs.most_common(10))}")

# Errors
errors = [e for e in with_dc
          if e["deep_classification"].get("category") in ("parse_error", "api_error")]
print(f"Failed: {len(errors)}")

# Confidence average
confs = [e["deep_classification"].get("confidence", 0) for e in with_dc]
print(f"Avg confidence: {sum(confs)/len(confs):.2f}")

# Show one good sample
sample = with_dc[20]
dc = sample["deep_classification"]
print(f"\nSample #{sample['id']} [{sample['subject']}]")
print(f"  Category: {dc['category']}/{dc['sub_category']}")
print(f"  Difficulty: {dc['difficulty']}")
print(f"  Root cause: {dc['root_cause'][:150]}")
print(f"  Fix: {dc['fix_suggestion'][:150]}")
print(f"  Confidence: {dc.get('confidence', 'N/A')}")
