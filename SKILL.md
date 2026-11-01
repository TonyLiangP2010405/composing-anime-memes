---
name: composing-anime-memes
description: Use when creating, sourcing, repairing, or accepting anime avatar GIF templates for meme-generator, especially when original anime GIFs must be found automatically, avatars look like stickers, batch output lacks scene fit, or tests pass without visual evidence.
---

# Composing Anime Memes

## Overview

用户未提供原始 GIF 时，先自动寻找并校验番剧双人/多人候选，再确定“头像在场景里是什么”和渲染方式。**没有通过逐模板完整 GIF 初审和用户终审的成果，不得标记为完成。**

本技能用于 `meme-generator 0.1.x` 的头像动画模板。纯文字模板或单纯后端 bug 不需要这套构图流程。

## Required workflow

复制并逐项完成：

- [ ] 用户未给 GIF 时自动找片，确认番剧正片来源并保留原片动作。
- [ ] 优先双人/多人，记录选角槽位并校验候选清单。
- [ ] 为每个场景写一句“头像是角色 / 印花 / 照片 / 粉笔画 / 不适合”。
- [ ] 每类先做代表样板，视觉方向通过后才批量。
- [ ] 保存参考帧、逐帧轨迹、允许变化蒙版和头像索引。
- [ ] 用真实后端生成完整 GIF 和前后对照。
- [ ] 运行机械验证，再逐模板播放完整 GIF 初审。
- [ ] 提交用户终审；重新渲染后重新验收。
- [ ] 分别报告通过、待修和淘汰，不混成“全部完成”。

### 0. 自动选材（用户未提供 GIF 时）

不得要求用户补素材。只接受能确认来自动画番剧正片片段的动态 GIF；剧场版、游戏、漫画、插画、VTuber、真人、同人动画、AMV、AI 画面和来源不明素材均不合格。保留原片动作、帧顺序和节奏。

优先双人/多人：双人为 `bot + trigger`，多人额外槽位为 `group_affection_random`；单人仅在没有合格多人候选时作为备选。找不到合格素材就继续找或报告无候选，不降低标准。完整规则见 [source-selection.md](references/source-selection.md)。

```bash
python scripts/validate_source.py candidates.json
python scripts/validate_source.py candidates.json --check-files
```

第一个命令只做结构预检；GIF 下载后必须运行第二个命令。候选示例见 [source_candidates.json](examples/source_candidates.json)。`SOURCES_VALID` 不代表番剧来源、动作或视觉已核验。

### 1. 先分类，不先写通用渲染器

| 场景语义 | 模式 | 必要结果 |
|---|---|---|
| 被抱、被咬、被展示的角色 | `character` | 非矩形角色轮廓、动作关系和独立前景 |
| 杯子、衣物、包装上的图案 | `print` | 无照片白底，继承曲面、纹理和明暗 |
| 书页、相框、相册中的照片 | `photo` | 纸边、透视、环境光和手指遮挡 |
| 黑板或粉笔画 | `chalk` | 可辨认线条和板面纹理，不是淡彩照片 |
| 目标过小、动作不清、跟踪失败 | `reject` | 淘汰、换素材或明确待修 |

无法写出这句话时，不得开始批量。完整模式见 [composition-patterns.md](references/composition-patterns.md)。

### 2. 代表样板先于批量

每类选择少量不同动作和遮挡的场景。样板未通过完整 GIF 初审时，不得用“先做出 100 个再统一修”继续扩张。

羽化、颜色匹配、UV、网格、光流或 AI 抠图都只是工具，不能替代场景分类和视觉验收。非照片场景不得保留矩形照片底；照片场景不得为了“去矩形”破坏纸张语义。

### 3. 使用脚本留下证据

从本技能目录运行：

```bash
python scripts/validate_scene.py scene.json
python scripts/preview_scene.py scene.json previews/out avatar.png --source original.gif
python scripts/verify_scene.py previews/out/after.gif --expected-duration 1000
```

返工时向预览脚本追加 `--baseline saved-old.gif`。缺少旧版会报错；新版不得伪造 before。新场景只展示未合成原片。

正式完成前再运行：

```bash
python scripts/validate_scene.py scene.json --completed
```

`verify_scene.py` 输出 `MECHANICAL_ONLY` 是正常结果，不是视觉批准。

### 4. 完整 GIF 初审与用户终审

逐模板按正常速度播放完整 GIF，检查动作关系、前后遮挡、漂移、闪烁、循环接缝和实际聊天显示尺寸。静帧、联系表和抽样只能辅助调参，不能代替全量动态初审。

初审记录绑定实际 GIF SHA256。用户终审通过后记录 `reviewer`、GIF `sha256` 和 `source_sha256`；任何重新渲染都会使旧审批失效。详细清单见 [acceptance-contract.md](references/acceptance-contract.md)。

## Delivery contract

最终回复必须分开列出。数量只能来自实际验收记录；没有记录时写“未核验”，不得用 0、估算值或计划数代替：

```text
机械验证：通过 X/Y（无记录时写未核验）
完整 GIF 模型初审：通过 X/Y，证据路径（无记录时写未核验）
用户终审：通过 X/Y（无记录时写未核验）
待修或 reject：键名及原因
```

只要仍有未初审或未经用户终审的模板，就写“部分完成”，不得写“全部效果已保证”。示例配置见 [character_scene.json](examples/character_scene.json)。

## Rationalizations

| 借口 | 现实 |
|---|---|
| “统一矩形贴片只需再修羽化和颜色” | 角色身份错误时，边缘参数不能创造动作关系 |
| “测试全绿、GIF 都能生成” | 只证明可运行，不证明场景契合 |
| “抽样盲评就够了” | 抽样能调参，不能替未检查的模板背书 |
| “高级 UV / 网格 / AI 抠图可以自动保证” | 技术不能替用户做最终视觉判断 |
| “已经投入很多，不能淘汰” | 不合格素材留为待修或 reject，不算完成 |
| “没有验收记录就写 0/100，比较保守” | 0 是实测数量，不是未知；无记录必须写未核验 |

## Red flags — STOP

- 先写通用贴片渲染器，再讨论头像在场景中的身份。
- 用“先做 100 个”绕过代表样板。
- 只看静帧或抽样就宣布全部通过。
- 把 `MECHANICAL_ONLY` 写成“视觉质量保证”。
- 重新渲染后沿用旧审批。
- 将未通过项计入完成数量。
- 把未知验收数量写成 0/100、估算值或计划数。
