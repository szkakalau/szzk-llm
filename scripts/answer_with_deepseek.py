# -*- coding: utf-8 -*-
"""
Step 3a: DeepSeek API 批量回答 488 道无答案题目
纯文本选择题，DeepSeek 直接作答，验证答案在选项中

用法:
  python scripts/answer_with_deepseek.py --dry-run    # 测试 5 题
  python scripts/answer_with_deepseek.py               # 全量
  python scripts/answer_with_deepseek.py --resume      # 断点续传
"""
import json, os, sys, time, argparse
from openai import OpenAI

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

INPUT = "data/extracted_questions.json"
PROGRESS = "data/answer_progress.json"
OUTPUT = "data/extracted_questions_answered.json"

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"


def build_prompt(q: dict) -> str:
    """构建答题 prompt"""
    opts = "\n".join(q.get("options", []))
    return f"""请回答以下中学学科选择题，只输出答案字母（A/B/C/D），不要输出任何解释。

学科: {q.get('subject', 'unknown')}

题目: {q['question']}

选项:
{opts}

你的答案（仅输出字母）:"""


def call_deepseek(prompt: str) -> str | None:
    """调用 DeepSeek API"""
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=10,
            )
            ans = resp.choices[0].message.content.strip().upper()
            # 提取第一个 A-D 字母
            for ch in ans:
                if ch in "ABCD":
                    return ch
            return None
        except Exception as e:
            print(f"    API error (attempt {attempt+1}): {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if not API_KEY:
        print("请设置 DEEPSEEK_API_KEY 环境变量")
        return

    # 加载数据
    with open(INPUT, encoding="utf-8") as f:
        all_qs = json.load(f)

    # 筛选无答案题目（且选项完整）
    unlabeled = []
    for q in all_qs:
        ans = q.get("answer", "")
        opts = q.get("options", [])
        if (not ans or ans[0] not in "ABCD") and len(opts) >= 3:
            unlabeled.append(q)

    print(f"无答案题目: {len(unlabeled)}/{len(all_qs)}")

    if args.resume and os.path.exists(PROGRESS):
        with open(PROGRESS, encoding="utf-8") as f:
            progress = json.load(f)
        done = progress.get("done", [])
        pending = [q for q in unlabeled if q["question"][:60] not in
                   set(d["question"][:60] for d in done)]
        print(f"恢复: 已完成 {len(done)}, 待处理 {len(pending)}")
    else:
        done = []
        pending = unlabeled
        if args.dry_run:
            pending = pending[:5]
            print(f"DRY RUN: {len(pending)} 题")

    if not pending:
        print("全部完成!")
    else:
        success = 0
        for i, q in enumerate(pending):
            print(f"[{i+1}/{len(pending)}] {q['subject']}: {q['question'][:60]}...")
            prompt = build_prompt(q)
            ans = call_deepseek(prompt)
            if ans:
                q["answer"] = ans
                q["answer_source"] = "deepseek"
                success += 1
                print(f"  → {ans}")
            else:
                print(f"  → FAILED")

            done.append(q)
            # 保存进度
            os.makedirs(os.path.dirname(PROGRESS), exist_ok=True)
            with open(PROGRESS, "w", encoding="utf-8") as f:
                json.dump({"done": done + pending[i+1:]}, f, ensure_ascii=False)

            if i < len(pending) - 1:
                time.sleep(0.3)

        print(f"\n完成: {success}/{len(pending)}")

    # 合并回原数据
    with open(INPUT, encoding="utf-8") as f:
        all_qs = json.load(f)

    # 更新答案
    answered_map = {}
    for q in done:
        if q.get("answer") in "ABCD":
            key = q["question"][:60]
            answered_map[key] = q["answer"]

    count = 0
    for q in all_qs:
        key = q["question"][:60]
        if key in answered_map and (not q.get("answer") or q.get("answer") not in "ABCD"):
            q["answer"] = answered_map[key]
            q["answer_source"] = "deepseek"
            count += 1

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(all_qs, f, ensure_ascii=False, indent=2)

    # 统计
    with_ans = sum(1 for q in all_qs if q.get("answer") and q.get("answer") in "ABCD")
    print(f"\n最终: {len(all_qs)} 题, 含答案: {with_ans} (+{count})")
    print(f"已保存: {OUTPUT}")


if __name__ == "__main__":
    main()
