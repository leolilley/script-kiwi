"""
Run history and analytics utilities for Script Kiwi.

Logs script executions to:
1. User space: ~/.script-kiwi/.runs/history.jsonl (matches Context Kiwi pattern)
2. Supabase: executions table (for remote analytics)
"""

import json
import logging
import os
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logger = logging.getLogger(__name__)


def _get_user_home() -> Path:
    """Get user home directory path."""
    return Path.home()


def _get_script_kiwi_home() -> Path:
    """Get script-kiwi home directory path from SCRIPT_KIWI_HOME env var or default to ~/.script-kiwi."""
    script_kiwi_home = os.getenv("SCRIPT_KIWI_HOME")
    if script_kiwi_home:
        return Path(script_kiwi_home)
    return Path.home() / ".script-kiwi"


def _get_history_file() -> Path:
    """Get path to history file in user space (~/.script-kiwi/.runs/history.jsonl)."""
    return _get_script_kiwi_home() / ".runs" / "history.jsonl"


def _ensure_runs_dir(history_file: Path):
    """Ensure runs directory exists."""
    history_file.parent.mkdir(parents=True, exist_ok=True)


def _get_supabase_client() -> Optional[Client]:
    """Get Supabase client for executions table."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    
    if not url or not key:
        return None
    
    return create_client(url, key)


def log_execution(
    script_name: str,
    status: str,
    duration_sec: float,
    inputs: Dict,
    outputs: Optional[Dict] = None,
    error: Optional[str] = None,
    cost_usd: Optional[float] = None,
    script_version: Optional[str] = None,
    rows_processed: Optional[int] = None,
    api_calls_made: Optional[int] = None,
    project: Optional[str] = None,
    execution_id: Optional[str] = None
) -> Dict:
    """
    Log a script execution to both user space and Supabase.
    
    Logs to:
    1. User space: ~/.script-kiwi/.runs/history.jsonl (matches Context Kiwi pattern)
    2. Supabase: executions table (for remote analytics)
    
    Args:
        script_name: Name of the script
        status: "success", "error", "timeout", "cancelled", "partial_success"
        duration_sec: How long the execution took
        inputs: Input parameters (will be summarized for local log)
        outputs: Output data (will be summarized for local log)
        error: Error message if failed
        cost_usd: Estimated or actual cost
        script_version: Script version used
        rows_processed: Number of rows/items processed
        api_calls_made: Number of API calls made
        project: Project name/path this was run in
        
    Returns:
        The logged execution entry with execution_id
    
    Example:
        log_execution(
            script_name="google_maps_leads",
            status="success",
            duration_sec=180,
            inputs={"search_term": "dentist", "location": "Texas", "count": 500},
            outputs={"lead_count": 500, "email_rate": 0.62},
            cost_usd=15.00,
            script_version="1.2.0",
            rows_processed=500
        )
    """
    def summarize(data, max_items=5):
        if not data:
            return None
        if isinstance(data, dict):
            return {k: v for i, (k, v) in enumerate(data.items()) if i < max_items}
        return data
    
    history_file = _get_history_file()
    _ensure_runs_dir(history_file)
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "execution_id": execution_id,
        "script": script_name,
        "status": status,
        "duration_sec": round(duration_sec, 2),
        "project": project,
        "inputs": summarize(inputs),
        "outputs": summarize(outputs),
        "error": error,
        "cost_usd": round(cost_usd, 4) if cost_usd else None,
        "script_version": script_version,
        "rows_processed": rows_processed,
        "api_calls_made": api_calls_made,
    }
    
    entry = {k: v for k, v in entry.items() if v is not None}
    
    try:
        with open(history_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
        logger.debug(f"Logged to user space: {script_name} -> {status}")
    except Exception as e:
        logger.error(f"Failed to log to user space: {e}")
    
    client = _get_supabase_client()
    supabase_execution_id = None
    
    if client:
        try:
            # Build execution data with all fields
            execution_data = {
                "script_name": script_name,
                "script_version": script_version,
                "status": status,
                "duration_sec": round(duration_sec, 3) if duration_sec is not None else None,
                "cost_usd": round(cost_usd, 4) if cost_usd else None,
                "error": error,
                "rows_processed": rows_processed,
                "api_calls_made": api_calls_made,
            }
            
            # Add inputs/outputs if provided
            if inputs is not None:
                execution_data["inputs"] = inputs
            if outputs is not None:
                execution_data["outputs"] = outputs
            
            # Remove None values
            execution_data = {k: v for k, v in execution_data.items() if v is not None}
            
            # Try to insert
            try:
                result = client.table("executions").insert(execution_data).execute()
                supabase_execution_id = result.data[0]["id"] if result.data else None
                logger.debug(f"Logged to Supabase: {script_name} -> {status}")
            except Exception as insert_error:
                # Check if it's a schema error about inputs/outputs columns
                error_str = str(insert_error)
                if "PGRST204" in error_str and ("inputs" in error_str or "outputs" in error_str):
                    # Retry without inputs/outputs (schema may not have these columns)
                    logger.debug(f"Schema error with inputs/outputs, retrying without them: {insert_error}")
                    execution_data_minimal = {
                        "script_name": script_name,
                        "script_version": script_version,
                        "status": status,
                        "duration_sec": round(duration_sec, 3) if duration_sec is not None else None,
                        "cost_usd": round(cost_usd, 4) if cost_usd else None,
                        "error": error,
                        "rows_processed": rows_processed,
                        "api_calls_made": api_calls_made,
                    }
                    execution_data_minimal = {k: v for k, v in execution_data_minimal.items() if v is not None}
                    result = client.table("executions").insert(execution_data_minimal).execute()
                    supabase_execution_id = result.data[0]["id"] if result.data else None
                    logger.debug(f"Logged to Supabase (without inputs/outputs): {script_name} -> {status}")
                else:
                    # Re-raise other errors
                    raise
        except Exception as e:
            # Log but don't fail - local logging still works
            error_str = str(e)
            if "PGRST204" in error_str or "column" in error_str.lower() or "schema cache" in error_str.lower():
                logger.warning(f"Supabase schema issue - table may need migration: {e}")
                logger.debug("Continuing without Supabase logging - local logging still works")
            else:
                logger.warning(f"Failed to log to Supabase: {e}")
    else:
        logger.debug("Supabase not configured, skipping remote log")
    
    # Return execution info
    return {
        "execution_id": execution_id or supabase_execution_id,
        "script_name": script_name,
        "status": status,
        "duration_sec": duration_sec,
        "cost_usd": cost_usd
    }


def log_execution_start(
    script_name: str,
    execution_id: str,
    inputs: Dict,
    script_version: Optional[str] = None,
    project: Optional[str] = None
) -> None:
    """
    Log script execution start to user space.
    
    This allows tracking long-running scripts in real-time.
    Writes to ~/.script-kiwi/.runs/history.jsonl immediately.
    
    Args:
        script_name: Name of the script
        execution_id: Unique execution ID
        inputs: Input parameters (will be summarized)
        script_version: Script version
        project: Project path
    """
    def summarize(data, max_items=5):
        if not data:
            return None
        if isinstance(data, dict):
            return {k: v for i, (k, v) in enumerate(data.items()) if i < max_items}
        return data
    
    history_file = _get_history_file()
    _ensure_runs_dir(history_file)
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "execution_id": execution_id,
        "script": script_name,
        "status": "running",
        "project": project,
        "inputs": summarize(inputs),
        "script_version": script_version,
    }
    
    entry = {k: v for k, v in entry.items() if v is not None}
    
    try:
        with open(history_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
        logger.debug(f"Logged execution start to user space: {script_name} (ID: {execution_id})")
    except Exception as e:
        logger.error(f"Failed to log execution start to user space: {e}")


def get_run_history(
    days: int = 30,
    script: Optional[str] = None,
    project: Optional[str] = None
) -> list:
    """
    Load run history from the last N days.
    
    Args:
        days: Number of days of history to load
        script: Optional filter by script name
        project: Optional filter by project
        
    Returns:
        List of run entries, most recent first
    """
    history_file = _get_history_file()
    if not history_file.exists():
        return []
    
    cutoff = datetime.now() - timedelta(days=days)
    runs = []
    
    with open(history_file, 'r') as f:
        for line in f:
            if line.strip():
                run = json.loads(line)
                run_time = datetime.fromisoformat(run['timestamp'])
                
                if run_time > cutoff:
                    if script and run.get('script') != script:
                        continue
                    if project and run.get('project') != project:
                        continue
                    runs.append(run)
    
    return sorted(runs, key=lambda x: x['timestamp'], reverse=True)


def script_stats(
    days: int = 30,
    project: Optional[str] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Calculate success rate and performance stats per script.
    
    Args:
        days: Number of days to analyze
        project: Optional filter by project
        
    Returns:
        Dictionary of script stats
    """
    runs = get_run_history(days=days, project=project)
    stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        'success': 0,
        'error': 0,
        'partial': 0,
        'total_duration': 0.0,
        'errors': []
    })
    
    for run in runs:
        script = run.get('script', 'unknown')
        stats[script]['total_duration'] += run.get('duration_sec', 0)
        
        if run['status'] == 'success':
            stats[script]['success'] += 1
        elif run['status'] == 'partial_success':
            stats[script]['partial'] += 1
        else:
            stats[script]['error'] += 1
            if run.get('error'):
                stats[script]['errors'].append(run['error'])
    
    result = {}
    for script, s in stats.items():
        total = s['success'] + s['error'] + s['partial']
        result[script] = {
            'total_runs': total,
            'success_rate': s['success'] / total if total > 0 else 0,
            'partial_rate': s['partial'] / total if total > 0 else 0,
            'error_rate': s['error'] / total if total > 0 else 0,
            'avg_duration_sec': s['total_duration'] / total if total > 0 else 0,
            'common_errors': list(set(s['errors']))[:3]
        }
    
    return result

