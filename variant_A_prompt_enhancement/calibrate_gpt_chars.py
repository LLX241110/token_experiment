#!/usr/bin/env python3
"""
为 gpt-4o-mini 校准梯度字集
对候选字逐一测试先验置信度，筛出覆盖 10→1 的7个氵部字

用法：
  OPENAI_API_KEY="key" OPENAI_BASE_URL="https://api.chatanywhere.tech/v1" \
  python3.12 calibrate_gpt_chars.py
"""

import os, time
from openai import OpenAI

# 候选字：按预期先验从高到低排列，每档多备几个
CANDIDATES = [
    # 先验 ~10
    {"char": "清", "pinyin": "qīng", "phonetic": "青"},
    {"char": "河", "pinyin": "hé",   "phonetic": "可"},
    # 先验 ~8
    {"char": "泗", "pinyin": "sì",   "phonetic": "四"},
    {"char": "沛", "pinyin": "pèi",  "phonetic": "市"},
    # 先验 ~6
    {"char": "洧", "pinyin": "wěi",  "phonetic": "有"},
    {"char": "汶", "pinyin": "wèn",  "phonetic": "文"},
    # 先验 ~4
    {"char": "浕", "pinyin": "jìn",  "phonetic": "尽"},
    {"char": "泫", "pinyin": "xuàn", "phonetic": "玄"},
    {"char": "洙", "pinyin": "zhū",  "phonetic": "朱"},
    # 先验 ~2
    {"char": "洣", "pinyin": "mǐ",   "phonetic": "米"},
    {"char": "湸", "pinyin": "liàng","phonetic": "亮"},
    {"char": "浰", "pinyin": "lì",   "phonetic": "栗"},
    # 先验 ~1
    {"char": "浯", "pinyin": "wú",   "phonetic": "吾"},
    {"char": "洭", "pinyin": "kuāng","phonetic": "匡"},
    {"char": "浛", "pinyin": "hán",  "phonetic": "含"},
    {"char": "泶", "pinyin": "xué",  "phonetic": "学"},
]

PROMPT_TPL = (
    "请直接回答：汉字「{char}」的读音是什么？含义是什么？"
    "如果你不确定，请说「不确定」并给出你的猜测依据。"
    "回答控制在50字以内。"
)

def test_prior(client, char):
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": PROMPT_TPL.format(char=char)}],
            max_tokens=80,
            temperature=0,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"ERROR: {e}"

def main():
    api_key  = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    client   = OpenAI(api_key=api_key, base_url=base_url)

    print("校准 gpt-4o-mini 先验置信度")
    print("=" * 60)

    for item in CANDIDATES:
        answer = test_prior(client, item["char"])
        # 判断是否"认识"：含正确读音则认识
        knows = item["pinyin"].replace("ā","a").replace("á","a").replace("ǎ","a").replace("à","a")\
                              .replace("ō","o").replace("ó","o").replace("ǒ","o").replace("ò","o")\
                              .replace("ē","e").replace("é","e").replace("ě","e").replace("è","e")\
                              .replace("ī","i").replace("í","i").replace("ǐ","i").replace("ì","i")\
                              .replace("ū","u").replace("ú","u").replace("ǔ","u").replace("ù","u")\
                              .replace("ǖ","v").replace("ǘ","v").replace("ǚ","v").replace("ǜ","v")
        flag = "✅" if any(p in answer.lower() for p in [item["pinyin"], knows]) else "❓"
        print(f"{flag} {item['char']}（应读{item['pinyin']}）: {answer[:60]}")
        time.sleep(0.5)

if __name__ == "__main__":
    main()
