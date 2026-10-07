"""校验 intake 格式的菜谱。

用法：python tools/validate_intake.py <文件或目录> [...]
有错误时退出码为 1。错误必须修正；提示供编辑者核对，不阻止提交。
规则说明见 docs/intake-format.md。
"""
import json
import os
import re
import sys
from collections import defaultdict

from jsonschema import Draft202012Validator

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = os.path.join(ROOT, "schemas", "intake.schema.json")
VOCAB = os.path.join(ROOT, "mappings", "component-types.json")


def load(path):
    with open(path, encoding="utf8") as f:
        return json.load(f)


def mentioned(item, text, lang):
    """食材名是否出现在步骤原文里。只用于提示，宽松匹配。"""
    if lang == "zh":
        cands = {item, item[-2:], item[:-1]} - {""}
        return any(c in text for c in cands)
    cands = {item.lower(), item.lower().split()[-1]}
    low = text.lower()
    return any(re.search(r"\b" + re.escape(c) + r"(e?s)?\b", low) for c in cands)


def validate(recipe, schema=None, vocab=None):
    """返回 (errors, warnings)，均为字符串列表。"""
    schema = schema or load(SCHEMA)
    vocab = vocab or load(VOCAB)
    errors = [f"格式：{'/'.join(map(str, e.absolute_path)) or '(根)'} {e.message}"
              for e in Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).iter_errors(recipe)]
    if errors:
        return errors, []

    warnings = []
    lang = recipe["lang"]
    comps = recipe["components"]
    sections = [(c["id"], c["name"], c) for c in comps] + [("assembly", "合成与装盘", recipe["assembly"])]

    # id 全菜唯一
    seen = defaultdict(int)
    for _, _, sec in sections:
        for ing in sec["ingredients"]:
            seen[ing["id"]] += 1
    for c in comps:
        seen[c["id"]] += 1
    errors += [f"id「{i}」重复 {n} 次" for i, n in seen.items() if n > 1]

    used_ing = defaultdict(list)   # 食材 id -> [(步骤 qty, unit)]
    used_comp = set()
    for idx, (sid, sname, sec) in enumerate(sections):
        own = {i["id"]: i for i in sec["ingredients"]}
        earlier = {c["id"]: c for c in comps[:idx]} if sid != "assembly" else {c["id"]: c for c in comps}
        for n, step in enumerate(sec["steps"], 1):
            where = f"「{sname}」第 {n} 步"
            missing = []
            for u in step["uses"]:
                ref = u["ref"]
                if ref in own:
                    ing = own[ref]
                    used_ing[ref].append(u)
                    if u.get("unit") and ing["unit"] and u["unit"] != ing["unit"]:
                        errors.append(f"{where}：「{ing['item']}」单位 {u['unit']} 与食材表 {ing['unit']} 不一致")
                    if not mentioned(ing["item"], step["text"], lang):
                        missing.append(ing["item"])
                elif ref in earlier:
                    used_comp.add(ref)
                    if u.get("qty") is not None:
                        errors.append(f"{where}：引用组件「{ref}」不应写用量")
                else:
                    errors.append(f"{where}：引用「{ref}」不存在，或不属于本组件 / 前面的组件")
            if missing:
                warnings.append(f"{where}：步骤原文中未找到 {'、'.join(missing)}，请核对引用")

        for ing in sec["ingredients"]:
            uses = used_ing.get(ing["id"])
            if not uses:
                errors.append(f"「{sname}」的食材「{ing['item']}」没有被任何步骤使用")
                continue
            part = [u["qty"] for u in uses if u.get("qty") is not None]
            if part and ing["qty"] is not None and sum(part) > ing["qty"]:
                errors.append(f"「{sname}」的「{ing['item']}」各步用量合计 {sum(part)} 超过总量 {ing['qty']}")
            if ing.get("listed_in_source") is False:
                warnings.append(f"「{sname}」的「{ing['item']}」原文食材表未列出，用量未知")

    errors += [f"组件「{c['name']}」没有被后续步骤使用" for c in comps if c["id"] not in used_comp]

    types = vocab["types"]
    for c in comps:
        t = c.get("type")
        if t and t not in types:
            warnings.append(f"组件「{c['name']}」的类型「{t}」不在词表中，可作为新类型提议")
        elif t and types[t]["status"] != "active":
            warnings.append(f"组件「{c['name']}」的类型「{t}」状态为 {types[t]['status']}")

    p = recipe["provenance"]
    if p["source_path"] is None:
        warnings.append("未登记原始资料的本地位置（provenance.source_path）")
    if p["locator"] is None:
        warnings.append("未登记页码或时间点（provenance.locator）")
    if recipe["servings"]["qty"] is None:
        warnings.append("份量未知（servings.qty），SOP 无法按人数缩放")
    return errors, warnings


def collect(paths):
    for p in paths:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                if name.endswith(".json"):
                    yield os.path.join(p, name)
        else:
            yield p


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    schema, vocab = load(SCHEMA), load(VOCAB)
    failed = 0
    for path in collect(argv):
        try:
            errors, warnings = validate(load(path), schema, vocab)
        except json.JSONDecodeError as e:
            errors, warnings = [f"JSON 解析失败：{e}"], []
        status = "未通过" if errors else "通过"
        print(f"\n{path}：{status}（错误 {len(errors)}，提示 {len(warnings)}）")
        for e in errors:
            print(f"  ✗ {e}")
        for w in warnings:
            print(f"  · {w}")
        failed += bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
