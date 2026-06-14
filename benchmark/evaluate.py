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

    策略（按优先级）:
    1. 显式答案标记 (【答案】/答案为/故选/所以选择)
    2. 最后一个"选X"类标记
    3. 行尾独立字母 (CoT格式)
    4. 括号中的字母
    5. 短文本fallback
    排除: "ABCD"连续序列、选项列表(A/B/C/D同时出现)
    """
    if not text:
        return None
    text = text.strip()

    # 排除"ABCD"连续序列
    if re.search(r'[A-D]{4}', text):
        return None

    # 1. 显式答案标记 (最高优先级)
    explicit_patterns = [
        r'【答案】\s*([A-D])',
        r'(?:所以选择|所以选|因此选择|因此选|综上.*?选)\s*([A-D])',
        r'(?:正确答案是?|正确.*?是?)\s*([A-D])',
        r'[Tt]he\s+answer\s+is\s+([A-D])',  # 英文格式
        r'答案[：:]\s*([A-D])',
        r'答案为?\s*([A-D])',
        r'(?:故选|应选|正确选项为?|正确选项[：:])\s*([A-D])',
    ]
    # 取最后一个匹配（CoT中最终答案在最后）
    last_match = None
    for pat in explicit_patterns:
        for m in re.finditer(pat, text):
            last_match = m.group(1)
    if last_match:
        return last_match

    # 2. "选X"类标记 (次优先级)
    choose_patterns = [
        r'(?:选项|选择|选择答案)\s*([A-D])',
        r'[选選]\s*([A-D])\s*(?:项|項|个)?',
    ]
    last_choose = None
    for pat in choose_patterns:
        for m in re.finditer(pat, text):
            last_choose = m.group(1)
    if last_choose:
        return last_choose

    # 3. 行尾/行首独立字母 (CoT格式: 每行一个选项判断)
    lines = text.split('\n')
    # 先找最后一行只有单个字母的情况
    for line in reversed(lines):
        stripped = line.strip()
        if len(stripped) <= 2 and stripped.upper() in 'ABCD':
            return stripped.upper()
    # 再找行首带标记的字母
    for line in reversed(lines):
        m = re.search(r'(?:^|\s)([A-D])[.\s、．，）)](?:\s|$)', line.strip())
        if m:
            return m.group(1)

    # 4. 括号中的字母
    bracket_matches = re.findall(r'[（(]\s*([A-D])\s*[）)]', text)
    if bracket_matches:
        return bracket_matches[-1]  # 最后一个括号中的

    # 5. 中文上下文中最后出现的独立字母
    # 匹配"是X" "为X" "选X" 后面的字母
    context_matches = re.findall(r'(?:是|为|选|选择)\s*([A-D])\s*(?:[。，、．\s]|$)', text)
    if context_matches:
        return context_matches[-1]

    # 6. 如果文本很短且以字母开头
    text_clean = text.strip().upper()
    if len(text_clean) <= 3 and text_clean[0] in 'ABCD':
        return text_clean[0]

    # 7. 最终fallback: 检查是否只有一个A-D字母出现且不连续
    found = [c for c in text_clean if c in 'ABCD']
    if len(found) == 1:
        return found[0]

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
