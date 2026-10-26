#!/usr/bin/env python3
"""nlpm-score: 对项目中所有 NL 工件进行 100 分制质量评分

用法:
    python3 nlpm-score.py [项目路径]
    python3 nlpm-score.py ~/projects/prompt-improver/
    
默认扫描当前目录。
"""

import os
import sys
import re
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

# 中文模糊量化词列表
VAGUE_TERMS_CN = [
    "适当的", "相关的", "根据需要", "充分的", "足够的", "合理的",
    "正确地", "一些", "几个", "各种", "尽量", "适当", "相关",
    "合适", "尽可能", "某种程度上", "一般来说", "通常", "可能",
    "应该", "需要", "能够", "可以"
]

# 英文模糊量化词列表
VAGUE_TERMS_EN = [
    "appropriate", "relevant", "as needed", "sufficient", "adequate",
    "reasonable", "properly", "correctly", "some", "several", "various"
]

# 根目录下可能是智能体定义的文件关键词
POSSIBLE_AGENT_KEYWORDS = ["agent", "智能体", "assistant", "助手", "improver", "reviewer", "checker"]

def extract_frontmatter(filepath: Path) -> Dict[str, str]:
    """从 Markdown 文件中提取 YAML frontmatter"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception:
        return {}
    
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return {}
    
    frontmatter_text = match.group(1)
    frontmatter = {}
    
    # 解析 YAML frontmatter（支持多行字符串）
    current_key = None
    current_value = []
    in_multiline = False
    multiline_indicator = None  # '>' 或 '|'
    
    for line in frontmatter_text.split('\n'):
        # 检查是否是多行字符串的开始
        if in_multiline:
            # 如果缩进继续，说明还是多行字符串的一部分
            if line.startswith('  ') or line.startswith('\t'):
                current_value.append(line.strip())
                continue
            else:
                # 多行字符串结束
                frontmatter[current_key] = ' '.join(current_value)
                in_multiline = False
                current_key = None
                current_value = []
        
        # 检查是否是新的键值对
        if ':' in line and not in_multiline:
            key, _, value = line.partition(':')
            key = key.strip()
            value = value.strip()
            
            # 检查是否是多行字符串指示符
            if value in ['>', '|', '>-', '|-']:
                in_multiline = True
                multiline_indicator = value
                current_key = key
                current_value = []
            elif value:
                # 普通单行值
                frontmatter[key] = value
    
    # 处理最后一个多行字符串（如果文件结束时还在多行模式中）
    if in_multiline and current_key:
        frontmatter[current_key] = ' '.join(current_value)
    
    return frontmatter

def count_lines(filepath: Path) -> int:
    """统计文件行数"""
    try:
        return len(filepath.read_text(encoding='utf-8').splitlines())
    except Exception:
        return 0

def count_vague_terms(content: str) -> Tuple[int, List[str]]:
    """统计模糊量化词的数量和位置"""
    count = 0
    found_terms = []
    
    # 检查中文模糊词
    for term in VAGUE_TERMS_CN:
        matches = re.findall(rf'\b{term}\b', content)
        count += len(matches)
        if matches:
            found_terms.extend([term] * len(matches))
    
    # 检查英文模糊词（不区分大小写）
    for term in VAGUE_TERMS_EN:
        matches = re.findall(rf'\b{term}\b', content, re.IGNORECASE)
        count += len(matches)
        if matches:
            found_terms.extend([term] * len(matches))
    
    return count, found_terms

def check_skill(filepath: Path, frontmatter: Dict, lines: int, content: str) -> List[Dict]:
    """检查技能文件"""
    findings = []
    
    # 检查 name 字段
    if not frontmatter.get("name"):
        findings.append({"rule": "--", "check": "name 存在", "penalty": -25, "message": "缺少 name 字段"})
    else:
        # 检查 name 是否匹配父目录
        parent_dir = filepath.parent.name
        if frontmatter["name"] != parent_dir:
            findings.append({"rule": "--", "check": "name 匹配父目录", "penalty": -15, "message": f"name '{frontmatter['name']}' 不匹配父目录 '{parent_dir}'"})
    
    # 检查 description 字段
    if not frontmatter.get("description"):
        findings.append({"rule": "R04", "check": "description 存在", "penalty": -25, "message": "缺少 description 字段"})
    else:
        desc = frontmatter["description"]
        # 检查触发器质量（简单检查：是否有 3+ 个逗号分隔的短语）
        trigger_phrases = len([p for p in desc.split(',') if len(p.strip()) > 10])
        if trigger_phrases <= 1:
            findings.append({"rule": "R04", "check": "触发器质量", "penalty": -15, "message": f"描述太泛，只有 {trigger_phrases} 个触发短语（需要 3+）"})
        
        # 检查描述长度
        if len(desc) > 800:
            findings.append({"rule": "R04", "check": "描述长度", "penalty": -10, "message": f"描述过长：{len(desc)} 字符（>800）"})
        elif len(desc) > 500:
            findings.append({"rule": "R04", "check": "描述长度", "penalty": -5, "message": f"描述较长：{len(desc)} 字符（500-800）"})
    
    # 检查文件长度
    if lines > 500:
        findings.append({"rule": "R05", "check": "body 长度", "penalty": -10, "message": f"文件过长：{lines} 行（>500）"})
    elif lines > 400:
        findings.append({"rule": "R05", "check": "body 长度", "penalty": -5, "message": f"文件较长：{lines} 行（400-500）"})
    
    # 检查代码示例
    has_code_examples = bool(re.search(r'```[\w]+\n', content))
    if not has_code_examples and lines > 50:
        findings.append({"rule": "R06", "check": "代码示例", "penalty": -10, "message": "技术技能没有代码示例"})
    
    # 检查 <example> 块
    user_invocable = frontmatter.get("user-invocable", "true").lower() != "false"
    if user_invocable and "<example>" not in content.lower():
        findings.append({"rule": "R06", "check": "<example> 块", "penalty": -10, "message": "用户可调用技能缺少 <example> 块"})
    
    # 检查范围说明
    if "scope" not in content.lower() and "参见" not in content and "see" not in content.lower():
        findings.append({"rule": "R07", "check": "范围说明", "penalty": -3, "message": "没有范围说明或交叉引用"})
    
    return findings

def check_agent(filepath: Path, frontmatter: Dict, lines: int, content: str) -> List[Dict]:
    """检查智能体文件"""
    findings = []
    
    # 检查 description 字段
    if not frontmatter.get("description"):
        findings.append({"rule": "R09", "check": "description 存在", "penalty": -25, "message": "缺少 description 字段"})
    else:
        desc = frontmatter["description"]
        
        # 检查 <example> 块
        if "<example>" not in desc.lower():
            findings.append({"rule": "R09", "check": "<example> 块", "penalty": -15, "message": "描述中没有 <example> 块"})
        
        # 检查排除条款
        exclusion_keywords = ["不用于", "不要用于", "not for", "do not use"]
        has_exclusion = any(kw in desc.lower() for kw in exclusion_keywords)
        if not has_exclusion:
            findings.append({"rule": "R09", "check": "排除条款", "penalty": -5, "message": "描述没有说明智能体不适用于什么情况"})
        
        # 检查描述长度
        if len(desc) > 1200:
            findings.append({"rule": "R09", "check": "描述长度", "penalty": -5, "message": f"描述过长：{len(desc)} 字符（>1200）"})
    
    # 检查 model 字段
    if not frontmatter.get("model"):
        findings.append({"rule": "R10", "check": "model 声明", "penalty": -5, "message": "缺少 model 字段"})
    
    # 检查 tools 字段
    if not frontmatter.get("tools"):
        findings.append({"rule": "R11", "check": "tools 声明", "penalty": -5, "message": "缺少 tools 字段"})
    
    # 检查输出格式
    output_keywords = ["输出格式", "output format", "报告格式", "report format"]
    has_output_format = any(kw in content.lower() for kw in output_keywords)
    if not has_output_format:
        findings.append({"rule": "R12", "check": "输出格式", "penalty": -10, "message": "body 中没有定义输出格式"})
    
    return findings

def check_rule(filepath: Path, frontmatter: Dict, lines: int, content: str) -> List[Dict]:
    """检查规则文件"""
    findings = []
    
    # 检查 description 字段
    if not frontmatter.get("description"):
        findings.append({"rule": "R21", "check": "description 存在", "penalty": -10, "message": "缺少 frontmatter description"})
    
    # 检查粗体祈使句
    if not re.search(r'\*\*[^*]+\*\*', content):
        findings.append({"rule": "R21", "check": "格式：粗体祈使句", "penalty": -5, "message": "没有粗体祈使句开头"})
    
    # 检查文件长度
    if lines > 500:
        findings.append({"rule": "R23", "check": "预算", "penalty": -15, "message": f"规则文件过长：{lines} 行（>500）"})
    
    return findings

def check_command(filepath: Path, frontmatter: Dict, lines: int, content: str) -> List[Dict]:
    """检查命令文件"""
    findings = []
    
    # 检查 description 字段
    if not frontmatter.get("description"):
        findings.append({"rule": "--", "check": "description 存在", "penalty": -25, "message": "缺少 description 字段"})
    
    # 检查步骤编号
    if lines > 20 and not re.search(r'^\d+\.', content, re.MULTILINE):
        findings.append({"rule": "R14", "check": "步骤编号", "penalty": -10, "message": "多步骤 body 没有编号步骤"})
    
    # 检查输出格式
    output_keywords = ["输出格式", "output format", "报告格式", "report format"]
    has_output_format = any(kw in content.lower() for kw in output_keywords)
    if not has_output_format:
        findings.append({"rule": "R16", "check": "输出格式", "penalty": -10, "message": "没有定义输出格式"})
    
    return findings

def check_project_doc(filepath: Path, frontmatter: Dict, lines: int, content: str) -> List[Dict]:
    """检查项目文档"""
    findings = []
    
    # 检查文件长度
    if lines > 200:
        findings.append({"rule": "--", "check": "控制在 200 行以内", "penalty": -5, "message": f"文件过长：{lines} 行（>200）"})
    
    # 检查构建/运行命令
    build_keywords = ["构建", "运行", "build", "run", "安装", "install"]
    has_build_cmd = any(kw in content.lower() for kw in build_keywords)
    if not has_build_cmd:
        findings.append({"rule": "R33", "check": "构建/运行命令", "penalty": -10, "message": "没有说明如何构建或运行项目"})
    
    # 检查测试命令
    test_keywords = ["测试", "test", "验证", "verify"]
    has_test_cmd = any(kw in content.lower() for kw in test_keywords)
    if not has_test_cmd:
        findings.append({"rule": "R34", "check": "测试命令", "penalty": -5, "message": "没有说明如何运行测试"})
    
    # 检查架构概述
    arch_keywords = ["架构", "结构", "architecture", "structure", "组件", "component"]
    has_arch = any(kw in content.lower() for kw in arch_keywords)
    if not has_arch:
        findings.append({"rule": "R35", "check": "架构概述", "penalty": -5, "message": "没有结构/组件描述"})
    
    return findings

def score_artifact(filepath: Path, artifact_type: str) -> Tuple[int, List[Dict]]:
    """对单个工件评分"""
    frontmatter = extract_frontmatter(filepath)
    lines = count_lines(filepath)
    
    try:
        content = filepath.read_text(encoding='utf-8').lower()
    except Exception:
        content = ""
    
    # 根据类型检查
    if artifact_type == "skill":
        findings = check_skill(filepath, frontmatter, lines, content)
    elif artifact_type == "agent":
        findings = check_agent(filepath, frontmatter, lines, content)
    elif artifact_type == "rule":
        findings = check_rule(filepath, frontmatter, lines, content)
    elif artifact_type == "command":
        findings = check_command(filepath, frontmatter, lines, content)
    elif artifact_type == "project_doc":
        findings = check_project_doc(filepath, frontmatter, lines, content)
    else:
        findings = []
    
    # 检查模糊量化词（所有类型，但规则文件除外）
    # 规则文件中引用模糊量化词是为了说明"不要使用这些词"，不是真正的使用
    if artifact_type != "rule":
        vague_count, vague_terms = count_vague_terms(content)
        if vague_count > 0:
            penalty = min(-2 * vague_count, -20)
            findings.append({
                "rule": "R01",
                "check": "模糊量化词",
                "penalty": penalty,
                "message": f"发现 {vague_count} 个模糊量化词: {', '.join(set(vague_terms[:5]))}"
            })
    
    # 计算总分
    total_penalty = sum(f["penalty"] for f in findings)
    score = max(0, min(100, 100 + total_penalty))
    
    return score, findings

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
        "agent": ["**/agents/**/*.md", "**/AGENTS.md"],
        "rule": ["**/rules/**/*.md"],
        "command": ["**/commands/**/*.md"],
        "project_doc": ["AGENTS.md", "CLAUDE.md", "GEMINI.md", "README.md", "PROJECT_STATUS.md"],
    }

    exclude_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', '.nlpm', 'tests'}

    for artifact_type, type_patterns in patterns.items():
        for pattern in type_patterns:
            for filepath in project_root.glob(pattern):
                if not filepath.is_file():
                    continue
                if any(part in exclude_dirs for part in filepath.parts):
                    continue
                if filepath not in artifacts[artifact_type]:
                    artifacts[artifact_type].append(filepath)

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
        
        if is_likely_agent and filepath not in artifacts["agent"]:
            artifacts["agent"].append(filepath)

    return artifacts

def format_report(results: Dict[str, List[Tuple[Path, int, List[Dict]]]], project_root: Path) -> str:
    """格式化评分报告"""
    lines = []
    lines.append(f"NLPM 质量评分 - {project_root}\n")
    
    total_score = 0
    total_count = 0
    
    type_names = {
        "skill": "技能",
        "agent": "智能体",
        "rule": "规则",
        "command": "命令",
        "project_doc": "项目文档",
    }
    
    for artifact_type, items in results.items():
        if not items:
            continue
        
        for filepath, score, findings in sorted(items, key=lambda x: x[0].name):
            rel_path = filepath.relative_to(project_root)
            
            # 确定等级
            if score >= 90:
                grade = "优秀"
            elif score >= 80:
                grade = "良好"
            elif score >= 70:
                grade = "及格"
            elif score >= 60:
                grade = "弱"
            else:
                grade = "需要重写"
            
            lines.append(f"{rel_path}: {score}/100 ({grade})")
            
            for finding in findings:
                lines.append(f"  ✗ {finding['rule']}: {finding['message']} ({finding['penalty']})")
            
            if not findings:
                lines.append("  ✓ 没有问题")
            
            lines.append("")
            
            total_score += score
            total_count += 1
    
    if total_count > 0:
        avg_score = total_score / total_count
        lines.append(f"平均分: {avg_score:.1f}/100")
    else:
        lines.append("没有发现 NL 工件。")
    
    return "\n".join(lines)

def save_history(project_root: Path, results: Dict[str, List[Tuple[Path, int, List[Dict]]]]):
    """保存评分历史"""
    history_dir = Path.home() / ".qwen" / "nlpm-qwen" / "data"
    history_dir.mkdir(parents=True, exist_ok=True)
    
    history_file = history_dir / "history.json"
    
    # 加载现有历史
    if history_file.exists():
        try:
            history = json.loads(history_file.read_text(encoding='utf-8'))
        except Exception:
            history = []
    else:
        history = []
    
    # 添加新记录
    record = {
        "timestamp": datetime.now().isoformat(),
        "project": str(project_root),
        "scores": {}
    }
    
    for artifact_type, items in results.items():
        for filepath, score, findings in items:
            rel_path = str(filepath.relative_to(project_root))
            record["scores"][rel_path] = score
    
    history.append(record)
    
    # 保存历史
    history_file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding='utf-8')

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
    
    # 评分
    results = {}
    for artifact_type, filepaths in artifacts.items():
        results[artifact_type] = []
        for filepath in filepaths:
            score, findings = score_artifact(filepath, artifact_type)
            results[artifact_type].append((filepath, score, findings))
    
    # 输出报告
    report = format_report(results, project_root)
    print(report)
    
    # 保存历史
    save_history(project_root, results)

if __name__ == "__main__":
    main()
