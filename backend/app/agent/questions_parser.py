from __future__ import annotations

import re

# 行首 数字. 问题文本，后跟可选的若干 (X)选项
# 例：1. 目标平台？(A)手机 (B)PC (C)网页
_QLINE = re.compile(r"^\s*(\d+)\s*[.、]\s*(.+?)\s*$")
_OPT = re.compile(r"[（(]([A-Za-z\d])[)）]\s*([^（()（）]+?)(?=\s*[（(][A-Za-z\d][)）]|$)")


def parse_questions(text: str) -> list[dict]:
    """解析 kimi-k3 的 'N. 问题 (A)选项 (B)选项' 文本成结构化。

    返回 [{id, question, options}]。容错：无问题/乱格式→[]。
    只取形如 '数字. ...' 的行，忽略前言后语。
    """
    if not text:
        return []
    out: list[dict] = []
    for line in text.splitlines():
        m = _QLINE.match(line)
        if not m:
            continue
        qid = m.group(1)
        rest = m.group(2)
        # 在 rest 里找 (A)选项 (B)选项 ...，分离 question 与 options
        opts = _OPT.findall(rest)
        if opts:
            # question 是第一个 (X) 之前的文本
            first_opt_pos = rest.find(opts[0][0])  # 用 label 字符定位
            # 更稳：用第一个 (X) 的位置
            mfirst = re.search(r"[（(][A-Za-z\d][)）]", rest)
            question = rest[: mfirst.start()].strip() if mfirst else rest.strip()
            options = [text_opt.strip() for _label, text_opt in opts]
        else:
            question = rest.strip()
            options = []
        # 去掉 question 末尾可能残留的冒号/问号空格
        out.append({"id": qid, "question": question, "options": options})
    return out
