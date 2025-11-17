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
SITE_LIST_PATH = pathlib.Path("crawler_src") / "site_list.csv"
BLOCKLIST_PATHS: Tuple[pathlib.Path, ...] = (
    pathlib.Path("crawler_src") / "disconnect_blocklist.json",
    pathlib.Path("disconnect_blocklist.json"),
)
ENTITIES_PATHS: Tuple[pathlib.Path, ...] = (
    pathlib.Path("analysis") / "entities.json",
    pathlib.Path("crawler_src") / "entities.json",
)
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


def load_disconnect_lookup(paths: Iterable[pathlib.Path]) -> Dict[str, str]:
    for path in paths:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        categories = data.get("categories", {})
        lookup: Dict[str, str] = {}

        def _register(value: str, category: str) -> None:
            domain = normalize_domain(value)
            if domain and "." in domain:
                lookup[domain] = category

        def _walk(payload, category: str) -> None:
            if isinstance(payload, str):
                _register(payload, category)
            elif isinstance(payload, dict):
                for key, nested in payload.items():
                    if isinstance(key, str):
                        _register(key, category)
                    _walk(nested, category)
            elif isinstance(payload, list):
                for item in payload:
                    _walk(item, category)

        for category, entities in categories.items():
            if isinstance(entities, dict):
                for entity_data in entities.values():
                    _walk(entity_data, category)
            elif isinstance(entities, list):
                for entity_data in entities:
                    _walk(entity_data, category)
        if lookup:
            return lookup
    return {}


def load_disconnect_entities(paths: Iterable[pathlib.Path]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}

    def _register(domain: str, entity: str) -> None:
        if domain and entity and domain not in lookup:
            lookup[domain.lower()] = entity

    for candidate in paths:
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        entities = payload.get("entities")
        if not isinstance(entities, dict):
            continue
        for entity_name, entity_data in entities.items():
            if not isinstance(entity_data, dict):
                continue
            for key in ("domains", "properties", "resources"):
                for item in entity_data.get(key, []) or []:
                    if isinstance(item, str):
                        _register(item, entity_name)
        if lookup:
            break
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


def lookup_disconnect_entity(host: Optional[str], lookup: Dict[str, str]) -> Optional[str]:
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
    har_blob: dict,
    first_party_domain: Optional[str],
    disconnect_lookup: Dict[str, str],
    disconnect_entity_lookup: Dict[str, str],
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
    disconnect_entity_counter: Counter[str] = Counter()

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
        entity = lookup_disconnect_entity(host, disconnect_entity_lookup)
        if category:
            disconnect_counter[category] += 1
        is_third = is_third_party(host, first_party_domain)
        if is_third:
            third_party_count += 1
            if domain:
                domains_third.add(domain)
            if entity:
                disconnect_entity_counter[entity] += 1
        status = response.get("status")
        if isinstance(status, int) and status >= 400:
            error_count += 1
        duration = entry.get("time")
        if isinstance(duration, (int, float)):
            total_latency_ms += max(duration, 0.0)
        blocked = bool(entry.get("_wasAborted", False))
        if not blocked:
            if status in (-1, 0, None):
                blocked = True
            elif response.get("_error"):
                blocked = True
            elif isinstance(response.get("statusText"), str):
                status_text = response.get("statusText", "").lower()
                if status_text in ("failed", "aborted", "blocked", "net::err_aborted", "net::err_blocked_by_client"):
                    blocked = True
        if isinstance(status, int) and status >= 400:
            error_count += 1
        duration = entry.get("time")
        if isinstance(duration, (int, float)):
            total_latency_ms += max(duration, 0.0)
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
            "disconnect_entity": entity,
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
        "disconnect_entities": sorted(disconnect_entity_counter.keys()),
        "disconnect_entity_counts": dict(disconnect_entity_counter),
        "disconnect_entity_unique_count": len(disconnect_entity_counter),
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
    disconnect_entity_lookup: Dict[str, str],
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
        har_blob, first_party_domain, disconnect_lookup, disconnect_entity_lookup
    )
    record["requests"] = requests
    record["summary"] = summary
    return record


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    site_catalog = load_site_catalog(SITE_LIST_PATH)
    disconnect_lookup = load_disconnect_lookup(BLOCKLIST_PATHS)
    disconnect_entities = load_disconnect_entities(ENTITIES_PATHS)

    with OUTPUT_PATH.open("w", encoding="utf-8") as sink:
        for har_path in iter_har_files(HAR_ROOTS):
            record = build_record(
                har_path,
                site_catalog,
                disconnect_lookup,
                disconnect_entities,
            )
            sink.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()