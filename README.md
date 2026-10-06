# Recipe Knowledge Base

个人菜谱知识库。

## 结构
- skills/western：西餐
- skills/chinese：中餐（按原始信息语言归类，技法来源另见 `technique_origin`）
- techniques/sichuan：川菜技法（爆、炒、熘、煎、浸、炸）
- assets：图片
- mappings：跨库映射（致敏食材关键词、食材分类）
- review：待复核项
- docs：操作笔记

## 约定
- 文件名与 `id` 一致：`skills/chinese/yuxiang-rou-pian.json` 的 `id` 为 `yuxiang-rou-pian`。
- 菜例必备字段：`technique`、`sub_technique`、`flavor_profile`（无对应技法时为 `null`）；`method` 为可选的工艺关键词列表。
- 菜例 → 技法：`technique.technique_ref`。技法 → 菜例：`related_dishes.dish_refs`，与 `related_dishes.original` 按位置对应，未收录的菜为 `null`。
- 步骤：`method_steps` 为烹饪步骤（整道菜或 `components[]` 内），`assembly` 为装盘。
