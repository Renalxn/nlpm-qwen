# nlpm-qwen

> 自然语言编程管理器（Qwen Code 版）

把自然语言工件（Skills、Agents、Rules、Commands 等 Markdown 文件）当作可被 Lint 和评分的"程序"来管理。

## 功能

对标 [NLPM](https://github.com/xiaolai/nlpm) 的完整功能，适配 Qwen Code 和中文：

| 命令 | 功能 |
|------|------|
| `nlpm ls [路径]` | 发现并列出所有 NL 工件 |
| `nlpm score [路径]` | 100 分制质量评分 |
| `nlpm check [路径]` | 跨组件一致性检查 |
| `nlpm fix [路径] [--dry-run]` | 自动修复确定性问题 |
| `nlpm trend [路径]` | 跟踪质量评分趋势 |
| `nlpm init [路径]` | 初始化项目 NLPM 配置 |
| `nlpm security [路径]` | 安全扫描 |

## 安装

nlpm-qwen 位于 `~/.qwen/nlpm-qwen/`，是 Qwen Code 的全局基础设施。

```bash
# 添加到 PATH（可选）
echo 'export PATH="$HOME/.qwen/nlpm-qwen:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## 使用

```bash
# 列出项目中的 NL 工件
nlpm ls ~/projects/my-project/

# 对工件进行质量评分
nlpm score ~/projects/my-project/

# 检查跨组件一致性
nlpm check ~/projects/my-project/

# 自动修复问题（预览模式）
nlpm fix ~/projects/my-project/ --dry-run

# 查看评分趋势
nlpm trend ~/projects/my-project/

# 安全扫描
nlpm security ~/projects/my-project/
```

## 规则

50 条自然语言编程规则（中文版），位于 `rules/core-rules.md`。

核心规则：
- R01: 不要使用模糊量化词
- R02: 每一行都要有价值
- R03: 用正面表述而不是禁止
- R04: 描述是触发器，不是总结
- R05: 控制在 500 行以内
- R06: 代码示例必须是可运行的
- R09: 智能体要有示例
- R12: 定义输出格式
- R17: 处理错误路径
- R22: 规则要可测试

## 评分标准

100 分制，详见 `scoring/rubric.md`：

| 分数段 | 等级 |
|--------|------|
| 90-100 | 优秀 |
| 80-89 | 良好 |
| 70-79 | 及格 |
| 60-69 | 弱 |
| <60 | 需要重写 |

## 自身状态

nlpm-qwen 已通过自身检查：
- 评分：100/100（优秀）
- 一致性：0 个问题
- 安全扫描：0 个问题

## 许可证

MIT
