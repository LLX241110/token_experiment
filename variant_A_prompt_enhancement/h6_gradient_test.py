#!/usr/bin/env python3
"""
H6 梯度实验：先验置信度 × 错误信息干扰效果
在 gpt-4o-mini 上复刻 Claude 的梯度实验，比较临界区差异

用法：
  OPENAI_API_KEY="your-key" OPENAI_BASE_URL="https://api.chatanywhere.tech/v1" \
  python3.12 h6_gradient_test.py
"""

import os
import json
import time
from datetime import datetime
from openai import OpenAI

# ── 梯度字集（同 Claude 实验，从先验强到弱）──────────────────────────
GRADIENT_CHARS = [
    {"char": "清", "correct_phonetic": "青", "correct_pinyin": "qīng",  "prior": 10},
    {"char": "泗", "correct_phonetic": "四", "correct_pinyin": "sì",    "prior": 8},
    {"char": "泫", "correct_phonetic": "玄", "correct_pinyin": "xuàn",  "prior": 6},
    {"char": "浕", "correct_phonetic": "尽", "correct_pinyin": "jìn",   "prior": 4},
    {"char": "湸", "correct_phonetic": "亮", "correct_pinyin": "liàng", "prior": 3},
    {"char": "洭", "correct_phonetic": "匡", "correct_pinyin": "kuāng", "prior": 2},
    {"char": "泶", "correct_phonetic": "学", "correct_pinyin": "xué",   "prior": 1},
]

# 统一干预：错误声旁「土」（读 tǔ）
WRONG_PHONETIC = "土"
WRONG_PINYIN   = "tǔ"

# ── Prompt 模板 ────────────────────────────────────────────────────────
def make_prompt(char: str, phonetic: str) -> str:
    return (
        f"请根据以下信息推断这个汉字的读音：\n\n"
        f"目标字：{char}（部首：氵，声旁：{phonetic}）\n\n"
        f"提示：这是一个形声字，声旁表示读音方向。请直接给出你推断的读音（拼音），"
        f"并说明推断依据。如果提供的信息与你已知的信息冲突，请指出冲突并说明你的判断。"
    )

# ── 主程序 ─────────────────────────────────────────────────────────────
def run():
    api_key  = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    if not api_key:
        print("错误：未设置 OPENAI_API_KEY")
        return

    client = OpenAI(api_key=api_key, base_url=base_url)
    model  = "gpt-4o-mini"
    results = []

    print(f"模型：{model}")
    print(f"干预：错误声旁「{WRONG_PHONETIC}」（读 {WRONG_PINYIN}）")
    print("=" * 60)

    for item in GRADIENT_CHARS:
        char    = item["char"]
        correct = item["correct_pinyin"]
        prior   = item["prior"]

        prompt_wrong   = make_prompt(char, WRONG_PHONETIC)
        prompt_correct = make_prompt(char, item["correct_phonetic"])

        print(f"\n字：{char}  先验:{prior}/10  正确读音:{correct}")

        # A 组：正确声旁（对照）
        try:
            resp_a = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt_correct}],
                max_tokens=200,
                temperature=0,
            )
            answer_a = resp_a.choices[0].message.content.strip()
        except Exception as e:
            answer_a = f"ERROR: {e}"
        time.sleep(0.8)

        # C 组：错误声旁（干预）
        try:
            resp_c = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt_wrong}],
                max_tokens=200,
                temperature=0,
            )
            answer_c = resp_c.choices[0].message.content.strip()
        except Exception as e:
            answer_c = f"ERROR: {e}"
        time.sleep(0.8)

        print(f"  A（正确声旁）: {answer_a[:80]}")
        print(f"  C（错误声旁）: {answer_c[:80]}")

        results.append({
            "char":            char,
            "prior":           prior,
            "correct_pinyin":  correct,
            "correct_phonetic": item["correct_phonetic"],
            "wrong_phonetic":  WRONG_PHONETIC,
            "answer_correct":  answer_a,
            "answer_wrong":    answer_c,
        })

    # ── 保存结果 ──────────────────────────────────────────────────────
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"results/h6_gradient_gpt4omini_{ts}.json"
    os.makedirs("results", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"model": model, "timestamp": ts, "results": results},
                  f, ensure_ascii=False, indent=2)

    print(f"\n\n结果已保存：{path}")

    # ── 终端汇总 ──────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("汇总（对比 Claude 临界区 6–7）")
    print("=" * 60)
    print(f"{'字':<4} {'先验':>4} {'正确读音':>6}  C组回答（前60字）")
    print("-" * 60)
    for r in results:
        c_ans = r["answer_wrong"].replace("\n", " ")[:60]
        print(f"{r['char']:<4} {r['prior']:>4}/10  {r['correct_pinyin']:>6}  {c_ans}")


if __name__ == "__main__":
    run()
