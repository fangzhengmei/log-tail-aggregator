import pytest
import time
from unittest.mock import Mock, call

from logtail.aggregator import Metrics, TimeWindowAggregator


class TestMetrics:
    def test_initial_state(self):
        metrics = Metrics()
        assert metrics.total_count == 0
        assert metrics.error_count == 0
        assert metrics.status_codes == {}
        assert metrics.response_times == []
        assert metrics.custom_fields == {}
    
    def test_update_basic(self):
        metrics = Metrics()
        metrics.update(data={'line': 'test log'})
        
        assert metrics.total_count == 1
        assert metrics.error_count == 0
    
    def test_update_with_error(self):
        metrics = Metrics()
        metrics.update(data={'line': 'error log'}, is_error=True)
        
        assert metrics.total_count == 1
        assert metrics.error_count == 1
    
    def test_update_with_status_code(self):
        metrics = Metrics()
        metrics.update(data={'line': 'log'}, status_code=200)
        metrics.update(data={'line': 'log'}, status_code=200)
        metrics.update(data={'line': 'log'}, status_code=500)
        
        assert metrics.total_count == 3
        assert metrics.status_codes[200] == 2
        assert metrics.status_codes[500] == 1
    
    def test_update_with_response_time(self):
        metrics = Metrics()
        metrics.update(data={'line': 'log'}, response_time=10.5)
        metrics.update(data={'line': 'log'}, response_time=20.5)
        metrics.update(data={'line': 'log'}, response_time=30.5)
        
        assert metrics.total_count == 3
        assert metrics.response_times == [10.5, 20.5, 30.5]
    
    def test_update_with_custom_fields(self):
        metrics = Metrics()
        metrics.update(data={'line': 'log'}, custom_extracted={'method': 'GET'})
        metrics.update(data={'line': 'log'}, custom_extracted={'method': 'POST'})
        metrics.update(data={'line': 'log'}, custom_extracted={'method': 'GET'})
        
        assert metrics.custom_fields['method']['GET'] == 2
        assert metrics.custom_fields['method']['POST'] == 1
    
    def test_get_qps(self):
        metrics = Metrics()
        for _ in range(100):
            metrics.update(data={'line': 'log'})
        
        qps = metrics.get_qps(10.0)
        assert qps == 10.0
    
    def test_get_qps_zero_duration(self):
        metrics = Metrics()
        metrics.update(data={'line': 'log'})
        
        qps = metrics.get_qps(0)
        assert qps == 0.0
    
    def test_get_error_rate(self):
        metrics = Metrics()
        for i in range(100):
            metrics.update(data={'line': 'log'}, is_error=(i < 10))
        
        error_rate = metrics.get_error_rate()
        assert error_rate == 10.0
    
    def test_get_error_rate_zero_count(self):
        metrics = Metrics()
        error_rate = metrics.get_error_rate()
        assert error_rate == 0.0
    
    def test_get_avg_response_time(self):
        metrics = Metrics()
        metrics.update(data={'line': 'log'}, response_time=10)
        metrics.update(data={'line': 'log'}, response_time=20)
        metrics.update(data={'line': 'log'}, response_time=30)
        
        avg = metrics.get_avg_response_time()
        assert avg == 20.0
    
    def test_get_avg_response_time_none(self):
        metrics = Metrics()
        avg = metrics.get_avg_response_time()
        assert avg is None
    
    def test_get_p95_response_time(self):
        metrics = Metrics()
        for i in range(100):
            metrics.update(data={'line': 'log'}, response_time=i + 1)
        
        p95 = metrics.get_p95_response_time()
        assert p95 == 96
    
    def test_get_p95_response_time_none(self):
        metrics = Metrics()
        p95 = metrics.get_p95_response_time()
        assert p95 is None
    
    def test_to_dict(self):
        metrics = Metrics()
        metrics.update(data={'line': 'log'}, is_error=True, status_code=500, response_time=100)
        metrics.update(data={'line': 'log'}, status_code=200, response_time=50)
        
        result = metrics.to_dict(2.0)
        
        assert result['total_count'] == 2
        assert result['error_count'] == 1
        assert result['qps'] == 1.0
        assert result['error_rate'] == 50.0
        assert result['status_codes'] == {200: 1, 500: 1}
        assert result['avg_response_time'] == 75.0
        assert 'p95_response_time' in result


class TestTimeWindowAggregator:
    def test_initial_state(self):
        aggregator = TimeWindowAggregator(window_seconds=10.0)
        
        assert aggregator.window_seconds == 10.0
        assert aggregator.on_window_complete is None
        assert aggregator.current_window_start is not None
        assert aggregator.current_metrics.total_count == 0
        assert aggregator.total_metrics.total_count == 0
    
    def test_add_log_entry_basic(self):
        callback = Mock()
        aggregator = TimeWindowAggregator(window_seconds=10.0, on_window_complete=callback)
        
        aggregator.add_log_entry(data={'line': 'test'})
        
        assert aggregator.current_metrics.total_count == 1
        assert aggregator.total_metrics.total_count == 1
        callback.assert_not_called()
    
    def test_add_log_entry_with_error(self):
        aggregator = TimeWindowAggregator(window_seconds=10.0)
        
        aggregator.add_log_entry(data={'line': 'error'}, is_error=True)
        
        assert aggregator.current_metrics.error_count == 1
        assert aggregator.total_metrics.error_count == 1
    
    def test_add_log_entry_with_status_code(self):
        aggregator = TimeWindowAggregator(window_seconds=10.0)
        
        aggregator.add_log_entry(data={'line': 'log'}, status_code=404)
        
        assert aggregator.current_metrics.status_codes[404] == 1
        assert aggregator.total_metrics.status_codes[404] == 1
    
    def test_add_log_entry_with_response_time(self):
        aggregator = TimeWindowAggregator(window_seconds=10.0)
        
        aggregator.add_log_entry(data={'line': 'log'}, response_time=15.5)
        
        assert aggregator.current_metrics.response_times == [15.5]
        assert aggregator.total_metrics.response_times == [15.5]
    
    def test_add_log_entry_with_custom_fields(self):
        aggregator = TimeWindowAggregator(window_seconds=10.0)
        
        aggregator.add_log_entry(data={'line': 'log'}, custom_extracted={'path': '/api'})
        
        assert aggregator.current_metrics.custom_fields['path']['/api'] == 1
        assert aggregator.total_metrics.custom_fields['path']['/api'] == 1
    
    def test_flush_calls_callback(self):
        callback = Mock()
        aggregator = TimeWindowAggregator(window_seconds=10.0, on_window_complete=callback)
        
        aggregator.add_log_entry(data={'line': 'log'})
        aggregator.flush()
        
        callback.assert_called_once()
        args = callback.call_args
        assert args[0][2].total_count == 1
    
    def test_flush_with_empty_window(self):
        callback = Mock()
        aggregator = TimeWindowAggregator(window_seconds=10.0, on_window_complete=callback)
        
        aggregator.flush()
        
        callback.assert_not_called()
    
    def test_get_current_stats_empty(self):
        aggregator = TimeWindowAggregator(window_seconds=10.0)
        
        stats = aggregator.get_current_stats()
        
        assert 'current_window' in stats
        assert 'total' in stats
        assert stats['current_window']['metrics']['total_count'] == 0
    
    def test_get_current_stats_with_data(self):
        aggregator = TimeWindowAggregator(window_seconds=10.0)
        
        aggregator.add_log_entry(data={'line': 'log'}, is_error=True, status_code=500)
        
        stats = aggregator.get_current_stats()
        
        assert stats['current_window']['metrics']['total_count'] == 1
        assert stats['current_window']['metrics']['error_count'] == 1
        assert stats['current_window']['metrics']['status_codes'] == {500: 1}
