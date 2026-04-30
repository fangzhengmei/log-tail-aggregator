import pytest
import json

from logtail.formatter import (
    JsonFormatter, TextFormatter, TableFormatter,
    get_formatter, BaseFormatter
)


class TestJsonFormatter:
    def test_format_window(self):
        formatter = JsonFormatter()
        
        metrics = {
            'total_count': 100,
            'error_count': 5,
            'qps': 10.0,
            'error_rate': 5.0,
            'status_codes': {200: 95, 500: 5}
        }
        
        result = formatter.format_window(1000000000.0, 1000000010.0, metrics)
        parsed = json.loads(result)
        
        assert parsed['type'] == 'window'
        assert 'start_time' in parsed
        assert 'end_time' in parsed
        assert parsed['metrics']['total_count'] == 100
        assert parsed['metrics']['error_count'] == 5
        assert parsed['metrics']['qps'] == 10.0
        assert parsed['metrics']['error_rate'] == 5.0
    
    def test_format_log_line(self):
        formatter = JsonFormatter()
        
        extracted = {
            'custom_fields': {'method': 'GET'},
            'is_error': False,
            'status_code': 200,
            'response_time': 45.5
        }
        
        result = formatter.format_log_line('/var/log/access.log', 'GET /api 200', extracted)
        parsed = json.loads(result)
        
        assert parsed['type'] == 'log_line'
        assert parsed['file'] == '/var/log/access.log'
        assert parsed['raw_line'] == 'GET /api 200'
        assert parsed['extracted']['custom_fields']['method'] == 'GET'
        assert parsed['extracted']['status_code'] == 200
    
    def test_format_summary(self):
        formatter = JsonFormatter()
        
        stats = {
            'total': {
                'metrics': {
                    'total_count': 1000,
                    'error_count': 50,
                    'qps': 100.0,
                    'error_rate': 5.0
                }
            }
        }
        
        result = formatter.format_summary(stats)
        parsed = json.loads(result)
        
        assert parsed['type'] == 'summary'
        assert parsed['stats']['total']['metrics']['total_count'] == 1000


class TestTextFormatter:
    def test_format_window_basic(self):
        formatter = TextFormatter()
        
        metrics = {
            'total_count': 100,
            'error_count': 5,
            'qps': 10.0,
            'error_rate': 5.0
        }
        
        result = formatter.format_window(1000000000.0, 1000000010.0, metrics)
        
        assert 'Total Requests: 100' in result
        assert 'QPS: 10.00' in result
        assert 'Error Rate: 5.00%' in result
    
    def test_format_window_with_status_codes(self):
        formatter = TextFormatter()
        
        metrics = {
            'total_count': 100,
            'error_count': 5,
            'qps': 10.0,
            'error_rate': 5.0,
            'status_codes': {200: 95, 500: 5}
        }
        
        result = formatter.format_window(1000000000.0, 1000000010.0, metrics)
        
        assert 'Status Codes:' in result
        assert '200: 95' in result
        assert '500: 5' in result
    
    def test_format_window_with_response_time(self):
        formatter = TextFormatter()
        
        metrics = {
            'total_count': 10,
            'error_count': 0,
            'qps': 1.0,
            'error_rate': 0.0,
            'avg_response_time': 50.5,
            'p95_response_time': 100.0
        }
        
        result = formatter.format_window(1000000000.0, 1000000010.0, metrics)
        
        assert 'Avg Response Time: 50.50ms' in result
        assert 'P95 Response Time: 100.00ms' in result
    
    def test_format_log_line_normal(self):
        formatter = TextFormatter()
        
        extracted = {
            'custom_fields': {},
            'is_error': False,
            'status_code': 200,
            'response_time': 45.5
        }
        
        result = formatter.format_log_line('access.log', 'GET /api', extracted)
        
        assert '[access.log] GET /api' in result
        assert 'status=200' in result
        assert 'rt=45.5ms' in result
    
    def test_format_log_line_error(self):
        formatter = TextFormatter()
        
        extracted = {
            'custom_fields': {},
            'is_error': True,
            'status_code': 500,
            'response_time': None
        }
        
        result = formatter.format_log_line('error.log', 'Something failed', extracted)
        
        assert 'ERROR' in result
        assert 'status=500' in result
    
    def test_format_summary(self):
        formatter = TextFormatter()
        
        stats = {
            'total': {
                'metrics': {
                    'total_count': 1000,
                    'error_count': 50,
                    'qps': 100.0,
                    'error_rate': 5.0,
                    'avg_response_time': 25.5
                }
            }
        }
        
        result = formatter.format_summary(stats)
        
        assert 'SUMMARY' in result
        assert 'Total Requests: 1000' in result
        assert 'Average QPS: 100.00' in result
        assert 'Error Rate: 5.00%' in result
        assert 'Avg Response Time: 25.50ms' in result


class TestTableFormatter:
    def test_format_window_structure(self):
        formatter = TableFormatter()
        
        metrics = {
            'total_count': 100,
            'error_count': 5,
            'qps': 10.0,
            'error_rate': 5.0
        }
        
        result = formatter.format_window(1000000000.0, 1000000010.0, metrics)
        
        assert result.startswith('+')
        assert '-' in result
        assert '|' in result
        assert 'Total Requests' in result
        assert 'QPS' in result
        assert 'Error Rate' in result
    
    def test_format_log_line(self):
        formatter = TableFormatter()
        
        extracted = {
            'custom_fields': {},
            'is_error': True,
            'status_code': 500,
            'response_time': 100.0
        }
        
        result = formatter.format_log_line('test.log', 'Error occurred', extracted)
        
        assert result.startswith('|')
        assert result.endswith('|')
        assert '[ERROR]' in result
        assert 'status=500' in result
    
    def test_format_summary(self):
        formatter = TableFormatter()
        
        stats = {
            'total': {
                'metrics': {
                    'total_count': 500,
                    'error_count': 10,
                    'qps': 50.0,
                    'error_rate': 2.0
                }
            }
        }
        
        result = formatter.format_summary(stats)
        
        assert 'SUMMARY' in result
        assert 'Total Requests: 500' in result
        assert 'Average QPS: 50.00' in result


class TestGetFormatter:
    def test_get_json_formatter(self):
        formatter = get_formatter('json')
        assert isinstance(formatter, JsonFormatter)
    
    def test_get_text_formatter(self):
        formatter = get_formatter('text')
        assert isinstance(formatter, TextFormatter)
    
    def test_get_table_formatter(self):
        formatter = get_formatter('table')
        assert isinstance(formatter, TableFormatter)
    
    def test_get_formatter_case_insensitive(self):
        formatter = get_formatter('JSON')
        assert isinstance(formatter, JsonFormatter)
        
        formatter = get_formatter('Text')
        assert isinstance(formatter, TextFormatter)
    
    def test_get_formatter_default(self):
        formatter = get_formatter('unknown_type')
        assert isinstance(formatter, TextFormatter)
