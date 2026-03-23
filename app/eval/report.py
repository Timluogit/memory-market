"""评估报告 - Evaluation Report Generation

支持:
- 报告生成 (Markdown / JSON / HTML)
- 可视化 (ASCII 图表)
- 对比分析
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.eval.runner import EvaluationResult


class EvaluationReport:
    """评估报告生成器"""

    @staticmethod
    def to_markdown(result: EvaluationResult) -> str:
        """生成 Markdown 格式报告"""
        lines = []
        lines.append(f"# 评估报告: {result.run_name}")
        lines.append("")
        lines.append(f"- **评估ID:** `{result.id}`")
        lines.append(f"- **数据集:** {result.dataset_name} (`{result.dataset_id}`)")
        lines.append(f"- **状态:** {result.status}")
        lines.append(f"- **开始时间:** {result.started_at or 'N/A'}")
        lines.append(f"- **完成时间:** {result.completed_at or 'N/A'}")
        lines.append(f"- **耗时:** {result.duration_seconds:.2f}s")
        lines.append(f"- **测试用例:** {result.total_cases} (完成: {result.completed_cases}, 失败: {result.failed_cases})")
        lines.append(f"- **成功率:** {result.success_rate:.1%}")
        lines.append("")

        # 聚合指标
        lines.append("## 聚合指标")
        lines.append("")
        lines.append("| 指标 | 值 | 说明 |")
        lines.append("|------|-----|------|")
        metric_descs = {
            "accuracy": "准确率", "precision": "精确率",
            "recall": "召回率", "f1": "F1分数",
            "mrr": "MRR", "ndcg": "NDCG",
        }
        for name, value in result.aggregated_metrics.items():
            desc = metric_descs.get(name, name)
            lines.append(f"| {desc} | {value:.4f} | - |")
        lines.append("")

        # 可视化
        lines.append("## 指标可视化")
        lines.append("")
        lines.append("```")
        for name, value in result.aggregated_metrics.items():
            desc = metric_descs.get(name, name)
            bar_len = int(value * 40)
            bar = "█" * bar_len + "░" * (40 - bar_len)
            lines.append(f"  {desc:6s} │{bar}│ {value:.4f}")
        lines.append("```")
        lines.append("")

        # 配置
        if result.config:
            lines.append("## 配置")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(result.config, indent=2, ensure_ascii=False))
            lines.append("```")
            lines.append("")

        # 错误详情
        errors = [cr for cr in result.case_results if cr.error]
        if errors:
            lines.append("## 错误详情")
            lines.append("")
            for cr in errors[:20]:
                lines.append(f"- **{cr.case_id}**: {cr.error}")
            lines.append("")

        # 各用例延迟分布
        latencies = [cr.latency_ms for cr in result.case_results if not cr.error]
        if latencies:
            avg_lat = sum(latencies) / len(latencies)
            max_lat = max(latencies)
            min_lat = min(latencies)
            lines.append("## 延迟统计")
            lines.append("")
            lines.append(f"- **平均:** {avg_lat:.1f}ms")
            lines.append(f"- **最小:** {min_lat:.1f}ms")
            lines.append(f"- **最大:** {max_lat:.1f}ms")
            lines.append("")

        lines.append("---")
        lines.append(f"*报告生成时间: {datetime.now().isoformat()}*")
        return "\n".join(lines)

    @staticmethod
    def to_json(result: EvaluationResult) -> Dict[str, Any]:
        """生成 JSON 格式报告"""
        return result.to_dict()

    @staticmethod
    def to_html(result: EvaluationResult) -> str:
        """生成简单 HTML 报告"""
        metric_descs = {
            "accuracy": "准确率", "precision": "精确率",
            "recall": "召回率", "f1": "F1分数",
            "mrr": "MRR", "ndcg": "NDCG",
        }

        metrics_rows = ""
        for name, value in result.aggregated_metrics.items():
            desc = metric_descs.get(name, name)
            bar_pct = value * 100
            color = "#4CAF50" if value >= 0.8 else "#FF9800" if value >= 0.5 else "#F44336"
            metrics_rows += f"""
            <tr>
                <td>{desc}</td>
                <td>
                    <div style="background:#eee;border-radius:4px;overflow:hidden;height:20px;width:200px">
                        <div style="background:{color};height:100%;width:{bar_pct}%"></div>
                    </div>
                </td>
                <td><strong>{value:.4f}</strong></td>
            </tr>"""

        errors = [cr for cr in result.case_results if cr.error]
        error_rows = ""
        for cr in errors[:10]:
            error_rows += f"<tr><td>{cr.case_id}</td><td>{cr.error}</td></tr>"

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>评估报告: {result.run_name}</title>
<style>
  body{{font-family:system-ui,sans-serif;max-width:900px;margin:0 auto;padding:20px}}
  h1{{color:#333}} table{{border-collapse:collapse;width:100%}}
  th,td{{border:1px solid #ddd;padding:8px;text-align:left}}
  th{{background:#f5f5f5}} .badge{{padding:2px 8px;border-radius:4px;color:#fff;font-size:12px}}
  .badge-ok{{background:#4CAF50}} .badge-fail{{background:#F44336}}
</style>
</head>
<body>
<h1>📊 {result.run_name}</h1>
<p><strong>ID:</strong> {result.id} | <strong>状态:</strong>
<span class="badge {'badge-ok' if result.status=='completed' else 'badge-fail'}">{result.status}</span>
| <strong>耗时:</strong> {result.duration_seconds:.2f}s</p>
<p><strong>用例:</strong> {result.total_cases} (完成 {result.completed_cases}, 失败 {result.failed_cases}, 成功率 {result.success_rate:.1%})</p>
<h2>聚合指标</h2>
<table><tr><th>指标</th><th>分布</th><th>值</th></tr>{metrics_rows}</table>
{"<h2>错误</h2><table><tr><th>Case</th><th>Error</th></tr>" + error_rows + "</table>" if error_rows else ""}
<footer><p style="color:#999;font-size:12px">Generated {datetime.now().isoformat()}</p></footer>
</body></html>"""

    @staticmethod
    def compare_markdown(results: List[EvaluationResult]) -> str:
        """生成对比报告"""
        if not results:
            return "# 对比报告\n\n无评估结果。"

        lines = ["# 评估对比报告", ""]

        # 基本信息表
        lines.append("## 基本信息")
        lines.append("")
        lines.append("| 运行名称 | 数据集 | 用例数 | 成功率 | 耗时 |")
        lines.append("|----------|--------|--------|--------|------|")
        for r in results:
            lines.append(f"| {r.run_name} | {r.dataset_name} | {r.total_cases} "
                        f"| {r.success_rate:.1%} | {r.duration_seconds:.2f}s |")
        lines.append("")

        # 指标对比
        all_metrics = set()
        for r in results:
            all_metrics.update(r.aggregated_metrics.keys())

        if all_metrics:
            lines.append("## 指标对比")
            lines.append("")
            header = "| 指标 |" + " | ".join(r.run_name for r in results) + " | 最佳 |"
            sep = "|------|" + "|".join(["-----"] * len(results)) + "|------|"
            lines.append(header)
            lines.append(sep)

            metric_descs = {
                "accuracy": "准确率", "precision": "精确率",
                "recall": "召回率", "f1": "F1分数",
                "mrr": "MRR", "ndcg": "NDCG",
            }

            for metric in sorted(all_metrics):
                desc = metric_descs.get(metric, metric)
                vals = [r.aggregated_metrics.get(metric, 0) for r in results]
                best_idx = vals.index(max(vals))
                best_name = results[best_idx].run_name
                row = f"| {desc} |" + " | ".join(f"{v:.4f}" for v in vals) + f"| {best_name} |"
                lines.append(row)
            lines.append("")

        # 可视化对比
        lines.append("## 可视化对比")
        lines.append("")
        lines.append("```")
        for metric in sorted(all_metrics):
            desc = metric_descs.get(metric, metric)
            lines.append(f"  {desc}:")
            for r in results:
                val = r.aggregated_metrics.get(metric, 0)
                bar_len = int(val * 30)
                bar = "█" * bar_len + "░" * (30 - bar_len)
                lines.append(f"    {r.run_name:15s} │{bar}│ {val:.4f}")
            lines.append("")
        lines.append("```")

        lines.append("---")
        lines.append(f"*报告生成时间: {datetime.now().isoformat()}*")
        return "\n".join(lines)
