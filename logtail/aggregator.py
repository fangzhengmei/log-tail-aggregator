import time
from collections import defaultdict
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class Metrics:
    total_count: int = 0
    error_count: int = 0
    status_codes: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    response_times: List[float] = field(default_factory=list)
    custom_fields: Dict[str, Dict[Any, int]] = field(default_factory=dict)
    
    def update(self, data: Dict[str, Any], is_error: bool = False, 
               status_code: Optional[int] = None, response_time: Optional[float] = None,
               custom_extracted: Optional[Dict[str, Any]] = None):
        self.total_count += 1
        
        if is_error:
            self.error_count += 1
        
        if status_code is not None:
            self.status_codes[status_code] += 1
        
        if response_time is not None:
            self.response_times.append(response_time)
        
        if custom_extracted:
            for field_name, value in custom_extracted.items():
                if field_name not in self.custom_fields:
                    self.custom_fields[field_name] = defaultdict(int)
                self.custom_fields[field_name][value] += 1
    
    def get_qps(self, duration_seconds: float) -> float:
        if duration_seconds <= 0:
            return 0.0
        return self.total_count / duration_seconds
    
    def get_error_rate(self) -> float:
        if self.total_count == 0:
            return 0.0
        return (self.error_count / self.total_count) * 100
    
    def get_avg_response_time(self) -> Optional[float]:
        if not self.response_times:
            return None
        return sum(self.response_times) / len(self.response_times)
    
    def get_p95_response_time(self) -> Optional[float]:
        if not self.response_times:
            return None
        return self._calculate_percentile(self.response_times, 95.0)
    
    def _calculate_percentile(self, data: List[float], percentile: float) -> float:
        """
        使用线性插值法计算百分位（NumPy/Excel 标准方法）
        
        公式：
        - n = 样本数
        - i = (percentile / 100) * (n - 1)
        - k = floor(i), d = i - k (小数部分)
        - 结果 = sorted[k] + d * (sorted[k+1] - sorted[k])
        
        例如：10 个样本，95 百分位
        - i = 0.95 * 9 = 8.55
        - k = 8, d = 0.55
        - 结果 = sorted[8] + 0.55 * (sorted[9] - sorted[8])
        
        这样避免了小样本时直接取最大值的偏差
        """
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        n = len(sorted_data)
        
        if n == 1:
            return sorted_data[0]
        
        if percentile <= 0:
            return sorted_data[0]
        if percentile >= 100:
            return sorted_data[-1]
        
        i = (percentile / 100.0) * (n - 1)
        k = int(i)
        d = i - k
        
        if k >= n - 1:
            return sorted_data[-1]
        
        if d == 0:
            return sorted_data[k]
        
        return sorted_data[k] + d * (sorted_data[k + 1] - sorted_data[k])
    
    def to_dict(self, duration_seconds: float) -> Dict[str, Any]:
        result = {
            'total_count': self.total_count,
            'error_count': self.error_count,
            'qps': self.get_qps(duration_seconds),
            'error_rate': self.get_error_rate(),
        }
        
        if self.status_codes:
            result['status_codes'] = dict(self.status_codes)
        
        if self.response_times:
            result['avg_response_time'] = self.get_avg_response_time()
            result['p95_response_time'] = self.get_p95_response_time()
        
        if self.custom_fields:
            result['custom_fields'] = {k: dict(v) for k, v in self.custom_fields.items()}
        
        return result


class TimeWindowAggregator:
    def __init__(self, window_seconds: float = 10.0, 
                 on_window_complete: Optional[Callable[[float, float, Metrics], None]] = None):
        self.window_seconds = window_seconds
        self.on_window_complete = on_window_complete
        self.current_window_start: float = time.time()
        self.current_metrics = Metrics()
        self.total_metrics = Metrics()
    
    def add_log_entry(self, data: Dict[str, Any], is_error: bool = False,
                      status_code: Optional[int] = None, response_time: Optional[float] = None,
                      custom_extracted: Optional[Dict[str, Any]] = None):
        now = time.time()
        
        if now - self.current_window_start >= self.window_seconds:
            self._complete_window()
        
        self.current_metrics.update(
            data=data,
            is_error=is_error,
            status_code=status_code,
            response_time=response_time,
            custom_extracted=custom_extracted
        )
        
        self.total_metrics.update(
            data=data,
            is_error=is_error,
            status_code=status_code,
            response_time=response_time,
            custom_extracted=custom_extracted
        )
    
    def _complete_window(self):
        window_end = time.time()
        window_duration = window_end - self.current_window_start
        
        if self.on_window_complete:
            self.on_window_complete(
                self.current_window_start,
                window_end,
                self.current_metrics
            )
        
        self.current_window_start = window_end
        self.current_metrics = Metrics()
    
    def flush(self):
        if self.current_metrics.total_count > 0:
            self._complete_window()
    
    def get_current_stats(self) -> Dict[str, Any]:
        now = time.time()
        current_duration = now - self.current_window_start
        
        return {
            'current_window': {
                'start_time': self.current_window_start,
                'duration_seconds': current_duration,
                'metrics': self.current_metrics.to_dict(current_duration)
            },
            'total': {
                'start_time': self.current_window_start - self.window_seconds if self.total_metrics.total_count > 0 else None,
                'end_time': now,
                'metrics': self.total_metrics.to_dict(
                    (now - (self.current_window_start - self.window_seconds)) 
                    if self.total_metrics.total_count > 0 else 0
                )
            }
        }
