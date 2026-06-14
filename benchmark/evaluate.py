# -*- coding: utf-8 -*-
"""
Day 9: 自动评分脚本
用法:
  python benchmark/evaluate.py                          # 默认模型 models/v1.1/final
  python benchmark/evaluate.py --model models/v1.0/final
  python benchmark/evaluate.py --test                  # 只测前10题，快速验证
  python benchmark/evaluate.py --json                  # 输出JSON格式结果
"""
import argparse, json, re, sys, time, os
from collections import defaultdict
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))
from sft.infer import load_model, generate

BENCHMARK_PATH = "benchmark/test_set_v0.1.json"


def extract_answer(text: str) -> str | None:
    """从模型输出中提取选项字母 A/B/C/D

    支持格式:
    - "A" "B" "C" "D" (纯字母)
    - "A." "A、" "（A）" "(A)"
    - "选A" "答案：A" "答案为A" "故选A"
    - "【答案】A"
    - CoT末尾的答案行
    """
    if not text:
        return None
    text = text.strip()

    # 1. 先尝试匹配常见的答案标记格式
    patterns = [
        r'【答案】\s*([A-D])',
        r'答案[：:]\s*([A-D])',
        r'(?:故选?|应选?|答案为?)\s*([A-D])',
        r'(?:选项|正确选项)\s*([A-D])',
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1)

    # 2. 寻找独立的选项字母（位于句首或括号中）
    patterns2 = [
        r'(?:^|\n)\s*([A-D])\s*[.\s、．，）)]?\s*(?:$|\n)',  # 行首或行尾的字母
        r'[（(]\s*([A-D])\s*[）)]',  # 括号中的字母
    ]
    for pat in patterns2:
        m = re.search(pat, text, re.MULTILINE)
        if m:
            return m.group(1)

    # 3. 如果文本很短且只有单个大写字母
    text_clean = text.strip().upper()
    if len(text_clean) <= 3 and text_clean and text_clean[0] in 'ABCD':
        return text_clean[0]

    # 4. 在整个文本中寻找最后一个独立出现的选项字母
    # （CoT输出中，答案通常在最后）
    lines = text.split('\n')
    for line in reversed(lines):
        line = line.strip()
        if len(line) <= 3 and line.upper() in 'ABCD':
            return line.upper()
        m = re.search(r'(?:^|\s)([A-D])(?:\s|$)', line)
        if m:
            return m.group(1)

    # 5. 最后的fallback: 找第一个大写A-D字母
    for ch in text_clean:
        if ch in 'ABCD':
            return ch

    return None


def evaluate_model(model, tokenizer, device: str, questions: list,
                   max_new_tokens: int = 256) -> dict:
    """对模型在benchmark上评测"""
    results = {
        "total": len(questions),
        "correct": 0,
        "by_subject": defaultdict(lambda: {"correct": 0, "total": 0}),
        "errors": [],
        "details": [],
    }
    t0 = time.time()

    for i, q in enumerate(questions):
        # 构建带选项的prompt
        prompt = q["question"]
        pred = generate(model, tokenizer, prompt,
                       max_new_tokens=max_new_tokens,
                       do_sample=False, device=device).strip()

        # 提取选项字母
        pred_letter = extract_answer(pred)
        true_letter = q["answer"].strip().upper()
        is_correct = (pred_letter == true_letter)

        # 统计
        subj = q["subject"]
        results["by_subject"][subj]["total"] += 1
        if is_correct:
            results["correct"] += 1
            results["by_subject"][subj]["correct"] += 1
        else:
            results["errors"].append({
                "id": q["id"],
                "subject": subj,
                "question": q["question"][:100],
                "expected": true_letter,
                "predicted": pred_letter or "?",
                "raw_output": pred[:150],
            })

        results["details"].append({
            "id": q["id"], "subject": subj,
            "correct": is_correct, "predicted": pred_letter,
        })

        # 进度打印（每20题）
        if (i + 1) % 20 == 0 or i == 0:
            acc_so_far = results["correct"] / (i + 1) * 100
            print(f"  [{i+1}/{len(questions)}] acc={acc_so_far:.1f}%")

    results["time"] = time.time() - t0
    results["accuracy"] = results["correct"] / results["total"] * 100
    return results


def print_report(results: dict):
    """打印评测报告"""
    print(f"\n{'=' * 60}")
    print("BENCHMARK v0.1 评测报告")
    print(f"{'=' * 60}")
    print(f"  总题数: {results['total']}")
    print(f"  正确: {results['correct']}")
    print(f"  错误: {results['total'] - results['correct']}")
    print(f"  准确率: {results['accuracy']:.1f}%")
    print(f"  耗时: {results['time']:.1f}s")

    print(f"\n{'─' * 40}")
    print(f"  各科得分:")
    print(f"  {'学科':10s} {'正确/总数':12s} {'准确率':>8s}")
    print(f"  {'─' * 30}")

    subjects_order = ["math", "physics", "chemistry", "chinese",
                      "english", "history", "politics"]
    for s in subjects_order:
        info = results["by_subject"].get(s)
        if info and info["total"] > 0:
            acc = info["correct"] / info["total"] * 100
            bar = "█" * int(acc / 5) + "░" * (20 - int(acc / 5))
            print(f"  {s:10s} {info['correct']:2d}/{info['total']:2d} = {acc:5.1f}%  {bar}")

    # 错误样例（前5条）
    if results["errors"]:
        print(f"\n{'─' * 40}")
        print(f"  错误样例 (前5条):")
        for err in results["errors"][:5]:
            print(f"  #{err['id']} [{err['subject']}] 预期:{err['expected']} 预测:{err['predicted']}")
            print(f"    Q: {err['question'][:80]}...")
            if err["predicted"] == "?":
                print(f"    Raw: {err['raw_output'][:100]}...")


def main():
    parser = argparse.ArgumentParser(description="Benchmark 自动评分")
    parser.add_argument("--model", default="models/v1.1/final", help="模型路径")
    parser.add_argument("--benchmark", default=BENCHMARK_PATH, help="题库路径")
    parser.add_argument("--test", action="store_true", help="仅测前10题")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    args = parser.parse_args()

    # 加载题库
    print(f"加载题库: {args.benchmark}")
    with open(args.benchmark, encoding="utf-8") as f:
        questions = json.load(f)
    if args.test:
        questions = questions[:10]
    print(f"  题目数: {len(questions)}")

    # 加载模型
    model, tokenizer, device = load_model(args.model)

    # 评测
    print(f"\n开始评测 ({len(questions)} 题)...")
    results = evaluate_model(model, tokenizer, device, questions)

    # 输出
    if args.json:
        # 简化JSON输出（排除details中的冗余信息）
        json_out = {
            "model": args.model,
            "total": results["total"],
            "correct": results["correct"],
            "accuracy": results["accuracy"],
            "time": results["time"],
            "by_subject": {
                s: {"correct": v["correct"], "total": v["total"],
                    "accuracy": round(v["correct"] / v["total"] * 100, 1)}
                for s, v in results["by_subject"].items()
            },
            "errors": results["errors"],
        }
        print(json.dumps(json_out, ensure_ascii=False, indent=2))
    else:
        print_report(results)

    return results


if __name__ == "__main__":
    main()
