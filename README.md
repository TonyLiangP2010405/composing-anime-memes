# composing-anime-memes

给 [meme-generator](https://github.com/MemeCrafters/meme-generator) 做**头像模板**的 Agent Skill：从头像只替换表情包里一块**圆形或方形**区域（电视屏幕、手机屏幕、来电头像位、相框、放大镜镜片、表盘、灯泡玻璃…），到选素材、量几何、生成模板、机械验证与视觉验收的完整流程。

椭圆（按脸型拟合的蛋形）明确淘汰——它在聊天尺寸下会读成"贴上去的一坨"，这是本 skill 迭代后被用户否掉的方案。

## 目录

```text
SKILL.md                          # 主流程：形状契约、渲染契约、选素材、验收、红旗清单
references/composition-patterns.md # 几何测量与参数（circle/square/rect/roundrect、feather、depth、zoom）
references/source-selection.md     # 找素材：发表情站内抓取（含接口/退避/坑）、360 图片搜索、别用的路线
references/acceptance-contract.md  # 三关验收：机械验证 / 视觉初审 / 用户终审
scripts/harvest_fabiaoqing.py      # 发表情（fabiaoqing.com）搜索页抓取：list → thumbs → large
scripts/validate_pack.py           # 校验一个模板包：几何、素材、SHA-256、渲染、头像是否真的落在开口里
tests/test_validate_pack.py        # validate_pack.py 的测试
```

## 快速使用

```bash
# 1. 找素材（中文斗图直接抓站内搜索，比搜索引擎干净）
python scripts/harvest_fabiaoqing.py list   --out /tmp/fbq --pages 6 --keywords 电视 手机 屏幕 圆形
python scripts/harvest_fabiaoqing.py thumbs --out /tmp/fbq
python scripts/harvest_fabiaoqing.py large  --out /tmp/fbq --pick 0 2 3

# 2. 校验一个模板包（scenes.json + render.py + assets/）
python scripts/validate_pack.py path/to/memes/<pack>

# 3. 跑 skill 自己的测试
python -m pytest tests -q
```

`validate_pack.py` 输出 `MECHANICAL_ONLY` 表示没有结构问题，**不代表视觉合格**——视觉初审和用户终审见 `references/acceptance-contract.md`。

## 核心规则

- 替换区必须是原图里已经画出来的**圆形或方形**开口，形状来自原图，不按头像输入变化。
- 头像先裁到脸部再用 cover 缩放填满开口；帽子、外侧头发、衣领、背景不得占满替换区。
- 原图的描边、机身、镜框、字幕全部保留；box 不得吃进描边。
- 动图用静止开口 + 逐帧合成；只有开口本身会动时才逐帧 box。
- 机械测试全绿 ≠ 视觉合格；没有验收记录就写"未核验"，不写 0 或估算值。

## License

仅供个人/群内非商业使用；素材版权归原作者。
