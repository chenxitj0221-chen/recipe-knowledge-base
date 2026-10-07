"""由 intake 格式的菜谱生成操作清单（SOP）：备料称量 + 制作步骤，每步写明用料和用量。

用法：python tools/sop.py <菜谱.json> [--scale 倍数] [-o 输出.md]
菜谱未通过校验时不生成。用量只来自原文；原文没写的，照录原文写法，不估算。
"""
import argparse
import os
import sys

from validate_intake import VOCAB, load, validate

UNKNOWN_QTY = "原文未给定量"


def fmt(qty, scale):
    v = qty * scale
    return str(int(v)) if float(v).is_integer() else f"{v:.2f}".rstrip("0").rstrip(".")


def amount(qty, unit, scale):
    return f"{fmt(qty, scale)} {unit or ''}".strip()


def ingredient_line(ing, scale, notes):
    if ing.get("listed_in_source") is False:
        qty = "⚠ 原文食材表未列出，用量未知"
    elif ing["qty"] is None:
        n = notes.setdefault(ing["raw"], len(notes) + 1)
        qty = f"{UNKNOWN_QTY}[^{n}]"
    else:
        qty = amount(ing["qty"], ing["unit"], scale)
    prep = f" — {ing['prep']}" if ing.get("prep") else ""
    return f"- [ ] **{ing['item']}**　{qty}{prep}"


def use_text(u, ing, n_steps, scale):
    if u.get("qty") is not None:
        return f"{ing['item']} {amount(u['qty'], u.get('unit') or ing['unit'], scale)}"
    if ing["qty"] is None:
        return f"{ing['item']}（{UNKNOWN_QTY}）"
    if n_steps == 1:
        return f"{ing['item']} {amount(ing['qty'], ing['unit'], scale)}"
    return f"{ing['item']}（分次使用，总量 {amount(ing['qty'], ing['unit'], scale)}）"


def render(recipe, scale, vocab):
    comps = recipe["components"]
    names = {c["id"]: c["name"] for c in comps}
    sections = [(c["name"], c.get("type"), c) for c in comps] + [("合成与装盘", None, recipe["assembly"])]
    ings = {i["id"]: i for _, _, s in sections for i in s["ingredients"]}
    step_count = {}
    for _, _, s in sections:
        for st in s["steps"]:
            for u in st["uses"]:
                step_count[u["ref"]] = step_count.get(u["ref"], 0) + 1

    p, sv = recipe["provenance"], recipe["servings"]
    serving = sv["raw"] or "原文未注明"
    if scale != 1:
        serving += f"；本清单已按 ×{fmt(scale, 1)} 线性换算。油、调味等不一定按比例增减，步骤原文中的数字未换算，请自行判断"
    lines = [
        f"# {recipe['name']}",
        "",
        f"- 份量：{serving}",
        f"- 来源：《{p['source_title']}》{('，' + p['author']) if p['author'] else ''}{('，' + p['locator']) if p['locator'] else ''}",
        f"- 原始资料位置：{p['source_path'] or '未登记'}",
        "",
        "## 一、备料称量",
    ]
    notes = {}
    for name, typ, s in sections:
        if not s["ingredients"]:
            continue
        label = vocab["types"][typ]["name"]["original"] if typ in vocab["types"] else typ
        lines += ["", f"### {name}" + (f"（{label}）" if label and label != name else "")]
        lines += [ingredient_line(i, scale, notes) for i in s["ingredients"]]
    if notes:
        lines += [""] + [f"[^{n}]: 原文：{raw}" for raw, n in notes.items()]

    lines += ["", "## 二、制作步骤"]
    n = 0
    for name, _, s in sections:
        lines += ["", f"### {name}"]
        for st in s["steps"]:
            n += 1
            lines.append(f"{n}. {st['text']}")
            parts = []
            for u in st["uses"]:
                if u["ref"] in names:
                    parts.append(f"←「{names[u['ref']]}」")
                else:
                    parts.append(use_text(u, ings[u["ref"]], step_count[u["ref"]], scale))
            if parts:
                lines.append(f"   - 用料：{'；'.join(parts)}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("recipe")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("-o", "--output")
    args = ap.parse_args()

    recipe = load(args.recipe)
    errors, _ = validate(recipe)
    if errors:
        print("菜谱未通过校验，不生成 SOP：", file=sys.stderr)
        for e in errors:
            print(f"  ✗ {e}", file=sys.stderr)
        return 1
    out = render(recipe, args.scale, load(VOCAB))
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf8", newline="\n") as f:
            f.write(out)
        print(f"已生成 {args.output}")
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
