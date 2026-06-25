"""Helpers for editing browser flow scenarios.

The current runner still stores executable flow scenarios in the legacy
``rpa84.scenarios`` config section.  This module keeps that storage detail in
one place so the UI can present the feature as a generic flow editor.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


FLOW_SECTION = "rpa84"
SUPPORTED_ACTIONS = {
    "goto",
    "click_first",
    "fill_first",
    "press_first",
    "wait_for_load_state",
    "wait",
    "assert_any_text",
    "assert_all_text",
    "screenshot",
    "manual_note",
}
SELECTOR_ACTIONS = {"click_first", "fill_first", "press_first"}
ASSERT_ACTIONS = {"assert_any_text", "assert_all_text"}
ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{1,80}$")


class FlowValidationError(ValueError):
    """Raised when a flow cannot be saved safely."""


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise FlowValidationError("config root must be an object")
    return data


def ensure_flow_section(config: dict[str, Any]) -> dict[str, Any]:
    section = config.setdefault(FLOW_SECTION, {})
    if not isinstance(section, dict):
        raise FlowValidationError(f"config.{FLOW_SECTION} must be an object")
    scenarios = section.setdefault("scenarios", [])
    if not isinstance(scenarios, list):
        raise FlowValidationError(f"config.{FLOW_SECTION}.scenarios must be a list")
    return section


def flow_list(config: dict[str, Any]) -> list[dict[str, Any]]:
    section = ensure_flow_section(config)
    return [item for item in section["scenarios"] if isinstance(item, dict)]


def clean_lines(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    elif isinstance(value, str):
        raw = value.replace("\r", "").split("\n")
    elif value is None:
        raw = []
    else:
        raw = [str(value)]
    return [str(item).strip() for item in raw if str(item).strip()]


def clean_object(value: Any, field_name: str) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    raise FlowValidationError(f"{field_name} must be an object")


def clean_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def clean_int(value: Any, default: int, minimum: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise FlowValidationError(f"{value!r} is not a valid integer") from exc
    return max(minimum, parsed)


def validate_id(flow_id: str) -> str:
    flow_id = str(flow_id or "").strip()
    if not ID_RE.match(flow_id):
        raise FlowValidationError("id must be 2-81 letters, numbers, dashes, or underscores")
    return flow_id


def validate_item_id(item_id: str, label: str = "id") -> str:
    item_id = str(item_id or "").strip()
    if not ID_RE.match(item_id):
        raise FlowValidationError(f"{label} must be 2-81 letters, numbers, dashes, or underscores")
    return item_id


def normalize_step(step: dict[str, Any], index: int) -> dict[str, Any]:
    if not isinstance(step, dict):
        raise FlowValidationError(f"step {index + 1} must be an object")
    action = str(step.get("action") or "").strip()
    if action not in SUPPORTED_ACTIONS:
        raise FlowValidationError(f"step {index + 1} has unsupported action: {action}")

    normalized: dict[str, Any] = {"action": action}
    name = str(step.get("name") or "").strip()
    if name:
        normalized["name"] = name
    if clean_bool(step.get("optional", False)):
        normalized["optional"] = True

    if action == "goto":
        url = str(step.get("url") or "").strip()
        path = str(step.get("path") or "").strip()
        if not url and not path:
            raise FlowValidationError(f"step {index + 1} goto needs path or url")
        if url:
            normalized["url"] = url
        if path:
            normalized["path"] = path
        wait_until = str(step.get("wait_until") or "").strip()
        if wait_until:
            normalized["wait_until"] = wait_until
    elif action in SELECTOR_ACTIONS:
        selectors = clean_lines(step.get("selectors"))
        if not selectors:
            raise FlowValidationError(f"step {index + 1} needs at least one selector")
        normalized["selectors"] = selectors
        timeout_ms = clean_int(step.get("timeout_ms"), 3500, 100)
        if timeout_ms != 3500:
            normalized["timeout_ms"] = timeout_ms
        if action == "click_first":
            click_timeout_ms = clean_int(step.get("click_timeout_ms"), 5000, 100)
            if click_timeout_ms != 5000:
                normalized["click_timeout_ms"] = click_timeout_ms
        elif action == "fill_first":
            normalized["value"] = str(step.get("value") or "")
        elif action == "press_first":
            normalized["key"] = str(step.get("key") or "Enter").strip() or "Enter"
    elif action == "wait_for_load_state":
        normalized["state"] = str(step.get("state") or "networkidle").strip() or "networkidle"
        normalized["timeout_ms"] = clean_int(step.get("timeout_ms"), 15000, 100)
    elif action == "wait":
        normalized["milliseconds"] = clean_int(step.get("milliseconds"), 1000, 0)
    elif action in ASSERT_ACTIONS:
        texts = clean_lines(step.get("texts"))
        if not texts:
            raise FlowValidationError(f"step {index + 1} needs at least one expected text")
        normalized["texts"] = texts
        timeout_ms = clean_int(step.get("timeout_ms"), 5000, 100)
        if timeout_ms != 5000:
            normalized["timeout_ms"] = timeout_ms
    elif action == "screenshot":
        filename = str(step.get("filename") or "").strip()
        if filename:
            normalized["filename"] = filename
        if clean_bool(step.get("full_page", False)):
            normalized["full_page"] = True
    elif action == "manual_note":
        normalized["note"] = str(step.get("note") or "").strip()

    return normalized


def normalize_flow(flow: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(flow, dict):
        raise FlowValidationError("flow must be an object")
    normalized = dict(existing or {})
    normalized["id"] = validate_id(str(flow.get("id") or normalized.get("id") or ""))
    normalized["name"] = str(flow.get("name") or "").strip()
    if not normalized["name"]:
        raise FlowValidationError("name is required")
    group = str(flow.get("group") or "").strip()
    if group:
        normalized["group"] = group
    elif "group" in normalized:
        normalized.pop("group")
    normalized["enabled"] = clean_bool(flow.get("enabled", False))
    if clean_bool(flow.get("side_effect", False)):
        normalized["side_effect"] = True
    else:
        normalized.pop("side_effect", None)

    input_data = clean_object(flow.get("input", {}), "input")
    if input_data:
        normalized["input"] = input_data
    else:
        normalized.pop("input", None)

    for key in ("acceptance", "exception"):
        values = clean_lines(flow.get(key))
        if values:
            normalized[key] = values
        else:
            normalized.pop(key, None)

    steps = flow.get("steps", [])
    if not isinstance(steps, list) or not steps:
        raise FlowValidationError("steps must contain at least one step")
    normalized["steps"] = [normalize_step(step, index) for index, step in enumerate(steps)]
    return normalized


def find_flow_index(flows: list[dict[str, Any]], flow_id: str) -> int | None:
    for index, flow in enumerate(flows):
        if str(flow.get("id")) == flow_id:
            return index
    return None


def upsert_flow(
    config: dict[str, Any],
    flow: dict[str, Any],
    previous_id: str | None = None,
) -> dict[str, Any]:
    section = ensure_flow_section(config)
    flows = section["scenarios"]
    lookup_id = previous_id or str(flow.get("id") or "")
    existing_index = find_flow_index(flows, lookup_id)
    existing = flows[existing_index] if existing_index is not None else None
    normalized = normalize_flow(flow, existing)

    duplicate_index = find_flow_index(flows, normalized["id"])
    if duplicate_index is not None and duplicate_index != existing_index:
        raise FlowValidationError(f"id already exists: {normalized['id']}")
    if existing_index is None:
        flows.append(normalized)
    else:
        flows[existing_index] = normalized
    return normalized


def delete_flow(config: dict[str, Any], flow_id: str) -> bool:
    section = ensure_flow_section(config)
    flows = section["scenarios"]
    index = find_flow_index(flows, flow_id)
    if index is None:
        return False
    del flows[index]
    return True


def page_list(config: dict[str, Any]) -> list[dict[str, Any]]:
    pages = config.setdefault("pages", [])
    if not isinstance(pages, list):
        raise FlowValidationError("config.pages must be a list")
    return [item for item in pages if isinstance(item, dict)]


def normalize_page(page: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(page, dict):
        raise FlowValidationError("page must be an object")
    normalized = dict(existing or {})
    normalized["id"] = validate_item_id(str(page.get("id") or normalized.get("id") or ""), "page id")
    normalized["name"] = str(page.get("name") or "").strip()
    if not normalized["name"]:
        raise FlowValidationError("page name is required")
    path = str(page.get("path") or "").strip()
    if not path:
        raise FlowValidationError("page path is required")
    normalized["path"] = path
    normalized["expected_title_contains"] = clean_lines(page.get("expected_title_contains"))
    normalized["required_texts"] = clean_lines(page.get("required_texts"))
    if clean_bool(page.get("full_page_screenshot", False)):
        normalized["full_page_screenshot"] = True
    else:
        normalized.pop("full_page_screenshot", None)
    return normalized


def find_item_index(items: list[dict[str, Any]], item_id: str) -> int | None:
    for index, item in enumerate(items):
        if str(item.get("id")) == item_id:
            return index
    return None


def upsert_page(
    config: dict[str, Any],
    page: dict[str, Any],
    previous_id: str | None = None,
) -> dict[str, Any]:
    pages = config.setdefault("pages", [])
    if not isinstance(pages, list):
        raise FlowValidationError("config.pages must be a list")
    lookup_id = previous_id or str(page.get("id") or "")
    existing_index = find_item_index(pages, lookup_id)
    existing = pages[existing_index] if existing_index is not None else None
    normalized = normalize_page(page, existing)
    duplicate_index = find_item_index(pages, normalized["id"])
    if duplicate_index is not None and duplicate_index != existing_index:
        raise FlowValidationError(f"page id already exists: {normalized['id']}")
    if existing_index is None:
        pages.append(normalized)
    else:
        pages[existing_index] = normalized
    return normalized


def delete_page(config: dict[str, Any], page_id: str) -> bool:
    pages = config.setdefault("pages", [])
    if not isinstance(pages, list):
        raise FlowValidationError("config.pages must be a list")
    index = find_item_index(pages, page_id)
    if index is None:
        return False
    del pages[index]
    return True


def update_search_check(config: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise FlowValidationError("search_check must be an object")
    section = dict(config.get("search_check") or {})
    section["enabled"] = clean_bool(data.get("enabled", False))
    section["query"] = str(data.get("query") or "").strip()
    section["trigger_selectors"] = clean_lines(data.get("trigger_selectors"))
    section["input_selectors"] = clean_lines(data.get("input_selectors"))
    section["submit_selectors"] = clean_lines(data.get("submit_selectors"))
    section["expected_any_text"] = clean_lines(data.get("expected_any_text"))
    config["search_check"] = section
    return section


def update_link_crawl(config: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise FlowValidationError("link_crawl must be an object")
    section = dict(config.get("link_crawl") or {})
    section["enabled"] = clean_bool(data.get("enabled", False))
    section["max_links"] = clean_int(data.get("max_links"), int(section.get("max_links", 120)), 1)
    section["request_timeout_ms"] = clean_int(
        data.get("request_timeout_ms"),
        int(section.get("request_timeout_ms", 25000)),
        100,
    )
    section["seed_paths"] = clean_lines(data.get("seed_paths"))
    section["ignore_url_keywords"] = clean_lines(data.get("ignore_url_keywords"))
    config["link_crawl"] = section
    return section


def update_ssl(config: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise FlowValidationError("ssl must be an object")
    section = dict(config.get("ssl") or {})
    section["enabled"] = clean_bool(data.get("enabled", False))
    section["port"] = clean_int(data.get("port"), int(section.get("port", 443)), 1)
    section["warn_days"] = clean_int(data.get("warn_days"), int(section.get("warn_days", 30)), 0)
    section["fail_days"] = clean_int(data.get("fail_days"), int(section.get("fail_days", 7)), 0)
    hosts = clean_lines(data.get("hosts"))
    if hosts:
        section["hosts"] = hosts
    else:
        section.pop("hosts", None)
    config["ssl"] = section
    return section


def update_general(config: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise FlowValidationError("general settings must be an object")
    if "target_name" in data:
        config["target_name"] = str(data.get("target_name") or "").strip()
    if "base_url" in data:
        config["base_url"] = str(data.get("base_url") or "").strip()
    if "global_timeout_seconds" in data:
        config["global_timeout_seconds"] = clean_int(data.get("global_timeout_seconds"), 1800, 0)
    if "allowed_hosts" in data:
        config["allowed_hosts"] = clean_lines(data.get("allowed_hosts"))
    if "ignore_url_keywords" in data:
        config["ignore_url_keywords"] = clean_lines(data.get("ignore_url_keywords"))
    return {
        "target_name": config.get("target_name", ""),
        "base_url": config.get("base_url", ""),
        "global_timeout_seconds": config.get("global_timeout_seconds", 1800),
        "allowed_hosts": config.get("allowed_hosts", []),
        "ignore_url_keywords": config.get("ignore_url_keywords", []),
    }


def save_config(path: Path, config: dict[str, Any]) -> Path | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path: Path | None = None
    if path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = path.with_name(f"{path.stem}.{timestamp}.bak{path.suffix}")
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)
    return backup_path


def flow_summary(flow: dict[str, Any]) -> dict[str, Any]:
    steps = flow.get("steps") if isinstance(flow.get("steps"), list) else []
    return {
        "id": flow.get("id", ""),
        "name": flow.get("name", ""),
        "group": flow.get("group", ""),
        "enabled": bool(flow.get("enabled", False)),
        "side_effect": bool(flow.get("side_effect", False)),
        "step_count": len(steps),
        "has_steps": bool(steps),
    }


def page_summary(page: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": page.get("id", ""),
        "name": page.get("name", ""),
        "path": page.get("path", ""),
        "required_text_count": len(page.get("required_texts") or []),
        "title_rule_count": len(page.get("expected_title_contains") or []),
        "full_page_screenshot": bool(page.get("full_page_screenshot", False)),
    }


def latest_report(output_dir: Path) -> dict[str, Any] | None:
    path = output_dir / "latest.json"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        return None
    data["_path"] = str(path)
    return data


def latest_report_summary(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    return {
        "ok": bool(report.get("ok", False)),
        "run_id": report.get("run_id", ""),
        "started_at": report.get("started_at", ""),
        "finished_at": report.get("finished_at", ""),
        "duration_seconds": report.get("duration_seconds", 0),
        "summary": report.get("summary", {}),
        "problem_checks": report.get("problem_checks", []),
        "screenshots": report.get("screenshots", []),
        "path": report.get("_path", ""),
    }


def inventory(config: dict[str, Any], report: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    flows = flow_list(config)
    pages = page_list(config)
    search_cfg = config.get("search_check") or {}
    link_cfg = config.get("link_crawl") or {}
    ssl_cfg = config.get("ssl") or {}
    checks = report.get("checks", []) if isinstance(report, dict) else []
    failed = [item for item in checks if item.get("status") == "fail"]
    warned = [item for item in checks if item.get("status") == "warn"]
    return [
        {
            "id": "pages",
            "name": "Page checks",
            "kind": "built-in",
            "enabled": True,
            "count": len(pages),
            "detail": f"{len(pages)} configured pages",
        },
        {
            "id": "search",
            "name": "Search check",
            "kind": "built-in",
            "enabled": bool(search_cfg.get("enabled", False)),
            "count": 1 if search_cfg else 0,
            "detail": str(search_cfg.get("query", "")),
        },
        {
            "id": "link-crawl",
            "name": "Link crawl",
            "kind": "built-in",
            "enabled": bool(link_cfg.get("enabled", False)),
            "count": int(link_cfg.get("max_links", 0) or 0),
            "detail": f"max {link_cfg.get('max_links', 0)} links",
        },
        {
            "id": "ssl",
            "name": "SSL certificate",
            "kind": "built-in",
            "enabled": bool(ssl_cfg.get("enabled", False)),
            "count": len(ssl_cfg.get("hosts") or config.get("allowed_hosts") or []),
            "detail": f"warn {ssl_cfg.get('warn_days', 30)}d / fail {ssl_cfg.get('fail_days', 7)}d",
        },
        {
            "id": "flows",
            "name": "User flows",
            "kind": "custom",
            "enabled": bool((config.get(FLOW_SECTION) or {}).get("enabled", False)),
            "count": len([flow for flow in flows if flow.get("enabled", False)]),
            "detail": f"{len(flows)} total flows",
        },
        {
            "id": "latest",
            "name": "Latest run",
            "kind": "result",
            "enabled": bool(report),
            "count": len(failed) + len(warned),
            "detail": "no report" if not report else f"{len(failed)} fail / {len(warned)} warn",
        },
    ]


def editor_payload(config: dict[str, Any], output_dir: Path | None = None) -> dict[str, Any]:
    section = ensure_flow_section(config)
    flows = flow_list(config)
    pages = page_list(config)
    report = latest_report(output_dir) if output_dir else None
    return {
        "target_name": config.get("target_name", ""),
        "base_url": config.get("base_url", ""),
        "global_timeout_seconds": config.get("global_timeout_seconds", 1800),
        "allowed_hosts": config.get("allowed_hosts", []),
        "ignore_url_keywords": config.get("ignore_url_keywords", []),
        "pages": pages,
        "page_summaries": [page_summary(page) for page in pages],
        "search_check": config.get("search_check", {}),
        "link_crawl": config.get("link_crawl", {}),
        "ssl": config.get("ssl", {}),
        "flow_enabled": bool(section.get("enabled", False)),
        "flows": flows,
        "summaries": [flow_summary(flow) for flow in flows],
        "supported_actions": sorted(SUPPORTED_ACTIONS),
        "inventory": inventory(config, report),
        "latest_report": latest_report_summary(report),
    }
