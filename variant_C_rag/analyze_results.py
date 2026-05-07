#!/usr/bin/env python3
"""
变体C结果分析：对比 baseline / manual / rag 三个条件
生成Markdown格式的分析报告
"""

import json
import os
import sys
import glob
from datetime import datetime

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
DICT_PATH = os.path.join(os.path.dirname(__file__), "char_dict.json")

# 评分维度
SCORE_DIMENSIONS = {
    "semantic": "语义推断",
    "phonetic": "读音推断",
}


def load_latest_results(provider: str = None) -> tuple[list, str]:
    pattern = os.path.join(RESULTS_DIR, "results_variant_C_*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        print("未找到结果文件，请先运行 rag_tester.py")
        sys.exit(1)
    if provider:
        files = [f for f in files if f"_{provider}_" in f]
    latest = files[-1]
    with open(latest, encoding="utf-8") as f:
        data = json.load(f)
    return data, latest


def load_char_dict() -> dict:
    with open(DICT_PATH, encoding="utf-8") as f:
        return json.load(f)["chars"]


def group_by_condition(results: list) -> dict:
    grouped = {"baseline": {}, "manual": {}, "rag": {}}
    for r in results:
        cond = r["condition"]
        char = r["char"]
        grouped[cond][char] = r
    return grouped


def print_report(results: list, filepath: str):
    char_dict = load_char_dict()
    grouped = group_by_condition(results)
    chars = sorted(set(r["char"] for r in results))

    print(f"# 变体C RAG实验结果分析\n")
    print(f"> 数据文件：{os.path.basename(filepath)}")
    print(f"> 分析时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    print(f"---\n")

    print("## 各字各条件回答对比\n")
    for char in chars:
        info = char_dict.get(char, {})
        has_phonetic = bool(info.get("phonetic"))
        char_type = "形声字" if has_phonetic else "会意字"
        print(f"### 「{char}」（{char_type}，部首：{info.get('radical','?')}，声旁：{info.get('phonetic','无')}，正确读音：{info.get('pinyin','?')}）\n")

        for cond in ["baseline", "manual", "rag"]:
            r = grouped[cond].get(char)
            if not r:
                print(f"**{cond}**：无数据\n")
                continue
            print(f"**{cond}（{_cond_label(cond)}）**\n")
            print(f"Prompt：\n```\n{r['prompt']}\n```\n")
            print(f"回答：\n> {r['response'].strip().replace(chr(10), chr(10) + '> ')}\n")
        print("---\n")

    print("## 核心对比：manual vs rag\n")
    print("| 字 | 类型 | 正确读音 | manual检索 | rag检索 | 一致性 |")
    print("|---|---|---|---|---|---|")
    for char in chars:
        info = char_dict.get(char, {})
        char_type = "形声字" if info.get("phonetic") else "会意字"
        pinyin = info.get("pinyin", "?")
        m = grouped["manual"].get(char, {}).get("response", "无数据")
        r = grouped["rag"].get(char, {}).get("response", "无数据")
        # 截取前30字作摘要
        m_short = m[:30].replace("\n", " ") + "…" if len(m) > 30 else m
        r_short = r[:30].replace("\n", " ") + "…" if len(r) > 30 else r
        print(f"| {char} | {char_type} | {pinyin} | {m_short} | {r_short} | 待评 |")

    print("\n> 注：一致性需人工评分，请对照上方逐字回答填写 ✅相符 / ⚠️部分相符 / ❌不符\n")

    print("## 实验设计说明\n")
    print("- **baseline**：只给目标字，不提供任何字典信息")
    print("- **manual**：直接将字典信息写入prompt（变体A方式，人工标注）")
    print("- **rag**：调用 `retrieve()` 从 char_dict.json 检索后注入（变体C自动化）")
    print("\n**核心验证命题**：manual ≈ rag >> baseline")
    print("若manual与rag结论一致，则证明RAG可完全替代手工注入，字典信息的价值可自动化复现。\n")


def _cond_label(cond: str) -> str:
    return {"baseline": "无信息", "manual": "手工注入", "rag": "自动检索"}[cond]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default=None)
    parser.add_argument("--file", default=None, help="指定结果文件路径")
    args = parser.parse_args()

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            results = json.load(f)
        filepath = args.file
    else:
        results, filepath = load_latest_results(args.provider)

    print_report(results, filepath)


if __name__ == "__main__":
    main()
