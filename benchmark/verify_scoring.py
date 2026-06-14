# -*- coding: utf-8 -*-
"""
Day 10: 评分逻辑100%验证
用法: python benchmark/verify_scoring.py
验证: 数据完整性 + 答案提取 + 评分准确性
"""
import json, sys, os, re
from collections import Counter

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from benchmark.evaluate import extract_answer

BENCHMARK_PATH = "benchmark/test_set_v0.1.json"

# ═══════════════════════════════════════════════════════
# 测试1: 数据完整性验证
# ═══════════════════════════════════════════════════════
def verify_data_integrity(questions: list) -> list[str]:
    issues = []
    ids = set()
    for q in questions:
        # ID唯一性
        if q["id"] in ids:
            issues.append(f"#{q['id']} ID重复")
        ids.add(q["id"])

        # 必需字段
        for field in ["id", "subject", "question", "options", "answer"]:
            if field not in q:
                issues.append(f"#{q['id']} 缺少字段: {field}")

        # 答案格式
        ans = q.get("answer", "")
        if not ans or ans not in "ABCD":
            issues.append(f"#{q['id']} [{q.get('subject')}] 答案格式异常: '{ans}'")

        # 选项数量
        opts = q.get("options", [])
        if len(opts) < 2:
            issues.append(f"#{q['id']} 选项不足: {len(opts)}")

        # 答案必须在选项中
        opt_letters = [o[0] for o in opts]
        if ans and ans not in opt_letters:
            issues.append(f"#{q['id']} [{q.get('subject')}] 答案'{ans}'不在选项{opt_letters}中")

        # 选项格式
        for o in opts:
            if len(o) < 2 or o[0] not in "ABCD" or o[1] not in ".．、)）":
                issues.append(f"#{q['id']} 选项格式不规范: '{o[:30]}'")

        # 题目长度
        qlen = len(q.get("question", ""))
        if qlen < 10:
            issues.append(f"#{q['id']} 题目过短: {qlen}字符")
        if qlen > 1000:
            issues.append(f"#{q['id']} 题目过长: {qlen}字符")

    return issues


# ═══════════════════════════════════════════════════════
# 测试2: 答案提取全覆盖
# ═══════════════════════════════════════════════════════
ANSWER_EXTRACTION_TESTS = [
    # 基础格式
    ("A", "A"), ("B", "B"), ("C", "C"), ("D", "D"),
    ("A.", "A"), ("B.", "B"), ("C、", "C"), ("D．", "D"),
    ("（A）", "A"), ("(B)", "B"), ("(C)", "C"), ("（D）", "D"),

    # 中文标记
    ("选A", "A"), ("故选B", "B"), ("应选C", "C"),
    ("答案为A", "A"), ("答案为：B", "B"), ("答案：C", "C"),
    ("正确答案是D", "D"), ("正确选项为A", "A"),

    # CoT 格式
    ("【答案】A", "A"), ("【答案】B", "B"),
    ("【分析】题目考查的是...\n【答案】C", "C"),
    ("【分析】三角函数计算\n步骤1:...\n步骤2:...\n【答案】D", "D"),

    # 长文本中的答案
    ("根据以上分析，这道题的正确答案是A", "A"),
    ("...所以综上所述，故选B", "B"),
    ("综合考虑所有选项，正确选项是C。", "C"),

    # 行尾独立字母
    ("分析如下：\nA", "A"),
    ("推理过程...\n\nB", "B"),
    ("...\n所以答案是\nC", "C"),

    # 实际模型可能输出
    ("A 【考点】三角函数", "A"),
    ("B\n解析：这道题...", "B"),
    ("故选：A．", "A"),

    # 空格和标点
    ("答案是 A", "A"), ("选 B 吧", "B"),
    (" A ", "A"), ("\n C \n", "C"),

    # 非答案（应返回None）
    ("", None), ("?", None), ("...", None),
    ("这是一道三角函数题", None), ("ABCD", None),
    ("我也不知道", None), ("根据题意", None),

    # 无效答案不应误提取
    ("The answer is B", "B"),  # 英文也支持
    ("这题选D因为...", "D"),
]

# 模拟不同类型模型输出
MODEL_OUTPUT_SIMULATIONS = [
    # (描述, 输出文本, 正确答案, 预期评分结果)
    ("v1.0直接输出字母", "A", "A", True),
    ("v1.0中文标记", "故选C", "C", True),
    ("v1.0训练格式残留", "B 【考点】词义辨析", "B", True),
    ("v1.1 CoT完整输出", "【分析】本题考查万有引力。\n月球引力是地球的1/6。\n质量不随位置变化，重力随g变化。\n【答案】A", "A", True),
    ("v1.1 CoT+中文", "【分析】逐项分析选项...\nA选项×\nB选项√\n所以选B", "B", True),
    ("v1.1 长CoT末尾答案",
     "【分析】" + "这是一个非常详细的推理过程。" * 20 + "\n\n综上所述，正确答案是C。", "C", True),
    ("v1.1 输出混淆", "【分析】...A和B都不对，C是正确的。所以选择D。", "D", True),
    ("无答案字母", "这道题考查的是力学知识，需要计算...", "A", False),
    ("答案与预期不符", "B", "A", False),
    ("模型输出正确答案字母错误", "【分析】...【答案】C", "B", False),
]


def run_extraction_tests() -> tuple[int, int, list]:
    """运行答案提取测试"""
    passed, failed = 0, 0
    failures = []
    for text, expected in ANSWER_EXTRACTION_TESTS:
        result = extract_answer(text)
        if result == expected:
            passed += 1
        else:
            failed += 1
            failures.append((text, expected, result))
    return passed, failed, failures


def run_scoring_simulation() -> list:
    """模拟模型输出并验证评分逻辑"""
    results = []
    for desc, output, correct_answer, expected_score in MODEL_OUTPUT_SIMULATIONS:
        extracted = extract_answer(output)
        actual_score = (extracted == correct_answer)
        ok = (actual_score == expected_score)
        results.append({
            "description": desc,
            "output": output[:80],
            "correct": correct_answer,
            "extracted": extracted,
            "expected_score": expected_score,
            "actual_score": actual_score,
            "pass": ok,
        })
    return results


# ═══════════════════════════════════════════════════════
# 测试3: 批量运行能力
# ═══════════════════════════════════════════════════════
def test_batch_processing(questions: list):
    """测试批量处理能力（不加载模型，用模拟输出）"""
    import time
    t0 = time.time()

    # 模拟：每个题用3种不同输出格式测试
    formats = [
        lambda q: q["answer"],                          # 格式1: 直接输出字母
        lambda q: f"故选{q['answer']}",                  # 格式2: 中文标记
        lambda q: f"【分析】推理过程...\n【答案】{q['answer']}",  # 格式3: CoT
    ]

    results = {fmt_idx: {"correct": 0, "total": 0}
               for fmt_idx in range(len(formats))}

    for q in questions:
        for fmt_idx, fmt_func in enumerate(formats):
            output = fmt_func(q)
            extracted = extract_answer(output)
            results[fmt_idx]["total"] += 1
            if extracted == q["answer"]:
                results[fmt_idx]["correct"] += 1

    elapsed = time.time() - t0
    return results, elapsed


# ═══════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("Day 10: 评分逻辑100%验证")
    print("=" * 60)

    # 加载数据
    with open(BENCHMARK_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    all_ok = True

    # ── 测试1: 数据完整性 ──
    print(f"\n[1/4] 数据完整性验证 ({len(questions)}题)...")
    issues = verify_data_integrity(questions)
    if issues:
        print(f"  ❌ 发现 {len(issues)} 个问题:")
        for iss in issues[:15]:
            print(f"    - {iss}")
        all_ok = False
    else:
        print(f"  ✅ 全部通过 — 200题无数据问题")

    # 学科分布
    subjects = Counter(q["subject"] for q in questions)
    print(f"  学科分布: {dict(subjects)}")

    # ── 测试2: 答案提取 ──
    print(f"\n[2/4] 答案提取测试 ({len(ANSWER_EXTRACTION_TESTS)}项)...")
    passed, failed, failures = run_extraction_tests()
    print(f"  通过: {passed}/{len(ANSWER_EXTRACTION_TESTS)}")
    if failed > 0:
        print(f"  ❌ 失败: {failed}")
        for text, expected, result in failures:
            print(f"    '{text[:50]}' → {result} (预期{expected})")
        all_ok = False
    else:
        print(f"  ✅ 全部通过")

    # ── 测试3: 评分模拟 ──
    print(f"\n[3/4] 评分模拟测试 ({len(MODEL_OUTPUT_SIMULATIONS)}项)...")
    sim_results = run_scoring_simulation()
    sim_failed = [r for r in sim_results if not r["pass"]]
    if sim_failed:
        print(f"  ❌ 失败: {len(sim_failed)}")
        for r in sim_failed:
            print(f"    {r['description']}: 提取={r['extracted']}, "
                  f"期望评分={r['expected_score']}, 实际={r['actual_score']}")
        all_ok = False
    else:
        print(f"  ✅ 全部通过 — 评分逻辑正确")
    # 展示所有模拟结果
    for r in sim_results:
        status = "✅" if r["pass"] else "❌"
        print(f"    {status} {r['description']:20s}: '{r['output'][:50]}' → {r['extracted']} (正确={r['correct']})")

    # ── 测试4: 批量运行 ──
    print(f"\n[4/4] 批量运行测试 (200题 × 3格式)...")
    batch_results, elapsed = test_batch_processing(questions)
    print(f"  处理时间: {elapsed:.3f}s")
    for fmt_idx, (desc, res) in enumerate(zip(
        ["直接输出", "中文标记", "CoT输出"], batch_results.values()
    )):
        acc = res["correct"] / res["total"] * 100 if res["total"] else 0
        status = "✅" if acc == 100 else "❌"
        print(f"  {status} {desc}: {res['correct']}/{res['total']} = {acc:.0f}%")
        if acc != 100:
            all_ok = False

    # ── 总结 ──
    print(f"\n{'=' * 60}")
    if all_ok:
        print("🎉 评分逻辑验证: 100%通过!")
        print("  - 200题数据完整无问题")
        print("  - 答案提取覆盖所有格式")
        print("  - 评分逻辑正确无误")
        print("  - 批量处理能力正常")
    else:
        print("⚠️  存在问题需要修复 (见上方详情)")
    print(f"{'=' * 60}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
