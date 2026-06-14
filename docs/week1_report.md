# SZZKLLM 第一周实验报告

> 2026年6月12日 — 6月19日 | 作者: szkakalau

---

## 一、项目概述

**目标**：基于 Qwen2.5-0.5B，通过 SFT 微调打造一个深圳中考学科答疑模型。

**技术栈**：PyTorch 2.12 / Transformers 5.11 / TRL 1.6 / WandB / DeepSeek API

**最终产出**：可一键运行的 SFT 训练流水线 + 2 个模型的完整对比实验。

---

## 二、每日执行记录

### Day 0 (6/12)：环境初始化

- 注册 WandB 账号（Entity: `33350441-sightwhale`）
- 初始化 Git 仓库并建立标准目录结构
- 配置 Python 虚拟环境，安装 PyTorch/Transformers/TRL/Datasets
- **验证**：`torch.cuda.is_available()` 返回 True（后续 Colab/GPU 训练）

### Day 1 (6/13)：最小数据集准备

- 从深圳中考真题试卷（语/数/英/物/化/史/政）中提取 QA 对
- 统一格式：`{"question": "", "answer": "", "subject": ""}`
- 划分训练集 (367 条) 和验证集 (43 条)
- **产出**：`data/v1.0/train.json` + `data/v1.0/val.json`
- **问题**：试卷提取脚本较为粗糙，部分题目混杂解析内容

### Day 2 (6/14)：最小训练脚本编写

- 基于 TRL SFTTrainer 编写训练脚本
- 集成 WandB 自动记录 Loss 和超参数
- 用 100 条数据做测试运行确保脚本无语法错误
- **产出**：`sft/train.py`
- **问题**：
  - TRL 1.6.0 将 `tokenizer` 参数改为 `processing_class` — 已修复
  - WandB 在线连接失败 → 启用 offline 模式回退

### Day 3 (6/15)：第一次完整训练

- 超参数：batch_size=4, grad_accum=2 (effective=8), lr=2e-5, epochs=2
- 第一次训练时模型推理无限生成 — 根因是缺少 `<|im_end|>` 作为停止 token
- **修复**：
  - 使用 Qwen 原生 chat_template
  - 添加 `eos_token_id=[151643, 151645]`（含 `<|im_end|>`）
- **产出**：`models/v1.0/final/` 模型权重 (2.0GB)
- **训练指标**：train_loss=1.821, eval_loss=1.836

### Day 4 (6/16)：推理测试与 Bug 修复

- 编写推理脚本，支持交互/单问/Benchmark 三种模式
- 用 5 道跨学科题目测试：3/5 正确 (60%)
- **修复的 Bug**：
  - 设备管理：自动检测 CUDA/CPU，inputs 移到正确设备
  - Benchmark 用贪婪解码（非采样）保证结果稳定
  - 选择题匹配：提取选项字母精确匹配
  - generation_config.json：添加 `151645` (`<|im_end|>`) 作为 eos token
- **产出**：`sft/infer.py` + `sft/test_infer.py`

### Day 5 (6/17)：CoT 数据准备

- 编写 API 批量 CoT 生成脚本（支持断点续传/进度保存）
- 手工编写 16 道高质量 CoT 示范 → 质量抽查全部通过
- 接入 DeepSeek V4 Pro API，生成 200 条 CoT 推理
- API 调用 200/200 全部成功，单条 CoT 长度 200-4000 字符
- 按学科比例分层采样（math:53, physics:44, history:37, english:33, chinese:22, chemistry:7, politics:5）
- **产出**：`data/v1.1/train.json` (567 条 = 367 原始 + 200 CoT)
- **问题**：Windows GBK 编码导致 UnicodeEncodeError → 修复 stdout UTF-8

### Day 6 (6/18)：第二次训练 + 对比

**v1.0 (基线)**：367 条，无 CoT

| 指标 | 值 |
|------|-----|
| train_loss | 1.821 |
| eval_loss | 1.836 |
| 推理得分 | 6/10 (60%) |
| 推理速度 | 10.6s |

**v1.1 (200 CoT)**：567 条，35% CoT

| 指标 | 值 |
|------|-----|
| train_loss | 1.373 ↓24% |
| eval_loss | 1.935 ↑5% |
| 推理得分 | 6/10 (60%) |
| 推理速度 | 21.1s |

**关键发现**：
1. **CoT 教学模式成功** — 模型学会了生成【分析】+【答案】结构化推理
2. Physics #8（流体压强）从错变对 ✅
3. History #3（商周青铜器）从对变错 — 因输出冗长 CoT 后匹配失败
4. 评估方法需要升级 — 简单字符串匹配无法正确评估 CoT 输出
5. 16 条 CoT (4%) 不够 → 200 条 (35%) 成功改变模型行为

---

## 三、问题与解决方案汇总

| # | 问题 | 根因 | 解决方案 | 日期 |
|---|------|------|----------|------|
| 1 | 推理无限生成 | 缺少 `<\|im_end\|>` eos token | 添加 `151645` 到 stop_ids | D3 |
| 2 | TRL tokenizer 废弃 | TRL 1.6 改名为 `processing_class` | 参数名称替换 | D2 |
| 3 | WandB 在线连接失败 | 网络/认证问题 | 启用 offline 模式 | D2 |
| 4 | CPU 训练时模型未在 GPU | 未指定 device_map | 自动检测 CUDA | D4 |
| 5 | Benchmark 结果不稳定 | 使用采样解码 | 贪婪解码 (do_sample=False) | D4 |
| 6 | API 脚本 GBK 编码崩溃 | Windows 默认编码 | stdout UTF-8 | D5 |
| 7 | 16 条 CoT 训练无效果 | CoT 占比太低 (4%) | 扩展到 200 条 (35%) | D6 |
| 8 | CoT 输出后简单匹配失效 | 模型输出推理+答案格式 | 需升级评估方法 | D6 |

---

## 四、模型能力分析

### 当前能力（v1.1）

**擅长**：
- 选择题直接输出选项（math/physics 多数正确）
- 化学概念判断（合金硬度、碳酸盐检验）
- 数学简单计算（概率、众数、统计）

**短板**：
- 英语词义辨析：输出带 `【考点】` 标签（训练数据残留）
- 中文简答题：容易输出空模板或编号列表（数据质量问题）
- 历史开放题：回答正确但评估函数未匹配到
- 物理概念题：部分仍判断错误（力学/平衡力）

**CoT 行为特征**：
- 模型已学会生成【分析】+【答案】结构化推理
- 但对简单选择题也会"过度思考"（不需要 CoT 的问题也输出推理）
- 推理时间翻倍（21s vs 11s）

---

## 五、技术经验总结

1. **小数据集也能训练**：367 条数据让 0.5B 模型学到了基本答题能力
2. **CoT 需要足够占比**：4% 无效果，35% 成功改变行为
3. **评估方法要跟上模型能力**：CoT 输出需要新的评估方式（如提取最终答案后再比较）
4. **离线 WandB 是救急方案**：`wandb sync` 可后续上传
5. **YAML 配置文件提升可复现性**：避免每次手动输入参数
6. **断点续传是必需功能**：长时间 API 调用或训练可能中断

---

## 六、第二周计划

| 日 | 任务 | 关键产出 |
|----|------|----------|
| D8 | 200 道客观题题库建设 | `benchmark/test_set_v0.1.json` |
| D9 | 自动评分脚本 | `benchmark/evaluate.py` |
| D10 | 评分逻辑 100% 验证 | 验证通过的评分脚本 |
| D11 | 双指标体系 (General + Error Recovery) | `benchmark/error_set_v1.0.json` |
| D12 | 基线模型评测 | v1.0 正式得分报告 |
| D13 | 初始 Error Set 建立 | 精选 20 道高价值错误 |
| D14 | 第二周复盘 | 技术文档 + 实验报告 |

---

## 附录：快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 一键训练 (YAML配置)
python sft/run_pipeline.py --config sft/config.yaml

# 推理测试
python sft/infer.py --model models/v1.1/final

# 模型对比
python sft/compare_models.py
```
