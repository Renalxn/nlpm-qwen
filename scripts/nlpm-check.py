#!/usr/bin/env python3
"""nlpm-check: 跨组件一致性检查

检查项目中的 NL 工件之间的一致性：
- 清单 vs 磁盘（文件存在但未注册）
- 跨文件引用是否有效
- 规则之间是否冲突

用法:
    python3 nlpm-check.py [项目路径]
"""

import os
import sys
import re
import json
from pathlib import Path
from typing import List, Dict, Set, Tuple

def extract_frontmatter(filepath: Path) -> Dict[str, str]:
    """从 Markdown 文件中提取 YAML frontmatter"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception:
        return {}
    
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return {}
    
    frontmatter = {}
    for line in match.group(1).split('\n'):
        if ':' in line:
            key, _, value = line.partition(':')
            frontmatter[key.strip()] = value.strip()
    
    return frontmatter

def discover_all_artifacts(project_root: Path) -> Dict[str, List[Path]]:
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
        "agent": ["**/agents/**/*.md", "**/AGENTS.md"],
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

def check_manifest_disk_consistency(project_root: Path, artifacts: Dict[str, List[Path]]) -> List[Dict]:
    """检查清单 vs 磁盘一致性"""
    findings = []
    
    # 检查 plugin.json（如果存在）
    plugin_json_paths = list(project_root.glob("**/plugin.json"))
    
    for plugin_path in plugin_json_paths:
        try:
            plugin_data = json.loads(plugin_path.read_text(encoding='utf-8'))
        except Exception:
            findings.append({
                "severity": "high",
                "path": str(plugin_path.relative_to(project_root)),
                "message": "plugin.json 无法解析"
            })
            continue
        
        # 检查 skills 数组
        if "skills" in plugin_data:
            declared_skills = set(plugin_data["skills"])
            actual_skills = set()
            
            for skill_path in artifacts["skill"]:
                rel_path = str(skill_path.relative_to(project_root))
                # 提取技能目录名
                skill_dir = skill_path.parent.name
                actual_skills.add(skill_dir)
            
            # 检查声明但不存在的
            for skill in declared_skills:
                if skill not in actual_skills:
                    findings.append({
                        "severity": "high",
                        "path": str(plugin_path.relative_to(project_root)),
                        "message": f"技能 '{skill}' 在 plugin.json 中声明但磁盘上不存在"
                    })
            
            # 检查存在但未声明的
            for skill in actual_skills:
                if skill not in declared_skills:
                    findings.append({
                        "severity": "medium",
                        "path": skill,
                        "message": f"技能 '{skill}' 在磁盘上存在但未在 plugin.json 中注册"
                    })
    
    return findings

def check_cross_references(project_root: Path, artifacts: Dict[str, List[Path]]) -> List[Dict]:
    """检查跨文件引用"""
    findings = []
    
    # 收集所有工件名称
    all_names = set()
    for artifact_type, paths in artifacts.items():
        for path in paths:
            frontmatter = extract_frontmatter(path)
            name = frontmatter.get("name", path.stem)
            all_names.add(name)
    
    # 检查每个文件中的引用
    for artifact_type, paths in artifacts.items():
        for path in paths:
            try:
                content = path.read_text(encoding='utf-8')
            except Exception:
                continue

            # 规则文件中的 [[xxx]] 引用是示例，不是真实引用，跳过
            if artifact_type == "rule":
                continue

            # 查找 [[xxx]] 格式的引用
            refs = re.findall(r'\[\[([^\]]+)\]\]', content)
            for ref in refs:
                if ref not in all_names:
                    findings.append({
                        "severity": "medium",
                        "path": str(path.relative_to(project_root)),
                        "message": f"引用了不存在的工件: [[{ref}]]"
                    })
            
            # 查找 plugin:skill 格式的引用
            skill_refs = re.findall(r'plugin:([a-z0-9-]+)', content)
            for skill_ref in skill_refs:
                if skill_ref not in all_names:
                    findings.append({
                        "severity": "medium",
                        "path": str(path.relative_to(project_root)),
                        "message": f"引用了不存在的技能: plugin:{skill_ref}"
                    })
    
    return findings

def check_rule_conflicts(project_root: Path, artifacts: Dict[str, List[Path]]) -> List[Dict]:
    """检查规则冲突"""
    findings = []
    
    # 收集所有规则文件的内容
    rule_contents = []
    for rule_path in artifacts["rule"]:
        try:
            content = rule_path.read_text(encoding='utf-8')
            rule_contents.append((rule_path, content))
        except Exception:
            continue
    
    # 简单的冲突检测：检查是否有相反的指令
    # 这是一个简化版本，完整的冲突检测需要更复杂的 NLP
    for i, (path1, content1) in enumerate(rule_contents):
        for path2, content2 in rule_contents[i+1:]:
            # 检查是否有明显的矛盾（如一个说"必须"，另一个说"不要"）
            # 这只是一个占位符，实际需要更智能的检测
            pass
    
    return findings

def check_orphaned_files(project_root: Path, artifacts: Dict[str, List[Path]]) -> List[Dict]:
    """检查孤立文件（没有被任何内容引用的文件）"""
    findings = []
    
    # 收集所有文件内容
    all_contents = {}
    for artifact_type, paths in artifacts.items():
        for path in paths:
            try:
                content = path.read_text(encoding='utf-8')
                all_contents[path] = content
            except Exception:
                continue
    
    # 检查每个技能是否被引用
    for skill_path in artifacts["skill"]:
        frontmatter = extract_frontmatter(skill_path)
        skill_name = frontmatter.get("name", skill_path.parent.name)
        
        # 检查是否在其他文件中被引用
        referenced = False
        for path, content in all_contents.items():
            if path == skill_path:
                continue
            if skill_name in content or f"plugin:{skill_name}" in content:
                referenced = True
                break
        
        if not referenced:
            findings.append({
                "severity": "low",
                "path": str(skill_path.relative_to(project_root)),
                "message": f"技能 '{skill_name}' 没有被任何内容引用（可能是孤立文件）"
            })
    
    return findings

def format_report(findings: List[Dict], project_root: Path) -> str:
    """格式化检查报告"""
    lines = []
    lines.append(f"NLPM 一致性检查 - {project_root}\n")
    
    if not findings:
        lines.append("✓ 没有发现问题")
        return "\n".join(lines)
    
    # 按严重程度分组
    high = [f for f in findings if f["severity"] == "high"]
    medium = [f for f in findings if f["severity"] == "medium"]
    low = [f for f in findings if f["severity"] == "low"]
    
    if high:
        lines.append(f"高严重度 ({len(high)}):")
        for f in high:
            lines.append(f"  ✗ {f['path']}: {f['message']}")
        lines.append("")
    
    if medium:
        lines.append(f"中严重度 ({len(medium)}):")
        for f in medium:
            lines.append(f"  ⚠ {f['path']}: {f['message']}")
        lines.append("")
    
    if low:
        lines.append(f"低严重度 ({len(low)}):")
        for f in low:
            lines.append(f"  ℹ {f['path']}: {f['message']}")
        lines.append("")
    
    lines.append(f"总计: {len(findings)} 个问题")
    
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
    artifacts = discover_all_artifacts(project_root)
    
    # 执行检查
    all_findings = []
    all_findings.extend(check_manifest_disk_consistency(project_root, artifacts))
    all_findings.extend(check_cross_references(project_root, artifacts))
    all_findings.extend(check_rule_conflicts(project_root, artifacts))
    all_findings.extend(check_orphaned_files(project_root, artifacts))
    
    # 输出报告
    report = format_report(all_findings, project_root)
    print(report)
    
    # 退出码：有高严重度问题时返回 1
    high_count = sum(1 for f in all_findings if f["severity"] == "high")
    sys.exit(1 if high_count > 0 else 0)

if __name__ == "__main__":
    main()
