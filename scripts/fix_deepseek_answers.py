# -*- coding: utf-8 -*-
"""
Step 3: 从解析卷提取标准答案替换 DeepSeek 答案
策略: 重新解析原 docx 文件的答案区, 用 "题号.答案字母" 格式匹配
"""
import json, re, sys
from pathlib import Path
from collections import defaultdict
from docx import Document

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

INPUT = "data/extracted_questions_answered.json"
EXAM_DIR = Path("exam-papers")

with open(INPUT, encoding="utf-8") as f:
    all_qs = json.load(f)

# 找 DeepSeek 答案
ds_qs = [q for q in all_qs if q.get("answer_source") == "deepseek"]
print(f"DeepSeek 答案: {len(ds_qs)}/{len(all_qs)}")
by_subj = defaultdict(int)
for q in ds_qs:
    by_subj[q["subject"]] += 1
print(f"学科分布: {dict(by_subj)}")

# 按源文件分组
by_file = defaultdict(list)
for q in ds_qs:
    src = q.get("source", "")
    if src:
        by_file[src].append(q)
print(f"涉及文件: {len(by_file)}")

# 对每个文件, 找到并解析标准答案
fixed = 0
not_found = 0

for filename, questions in by_file.items():
    # 找对应的 docx 文件
    docx_path = None
    for d in EXAM_DIR.rglob("*.docx"):
        if d.name == filename:
            docx_path = d
            break

    if not docx_path:
        print(f"  ⚠ 文件未找到: {filename}")
        not_found += len(questions)
        continue

    try:
        doc = Document(str(docx_path))
        paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    except:
        not_found += len(questions)
        continue

    # 找答案区
    answer_start = len(paras)
    for i, t in enumerate(paras):
        if "参考答案" in t or "试题解析" in t or "答案与解析" in t:
            answer_start = i
            break
    # 如果没找到, 从后20%开始找
    if answer_start >= len(paras):
        answer_start = max(0, int(len(paras) * 0.8))

    answer_paras = paras[answer_start:]

    # 提取 "题号.答案" 或 "题号．答案" 格式
    standard_answers = {}
    for text in answer_paras:
        pairs = re.findall(r'(\d+)\s*[\.、．]\s*([A-D])\b', text)
        for qnum_str, letter in pairs:
            qnum = int(qnum_str)
            if qnum not in standard_answers:
                standard_answers[qnum] = letter

    if not standard_answers:
        # 也尝试全文搜索
        for text in paras:
            pairs = re.findall(r'(\d+)\s*[\.、．]\s*([A-D])\b', text)
            for qnum_str, letter in pairs:
                qnum = int(qnum_str)
                if qnum not in standard_answers:
                    standard_answers[qnum] = letter

    if standard_answers:
        file_fixed = 0
        for i, q in enumerate(questions):
            qnum = i + 1  # 第N题
            if qnum in standard_answers:
                old_ans = q.get("answer", "?")
                new_ans = standard_answers[qnum]
                if old_ans != new_ans:
                    q["answer"] = new_ans
                    q["answer_source"] = "standard"
                    file_fixed += 1
                    fixed += 1
        if file_fixed > 0:
            print(f"  [{filename[:50]}] 修复 {file_fixed}/{len(questions)} 题")
    else:
        not_found += len(questions)

print(f"\n修复: {fixed}, 仍未找到标准答案: {not_found}")

# 保存
OUTPUT = "data/extracted_questions_fixed.json"
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(all_qs, f, ensure_ascii=False, indent=2)

# 统计最终状态
ds_left = sum(1 for q in all_qs if q.get("answer_source") == "deepseek")
std = sum(1 for q in all_qs if q.get("answer_source") in ("standard", "original"))
print(f"最终: 标准答案 {std}, DeepSeek答案 {ds_left}")
print(f"已保存: {OUTPUT}")
