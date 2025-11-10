from __future__ import annotations

'''
Author: Mikel Telleria
-----
Last Modified: Saturday, 8th November 2025 8:00:00 pm
Modified By: Mikel Telleria
-----
'''

"""Transforms HAR outputs into structured JSON lines for downstream analysis."""

import csv
import json
import pathlib
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

HAR_ROOTS: Tuple[pathlib.Path, ...] = (
    pathlib.Path("crawl_data_accept"),
    pathlib.Path("crawl_data_reject"),
    pathlib.Path("crawl_data_block"),
)
SITE_LIST_PATH = pathlib.Path("site_list.csv")
BLOCKLIST_PATH = pathlib.Path("disconnect_blocklist.json")
OUTPUT_PATH = pathlib.Path("analysis") / "results.jsonl"


def load_site_catalog(path: pathlib.Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    catalog: Dict[str, Dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            domain = (
                row.get("domain")
                or row.get("site")
                or row.get("url")
                or row.get("homepage")
                or ""
            ).strip()
            if not domain:
                continue
            normalized = normalize_domain(domain)
            if normalized:
                catalog[normalized] = row
    return catalog


def load_disconnect_lookup(path: pathlib.Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    categories = data.get("categories", {})
    lookup: Dict[str, str] = {}

    def _register(domain: str, category: str) -> None:
        if domain:
            lookup[domain.lower()] = category

    for category, entities in categories.items():
        if not isinstance(entities, dict):
            continue
        for entity, entity_data in entities.items():
            _register(entity, category)
            if isinstance(entity_data, dict):
                for coll_name in ("domains", "properties", "resources"):
                    for item in entity_data.get(coll_name, []):
                        if isinstance(item, str):
                            _register(item, category)
    return lookup


def normalize_domain(domain: str) -> str:
    if not domain:
        return ""
    domain = domain.lower()
    parsed = urlparse(domain if "://" in domain else f"https://{domain}")
    host = parsed.hostname or domain
    if host.startswith("www."):
        host = host[4:]
    return host


def detect_mode(har_path: pathlib.Path) -> str:
    parts = [part.lower() for part in har_path.parts]
    for mode in ("accept", "reject", "block"):
        if f"crawl_data_{mode}" in parts:
            return mode
    return "unknown"


def load_metadata(
    har_path: pathlib.Path, catalog: Dict[str, Dict[str, str]]
) -> Dict[str, Optional[object]]:
    visit_id = har_path.stem
    mode = detect_mode(har_path)
    normalized = normalize_domain(visit_id)
    site_row = catalog.get(normalized)
    site_url = None
    country = None
    if site_row:
        site_url = (
            site_row.get("url")
            or site_row.get("homepage")
            or site_row.get("site")
            or site_row.get("domain")
        )
        country = site_row.get("country")
    if not site_url:
        site_url = f"https://{normalized}" if normalized else visit_id
    consent_action_map = {
        "accept": "accept_all",
        "reject": "reject_all",
        "block": "disconnect_blocklist",
    }
    return {
        "site_url": site_url,
        "site_domain": normalized or None,
        "crawl_mode": mode,
        "consent_action": consent_action_map.get(mode),
        "country": country,
        "site_list_row": site_row,
    }


def parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def headers_to_dict(items: Iterable[dict]) -> Dict[str, object]:
    result: Dict[str, object] = {}
    for item in items or []:
        name = item.get("name")
        if not name:
            continue
        value = item.get("value")
        key = name.lower()
        if key in result:
            existing = result[key]
            if isinstance(existing, list):
                existing.append(value)
            else:
                result[key] = [existing, value]
        else:
            result[key] = value
    return result


def simplify_cookies(items: Iterable[dict]) -> List[dict]:
    simplified: List[dict] = []
    for cookie in items or []:
        simplified.append(
            {
                "name": cookie.get("name"),
                "value": cookie.get("value"),
                "domain": cookie.get("domain"),
                "path": cookie.get("path"),
                "expires": cookie.get("expires"),
                "httpOnly": cookie.get("httpOnly"),
                "secure": cookie.get("secure"),
                "sameSite": cookie.get("sameSite"),
            }
        )
    return simplified


def lookup_disconnect_category(host: Optional[str], lookup: Dict[str, str]) -> Optional[str]:
    if not host:
        return None
    host = host.lower()
    parts = host.split(".")
    for idx in range(len(parts)):
        candidate = ".".join(parts[idx:])
        if candidate in lookup:
            return lookup[candidate]
    return None


def is_third_party(host: Optional[str], first_party: Optional[str]) -> bool:
    if not host or not first_party:
        return False
    host = host.lower()
    first_party = first_party.lower()
    return not (host == first_party or host.endswith("." + first_party))


def extract_visit_bounds(entries: List[dict]) -> Tuple[Optional[str], Optional[str]]:
    start_candidates: List[datetime] = []
    end_candidates: List[datetime] = []
    for entry in entries:
        started = parse_iso8601(entry.get("startedDateTime"))
        if not started:
            continue
        start_candidates.append(started)
        duration = entry.get("time")
        if isinstance(duration, (int, float)) and duration >= 0:
            end_candidates.append(started + timedelta(milliseconds=duration))
        else:
            end_candidates.append(started)
    start_dt = min(start_candidates) if start_candidates else None
    end_dt = max(end_candidates) if end_candidates else None
    fmt = lambda dt: dt.isoformat(timespec="milliseconds") if dt else None
    return fmt(start_dt), fmt(end_dt)


def extract_requests(
    har_blob: dict, first_party_domain: Optional[str], disconnect_lookup: Dict[str, str]
) -> Tuple[List[dict], Dict[str, object]]:
    entries = har_blob.get("log", {}).get("entries", []) or []
    requests: List[dict] = []
    total_latency_ms = 0.0
    blocked_count = 0
    error_count = 0
    total_body_bytes = 0
    third_party_count = 0
    domains_total: set[str] = set()
    domains_third: set[str] = set()
    disconnect_counter: Counter[str] = Counter()

    for entry in entries:
        request = entry.get("request", {})
        response = entry.get("response", {})
        url = request.get("url")
        if not url:
            continue
        parsed = urlparse(url)
        host = parsed.hostname or ""
        domain = host.lower()
        domains_total.add(domain)
        category = lookup_disconnect_category(host, disconnect_lookup)
        if category:
            disconnect_counter[category] += 1
        is_third = is_third_party(host, first_party_domain)
        if is_third:
            third_party_count += 1
            if domain:
                domains_third.add(domain)
        status = response.get("status")
        if isinstance(status, int) and status >= 400:
            error_count += 1
        duration = entry.get("time")
        if isinstance(duration, (int, float)):
            total_latency_ms += max(duration, 0.0)
        blocked = bool(entry.get("_blocked", False) or entry.get("blocked", False))
        if blocked:
            blocked_count += 1
        body_size = response.get("bodySize")
        if isinstance(body_size, (int, float)):
            total_body_bytes += max(body_size, 0)
        record = {
            "url": url,
            "method": request.get("method"),
            "status": status,
            "startedDateTime": entry.get("startedDateTime"),
            "time": duration,
            "resourceType": entry.get("_resourceType")
            or entry.get("_resource_type")
            or response.get("content", {}).get("mimeType"),
            "ipAddress": entry.get("serverIPAddress"),
            "protocol": request.get("httpVersion"),
            "is_third_party": is_third,
            "disconnect_category": category,
            "request_headers": headers_to_dict(request.get("headers", [])),
            "response_headers": headers_to_dict(response.get("headers", [])),
            "request_cookies": simplify_cookies(request.get("cookies", [])),
            "response_cookies": simplify_cookies(response.get("cookies", [])),
            "timings": {k: v for k, v in (entry.get("timings") or {}).items() if v is not None},
            "fromCache": entry.get("cache"),
            "encodedBodySize": response.get("content", {}).get("size"),
            "redirectURL": response.get("redirectURL"),
            "blocked": blocked,
            "initiator": entry.get("_initiator"),
        }
        requests.append(record)

    summary = {
        "total_requests": len(requests),
        "first_party_requests": len(requests) - third_party_count,
        "third_party_requests": third_party_count,
        "unique_domains_total": len(domains_total),
        "unique_domains_third_party": len(domains_third),
        "disconnect_categories": sorted(disconnect_counter.keys()),
        "disconnect_category_counts": dict(disconnect_counter),
        "total_latency_ms": total_latency_ms,
        "blocked_requests": blocked_count,
        "error_responses": error_count,
        "total_response_body_bytes": total_body_bytes,
    }
    return requests, summary


def iter_har_files(roots: Iterable[pathlib.Path]) -> Iterable[pathlib.Path]:
    for root in roots:
        if not root.exists():
            continue
        for har_file in sorted(root.rglob("*.har")):
            yield har_file


def build_record(
    har_path: pathlib.Path,
    catalog: Dict[str, Dict[str, str]],
    disconnect_lookup: Dict[str, str],
) -> dict:
    metadata = load_metadata(har_path, catalog)
    record = {
        "visit_id": har_path.stem,
        "timestamp_ingested": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **{k: v for k, v in metadata.items() if k != "site_list_row"},
        "artifacts": {
            "har": str(har_path),
            "screenshot_before": str(har_path.with_suffix(".before.png")),
            "screenshot_after": str(har_path.with_suffix(".after.png")),
            "video": str(har_path.with_suffix(".webm")),
        },
        "summary": {},
        "requests": [],
        "errors": [],
    }
    if metadata.get("site_list_row"):
        record["site_metadata"] = metadata["site_list_row"]
    try:
        har_blob = json.loads(har_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        record["errors"].append(f"HAR parse error: {exc}")
        return record

    entries = har_blob.get("log", {}).get("entries", []) or []
    visit_start, visit_end = extract_visit_bounds(entries)
    record["visit_started_at"] = visit_start
    record["visit_finished_at"] = visit_end

    first_party_domain = metadata.get("site_domain")
    if not isinstance(first_party_domain, str):
        first_party_domain = None
    requests, summary = extract_requests(
        har_blob, first_party_domain, disconnect_lookup
    )
    record["requests"] = requests
    record["summary"] = summary
    return record


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    site_catalog = load_site_catalog(SITE_LIST_PATH)
    disconnect_lookup = load_disconnect_lookup(BLOCKLIST_PATH)

    with OUTPUT_PATH.open("w", encoding="utf-8") as sink:
        for har_path in iter_har_files(HAR_ROOTS):
            record = build_record(har_path, site_catalog, disconnect_lookup)
            sink.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()