import pytest
import tempfile
import os
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from logtail.cli import main, LogTailAggregator
from logtail.extractor import LogExtractor


class TestCliCommands:
    def test_main_group(self):
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])
        
        assert result.exit_code == 0
        assert '日志 Tail 聚合器' in result.output
        assert 'tail' in result.output
        assert 'analyze' in result.output
    
    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(main, ['--version'])
        
        assert result.exit_code == 0
        assert '0.1.0' in result.output
    
    def test_tail_command_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ['tail', '--help'])
        
        assert result.exit_code == 0
        assert '聚合时间窗口' in result.output
        assert '输出格式' in result.output
        assert '实时显示原始日志行' in result.output
        assert 'YAML 配置文件路径' in result.output
    
    def test_analyze_command_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ['analyze', '--help'])
        
        assert result.exit_code == 0
        assert '从文件末尾读取的行数' in result.output
        assert '输出格式' in result.output
    
    def test_analyze_command_basic(self, tmp_path):
        log_file = tmp_path / 'access.log'
        log_content = """GET /api/users HTTP/1.1 200 45ms
POST /api/create HTTP/1.1 201 120ms
GET /api/users HTTP/1.1 200 30ms
ERROR: Database connection failed
GET /api/nonexistent HTTP/1.1 404 10ms
"""
        log_file.write_text(log_content)
        
        runner = CliRunner()
        result = runner.invoke(main, ['analyze', str(log_file), '--lines', '5'])
        
        assert result.exit_code == 0
        assert 'Total Requests' in result.output
        assert 'QPS' in result.output
        assert 'Error Rate' in result.output
        assert 'Status Codes' in result.output
        assert '200' in result.output
        assert '201' in result.output
        assert '404' in result.output
        assert 'Error' in result.output or 'ERROR' in result.output
    
    def test_analyze_command_json_format(self, tmp_path):
        log_file = tmp_path / 'test.log'
        log_file.write_text('GET /api HTTP/1.1 200 50ms\n')
        
        runner = CliRunner()
        result = runner.invoke(main, ['analyze', str(log_file), '--format', 'json'])
        
        assert result.exit_code == 0
        import json
        parsed = json.loads(result.output)
        assert parsed['type'] == 'window'
        assert 'metrics' in parsed
    
    def test_analyze_command_table_format(self, tmp_path):
        log_file = tmp_path / 'test.log'
        log_file.write_text('GET /api HTTP/1.1 200 50ms\n')
        
        runner = CliRunner()
        result = runner.invoke(main, ['analyze', str(log_file), '--format', 'table'])
        
        assert result.exit_code == 0
        assert '+' in result.output
        assert '|' in result.output
        assert '-' in result.output


class TestLogTailAggregator:
    def test_initialization(self):
        aggregator = LogTailAggregator(
            patterns=['*.log'],
            window_seconds=5.0,
            format_type='json',
            show_logs=True,
            poll_interval=0.05
        )
        
        assert aggregator.patterns == ['*.log']
        assert aggregator.window_seconds == 5.0
        assert aggregator.format_type == 'json'
        assert aggregator.show_logs == True
        assert aggregator.poll_interval == 0.05
        assert aggregator.aggregator is None
        assert aggregator.tailer is None
        assert aggregator.running == False
    
    def test_initialization_with_extractor_config(self):
        config = {
            'rules': [
                {'name': 'test', 'pattern': r'(test)'}
            ]
        }
        
        aggregator = LogTailAggregator(
            patterns=['*.log'],
            extractor_config=config
        )
        
        assert aggregator.extractor is not None
    
    def test_on_log_line_extracts_fields(self):
        aggregator = LogTailAggregator(
            patterns=['*.log'],
            window_seconds=10.0,
            show_logs=True
        )
        
        aggregator.aggregator = MagicMock()
        
        log_data = {
            'file': 'test.log',
            'line': 'GET /api HTTP/1.1 200 50ms',
            'timestamp': 1000000000.0
        }
        
        aggregator.on_log_line(log_data)
        
        aggregator.aggregator.add_log_entry.assert_called_once()
        call_args = aggregator.aggregator.add_log_entry.call_args
        assert call_args[1]['status_code'] == 200
        assert call_args[1]['response_time'] == 50.0
    
    def test_on_log_line_detects_errors(self):
        aggregator = LogTailAggregator(
            patterns=['*.log'],
            window_seconds=10.0
        )
        
        aggregator.aggregator = MagicMock()
        
        log_data = {
            'file': 'error.log',
            'line': 'ERROR: Something went wrong',
            'timestamp': 1000000000.0
        }
        
        aggregator.on_log_line(log_data)
        
        call_args = aggregator.aggregator.add_log_entry.call_args
        assert call_args[1]['is_error'] == True
    
    def test_on_window_complete_outputs_metrics(self, capsys):
        aggregator = LogTailAggregator(
            patterns=['*.log'],
            format_type='json'
        )
        
        from logtail.aggregator import Metrics
        metrics = Metrics()
        metrics.update(data={'line': 'test'})
        metrics.update(data={'line': 'test2'})
        
        aggregator.on_window_complete(1000000000.0, 1000000010.0, metrics)
        
        captured = capsys.readouterr()
        import json
        parsed = json.loads(captured.out)
        assert parsed['type'] == 'window'
        assert parsed['metrics']['total_count'] == 2
