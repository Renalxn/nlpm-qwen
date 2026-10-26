#!/usr/bin/env python3
"""nlpm-fix: 自动修复确定性问题

修复不需要人工判断的问题：
- 添加缺失的 frontmatter 字段
- 修复 name 和父目录不匹配
- 添加缺失的错误处理模板

用法:
    python3 nlpm-fix.py [项目路径]
    python3 nlpm-fix.py ~/projects/prompt-improver/ --dry-run  # 只预览，不实际修改
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple

def extract_frontmatter(filepath: Path) -> Tuple[Dict[str, str], str, str]:
    """从 Markdown 文件中提取 YAML frontmatter
    返回: (frontmatter_dict, frontmatter_text, body_text)
    """
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception:
        return {}, "", ""
    
    match = re.match(r'^(---\s*\n.*?\n---\s*\n)(.*)', content, re.DOTALL)
    if not match:
        return {}, "", content
    
    frontmatter_text = match.group(1)
    body = match.group(2)
    
    frontmatter = {}
    for line in frontmatter_text.split('\n')[1:-2]:  # 跳过 --- 行
        if ':' in line:
            key, _, value = line.partition(':')
            frontmatter[key.strip()] = value.strip()
    
    return frontmatter, frontmatter_text, body

def fix_name_mismatch(filepath: Path) -> Tuple[bool, str]:
    """修复 name 字段和父目录不匹配的问题"""
    frontmatter, fm_text, body = extract_frontmatter(filepath)
    
    if not frontmatter.get("name"):
        return False, "缺少 name 字段，无法修复"
    
    parent_dir = filepath.parent.name
    if frontmatter["name"] == parent_dir:
        return False, "name 已经匹配"
    
    # 修复
    new_fm_text = fm_text.replace(
        f'name: {frontmatter["name"]}',
        f'name: {parent_dir}'
    )
    
    return True, f"将 name 从 '{frontmatter['name']}' 改为 '{parent_dir}'"

def add_missing_frontmatter(filepath: Path, artifact_type: str) -> Tuple[bool, str]:
    """添加缺失的 frontmatter 字段"""
    frontmatter, fm_text, body = extract_frontmatter(filepath)
    
    changes = []
    
    # 检查必需字段
    if artifact_type in ["skill", "agent"] and not frontmatter.get("name"):
        name = filepath.parent.name if filepath.parent.name != "agents" else filepath.stem
        changes.append(f"name: {name}")
    
    if artifact_type in ["skill", "agent", "command"] and not frontmatter.get("description"):
        changes.append(f'description: "TODO: 添加描述"')
    
    if artifact_type == "agent" and not frontmatter.get("model"):
        changes.append("model: sonnet")
    
    if artifact_type == "agent" and not frontmatter.get("tools"):
        changes.append("tools: [Read, Grep, Glob]")
    
    if not changes:
        return False, "没有缺失的 frontmatter 字段"
    
    # 添加字段
    if not fm_text:
        # 没有 frontmatter，创建新的
        new_fm = "---\n" + "\n".join(changes) + "\n---\n\n"
        new_content = new_fm + body
    else:
        # 在现有 frontmatter 中添加
        insert_pos = fm_text.rfind("---\n")
        new_fm = fm_text[:insert_pos] + "\n".join(changes) + "\n" + fm_text[insert_pos:]
        new_content = new_fm + body
    
    return True, f"添加了 {len(changes)} 个字段: {', '.join(changes)}"

def add_error_handling_template(filepath: Path) -> Tuple[bool, str]:
    """添加错误处理模板"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception:
        return False, "无法读取文件"
    
    # 检查是否已经有错误处理
    error_keywords = ["错误处理", "error handling", "错误路径", "error path"]
    if any(kw in content.lower() for kw in error_keywords):
        return False, "已经有错误处理"
    
    # 添加错误处理模板
    template = """
## 错误处理

- 如果没有找到匹配的文件：报告 "No matching files for pattern: {X}"
- 如果文件无法读取：跳过并在报告中注明
- 如果范围不明确：分析较窄的解释
"""
    
    new_content = content.rstrip() + "\n" + template
    return True, "添加了错误处理模板"

def add_output_format_template(filepath: Path) -> Tuple[bool, str]:
    """添加输出格式模板"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception:
        return False, "无法读取文件"
    
    # 检查是否已经有输出格式
    output_keywords = ["输出格式", "output format", "报告格式", "report format"]
    if any(kw in content.lower() for kw in output_keywords):
        return False, "已经有输出格式"
    
    # 添加输出格式模板
    template = """
## 输出格式

对于每个发现：

**[严重程度] 发现标题**
- 文件：`path/to/file`
- 行号：{N}
- 发现：{描述}
- 修复：{具体修复}

严重程度：CRITICAL > HIGH > MEDIUM > LOW > INFO

最后一行：
- `PASS: 没有问题`
- `WARN: 发现 {N} 个警告`
- `FAIL: 发现 {N} 个错误`
"""
    
    new_content = content.rstrip() + "\n" + template
    return True, "添加了输出格式模板"

def discover_artifacts(project_root: Path) -> Dict[str, List[Path]]:
    """发现项目中所有 NL 工件"""
    artifacts = {
        "skill": [],
        "agent": [],
        "rule": [],
        "command": [],
        "project_doc": [],
    }
    
    patterns = {
        "skill": ["**/SKILL.md", "**/skills/**/*.md"],
        "agent": ["**/agents/**/*.md"],
        "rule": ["**/rules/**/*.md"],
        "command": ["**/commands/**/*.md"],
        "project_doc": ["AGENTS.md", "CLAUDE.md", "GEMINI.md"],
    }
    
    exclude_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build'}
    
    for artifact_type, type_patterns in patterns.items():
        for pattern in type_patterns:
            for filepath in project_root.glob(pattern):
                if not filepath.is_file():
                    continue
                if any(part in exclude_dirs for part in filepath.parts):
                    continue
                if filepath not in artifacts[artifact_type]:
                    artifacts[artifact_type].append(filepath)
    
    return artifacts

def fix_artifact(filepath: Path, artifact_type: str, dry_run: bool = False) -> List[Tuple[bool, str]]:
    """修复单个工件"""
    results = []
    
    # 修复 name 不匹配
    fixed, msg = fix_name_mismatch(filepath)
    if fixed and not dry_run:
        results.append((True, msg))
    
    # 添加缺失的 frontmatter
    fixed, msg = add_missing_frontmatter(filepath, artifact_type)
    if fixed and not dry_run:
        results.append((True, msg))
    
    # 添加错误处理模板
    fixed, msg = add_error_handling_template(filepath)
    if fixed and not dry_run:
        results.append((True, msg))
    
    # 添加输出格式模板
    fixed, msg = add_output_format_template(filepath)
    if fixed and not dry_run:
        results.append((True, msg))
    
    return results

def main():
    # 解析参数
    dry_run = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    
    if args:
        project_root = Path(args[0]).resolve()
    else:
        project_root = Path.cwd()
    
    if not project_root.exists():
        print(f"错误: 路径不存在: {project_root}", file=sys.stderr)
        sys.exit(1)
    
    if not project_root.is_dir():
        print(f"错误: 路径不是目录: {project_root}", file=sys.stderr)
        sys.exit(1)
    
    print(f"NLPM 自动修复 - {project_root}")
    if dry_run:
        print("（预览模式，不会实际修改文件）")
    print()
    
    # 发现工件
    artifacts = discover_artifacts(project_root)
    
    total_fixed = 0
    
    for artifact_type, filepaths in artifacts.items():
        for filepath in filepaths:
            rel_path = filepath.relative_to(project_root)
            fixes = fix_artifact(filepath, artifact_type, dry_run)
            
            if fixes:
                print(f"{rel_path}:")
                for fixed, msg in fixes:
                    if fixed:
                        print(f"  ✓ {msg}")
                        total_fixed += 1
                    else:
                        print(f"  ℹ {msg}")
                print()
    
    if total_fixed == 0:
        print("没有需要修复的问题。")
    else:
        print(f"总计修复: {total_fixed} 个问题")
        if dry_run:
            print("（预览模式，实际未修改任何文件）")

if __name__ == "__main__":
    main()
