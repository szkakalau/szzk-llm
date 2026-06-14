# -*- coding: utf-8 -*-
"""
Day 6: v1.0 vs v1.1 模型对比脚本
用法: python sft/compare_models.py
"""
import sys, time, json, os
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from sft.infer import load_model, generate

# 10道测试题，覆盖各学科
TEST_CASES = [
    {"question": "一组数据：5, 7, 7, 8, 9, 7, 6，这组数据的众数是（ ）A. 5 B. 7 C. 8 D. 9", "answer": "B", "subject": "math"},
    {"question": "下列图形中，是轴对称图形的是（ ）A. 平行四边形 B. 三角形 C. 圆 D. 梯形", "answer": "C", "subject": "math"},
    {"question": "商周时期最具代表性的器物是（ ）A. 瓷器 B. 铁器 C. 青铜器 D. 陶器", "answer": "C", "subject": "history"},
    {"question": "1911年辛亥革命的历史意义是什么？", "answer": "推翻了清朝统治，结束了封建君主专制制度", "subject": "history"},
    {"question": "The word 'afford' means（ ）A. 租用 B. 借用 C. 买得起", "answer": "C", "subject": "english"},
    {"question": "'What's going on?' means 'What's ______?' A. appearing B. happening C. working", "answer": "B", "subject": "english"},
    {"question": "物体在月球上的质量与地球上相比（ ）A. 变大 B. 变小 C. 不变 D. 先变大后变小", "answer": "C", "subject": "physics"},
    {"question": "两艘船并行时不能靠太近，这是因为流体流速大的地方压强___？", "answer": "小", "subject": "physics"},
    {"question": "《陋室铭》中表达了作者怎样的生活态度？", "answer": "安贫乐道、高洁傲岸", "subject": "chinese"},
    {"question": "合金的硬度通常比其组分纯金属的硬度___？", "answer": "大", "subject": "chemistry"},
]

def test_model(model, tokenizer, device, name: str) -> dict:
    """对单个模型跑10道测试题"""
    correct = 0
    details = []
    t0 = time.time()

    for i, item in enumerate(TEST_CASES):
        pred = generate(
            model, tokenizer, item["question"],
            max_new_tokens=128, do_sample=False, device=device
        ).strip()

        # 选择题匹配选项字母，简答题包含匹配
        is_correct = item["answer"].upper() in pred.upper()

        details.append({
            "id": i+1,
            "subject": item["subject"],
            "question": item["question"][:80],
            "expected": item["answer"],
            "predicted": pred[:100],
            "correct": is_correct,
        })
        if is_correct:
            correct += 1
        print(f"  [{i+1}/10] {item['subject']:8s} {'OK' if is_correct else '??'} | {pred[:50]}")

    elapsed = time.time() - t0
    acc = correct / len(TEST_CASES) * 100

    print(f"\n  {name} 结果: {correct}/{len(TEST_CASES)} = {acc:.0f}% | 耗时: {elapsed:.1f}s")
    return {"name": name, "correct": correct, "total": len(TEST_CASES), "accuracy": acc, "time": elapsed, "details": details}


def main():
    print("=" * 60)
    print("Day 6: v1.0 vs v1.1 模型对比评测")
    print("=" * 60)

    results = {}
    for version in ["v1.0", "v1.1"]:
        model_path = f"models/{version}/final"
        if not os.path.exists(model_path):
            print(f"\n  [SKIP] {model_path} 不存在")
            continue

        print(f"\n--- 测试 {version} 模型 ---")
        model, tokenizer, device = load_model(model_path)
        results[version] = test_model(model, tokenizer, device, version)

    # 对比报告
    if len(results) == 2:
        v10 = results["v1.0"]
        v11 = results["v1.1"]
        delta = v11["accuracy"] - v10["accuracy"]
        delta_t = v11["time"] - v10["time"]

        print(f"\n{'=' * 60}")
        print("对比报告")
        print(f"{'=' * 60}")
        print(f"         v1.0: {v10['correct']}/{v10['total']} = {v10['accuracy']:.0f}% ({v10['time']:.1f}s)")
        print(f"         v1.1: {v11['correct']}/{v11['total']} = {v11['accuracy']:.0f}% ({v11['time']:.1f}s)")
        print(f"         Delta: {'+' if delta >= 0 else ''}{delta:.0f}%")
        print()

        # 逐题对比
        print("逐题对比:")
        for i in range(10):
            c10 = "OK" if v10["details"][i]["correct"] else "??"
            c11 = "OK" if v11["details"][i]["correct"] else "??"
            marker = "  <--" if c10 != c11 else ""
            print(f"  #{i+1} [{v10['details'][i]['subject']:8s}] v1.0:{c10} v1.1:{c11}{marker}")

    print(f"\n{'=' * 60}")
    print("Done")


if __name__ == "__main__":
    main()
