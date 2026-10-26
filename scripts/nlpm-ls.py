#!/usr/bin/env python3
"""nlpm-ls: 发现并列出项目中所有 NL 工件

用法:
    python3 nlpm-ls.py [项目路径]
    
默认扫描当前目录。
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple

# NL 工件的类型和对应路径模式
ARTIFACT_PATTERNS = {
    "skill": [
        "**/SKILL.md",
        "**/skills/**/*.md",
    ],
    "agent": [
        "**/agents/**/*.md",
        "**/AGENTS.md",
    ],
    "rule": [
        "**/rules/**/*.md",
    ],
    "command": [
        "**/commands/**/*.md",
    ],
    "project_doc": [
        "AGENTS.md",
        "CLAUDE.md",
        "GEMINI.md",
        "README.md",
        "PROJECT_STATUS.md",
    ],
}

# 根目录下可能是智能体定义的文件（包含特定关键词）
POSSIBLE_AGENT_KEYWORDS = ["agent", "智能体", "assistant", "助手", "improver", "reviewer", "checker"]

def extract_frontmatter(filepath: Path) -> Dict[str, str]:
    """从 Markdown 文件中提取 YAML frontmatter"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception:
        return {}
    
    # 匹配 --- 包围的 frontmatter
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return {}
    
    frontmatter = {}
    for line in match.group(1).split('\n'):
        if ':' in line:
            key, _, value = line.partition(':')
            frontmatter[key.strip()] = value.strip()
    
    return frontmatter

def count_lines(filepath: Path) -> int:
    """统计文件行数"""
    try:
        return len(filepath.read_text(encoding='utf-8').splitlines())
    except Exception:
        return 0

def discover_artifacts(project_root: Path) -> Dict[str, List[Dict]]:
    """发现项目中所有 NL 工件"""
    artifacts = {
        "skill": [],
        "agent": [],
        "rule": [],
        "command": [],
        "project_doc": [],
    }
    
    # 排除的目录
    exclude_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', '.nlpm', 'tests'}
    
    for artifact_type, patterns in ARTIFACT_PATTERNS.items():
        for pattern in patterns:
            for filepath in project_root.glob(pattern):
                if not filepath.is_file():
                    continue
                
                # 检查是否在排除目录中
                if any(part in exclude_dirs for part in filepath.parts):
                    continue
                
                # 提取信息
                frontmatter = extract_frontmatter(filepath)
                lines = count_lines(filepath)
                rel_path = filepath.relative_to(project_root)
                
                artifacts[artifact_type].append({
                    "path": str(rel_path),
                    "name": frontmatter.get("name", filepath.stem),
                    "description": frontmatter.get("description", ""),
                    "lines": lines,
                    "has_frontmatter": bool(frontmatter),
                })
    
    # 特殊处理：检查根目录下的独立 .md 文件是否可能是智能体定义
    for filepath in project_root.glob("*.md"):
        if not filepath.is_file():
            continue
        
        # 排除已知的项目文档
        if filepath.name in ["README.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md", "PROJECT_STATUS.md", "CHANGELOG.md"]:
            continue
        
        # 检查文件名或内容是否包含智能体关键词
        filename_lower = filepath.stem.lower()
        is_likely_agent = any(kw in filename_lower for kw in POSSIBLE_AGENT_KEYWORDS)
        
        if not is_likely_agent:
            try:
                content = filepath.read_text(encoding='utf-8').lower()
                is_likely_agent = any(kw in content for kw in POSSIBLE_AGENT_KEYWORDS)
            except Exception:
                pass
        
        if is_likely_agent:
            frontmatter = extract_frontmatter(filepath)
            lines = count_lines(filepath)
            rel_path = filepath.relative_to(project_root)
            
            # 检查是否已经添加过
            if not any(a["path"] == str(rel_path) for a in artifacts["agent"]):
                artifacts["agent"].append({
                    "path": str(rel_path),
                    "name": frontmatter.get("name", filepath.stem),
                    "description": frontmatter.get("description", ""),
                    "lines": lines,
                    "has_frontmatter": bool(frontmatter),
                })
    
    # 去重（某些文件可能匹配多个模式）
    for artifact_type in artifacts:
        seen = set()
        unique = []
        for artifact in artifacts[artifact_type]:
            if artifact["path"] not in seen:
                seen.add(artifact["path"])
                unique.append(artifact)
        artifacts[artifact_type] = unique
    
    return artifacts

def format_report(artifacts: Dict[str, List[Dict]], project_root: Path) -> str:
    """格式化输出报告"""
    lines = []
    lines.append(f"NLPM 工件清单 - {project_root}\n")
    
    total_count = 0
    total_lines = 0
    
    type_names = {
        "skill": "技能 (Skills)",
        "agent": "智能体 (Agents)",
        "rule": "规则 (Rules)",
        "command": "命令 (Commands)",
        "project_doc": "项目文档 (Project Docs)",
    }
    
    for artifact_type, items in artifacts.items():
        if not items:
            continue
        
        lines.append(f"{type_names[artifact_type]} ({len(items)}):")
        
        for item in sorted(items, key=lambda x: x["path"]):
            name = item["name"]
            path = item["path"]
            lines_count = item["lines"]
            
            # 标记缺少 frontmatter 的文件
            warning = "" if item["has_frontmatter"] else " ⚠️ 缺少 frontmatter"
            
            lines.append(f"  - {path} ({lines_count} 行){warning}")
            
            total_count += 1
            total_lines += lines_count
        
        lines.append("")
    
    if total_count == 0:
        lines.append("没有发现 NL 工件。")
    else:
        lines.append(f"总计: {total_count} 个工件, {total_lines} 行")
    
    return "\n".join(lines)

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
    
    # 发现工件
    artifacts = discover_artifacts(project_root)
    
    # 输出报告
    report = format_report(artifacts, project_root)
    print(report)

if __name__ == "__main__":
    main()
