# -*- coding: utf-8 -*-
"""
Day 4: 推理测试 — 从验证集抽取 5 个不同学科的问题进行测试
用法: python sft/test_infer.py
"""
import sys, time, os
# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from sft.infer import load_model, generate

# 从验证集挑选 5 个不同学科的测试问题 (纯 ASCII + 常见中文)
TEST_QUESTIONS = [
    {
        "id": 1,
        "question": "他们的目的在于恢复儒家的地位，使这个极其落魄的帝国恢复传统专制制度那种平静安稳的统治。但是也逐渐认识到改革和谨慎的现代化的必要性。改革和谨慎的现代化是指（ ）A. 洋务运动 B. 新文化运动 C. 戊戌变法 D. 实业救国",
        "subject": "history",
        "expected": "C"
    },
    {
        "id": 2,
        "question": "下列计算正确的是（ ）A. a的平方乘a的立方等于a的六次方 B. a的平方的立方等于a的五次方 C. a的立方除以a等于a的立方 D. a加b的平方等于a方加2ab加b方",
        "subject": "math",
        "expected": "D"
    },
    {
        "id": 3,
        "question": "Hi, Bob! What is going on over there? 请问 going on 在此处的含义是什么？",
        "subject": "english",
        "expected": "发生"
    },
    {
        "id": 4,
        "question": "请简述陋室铭的主旨思想。作者是刘禹锡。",
        "subject": "chinese",
        "expected": "安贫乐道"
    },
    {
        "id": 5,
        "question": "一辆汽车在水平公路上匀速行驶，下列说法中正确的是（ ）A. 汽车受到的重力与汽车对地面的压力是一对平衡力 B. 汽车受到的牵引力与汽车受到的阻力是一对平衡力 C. 汽车受到的重力与地面对汽车的支持力是一对相互作用力 D. 汽车对地面的压力与地面对汽车的支持力是一对平衡力",
        "subject": "physics",
        "expected": "B"
    },
]

def main():
    print("=" * 60)
    print("Day 4: Inference Test - 5 questions across subjects")
    print("=" * 60)

    model, tokenizer, device = load_model("models/v1.0/final")
    print(f"  Device: {device}")
    print(f"  Vocab size: {tokenizer.vocab_size}")

    passed = 0
    total_time = 0

    for i, item in enumerate(TEST_QUESTIONS):
        print(f"\n{'-' * 50}")
        print(f"Test {i+1}/5 [{item['subject'].upper()}]")
        # 截断过长的问题
        q_preview = item['question'][:120]
        print(f"Q: {q_preview}...")

        t0 = time.time()
        answer = generate(
            model, tokenizer, item["question"],
            max_new_tokens=128,
            do_sample=False,
            device=device,
        )
        elapsed = time.time() - t0
        total_time += elapsed

        # 截断过长的回答
        a_preview = answer[:200]
        print(f"A: {a_preview}")
        print(f"[TIME] {elapsed:.1f}s")

        expected = item.get("expected", "")
        if expected:
            if expected.upper() in answer.upper():
                print(f"[OK] Contains expected: {expected}")
                passed += 1
            else:
                print(f"[?] Missing expected: {expected}")

    print(f"\n{'=' * 60}")
    print(f"Result: {passed}/5 questions contain expected keywords")
    print(f"Total time: {total_time:.1f}s, Avg: {total_time/5:.1f}s/q")
    print(f"Device: {device}")
    print(f"{'=' * 60}")

    return passed

if __name__ == "__main__":
    main()
