#!/usr/bin/env python3
"""nlpm-security: 扫描 NL 工件中的安全风险

检查：
- 危险命令（curl | bash、eval $var 等）
- 敏感信息泄露（API 密钥、密码等）
- 不安全的依赖
- 提示注入风险

用法:
    python3 nlpm-security.py [项目路径]
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple

# 危险命令模式
DANGEROUS_PATTERNS = {
    "critical": [
        (r'curl.*\|.*sh', "管道到 shell 执行（远程代码执行风险）"),
        (r'curl.*\|.*bash', "管道到 bash 执行（远程代码执行风险）"),
        (r'wget.*\|.*sh', "wget 管道到 shell（远程代码执行风险）"),
        (r'wget.*\|.*bash', "wget 管道到 bash（远程代码执行风险）"),
        (r'eval\s+["\']?\$', "eval 与变量（任意代码执行）"),
        (r'bash\s+-i\s+>&', "反向 shell"),
        (r'/dev/tcp/', "反向 shell"),
        (r'base64.*\|.*sh', "base64 解码并执行"),
        (r'base64.*\|.*bash', "base64 解码并执行"),
        (r'base64.*\|.*python', "base64 解码并执行"),
    ],
    "high": [
        (r'subprocess\.(call|run|Popen).*shell\s*=\s*True', "subprocess 与 shell=True（未过滤输入到达 shell）"),
        (r'os\.system\(', "os.system 调用（无参数转义）"),
        (r'require\(\s*\$', "动态 require（攻击者控制的模块路径）"),
        (r'import\(\s*\$', "动态 import（攻击者控制的模块路径）"),
        (r'new\s+Function\(', "new Function 与动态字符串（任意代码执行）"),
        (r'>\s*~/', "写入主目录（系统修改）"),
        (r'>\s*/etc/', "写入 /etc（系统修改）"),
        (r'sudo\s+', "sudo 使用（权限提升）"),
    ],
    "medium": [
        (r'curl\s+', "网络调用（可能泄露数据）"),
        (r'wget\s+', "网络调用（可能泄露数据）"),
        (r'process\.env', "环境变量访问（可能泄露密钥）"),
        (r'os\.environ', "环境变量访问（可能泄露密钥）"),
        # pip/npm install 需要特殊处理：如果锁定了版本就不报告
        # 这些模式会在 scan_file_for_patterns 中特殊处理
    ]
}

# 需要特殊处理的模式（如果锁定了版本就不报告）
CONDITIONAL_PATTERNS = [
    (r'npm\s+install(?!.*==)', "运行时包安装（未锁定版本）"),
    (r'pip\s+install(?!.*==)', "运行时包安装（未锁定版本）"),
]

# 敏感信息模式
SENSITIVE_PATTERNS = [
    (r'AKIA[0-9A-Z]{16}', "AWS 访问密钥"),
    (r'ghp_[a-zA-Z0-9]{36}', "GitHub 个人访问令牌"),
    (r'gho_[a-zA-Z0-9]{36}', "GitHub OAuth 令牌"),
    (r'sk-[a-zA-Z0-9]{20,}', "OpenAI API 密钥"),
    (r'sk-ant-[a-zA-Z0-9]{20,}', "Anthropic API 密钥"),
    (r'-----BEGIN\s+(RSA|DSA|EC|OPENSSH|PGP)\s+PRIVATE\s+KEY-----', "私钥"),
    (r'AIza[0-9A-Za-z_-]{35}', "Google API 密钥"),
    (r'[0-9a-f]{32}-us[0-9]{1,2}', "Mailchimp API 密钥"),
    (r'SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}', "SendGrid API 密钥"),
]

def scan_file_for_patterns(filepath: Path) -> List[Dict]:
    """扫描文件中的危险模式"""
    findings = []

    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception:
        return findings

    lines = content.splitlines()

    # 检查危险命令
    for severity, patterns in DANGEROUS_PATTERNS.items():
        for pattern, description in patterns:
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append({
                        "severity": severity,
                        "path": str(filepath),
                        "line": i,
                        "pattern": pattern,
                        "message": description,
                        "content": line.strip()[:100]
                    })

    # 检查条件性模式（如 pip/npm install，如果锁定了版本就不报告）
    for pattern, description in CONDITIONAL_PATTERNS:
        for i, line in enumerate(lines, 1):
            if re.search(pattern, line, re.IGNORECASE):
                findings.append({
                    "severity": "medium",
                    "path": str(filepath),
                    "line": i,
                    "pattern": pattern,
                    "message": description,
                    "content": line.strip()[:100]
                })

    # 检查敏感信息
    for pattern, description in SENSITIVE_PATTERNS:
        for i, line in enumerate(lines, 1):
            if re.search(pattern, line):
                findings.append({
                    "severity": "critical",
                    "path": str(filepath),
                    "line": i,
                    "pattern": pattern,
                    "message": f"敏感信息泄露: {description}",
                    "content": "[已隐藏]"
                })

    return findings

def scan_file_for_injection(filepath: Path) -> List[Dict]:
    """扫描提示注入风险"""
    findings = []
    
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception:
        return findings
    
    # 检查是否读取用户文件后传递给 Bash
    if re.search(r'read.*user.*file', content, re.IGNORECASE):
        if re.search(r'bash|shell|exec', content, re.IGNORECASE):
            findings.append({
                "severity": "high",
                "path": str(filepath),
                "line": 0,
                "pattern": "user-file-to-bash",
                "message": "可能将用户文件内容传递给 Bash（提示注入风险）",
                "content": ""
            })
    
    # 检查是否缺少注入抵抗声明
    injection_keywords = ["视为数据", "treat.*as.*data", "不是指令", "not.*instructions"]
    has_resistance = any(re.search(kw, content, re.IGNORECASE) for kw in injection_keywords)
    
    if not has_resistance and re.search(r'user.*input|用户.*输入', content, re.IGNORECASE):
        findings.append({
            "severity": "medium",
            "path": str(filepath),
            "line": 0,
            "pattern": "no-injection-resistance",
            "message": "处理用户输入但没有注入抵抗声明",
            "content": ""
        })
    
    return findings

def discover_scannable_files(project_root: Path) -> List[Path]:
    """发现需要扫描的文件"""
    files = []
    
    # 扫描所有 Markdown 文件
    for pattern in ["**/*.md", "**/*.sh", "**/*.py", "**/*.js"]:
        for filepath in project_root.glob(pattern):
            if not filepath.is_file():
                continue
            
            # 排除目录
            exclude_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build'}
            if any(part in exclude_dirs for part in filepath.parts):
                continue
            
            # 排除 nlpm 自身
            if '.qwen/nlpm-qwen' in str(filepath):
                continue
            
            files.append(filepath)
    
    return files

def format_report(findings: List[Dict], project_root: Path) -> str:
    """格式化安全扫描报告"""
    lines = []
    lines.append(f"NLPM 安全扫描 - {project_root}\n")
    
    if not findings:
        lines.append("✓ 没有发现安全问题")
        return "\n".join(lines)
    
    # 按严重程度分组
    critical = [f for f in findings if f["severity"] == "critical"]
    high = [f for f in findings if f["severity"] == "high"]
    medium = [f for f in findings if f["severity"] == "medium"]
    
    lines.append(f"发现 {len(findings)} 个安全问题:\n")
    
    if critical:
        lines.append(f"严重 ({len(critical)}):")
        for f in critical:
            rel_path = Path(f["path"]).relative_to(project_root)
            line_info = f" 第 {f['line']} 行" if f["line"] > 0 else ""
            lines.append(f"  ✗ {rel_path}{line_info}: {f['message']}")
            if f["content"]:
                lines.append(f"    内容: {f['content']}")
        lines.append("")
    
    if high:
        lines.append(f"高 ({len(high)}):")
        for f in high:
            rel_path = Path(f["path"]).relative_to(project_root)
            line_info = f" 第 {f['line']} 行" if f["line"] > 0 else ""
            lines.append(f"  ⚠ {rel_path}{line_info}: {f['message']}")
        lines.append("")
    
    if medium:
        lines.append(f"中 ({len(medium)}):")
        for f in medium:
            rel_path = Path(f["path"]).relative_to(project_root)
            line_info = f" 第 {f['line']} 行" if f["line"] > 0 else ""
            lines.append(f"  ℹ {rel_path}{line_info}: {f['message']}")
        lines.append("")
    
    lines.append("建议:")
    lines.append("  - 严重问题必须立即修复")
    lines.append("  - 高严重度问题应尽快修复")
    lines.append("  - 中严重度问题应在下次更新时修复")
    
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
    
    # 发现文件
    files = discover_scannable_files(project_root)
    
    # 扫描
    all_findings = []
    for filepath in files:
        all_findings.extend(scan_file_for_patterns(filepath))
        all_findings.extend(scan_file_for_injection(filepath))
    
    # 输出报告
    report = format_report(all_findings, project_root)
    print(report)
    
    # 退出码：有严重问题时返回 1
    critical_count = sum(1 for f in all_findings if f["severity"] == "critical")
    sys.exit(1 if critical_count > 0 else 0)

if __name__ == "__main__":
    main()
