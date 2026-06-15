# -*- coding: utf-8 -*-
"""快速查看 v1.2 新引入的回归错误"""
import json, sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("error_analysis/all_errors.json", encoding="utf-8") as f:
    db = json.load(f)

new = [e for e in db["errors"] if e["is_new_in_v1_2"]]
print(f"v1.2 新引入错误 ({len(new)} 题 — v1.0/v1.1正确但v1.2错了):")
for e in new:
    print(f"\n#{e['id']} [{e['subject']:10s}] "
          f"ans={e['correct_answer']} pred={e['latest_model_answer']} "
          f"[{e['latest_error_type']}]")
    print(f"  历史: {' | '.join(e['error_history'])}")
    print(f"  Q: {e['question'][:150]}")

# 也检查一下当前 v1.2 恢复的错题 (v1.0/v1.1 open but v1.2 fixed)
recovered = [e for e in db["errors"]
             if e["version_status"].get("v1.1") == "open"
             and e["current_status"] == "fixed"]
print(f"\n\nv1.2 恢复的错题 (v1.1 open → v1.2 fixed): {len(recovered)} 题")
for e in recovered[:5]:
    print(f"  #{e['id']} [{e['subject']:10s}] ans={e['correct_answer']} "
          f"history={' | '.join(e['error_history'])}")
if len(recovered) > 5:
    print(f"  ... 还有 {len(recovered)-5} 题")
