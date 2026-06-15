# -*- coding: utf-8 -*-
"""
Qwen2.5-7B LoRA 推理 + Benchmark 评测
用法:
  python sft/infer_7b.py --model models/qwen7b-lora/final
  python sft/infer_7b.py --model models/qwen7b-lora/final --benchmark
  python sft/infer_7b.py --model ... --question "你的问题"
"""
import argparse, json, sys, time, re
from pathlib import Path
from collections import defaultdict

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

SYSTEM_PROMPT = "你是一个专业的中学学科答疑助手，请用简洁准确的语言回答问题。"
BENCHMARK_PATH = "data/clean_bench.json"


def load_model(model_path: str):
    """加载 LoRA 模型"""
    print(f"Loading model from {model_path}...")
    adapter_config = Path(model_path) / "adapter_config.json"

    if adapter_config.exists():
        # LoRA 模型: 先加载基座，再加适配器
        with open(adapter_config, encoding="utf-8") as f:
            import json as j
            ac = j.load(f)
        base_model = ac.get("base_model_name_or_path", "Qwen/Qwen2.5-7B-Instruct")
        print(f"  Base: {base_model}")

        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
        )
        model = PeftModel.from_pretrained(model, model_path)
        model = model.merge_and_unload()  # 合并加速推理
        print("  LoRA merged")
    else:
        # 完整模型
        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
        )

    model.eval()
    print(f"  Model loaded on {model.device}")
    return model, tokenizer


def generate(model, tokenizer, question: str, max_tokens: int = 128) -> str:
    """单次推理"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=[tokenizer.eos_token_id, 151645],
        )

    response = tokenizer.decode(
        outputs[0][len(inputs["input_ids"][0]):],
        skip_special_tokens=True,
    )
    return response.strip()


def extract_answer(text: str) -> str | None:
    """从输出提取答案字母"""
    if not text:
        return None
    text = text.strip()

    # 纯字母
    if len(text) <= 2 and text.upper() in "ABCD":
        return text.upper()

    # 各种答案标记
    patterns = [
        r'【答案】\s*([A-D])',
        r'故选[：:]?\s*([A-D])',
        r'答案为?\s*([A-D])',
        r'答案[：:]\s*([A-D])',
        r'(?:选|选择)\s*([A-D])',
        r'([A-D])\s*(?:选项|正确|符合)',
    ]
    for pat in patterns:
        matches = re.findall(pat, text)
        if matches:
            return matches[-1]

    # 末尾字母
    for ch in reversed(text):
        if ch.upper() in "ABCD":
            return ch.upper()

    return None


def benchmark(model, tokenizer, bench_path: str = BENCHMARK_PATH):
    """跑 Benchmark 评测"""
    with open(bench_path, encoding="utf-8") as f:
        questions = json.load(f)

    print(f"\nBenchmark: {len(questions)} 题")
    print(f"{'=' * 60}")

    correct = 0
    by_subject = defaultdict(lambda: {"correct": 0, "total": 0})
    errors = []

    t0 = time.time()
    for i, q in enumerate(questions):
        prompt = q["question"]
        if "options" in q:
            prompt += " " + " ".join(q["options"])

        pred = generate(model, tokenizer, prompt, max_tokens=64)
        pred_letter = extract_answer(pred)
        true_letter = q["answer"].strip().upper()
        is_correct = (pred_letter == true_letter)

        subj = q["subject"]
        by_subject[subj]["total"] += 1
        if is_correct:
            correct += 1
            by_subject[subj]["correct"] += 1
        else:
            errors.append({
                "id": q["id"], "subject": subj,
                "expected": true_letter, "predicted": pred_letter or "?",
                "question": q["question"][:100],
            })

        if (i + 1) % 50 == 0:
            acc = correct / (i + 1) * 100
            elapsed = time.time() - t0
            eta = elapsed / (i + 1) * (len(questions) - i - 1)
            print(f"  [{i+1}/{len(questions)}] acc={acc:.1f}%  ETA:{eta:.0f}s")

    elapsed = time.time() - t0
    acc = correct / len(questions) * 100

    print(f"\n{'=' * 60}")
    print(f"Benchmark 结果")
    print(f"{'=' * 60}")
    print(f"  总分: {correct}/{len(questions)} = {acc:.1f}%")
    print(f"  耗时: {elapsed:.0f}s ({elapsed/len(questions):.1f}s/题)")
    print(f"\n各学科:")
    for subj in ["math", "physics", "chemistry", "chinese", "english", "history", "politics"]:
        s = by_subject.get(subj)
        if s and s["total"] > 0:
            sacc = s["correct"] / s["total"] * 100
            bar = "█" * int(sacc / 4) + "░" * (25 - int(sacc / 4))
            print(f"  {subj:10s} {s['correct']:3d}/{s['total']:3d} = {sacc:5.1f}% {bar}")

    return acc, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="models/qwen7b-lora/final")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--question", type=str)
    parser.add_argument("--bench_path", default=BENCHMARK_PATH)
    args = parser.parse_args()

    model, tokenizer = load_model(args.model)

    if args.question:
        answer = generate(model, tokenizer, args.question)
        print(f"\nQ: {args.question}")
        print(f"A: {answer}")
    elif args.benchmark:
        benchmark(model, tokenizer, args.bench_path)
    else:
        # 交互模式
        print("\n交互模式 — 输入 quit 退出")
        while True:
            try:
                q = input("\n[Q] ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if q.lower() in ("quit", "exit", "q"):
                break
            if not q:
                continue
            answer = generate(model, tokenizer, q)
            print(f"[A] {answer}")


if __name__ == "__main__":
    main()
