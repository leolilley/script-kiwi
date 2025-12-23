"""
Execution Logger

Logs script executions to Supabase executions table.
"""

import os
import uuid
from typing import Dict, Any, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


class ExecutionLogger:
    """Log script executions to Supabase."""
    
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_SECRET_KEY")
        
        if not self.url or not self.key:
            self.client = None
        else:
            self.client = create_client(self.url, self.key)
    
    async def start_execution(
        self,
        script_name: str,
        script_version: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Start execution logging.
        
        Returns:
            execution_id (UUID string)
        """
        return str(uuid.uuid4())
    
    async def complete_execution(
        self,
        execution_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        duration_sec: Optional[float] = None,
        cost_usd: Optional[float] = None
    ):
        """
        Complete execution logging.
        
        Args:
            execution_id: Execution ID from start_execution
            status: 'success', 'error', 'timeout', 'cancelled', 'partial_success'
            result: Execution result data
            error: Error message if failed
            duration_sec: Execution duration
            cost_usd: Cost in USD
        """
        if not self.client:
            print(f"Execution {execution_id}: {status} (Supabase not configured)")
            return
        
        try:
            execution_data = {
                "id": execution_id,
                "script_name": result.get("script_name") if result else None,
                "script_version": result.get("version") if result else None,
                "status": status,
                "duration_sec": duration_sec,
                "cost_usd": cost_usd,
                "inputs": result.get("inputs") if result else None,
                "outputs": result.get("data") if result else None,
                "error": error,
                "rows_processed": result.get("metadata", {}).get("rows_processed") if result else None,
            }
            
            self.client.table("executions").insert(execution_data).execute()
        except Exception as e:
            print(f"Error logging execution: {e}")

