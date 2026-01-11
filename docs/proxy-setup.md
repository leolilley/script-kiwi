# Proxy Setup Guide

This guide explains how to configure and use proxies with Script Kiwi for web scraping and automation.

## Overview

Script Kiwi provides a flexible proxy system with:

- **Multiple proxy service support** (NodeMaven, Bright Data, Oxylabs, etc.)
- **Automatic rotation** with health tracking
- **Multiple strategies** (round-robin, random, least-used, fastest)
- **Cookie management** for authenticated sessions

## Quick Start

### 1. Choose a Proxy Service

| Service           | Best For                   | Price     | Notes                                              |
| ----------------- | -------------------------- | --------- | -------------------------------------------------- |
| **NodeMaven**     | Scraping, multi-accounting | ~$4/GB    | Premium quality, 24h sticky sessions, IP filtering |
| Bright Data       | Large scale                | ~$4/GB    | Huge pool, good geo-coverage                       |
| Smartproxy/Decodo | Budget scraping            | ~$2.50/GB | Good value, 99% success rate                       |
| Oxylabs           | Enterprise                 | ~$4/GB    | Very reliable                                      |
| Webshare          | Testing                    | ~$3/GB    | Budget option                                      |

### 2. Configure Your Proxy

There are three ways to configure proxies:

#### Option A: Static Proxy URL (Simplest)

Set a single proxy URL in your `.env`:

```bash
PROXY_URL=http://username:password@proxy.example.com:8080
```

#### Option B: Proxy Service Credentials

Configure a paid service:

```bash
# For NodeMaven (recommended)
PROXY_SERVICE=nodemaven
PROXY_USERNAME=your-username
PROXY_PASSWORD=your-password
PROXY_COUNTRY=us           # Optional: us, gb, nz, etc.
PROXY_FILTER=medium        # Optional: medium, high (IP quality)
PROXY_SESSION_ID=session1  # Optional: for sticky sessions
```

#### Option C: Multiple Proxies from File (Best for Rotation)

For services like NodeMaven that provide multiple pre-generated proxies:

1. Save your proxy usernames to `.ai/tmp/nodemaven_proxies.txt`:

```
# One username per line
username-country-us-sid-abc123-ttl-24h-filter-medium
username-country-us-sid-def456-ttl-24h-filter-medium
username-country-nz-sid-xyz789-ttl-24h-filter-medium
```

2. Set your password:

```bash
PROXY_PASSWORD=your-password
```

3. The ProxyPool will automatically load and rotate through all proxies.

## Usage

### Simple: Get a Session

```python
from lib.http_session import get_session

# Auto-configures from environment
session = get_session()
response = session.get("https://example.com")
```

### With Proxy Pool Rotation

```python
from lib.proxy_pool import ProxyPool

# Creates pool, auto-loads proxies from file if available
pool = ProxyPool()

# Get a proxy (rotates through available proxies)
proxy = pool.get_proxy(strategy="round_robin")

# Use it
import requests
response = requests.get(url, proxies={"http": proxy, "https": proxy})

# Track success/failure for health monitoring
if response.status_code == 200:
    pool.mark_success(proxy, latency=response.elapsed.total_seconds())
else:
    pool.mark_failed(proxy, reason="Bad status code")
```

### Rotation Strategies

```python
# Round-robin (default): cycles through proxies in order
proxy = pool.get_proxy(strategy="round_robin")

# Random: picks a random healthy proxy
proxy = pool.get_proxy(strategy="random")

# Least-used: picks the proxy with fewest requests
proxy = pool.get_proxy(strategy="least_used")

# Fastest: picks the proxy with lowest average latency
proxy = pool.get_proxy(strategy="fastest")
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Your Script                             │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   http_session.py                            │
│  get_session() - Configured requests.Session                │
│  - Loads proxy from ProxyPool or env                        │
│  - Loads cookies from CookieManager                         │
│  - Configures retries, headers, timeouts                    │
└─────────────────────┬───────────────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
┌─────────────────────┐ ┌─────────────────────┐
│   proxy_pool.py     │ │  cookie_manager.py  │
│                     │ │                     │
│ - Load from file    │ │ - Extract cookies   │
│ - Load from env     │ │   via Playwright    │
│ - Health tracking   │ │ - Netscape format   │
│ - Rotation strategies│ │ - Expiration check │
│ - Stats & metrics   │ │                     │
└─────────────────────┘ └─────────────────────┘
```

## Files

| File                                | Purpose                             |
| ----------------------------------- | ----------------------------------- |
| `.ai/scripts/lib/proxy_pool.py`     | Proxy pool manager with rotation    |
| `.ai/scripts/lib/http_session.py`   | HTTP session factory                |
| `.ai/scripts/lib/cookie_manager.py` | Cookie extraction and management    |
| `.ai/tmp/nodemaven_proxies.txt`     | Your proxy usernames (one per line) |
| `.ai/tmp/proxy_pool.json`           | Pool state (health, stats, etc.)    |
| `.ai/tmp/cookies/`                  | Extracted cookies by domain         |

## Environment Variables

### Proxy Configuration

| Variable           | Description            | Example                              |
| ------------------ | ---------------------- | ------------------------------------ |
| `PROXY_URL`        | Static proxy URL       | `http://user:pass@host:8080`         |
| `PROXY_SERVICE`    | Service name           | `nodemaven`, `brightdata`, `oxylabs` |
| `PROXY_USERNAME`   | Service username       | `your-username`                      |
| `PROXY_PASSWORD`   | Service password       | `your-password`                      |
| `PROXY_COUNTRY`    | Geo-targeting          | `us`, `gb`, `nz`, `any`              |
| `PROXY_FILTER`     | IP quality (NodeMaven) | `medium`, `high`                     |
| `PROXY_SESSION_ID` | Sticky session ID      | `session123`                         |
| `PROXY_ZONE`       | Zone (Bright Data)     | `residential`                        |
| `PROXY_FILE`       | Path to proxies file   | `.ai/tmp/nodemaven_proxies.txt`      |

### Priority Order

1. Explicit parameters passed to functions
2. `PROXY_URL` environment variable
3. `PROXY_SERVICE` + credentials
4. Proxies file (for ProxyPool)

## Supported Services

### NodeMaven (Recommended)

```bash
PROXY_SERVICE=nodemaven
PROXY_USERNAME=leo_lml_lilley_gmail_com
PROXY_PASSWORD=your-password
PROXY_COUNTRY=us
PROXY_FILTER=medium
```

Features:

- 24-hour sticky sessions
- IP quality filtering (medium/high)
- Premium residential IPs
- ~85% success rate on tough sites

### Bright Data

```bash
PROXY_SERVICE=brightdata
PROXY_USERNAME=brd-customer-xxxxx
PROXY_PASSWORD=your-password
PROXY_ZONE=residential
PROXY_COUNTRY=us
```

### Smartproxy / Decodo

```bash
PROXY_SERVICE=smartproxy  # or "decodo"
PROXY_USERNAME=your-username
PROXY_PASSWORD=your-password
```

### Oxylabs

```bash
PROXY_SERVICE=oxylabs
PROXY_USERNAME=customer-xxxxx
PROXY_PASSWORD=your-password
PROXY_COUNTRY=us
```

## Health Tracking

The proxy pool automatically tracks:

- **Success/failure counts** per proxy
- **Average latency** per proxy
- **Last used/success/failure** timestamps
- **Failure reasons**

Proxies are marked unhealthy after >50% failure rate (with 5+ requests).

```python
# View pool statistics
stats = pool.get_stats()
print(stats)
# {
#   "total_proxies": 29,
#   "healthy_proxies": 28,
#   "unhealthy_proxies": 1,
#   "sources": ["nodemaven"],
#   "rotation_strategy": "round_robin"
# }
```

## Cookie Management

For sites requiring authentication (YouTube, etc.):

```python
from lib.cookie_manager import CookieManager

cookie_mgr = CookieManager()

# Check if cookies exist
if cookie_mgr.has_cookies("youtube.com"):
    path = cookie_mgr.get_cookies_path("youtube.com")
else:
    # Extract cookies using Playwright (opens browser)
    path = cookie_mgr.extract_cookies("youtube.com", headless=False)

# Use with session
from lib.http_session import get_session
session = get_session(domain="youtube.com", use_cookies=True)
```

## Troubleshooting

### No proxies loading

1. Check `PROXY_PASSWORD` is set
2. Check `.ai/tmp/nodemaven_proxies.txt` exists and has usernames
3. Run: `python .ai/scripts/lib/proxy_pool.py` to diagnose

### Proxies failing health checks

1. Verify credentials are correct
2. Check proxy service dashboard for usage limits
3. Try a different country/region

### Cookies expired

```python
cookie_mgr = CookieManager()
cookie_mgr.delete_cookies("youtube.com")
cookie_mgr.extract_cookies("youtube.com", headless=False)  # Re-extract
```

## Testing

```bash
# Test proxy configuration
python .ai/scripts/lib/proxy_pool.py

# Expected output:
# Proxy Pool Configuration Check
# ========================================
# Environment:
#   PROXY_URL: not set
#   PROXY_SERVICE: not set
#   PROXY_PASSWORD: set
#
# Pool Stats:
# {
#   "total_proxies": 29,
#   "healthy_proxies": 29,
#   ...
# }
```

## Security Notes

- Never commit `.env` files (already in `.gitignore`)
- Never commit `.ai/tmp/` (already in `.gitignore`)
- Proxy credentials are masked in logs
- Pool state file contains URLs with credentials - keep secure
