# -*- coding: utf-8 -*-
"""
Day 5: CoT (Chain of Thought) 数据生成脚本
用法:
  # 预览模式 — 只用前5题生成CoT，测试脚本和prompt
  python scripts/generate_cot.py --dry-run

  # 正式运行 — 采样200题生成CoT
  python scripts/generate_cot.py --api-key YOUR_KEY --base-url https://api.deepseek.com/v1

  # 指定模型和采样数量
  python scripts/generate_cot.py --model deepseek-chat --num 200 --api-key YOUR_KEY

  # 从进度文件恢复继续
  python scripts/generate_cot.py --resume data/v1.1/cot_progress.json --api-key YOUR_KEY

输出:
  data/v1.1/cot_progress.json  — 中间进度文件（支持断点续传）
  data/v1.1/train.json         — 最终数据集（原始367题 + 200 CoT增强题）
"""
import argparse, json, os, random, sys, time
from pathlib import Path
from typing import Optional

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ============================================================
# CoT 生成 Prompt
# ============================================================
COT_SYSTEM_PROMPT = """你是一位资深的中学教师，精通中考各学科的教学。你的任务是为题目生成详细的解题思路（Chain of Thought）。

请按以下格式输出，严格遵循：

【分析】一步一步推理这道题的解题过程。对于：
- 选择题：逐一分析每个选项为什么对或错，然后选出正确答案
- 填空题：展示计算过程、公式推导或逻辑推理
- 简答题：分层次、有条理地展开论述

【答案】给出最终答案（选项字母、数值、或完整表述）

注意：
1. 推理过程要像老师在课堂上讲解一样清晰易懂
2. 涉及计算的题目必须写出公式和步骤
3. 文科类题目要引用相关知识点
4. 答案必须与原始正确答案一致，不要改变答案内容"""


def load_train_data(path: str = "data/v1.0/train.json") -> list:
    """加载训练数据"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sample_questions(data: list, n: int = 200, seed: int = 42) -> list:
    """按学科比例分层采样"""
    random.seed(seed)

    # 按学科分组
    by_subject: dict[str, list] = {}
    for i, item in enumerate(data):
        subj = item.get("subject", "unknown")
        by_subject.setdefault(subj, []).append(i)

    # 按比例采样
    total = len(data)
    sampled = []
    for subj, indices in sorted(by_subject.items()):
        # 每科按比例分配名额，至少1题
        quota = max(1, round(n * len(indices) / total))
        quota = min(quota, len(indices))  # 不超过该科总题数
        chosen = random.sample(indices, quota)
        sampled.extend(chosen)
        print(f"  {subj}: {quota}/{len(indices)}")

    # 如果采样数量超过n，随机裁剪；不足则补全
    if len(sampled) > n:
        sampled = random.sample(sampled, n)
    elif len(sampled) < n:
        remaining = [i for i in range(total) if i not in sampled]
        extra = random.sample(remaining, min(n - len(sampled), len(remaining)))
        sampled.extend(extra)

    random.shuffle(sampled)
    print(f"  总计采样: {len(sampled)}/{total}")
    return [data[i] for i in sampled]


def build_cot_prompt(question: str, answer: str, subject: str) -> str:
    """构建生成CoT的用户提示"""
    return f"""学科：{subject}

题目：
{question}

正确答案：{answer}

请为这道题生成详细的解题思路分析。"""


def call_api(prompt: str, api_key: str, base_url: str, model: str,
             system_prompt: str = COT_SYSTEM_PROMPT,
             temperature: float = 0.3,
             max_tokens: int = 2048,
             max_retries: int = 3) -> Optional[str]:
    """调用 OpenAI 兼容 API 生成 CoT"""
    try:
        from openai import OpenAI
    except ImportError:
        print("  需要安装 openai 库: pip install openai")
        return None

    client = OpenAI(api_key=api_key, base_url=base_url)

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"    API调用失败 (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
    return None


def build_v1_1_dataset(original_data: list, cot_data: list) -> list:
    """
    构建 v1.1 数据集
    格式: {"question": "...", "answer": "...", "cot": "...(如有)", "subject": "..."}
    包含:
    - 原始367题（保持原格式）
    - CoT增强的200题（含cot字段）
    注意：同一道题如果出现在CoT中，会在数据集中出现两次：
    一次原版（不含cot），一次CoT版（含cot）。这样训练时模型能学到两种回答方式。
    """
    # 构建原始问题的索引 (question -> item)
    orig_set = set()
    result = []

    # 先添加所有原始数据（不含cot）
    for item in original_data:
        result.append({
            "question": item["question"],
            "answer": item["answer"],
            "subject": item.get("subject", "unknown"),
        })
        orig_set.add(item["question"].strip())

    # 添加CoT增强版本
    cot_count = 0
    for item in cot_data:
        q = item["question"].strip()
        # 检查这道题是否在原始数据中
        if q not in orig_set:
            print(f"  警告: CoT题目不在原始训练集中，跳过: {q[:60]}...")
            continue
        cot_count += 1
        result.append({
            "question": item["question"],
            "answer": item["answer"],
            "cot": item.get("cot", ""),
            "subject": item.get("subject", "unknown"),
        })

    print(f"  v1.1 数据集: {len(result)} 条 (原始 {len(original_data)} + CoT增强 {cot_count})")
    return result


def load_progress(progress_path: str) -> tuple[list, list]:
    """加载已有的进度文件"""
    with open(progress_path, encoding="utf-8") as f:
        data = json.load(f)
    done = [x for x in data if "cot" in x]
    pending = [x for x in data if "cot" not in x]
    return done, pending


def save_progress(data: list, path: str):
    """保存进度"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="生成 CoT 数据")
    parser.add_argument("--api-key", default=os.environ.get("DEEPSEEK_API_KEY", ""),
                        help="API Key (或设环境变量 DEEPSEEK_API_KEY)")
    parser.add_argument("--base-url", default="https://api.deepseek.com",
                        help="API 基础URL")
    parser.add_argument("--model", default="deepseek-chat", help="模型名称")
    parser.add_argument("--num", type=int, default=200, help="生成CoT的题目数")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--dry-run", action="store_true",
                        help="预览模式：只用5题测试流程")
    parser.add_argument("--resume", help="从进度文件恢复")
    parser.add_argument("--train-data", default="data/v1.0/train.json")
    parser.add_argument("--cot-output", default="data/v1.1/cot_progress.json")
    parser.add_argument("--final-output", default="data/v1.1/train.json")
    args = parser.parse_args()

    print("=" * 60)
    print("Day 5: CoT 数据生成")
    print("=" * 60)

    # ── 1. 加载/准备题目 ──
    if args.resume:
        print(f"\n[1/4] 从进度文件恢复: {args.resume}")
        done, pending = load_progress(args.resume)
        print(f"  已完成: {len(done)}, 待处理: {len(pending)}")
    else:
        print(f"\n[1/4] 加载训练数据并采样...")
        train_data = load_train_data(args.train_data)
        print(f"  训练集总数: {len(train_data)}")

        if args.dry_run:
            args.num = 5
            print("  [DRY RUN] 仅采样5题测试")

        sampled = sample_questions(train_data, args.num, args.seed)
        # 构建进度数据：每个item加上cot字段（先为空）
        done = []
        pending = [{
            "question": q["question"],
            "answer": q["answer"],
            "subject": q.get("subject", "unknown"),
        } for q in sampled]
        save_progress(pending, args.cot_output)
        print(f"  进度文件已保存: {args.cot_output}")

    if not pending:
        print("\n  所有题目已处理完毕！")
        # 直接跳到构建最终数据集
        cot_data = done
        train_data = load_train_data(args.train_data)
        final_data = build_v1_1_dataset(train_data, cot_data)
        save_progress(final_data, args.final_output)
        print(f"  最终数据集: {args.final_output} ({len(final_data)} 条)")
        return

    # ── 2. 调用API生成CoT ──
    print(f"\n[2/4] 生成 CoT ({len(pending)} 题待处理)...")

    if args.dry_run:
        print("  [DRY RUN] 不调用API，直接生成演示数据...")
        # dry-run: 用模板生成假的CoT用于测试
        for i, item in enumerate(pending):
            print(f"  [{i+1}/{len(pending)}] {item['subject']}: {item['question'][:60]}...")
            item["cot"] = f"【分析】这是{ item['subject'] }学科的题目。解题思路：...(此处需要API生成)\n【答案】{item['answer']}"
            item["cot_status"] = "placeholder"
            done.append(item)
            save_progress(done + pending[i+1:], args.cot_output)
        pending = []
        print(f"  [DRY RUN] 完成，cot_status=placeholder 表示需要API填充")
    elif not args.api_key:
        print("\n  [ERROR] 未提供 API Key！")
        print("  请通过 --api-key 参数或环境变量 DEEPSEEK_API_KEY 提供")
        print("  或者用 --dry-run 测试脚本流程")
        sys.exit(1)
    else:
        for i, item in enumerate(pending):
            print(f"\n  [{i+1}/{len(pending)}] {item['subject']}: {item['question'][:80]}...")
            prompt = build_cot_prompt(item["question"], item["answer"], item["subject"])
            cot = call_api(prompt, args.api_key, args.base_url, args.model)
            if cot:
                item["cot"] = cot
                item["cot_status"] = "generated"
                print(f"    OK ({len(cot)} chars)")
            else:
                item["cot"] = ""
                item["cot_status"] = "failed"
                print(f"    FAILED — 跳过")
            done.append(item)
            # 每完成一题就保存进度
            save_progress(done + pending[i+1:], args.cot_output)
            time.sleep(0.3)  # rate limiting

    # ── 3. 生成最终数据集 ──
    print(f"\n[3/4] 构建 v1.1 数据集...")
    train_data = load_train_data(args.train_data)
    cot_data = [x for x in done if x.get("cot") and x.get("cot_status") != "failed"]
    print(f"  CoT有效数据: {len(cot_data)}/{len(done)}")

    final_data = build_v1_1_dataset(train_data, cot_data)
    save_progress(final_data, args.final_output)
    print(f"  已保存: {args.final_output}")

    # ── 4. 统计 ──
    print(f"\n[4/4] 数据集统计:")
    with_cot = sum(1 for x in final_data if x.get("cot"))
    without_cot = len(final_data) - with_cot
    print(f"  总计: {len(final_data)} 条")
    print(f"  含CoT: {with_cot} 条")
    print(f"  无CoT: {without_cot} 条")

    subjects = {}
    for x in final_data:
        s = x.get("subject", "unknown")
        subjects[s] = subjects.get(s, 0) + 1
    for s, n in sorted(subjects.items()):
        print(f"    {s}: {n}")

    print(f"\n{'=' * 60}")
    print("Done! 下一步: 抽查质量 → Day 6: 第二次训练")
    print(f"  python sft/train.py --train_data {args.final_output}")


if __name__ == "__main__":
    main()
