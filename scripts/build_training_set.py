# -*- coding: utf-8 -*-
"""
Step 2: 清洗合并 677 题 → 构建标准训练数据集
输出: data/clean_train.json (训练格式), data/clean_bench.json (评测格式)
"""
import json, re, sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

INPUT = "data/extracted_questions.json"
OUT_TRAIN = "data/clean_train.json"
OUT_BENCH = "data/clean_bench.json"

with open(INPUT, encoding="utf-8") as f:
    raw = json.load(f)

print(f"原始题目: {len(raw)}")

# ── 清洗流水线 ──
def clean_text(text: str) -> str:
    """清洗单个文本"""
    # 移除多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    # 移除题号前的年份引用 "(2008•深圳)"
    text = re.sub(r'[（(]\d{4}[•·]\w+[）)]', '', text)
    # 移除分值 "(2分)" "(1.5分)"
    text = re.sub(r'[（(]\d+\.?\d*\s*分[）)]', '', text)
    # 移除纯选择题标记残留
    text = re.sub(r'第[一二三四五六七八九十]+部分\s*选择题?', '', text)
    return text.strip()


def validate_options(options: list) -> list | None:
    """验证并清洗选项，返回 None 如果无效"""
    if not options or len(options) < 2:
        return None
    clean = []
    for o in options:
        o = re.sub(r'\s+', ' ', o).strip()
        # 必须 A-D 开头
        if re.match(r'^[A-D][\.\、．）)]', o):
            clean.append(o)
    if len(clean) < 2:
        return None
    # 选项不应是重复的同一字母
    letters = [o[0] for o in clean]
    if len(set(letters)) < 2:
        return None
    return clean


# ── 主清洗循环 ──
valid = []
stats = Counter()

for q in raw:
    stats["total"] += 1

    # 必须有答案
    ans = q.get("answer", "")
    if not ans or ans[0] not in "ABCD":
        stats["no_answer"] += 1
        continue

    # 清洗题干
    question = clean_text(q.get("question", ""))
    if len(question) < 8:
        stats["question_too_short"] += 1
        continue

    # 清洗选项
    options = validate_options(q.get("options", []))
    if not options:
        stats["bad_options"] += 1
        continue

    # 答案必须在选项中
    opt_letters = [o[0] for o in options]
    if ans[0] not in opt_letters:
        stats["answer_not_in_options"] += 1
        continue

    subject = q.get("subject", "unknown")
    stats["valid"] += 1

    valid.append({
        "question": question,
        "options": options,
        "answer": ans[0],
        "subject": subject,
        "year": q.get("year"),
        "source": q.get("source", ""),
    })

# ── 去重 ──
seen = set()
unique = []
for q in valid:
    key = q["question"][:80]
    if key not in seen:
        seen.add(key)
        unique.append(q)
dupes = len(valid) - len(unique)

# ── 统计 ──
by_subj = defaultdict(list)
for q in unique:
    by_subj[q["subject"]].append(q)

print(f"\n清洗结果:")
print(f"  原始: {stats['total']}")
print(f"  无答案: {stats['no_answer']}")
print(f"  题干过短: {stats['question_too_short']}")
print(f"  选项无效: {stats['bad_options']}")
print(f"  答案不匹配: {stats['answer_not_in_options']}")
print(f"  有效: {stats['valid']} → 去重: {len(unique)} (去{dupes}个重复)")

print(f"\n各学科:")
for subj in sorted(by_subj):
    qs = by_subj[subj]
    years = sorted(set(q.get("year") for q in qs if q.get("year")))
    print(f"  {subj:12s}: {len(qs):4d}题, 年份: {min(years)}-{max(years)}")

# ── 保存训练格式 ──
# 训练格式: {"question": "...", "answer": "X", "subject": "..."}
train_data = []
for q in unique:
    # 把选项拼入题干（与现有训练数据格式一致）
    opts_str = " ".join(q["options"])
    train_data.append({
        "question": f"{q['question']} {opts_str}",
        "answer": q["answer"],
        "subject": q["subject"],
    })

with open(OUT_TRAIN, "w", encoding="utf-8") as f:
    json.dump(train_data, f, ensure_ascii=False, indent=2)

# ── 保存 Benchmark 格式 ──
# Benchmark 格式: {"id": N, "subject": "", "question": "", "options": [], "answer": ""}
bench_data = []
for i, q in enumerate(unique):
    bench_data.append({
        "id": i + 1,
        "subject": q["subject"],
        "question": q["question"],
        "options": q["options"],
        "answer": q["answer"],
    })

with open(OUT_BENCH, "w", encoding="utf-8") as f:
    json.dump(bench_data, f, ensure_ascii=False, indent=2)

print(f"\n已保存:")
print(f"  训练集: {OUT_TRAIN} ({len(train_data)} 条)")
print(f"  评测集: {OUT_BENCH} ({len(bench_data)} 条)")
print(f"\n总计可训练题目: {len(train_data)} 题 (7学科)")
