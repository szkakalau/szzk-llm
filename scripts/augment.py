# -*- coding: utf-8 -*-
"""
数据扩增脚本 — DeepSeek API 批量生成题目变体
用法:
  python scripts/augment.py                          # 全量扩增
  python scripts/augment.py --test                   # 测试 (10题)
  python scripts/augment.py --resume                 # 断点续传
"""
import json, os, time, sys, argparse
from openai import OpenAI

MULT = {"math": 8, "physics": 6, "chemistry": 5, "english": 3, "politics": 2, "history": 2, "chinese": 2}
INPUT = "data/clean_train.json"
PROGRESS = "data/augment_progress.json"
OUTPUT = "data/augmented_train.json"


def augment(client, q, n):
    """用 DeepSeek API 为一道题生成 n 个变体"""
    if n <= 0:
        return []
    subj = q.get("subject", "unknown")
    prompt = (
        f"你是中学教育专家。为这道{subj}选择题生成{n}个变体。"
        f"保持知识点相同，只改数字/场景/选项内容。"
        f"每行一个JSON，不要其他内容：\n\n"
        f"原题：{q['question']}\n答案：{q['answer']}\n\n请输出{n}行JSON："
    )

    for _ in range(3):
        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8, max_tokens=2000,
            )
            text = resp.choices[0].message.content
            variants = []
            for line in text.strip().split("\n"):
                line = line.strip()
                if line.startswith("{") and "question" in line and "answer" in line:
                    try:
                        v = json.loads(line)
                        ans = str(v.get("answer", "")).strip()
                        if len(ans) >= 1 and ans[0] in "ABCD":
                            variants.append({
                                "question": v["question"],
                                "answer": ans[0],
                                "subject": subj,
                            })
                    except json.JSONDecodeError:
                        pass
            return variants[:n]
        except Exception as e:
            print(f"  API Error: {e}")
            time.sleep(2)
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="测试模式 (10题)")
    parser.add_argument("--resume", action="store_true", help="断点续传")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("请设置 DEEPSEEK_API_KEY 环境变量")
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    with open(INPUT, encoding="utf-8") as f:
        data = json.load(f)

    if args.test:
        data = data[:10]
        print(f"测试模式: {len(data)} 题")

    done = {}
    if args.resume and os.path.exists(PROGRESS) and os.path.getsize(PROGRESS) > 10:
        with open(PROGRESS, encoding="utf-8") as f:
            done = json.load(f)
        print(f"断点续传: {len(done)} 已完成")

    all_data = []
    for i, q in enumerate(data):
        key = q["question"][:60]
        subj = q.get("subject", "unknown")
        n = MULT.get(subj, 1)

        # 保留原题
        all_data.append({"question": q["question"], "answer": q["answer"], "subject": subj})

        # 已完成则复用
        if key in done:
            for v in done[key]:
                all_data.append(v)
            continue

        # 生成变体
        sys.stdout.write(f"[{i+1}/{len(data)}] {subj}: {q['question'][:30]}... ({n})\n")
        sys.stdout.flush()
        variants = augment(client, q, n)
        done[key] = variants
        for v in variants:
            all_data.append(v)

        # 每 10 题保存进度
        if (i + 1) % 10 == 0:
            with open(PROGRESS, "w", encoding="utf-8") as f:
                json.dump(done, f, ensure_ascii=False)
            with open(OUTPUT, "w", encoding="utf-8") as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)
            print(f"  [保存 {len(all_data)} 条]")

        time.sleep(0.3)

    # 最终保存
    with open(PROGRESS, "w", encoding="utf-8") as f:
        json.dump(done, f, ensure_ascii=False)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"\n完成! {len(data)} → {len(all_data)} 条 ({len(all_data)/len(data):.1f}x)")
    print(f"保存: {OUTPUT}")


if __name__ == "__main__":
    main()
