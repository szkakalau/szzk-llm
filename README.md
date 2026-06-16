# 📚 SZZKLLM — 深圳中考 AI 答疑模型

[![Accuracy](https://img.shields.io/badge/Accuracy-89.3%25-brightgreen)](https://u1046415-a5b8-78a828a3.westc.seetacloud.com:8443)
[![Model](https://img.shields.io/badge/Model-Qwen2.5--7B-blue)](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct)
[![Data](https://img.shields.io/badge/Data-5,527%20题-orange)](data/)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](LICENSE)
[![Demo](https://img.shields.io/badge/Demo-在线体验-red)](https://u1046415-a5b8-78a828a3.westc.seetacloud.com:8443)

基于 Qwen2.5-7B 微调，覆盖深圳中考 7 个学科（语文/数学/英语/物理/化学/历史/道法），**89.3% Benchmark 准确率**。

> 🚀 [在线 Demo 体验](https://u1046415-a5b8-78a828a3.westc.seetacloud.com:8443)

## 模型性能

```
7B v3:  89.3% ██████████████████████████████████████████████ ⭐
7B v2:  72.4% ████████████████████████████████████
0.5B:   63.5% ████████████████████████████████
```

| 学科 | 准确率 | 
|------|--------|
| history | 94.1% |
| english | 93.8% |
| politics | 92.9% |
| physics | 90.3% |
| chemistry | 89.0% |
| chinese | 82.4% |
| math | 70.4% |

## 一键复现

```bash
# 1. 环境 (RTX 4090 24GB)
pip install transformers==4.46.3 peft==0.13.2 trl==0.12.0 datasets openai fastapi uvicorn

# 2. 数据提取 (从原始 .docx 试卷)
python scripts/extract_v2.py --output data/extracted_questions.json

# 3. 数据扩增 (DeepSeek API, ~¥0.30)
export DEEPSEEK_API_KEY="sk-xxx"
python scripts/augment.py

# 4. 训练 (~50 分钟)
export HF_ENDPOINT=https://hf-mirror.com
python sft/train_7b.py --batch 1 --epochs 2

# 5. 部署
python api/main.py --model models/qwen7b-merged --port 8000
```

## 数据流水线

```
303 个原始 .docx 试卷 (2008-2025)
    ↓ python-docx 提取
1,193 道选择题 (7学科)
    ↓ DeepSeek API 扩增 (4.6×)
5,527 道训练数据
    ↓ Qwen2.5-7B LoRA
89.3% 准确率
```

## 项目结构

```
├── sft/               训练与推理 (train_7b.py, infer_7b.py, merge_lora.py)
├── api/               FastAPI 部署 (main.py)
├── scripts/           数据工具 (extract_v2.py, augment.py, build_training_set.py)
├── data/              训练数据 (clean_train.json 1,193题, augmented 5,527题)
├── benchmark/         评测体系 (evaluate.py, test_set_v0.1.json)
├── error_analysis/    错误分析 (root_cause.md, classified_errors.json)
├── exam-papers/       303 个原始试卷
├── docs/              实验报告 (week1-4_report.md)
└── models/            模型权重 (gitignored)
```

## 迭代历程

| 版本 | 模型 | 数据 | 准确率 | 关键发现 |
|------|------|------|--------|---------|
| v1.3 | 0.5B | 630 手工 | 63.5% | 概念辨析有效 |
| v2 | 7B | 1,193 真题 | 72.4% | 大模型+真题数据 |
| **v3** | **7B** | **5,527 扩增** | **89.3%** | **数据扩增是关键** |

完整实验记录见 [docs/week4_report.md](docs/week4_report.md)。

## 经验教训

1. **数据扩增 > 模型大小** — 1,193→5,527 带来 +16.9%，比换大模型更有效
2. **CoT 对选择题有害** — 加入后 62.5%→43.5%
3. **0.5B 天花板 ~65%** — 再优化也无法突破知识容量瓶颈
4. **真题质量是基础** — python-docx 直接从试卷提取比手工编写准确
5. **89%→95% 需要解决含图公式题** — Math 仍是短板

## 技术栈

Qwen2.5-7B-Instruct · LoRA (r=64) · TRL SFTTrainer · DeepSeek API · python-docx · FastAPI · RTX 4090

---

*56 次提交 · 5,527 题 · 89.3% · 4 天完成*
