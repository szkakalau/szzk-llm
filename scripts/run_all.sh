#!/bin/bash
# ============================================
# SZZKLLM 7B 训练 + 评测 一键脚本
# 在 GPU 服务器上执行: bash scripts/run_all.sh
# ============================================
set -e

echo "========================================"
echo "SZZKLLM Qwen2.5-7B 训练流水线"
echo "========================================"

# Step 1: 环境检查
echo ""
echo "[Step 1/4] GPU 环境..."
python -c "import torch; print(f'GPU: {torch.cuda.get_device_name(0)}')"

# Step 2: 快速测试
echo ""
echo "[Step 2/4] 测试训练流程 (10条数据)..."
python sft/train_7b.py --test --output_dir models/qwen7b-lora-test

# Step 3: 完整训练
echo ""
echo "[Step 3/4] 完整训练 (1193条数据)..."
python sft/train_7b.py

# Step 4: 评测
echo ""
echo "[Step 4/4] Benchmark 评测..."
python sft/infer_7b.py --model models/qwen7b-lora/final --benchmark

echo ""
echo "========================================"
echo "流水线完成!"
echo "========================================"
echo "模型: models/qwen7b-lora/final/"
echo "合并: python sft/merge_lora.py"
echo "========================================"
