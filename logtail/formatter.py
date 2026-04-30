import json
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass


class BaseFormatter(ABC):
    @abstractmethod
    def format_window(self, start_time: float, end_time: float, metrics: Dict[str, Any]) -> str:
        pass
    
    @abstractmethod
    def format_static_analysis(self, metrics: Dict[str, Any], analysis_time: float = None) -> str:
        pass
    
    @abstractmethod
    def format_log_line(self, file_path: str, line: str, extracted: Dict[str, Any]) -> str:
        pass
    
    @abstractmethod
    def format_summary(self, total_stats: Dict[str, Any]) -> str:
        pass
    
    def _format_time(self, timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    
    def _get_analysis_time(self, analysis_time: float = None) -> str:
        if analysis_time is None:
            analysis_time = time.time()
        return self._format_time(analysis_time)


class JsonFormatter(BaseFormatter):
    def format_window(self, start_time: float, end_time: float, metrics: Dict[str, Any]) -> str:
        data = {
            'type': 'window',
            'start_time': self._format_time(start_time),
            'end_time': self._format_time(end_time),
            'metrics': metrics
        }
        return json.dumps(data, ensure_ascii=False, default=str)
    
    def format_static_analysis(self, metrics: Dict[str, Any], analysis_time: float = None) -> str:
        data = {
            'type': 'static_analysis',
            'analysis_time': self._get_analysis_time(analysis_time),
            'metrics': metrics
        }
        return json.dumps(data, ensure_ascii=False, default=str)
    
    def format_log_line(self, file_path: str, line: str, extracted: Dict[str, Any]) -> str:
        data = {
            'type': 'log_line',
            'file': file_path,
            'raw_line': line,
            'extracted': extracted
        }
        return json.dumps(data, ensure_ascii=False, default=str)
    
    def format_summary(self, total_stats: Dict[str, Any]) -> str:
        data = {
            'type': 'summary',
            'stats': total_stats
        }
        return json.dumps(data, ensure_ascii=False, default=str)


class TextFormatter(BaseFormatter):
    def _format_float(self, value: Optional[float], default: str = "N/A") -> str:
        if value is None:
            return default
        return f"{value:.2f}"
    
    def format_window(self, start_time: float, end_time: float, metrics: Dict[str, Any]) -> str:
        qps_value = metrics.get('qps')
        qps_str = self._format_float(qps_value, "N/A (use --duration)")
        
        lines = [
            "=" * 60,
            f"Window: {self._format_time(start_time)} - {self._format_time(end_time)}",
            "=" * 60,
            f"  Total Requests: {metrics.get('total_count', 0)}",
            f"  QPS: {qps_str}",
            f"  Error Rate: {self._format_float(metrics.get('error_rate', 0.0))}%",
        ]
        
        if 'qps_note' in metrics:
            lines.append(f"  Note: {metrics['qps_note']}")
        
        if 'qps_calculation_note' in metrics:
            lines.append(f"  Note: {metrics['qps_calculation_note']}")
        
        if 'status_codes' in metrics:
            lines.append("  Status Codes:")
            for code, count in sorted(metrics['status_codes'].items()):
                lines.append(f"    {code}: {count}")
        
        if 'avg_response_time' in metrics:
            lines.append(f"  Avg Response Time: {metrics['avg_response_time']:.2f}ms")
        
        if 'p95_response_time' in metrics:
            lines.append(f"  P95 Response Time: {metrics['p95_response_time']:.2f}ms")
        
        if 'custom_fields' in metrics:
            for field_name, values in metrics['custom_fields'].items():
                lines.append(f"  {field_name}:")
                for value, count in sorted(values.items(), key=lambda x: x[1], reverse=True):
                    lines.append(f"    {value}: {count}")
        
        lines.append("=" * 60)
        return "\n".join(lines)
    
    def format_static_analysis(self, metrics: Dict[str, Any], analysis_time: float = None) -> str:
        qps_value = metrics.get('qps')
        qps_str = self._format_float(qps_value, "N/A (use --duration)")
        analysis_time_str = self._get_analysis_time(analysis_time)
        
        lines = [
            "=" * 60,
            f"静态分析 - {analysis_time_str}",
            "=" * 60,
            f"  Total Requests: {metrics.get('total_count', 0)}",
            f"  QPS: {qps_str}",
            f"  Error Rate: {self._format_float(metrics.get('error_rate', 0.0))}%",
        ]
        
        if 'qps_note' in metrics:
            lines.append(f"  Note: {metrics['qps_note']}")
        
        if 'qps_calculation_note' in metrics:
            lines.append(f"  Note: {metrics['qps_calculation_note']}")
        
        if 'status_codes' in metrics:
            lines.append("  Status Codes:")
            for code, count in sorted(metrics['status_codes'].items()):
                lines.append(f"    {code}: {count}")
        
        if 'avg_response_time' in metrics:
            lines.append(f"  Avg Response Time: {metrics['avg_response_time']:.2f}ms")
        
        if 'p95_response_time' in metrics:
            lines.append(f"  P95 Response Time: {metrics['p95_response_time']:.2f}ms")
        
        if 'custom_fields' in metrics:
            for field_name, values in metrics['custom_fields'].items():
                lines.append(f"  {field_name}:")
                for value, count in sorted(values.items(), key=lambda x: x[1], reverse=True):
                    lines.append(f"    {value}: {count}")
        
        lines.append("=" * 60)
        return "\n".join(lines)
    
    def format_log_line(self, file_path: str, line: str, extracted: Dict[str, Any]) -> str:
        parts = [f"[{file_path}] {line}"]
        
        extracted_info = []
        if extracted.get('is_error'):
            extracted_info.append("ERROR")
        if extracted.get('status_code'):
            extracted_info.append(f"status={extracted['status_code']}")
        if extracted.get('response_time'):
            extracted_info.append(f"rt={extracted['response_time']}ms")
        
        if extracted_info:
            parts.append(f" ({', '.join(extracted_info)})")
        
        return "".join(parts)
    
    def format_summary(self, total_stats: Dict[str, Any]) -> str:
        total = total_stats.get('total', {}).get('metrics', {})
        qps_value = total.get('qps')
        qps_str = self._format_float(qps_value, "N/A")
        
        lines = [
            "=" * 60,
            "SUMMARY",
            "=" * 60,
            f"  Total Requests: {total.get('total_count', 0)}",
            f"  Average QPS: {qps_str}",
            f"  Error Rate: {self._format_float(total.get('error_rate', 0.0))}%",
        ]
        
        if 'status_codes' in total:
            lines.append("  Status Codes:")
            for code, count in sorted(total['status_codes'].items()):
                lines.append(f"    {code}: {count}")
        
        if 'avg_response_time' in total:
            lines.append(f"  Avg Response Time: {total['avg_response_time']:.2f}ms")
        
        if 'p95_response_time' in total:
            lines.append(f"  P95 Response Time: {total['p95_response_time']:.2f}ms")
        
        lines.append("=" * 60)
        return "\n".join(lines)


class TableFormatter(BaseFormatter):
    def _format_float(self, value: Optional[float], default: str = "N/A") -> str:
        if value is None:
            return default
        return f"{value:.2f}"
    
    def _draw_line(self, width: int, char: str = "-") -> str:
        return "+" + char * (width - 2) + "+"
    
    def _format_row(self, text: str, width: int) -> str:
        return f"| {text:<{width - 4}} |"
    
    def format_window(self, start_time: float, end_time: float, metrics: Dict[str, Any]) -> str:
        width = 60
        qps_value = metrics.get('qps')
        qps_str = self._format_float(qps_value, "N/A")
        
        lines = [
            self._draw_line(width),
            self._format_row(f"Window: {self._format_time(start_time)} - {self._format_time(end_time)}", width),
            self._draw_line(width, "="),
        ]
        
        rows = [
            ("Total Requests", str(metrics.get('total_count', 0))),
            ("QPS", qps_str),
            ("Error Rate", f"{self._format_float(metrics.get('error_rate', 0.0))}%"),
        ]
        
        for label, value in rows:
            lines.append(self._format_row(f"{label}: {value}", width))
        
        if 'qps_note' in metrics:
            lines.append(self._format_row(f"Note: {metrics['qps_note']}", width))
        
        if 'status_codes' in metrics:
            lines.append(self._draw_line(width, "-"))
            lines.append(self._format_row("Status Codes:", width))
            for code, count in sorted(metrics['status_codes'].items()):
                lines.append(self._format_row(f"  {code}: {count}", width))
        
        if 'avg_response_time' in metrics:
            lines.append(self._draw_line(width, "-"))
            lines.append(self._format_row(f"Avg Response Time: {metrics['avg_response_time']:.2f}ms", width))
        
        if 'p95_response_time' in metrics:
            lines.append(self._format_row(f"P95 Response Time: {metrics['p95_response_time']:.2f}ms", width))
        
        lines.append(self._draw_line(width, "="))
        return "\n".join(lines)
    
    def format_static_analysis(self, metrics: Dict[str, Any], analysis_time: float = None) -> str:
        width = 60
        qps_value = metrics.get('qps')
        qps_str = self._format_float(qps_value, "N/A")
        analysis_time_str = self._get_analysis_time(analysis_time)
        
        lines = [
            self._draw_line(width, "="),
            self._format_row(f"静态分析 - {analysis_time_str}", width),
            self._draw_line(width, "="),
        ]
        
        rows = [
            ("Total Requests", str(metrics.get('total_count', 0))),
            ("QPS", qps_str),
            ("Error Rate", f"{self._format_float(metrics.get('error_rate', 0.0))}%"),
        ]
        
        for label, value in rows:
            lines.append(self._format_row(f"{label}: {value}", width))
        
        if 'qps_note' in metrics:
            lines.append(self._format_row(f"Note: {metrics['qps_note']}", width))
        
        if 'qps_calculation_note' in metrics:
            lines.append(self._format_row(f"Note: {metrics['qps_calculation_note']}", width))
        
        if 'status_codes' in metrics:
            lines.append(self._draw_line(width, "-"))
            lines.append(self._format_row("Status Codes:", width))
            for code, count in sorted(metrics['status_codes'].items()):
                lines.append(self._format_row(f"  {code}: {count}", width))
        
        if 'avg_response_time' in metrics:
            lines.append(self._draw_line(width, "-"))
            lines.append(self._format_row(f"Avg Response Time: {metrics['avg_response_time']:.2f}ms", width))
        
        if 'p95_response_time' in metrics:
            lines.append(self._format_row(f"P95 Response Time: {metrics['p95_response_time']:.2f}ms", width))
        
        lines.append(self._draw_line(width, "="))
        return "\n".join(lines)
    
    def format_log_line(self, file_path: str, line: str, extracted: Dict[str, Any]) -> str:
        width = 60
        parts = []
        
        error_marker = "[ERROR] " if extracted.get('is_error') else ""
        status = f" status={extracted['status_code']}" if extracted.get('status_code') else ""
        rt = f" rt={extracted['response_time']}ms" if extracted.get('response_time') else ""
        
        log_text = f"{error_marker}[{file_path}] {line}{status}{rt}"
        
        if len(log_text) > width - 4:
            log_text = log_text[:width - 7] + "..."
        
        return f"| {log_text:<{width - 4}} |"
    
    def format_summary(self, total_stats: Dict[str, Any]) -> str:
        width = 60
        total = total_stats.get('total', {}).get('metrics', {})
        qps_value = total.get('qps')
        qps_str = self._format_float(qps_value, "N/A")
        
        lines = [
            self._draw_line(width, "="),
            self._format_row("SUMMARY", width),
            self._draw_line(width, "="),
            self._format_row(f"Total Requests: {total.get('total_count', 0)}", width),
            self._format_row(f"Average QPS: {qps_str}", width),
            self._format_row(f"Error Rate: {self._format_float(total.get('error_rate', 0.0))}%", width),
        ]
        
        if 'avg_response_time' in total:
            lines.append(self._format_row(f"Avg Response Time: {total['avg_response_time']:.2f}ms", width))
        
        if 'p95_response_time' in total:
            lines.append(self._format_row(f"P95 Response Time: {total['p95_response_time']:.2f}ms", width))
        
        lines.append(self._draw_line(width, "="))
        return "\n".join(lines)


def get_formatter(format_type: str) -> BaseFormatter:
    formatters = {
        'json': JsonFormatter,
        'text': TextFormatter,
        'table': TableFormatter,
    }
    formatter_class = formatters.get(format_type.lower(), TextFormatter)
    return formatter_class()
