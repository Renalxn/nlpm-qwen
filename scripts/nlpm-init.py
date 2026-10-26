#!/usr/bin/env python3
"""nlpm-init: 为项目初始化 nlpm-qwen 配置

创建项目级别的 NLPM 配置文件和目录结构。

用法:
    python3 nlpm-init.py [项目路径]
    python3 nlpm-init.py ~/projects/new-project/
"""

import sys
import json
from pathlib import Path
from datetime import datetime

def create_directory_structure(project_root: Path) -> None:
    """创建目录结构"""
    dirs = [
        project_root / ".nlpm",
    ]
    
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

def create_config_file(project_root: Path) -> None:
    """创建配置文件"""
    config = {
        "version": "1.0",
        "created": datetime.now().isoformat(),
        "score_threshold": 70,
        "rules": {
            "R01": {"enabled": True, "max_penalty": -20},
            "R05": {"enabled": True, "threshold": 500},
            "R09": {"enabled": True, "min_examples": 1},
        },
        "language": "zh-CN",
        "auto_fix": True,
    }
    
    config_path = project_root / ".nlpm" / "config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')

def create_readme(project_root: Path) -> None:
    """创建 NLPM README"""
    readme = f"""# NLPM 配置

本项目已配置 nlpm-qwen 质量管理系统。

## 配置

- 评分阈值: 70 分（可调整）
- 语言: 中文
- 自动修复: 启用

## 使用方法

### 检查项目质量
```bash
python3 ~/.qwen/nlpm-qwen/scripts/nlpm-score.py {project_root}
```

### 自动修复问题
```bash
python3 ~/.qwen/nlpm-qwen/scripts/nlpm-fix.py {project_root}
```

### 查看趋势
```bash
python3 ~/.qwen/nlpm-qwen/scripts/nlpm-trend.py {project_root}
```

## 配置文件

- `.nlpm/config.json` - 项目配置
- `.nlpm/README.md` - 本文件

## 全局配置

全局 nlpm-qwen 配置位于: `~/.qwen/nlpm-qwen/`
"""
    
    readme_path = project_root / ".nlpm" / "README.md"
    readme_path.write_text(readme, encoding='utf-8')

def create_agents_template(project_root: Path) -> None:
    """创建 AGENTS.md 模板（如果不存在）"""
    agents_path = project_root / "AGENTS.md"
    
    if agents_path.exists():
        return
    
    template = f"""# {project_root.name}

> 项目描述（一句话）

## 架构

```
{project_root.name}/
├── agents/          # 智能体定义
├── skills/          # 技能定义
├── rules/           # 规则定义
└── AGENTS.md        # 本文件
```

## 构建

```bash
# 构建命令
echo "TODO: 添加构建命令"
```

## 运行

```bash
# 运行命令
echo "TODO: 添加运行命令"
```

## 测试

```bash
# 测试命令
echo "TODO: 添加测试命令"
```

## 约定

- 所有 NL 工件应遵循 nlpm-qwen 规则
- 使用 `python3 ~/.qwen/nlpm-qwen/scripts/nlpm-score.py` 检查质量
- 目标评分: 70+ 分
"""
    
    agents_path.write_text(template, encoding='utf-8')

def main():
    # 解析参数
    if len(sys.argv) > 1:
        project_root = Path(sys.argv[1]).resolve()
    else:
        project_root = Path.cwd()
    
    if not project_root.exists():
        print(f"错误: 路径不存在: {project_root}", file=sys.stderr)
        sys.exit(1)
    
    if not project_root.is_dir():
        print(f"错误: 路径不是目录: {project_root}", file=sys.stderr)
        sys.exit(1)
    
    print(f"NLPM 项目初始化 - {project_root}\n")
    
    # 创建目录结构
    print("✓ 创建 .nlpm/ 目录")
    create_directory_structure(project_root)
    
    # 创建配置文件
    print("✓ 创建 .nlpm/config.json")
    create_config_file(project_root)
    
    # 创建 README
    print("✓ 创建 .nlpm/README.md")
    create_readme(project_root)
    
    # 创建 AGENTS.md 模板
    agents_path = project_root / "AGENTS.md"
    if not agents_path.exists():
        print("✓ 创建 AGENTS.md 模板")
        create_agents_template(project_root)
    else:
        print("ℹ AGENTS.md 已存在，跳过")
    
    print(f"\n项目已初始化完成！")
    print(f"\n下一步:")
    print(f"  1. 编辑 AGENTS.md，填写项目描述和架构")
    print(f"  2. 运行评分: python3 ~/.qwen/nlpm-qwen/scripts/nlpm-score.py {project_root}")
    print(f"  3. 根据评分结果改进你的 NL 工件")

if __name__ == "__main__":
    main()
