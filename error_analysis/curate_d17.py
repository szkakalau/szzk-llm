# -*- coding: utf-8 -*-
"""
Day 17: 人工审核 DeepSeek 分类结果 + 优先级标注 + 错误模式聚类
用法: python error_analysis/curate_d17.py
产出: error_analysis/curated_errors.json — 审核后的优先修复清单
"""
import json, os, sys
from collections import Counter, defaultdict
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

INPUT_PATH = "error_analysis/classified_errors.json"
BENCHMARK_PATH = "benchmark/test_set_v0.1.json"
OUTPUT_PATH = "error_analysis/curated_errors.json"


def load_data():
    with open(INPUT_PATH, encoding="utf-8") as f:
        classified = json.load(f)
    with open(BENCHMARK_PATH, encoding="utf-8") as f:
        bench = {q["id"]: q for q in json.load(f)}
    return classified, bench


# ═══════════════════════════════════════════════════════
# 审核规则引擎
# ═══════════════════════════════════════════════════════
def review_classification(error: dict, bench_q: dict) -> dict:
    """
    审核 DeepSeek 分类并返回审核意见。
    自动标记以下需要人工关注的情况:
    1. 概念误标: 明明是知识缺失却被标为 logic
    2. 难度误标: 涉及多步推理的标为 easy
    3. 格式类被低估: pred=? 但没有标为 format
    4. 噪声数据: question 包含非题目内容
    """
    dc = error.get("deep_classification", {})
    category = dc.get("category", "unknown")
    sub = dc.get("sub_category", "unknown")
    diff = dc.get("difficulty", "unknown")
    root_cause = dc.get("root_cause", "")
    fix = dc.get("fix_suggestion", "")
    pred = error.get("latest_model_answer", "?")
    ans = error.get("correct_answer", "?")
    question = error.get("question", "")

    review = {
        "category_ok": True,
        "sub_category_ok": True,
        "difficulty_ok": True,
        "warnings": [],
        "corrected_category": None,
        "corrected_sub": None,
        "corrected_difficulty": None,
        "priority": "P1",
        "priority_reason": "",
        "data_quality": "clean",  # clean / noisy / needs_fix
    }

    # ── Rule 1: pred=? 但 category 不是 format ──
    if pred == "?" and category != "format":
        review["warnings"].append(
            f"模型输出无法解析(pred=?)但分类为{category}/{sub}，应检查是否为格式问题"
        )
        review["corrected_category"] = "format"
        review["corrected_sub"] = "cot_unparseable"

    # ── Rule 2: 明确的概念题被标为 logic ──
    concept_questions = ["下列", "属于", "正确", "错误", "不正确", "没有", "有",
                         "概念", "定义", "性质", "正确的是", "错误的是", "说法",
                         "What", "Which", "Who", "When"]
    has_option_pattern = any(kw in question for kw in ["A.", "B.", "C.", "D."])
    is_concept_judgement = any(kw in question for kw in concept_questions)

    if is_concept_judgement and category == "logic" and diff == "easy":
        review["warnings"].append(
            "基础概念判断题被标为logic，考虑是否应归为knowledge/concept_misunderstanding"
        )

    # ── Rule 3: 噪声检测 ──
    noise_markers = ["解析：", "故选", "【考点】", "一、单选题", "一、选择题",
                     "本卷可能用到", "考试时间", "说明：本卷", "故选：",
                     "．",  # 全角句点出现在题首
                     ]
    noise_count = sum(1 for marker in noise_markers if marker in question[:80])
    if noise_count >= 2:
        review["data_quality"] = "noisy"
        review["warnings"].append(
            f"题目文本包含训练数据噪声(检测到{noise_count}个噪声标记)，可能影响模型判断"
        )

    # ── Rule 4: 知识点重复出现在错误集中 ──
    # (handled at aggregate level)

    # ── Rule 5: 优先级判定 ──
    # P0: easy + concept_misunderstanding → 基础送分 → 必须修复
    if diff == "easy" and sub in ("concept_misunderstanding", "fact_error"):
        review["priority"] = "P0"
        review["priority_reason"] = "基础送分题因概念/知识缺失而错误，修复成本低收益高"
    elif diff == "easy" and sub in ("trap_fall", "reasoning_chain_error"):
        review["priority"] = "P0"
        review["priority_reason"] = "简单题因推理/陷阱而错误，说明基本推理能力缺失"
    elif diff == "medium" and sub in ("concept_misunderstanding", "fact_error"):
        review["priority"] = "P1"
        review["priority_reason"] = "中等难度概念题，需补充针对性训练数据"
    elif diff == "medium":
        review["priority"] = "P1"
        review["priority_reason"] = "中等难度题目，常规优化可解决"
    elif diff == "hard":
        review["priority"] = "P2"
        review["priority_reason"] = "高难度题，投入产出比低，可后期处理"
    else:
        review["priority"] = "P1"

    # ── Rule 6: 判断题干是否清晰 ──
    # 题干少于20字的通常是简短判断，分类应该直接
    if len(question) < 20 and category == "logic":
        review["warnings"].append("超短题干被标为logic，可能不需要深度推理")

    return review


# ═══════════════════════════════════════════════════════
# 错误模式聚类
# ═══════════════════════════════════════════════════════
def cluster_by_pattern(errors: list) -> list[dict]:
    """将错误按根因模式聚类，找出可以批量修复的组"""
    patterns = defaultdict(list)

    for e in errors:
        dc = e.get("deep_classification", {})
        subj = e["subject"]
        cat = dc.get("category", "?")
        sub = dc.get("sub_category", "?")

        # 构建模式键
        if sub == "concept_misunderstanding":
            # 按学科+概念大类分组
            key = f"{subj}:概念理解偏差"
        elif sub == "trap_fall":
            key = f"{subj}:落入陷阱"
        elif sub == "reasoning_chain_error":
            key = f"{subj}:推理链错误"
        elif sub in ("fact_error", "formula_misapplication"):
            key = f"{subj}:知识/公式记忆"
        elif cat == "format":
            key = "跨学科:格式问题"
        else:
            key = f"{subj}:其他({sub})"

        patterns[key].append(e["id"])

    # 按组大小排序
    clusters = []
    for key, ids in sorted(patterns.items(), key=lambda x: -len(x[1])):
        clusters.append({
            "pattern": key,
            "count": len(ids),
            "error_ids": sorted(ids),
            "fix_approach": suggest_fix_approach(key, len(ids)),
        })

    return clusters


def suggest_fix_approach(pattern: str, count: int) -> str:
    if "概念理解偏差" in pattern:
        return (f"批量补充{count}道基础概念辨析题到训练集，"
                "每道题包含该概念的正反例对比")
    elif "落入陷阱" in pattern:
        return (f"为{count}道题创建'陷阱变体'：原题 + 故意设置相似干扰项的版本，"
                "训练模型识别常见陷阱模式")
    elif "推理链错误" in pattern:
        return (f"为{count}道题补充完整的CoT推理过程，"
                "每步推理标注'为什么这一步是对的'")
    elif "知识/公式记忆" in pattern:
        return (f"创建{count}道知识点记忆卡，"
                "将公式/定理以QA对形式加入训练集")
    elif "格式问题" in pattern:
        return ("统一修复所有格式错误：在训练数据中加入明确的输出格式指令，"
                "如'请直接输出选项字母，不要输出解析过程'")
    return "逐题人工修复"


# ═══════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════
def main():
    print("Day 17: 人工审核 TOP 错误")
    print("=" * 60)

    classified, bench = load_data()
    errors = [e for e in classified if "deep_classification" in e]
    print(f"\n加载 {len(errors)} 道已分类错误")

    # ── 逐题审核 ──
    print(f"\n[1/4] 逐题审核...")
    reviewed = []
    review_stats = Counter()

    for e in errors:
        qid = e["id"]
        bq = bench.get(qid, {})
        review = review_classification(e, bq)

        curated = {
            **e,
            "review": review,
        }
        reviewed.append(curated)
        review_stats["total"] += 1
        if review["warnings"]:
            review_stats["with_warnings"] += 1
        if review["data_quality"] == "noisy":
            review_stats["noisy_questions"] += 1
        if review["priority"] == "P0":
            review_stats["p0"] += 1
        elif review["priority"] == "P1":
            review_stats["p1"] += 1
        else:
            review_stats["p2"] += 1

    print(f"  审核完成: {review_stats['total']} 题")
    print(f"  有警告: {review_stats.get('with_warnings', 0)} 题")
    print(f"  噪声数据: {review_stats.get('noisy_questions', 0)} 题")
    print(f"  P0: {review_stats.get('p0', 0)}, "
          f"P1: {review_stats.get('p1', 0)}, "
          f"P2: {review_stats.get('p2', 0)}")

    # ── 聚类分析 ──
    print(f"\n[2/4] 错误模式聚类...")
    clusters = cluster_by_pattern(reviewed)
    for c in clusters:
        bar = "█" * c["count"]
        print(f"  {c['pattern']:30s} {c['count']:2d} {bar}")
        print(f"    修复方案: {c['fix_approach'][:100]}")

    # ── 打印需关注的警告 ──
    print(f"\n[3/4] 分类需纠正的题目:")
    warnings_found = [e for e in reviewed if e["review"]["warnings"]]
    if warnings_found:
        for e in warnings_found[:15]:
            qid = e["id"]
            dc = e.get("deep_classification", {})
            review = e["review"]
            print(f"\n  ⚠ #{qid} [{e['subject']}] "
                  f"原分类={dc.get('category','?')}/{dc.get('sub_category','?')}")
            for w in review["warnings"]:
                print(f"    {w}")
            if review["corrected_category"]:
                print(f"    → 建议纠正为: {review['corrected_category']}/"
                      f"{review.get('corrected_sub', review['corrected_category'])}")
        if len(warnings_found) > 15:
            print(f"\n  ... 还有 {len(warnings_found)-15} 题")
    else:
        print("  ✅ 无需要纠正的分类")

    # ── P0 优先修复清单 ──
    print(f"\n[4/4] P0 优先修复清单:")
    p0_list = sorted(
        [e for e in reviewed if e["review"]["priority"] == "P0"],
        key=lambda e: (e["subject"], e["id"])
    )
    # 按学科分组
    by_subj = defaultdict(list)
    for e in p0_list:
        by_subj[e["subject"]].append(e)

    for subj in ["math", "physics", "chemistry", "chinese", "english", "history", "politics"]:
        items = by_subj.get(subj, [])
        if items:
            print(f"\n  {subj} ({len(items)} 题):")
            for e in items:
                dc = e.get("deep_classification", {})
                review = e["review"]
                q = e["question"][:80].replace("\n", " ")
                print(f"    #{e['id']:3d} [{dc.get('category','?'):10s}/{dc.get('sub_category','?'):25s}] "
                      f"ans={e['correct_answer']} pred={e['latest_model_answer']}")
                if review["data_quality"] == "noisy":
                    print(f"         ⚠ 噪声数据: {q[:60]}...")
                else:
                    print(f"         Q: {q}...")

    # ── 保存 ──
    output = {
        "meta": {
            "description": "D17 人工审核结果 — 带优先级和修复群组的错误清单",
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": INPUT_PATH,
            "ready_for": "D18: 根因分析报告 + D19: 优化方案设计",
        },
        "review_stats": {
            "total_reviewed": review_stats["total"],
            "with_warnings": review_stats.get("with_warnings", 0),
            "noisy_questions": review_stats.get("noisy_questions", 0),
            "p0_count": review_stats.get("p0", 0),
            "p1_count": review_stats.get("p1", 0),
            "p2_count": review_stats.get("p2", 0),
            "categories_corrected": len(warnings_found),
        },
        "fix_clusters": clusters,
        "errors": reviewed,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已保存: {OUTPUT_PATH}")

    # ── 汇总 ──
    print(f"\n{'=' * 60}")
    print("Day 17 审核汇总")
    print(f"{'=' * 60}")
    print(f"  审核: {review_stats['total']} 题")
    print(f"  P0 (必须修复): {review_stats.get('p0', 0)} 题")
    print(f"  P1 (应该修复): {review_stats.get('p1', 0)} 题")
    print(f"  P2 (可以延后): {review_stats.get('p2', 0)} 题")
    print(f"  噪声数据: {review_stats.get('noisy_questions', 0)} 题")
    print(f"  分类纠正: {len(warnings_found)} 题")
    print(f"  修复群组: {len(clusters)} 组")
    print(f"\n下一步: D18 根因分析报告 (基于 D17 审核结果)")


if __name__ == "__main__":
    main()
