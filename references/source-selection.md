# 番剧 GIF 自动选材

## 来源硬门槛

用户未提供原始 GIF 时，使用当前环境可用的搜索或浏览器工具自动寻找，不要求用户补素材。只接受能够确认来自**动画番剧正片连续片段**的动态 GIF。

以下来源一律排除：

- 来源不明、只有“动漫风”而无法确认番剧的素材。
- 剧场版、游戏或过场动画、漫画、插画、VTuber、真人、同人动画、AMV 和 AI 生成画面。
- 静态图、单帧 GIF、把静帧做成的滑动或缩放动画。
- 已经合成过群友头像的模板，不得冒充原始片段。

来源页或可靠元数据必须能确认番剧名。集数、时间码等信息不知道就省略，不得编造。公开来源不可访问时换其他公开候选，不绕过登录、付费墙或反爬限制。

## 动作保留

保留所选连续片段的原片动作、帧顺序和节奏。不得倒放、调速、AI 补帧或把动作替换成另一段；可以裁掉所选片段前后的无关内容，但不能拼接改变动作关系。

`origin_confirmed`、`animated`、`motion_preserved` 只有在实际核验后才能写 `true`。校验脚本不能机械证明番剧来源或动作是否自然。

## 人数与选角

优先双人、多人互动场景。只有当前搜索没有合格双人或多人候选时，才列单人备选；不得用单人凑多人目标。

| 人数 | `priority` | `casting` |
|---|---|---|
| 1（仅备选） | `fallback` | `["trigger"]` |
| 2 | `preferred` | `["bot", "trigger"]` |
| 3 及以上 | `preferred` | 前两位为 `bot`、`trigger`，其余均为 `group_affection_random` |

`group_affection_random` 是运行时槽位：从本群好感榜随机补人。制作模板时不虚构具体群友，不把好感排名当成随机结果。多人模板按固定人数分别制作，不做 2–4 人自适应模板。

## 候选清单

每个候选记录：

- `key`、`anime_title`、`source_url`、`gif`。
- `source_type: "anime_episode"`。
- `origin_confirmed`、`animated`、`motion_preserved`。
- `participant_count`、`priority`、`casting`。
- 可选 `episode`、`note`；未知信息不填，不编造。

完整结构见 `examples/source_candidates.json`。示例只展示结构，不是已核验的真实素材；其中的布尔值是占位符，复制后必须重新核验，不能直接当作真实候选提交。

```bash
python scripts/validate_source.py candidates.json
python scripts/validate_source.py candidates.json --check-files
```

第一个命令只做结构预检；GIF 下载后必须运行第二个命令。`--check-files` 以清单所在目录解析相对 GIF 路径，并检查真实 GIF 至少有两个不同帧。成功输出 `SOURCES_VALID` 只表示候选记录通过机械校验，不代表番剧来源、动作、构图或视觉验收通过。

## 无合格候选

继续搜索其他公开候选；仍没有时明确报告“无合格候选”。不得放宽番剧来源、动作保留或人数规则来凑数。候选校验通过后，才进入场景分类和代表样板。
