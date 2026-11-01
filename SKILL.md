---
name: composing-anime-memes
description: Use when creating, sourcing, repairing, or accepting anime avatar GIF templates for meme-generator, especially when original anime GIFs must be found automatically, avatars look like stickers, batch output lacks scene fit, or tests pass without visual evidence.
---

# Composing Anime Memes

## Overview

用户明确只做一张时，直接完成这一张并进入终审；批量任务才先完成 **1 个代表样板**，再决定是否扩展。头像形状必须来自目标区域：角色用脸部或头部轮廓，画和照片用实际四边形，杯身印花用杯身区域。**禁止无依据的圆形、椭圆或统一头像形状。**

没有通过逐模板完整 GIF 初审和用户终审的成果，不得标记为完成。本技能用于 `meme-generator 0.1.x` 的头像动画模板；纯文字模板或单纯后端 bug 不需要这套构图流程。

## Required workflow

复制并逐项完成：

- [ ] 优先复用已验证素材；用户未给 GIF 且没有可复用素材时，采用首个合格候选，不扩张候选池。
- [ ] 确认番剧正片来源并保留原片动作；优先双人/多人，记录选角槽位。
- [ ] 为场景写一句“头像是角色 / 印花 / 照片或画 / 粉笔画 / 不适合”。
- [ ] 单张任务直接制作目标模板；批量任务先做一个代表样板，完整 GIF 初审和用户方向确认后才扩展。
- [ ] 按目标类型声明 `shape`，保存目标蒙版、四边形、轨迹和头像索引。
- [ ] 按“原片底层 → 头像层 → 原片前景层”合成；旧五官随旧脸清除，头发等前景最后恢复。
- [ ] 静止目标复用蒙版；运动目标只标必要关键帧并插值，不默认逐帧手标。
- [ ] 用真实后端生成完整 GIF 和前后对照，运行机械验证并播放完整 GIF 初审。
- [ ] 提交用户终审；重新渲染后重新验收。
- [ ] 分别报告通过、待修和淘汰，不混成“全部完成”。

### 0. 快速选材

不得要求用户补素材。只接受能确认来自动画番剧正片片段的动态 GIF；剧场版、游戏、漫画、插画、VTuber、真人、同人动画、AMV、AI 画面和来源不明素材均不合格。保留原片动作、帧顺序和节奏。

已有通过来源校验且适合当前构图的 GIF 时直接复用。需要找新片时，找到首个满足来源、动作和构图要求的候选就进入制作，不为“可能有更好素材”继续扩大搜索。

优先双人/多人：双人为 `bot + trigger`，多人额外槽位为 `group_affection_random`；单人仅在没有合格多人候选时作为备选。完整规则见 [source-selection.md](references/source-selection.md)。

```bash
python scripts/validate_source.py candidates.json
python scripts/validate_source.py candidates.json --check-files
```

第一个命令只做结构预检；GIF 下载后必须运行第二个命令。`SOURCES_VALID` 不代表番剧来源、动作或视觉已核验。

### 1. 目标形状契约

| 场景语义 | 模式 | `actors[].shape` | 填充方式 |
|---|---|---|---|
| 被抱、被咬、被展示的角色 | `character` | `target_mask` | 按原角色脸部或头部轮廓填充 |
| 杯子、衣物、包装上的图案 | `print` | `surface_mask` | 按物体印花区域填充并贴合曲面 |
| 书页、相框、相册、方形绘画 | `photo` | `quad_fill` | 填满实际方形或透视四边形 |
| 黑板或粉笔画 | `chalk` | `target_mask` | 在目标轮廓内生成可辨认线条 |
| 目标过小、动作不清、跟踪失败 | `reject` | 不适用 | 淘汰、换素材或明确待修 |

蒙版是黑白灰度图：**白色显示头像，黑色保留原片，灰色表示过渡。** 角色和印花不得用圆形蒙版代替目标轮廓；不得为了统一输入形状而裁剪成圆形。完整资产规则见 [composition-patterns.md](references/composition-patterns.md)。

角色替换必须分成三层，顺序固定为 **原片底层 → 头像层 → 原片前景层**：

- `target_mask` 覆盖完整旧脸和旧五官，眉毛、眼睛、眼线、鼻子、嘴默认全部替换，不得留下双重五官或旧肤色残边。
- `foreground_mask` 最后恢复原片的刘海、头发、帽子、饰品、手等前景；它与头像蒙版重叠时，前景必须位于头像上方。
- 静止前景使用 `actors[].foreground_mask`；运动前景使用 `actors[].frames[].foreground_mask` 覆盖默认值。

不能用单张蒙版挖洞同时表达“删除旧五官”和“恢复头发前景”，也不能把旧眉毛等放入前景蒙版。放大局部检查清理结果，不能仅凭蒙版文件存在就认定扣干净了。

### 2. 单张与批量流程

**用户明确只做一张、一个或单个模板时，进入单张流程。** 直接制作用户要求的模板，不寻找额外场景，不把它称为代表样板，不等待扩展批准，也不编写批量渲染或批量验收工具。完成真实 GIF、机械验证、完整播放初审和用户终审后即交付。

**用户要求多个、一批或批量模板时，进入批量流程。** 先制作一个代表样板，完整 GIF 初审和用户方向确认后才扩展。不得为了“以后可能有用”提前制作额外场景、新通用渲染器或全量逐帧轨迹。

两种流程都复用静止蒙版，运动目标只标必要关键帧并插值；都保留目标形状、旧脸清理、前景遮挡和最终视觉验收，不因单张而省略。

### 3. 使用脚本留下证据

从本技能目录运行：

```bash
python scripts/validate_scene.py scene.json
python scripts/preview_scene.py scene.json previews/out avatar.png --source original.gif
python scripts/verify_scene.py previews/out/after.gif --expected-duration 1000
```

`validate_scene.py` 会读取相对于 scene JSON 的真实目标蒙版和前景蒙版，检查形状契约、灰度、尺寸和有效区域；只填写蒙版路径不算通过。示例配置见 [character_scene.json](examples/character_scene.json)。

返工时向预览脚本追加 `--baseline saved-old.gif`。缺少旧版会报错；新版不得伪造 before。新场景只展示未合成原片。正式完成前再运行 `python scripts/validate_scene.py scene.json --completed`。

`verify_scene.py` 输出 `MECHANICAL_ONLY` 是正常结果，不是视觉批准，也不能证明旧五官已清理或图层顺序正确。

### 4. 完整 GIF 初审与用户终审

逐模板按正常速度播放完整 GIF，检查动作关系、前后遮挡、旧五官残留、漂移、闪烁、循环接缝和实际聊天显示尺寸。静帧、联系表和抽样只能辅助调参，不能代替全量动态初审。

初审记录绑定实际 GIF SHA256。用户终审通过后记录 `reviewer`、GIF `sha256` 和 `source_sha256`；任何重新渲染都会使旧审批失效。详细清单见 [acceptance-contract.md](references/acceptance-contract.md)。

## Delivery contract

最终回复必须分开列出。数量只能来自实际验收记录；没有记录时写“未核验”，不得用 0、估算值或计划数代替：

```text
机械验证：通过 X/Y（无记录时写未核验）
完整 GIF 模型初审：通过 X/Y，证据路径（无记录时写未核验）
用户终审：通过 X/Y（无记录时写未核验）
待修或 reject：键名及原因
```

只要仍有未初审或未经用户终审的模板，就写“部分完成”，不得写“全部效果已保证”。

## Rationalizations

| 借口 | 现实 |
|---|---|
| “圆形是头像的标准形状” | 目标形状才是形状依据；圆形只能在目标本身确实是圆形时使用 |
| “保留原眉毛和头发会更自然” | 头发应作为前景恢复，旧眉毛等五官方应随旧脸替换，两者不能混在一层 |
| “一张蒙版已经能出图” | 能出图不等于旧脸清干净；目标替换与前景恢复必须分别表达 |
| “先多找素材、多做几个更稳” | 首个合格素材和一个样板足以确认方向，扩张只会放大返工 |
| “统一贴片只需再修羽化和颜色” | 目标形状或图层错误时，边缘参数不能创造正确构图 |
| “测试全绿、GIF 都能生成” | 只证明可运行，不证明场景契合 |
| “抽样盲评就够了” | 抽样能调参，不能替未检查的模板背书 |
| “高级 UV / 网格 / AI 抠图可以自动保证” | 技术不能替用户做最终视觉判断 |
| “已经投入很多，不能淘汰” | 不合格素材留为待修或 reject，不算完成 |
| “没有验收记录就写 0/100，比较保守” | 0 是实测数量，不是未知；无记录必须写未核验 |

## Red flags — STOP

- 不读取目标区域就使用圆形、椭圆或统一头像形状。
- 头像直接盖住刘海、头发、帽子或其他应保持在上层的原片前景。
- 旧眉毛、眼睛、眼线、鼻子、嘴或肤色残边仍叠在新头像上。
- 用一张蒙版同时承担旧脸替换和前景恢复，或把旧五官放进 `foreground_mask`。
- 先写通用贴片渲染器，再讨论头像在场景中的身份。
- 一个样板尚未确认，就继续找片、标注或批量扩张。
- 静止目标也逐帧重复标注，或对所有帧默认人工跟踪。
- 只看静帧或抽样就宣布全部通过。
- 把 `MECHANICAL_ONLY` 写成“视觉质量保证”。
- 重新渲染后沿用旧审批。
- 将未通过项计入完成数量。
- 把未知验收数量写成 0/100、估算值或计划数。
