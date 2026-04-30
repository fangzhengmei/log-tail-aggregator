import pytest

from logtail.extractor import LogExtractor, ExtractionRule, FieldType


class TestExtractionRule:
    def test_basic_string_extraction(self):
        rule = ExtractionRule(
            name='method',
            pattern=r'(GET|POST|PUT|DELETE)',
            field_type=FieldType.STRING
        )
        
        result = rule.extract('GET /api/users HTTP/1.1')
        assert result == 'GET'
    
    def test_integer_extraction(self):
        rule = ExtractionRule(
            name='status',
            pattern=r'HTTP/\d\.\d\s+(\d{3})',
            field_type=FieldType.INTEGER
        )
        
        result = rule.extract('GET /api HTTP/1.1 200 OK')
        assert result == 200
        assert isinstance(result, int)
    
    def test_float_extraction(self):
        rule = ExtractionRule(
            name='rt',
            pattern=r'(\d+\.\d+)\s*ms',
            field_type=FieldType.FLOAT
        )
        
        result = rule.extract('Request completed in 123.45 ms')
        assert result == 123.45
        assert isinstance(result, float)
    
    def test_custom_group(self):
        rule = ExtractionRule(
            name='path',
            pattern=r'GET\s+(\S+)\s+HTTP',
            group=1
        )
        
        result = rule.extract('GET /api/users HTTP/1.1')
        assert result == '/api/users'
    
    def test_group_2(self):
        rule = ExtractionRule(
            name='path',
            pattern=r'(GET|POST)\s+(\S+)',
            group=2
        )
        
        result = rule.extract('POST /api/create')
        assert result == '/api/create'
    
    def test_no_match_returns_none(self):
        rule = ExtractionRule(
            name='status',
            pattern=r'HTTP/\d\.\d\s+(\d{3})'
        )
        
        result = rule.extract('This is not a HTTP log')
        assert result is None
    
    def test_invalid_group_index(self):
        rule = ExtractionRule(
            name='test',
            pattern=r'(GET)',
            group=2
        )
        
        result = rule.extract('GET /api')
        assert result is None
    
    def test_invalid_integer(self):
        rule = ExtractionRule(
            name='num',
            pattern=r'(\w+)',
            field_type=FieldType.INTEGER
        )
        
        result = rule.extract('not_a_number')
        assert result is None
    
    def test_invalid_float(self):
        rule = ExtractionRule(
            name='num',
            pattern=r'(\w+)',
            field_type=FieldType.FLOAT
        )
        
        result = rule.extract('not_a_float')
        assert result is None


class TestLogExtractor:
    def test_empty_extractor(self):
        extractor = LogExtractor()
        
        result = extractor.extract('Some log line')
        
        assert result['custom_fields'] == {}
        assert result['is_error'] == False
        assert result['status_code'] is None
        assert result['response_time'] is None
    
    def test_add_rule(self):
        extractor = LogExtractor()
        rule = ExtractionRule(name='test', pattern=r'(test)')
        extractor.add_rule(rule)
        
        result = extractor.extract('this is a test')
        
        assert result['custom_fields']['test'] == 'test'
    
    def test_multiple_rules(self):
        rules = [
            ExtractionRule(name='method', pattern=r'(GET|POST)'),
            ExtractionRule(name='status', pattern=r'status=(\d+)', field_type=FieldType.INTEGER),
        ]
        extractor = LogExtractor(rules=rules)
        
        result = extractor.extract('GET /api status=200')
        
        assert result['custom_fields']['method'] == 'GET'
        assert result['custom_fields']['status'] == 200
    
    def test_error_indicator_rule(self):
        rules = [
            ExtractionRule(
                name='error',
                pattern=r'(ERROR)',
                is_error_indicator=True
            )
        ]
        extractor = LogExtractor(rules=rules)
        
        result = extractor.extract('ERROR: Something went wrong')
        
        assert result['is_error'] == True
        assert result['custom_fields']['error'] == 'ERROR'
    
    def test_status_code_rule(self):
        rules = [
            ExtractionRule(
                name='status',
                pattern=r'(\d{3})',
                field_type=FieldType.INTEGER,
                is_status_code=True
            )
        ]
        extractor = LogExtractor(rules=rules)
        
        result = extractor.extract('Response: 404')
        
        assert result['status_code'] == 404
    
    def test_response_time_rule(self):
        rules = [
            ExtractionRule(
                name='rt',
                pattern=r'(\d+\.?\d*)',
                field_type=FieldType.FLOAT,
                is_response_time=True
            )
        ]
        extractor = LogExtractor(rules=rules)
        
        result = extractor.extract('Time: 123.45')
        
        assert result['response_time'] == 123.45
    
    def test_default_extractor_basic(self):
        extractor = LogExtractor.create_default()
        
        result = extractor.extract('GET /api/users HTTP/1.1 200 OK')
        
        assert result['custom_fields']['method'] == 'GET'
        assert result['custom_fields']['path'] == '/api/users'
        assert result['status_code'] == 200
    
    def test_default_extractor_error(self):
        extractor = LogExtractor.create_default()
        
        result = extractor.extract('ERROR: Database connection failed')
        
        assert result['is_error'] == True
    
    def test_default_extractor_response_time(self):
        extractor = LogExtractor.create_default()
        
        result = extractor.extract('Request completed in 45.67 ms')
        
        assert result['response_time'] == 45.67
    
    def test_from_yaml_config(self):
        config = {
            'rules': [
                {
                    'name': 'method',
                    'pattern': r'(GET|POST|PUT|DELETE)',
                    'type': 'string'
                },
                {
                    'name': 'status_code',
                    'pattern': r'HTTP/\d\.\d\s+(\d{3})',
                    'type': 'integer',
                    'is_status_code': True
                }
            ]
        }
        
        extractor = LogExtractor.from_yaml_config(config)
        
        result = extractor.extract('POST /api HTTP/1.1 201 Created')
        
        assert result['custom_fields']['method'] == 'POST'
        assert result['status_code'] == 201
    
    def test_yaml_config_with_response_time(self):
        config = {
            'rules': [
                {
                    'name': 'rt',
                    'pattern': r'response_time=(\d+\.?\d*)',
                    'type': 'float',
                    'is_response_time': True
                }
            ]
        }
        
        extractor = LogExtractor.from_yaml_config(config)
        
        result = extractor.extract('Request response_time=123.5')
        
        assert result['response_time'] == 123.5
    
    def test_yaml_config_with_error_indicator(self):
        config = {
            'rules': [
                {
                    'name': 'error',
                    'pattern': r'(Exception|Error)',
                    'is_error_indicator': True
                }
            ]
        }
        
        extractor = LogExtractor.from_yaml_config(config)
        
        result = extractor.extract('NullPointerException occurred')
        
        assert result['is_error'] == True
