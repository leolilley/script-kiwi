"""
Pre-flight validation utilities.

Run checks before expensive operations to fail fast:
- Credential validation
- Input validation
- Cost estimation
- Rate limit checking
"""

import os
import re
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def check_credentials(required_keys: List[str]) -> Dict:
    """
    Verify required environment variables/credentials exist.
    
    Args:
        required_keys: List of environment variable names to check
        
    Returns:
        {"status": "pass"} or {"status": "fail", "missing": [...]}
        
    Example:
        result = check_credentials(["APIFY_API_TOKEN", "GOOGLE_SHEETS_CREDENTIALS"])
        if result["status"] == "fail":
            print(f"Missing: {result['missing']}")
    """
    missing = [k for k in required_keys if not os.getenv(k)]
    
    if missing:
        logger.warning(f"Missing credentials: {missing}")
        return {"status": "fail", "missing": missing}
    
    logger.debug(f"All credentials present: {required_keys}")
    return {"status": "pass"}


def validate_inputs(inputs: Dict, rules: List[Dict]) -> Dict:
    """
    Validate inputs against rules.
    
    Args:
        inputs: Dictionary of input values
        rules: List of validation rules
        
    Rules format:
        {"field": "name", "required": True}
        {"field": "count", "min": 1, "max": 10000}
        {"field": "email", "pattern": r"^[\\w.-]+@[\\w.-]+\\.\\w+$"}
        {"field": "industry", "type": "string"}
        
    Returns:
        {"status": "pass"} or {"status": "fail", "errors": [...]}
        
    Example:
        rules = [
            {"field": "count", "required": True, "min": 1, "max": 10000},
            {"field": "industry", "required": True, "type": "string"}
        ]
        result = validate_inputs({"count": 500, "industry": "dentists"}, rules)
    """
    errors = []
    
    for rule in rules:
        field = rule.get("field")
        value = inputs.get(field)
        
        # Required check
        if rule.get("required") and value is None:
            errors.append(f"'{field}' is required but missing")
            continue
        
        # Skip other checks if value is None and not required
        if value is None:
            continue
        
        # Type check
        expected_type = rule.get("type")
        if expected_type:
            type_map = {"string": str, "integer": int, "float": (int, float), "boolean": bool}
            if expected_type in type_map and not isinstance(value, type_map[expected_type]):
                errors.append(f"'{field}' must be {expected_type}, got {type(value).__name__}")
        
        # Min/max check (for numbers)
        if "min" in rule and isinstance(value, (int, float)) and value < rule["min"]:
            errors.append(f"'{field}' must be >= {rule['min']}, got {value}")
        if "max" in rule and isinstance(value, (int, float)) and value > rule["max"]:
            errors.append(f"'{field}' must be <= {rule['max']}, got {value}")
        
        # Pattern check (for strings)
        if "pattern" in rule and isinstance(value, str):
            if not re.match(rule["pattern"], value):
                errors.append(f"'{field}' doesn't match required pattern: {rule['pattern']}")
        
        # Enum check
        if "enum" in rule and value not in rule["enum"]:
            errors.append(f"'{field}' must be one of {rule['enum']}, got '{value}'")
    
    if errors:
        logger.warning(f"Input validation failed: {errors}")
        return {"status": "fail", "errors": errors}
    
    logger.debug("Input validation passed")
    return {"status": "pass"}


def estimate_cost(formula: str, inputs: Dict) -> Dict:
    """
    Calculate estimated cost from formula.
    
    Args:
        formula: Cost formula using input variable names
        inputs: Dictionary of input values
        
    Returns:
        {"estimated_cost_usd": float, "formula": str}
        
    Example:
        # $0.01 per lead + $0.02 per email (assuming 40% enrichment)
        cost = estimate_cost("count * 0.01 + (count * 0.4 * 0.02)", {"count": 500})
        # Returns: {"estimated_cost_usd": 9.0, "formula": "..."}
    """
    try:
        # Safe eval with only inputs as context (no builtins)
        cost = eval(formula, {"__builtins__": {}}, inputs)
        result = {
            "estimated_cost_usd": round(float(cost), 2),
            "formula": formula,
            "inputs_used": {k: v for k, v in inputs.items() if k in formula}
        }
        logger.info(f"Cost estimate: ${result['estimated_cost_usd']}")
        return result
    except Exception as e:
        logger.error(f"Cost estimation failed: {e}")
        return {"error": str(e), "formula": formula}


def estimate_time(formula: str, inputs: Dict) -> Dict:
    """
    Calculate estimated time from formula.
    
    Args:
        formula: Time formula in seconds using input variable names
        inputs: Dictionary of input values
        
    Returns:
        {"estimated_seconds": int, "human_readable": str}
        
    Example:
        time_est = estimate_time("count * 1.5", {"count": 500})
        # Returns: {"estimated_seconds": 750, "human_readable": "12 minutes 30 seconds"}
    """
    try:
        seconds = eval(formula, {"__builtins__": {}}, inputs)
        seconds = int(seconds)
        
        # Human readable
        if seconds < 60:
            human = f"{seconds} seconds"
        elif seconds < 3600:
            mins = seconds // 60
            secs = seconds % 60
            human = f"{mins} minutes {secs} seconds" if secs else f"{mins} minutes"
        else:
            hours = seconds // 3600
            mins = (seconds % 3600) // 60
            human = f"{hours} hours {mins} minutes" if mins else f"{hours} hours"
        
        return {
            "estimated_seconds": seconds,
            "human_readable": human
        }
    except Exception as e:
        logger.error(f"Time estimation failed: {e}")
        return {"error": str(e)}


def run_preflight(
    inputs: Dict,
    required_credentials: List[str] = None,
    validation_rules: List[Dict] = None,
    cost_formula: str = None,
    cost_warn_threshold: float = None,
    cost_block_threshold: float = None,
    time_formula: str = None
) -> Dict:
    """
    Run all preflight checks.
    
    Args:
        inputs: User-provided inputs
        required_credentials: List of required env vars
        validation_rules: Input validation rules
        cost_formula: Formula for cost estimation
        cost_warn_threshold: Warn if cost exceeds this
        cost_block_threshold: Block if cost exceeds this
        time_formula: Formula for time estimation
        
    Returns:
        {
            "pass": bool,
            "checks": {
                "credentials": {...},
                "inputs": {...},
                "cost": {...},
                "time": {...}
            },
            "warnings": [...],
            "blockers": [...]
        }
        
    Example:
        result = run_preflight(
            inputs={"count": 500, "industry": "dentists"},
            required_credentials=["APIFY_API_TOKEN"],
            validation_rules=[{"field": "count", "min": 1, "max": 10000}],
            cost_formula="count * 0.03",
            cost_warn_threshold=10,
            cost_block_threshold=100
        )
        
        if not result["pass"]:
            print(f"Blockers: {result['blockers']}")
    """
    checks = {}
    warnings = []
    blockers = []
    
    # Credential check
    if required_credentials:
        cred_result = check_credentials(required_credentials)
        checks["credentials"] = cred_result
        if cred_result["status"] == "fail":
            blockers.append(f"Missing credentials: {cred_result['missing']}")
    
    # Input validation
    if validation_rules:
        input_result = validate_inputs(inputs, validation_rules)
        checks["inputs"] = input_result
        if input_result["status"] == "fail":
            blockers.extend(input_result["errors"])
    
    # Cost estimation
    if cost_formula:
        cost_result = estimate_cost(cost_formula, inputs)
        checks["cost"] = cost_result
        
        if "estimated_cost_usd" in cost_result:
            cost = cost_result["estimated_cost_usd"]
            if cost_block_threshold and cost > cost_block_threshold:
                blockers.append(f"Estimated cost ${cost} exceeds block threshold ${cost_block_threshold}")
            elif cost_warn_threshold and cost > cost_warn_threshold:
                warnings.append(f"Estimated cost ${cost} exceeds warning threshold ${cost_warn_threshold}")
    
    # Time estimation
    if time_formula:
        time_result = estimate_time(time_formula, inputs)
        checks["time"] = time_result
    
    # Summary
    all_pass = len(blockers) == 0
    
    result = {
        "pass": all_pass,
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers
    }
    
    if all_pass:
        logger.info("Preflight checks passed")
    else:
        logger.warning(f"Preflight checks failed: {blockers}")
    
    return result

