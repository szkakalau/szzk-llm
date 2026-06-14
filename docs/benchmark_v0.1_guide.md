# Benchmark v0.1 技术文档

> SZZKLLM 模型评测体系 — 200 道选择题标准化评测

---

## 1. 概述

Benchmark v0.1 是 SZZKLLM 项目的标准化评测体系，包含 200 道中考选择题，覆盖 7 个学科。支持双指标（General Score + Error Recovery Score）和自动错误集追踪。

## 2. 快速开始

```bash
# 首次评测（生成 Error Set）
python benchmark/evaluate.py --model models/v1.0/final

# 迭代评测（双指标对比）
python benchmark/evaluate.py --model models/v1.1/final \
    --error-set benchmark/error_set_v1.0.json

# 快速测试（10 题）
python benchmark/evaluate.py --model models/v1.0/final --test

# JSON 输出
python benchmark/evaluate.py --model models/v1.0/final --json
```

## 3. 题库格式

```json
{
  "id": 1,
  "subject": "math",
  "question": "－3的绝对值是（ ）A. 3 B. -3 C. 1/3 D. -1/3",
  "options": ["A. 3", "B. -3", "C. 1/3", "D. -1/3"],
  "answer": "A"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 唯一编号 1-200 |
| subject | string | 学科：math/physics/chemistry/chinese/english/history/politics |
| question | string | 题目文本（含选项标记）|
| options | list | 选项数组，格式 `"A. 内容"` |
| answer | string | 正确答案字母 A/B/C/D |

### 学科分布

```
math      34  █████████████████
physics   33  ████████████████▌
history   30  ███████████████
chinese   29  ██████████████▌
chemistry 27  █████████████▌
english   27  █████████████▌
politics  20  ██████████
```

## 4. 双指标体系

### General Score

```
General Score = 正确数 / 200
```

标准准确率，衡量模型整体答题能力。

### Error Recovery Score

```
Error Recovery Score = 本次答对的旧错题数 / 上次打开的错题总数
```

衡量模型对已知错误的修复能力。通过 `--error-set` 参数加载历史错误集。

### 报告示例

```
BENCHMARK v0.1 评测报告
  总题数: 200
  正确: 125   错误: 75

  📊 双指标:
  General Score:        125/200 =  62.5%
  Error Recovery Score:   55/113 =  48.7%

  错误类型分布:
    知识错误: 57    格式错误: 11    逻辑错误: 5    幻觉错误: 2

  各科得分:
  history    83.3%  ████████████████░░░░
  chemistry  74.1%  ██████████████░░░░░░
  physics    60.6%  ████████████░░░░░░░░
  math       47.1%  █████████░░░░░░░░░░░
```

## 5. 答案提取策略

按优先级从模型输出中提取选项字母：

| 优先级 | 策略 | 示例 |
|--------|------|------|
| 1 | 显式答案标记 | `【答案】A`, `正确答案是C` |
| 2 | 选择标记 | `选B`, `所以选择D` |
| 3 | 行尾独立字母 | `\nA`, CoT 末尾 |
| 4 | 括号字母 | `（B）`, `(C)` |
| 5 | 短文本 fallback | `A`（仅当文本≤3字符）|
| — | 排除序列 | `ABCD` 连续4字母不匹配 |

## 6. 错误分类

| 类型 | 含义 | 自动检测规则 |
|------|------|-------------|
| `knowledge` | 知识性错误（选错了）| 输出选项字母但非正确答案 |
| `logic` | 逻辑推理错误 | 输出选项字母，模型给出推理但推错 |
| `format` | 格式错误（无字母）| 输出不含 A-D 字母 |
| `hallucination` | 训练残留幻觉 | 输出含 `【考点】` `/` 解析：` 等训练数据格式 |

## 7. Error Set 管理

### 生命周期

```
首次评测 → error_set_v1.0.json (status: open)
    ↓
迭代评测 → merge (fixed: 答对的旧错 → status=fixed)
    ↓
精选 → error_set_v1.0_curated.json (20道高价值错误)
```

### 错误条目格式

```json
{
  "id": 12,
  "subject": "math",
  "question": "－3的绝对值是（ ）...",
  "correct_answer": "A",
  "error_type": "knowledge",
  "model_answer": "C",
  "status": "open",
  "first_appeared": "v1.0",
  "fixed_in": null,
  "root_cause": "混淆了绝对值和倒数"
}
```

## 8. 验证体系

```bash
python benchmark/verify_scoring.py
```

| 测试层 | 项数 | 说明 |
|--------|------|------|
| 数据完整性 | 200 | ID唯一/答案格式/选项匹配/题目长度 |
| 答案提取 | 46 | 纯字母/中文标记/CoT/英文/边界 |
| 评分模拟 | 10 | v1.0/v1.1 各种输出格式 |
| 批量运行 | 600 | 200题 × 3种输出格式 |

## 9. 基线记录

| 版本 | 日期 | 训练数据 | General Score | 备注 |
|------|------|----------|---------------|------|
| v1.0 | 2026-06-15 | 367 (无CoT) | **62.5%** | 官方基线 |
| v1.1 | 2026-06-18 | 567 (200 CoT) | 43.5% | CoT 适得其反 |
