#!/usr/bin/env python3
"""
Cost tracking for API usage across directives.

Tracks token usage and calculates costs based on provider pricing.
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Provider pricing (per 1M tokens) - update as needed
PRICING = {
    "openrouter": {
        "anthropic/claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
        "openai/gpt-4": {"input": 30.0, "output": 60.0},
        "openai/gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "openai/gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
        "default": {"input": 1.0, "output": 3.0}
    },
    "openai": {
        "gpt-4": {"input": 30.0, "output": 60.0},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
        "default": {"input": 1.0, "output": 3.0}
    },
    "anthropic": {
        "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
        "claude-3-opus-20240229": {"input": 15.0, "output": 75.0},
        "claude-3-sonnet-20240229": {"input": 3.0, "output": 15.0},
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
        "default": {"input": 3.0, "output": 15.0}
    }
}

# Embedding pricing
EMBEDDING_PRICING = {
    "openrouter": {
        "openai/text-embedding-3-small": 0.02,
        "openai/text-embedding-3-large": 0.13,
        "default": 0.02
    },
    "openai": {
        "text-embedding-3-small": 0.02,
        "text-embedding-3-large": 0.13,
        "default": 0.02
    }
}


def calculate_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int = 0,
    is_embedding: bool = False
) -> float:
    """
    Calculate cost for API usage.
    
    Args:
        provider: LLM provider (openrouter, openai, anthropic)
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        is_embedding: Whether this is an embedding call
        
    Returns:
        Cost in USD
    """
    if is_embedding:
        pricing = EMBEDDING_PRICING.get(provider, {})
        price_per_million = pricing.get(model, pricing.get("default", 0.02))
        return (input_tokens / 1_000_000) * price_per_million
    
    pricing = PRICING.get(provider, {})
    model_pricing = pricing.get(model, pricing.get("default", {"input": 1.0, "output": 3.0}))
    
    input_cost = (input_tokens / 1_000_000) * model_pricing["input"]
    output_cost = (output_tokens / 1_000_000) * model_pricing["output"]
    
    return input_cost + output_cost


def log_api_usage(
    directive: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int = 0,
    is_embedding: bool = False,
    metadata: Optional[Dict] = None
) -> Dict:
    """
    Log API usage and calculate cost.
    
    Args:
        directive: Directive name
        provider: LLM provider
        model: Model used
        input_tokens: Input tokens
        output_tokens: Output tokens
        is_embedding: Whether this is an embedding call
        metadata: Additional metadata
        
    Returns:
        Logged usage entry with cost
    """
    cost = calculate_cost(provider, model, input_tokens, output_tokens, is_embedding)
    
    usage_entry = {
        "timestamp": datetime.now().isoformat(),
        "directive": directive,
        "provider": provider,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": round(cost, 6),
        "is_embedding": is_embedding,
        "metadata": metadata or {}
    }
    
    # Log to usage history
    usage_file = ".runs/api_usage.jsonl"
    os.makedirs(os.path.dirname(usage_file), exist_ok=True)
    
    with open(usage_file, 'a') as f:
        f.write(json.dumps(usage_entry) + '\n')
    
    logger.debug(f"Logged API usage: {directive} -> {cost:.6f} USD ({input_tokens + output_tokens} tokens)")
    
    return usage_entry


def get_cost_summary(
    days: int = 30,
    directive: Optional[str] = None,
    provider: Optional[str] = None
) -> Dict:
    """
    Get cost summary from usage history.
    
    Args:
        days: Number of days to analyze
        directive: Filter by directive (optional)
        provider: Filter by provider (optional)
        
    Returns:
        {
            "total_cost": float,
            "total_tokens": int,
            "by_directive": Dict[str, float],
            "by_provider": Dict[str, float],
            "by_model": Dict[str, float],
            "daily_average": float,
            "entry_count": int
        }
    """
    from datetime import timedelta
    
    usage_file = ".runs/api_usage.jsonl"
    if not os.path.exists(usage_file):
        return {
            "total_cost": 0.0,
            "total_tokens": 0,
            "by_directive": {},
            "by_provider": {},
            "by_model": {},
            "daily_average": 0.0,
            "entry_count": 0
        }
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    total_cost = 0.0
    total_tokens = 0
    by_directive = {}
    by_provider = {}
    by_model = {}
    entry_count = 0
    
    with open(usage_file, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            
            try:
                entry = json.loads(line)
                entry_time = datetime.fromisoformat(entry["timestamp"])
                
                if entry_time < cutoff_date:
                    continue
                
                # Apply filters
                if directive and entry.get("directive") != directive:
                    continue
                if provider and entry.get("provider") != provider:
                    continue
                
                cost = entry.get("cost_usd", 0.0)
                tokens = entry.get("total_tokens", 0)
                
                total_cost += cost
                total_tokens += tokens
                entry_count += 1
                
                # Aggregate by directive
                dir_name = entry.get("directive", "unknown")
                by_directive[dir_name] = by_directive.get(dir_name, 0.0) + cost
                
                # Aggregate by provider
                prov_name = entry.get("provider", "unknown")
                by_provider[prov_name] = by_provider.get(prov_name, 0.0) + cost
                
                # Aggregate by model
                model_name = entry.get("model", "unknown")
                by_model[model_name] = by_model.get(model_name, 0.0) + cost
                
            except Exception as e:
                logger.warning(f"Error parsing usage entry: {e}")
                continue
    
    return {
        "total_cost": round(total_cost, 2),
        "total_tokens": total_tokens,
        "by_directive": {k: round(v, 2) for k, v in sorted(by_directive.items(), key=lambda x: x[1], reverse=True)},
        "by_provider": {k: round(v, 2) for k, v in sorted(by_provider.items(), key=lambda x: x[1], reverse=True)},
        "by_model": {k: round(v, 2) for k, v in sorted(by_model.items(), key=lambda x: x[1], reverse=True)},
        "daily_average": round(total_cost / days, 2) if days > 0 else 0.0,
        "entry_count": entry_count
    }


def get_expensive_directives(days: int = 30, limit: int = 10) -> List[Dict]:
    """
    Get most expensive directives.
    
    Args:
        days: Number of days to analyze
        limit: Number of directives to return
        
    Returns:
        List of dicts with directive, cost, token count
    """
    summary = get_cost_summary(days=days)
    
    expensive = []
    for directive, cost in summary["by_directive"].items():
        # Get token count for this directive
        dir_summary = get_cost_summary(days=days, directive=directive)
        expensive.append({
            "directive": directive,
            "cost_usd": cost,
            "total_tokens": dir_summary["total_tokens"],
            "entry_count": dir_summary["entry_count"]
        })
    
    expensive.sort(key=lambda x: x["cost_usd"], reverse=True)
    return expensive[:limit]


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Cost tracking utilities")
    parser.add_argument("--summary", action="store_true", help="Show cost summary")
    parser.add_argument("--days", type=int, default=30, help="Number of days")
    parser.add_argument("--directive", help="Filter by directive")
    parser.add_argument("--provider", help="Filter by provider")
    parser.add_argument("--expensive", type=int, help="Show N most expensive directives")
    
    args = parser.parse_args()
    
    if args.expensive:
        expensive = get_expensive_directives(days=args.days, limit=args.expensive)
        print(f"\nTop {args.expensive} Most Expensive Directives (last {args.days} days):")
        for i, item in enumerate(expensive, 1):
            print(f"{i}. {item['directive']}: ${item['cost_usd']:.2f} ({item['total_tokens']:,} tokens)")
    else:
        summary = get_cost_summary(days=args.days, directive=args.directive, provider=args.provider)
        print(f"\nCost Summary (last {args.days} days):")
        print(f"  Total cost: ${summary['total_cost']:.2f}")
        print(f"  Total tokens: {summary['total_tokens']:,}")
        print(f"  Daily average: ${summary['daily_average']:.2f}")
        print(f"  Entries: {summary['entry_count']}")
        print(f"\n  By directive:")
        for directive, cost in list(summary['by_directive'].items())[:10]:
            print(f"    {directive}: ${cost:.2f}")
        print(f"\n  By provider:")
        for provider, cost in summary['by_provider'].items():
            print(f"    {provider}: ${cost:.2f}")

