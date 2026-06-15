# -*- coding: utf-8 -*-
"""
Day 15: 错误数据库构建 — 合并 v1.0/v1.1/v1.2 三个版本的 Error Set
产出: error_analysis/all_errors.json (统一错误数据库, 为 D16 DeepSeek API 分类做准备)
用法: python error_analysis/build_error_db.py
"""
import json, os, sys
from collections import Counter, defaultdict
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BENCHMARK_PATH = "benchmark/test_set_v0.1.json"
ERROR_SETS = {
    "v1.0": "benchmark/error_set_v1.0.json",
    "v1.1": "benchmark/error_set_v1.1.json",
    "v1.2": "benchmark/error_set_v1.2.json",
}
OUTPUT_PATH = "error_analysis/all_errors.json"

# ═══════════════════════════════════════════════════════
# Step 1: 加载 Benchmark 题库
# ═══════════════════════════════════════════════════════
def load_benchmark(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        questions = json.load(f)
    return {q["id"]: q for q in questions}


# ═══════════════════════════════════════════════════════
# Step 2: 加载所有版本 Error Set
# ═══════════════════════════════════════════════════════
def load_error_sets(paths: dict) -> dict:
    result = {}
    for version, path in paths.items():
        if not os.path.exists(path):
            print(f"  ⚠ {version}: {path} 不存在, 跳过")
            result[version] = {"errors": []}
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        result[version] = data
        print(f"  {version}: {len(data['errors'])} entries "
              f"(open={data['total_errors']}, fixed={data['total_fixed']})")
    return result


# ═══════════════════════════════════════════════════════
# Step 3: 合并去重 — 建立统一错误索引
# ═══════════════════════════════════════════════════════
def merge_errors(version_data: dict, bench_lookup: dict) -> list:
    """
    以 question ID 为 key，合并所有版本中出现的错误。
    每条记录包含:
    - 题目完整信息 (从 benchmark 获取)
    - 各版本状态追踪 (v1.0_status, v1.1_status, v1.2_status)
    - 各版本模型答案和错误类型
    - 当前状态 (current_status) = 最新版本的 status
    """
    # 收集所有出现过的 question ID
    all_ids = set()
    for ver, data in version_data.items():
        for e in data.get("errors", []):
            all_ids.add(e["id"])

    # 按 ID 聚合
    by_id = defaultdict(lambda: {"versions": {}})
    for ver, data in version_data.items():
        for e in data.get("errors", []):
            qid = e["id"]
            by_id[qid]["versions"][ver] = {
                "status": e.get("status", "unknown"),
                "error_type": e.get("error_type", "unknown"),
                "model_answer": e.get("model_answer", "?"),
                "first_appeared": e.get("first_appeared"),
                "fixed_in": e.get("fixed_in"),
            }

    # 构建统一记录
    unified = []
    for qid in sorted(all_ids):
        entry = by_id[qid]
        bench_q = bench_lookup.get(qid)
        if not bench_q:
            print(f"  ⚠ ID={qid}: 不在 benchmark 题库中, 跳过")
            continue

        # 版本状态摘要
        versions = entry["versions"]
        v_status = {}
        for ver in ["v1.0", "v1.1", "v1.2"]:
            if ver in versions:
                v_status[ver] = versions[ver]["status"]
            else:
                v_status[ver] = "not_tested"

        # 当前状态：按最新版本判定
        if "v1.2" in versions:
            current_status = versions["v1.2"]["status"]
        elif "v1.1" in versions:
            current_status = versions["v1.1"]["status"]
        elif "v1.0" in versions:
            current_status = versions["v1.0"]["status"]
        else:
            current_status = "unknown"

        # 首次出现和修复版本
        first_ver = None
        fixed_ver = None
        for ver in ["v1.0", "v1.1", "v1.2"]:
            if ver in versions:
                v = versions[ver]
                if first_ver is None:
                    first_ver = v.get("first_appeared") or ver
                if v.get("status") == "fixed" and fixed_ver is None:
                    fixed_ver = v.get("fixed_in") or ver

        # 最新版本的错误类型和模型答案
        latest_ver = sorted([v for v in versions.keys()], reverse=True)[0]
        latest_error_type = versions[latest_ver].get("error_type", "unknown")
        latest_model_answer = versions[latest_ver].get("model_answer", "?")

        # 错误历史摘要
        error_history = []
        for ver in ["v1.0", "v1.1", "v1.2"]:
            if ver in versions:
                v = versions[ver]
                error_history.append(
                    f"{ver}:{v['status']}"
                    f"(pred={v['model_answer']}, err={v['error_type']})"
                )

        unified.append({
            "id": qid,
            "subject": bench_q["subject"],
            # 完整题目信息
            "question": bench_q["question"],
            "options": bench_q.get("options", []),
            "correct_answer": bench_q["answer"],
            # 版本状态
            "version_status": v_status,
            "current_status": current_status,
            "first_appeared": first_ver or "unknown",
            "fixed_in": fixed_ver,
            # 最新错误分析
            "latest_error_type": latest_error_type,
            "latest_model_answer": latest_model_answer,
            # 历史追踪
            "error_history": error_history,
            # 持久性标记
            "is_persistent": all(
                v_status.get(ver, "not_tested") == "open"
                for ver in ["v1.0", "v1.1", "v1.2"]
                if v_status.get(ver) != "not_tested"
            ),
            "is_new_in_v1_2": (
                v_status.get("v1.2") == "open"
                and v_status.get("v1.0", "not_tested") == "not_tested"
                and v_status.get("v1.1", "not_tested") != "open"
            ),
        })

    return unified


# ═══════════════════════════════════════════════════════
# Step 4: 统计分析
# ═══════════════════════════════════════════════════════
def analyze(unified: list) -> dict:
    total = len(unified)
    currently_open = [e for e in unified if e["current_status"] == "open"]
    currently_fixed = [e for e in unified if e["current_status"] == "fixed"]
    persistent = [e for e in unified if e["is_persistent"]]
    new_in_v12 = [e for e in unified if e["is_new_in_v1_2"]]

    # 各版本"当时"的 open 数量 (从 version_status 字段看)
    open_by_ver = defaultdict(int)
    for e in unified:
        for ver, status in e["version_status"].items():
            if status == "open":
                open_by_ver[ver] += 1

    return {
        "total_unique_errors": total,
        "currently_open": len(currently_open),
        "currently_fixed": len(currently_fixed),
        "persistent_errors": len(persistent),
        "new_in_v1_2": len(new_in_v12),
        "open_by_subject": dict(Counter(e["subject"] for e in currently_open)),
        "open_by_type": dict(Counter(e["latest_error_type"] for e in currently_open)),
        "persistent_by_subject": dict(Counter(e["subject"] for e in persistent)),
        "open_count_by_version": dict(open_by_ver),
    }


def print_report(analysis: dict):
    print(f"\n{'=' * 60}")
    print("Day 15: 错误数据库构建完成")
    print(f"{'=' * 60}")

    print(f"\n📊 总览:")
    print(f"  历史总计出现过错误: {analysis['total_unique_errors']} 道题 (至少一个版本错过)")
    print(f"  当前仍打开: {analysis['currently_open']}")
    print(f"  已修复: {analysis['currently_fixed']}")

    print(f"\n🔴 顽固错误 (所有版本都错过): {analysis['persistent_errors']}")
    if analysis["persistent_by_subject"]:
        print(f"  学科分布: {analysis['persistent_by_subject']}")

    print(f"\n🆕 v1.2 新引入错误: {analysis['new_in_v1_2']}")

    print(f"\n📈 各版本 open 数量变化:")
    for ver in ["v1.0", "v1.1", "v1.2"]:
        count = analysis["open_count_by_version"].get(ver, "N/A")
        print(f"  {ver}: {count} open")

    print(f"\n📚 当前打开错误 - 学科分布:")
    for subj, count in sorted(analysis["open_by_subject"].items(), key=lambda x: -x[1]):
        bar = "█" * count
        print(f"  {subj:10s} {count:2d} {bar}")

    print(f"\n🏷 当前打开错误 - 类型分布:")
    type_labels = {"knowledge": "知识错误", "logic": "逻辑错误",
                   "format": "格式错误", "hallucination": "幻觉错误"}
    for t, count in sorted(analysis["open_by_type"].items(), key=lambda x: -x[1]):
        label = type_labels.get(t, t)
        print(f"  {label} ({t}): {count}")


# ═══════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════
def main():
    print("Day 15: 错误数据库构建")
    print("-" * 40)

    # 1. 加载 benchmark
    print("\n[1/4] 加载 Benchmark 题库...")
    bench = load_benchmark(BENCHMARK_PATH)
    print(f"  {len(bench)} 题")

    # 2. 加载所有 Error Set
    print("\n[2/4] 加载各版本 Error Set...")
    version_data = load_error_sets(ERROR_SETS)

    # 3. 合并去重
    print("\n[3/4] 合并去重...")
    unified = merge_errors(version_data, bench)

    # 4. 分析
    print("\n[4/4] 统计分析...")
    stats = analyze(unified)

    # 构建最终输出
    output = {
        "meta": {
            "description": "SZZKLLM 统一错误数据库 — 合并 v1.0/v1.1/v1.2 所有错误记录",
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "benchmark": "test_set_v0.1 (200题)",
            "versions_included": list(ERROR_SETS.keys()),
            "ready_for": "D16: DeepSeek API 深度错误分类",
        },
        "statistics": stats,
        "errors": unified,
    }

    # 保存
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已保存: {OUTPUT_PATH} ({len(unified)} 条错误记录)")

    # 打印报告
    print_report(stats)

    # ── 顽固错误清单 ──
    persistent = [e for e in unified if e["is_persistent"]]
    if persistent:
        print(f"\n{'─' * 40}")
        print("🔴 顽固错误 (所有版本均错) — 优先关注：")
        for e in persistent:
            q = e["question"][:80].replace("\n", " ")
            print(f"  #{e['id']} [{e['subject']:10s}] "
                  f"正确={e['correct_answer']} "
                  f"v1.2预测={e['latest_model_answer']} "
                  f"[{e['latest_error_type']}]")
            print(f"    历史: {' | '.join(e['error_history'])}")
            print(f"    Q: {q}...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
