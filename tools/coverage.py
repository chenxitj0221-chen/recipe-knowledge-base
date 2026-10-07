"""菜例覆盖统计：菜系、主材类别、场景、角色。

用法：python tools/coverage.py
输出：review/coverage-report.md

主材类别不是原文字段，由本脚本推断，并在明细表里写明依据；推断不出时标"未确定"。
"""
import glob
import json
import os
import re
from collections import Counter, defaultdict
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "review", "coverage-report.md")

# 推断主材时只看这些大类；水果、调味品、酒、乳制品等不作为主材
NAME_PRIORITY = [["seafood", "meat", "egg"], ["vegetable", "staple"]]
UNKNOWN = "未确定"


def load(path):
    with open(path, encoding="utf8") as f:
        return json.load(f)


def zh(field):
    """取双语字段中的中文一侧。"""
    if not isinstance(field, dict):
        return field
    return field["original"] if field.get("original_lang") == "zh" else field.get("translation")


def as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def build_keywords(cats):
    """返回 [(关键词, 是否中文, 大类, 小类路径, 中文名)]，长关键词优先。"""
    out = []
    for ck, cv in cats["categories"].items():
        subs = cv.get("subcategories") or {ck: cv}
        for sk, sv in subs.items():
            path = ck if sk == ck else f"{ck}.{sk}"
            label = cv["name"]["original"] if sk == ck else f"{cv['name']['original']} / {sv['name']['original']}"
            for kw in sv.get("keywords_zh", []):
                out.append((kw, True, ck, path, label))
            for kw in sv.get("keywords_en", []):
                out.append((kw.lower(), False, ck, path, label))
    out.sort(key=lambda x: -len(x[0]))
    return out


def match(text, keywords, allowed):
    """在全部类别里找命中，去掉被更长命中覆盖的（如「牛奶」覆盖「牛」），再按 allowed 取第一个。"""
    if not text:
        return None
    low = text.lower()
    hits = []
    for kw, is_zh, top, path, label in keywords:
        pattern = re.escape(kw) if is_zh else r"\b" + re.escape(kw) + r"s?\b"
        for m in re.finditer(pattern, text if is_zh else low):
            hits.append((m.start(), m.end(), top, path, label, kw))
    kept = [h for h in hits if not any(o[0] <= h[0] and h[1] <= o[1] and o[1] - o[0] > h[1] - h[0] for o in hits)]
    for h in kept:
        if h[2] in allowed:
            return h[3], h[4], h[5]
    return None


def infer_main(dish, keywords):
    names = [dish["name"].get("original"), dish["name"].get("translation")]
    for n in names:
        for tier in NAME_PRIORITY:
            m = match(n, keywords, tier)
            if m:
                return m[0], m[1], f"菜名含「{m[2]}」"
    # 中餐：原书的"主料"分组里第一项即主材
    comps = dish.get("components") or []
    main = next((c for c in comps if c.get("id") == "main"), None)
    if dish.get("cuisine_branch") == "chinese" and main and main.get("ingredients"):
        item = main["ingredients"][0]["item"]
        allowed = [c for tier in NAME_PRIORITY for c in tier]
        for t in (item.get("original"), item.get("translation")):
            m = match(t, keywords, allowed)
            if m:
                return m[0], m[1], f"主料首项「{item.get('original')}」"
    return None, UNKNOWN, "菜名与主料均无法判断"


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def counter_table(title, counter, total):
    rows = [(k, v, f"{v / total:.0%}") for k, v in counter.most_common()]
    return f"## {title}\n\n" + table(["项", "菜例数", "占比"], rows)


def main():
    cats = load(os.path.join(ROOT, "mappings", "ingredient-categories.json"))
    keywords = build_keywords(cats)
    dishes = [load(f) for f in sorted(glob.glob(os.path.join(ROOT, "skills", "*", "*.json")))]
    total = len(dishes)

    rows, cuisine, main_top, main_sub, scenes, roles = [], Counter(), Counter(), Counter(), Counter(), Counter()
    cross = defaultdict(Counter)
    role_by_branch = defaultdict(Counter)
    for d in dishes:
        cl = d["classification"]
        cu = zh(cl["cuisine"])
        role = zh(cl.get("role"))
        sc = as_list(zh(cl.get("scenes")))
        path, label, basis = infer_main(d, keywords)
        top = label.split(" / ")[0]
        cuisine[cu] += 1
        main_top[top] += 1
        main_sub[label] += 1
        roles[role] += 1
        role_by_branch[d["cuisine_branch"]][role] += 1
        cross[cu][top] += 1
        for s in sc:
            scenes[s] += 1
        rows.append((d["id"], d["cuisine_branch"], cu, role, label, basis, "、".join(sc)))

    # 缺口：可作为主材的小类里，一道菜都没有的
    used = set(main_sub)
    empty = []
    for ck in [c for tier in NAME_PRIORITY for c in tier]:
        cv = cats["categories"][ck]
        for sk, sv in (cv.get("subcategories") or {ck: cv}).items():
            label = cv["name"]["original"] if sk == ck else f"{cv['name']['original']} / {sv['name']['original']}"
            if label not in used:
                empty.append(label)

    tops = sorted({t for c in cross.values() for t in c})
    cross_rows = [[cu] + [cross[cu].get(t, "") for t in tops] for cu in sorted(cross)]
    all_roles = sorted({r for c in role_by_branch.values() for r in c})
    role_rows = [[b] + [role_by_branch[b].get(r, "") for r in all_roles] for b in sorted(role_by_branch)]

    parts = [
        "# 菜例覆盖统计",
        f"生成日期：{date.today().isoformat()}　菜例总数：{total}　由 `tools/coverage.py` 生成，请勿手改。",
        "> 「主材类别」是脚本推断，不是原文字段；依据见文末明细表。菜系、场景、角色取自各菜例 `classification` 的中文一侧，未做归并。",
        counter_table("菜系", cuisine, total),
        counter_table("主材大类（推断）", main_top, total),
        counter_table("主材小类（推断）", main_sub, total),
        "## 菜系 × 主材大类\n\n" + table(["菜系"] + tops, cross_rows),
        "## 分支 × 角色\n\n" + table(["分支"] + all_roles, role_rows),
        counter_table("场景（一道菜可有多个场景）", scenes, total),
        "## 缺口：尚无菜例的主材类别\n\n" + "\n".join(f"- {e}" for e in empty),
        "## 明细\n\n" + table(["id", "分支", "菜系", "角色", "主材（推断）", "依据", "场景"], rows),
    ]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf8", newline="\n") as f:
        f.write("\n\n".join(parts) + "\n")
    print(f"已生成 {os.path.relpath(OUT, ROOT)}（{total} 道菜例，主材未确定 {main_top.get(UNKNOWN, 0)} 道）")


if __name__ == "__main__":
    main()
