# -*- coding: utf-8 -*-
"""
构建 v1.2 数据集: 清洗噪声 + 保留CoT
策略: 去噪30%+保留已有CoT → 训练干净模型
"""
import json, re, os, sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NOISE_PATTERNS = [
    r'^(?:解析|【解析】)',
    r'故选[：:]',
    r'答案为?[：:]',
]

def is_noisy(question: str) -> bool:
    if len(question) > 500:
        return True
    for pat in NOISE_PATTERNS:
        if re.search(pat, question):
            return True
    return False

def main():
    # Load training data only (val is separate, unchanged)
    train = json.load(open("data/v1.0/train.json", encoding="utf-8"))
    print(f"原始训练集: {len(train)}")

    # Load existing CoT from v1.1 progress
    cot_map = {}
    if os.path.exists("data/v1.1/cot_progress.json"):
        cot_data = json.load(open("data/v1.1/cot_progress.json", encoding="utf-8"))
        for item in cot_data:
            if item.get("cot") and item.get("cot_status") == "generated":
                key = item["question"].strip()[:80]
                cot_map[key] = item["cot"]
        print(f"已有CoT: {len(cot_map)} 条")

    # Filter clean
    clean_qa = []
    noisy_count = 0
    for q in train:
        if is_noisy(q["question"]):
            noisy_count += 1
        else:
            clean_qa.append(q)

    print(f"干净: {len(clean_qa)} | 噪声: {noisy_count} (去除{noisy_count/len(train)*100:.0f}%)")

    # Build v1.2: clean QA + CoT for matched questions
    result = []
    cot_added = 0
    for q in clean_qa:
        # 原始格式
        result.append({
            "question": q["question"],
            "answer": q["answer"],
            "subject": q.get("subject", "unknown"),
        })
        # 如果有CoT, 添加CoT版本
        key = q["question"].strip()[:80]
        if key in cot_map:
            result.append({
                "question": q["question"],
                "answer": q["answer"],
                "cot": cot_map[key],
                "subject": q.get("subject", "unknown"),
            })
            cot_added += 1

    print(f"v1.2 数据集: {len(result)} 条 (干净QA + CoT增强 {cot_added})")

    # Save
    os.makedirs("data/v1.2", exist_ok=True)
    with open("data/v1.2/train.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Stats
    from collections import Counter
    subj = Counter(q["subject"] for q in result)
    print("学科分布:")
    for s, n in sorted(subj.items()):
        print(f"  {s}: {n}")

    print(f"\n✅ 已保存: data/v1.2/train.json")
    print(f"下一步: python sft/train.py --train_data data/v1.2/train.json --output_dir models/v1.2")

if __name__ == "__main__":
    main()
