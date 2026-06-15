#!/bin/bash
# ============================================
# AutoDL GPU 环境一键部署脚本
# 用法: bash scripts/gpu_setup.sh
# ============================================
set -e

echo "=============================="
echo "SZZKLLM GPU 环境部署"
echo "=============================="

# 1. 检查 GPU
echo ""
echo "[1/4] GPU 检查..."
nvidia-smi
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0)}'); print(f'VRAM: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB')"

# 2. 安装依赖
echo ""
echo "[2/4] 安装依赖..."
pip install transformers datasets peft trl accelerate torch --quiet
pip install bitsandbytes --quiet  # QLoRA 备用

# 3. 验证关键库
echo ""
echo "[3/4] 验证库版本..."
python -c "
import transformers; print(f'transformers: {transformers.__version__}')
import torch; print(f'torch: {torch.__version__}')
import peft; print(f'peft: {peft.__version__}')
import trl; print(f'trl: {trl.__version__}')
"

# 4. 目录准备
echo ""
echo "[4/4] 准备目录..."
mkdir -p models/qwen7b-lora
mkdir -p data

echo ""
echo "=============================="
echo "部署完成!"
echo ""
echo "下一步:"
echo "  # 上传数据 (本地执行)"
echo "  scp data/clean_train.json user@server:/root/SZZKLLM/data/"
echo ""
echo "  # 测试训练 (服务器执行)"
echo "  cd /root/SZZKLLM"
echo "  python sft/train_7b.py --test"
echo ""
echo "  # 完整训练"
echo "  python sft/train_7b.py"
echo ""
echo "  # 评测"
echo "  python sft/infer_7b.py --model models/qwen7b-lora/final --benchmark"
echo "=============================="
