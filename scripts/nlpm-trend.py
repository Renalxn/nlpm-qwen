#!/usr/bin/env python3
"""nlpm-trend: 跟踪质量评分趋势

读取评分历史数据，生成趋势报告。

用法:
    python3 nlpm-trend.py [项目路径]
    python3 nlpm-trend.py ~/projects/prompt-improver/
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict

def load_history() -> List[Dict]:
    """加载评分历史"""
    history_file = Path.home() / ".qwen" / "nlpm-qwen" / "data" / "history.json"
    
    if not history_file.exists():
        return []
    
    try:
        return json.loads(history_file.read_text(encoding='utf-8'))
    except Exception:
        return []

def filter_by_project(history: List[Dict], project_root: Path) -> List[Dict]:
    """按项目过滤历史记录"""
    project_str = str(project_root)
    return [r for r in history if r.get("project") == project_str]

def format_trend_report(records: List[Dict], project_root: Path) -> str:
    """格式化趋势报告"""
    lines = []
    lines.append(f"NLPM 质量趋势 - {project_root}\n")
    
    if not records:
        lines.append("没有评分历史记录。")
        lines.append("请先运行 nlpm-score.py 生成基线评分。")
        return "\n".join(lines)
    
    # 计算每次的平均分
    averages = []
    for record in records:
        scores = list(record.get("scores", {}).values())
        if scores:
            avg = sum(scores) / len(scores)
            averages.append({
                "timestamp": record["timestamp"],
                "average": avg,
                "count": len(scores),
                "scores": record["scores"]
            })
    
    if not averages:
        lines.append("没有有效的评分数据。")
        return "\n".join(lines)
    
    # 显示趋势
    lines.append("评分历史:\n")
    
    prev_avg = None
    for i, entry in enumerate(averages):
        timestamp = entry["timestamp"][:19]  # 截取到秒
        avg = entry["average"]
        count = entry["count"]
        
        # 计算变化
        if prev_avg is not None:
            change = avg - prev_avg
            if change > 0:
                trend = f"↑ +{change:.1f}"
            elif change < 0:
                trend = f"↓ {change:.1f}"
            else:
                trend = "→ 持平"
        else:
            trend = "(初始)"
        
        lines.append(f"{timestamp}: {avg:.0f}/100 ({count} 个工件) {trend}")
        prev_avg = avg
    
    # 计算总体趋势
    if len(averages) >= 2:
        first_avg = averages[0]["average"]
        last_avg = averages[-1]["average"]
        total_change = last_avg - first_avg
        
        lines.append("")
        if total_change > 0:
            lines.append(f"趋势: ↑ 持续改进 (+{total_change:.1f} 分, {total_change/first_avg*100:.1f}% 提升)")
        elif total_change < 0:
            lines.append(f"趋势: ↓ 质量下降 ({total_change:.1f} 分, {abs(total_change)/first_avg*100:.1f}% 下降)")
        else:
            lines.append("趋势: → 保持稳定")
    
    # 显示最近一次评分的详细信息
    if averages:
        latest = averages[-1]
        lines.append(f"\n最近一次评分 ({latest['timestamp'][:10]}):")
        
        # 按分数排序
        sorted_scores = sorted(latest["scores"].items(), key=lambda x: x[1])
        
        # 显示最低分的 5 个
        if len(sorted_scores) > 5:
            lines.append("  最低分的 5 个工件:")
            for path, score in sorted_scores[:5]:
                lines.append(f"    - {path}: {score:.0f}/100")
        
        # 显示最高分的 3 个
        if len(sorted_scores) > 3:
            lines.append("  最高分的 3 个工件:")
            for path, score in sorted_scores[-3:]:
                lines.append(f"    - {path}: {score:.0f}/100")
    
    return "\n".join(lines)

def main():
    # 解析参数
    if len(sys.argv) > 1:
        project_root = Path(sys.argv[1]).resolve()
    else:
        project_root = Path.cwd()
    
    # 加载历史
    history = load_history()
    
    # 按项目过滤
    records = filter_by_project(history, project_root)
    
    # 输出报告
    report = format_trend_report(records, project_root)
    print(report)

if __name__ == "__main__":
    main()
