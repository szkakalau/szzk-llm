# -*- coding: utf-8 -*-
"""
Day 16: DeepSeek API 深度错误分类
用法:
  python error_analysis/deep_classify.py --dry-run       # 测试模式 (3题)
  python error_analysis/deep_classify.py                 # 完整分类 (72题)
  python error_analysis/deep_classify.py --api-key KEY   # 指定API Key
  python error_analysis/deep_classify.py --resume        # 从进度恢复
  python error_analysis/deep_classify.py --only-persistent # 仅58道顽固错误

产出:
  error_analysis/classify_progress.json  — 中间进度文件
  error_analysis/classified_errors.json  — 最终分类结果
"""
import argparse, json, os, sys, time
from datetime import datetime
from typing import Optional

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

INPUT_PATH = "error_analysis/all_errors.json"
PROGRESS_PATH = "error_analysis/classify_progress.json"
OUTPUT_PATH = "error_analysis/classified_errors.json"

# ═══════════════════════════════════════════════════════
# 分类 Prompt — 要求 DeepSeek 做深度根因分析
# ═══════════════════════════════════════════════════════
CLASSIFY_SYSTEM_PROMPT = """你是一位资深的中考教学质量分析专家，擅长诊断AI模型在中学学科题目上的错误根因。

你的任务是对每道AI模型答错的题目进行深度分类。请从以下维度分析：

## 1. 错误大类 (category)
- **knowledge**: 知识性错误 — 模型缺乏相关知识或记忆了错误知识
- **logic**: 逻辑性错误 — 模型有相关知识但推理过程出错
- **format**: 格式性错误 — 模型知道答案但输出格式无法被解析
- **hallucination**: 幻觉错误 — 模型生成了与题目无关的内容

## 2. 错误子类 (sub_category)
Knowledge 子类:
- concept_misunderstanding: 概念理解偏差
- fact_error: 事实/知识点记忆错误
- formula_misapplication: 公式/定理误用
- terminology_confusion: 术语/定义混淆

Logic 子类:
- reasoning_chain_error: 推理链条断裂/方向错误
- trap_fall: 落入题目陷阱/被干扰项误导
- option_misreading: 选项内容理解偏差
- condition_miss: 遗漏关键条件或约束
- overthinking: 过度推理导致从正确走向错误

Format 子类:
- cot_unparseable: CoT冗长输出使答案无法提取
- wrong_output_pattern: 输出格式不符合选择题要求
- context_noise: 输出中包含训练数据噪声

Hallucination 子类:
- training_leakage: 训练数据格式残留(如输出解析内容)
- irrelevant_generation: 生成与题目无关的内容
- answer_fabrication: 编造不存在的选项或答案

## 3. 难度评估 (difficulty)
- easy: 基础送分题，模型不应该错
- medium: 需要一定理解和分析的题目
- hard: 需要深度推理或多知识点综合的题目

## 4. 根因分析 (root_cause)
用1-2句话精确描述模型为什么会错，要具体到题目内容。

## 5. 修复建议 (fix_suggestion)
针对这个具体错误，给出2-3条可操作的数据/训练改进建议。

请严格按以下 JSON 格式输出（不要加markdown代码块标记）:
{
  "category": "knowledge|logic|format|hallucination",
  "sub_category": "...",
  "difficulty": "easy|medium|hard",
  "root_cause": "...",
  "fix_suggestion": "...",
  "confidence": 0.0-1.0
}"""


def build_classify_prompt(error: dict) -> str:
    """为单个错误构建分类请求"""
    q = error["question"]
    opts = "\n".join(error.get("options", []))
    correct = error["correct_answer"]
    predicted = error["latest_model_answer"]
    subject = error["subject"]
    history = " | ".join(error.get("error_history", ["unknown"]))
    persistent = "是" if error.get("is_persistent") else "否"

    return f"""请分析以下AI模型答错的题目：

学科: {subject}
是否顽固错误(三版本全错): {persistent}
错误历史: {history}

【题目】
{q}

【选项】
{opts}

【正确答案】{correct}
【模型输出/预测】{predicted}

请进行深度分类，输出 JSON。"""


def call_deepseek(prompt: str, api_key: str, base_url: str, model: str,
                  max_retries: int = 3) -> Optional[str]:
    """调用 DeepSeek API (OpenAI 兼容接口)"""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,  # 低温度保证分类稳定性
                max_tokens=1024,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"    API错误 (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    return None


def parse_classification(raw: str) -> Optional[dict]:
    """从 DeepSeek 返回中提取 JSON 分类结果"""
    if not raw:
        return None
    raw = raw.strip()
    # 去除可能的 markdown 代码块标记
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        raw = "\n".join(lines)
    # 提取第一个完整 JSON 对象
    # 尝试直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # 尝试找到 {} 块
    import re
    m = re.search(r'\{[^{}]*"category"[^{}]*\}', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    # 尝试更宽松的匹配
    m = re.search(r'\{.*?\}', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


def load_progress(path: str) -> tuple[list, list]:
    """加载进度"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    done = [x for x in data if "deep_classification" in x]
    pending = [x for x in data if "deep_classification" not in x]
    return done, pending


def save_progress(data: list, path: str):
    """保存进度"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def print_summary(classified: list):
    """打印分类结果统计"""
    from collections import Counter

    total = len(classified)
    if not total:
        return

    categories = Counter(c["deep_classification"].get("category", "unknown")
                        for c in classified)
    sub_cats = Counter(c["deep_classification"].get("sub_category", "unknown")
                      for c in classified)
    difficulties = Counter(c["deep_classification"].get("difficulty", "unknown")
                         for c in classified)

    print(f"\n{'=' * 60}")
    print("D16 深度分类结果")
    print(f"{'=' * 60}")
    print(f"  已分类: {total} 题")

    print(f"\n  大类分布:")
    cat_labels = {"knowledge": "知识错误", "logic": "逻辑错误",
                  "format": "格式错误", "hallucination": "幻觉错误"}
    for cat, count in categories.most_common():
        label = cat_labels.get(cat, cat)
        bar = "█" * count
        print(f"    {label:8s} ({cat:15s}) {count:2d} {bar}")

    print(f"\n  子类分布 (Top 10):")
    for sub, count in sub_cats.most_common(10):
        print(f"    {sub:30s} {count:2d}")

    print(f"\n  难度分布:")
    diff_labels = {"easy": "基础送分", "medium": "中等难度", "hard": "高难度"}
    for diff, count in difficulties.most_common():
        label = diff_labels.get(diff, diff)
        print(f"    {label:8s} ({diff}) {count:2d}")

    # 按学科 × 大类交叉
    print(f"\n  学科 × 错误大类:")
    by_subj_cat = Counter(
        (c["subject"], c["deep_classification"].get("category", "?"))
        for c in classified
    )
    subjects = ["math", "physics", "chemistry", "chinese", "english", "history", "politics"]
    for subj in subjects:
        parts = []
        for cat in ["knowledge", "logic", "format", "hallucination"]:
            count = by_subj_cat.get((subj, cat), 0)
            if count:
                parts.append(f"{cat}={count}")
        if parts:
            print(f"    {subj:10s}: {', '.join(parts)}")


def main():
    parser = argparse.ArgumentParser(description="D16: DeepSeek API 深度错误分类")
    parser.add_argument("--api-key", default=os.environ.get("DEEPSEEK_API_KEY", ""),
                        help="DeepSeek API Key")
    parser.add_argument("--base-url", default="https://api.deepseek.com",
                        help="API Base URL")
    parser.add_argument("--model", default="deepseek-chat",
                        help="模型名称")
    parser.add_argument("--dry-run", action="store_true",
                        help="测试模式: 仅分类前3题")
    parser.add_argument("--resume", action="store_true",
                        help="从进度文件恢复")
    parser.add_argument("--only-persistent", action="store_true",
                        help="仅分类58道顽固错误")
    parser.add_argument("--input", default=INPUT_PATH,
                        help="输入文件")
    args = parser.parse_args()

    print("Day 16: DeepSeek API 深度错误分类")
    print("-" * 40)

    # ── 1. 加载错误数据 ──
    if args.resume and os.path.exists(PROGRESS_PATH):
        print(f"\n[1/3] 从进度文件恢复: {PROGRESS_PATH}")
        done, pending = load_progress(PROGRESS_PATH)
        print(f"  已分类: {len(done)}, 待处理: {len(pending)}")
    else:
        print(f"\n[1/3] 加载错误数据: {args.input}")
        with open(args.input, encoding="utf-8") as f:
            db = json.load(f)

        # 筛选当前打开的错误
        errors = [e for e in db["errors"] if e["current_status"] == "open"]

        # 可选：仅顽固错误
        if args.only_persistent:
            errors = [e for e in errors if e.get("is_persistent")]
            print(f"  仅顽固错误: {len(errors)} 题")
        else:
            print(f"  当前打开: {len(errors)} 题")
            persistent_count = sum(1 for e in errors if e.get("is_persistent"))
            print(f"  其中顽固: {persistent_count} 题")

        if args.dry_run:
            errors = errors[:3]
            print(f"  [DRY RUN] 仅测试 {len(errors)} 题")

        # 初始化进度数据
        done = []
        pending = errors
        save_progress(pending, PROGRESS_PATH)
        print(f"  进度文件: {PROGRESS_PATH}")

    if not pending:
        print("\n  所有题目已分类完毕!")
        save_progress(done, PROGRESS_PATH)
        classified = done
        print_summary(classified)
        # 保存最终结果
        save_progress(classified, OUTPUT_PATH)
        print(f"\n  最终结果: {OUTPUT_PATH}")
        return

    # ── 2. 调用 API 分类 ──
    if args.dry_run:
        print(f"\n[2/3] [DRY RUN] 模拟分类 {len(pending)} 题...")
        for i, item in enumerate(pending):
            print(f"  [{i+1}/{len(pending)}] "
                  f"#{item['id']} [{item['subject']}] "
                  f"ans={item['correct_answer']} pred={item['latest_model_answer']}")
            # 模拟分类结果
            item["deep_classification"] = {
                "category": item.get("latest_error_type", "logic"),
                "sub_category": "placeholder_dry_run",
                "difficulty": "medium",
                "root_cause": "[DRY RUN] 需要实际API调用",
                "fix_suggestion": "[DRY RUN] 需要实际API调用",
                "confidence": 0.0,
            }
            done.append(item)
            save_progress(done + pending[i+1:], PROGRESS_PATH)
        pending = []
    elif not args.api_key:
        print("\n  ❌ 未提供 API Key!")
        print("  请通过 --api-key 参数或环境变量 DEEPSEEK_API_KEY 提供")
        print("  或使用 --dry-run 测试脚本流程")
        sys.exit(1)
    else:
        print(f"\n[2/3] 调用 DeepSeek API ({args.model}) 分类 {len(pending)} 题...")
        success = 0
        failed = 0

        for i, item in enumerate(pending):
            qid = item["id"]
            subj = item["subject"]
            print(f"\n  [{i+1}/{len(pending)}] "
                  f"#{qid} [{subj}] "
                  f"ans={item['correct_answer']} pred={item['latest_model_answer']} "
                  f"persistent={item.get('is_persistent', False)}")

            prompt = build_classify_prompt(item)
            raw = call_deepseek(prompt, args.api_key, args.base_url, args.model)

            if raw:
                parsed = parse_classification(raw)
                if parsed:
                    item["deep_classification"] = parsed
                    item["_raw_response"] = raw[:200]  # 保留开头用于 debug
                    success += 1
                    cat = parsed.get("category", "?")
                    sub = parsed.get("sub_category", "?")
                    diff = parsed.get("difficulty", "?")
                    print(f"    ✅ {cat}/{sub} (难度={diff})")
                else:
                    # 解析失败，保留原始输出
                    item["deep_classification"] = {
                        "category": "parse_error",
                        "sub_category": "unknown",
                        "difficulty": "unknown",
                        "root_cause": f"[解析失败] 原始输出: {raw[:200]}",
                        "fix_suggestion": "需要人工审核",
                        "confidence": 0.0,
                    }
                    item["_raw_response"] = raw
                    failed += 1
                    print(f"    ⚠ 解析失败 (raw={raw[:80]}...)")
            else:
                item["deep_classification"] = {
                    "category": "api_error",
                    "sub_category": "unknown",
                    "difficulty": "unknown",
                    "root_cause": "API调用失败，需重试",
                    "fix_suggestion": "重新运行 --resume",
                    "confidence": 0.0,
                }
                failed += 1
                print(f"    ❌ API调用失败")

            done.append(item)
            save_progress(done + pending[i+1:], PROGRESS_PATH)

            if i < len(pending) - 1:
                time.sleep(0.5)  # rate limiting

        print(f"\n  完成: 成功 {success}, 失败 {failed}")

    # ── 3. 保存结果 ──
    print(f"\n[3/3] 保存结果...")
    classified = done

    # 检查是否有未分类的
    unclassified = [e for e in classified if "deep_classification" not in e]
    if unclassified:
        print(f"  ⚠ {len(unclassified)} 题未分类")

    save_progress(classified, PROGRESS_PATH)
    save_progress(classified, OUTPUT_PATH)
    print(f"  进度文件: {PROGRESS_PATH}")
    print(f"  最终结果: {OUTPUT_PATH}")

    # 汇总
    print_summary(classified)

    # ── 列出高优先级修复项 ──
    easy_errors = [e for e in classified
                   if e.get("deep_classification", {}).get("difficulty") == "easy"]
    if easy_errors:
        print(f"\n{'─' * 40}")
        print(f"🎯 基础送分题却错了 ({len(easy_errors)} 题) — 性价比最高的修复:")
        for e in easy_errors[:10]:
            dc = e.get("deep_classification", {})
            print(f"  #{e['id']} [{e['subject']:10s}] "
                  f"{dc.get('category','?')}/{dc.get('sub_category','?')}")
            print(f"    根因: {dc.get('root_cause', 'N/A')[:120]}")

    print(f"\n{'=' * 60}")
    print("Day 16 完成! 下一步: D17 人工审核 TOP 错误")
    print(f"  python error_analysis/deep_classify.py --resume  # 如需补充失败题目")


if __name__ == "__main__":
    main()
