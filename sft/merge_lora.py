# -*- coding: utf-8 -*-
"""
合并 LoRA 适配器到基座模型 → 导出完整 HF 模型
用法:
  python sft/merge_lora.py --lora models/qwen7b-lora/final --out models/qwen7b-merged
"""
import argparse, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lora", default="models/qwen7b-lora/final")
    parser.add_argument("--out", default="models/qwen7b-merged")
    args = parser.parse_args()

    import json
    with open(f"{args.lora}/adapter_config.json", encoding="utf-8") as f:
        ac = json.load(f)
    base_model = ac.get("base_model_name_or_path", "Qwen/Qwen2.5-7B-Instruct")
    print(f"Base: {base_model}")
    print(f"LoRA: {args.lora}")

    # 加载基座
    print("Loading base model...")
    model = AutoModelForCausalLM.from_pretrained(
        base_model, torch_dtype=torch.bfloat16,
        device_map="cpu", trust_remote_code=True,
    )

    # 加载 LoRA
    print("Loading LoRA adapter...")
    model = PeftModel.from_pretrained(model, args.lora)

    # 合并
    print("Merging...")
    model = model.merge_and_unload()

    # 保存
    print(f"Saving to {args.out}...")
    model.save_pretrained(args.out, safe_serialization=True)

    tokenizer = AutoTokenizer.from_pretrained(args.lora, trust_remote_code=True)
    tokenizer.save_pretrained(args.out)

    print(f"Done! Model at {args.out}")


if __name__ == "__main__":
    main()
