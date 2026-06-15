# -*- coding: utf-8 -*-
"""为 D18 根因分析报告生成数据统计"""
import json
from collections import Counter, defaultdict

with open("error_analysis/curated_errors.json", encoding="utf-8") as f:
    curated = json.load(f)

errors = curated["errors"]
p0 = [e for e in errors if e["review"]["priority"] == "P0"]
p1 = [e for e in errors if e["review"]["priority"] == "P1"]
p2 = [e for e in errors if e["review"]["priority"] == "P2"]
noisy = [e for e in errors if e["review"]["data_quality"] == "noisy"]

# Print stats
print(f"Total: {len(errors)}")
print(f"P0: {len(p0)}, P1: {len(p1)}, P2: {len(p2)}")
print(f"Noisy: {len(noisy)}")

# P0 by subject
print("\n=== P0 by subject ===")
p0_by_subj = Counter(e["subject"] for e in p0)
for s, c in p0_by_subj.most_common():
    print(f"  {s}: {c}")

# P0 by sub_category
print("\n=== P0 by sub_category ===")
p0_by_sub = Counter(e["deep_classification"]["sub_category"] for e in p0)
for s, c in p0_by_sub.most_common():
    print(f"  {s}: {c}")

# Version comparison
print("\n=== Version history ===")
by_ver = defaultdict(int)
for e in errors:
    for ver, status in e["version_status"].items():
        if status == "open":
            by_ver[ver] += 1
for ver in ["v1.0", "v1.1", "v1.2"]:
    print(f"  {ver}: {by_ver.get(ver, 0)} open")

# Subject accuracy by version
print("\n=== Subject accuracy by version (from error data) ===")
# We know total per subject from benchmark (200 total)
TOTAL = {"math": 34, "physics": 33, "history": 30, "english": 27, "chinese": 29, "chemistry": 27, "politics": 20}
for ver in ["v1.0", "v1.1", "v1.2"]:
    print(f"\n  {ver}:")
    for subj in ["math", "physics", "chemistry", "chinese", "english", "history", "politics"]:
        open_count = sum(1 for e in errors
                        if e["subject"] == subj
                        and e["version_status"].get(ver) == "open")
        total = TOTAL.get(subj, 30)
        acc = (total - open_count) / total * 100
        print(f"    {subj:10s} {total-open_count:2d}/{total:2d} = {acc:4.1f}%")

# Fix clusters
print("\n=== Fix clusters ===")
for c in curated.get("fix_clusters", []):
    if c["count"] >= 2:
        print(f"  {c['pattern']:30s} {c['count']:2d} → {c['fix_approach'][:80]}")

# Warning summary
print("\n=== Review warnings ===")
warn_cats = Counter()
for e in errors:
    for w in e["review"]["warnings"]:
        warn_cats[w[:60]] += 1
for w, c in warn_cats.most_common():
    print(f"  [{c}] {w}")

# Specific error list for report
print("\n=== P0 top errors for report ===")
for e in p0[:20]:
    dc = e["deep_classification"]
    q = e["question"][:100].replace("\n", " ")
    print(f"  #{e['id']:3d} [{e['subject']:10s}] ans={e['correct_answer']} pred={e['latest_model_answer']}")
    print(f"       {dc['category']}/{dc['sub_category']} | difficulty={dc['difficulty']}")
    print(f"       root: {dc.get('root_cause', 'N/A')[:120]}")
    print(f"       Q: {q}")
