# Recipe Intake 格式 v0.1

外部编辑系统把菜谱按本格式拆分、编辑好，再提交给知识库。

- 机器可读的定义：[schemas/intake.schema.json](../schemas/intake.schema.json)
- 样例：[intake/examples/](../intake/examples/)（含由样例生成的 SOP）

## 分工

| 外部编辑系统 | 知识库 |
|---|---|
| 只录原文（Source Knowledge），单一语言 | 校验、翻译、分类、主材、过敏原，全部标为 AI 推断 |
| 决定怎样拆分组件 | 生成 SOP，转换为库内完整双语格式 |

## 结构

```
provenance   来源：资料类型、书名、作者、本地路径、页码/时间点、编辑者、编辑日期
lang         原文语言（zh / en …）
name         菜名（原文）
servings     份量：qty 数字 + raw 原文写法；原文没写都填 null
components[] 组件：id、name、type（可选）、ingredients[]、steps[]
assembly     合成与装盘：ingredients[]、steps[]（不算组件）
notes[]      原文中的提示（可选）
```

食材：`id`、`raw`（原文整行）、`item`、`qty`（数字）、`unit`、`prep`（原文写的处理方式）、`listed_in_source`（可选）。

步骤：`text`（原文）、`uses[]`。每个 use 引用一个食材 id 或前面组件的 id，原文写明本步用量时加 `qty` 和 `unit`。

## 规则

1. **原文不改写。** `raw` 和 `text` 照抄原文；`item`、`qty`、`unit`、`prep` 是从原文拆出来的，原文没有就填 `null`，不估算。
2. **组件自带食材和步骤。** 组件的步骤只能用本组件的食材，或前面组件的产出；装盘可以引用所有组件。
3. **每样食材都要被步骤用到，每个组件都要被后面的步骤用到。**
4. **一行原文写了多样食材**（如「盐、味精、胡椒面 适量」）**时拆成多项**，`raw` 都写同一整行。
5. **同一调料用在多个组件时**，在每个组件里各列一项（id 不同），`raw` 相同。
6. **同一食材分几步用**：原文写了每步用量就在 use 上填 `qty`；没写的，SOP 显示「分次使用，总量 X」。
7. **原文食材表没列、只在步骤里出现的食材**：照样列出，`listed_in_source: false`，`raw` 写步骤原话，`qty` 填 `null`。
8. **id** 用小写字母、数字和连字符，全菜唯一。
9. **原始资料不入库**，只在 `provenance.source_path` 登记它在本地电脑的位置，在 `locator` 登记页码或时间点。

## 组件类型（type）

`name` 自由填写，沿用原文叫法。可以泛用到其他菜的组件，再加 `type`，取自 [mappings/component-types.json](../mappings/component-types.json)。

- **按菜系划分作用域，不做跨菜系对应。** 英文只是释义。
- **可升级。** 填了词表外的 type 不算错误，校验会提示「可作为新类型提议」。确认后加入词表，状态设为 `active`，并升级版本号。
- **初版词表的定义待审。** v1.0 的 6 个中餐类型（码味、码芡、挂糊、拍粉、滋汁、高汤）定义由 AI 起草，`review_status` 为 `pending`，需要人工确认。

## 校验

```
python tools/validate_intake.py intake/
```

**错误**（必须修正，有错误时退出码为 1）：
- 格式不符
- id 重复
- 引用不存在或越界
- 食材或组件没有被使用
- 单位不一致
- 分步用量合计超过总量

**提示**（供核对，不阻止提交）：
- 步骤原文里找不到被引用的食材名
- 原文未列出的食材
- 词表外的类型
- 未登记来源位置或页码
- 份量未知

## SOP

```
python tools/sop.py intake/examples/xianliu-yu-pian.json [--scale 2] [-o 输出.md]
```

SOP 由两部分组成：
- **备料称量清单**：按组件分组。
- **制作步骤**：每步列出用料和用量。

生成规则：
- 未通过校验的菜谱不生成 SOP。
- 原文没给的量，照录原文写法（以脚注列出），不估算。
- `--scale` 是线性换算，清单里会提醒油、调味等不一定按比例增减，由 Chef 判断。
