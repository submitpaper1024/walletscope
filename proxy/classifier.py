"""
Claude-assisted classifier: maps captured network requests to the five
wallet functional categories used by WalletScope (token_price, tx_history,
recipient_verification, rpc_relay, simulation).
"""

import json
import os
from typing import Any, Dict, List

import anthropic
import yaml

from .. import config  # noqa: F401  — ensures .env is loaded before os.getenv


_DEFAULT_CONFIG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "config.yaml"
)


class TrafficClassifier:
    """Classify wallet network traffic into provider-feature buckets."""

    def __init__(self, config_path: str = _DEFAULT_CONFIG):
        """Initialize Claude analyzer with configuration."""
        self.config = self._load_config(config_path)

        # API key lives in .env (ANTHROPIC_API_KEY); never in config.yaml.
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not set. Add it to walletscope/.env."
            )

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = self.config["claude"]["model"]
        self.max_tokens = self.config["claude"]["max_tokens"]
        self.temperature = self.config["claude"]["temperature"]

        # Ethereum mainnet chain IDs
        self.mainnet_chain_ids = set(self.config["ethereum"]["chain_ids"])

    def _load_config(self, path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Config file {path} not found. Please create it from config.yaml"
            )

    def is_ethereum_mainnet_request(self, record: Dict[str, Any]) -> bool:
        """
        Check if a request is for Ethereum mainnet.

        Checks:
        1. JSON-RPC method eth_chainId response
        2. net_version response
        3. URL contains mainnet indicators
        4. Request body contains mainnet chain ID
        """
        url_low = record.get("url", "").lower()
        body = record.get("request_body", "")

        # Check URL for mainnet indicators
        mainnet_indicators = ["mainnet", "eth-mainnet", "ethereum-mainnet"]
        if any(indicator in url_low for indicator in mainnet_indicators):
            return True

        # Check if it's a chainId or net_version request
        rpc_method = record.get("rpc_method", "")
        if rpc_method in ("eth_chainId", "net_version"):
            # These requests themselves don't tell us the chain,
            # but we'll mark them as potential mainnet for analysis
            return True

        # Check body for chain ID references
        try:
            if body and ("0x1" in body or '"chainId":"1"' in body or '"chainId":1' in body):
                return True
        except Exception:
            pass

        return False

    def filter_ethereum_mainnet_requests(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter records to only include Ethereum mainnet requests."""
        return [r for r in records if self.is_ethereum_mainnet_request(r)]

    def _build_analysis_prompt(self, records: List[Dict[str, Any]]) -> str:
        """Build prompt for Claude to analyze network traffic."""

        features = self.config["features"]
        feature_descriptions = "\n".join([
            f"{i+1}. **{f['name']}**: {f['description']}"
            for i, f in enumerate(features)
        ])

        # Prepare simplified records for analysis
        simplified_records = []
        for idx, r in enumerate(records):
            simplified = {
                "index": idx,
                "method": r.get("method", "GET"),
                "url": r.get("url", ""),
                "host": r.get("host", ""),
                "path": r.get("path", ""),
                "is_jsonrpc": r.get("is_jsonrpc", False),
                "rpc_method": r.get("rpc_method"),
                "rpc_params": r.get("rpc_params"),
                "current_tag": r.get("tag", "unknown"),
            }

            # Include a snippet of request body for context (first 500 chars)
            body = r.get("request_body", "")
            if body and len(body) > 500:
                simplified["request_body_snippet"] = body[:500] + "..."
            elif body:
                simplified["request_body_snippet"] = body

            # Include response data for better analysis
            simplified["response_status"] = r.get("response_status")

            # Include response body snippet (first 1000 chars for better context)
            response_body = r.get("response_body", "")
            if response_body:
                if len(response_body) > 1000:
                    simplified["response_body_snippet"] = response_body[:1000] + "..."
                else:
                    simplified["response_body_snippet"] = response_body

                # Try to parse JSON response for structured data
                try:
                    response_json = json.loads(response_body)
                    # Include key fields that might help identify the service
                    if isinstance(response_json, dict):
                        # Keep track of response structure hints
                        simplified["response_keys"] = list(response_json.keys())[:10]
                except Exception:
                    pass

            simplified_records.append(simplified)

        records_json = json.dumps(simplified_records, indent=2, ensure_ascii=False)

        prompt = f"""You are analyzing network traffic from Web3 wallet applications to identify which API providers/endpoints are used for specific wallet features on Ethereum mainnet.

I need you to analyze these network requests and classify them into the following categories:

{feature_descriptions}

Here are the network requests to analyze (JSON format):

```json
{records_json}
```

For each request, determine which feature category it belongs to. Consider:
- URL patterns and hostnames
- JSON-RPC methods and parameters
- Request patterns (e.g., eth_sendRawTransaction for tx submission)
- API endpoint paths
- **HTTP response status codes and response body content** - This is CRITICAL for accurate classification
- Response data structure (e.g., transaction lists indicate tx_history, price data indicates token_price)
- Response field names and data types that reveal the API's purpose

**IMPORTANT**: Pay special attention to the response data, as it often provides the most reliable indicator of what a service actually does. For example:
- Responses with transaction arrays/lists indicate transaction history services
- Responses with price/value data indicate token price services
- Responses with name/ENS data indicate recipient verification services
- Responses with simulation results indicate transaction simulation services

Please respond with a JSON object in this exact format:
{{
  "classifications": [
    {{
      "index": 0,
      "feature": "token_price|tx_history|recipient_verification|rpc_relay|simulation|other",
      "confidence": "high|medium|low",
      "provider": "name of the provider/service if identifiable",
      "reasoning": "brief explanation of why this request matches this feature, including response data analysis"
    }}
  ],
  "provider_summary": {{
    "token_price": ["list of unique providers/endpoints"],
    "tx_history": ["list of unique providers/endpoints"],
    "recipient_verification": ["list of unique providers/endpoints"],
    "rpc_relay": ["list of unique providers/endpoints"],
    "simulation": ["list of unique providers/endpoints"]
  }}
}}

Focus on identifying the actual service providers (e.g., Infura, Alchemy, QuickNode, CoinGecko, MetaMask API, etc.) and their endpoints.
Only include Ethereum mainnet providers."""

        return prompt

    def analyze_batch(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze a batch of network requests using Claude API.

        Args:
            records: List of network request records

        Returns:
            Analysis results with classifications and provider summary
        """
        if not records:
            return {
                "classifications": [],
                "provider_summary": {
                    "token_price": [],
                    "tx_history": [],
                    "recipient_verification": [],
                    "rpc_relay": [],
                    "simulation": []
                }
            }

        prompt = self._build_analysis_prompt(records)

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extract response text
            response_text = message.content[0].text

            # Parse JSON response
            # Try to find JSON in the response (Claude might wrap it in markdown)
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)
                return result
            else:
                print("Warning: Could not parse Claude response as JSON")
                print(f"Response: {response_text[:500]}")
                return {
                    "classifications": [],
                    "provider_summary": {},
                    "raw_response": response_text
                }

        except anthropic.APIError as e:
            print(f"Claude API error: {e}")
            return {
                "classifications": [],
                "provider_summary": {},
                "error": str(e)
            }
        except Exception as e:
            print(f"Error analyzing batch: {e}")
            return {
                "classifications": [],
                "provider_summary": {},
                "error": str(e)
            }

    def analyze_traffic(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze all traffic records, filtering for Ethereum mainnet and batching requests.

        Args:
            records: All network request records from mm_log.jsonl

        Returns:
            Complete analysis results with all classifications and provider summary
        """
        # Filter for Ethereum mainnet requests
        mainnet_records = self.filter_ethereum_mainnet_requests(records)

        print(f"Total requests: {len(records)}")
        print(f"Ethereum mainnet requests: {len(mainnet_records)}")

        if not mainnet_records:
            print("No Ethereum mainnet requests found.")
            return {
                "total_requests": len(records),
                "mainnet_requests": 0,
                "classifications": [],
                "provider_summary": {}
            }

        # Batch processing
        batch_size = self.config["analysis"]["batch_size"]
        all_classifications = []

        for i in range(0, len(mainnet_records), batch_size):
            batch = mainnet_records[i:i + batch_size]
            print(f"Analyzing batch {i//batch_size + 1} ({len(batch)} requests)...")

            result = self.analyze_batch(batch)

            if "classifications" in result:
                # Adjust indices to match original records
                for classification in result["classifications"]:
                    classification["original_index"] = i + classification["index"]
                all_classifications.extend(result["classifications"])

        # Merge provider summaries
        merged_summary = {
            "token_price": set(),
            "tx_history": set(),
            "recipient_verification": set(),
            "rpc_relay": set(),
            "simulation": set()
        }

        for classification in all_classifications:
            feature = classification.get("feature", "other")
            provider = classification.get("provider", "unknown")

            if feature in merged_summary and provider != "unknown":
                merged_summary[feature].add(provider)

        # Convert sets to sorted lists
        final_summary = {
            k: sorted(list(v)) for k, v in merged_summary.items()
        }

        return {
            "total_requests": len(records),
            "mainnet_requests": len(mainnet_records),
            "analyzed_requests": len(all_classifications),
            "classifications": all_classifications,
            "provider_summary": final_summary,
            "mainnet_records": mainnet_records
        }
