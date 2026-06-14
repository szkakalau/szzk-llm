# -*- coding: utf-8 -*-
"""
Day 13: 精选20道最具代表性错误
根据实际 error ID 精确匹配
"""
import json, sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# {error_id: {error_type, root_cause}}
CURATED = {
    # ── Math (3) ──
    12: {"error_type": "knowledge",
         "root_cause": "绝对值概念: |−3|=3, 模型选C(=1/3)说明混淆了绝对值和倒数"},
    31: {"error_type": "knowledge",
         "root_cause": "函数定义域: √(x-1)要求x-1≥0→x≥1, 模型选D(x≤1)完全相反"},
    29: {"error_type": "knowledge",
         "root_cause": "指数运算法则: (ab)²=a²b², a⁶÷a²=a⁴(非a³), (a²)³=a⁶(非a⁵)"},

    # ── Physics (3) ──
    46: {"error_type": "knowledge",
         "root_cause": "质量vs重力: 质量是物体固有属性不随位置变化, 月球→地球质量不变"},
    55: {"error_type": "knowledge",
         "root_cause": "物理估算: 人步行约1.1m/s≈4km/h, 10m/s=36km/h远超正常值"},
    191: {"error_type": "logic",
         "root_cause": "电器原理: 电饭煲用电流热效应, 电风扇用电动机(磁效应), 模型选了洗衣机"},

    # ── History (3) ──
    68: {"error_type": "knowledge",
         "root_cause": "拉美独立领袖: 玻利瓦尔领导南美独立战争, 被誉为'解放者'(El Libertador)"},
    89: {"error_type": "knowledge",
         "root_cause": "英国宪政: 《权利法案》(1689)限制王权保证议会立法权, 区别于《独立宣言》"},
    73: {"error_type": "knowledge",
         "root_cause": "跨区域文明: 两河流域出土印度器具证明古代亚非文明之间存在联系"},

    # ── Chinese (3) ──
    124: {"error_type": "knowledge",
         "root_cause": "错别字辨析: '迫不及待'正确, '走头无路'应为'走投无路', '一诺千斤'应为'一诺千金'"},
    172: {"error_type": "logic",
         "root_cause": "文言翻译: '三人行必有我师'意为几个人一起走其中必有可做我老师的人, C翻译为'几个人走路'过于字面"},
    130: {"error_type": "knowledge",
         "root_cause": "文体常识: 散文形散神聚不要求完整故事线索, 小说才需要完整情节"},

    # ── Chemistry (3) ──
    136: {"error_type": "logic",
         "root_cause": "纯净物概念: 蒸馏水只含H₂O分子是纯净物, 空气/海水/石灰水均为混合物"},
    180: {"error_type": "knowledge",
         "root_cause": "反应类型: Zn+H₂SO₄→ZnSO₄+H₂↑ 单质置换酸中的氢, 属置换反应"},
    145: {"error_type": "knowledge",
         "root_cause": "质量守恒定律: 化学反应前后原子种类和数目不变, 分子种类改变"},

    # ── English (2) ──
    105: {"error_type": "logic",
         "root_cause": "固定搭配: Let's+动词原形; prefer A(n.) to B(n.); would rather do than do"},
    121: {"error_type": "logic",
         "root_cause": "比较级句型: 'the more you read, the better you will be' 双重比较结构"},

    # ── Politics (3) ──
    163: {"error_type": "logic",
         "root_cause": "宪法第2条: '中华人民共和国的一切权力属于人民', '公民'是具有国籍的法律概念≠人民"},
    164: {"error_type": "logic",
         "root_cause": "网络作用: 网络为文化传播搭建新平台丰富生活, 而非完全取代传统方式"},
    158: {"error_type": "knowledge",
         "root_cause": "权利义务统一: 哄抬物价受处罚→行使权利时必须履行守法义务, 权利与义务相统一"},
}


def main():
    with open("benchmark/error_set_v1.0.json", encoding="utf-8") as f:
        es = json.load(f)

    # ID索引
    by_id = {e["id"]: e for e in es["errors"]}

    curated = []
    for eid, meta in CURATED.items():
        if eid in by_id:
            err = by_id[eid].copy()
            err["error_type"] = meta["error_type"]
            err["root_cause"] = meta["root_cause"]
            err["selected_for"] = "v1.0_curated_20"
            curated.append(err)
        else:
            print(f"  WARNING: id={eid} not found, skipping")

    print(f"精选: {len(curated)}/20")

    from collections import Counter
    print(f"学科: {dict(Counter(e['subject'] for e in curated))}")
    print(f"类型: {dict(Counter(e['error_type'] for e in curated))}")

    # 保存
    curated_set = {
        "version": "v1.0-curated-20",
        "description": "从v1.0基线75个打开错误中精选20道高价值代表性题目",
        "updated": es["updated"],
        "total_errors": len(curated),
        "total_fixed": 0,
        "selection_criteria": [
            "七学科覆盖: math(3) physics(3) history(3) chinese(3) chemistry(3) english(2) politics(3)",
            "类型覆盖: knowledge(13) + logic(7)",
            "每道题标注root_cause(人工分析)和修正error_type",
            "优先选概念性/基础性错误, 避免噪声数据",
        ],
        "errors": curated,
    }

    path = "benchmark/error_set_v1.0_curated.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(curated_set, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已保存: {path} ({len(curated)}题)")

    # 清单
    print(f"\n{'='*60}")
    print("20道精选错误清单:")
    print(f"{'='*60}")
    for i, e in enumerate(curated):
        q = e["question"][:100].replace("\n", " ")
        print(f"\n{i+1:2d}. #{e['id']} [{e['subject']:10s}] [{e['error_type']:10s}] "
              f"exp={e['correct_answer']} pred={e['model_answer']}")
        print(f"   Q: {q}")
        print(f"   根因: {e['root_cause']}")


if __name__ == "__main__":
    main()
