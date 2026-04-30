import click
import sys
import signal
import time
import yaml
import re
from typing import List, Optional, Dict, Any

from logtail.tail import LogTailer
from logtail.aggregator import TimeWindowAggregator, Metrics
from logtail.extractor import LogExtractor, ExtractionRule, InvalidRegexError
from logtail.formatter import get_formatter, BaseFormatter


class EncodingError(Exception):
    pass


class LogTailAggregator:
    def __init__(self, 
                 patterns: List[str],
                 window_seconds: float = 10.0,
                 format_type: str = 'text',
                 show_logs: bool = False,
                 extractor_config: Optional[Dict[str, Any]] = None,
                 poll_interval: float = 0.1):
        self.patterns = patterns
        self.window_seconds = window_seconds
        self.format_type = format_type
        self.show_logs = show_logs
        self.poll_interval = poll_interval
        
        self.formatter: BaseFormatter = get_formatter(format_type)
        
        if extractor_config:
            self.extractor = LogExtractor.from_yaml_config(extractor_config)
        else:
            self.extractor = LogExtractor.create_default()
        
        self.aggregator: Optional[TimeWindowAggregator] = None
        self.tailer: Optional[LogTailer] = None
        self.running = False
    
    def on_window_complete(self, start_time: float, end_time: float, metrics: Metrics):
        duration = end_time - start_time
        metrics_dict = metrics.to_dict(duration)
        output = self.formatter.format_window(start_time, end_time, metrics_dict)
        click.echo(output)
    
    def on_log_line(self, log_data: Dict[str, Any]):
        line = log_data['line']
        file_path = log_data['file']
        
        extracted = self.extractor.extract(line)
        
        if self.aggregator:
            self.aggregator.add_log_entry(
                data=log_data,
                is_error=extracted.get('is_error', False),
                status_code=extracted.get('status_code'),
                response_time=extracted.get('response_time'),
                custom_extracted=extracted.get('custom_fields')
            )
        
        if self.show_logs:
            output = self.formatter.format_log_line(file_path, line, extracted)
            click.echo(output)
    
    def start(self):
        self.running = True
        
        self.aggregator = TimeWindowAggregator(
            window_seconds=self.window_seconds,
            on_window_complete=self.on_window_complete
        )
        
        self.tailer = LogTailer(
            patterns=self.patterns,
            callback=self.on_log_line
        )
        
        self.tailer.start(poll_interval=self.poll_interval)
        
        def signal_handler(sig, frame):
            self.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        self.running = False
        
        if self.tailer:
            self.tailer.stop()
        
        if self.aggregator:
            self.aggregator.flush()
            stats = self.aggregator.get_current_stats()
            output = self.formatter.format_summary(stats)
            click.echo(output)
        
        sys.exit(0)


@click.group()
@click.version_option(version='0.1.0')
def main():
    """日志 Tail 聚合器 - 同时 tail 多个日志文件并聚合统计指标"""
    pass


@main.command()
@click.argument('patterns', nargs=-1, required=True)
@click.option('--window', '-w', 'window_seconds', type=float, default=10.0,
              help='聚合时间窗口（秒），默认 10 秒')
@click.option('--format', '-f', 'format_type', type=click.Choice(['text', 'json', 'table']),
              default='text', help='输出格式：text（默认）、json 或 table')
@click.option('--show-logs', '-l', is_flag=True, default=False,
              help='实时显示原始日志行')
@click.option('--config', '-c', 'config_file', type=click.Path(exists=True),
              help='YAML 配置文件路径，包含字段提取规则')
@click.option('--poll-interval', '-p', type=float, default=0.1,
              help='文件轮询间隔（秒），默认 0.1 秒')
def tail(patterns, window_seconds, format_type, show_logs, config_file, poll_interval):
    """
    Tail 多个日志文件并聚合统计指标
    
    PATTERNS: 一个或多个日志文件路径，支持 glob 通配符（如 logs/*.log、**/*.log）
    
    示例:
        logtail tail logs/*.log
        logtail tail /var/log/nginx/*.log --window 5 --format json
        logtail tail logs/**/*.log --show-logs --config rules.yaml
    """
    try:
        extractor_config = None
        if config_file:
            with open(config_file, 'r', encoding='utf-8') as f:
                extractor_config = yaml.safe_load(f)
        
        aggregator = LogTailAggregator(
            patterns=list(patterns),
            window_seconds=window_seconds,
            format_type=format_type,
            show_logs=show_logs,
            extractor_config=extractor_config,
            poll_interval=poll_interval
        )
    except re.error as e:
        click.echo(f"错误: 配置文件中的正则表达式无效: {e}", err=True)
        sys.exit(1)
    except InvalidRegexError as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"错误: 初始化失败: {e}", err=True)
        sys.exit(1)
    
    click.echo(f"开始监控日志文件: {', '.join(patterns)}")
    click.echo(f"时间窗口: {window_seconds} 秒")
    click.echo(f"输出格式: {format_type}")
    click.echo("按 Ctrl+C 停止...")
    click.echo("-" * 60)
    
    aggregator.start()


def read_file_with_fallback(file_path: str, encodings_to_try=None):
    if encodings_to_try is None:
        encodings_to_try = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1']
    
    last_error = None
    for encoding in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.readlines()
        except UnicodeDecodeError as e:
            last_error = e
            continue
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            click.echo(f"警告: 文件 '{file_path}' 包含非 UTF-8 编码字符，已使用替换模式读取", err=True)
            return lines
    except Exception as e:
        raise EncodingError(f"无法读取文件 '{file_path}': {e}") from last_error


@main.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--lines', '-n', type=int, default=10,
              help='从文件末尾读取的行数，默认 10 行')
@click.option('--format', '-f', 'format_type', type=click.Choice(['text', 'json', 'table']),
              default='text', help='输出格式：text（默认）、json 或 table')
@click.option('--config', '-c', 'config_file', type=click.Path(exists=True),
              help='YAML 配置文件路径，包含字段提取规则')
@click.option('--duration', '-d', type=float, default=None,
              help='日志覆盖的时间范围（秒），用于计算 QPS。如果不指定，QPS 将不显示')
def analyze(file_path, lines, format_type, config_file, duration):
    """
    分析已有的日志文件（非实时）
    
    FILE_PATH: 要分析的日志文件路径
    
    示例:
        logtail analyze access.log --lines 100
        logtail analyze /var/log/nginx/access.log --format json
        logtail analyze access.log --duration 3600  # 假设日志覆盖 1 小时，计算 QPS
    """
    formatter = get_formatter(format_type)
    
    try:
        if config_file:
            with open(config_file, 'r', encoding='utf-8') as f:
                extractor_config = yaml.safe_load(f)
            extractor = LogExtractor.from_yaml_config(extractor_config)
        else:
            extractor = LogExtractor.create_default()
    except re.error as e:
        click.echo(f"错误: 配置文件中的正则表达式无效: {e}", err=True)
        sys.exit(1)
    except InvalidRegexError as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"错误: 加载配置文件失败: {e}", err=True)
        sys.exit(1)
    
    try:
        all_lines = read_file_with_fallback(file_path)
    except EncodingError as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)
    
    recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
    
    metrics = Metrics()
    
    for line in recent_lines:
        line = line.rstrip('\n')
        if not line:
            continue
        
        extracted = extractor.extract(line)
        metrics.update(
            data={'line': line},
            is_error=extracted.get('is_error', False),
            status_code=extracted.get('status_code'),
            response_time=extracted.get('response_time'),
            custom_extracted=extracted.get('custom_fields')
        )
    
    if duration is not None and duration > 0:
        metrics_dict = metrics.to_dict(duration)
        metrics_dict['qps_calculation_note'] = f"基于用户指定的 {duration} 秒时间范围计算"
    else:
        metrics_dict = metrics.to_dict(0)
        metrics_dict['qps'] = None
        metrics_dict['qps_note'] = "未指定时间范围，QPS 不适用（使用 --duration 参数指定时间范围以计算 QPS）"
    
    output = formatter.format_window(0, len(recent_lines), metrics_dict)
    click.echo(output)


if __name__ == '__main__':
    main()
