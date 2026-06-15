# -*- coding: utf-8 -*-
"""
Qwen2.5-7B LoRA 训练脚本 — RTX 4090 24GB 优化版
用法:
  python sft/train_7b.py                          # 默认配置
  python sft/train_7b.py --epochs 5 --batch 8     # 自定义参数
  python sft/train_7b.py --test                   # 测试 (10条数据, 1步)

输出: models/qwen7b-lora/final/
"""
import argparse, json, os, sys, gc
from pathlib import Path

import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM, AutoTokenizer,
    TrainingArguments, BitsAndBytesConfig,
)
from peft import LoraConfig, get_peft_model, TaskType, PeftModel
from trl import SFTTrainer

# ═══════════════════════════════════════════════
# 默认配置 — RTX 4090 24GB 优化
# ═══════════════════════════════════════════════
CONFIG = {
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "train_data": "data/clean_train.json",
    "output_dir": "models/qwen7b-lora",
    "epochs": 3,
    "batch_size": 4,
    "gradient_accumulation": 2,        # effective batch = 8
    "learning_rate": 2e-4,             # LoRA 推荐 1e-4 ~ 3e-4
    "warmup_ratio": 0.05,
    "max_seq_length": 1024,
    "save_steps": 200,
    "logging_steps": 10,
    # LoRA
    "lora_r": 64,
    "lora_alpha": 128,
    "lora_dropout": 0.05,
    "lora_target_modules": [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
    # System
    "use_gradient_checkpointing": True,
    "bf16": True,
    "tf32": True,
}

SYSTEM_PROMPT = "你是一个专业的中学学科答疑助手，请用简洁准确的语言回答问题。"


def check_gpu():
    """检查 GPU 环境"""
    if not torch.cuda.is_available():
        print("❌ CUDA 不可用! 请检查 GPU 环境")
        sys.exit(1)

    gpu_name = torch.cuda.get_device_name(0)
    vram = torch.cuda.get_device_properties(0).total_mem / 1e9
    print(f"GPU: {gpu_name} ({vram:.1f} GB)")

    if vram < 20:
        print(f"⚠ VRAM {vram:.1f}GB 偏小，建议用 QLoRA")
        print("  添加 --qlora 参数启用 4bit 量化")
    return vram


def load_data(train_path: str, test_mode: bool = False):
    """加载训练数据"""
    with open(train_path, encoding="utf-8") as f:
        raw = json.load(f)

    if test_mode:
        raw = raw[:10]

    # 格式化为 ChatML
    formatted = []
    for item in raw:
        formatted.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": item["question"]},
                {"role": "assistant", "content": item["answer"]},
            ]
        })

    dataset = Dataset.from_list(formatted)

    # 简单划分: 95% 训练, 5% 验证
    split = dataset.train_test_split(test_size=0.05, seed=42)
    print(f"训练集: {len(split['train'])} 条, 验证集: {len(split['test'])} 条")

    # 按学科统计
    subjects = {}
    for item in raw:
        s = item.get("subject", "unknown")
        subjects[s] = subjects.get(s, 0) + 1
    print("学科分布:", {k: v for k, v in sorted(subjects.items())})

    return split["train"], split["test"]


def main():
    parser = argparse.ArgumentParser(description="Qwen2.5-7B LoRA 训练")
    parser.add_argument("--test", action="store_true", help="测试模式 (10条)")
    parser.add_argument("--qlora", action="store_true", help="用 QLoRA 4bit (显存<20GB)")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--lora_r", type=int, default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--train_data", default=None)
    parser.add_argument("--output_dir", default=None)
    args = parser.parse_args()

    # 合并参数
    cfg = CONFIG.copy()
    for key in ["epochs", "lora_r"]:
        val = getattr(args, key, None)
        if val is not None:
            cfg[key] = val
    if args.batch:
        cfg["batch_size"] = args.batch
    if args.lr:
        cfg["learning_rate"] = args.lr
    if args.model:
        cfg["model"] = args.model
    if args.train_data:
        cfg["train_data"] = args.train_data
    if args.output_dir:
        cfg["output_dir"] = args.output_dir

    print("=" * 60)
    print("Qwen2.5-7B LoRA 训练")
    print("=" * 60)

    # ── 0. 环境检查 ──
    print("\n[0/5] GPU 检查...")
    vram = check_gpu()

    if args.qlora or vram < 20:
        print("  启用 QLoRA 4bit 量化")
        cfg["use_qlora"] = True
    else:
        cfg["use_qlora"] = False

    # ── 1. 加载数据 ──
    print(f"\n[1/5] 加载数据: {cfg['train_data']}")
    train_data, val_data = load_data(cfg["train_data"], test_mode=args.test)

    # ── 2. 加载模型 ──
    print(f"\n[2/5] 加载模型: {cfg['model']}")
    torch.cuda.empty_cache()
    gc.collect()

    # 量化配置 (QLoRA only)
    bnb_config = None
    if cfg.get("use_qlora"):
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
        print("  使用 4bit NF4 量化")

    load_kwargs = {
        "trust_remote_code": True,
        "torch_dtype": torch.bfloat16,
        "device_map": "auto",
    }
    if bnb_config:
        load_kwargs["quantization_config"] = bnb_config

    model = AutoModelForCausalLM.from_pretrained(
        cfg["model"], **load_kwargs
    )

    # 梯度检查点 (省显存)
    if cfg["use_gradient_checkpointing"]:
        model.gradient_checkpointing_enable()
        print("  Gradient checkpointing: ON")

    tokenizer = AutoTokenizer.from_pretrained(cfg["model"], trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ── 3. LoRA 配置 ──
    print(f"\n[3/5] LoRA 配置: r={cfg['lora_r']}, alpha={cfg['lora_alpha']}")

    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=cfg["lora_r"],
        lora_alpha=cfg["lora_alpha"],
        lora_dropout=cfg["lora_dropout"],
        target_modules=cfg["lora_target_modules"],
        bias="none",
    )

    # ── 4. 训练参数 ──
    effective_batch = cfg["batch_size"] * cfg["gradient_accumulation"]
    total_steps = len(train_data) * cfg["epochs"] // effective_batch
    print(f"\n[4/5] 训练参数:")
    print(f"  Epochs: {cfg['epochs']}")
    print(f"  Batch: {cfg['batch_size']} × {cfg['gradient_accumulation']} = {effective_batch}")
    print(f"  LR: {cfg['learning_rate']}")
    print(f"  预计步数: ~{total_steps}")
    print(f"  预计时间: ~{total_steps * 3 / 60:.0f} 分钟 (RTX 4090)")

    training_args = TrainingArguments(
        output_dir=cfg["output_dir"],
        num_train_epochs=1 if args.test else cfg["epochs"],
        per_device_train_batch_size=cfg["batch_size"],
        per_device_eval_batch_size=cfg["batch_size"],
        gradient_accumulation_steps=1 if args.test else cfg["gradient_accumulation"],
        learning_rate=cfg["learning_rate"],
        warmup_ratio=cfg["warmup_ratio"],
        logging_steps=cfg["logging_steps"],
        save_steps=cfg["save_steps"],
        eval_strategy="steps",
        eval_steps=cfg["save_steps"],
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        bf16=cfg["bf16"],
        tf32=cfg["tf32"],
        dataloader_num_workers=2,
        remove_unused_columns=False,
        report_to=["none"],  # 不用 WandB
        run_name="qwen7b-lora-szzkllm",
        gradient_checkpointing=cfg["use_gradient_checkpointing"],
    )

    # ── 5. 训练 ──
    print(f"\n[5/5] 开始训练...")
    print(f"{'=' * 60}")

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_data,
        eval_dataset=val_data,
        processing_class=tokenizer,
        peft_config=peft_config,
    )

    t_start = torch.cuda.Event(enable_timing=True)
    t_end = torch.cuda.Event(enable_timing=True)
    t_start.record()

    try:
        trainer.train()
    except KeyboardInterrupt:
        print("\n⚠ 训练被手动中断")
    except Exception as e:
        print(f"\n❌ 训练出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    t_end.record()
    torch.cuda.synchronize()
    elapsed = t_start.elapsed_time(t_end) / 1000

    # ── 保存 ──
    final_path = Path(cfg["output_dir"]) / "final"
    print(f"\n保存模型到 {final_path}...")
    trainer.save_model(str(final_path))
    tokenizer.save_pretrained(str(final_path))

    # 保存训练配置
    with open(final_path / "train_config.json", "w", encoding="utf-8") as f:
        json.dump({k: str(v) for k, v in cfg.items()}, f, ensure_ascii=False, indent=2)

    # ── 总结 ──
    print(f"\n{'=' * 60}")
    print("训练完成!")
    print(f"{'=' * 60}")
    print(f"  耗时: {elapsed/60:.1f} 分钟")
    print(f"  LoRA 权重: {final_path}")
    print(f"  推理测试: python sft/infer_7b.py --model {final_path}")
    print(f"  合并导出: python sft/merge_lora.py --base {cfg['model']} --lora {final_path}")


if __name__ == "__main__":
    main()
