import re
import json
from typing import Dict, Any, List, Optional, Callable, Pattern
from dataclasses import dataclass
from enum import Enum


class FieldType(Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    TIMESTAMP = "timestamp"


@dataclass
class ExtractionRule:
    name: str
    pattern: str
    group: int = 1
    field_type: FieldType = FieldType.STRING
    is_error_indicator: bool = False
    is_status_code: bool = False
    is_response_time: bool = False
    is_timestamp: bool = False
    compiled_pattern: Optional[Pattern] = None
    
    def __post_init__(self):
        self.compiled_pattern = re.compile(self.pattern)
    
    def extract(self, line: str) -> Any:
        match = self.compiled_pattern.search(line)
        if not match:
            return None
        
        try:
            value = match.group(self.group)
        except IndexError:
            return None
        
        if value is None:
            return None
        
        return self._convert_type(value)
    
    def _convert_type(self, value: str) -> Any:
        if self.field_type == FieldType.INTEGER:
            try:
                return int(value)
            except (ValueError, TypeError):
                return None
        elif self.field_type == FieldType.FLOAT:
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        return value


class LogExtractor:
    def __init__(self, rules: Optional[List[ExtractionRule]] = None):
        self.rules: List[ExtractionRule] = []
        if rules:
            self.rules = rules
    
    def add_rule(self, rule: ExtractionRule):
        self.rules.append(rule)
    
    def extract(self, line: str) -> Dict[str, Any]:
        result = {
            'custom_fields': {},
            'is_error': False,
            'status_code': None,
            'response_time': None,
            'timestamp': None
        }
        
        for rule in self.rules:
            value = rule.extract(line)
            
            if value is None:
                continue
            
            if rule.is_error_indicator:
                result['is_error'] = True
                if rule.name not in result['custom_fields']:
                    result['custom_fields'][rule.name] = value
            elif rule.is_status_code:
                if result['status_code'] is None:
                    result['status_code'] = value
            elif rule.is_response_time:
                if result['response_time'] is None:
                    result['response_time'] = value
            elif rule.is_timestamp:
                if result['timestamp'] is None:
                    result['timestamp'] = value
            else:
                if rule.name not in result['custom_fields']:
                    result['custom_fields'][rule.name] = value
        
        return result
    
    @classmethod
    def from_yaml_config(cls, config: Dict[str, Any]) -> 'LogExtractor':
        rules = []
        for rule_config in config.get('rules', []):
            field_type = FieldType(rule_config.get('type', 'string'))
            rule = ExtractionRule(
                name=rule_config['name'],
                pattern=rule_config['pattern'],
                group=rule_config.get('group', 1),
                field_type=field_type,
                is_error_indicator=rule_config.get('is_error_indicator', False),
                is_status_code=rule_config.get('is_status_code', False),
                is_response_time=rule_config.get('is_response_time', False),
                is_timestamp=rule_config.get('is_timestamp', False)
            )
            rules.append(rule)
        return cls(rules=rules)
    
    @classmethod
    def create_default(cls) -> 'LogExtractor':
        default_rules = [
            ExtractionRule(
                name='error',
                pattern=r'(ERROR|error|Error|Exception|exception|Exception)',
                is_error_indicator=True
            ),
            ExtractionRule(
                name='status_code',
                pattern=r'HTTP/\d\.\d\s+(\d{3})',
                field_type=FieldType.INTEGER,
                is_status_code=True
            ),
            ExtractionRule(
                name='status_code',
                pattern=r'\sstatus[=:]\s*(\d{3})',
                field_type=FieldType.INTEGER,
                is_status_code=True
            ),
            ExtractionRule(
                name='response_time',
                pattern=r'(\d+(?:\.\d+)?)\s*ms',
                field_type=FieldType.FLOAT,
                is_response_time=True
            ),
            ExtractionRule(
                name='response_time',
                pattern=r'response[_\s]?time[=:]\s*(\d+(?:\.\d+)?)',
                field_type=FieldType.FLOAT,
                is_response_time=True
            ),
            ExtractionRule(
                name='method',
                pattern=r'(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)',
                field_type=FieldType.STRING
            ),
            ExtractionRule(
                name='path',
                pattern=r'\"(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(\S+)',
                group=2
            ),
            ExtractionRule(
                name='path',
                pattern=r'(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(\S+)',
                group=2
            ),
            ExtractionRule(
                name='user_agent',
                pattern=r'\"[^\"]*\"\s+\"([^\"]+)\"',
            ),
        ]
        return cls(rules=default_rules)
