"""Help tool for Script Kiwi."""

from typing import Dict, Any
import json


class HelpTool:
    """Provide workflow guidance and troubleshooting"""
    
    async def execute(self, params: Dict[str, Any]) -> str:
        """
        Get help with scripts and workflows
        
        Args:
            query: What you need help with
            context: Additional context
        
        Returns:
            Helpful guidance and examples
        """
        query = params.get("query", "").lower()
        context = params.get("context", "")
        
        # Pattern matching for common queries
        if "scrape" in query or "leads" in query:
            return self._help_scraping()
        elif "email" in query or "enrich" in query:
            return self._help_enrichment()
        elif "workflow" in query or "campaign" in query:
            return self._help_workflow()
        else:
            return self._help_general()
    
    def _help_scraping(self) -> str:
        return json.dumps({
            "topic": "Lead Scraping",
            "workflow": [
                "1. Search for scraping script: search({'query': 'scrape Google Maps'})",
                "2. Load script details: load({'script_name': 'google_maps_leads'})",
                "3. Run with params: run({'script_name': 'google_maps_leads', 'parameters': {'search_term': '...', 'location': '...'}})",
                "4. Results saved to execution log"
            ],
            "common_scripts": [
                "google_maps_leads - Scrape local businesses from Google Maps",
                "linkedin_scraper - Extract LinkedIn profiles",
                "website_crawler - Crawl and extract from websites"
            ],
            "tips": [
                "Start with small counts (10-50) to test",
                "Check cost estimates before large runs",
                "Use location splitting for >1000 results"
            ]
        }, indent=2)
    
    def _help_enrichment(self) -> str:
        return json.dumps({
            "topic": "Email Enrichment",
            "workflow": [
                "1. Have leads with company names/domains",
                "2. Search: search({'query': 'enrich emails'})",
                "3. Load: load({'script_name': 'email_waterfall'})",
                "4. Run: run({'script_name': 'email_waterfall', 'parameters': {'leads': [...]}})",
                "5. Get results with enriched emails"
            ],
            "strategies": {
                "waterfall": "Try multiple sources (cost-effective)",
                "premium": "Use best source first (fastest)",
                "validation_only": "Just validate existing emails"
            },
            "tips": [
                "Waterfall strategy saves money (starts with free methods)",
                "Success rate typically 70-90% for business emails",
                "Always validate before sending campaigns"
            ]
        }, indent=2)
    
    def _help_workflow(self) -> str:
        return json.dumps({
            "topic": "Complete Outbound Campaign Workflow",
            "steps": [
                {
                    "phase": "1. Lead Generation",
                    "scripts": ["google_maps_leads", "linkedin_scraper"],
                    "output": "List of companies with contact info"
                },
                {
                    "phase": "2. Email Enrichment",
                    "scripts": ["email_waterfall", "email_validation"],
                    "output": "Valid email addresses"
                },
                {
                    "phase": "3. Research (use web_search via Anthropic API)",
                    "action": "Research each company for personalization",
                    "output": "Company insights stored in Knowledge Kiwi"
                },
                {
                    "phase": "4. Campaign Creation (use Campaign Kiwi MCP)",
                    "action": "Create campaign and generate emails",
                    "output": "Personalized emails ready to send"
                },
                {
                    "phase": "5. Monitoring (use Campaign Kiwi MCP)",
                    "action": "Track sends, opens, replies",
                    "output": "Campaign analytics"
                }
            ],
            "example_prompt": "Find 500 SaaS founders in Austin, enrich emails, research companies, create personalized campaign"
        }, indent=2)
    
    def _help_general(self) -> str:
        return json.dumps({
            "available_tools": [
                "search - Find scripts by intent",
                "load - Get script details",
                "run - Run a script",
                "publish - Publish script to registry",
                "help - Get guidance (this tool)"
            ],
            "script_categories": [
                "scraping - Extract data from web",
                "enrichment - Add emails, contacts",
                "extraction - YouTube, docs, GitHub",
                "validation - Check data quality",
                "maintenance - Cleanup, reports",
                "utility - Helper functions"
            ],
            "getting_started": [
                "1. Use search() to find what you need",
                "2. Use load() to see how to use it",
                "3. Use run() to execute it",
                "4. Use publish() to share scripts",
                "5. Use help() if you get stuck"
            ],
            "tips": [
                "All scripts have cost estimates",
                "Use dry_run=true to test without executing",
                "Check execution logs for history"
            ]
        }, indent=2)
