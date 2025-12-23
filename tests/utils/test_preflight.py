"""
Tests for preflight utilities.
"""

import os
from unittest.mock import patch

from script_kiwi.utils.shared.preflight import (
    check_credentials,
    validate_inputs,
    estimate_cost,
    estimate_time,
    run_preflight
)


class TestCheckCredentials:
    """Tests for check_credentials function."""
    
    def test_check_credentials_all_present(self):
        """Test when all credentials are present."""
        with patch.dict(os.environ, {'API_KEY': 'test-key', 'API_SECRET': 'test-secret'}):
            result = check_credentials(['API_KEY', 'API_SECRET'])
            
            assert result['status'] == 'pass'
            assert 'missing' not in result
    
    def test_check_credentials_some_missing(self):
        """Test when some credentials are missing."""
        with patch.dict(os.environ, {'API_KEY': 'test-key'}, clear=True):
            result = check_credentials(['API_KEY', 'API_SECRET', 'API_TOKEN'])
            
            assert result['status'] == 'fail'
            assert 'missing' in result
            assert 'API_SECRET' in result['missing']
            assert 'API_TOKEN' in result['missing']
            assert 'API_KEY' not in result['missing']
    
    def test_check_credentials_all_missing(self):
        """Test when all credentials are missing."""
        with patch.dict(os.environ, {}, clear=True):
            result = check_credentials(['API_KEY', 'API_SECRET'])
            
            assert result['status'] == 'fail'
            assert len(result['missing']) == 2
            assert 'API_KEY' in result['missing']
            assert 'API_SECRET' in result['missing']
    
    def test_check_credentials_empty_list(self):
        """Test with empty credentials list."""
        result = check_credentials([])
        
        assert result['status'] == 'pass'


class TestValidateInputs:
    """Tests for validate_inputs function."""
    
    def test_validate_inputs_all_pass(self):
        """Test validation when all inputs pass."""
        inputs = {'name': 'Test', 'count': 5, 'email': 'test@example.com'}
        rules = [
            {'field': 'name', 'required': True, 'type': 'string'},
            {'field': 'count', 'required': True, 'type': 'integer', 'min': 1, 'max': 10},
            {'field': 'email', 'required': True, 'type': 'string', 'pattern': r'^[\w.-]+@[\w.-]+\.\w+$'}
        ]
        
        result = validate_inputs(inputs, rules)
        
        assert result['status'] == 'pass'
        assert 'errors' not in result
    
    def test_validate_inputs_missing_required(self):
        """Test validation when required field is missing."""
        inputs = {'name': 'Test'}
        rules = [
            {'field': 'name', 'required': True},
            {'field': 'count', 'required': True}
        ]
        
        result = validate_inputs(inputs, rules)
        
        assert result['status'] == 'fail'
        assert 'errors' in result
        assert any("'count' is required" in err for err in result['errors'])
    
    def test_validate_inputs_type_mismatch(self):
        """Test validation when type doesn't match."""
        inputs = {'count': 'not-a-number'}
        rules = [
            {'field': 'count', 'type': 'integer'}
        ]
        
        result = validate_inputs(inputs, rules)
        
        assert result['status'] == 'fail'
        assert any("must be integer" in err for err in result['errors'])
    
    def test_validate_inputs_min_max(self):
        """Test min/max validation."""
        inputs = {'count': 15}
        rules = [
            {'field': 'count', 'type': 'integer', 'min': 1, 'max': 10}
        ]
        
        result = validate_inputs(inputs, rules)
        
        assert result['status'] == 'fail'
        assert any("must be <=" in err for err in result['errors'])


class TestEstimateCost:
    """Tests for estimate_cost function."""
    
    def test_estimate_cost_simple(self):
        """Test simple cost estimation."""
        result = estimate_cost('count * 0.01', {'count': 100})
        
        assert 'estimated_cost_usd' in result
        assert result['estimated_cost_usd'] == 1.0
        assert result['formula'] == 'count * 0.01'
    
    def test_estimate_cost_complex(self):
        """Test complex cost estimation."""
        result = estimate_cost('count * 0.01 + (count * 0.4 * 0.02)', {'count': 500})
        
        assert 'estimated_cost_usd' in result
        assert result['estimated_cost_usd'] == 9.0  # 500 * 0.01 + 500 * 0.4 * 0.02
    
    def test_estimate_cost_invalid_formula(self):
        """Test cost estimation with invalid formula."""
        result = estimate_cost('invalid * formula', {'count': 100})
        
        assert 'error' in result
        assert 'formula' in result


class TestEstimateTime:
    """Tests for estimate_time function."""
    
    def test_estimate_time_seconds(self):
        """Test time estimation in seconds."""
        result = estimate_time('count * 1.5', {'count': 10})
        
        assert 'estimated_seconds' in result
        assert result['estimated_seconds'] == 15
        assert 'human_readable' in result
        assert 'seconds' in result['human_readable']
    
    def test_estimate_time_minutes(self):
        """Test time estimation in minutes."""
        result = estimate_time('count * 6', {'count': 10})
        
        assert result['estimated_seconds'] == 60
        assert 'minute' in result['human_readable'].lower()


class TestRunPreflight:
    """Tests for run_preflight function."""
    
    def test_run_preflight_all_pass(self):
        """Test preflight when all checks pass."""
        with patch.dict(os.environ, {'API_KEY': 'test-key'}):
            result = run_preflight(
                inputs={'count': 5},
                required_credentials=['API_KEY'],
                validation_rules=[{'field': 'count', 'type': 'integer', 'min': 1}]
            )
            
            assert result['pass'] is True
            assert len(result['blockers']) == 0
            assert 'checks' in result
    
    def test_run_preflight_credential_fail(self):
        """Test preflight when credentials are missing."""
        with patch.dict(os.environ, {}, clear=True):
            result = run_preflight(
                inputs={'count': 5},
                required_credentials=['API_KEY', 'API_SECRET']
            )
            
            assert result['pass'] is False
            assert len(result['blockers']) > 0
            assert any('Missing credentials' in blocker for blocker in result['blockers'])
    
    def test_run_preflight_validation_fail(self):
        """Test preflight when validation fails."""
        result = run_preflight(
            inputs={'count': -5},
            validation_rules=[{'field': 'count', 'type': 'integer', 'min': 1}]
        )
        
        assert result['pass'] is False
        assert len(result['blockers']) > 0
    
    def test_run_preflight_cost_warning(self):
        """Test preflight with cost warning threshold."""
        result = run_preflight(
            inputs={'count': 1000},
            cost_formula='count * 0.01',
            cost_warn_threshold=5.0
        )
        
        assert result['pass'] is True  # Should still pass, just warn
        assert len(result['warnings']) > 0
        assert any('cost' in warning.lower() for warning in result['warnings'])

