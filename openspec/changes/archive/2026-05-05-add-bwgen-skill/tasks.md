## 1. 创建技能骨架

- [x] 1.1 创建 `.claude/skills/bwgen/scripts/` 目录
- [x] 1.2 编写 `SKILL.md`（技能名称、描述、触发条件、使用说明）

## 2. 实现核心脚本

- [x] 2.1 编写 `bw_gen.py`，解析 `-p`、`-r`、`-s`、`-o` 参数
- [x] 2.2 实现 Step 1：纯文生图，生成黑底图，追加 "pure black background" 到 prompt
- [x] 2.3 实现 Step 2：以黑底图为输入，调用 Gemini 编辑背景为白色
- [x] 2.4 保存双图：`<slug>_black.png` 和 `<slug>_white.png`

## 3. 测试验证

- [x] 3.1 用简单描述（如"一个苹果"）测试完整流程
- [x] 3.2 验证输出双图尺寸一致，可传入 bwdiff
- [x] 3.3 验证异常情况：API 密钥缺失时报错退出
