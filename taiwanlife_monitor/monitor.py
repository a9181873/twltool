#!/usr/bin/env python3
"""Taiwan Life website synthetic monitor.

The monitor is intentionally dependency-light. Playwright is imported lazily so
configuration, report generation, and SMTP alerting can still be tested before
browser dependencies are installed.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import re
import smtplib
import socket
import ssl
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urldefrag, urljoin, urlparse, urlunparse


TAIPEI_TZ = timezone(timedelta(hours=8), "Asia/Taipei")
VERSION = "0.2.0"
RESOURCE_TYPES = {"document", "script", "stylesheet", "image", "font", "xhr", "fetch"}
MAX_DETAIL_CHARS = 500
MAX_ERROR_CHARS = 320
URL_RE = re.compile(r"https?://[^\s)>'\"]+")
SENSITIVE_KEYWORDS = (
    "token",
    "secret",
    "password",
    "passwd",
    "pwd",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "session",
    "sid",
    "cookie",
    "jwt",
)


@dataclass
class CheckResult:
    id: str
    name: str
    status: str
    detail: str
    elapsed_ms: int = 0
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        data = {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "elapsed_ms": self.elapsed_ms,
        }
        if self.evidence:
            data["evidence"] = self.evidence
        return data


def taipei_now() -> datetime:
    return datetime.now(TAIPEI_TZ)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    chmod_quietly(path, 0o640)


def chmod_quietly(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except Exception:
        return


def safe_slug(value: str) -> str:
    keep = []
    for ch in value.lower():
        if ch.isascii() and ch.isalnum():
            keep.append(ch)
        elif ch in {"-", "_"}:
            keep.append(ch)
        else:
            keep.append("-")
    slug = "".join(keep).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "page"


def elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def has_bad_status(status: int) -> bool:
    return status >= 400 or status == 0


def status_rank(status: str) -> int:
    return {"pass": 0, "warn": 1, "fail": 2}.get(status, 2)


def worst_status(*statuses: str) -> str:
    return max(statuses, key=status_rank)


def env_or_value(value: str | None, env_name: str | None, default: str = "") -> str:
    if env_name and os.getenv(env_name):
        return os.getenv(env_name, default)
    return value or default


def truthy_env(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def split_emails(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return [item.strip() for item in value if item.strip()]
    return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]


def ignored(url: str, patterns: list[str]) -> bool:
    lowered = url.lower()
    return any(pattern.lower() in lowered for pattern in patterns)


def unique_items(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def problem_checks_from_report(report: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    for item in report.get("checks", []):
        if item.get("status") == "pass":
            continue
        problem = {
            "id": item.get("id", ""),
            "name": item.get("name", ""),
            "status": item.get("status", ""),
            "detail": item.get("detail", ""),
        }
        evidence = item.get("evidence") or {}
        if isinstance(evidence, dict):
            if evidence.get("url"):
                problem["url"] = evidence["url"]
            if evidence.get("screenshot"):
                problem["screenshot"] = evidence["screenshot"]
        problems.append(problem)
        if len(problems) >= limit:
            break
    return problems


def normalize_url(base_url: str, href: str) -> str | None:
    href = (href or "").strip()
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "sms:")):
        return None
    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return None
    return urldefrag(absolute)[0]


def compact_text(value: Any, limit: int = MAX_DETAIL_CHARS) -> str:
    text = " ".join(str(value or "").replace("\x00", "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 14)].rstrip() + "...(已截斷)"


def first_exception_line(exc: BaseException) -> str:
    lines = [line.strip() for line in str(exc).splitlines() if line.strip()]
    if not lines:
        return exc.__class__.__name__
    for line in lines:
        if line.lower().startswith("call log"):
            break
        return line
    return lines[0]


def is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    exact_matches = {"key", "api_key", "apikey", "access_key", "secret_key", "sid"}
    if lowered in exact_matches:
        return True
    return any(keyword in lowered for keyword in SENSITIVE_KEYWORDS)


def sanitize_url(url: str, limit: int = MAX_DETAIL_CHARS) -> str:
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return compact_text(url, limit)
        query_items = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            query_items.append((key, "REDACTED" if is_sensitive_key(key) else value))
        safe = urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                urlencode(query_items, doseq=True),
                "",
            )
        )
        return compact_text(safe, limit)
    except Exception:
        return compact_text(url, limit)


def sanitize_message_text(value: Any, limit: int = MAX_DETAIL_CHARS) -> str:
    text = compact_text(value, limit * 2)
    text = URL_RE.sub(lambda match: sanitize_url(match.group(0)), text)
    return compact_text(text, limit)


def sanitize_evidence(value: Any, key_name: str = "") -> Any:
    if is_sensitive_key(key_name):
        return "<redacted>"
    lowered_key = key_name.lower()
    if lowered_key in {"traceback", "stack", "stacktrace"}:
        return "已省略 stack trace，避免機密或過長內容進入報表"
    if isinstance(value, dict):
        return {str(key): sanitize_evidence(item, str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_evidence(item, key_name) for item in value]
    if isinstance(value, tuple):
        return [sanitize_evidence(item, key_name) for item in value]
    if isinstance(value, str):
        if "url" in lowered_key or value.startswith(("http://", "https://")):
            return sanitize_url(value)
        return sanitize_message_text(value)
    return value


def categorize_error(message: str, exc: BaseException | None = None) -> tuple[str, str, str]:
    lowered = message.lower()
    is_dns_error = bool(exc and isinstance(exc, socket.gaierror))
    is_tls_error = bool(exc and isinstance(exc, ssl.SSLError))
    is_timeout_error = bool(exc and isinstance(exc, (socket.timeout, TimeoutError)))
    error_no = getattr(exc, "errno", None)
    if is_dns_error or any(
        token in lowered
        for token in (
            "err_name_not_resolved",
            "err_name_resolution_failed",
            "enotfound",
            "getaddrinfo",
            "name or service not known",
            "nodename nor servname",
            "temporary failure in name resolution",
        )
    ):
        return (
            "dns",
            "DNS 解析失敗",
            "請確認網域、DNS 伺服器與執行環境出口解析設定",
        )
    if is_tls_error or any(
        token in lowered
        for token in (
            "err_cert",
            "ssl",
            "tls",
            "certificate",
            "cert_authority_invalid",
            "cert_date_invalid",
            "cert_common_name_invalid",
        )
    ):
        return (
            "tls",
            "TLS/SSL 交握或憑證失敗",
            "請確認憑證鏈、到期日、SNI 與中間憑證設定",
        )
    if is_timeout_error or error_no == errno.ETIMEDOUT or any(
        token in lowered for token in ("timeout", "timed out", "err_connection_timed_out")
    ):
        return (
            "timeout",
            "連線或頁面載入逾時",
            "請確認站台回應時間、WAF/CDN 與 n8n/cron 執行環境出口網路",
        )
    if error_no in {errno.ECONNREFUSED, errno.ECONNRESET, errno.EPIPE} or any(
        token in lowered
        for token in (
            "err_connection_refused",
            "err_connection_reset",
            "err_connection_closed",
            "connection refused",
            "connection reset",
            "connection closed",
            "remote end closed",
        )
    ):
        return (
            "connection",
            "連線被拒絕或中斷",
            "請確認服務是否開啟，以及 CDN/WAF/防火牆是否阻擋巡檢來源",
        )
    if error_no in {errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ENETDOWN} or any(
        token in lowered
        for token in (
            "network is unreachable",
            "no route",
            "err_network_changed",
            "err_internet_disconnected",
            "err_tunnel_connection_failed",
            "proxy",
        )
    ):
        return (
            "network",
            "網路路徑異常",
            "請確認執行主機出口網路、Proxy、DNS 與目標站台狀態",
        )
    if any(
        token in lowered
        for token in (
            "executable doesn't exist",
            "browser executable",
            "browser has been closed",
            "target page, context or browser has been closed",
            "browsertype.launch",
        )
    ):
        return (
            "browser",
            "瀏覽器執行環境失敗",
            "請確認 Playwright Chromium 已安裝，且容器具備必要系統套件",
        )
    return (
        "unknown",
        "未預期例外",
        "請查看本次檢查項目與執行環境日誌",
    )


def exception_evidence(exc: BaseException) -> dict[str, str]:
    message = sanitize_message_text(first_exception_line(exc), MAX_ERROR_CHARS)
    error_type, label, hint = categorize_error(str(exc), exc)
    return {
        "error_type": error_type,
        "error_label": label,
        "error_message": message,
        "operator_hint": hint,
    }


def exception_detail(operation: str, exc: BaseException) -> str:
    data = exception_evidence(exc)
    detail = f"{operation}失敗：{data['error_label']}。{data['operator_hint']}"
    if data["error_message"]:
        detail += f"；訊息：{data['error_message']}"
    return compact_text(detail)


class TaiwanLifeMonitor:
    def __init__(self, config: dict[str, Any], output_dir: Path) -> None:
        self.config = config
        self.output_dir = output_dir
        self.results_dir = output_dir / "results"
        self.screenshot_dir = output_dir / "screenshots"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        chmod_quietly(self.output_dir, 0o750)
        chmod_quietly(self.results_dir, 0o750)
        chmod_quietly(self.screenshot_dir, 0o750)
        self.timestamp = taipei_now()
        self.run_id = self.timestamp.strftime("%Y%m%d_%H%M%S")
        self.checks: list[CheckResult] = []
        self.broken_resources: list[dict[str, Any]] = []
        self.broken_links: list[dict[str, Any]] = []
        self.console_errors: list[dict[str, str]] = []
        self.page_errors: list[dict[str, str]] = []
        self.screenshots: list[str] = []

    @property
    def base_url(self) -> str:
        return self.config["base_url"].rstrip("/") + "/"

    @property
    def timeout_ms(self) -> int:
        return int(self.config.get("browser", {}).get("timeout_ms", 45000))

    def retry_call(self, operation: str, fn: Any) -> Any:
        retry_cfg = self.config.get("retry", {})
        if not retry_cfg.get("enabled", True):
            return fn()
        max_attempts = max(1, int(retry_cfg.get("max_attempts", 3)))
        base_delay = max(0.0, float(retry_cfg.get("base_delay_seconds", 1.5)))
        max_delay = max(base_delay, float(retry_cfg.get("max_delay_seconds", 8.0)))
        last_exc: BaseException | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                return fn()
            except Exception as exc:
                last_exc = exc
                if attempt >= max_attempts:
                    raise
                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                time.sleep(delay)
        if last_exc:
            raise last_exc
        raise RuntimeError(f"{operation} retry failed without exception")

    def add_check(
        self,
        check_id: str,
        name: str,
        status: str,
        detail: str,
        start: float,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        self.checks.append(
            CheckResult(
                id=check_id,
                name=name,
                status=status,
                detail=compact_text(detail),
                elapsed_ms=elapsed_ms(start),
                evidence=sanitize_evidence(evidence or {}),
            )
        )

    def close_quietly(self, target: Any, name: str) -> None:
        if not target:
            return
        try:
            target.close()
        except Exception as exc:
            start = time.monotonic()
            self.add_check(
                f"{safe_slug(name)}-close",
                f"{name}關閉",
                "warn",
                exception_detail(f"{name}關閉", exc),
                start,
                exception_evidence(exc),
            )

    def capture_screenshot(
        self, page: Any, filename: str, full_page: bool = False
    ) -> tuple[str | None, dict[str, str] | None]:
        screenshot_path = self.screenshot_dir / filename
        try:
            page.screenshot(path=str(screenshot_path), full_page=full_page)
            chmod_quietly(screenshot_path, 0o640)
            self.screenshots.append(str(screenshot_path))
            return str(screenshot_path), None
        except Exception as exc:
            evidence = exception_evidence(exc)
            evidence["screenshot"] = str(screenshot_path)
            return None, evidence

    def attach_page_listeners(self, page: Any, source: str) -> list[dict[str, Any]]:
        local_resources: list[dict[str, Any]] = []
        ignore_patterns = self.config.get("ignore_url_keywords", [])

        def on_response(response: Any) -> None:
            try:
                request = response.request
                resource_type = getattr(request, "resource_type", "")
                url = response.url
                if resource_type in RESOURCE_TYPES and has_bad_status(response.status):
                    if ignored(url, ignore_patterns):
                        return
                    item = {
                        "source": source,
                        "url": sanitize_url(url),
                        "status": response.status,
                        "type": resource_type,
                    }
                    local_resources.append(item)
                    self.broken_resources.append(item)
            except Exception:
                return

        def on_request_failed(request: Any) -> None:
            try:
                url = request.url
                if ignored(url, ignore_patterns):
                    return
                failure = getattr(request, "failure", "")
                if callable(failure):
                    failure = failure()
                failure_text = compact_text(failure, MAX_ERROR_CHARS)
                error_type, label, hint = categorize_error(failure_text)
                item = {
                    "source": source,
                    "url": sanitize_url(url),
                    "status": "request_failed",
                    "type": getattr(request, "resource_type", ""),
                    "error_type": error_type,
                    "failure": label,
                    "operator_hint": hint,
                    "error_message": failure_text,
                }
                local_resources.append(item)
                self.broken_resources.append(item)
            except Exception:
                return

        def on_console(msg: Any) -> None:
            try:
                if msg.type == "error":
                    self.console_errors.append({"source": source, "text": compact_text(msg.text)})
            except Exception:
                return

        def on_page_error(exc: Exception) -> None:
            data = exception_evidence(exc)
            self.page_errors.append(
                {
                    "source": source,
                    "error_type": data["error_type"],
                    "text": data["error_message"],
                }
            )

        page.on("response", on_response)
        page.on("requestfailed", on_request_failed)
        page.on("console", on_console)
        page.on("pageerror", on_page_error)
        return local_resources

    def ssl_hosts(self) -> list[str]:
        ssl_cfg = self.config.get("ssl", {})
        configured = ssl_cfg.get("hosts")
        if configured:
            return unique_items(configured)
        base_host = urlparse(self.base_url).hostname or ""
        return unique_items([base_host])

    def run_ssl_check(self) -> None:
        ssl_cfg = self.config.get("ssl", {})
        if not ssl_cfg.get("enabled", True):
            return
        port = int(ssl_cfg.get("port", 443))
        warn_days = int(ssl_cfg.get("warn_days", 30))
        fail_days = int(ssl_cfg.get("fail_days", 7))
        for host in self.ssl_hosts():
            start = time.monotonic()
            try:
                # ARM64 OpenSSL 環境在 CERT_REQUIRED 模式下可能遇到 SKI 驗證問題。
                # 改用 ssl.get_server_certificate() 取得 PEM 後用 openssl 解析。
                import subprocess, tempfile
                pem = ssl.get_server_certificate((host, port), timeout=10)
                with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as tf:
                    tf.write(pem)
                    tf.flush()
                    result = subprocess.run(
                        ["openssl", "x509", "-noout", "-enddate", "-in", tf.name],
                        capture_output=True, text=True, timeout=10
                    )
                import os as _os; _os.unlink(tf.name)
                # 輸出格式：notAfter=Jun 15 12:00:00 2026 GMT
                import re as _re
                m = _re.search(r"notAfter=(.+)", result.stdout)
                if not m:
                    raise ValueError(f"openssl parse failed: {result.stdout[:200]}")
                expires = datetime.strptime(m.group(1).strip(), "%b %d %H:%M:%S %Y %Z").replace(
                    tzinfo=timezone.utc
                )
                days_left = (expires - datetime.now(timezone.utc)).days
                status = "pass"
                if days_left < fail_days:
                    status = "fail"
                elif days_left < warn_days:
                    status = "warn"
                self.add_check(
                    f"ssl-{safe_slug(host)}",
                    f"TLS 憑證有效期：{host}",
                    status,
                    f"{host} 憑證剩餘 {days_left} 天，到期日 {expires.astimezone(TAIPEI_TZ).isoformat()}",
                    start,
                    {"host": host, "days_left": days_left},
                )
            except Exception as exc:
                self.add_check(
                    f"ssl-{safe_slug(host)}",
                    f"TLS 憑證有效期：{host}",
                    "fail",
                    exception_detail("TLS 憑證檢查", exc),
                    start,
                    {"host": host, "port": port, **exception_evidence(exc)},
                )

    def run_page_check(self, context: Any, page_cfg: dict[str, Any]) -> None:
        start = time.monotonic()
        name = page_cfg["name"]
        url = urljoin(self.base_url, page_cfg.get("path", "/"))
        evidence: dict[str, Any] = {"url": url}
        page = None
        local_resources: list[dict[str, Any]] = []
        try:
            page = context.new_page()
            page.set_default_timeout(self.timeout_ms)
            local_resources = self.attach_page_listeners(page, name)
            response = self.retry_call(
                f"頁面載入：{name}",
                lambda: page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms),
            )
            try:
                page.wait_for_load_state("networkidle", timeout=int(page_cfg.get("networkidle_ms", 15000)))
            except Exception:
                pass

            title = page.title()
            status_code = response.status if response else 0
            body_text = page.locator("body").inner_text(timeout=5000)
            evidence.update({"http_status": status_code, "title": title})

            missing_text = [text for text in page_cfg.get("required_texts", []) if text not in body_text]
            missing_title = [
                text for text in page_cfg.get("expected_title_contains", []) if text not in title
            ]

            screenshot_name = f"{self.run_id}_{safe_slug(page_cfg.get('id', name))}.png"
            screenshot, screenshot_error = self.capture_screenshot(
                page,
                screenshot_name,
                full_page=bool(page_cfg.get("full_page_screenshot", False)),
            )
            if screenshot:
                evidence["screenshot"] = screenshot
            if screenshot_error:
                evidence["screenshot_error"] = screenshot_error

            status = "pass"
            details = [f"HTTP {status_code}", f"title={title!r}"]
            if has_bad_status(status_code):
                status = "fail"
                details.append("HTTP 狀態異常")
            if missing_title:
                status = "fail"
                details.append("標題缺少 " + ", ".join(missing_title))
            if missing_text:
                status = "fail"
                details.append("頁面缺少關鍵文字 " + ", ".join(missing_text))
                evidence["missing_text"] = missing_text
            if local_resources:
                status = worst_status(status, "fail")
                details.append(f"壞掉的頁面物件 {len(local_resources)} 個")
                evidence["broken_resources"] = local_resources[:10]
            if screenshot_error:
                status = worst_status(status, "warn")
                details.append("截圖失敗")

            self.add_check(page_cfg.get("id", safe_slug(name)), f"頁面巡檢：{name}", status, "; ".join(details), start, evidence)
        except Exception as exc:
            evidence.update(exception_evidence(exc))
            if local_resources:
                evidence["broken_resources"] = local_resources[:10]
            self.add_check(
                page_cfg.get("id", safe_slug(name)),
                f"頁面巡檢：{name}",
                "fail",
                exception_detail(f"頁面巡檢：{name}", exc),
                start,
                evidence,
            )
        finally:
            self.close_quietly(page, f"page-{page_cfg.get('id', safe_slug(name))}")

    def find_first_visible(self, page: Any, selectors: list[str], timeout_ms: int = 2500) -> Any | None:
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if locator.is_visible(timeout=timeout_ms):
                    return locator
            except Exception:
                continue
        return None

    def load_rpa84_scenarios(self) -> list[dict[str, Any]]:
        rpa_cfg = self.config.get("rpa84", {})
        scenarios = rpa_cfg.get("scenarios", [])
        if not isinstance(scenarios, list):
            raise ValueError("config.rpa84.scenarios must be a list")
        return [item for item in scenarios if isinstance(item, dict)]

    def scenario_selectors(self, step: dict[str, Any]) -> list[str]:
        selectors = step.get("selectors", [])
        if isinstance(selectors, str):
            return [selectors]
        return [str(item) for item in selectors if item]

    def run_scenario_step(
        self,
        page: Any,
        scenario: dict[str, Any],
        step: dict[str, Any],
        evidence: dict[str, Any],
    ) -> None:
        action = step.get("action")
        optional = bool(step.get("optional", False))
        label = step.get("name") or action or "未命名步驟"
        step_record: dict[str, Any] = {"name": label, "action": action}
        evidence.setdefault("steps", []).append(step_record)

        try:
            if action == "goto":
                url = step.get("url") or urljoin(self.base_url, step.get("path", "/"))
                step_record["url"] = sanitize_url(url)
                self.retry_call(
                    f"RPA84 {scenario.get('id')} 開頁",
                    lambda: page.goto(url, wait_until=step.get("wait_until", "domcontentloaded"), timeout=self.timeout_ms),
                )
            elif action == "wait_for_load_state":
                page.wait_for_load_state(step.get("state", "networkidle"), timeout=int(step.get("timeout_ms", 15000)))
            elif action == "wait":
                page.wait_for_timeout(int(step.get("milliseconds", 1000)))
            elif action in {"click_first", "fill_first", "press_first"}:
                selectors = self.scenario_selectors(step)
                locator = self.find_first_visible(page, selectors, int(step.get("timeout_ms", 3500)))
                if not locator:
                    raise LookupError(f"找不到可操作元素：{', '.join(selectors)}")
                step_record["selector_count"] = len(selectors)
                if action == "click_first":
                    locator.click(timeout=int(step.get("click_timeout_ms", 5000)))
                elif action == "fill_first":
                    locator.fill(str(step.get("value", "")))
                else:
                    locator.press(str(step.get("key", "Enter")))
            elif action == "assert_any_text":
                texts = [str(item) for item in step.get("texts", []) if item]
                body_text = page.locator("body").inner_text(timeout=int(step.get("timeout_ms", 5000)))
                title = page.title()
                haystack = "\n".join([body_text, title, page.url])
                matched = [text for text in texts if text in haystack]
                step_record["matched"] = matched
                if not matched:
                    raise AssertionError("未看到任一預期文字：" + ", ".join(texts))
            elif action == "assert_all_text":
                texts = [str(item) for item in step.get("texts", []) if item]
                body_text = page.locator("body").inner_text(timeout=int(step.get("timeout_ms", 5000)))
                title = page.title()
                haystack = "\n".join([body_text, title, page.url])
                missing = [text for text in texts if text not in haystack]
                step_record["missing"] = missing
                if missing:
                    raise AssertionError("缺少預期文字：" + ", ".join(missing))
            elif action == "screenshot":
                name = step.get("filename") or f"{self.run_id}_{safe_slug(str(scenario.get('id', 'rpa84')))}.png"
                screenshot, screenshot_error = self.capture_screenshot(
                    page,
                    str(name),
                    full_page=bool(step.get("full_page", False)),
                )
                if screenshot:
                    step_record["screenshot"] = screenshot
                    evidence["screenshot"] = screenshot
                if screenshot_error:
                    step_record["screenshot_error"] = screenshot_error
                    raise RuntimeError("截圖失敗")
            elif action == "manual_note":
                step_record["note"] = step.get("note", "")
            else:
                raise ValueError(f"不支援的 RPA84 動作：{action}")
            step_record["status"] = "pass"
        except Exception as exc:
            if optional:
                step_record["status"] = "skip"
                step_record["detail"] = compact_text(exc)
                return
            step_record["status"] = "fail"
            step_record["detail"] = compact_text(exc)
            raise

    def run_rpa84_scenario(self, context: Any, scenario: dict[str, Any]) -> None:
        start = time.monotonic()
        scenario_id = str(scenario.get("id") or safe_slug(str(scenario.get("name", "rpa84"))))
        name = str(scenario.get("name") or scenario_id)
        evidence: dict[str, Any] = {
            "scenario_id": scenario_id,
            "group": scenario.get("group", ""),
            "input": scenario.get("input", {}),
            "acceptance": scenario.get("acceptance", []),
            "side_effect": bool(scenario.get("side_effect", False)),
        }
        page = None
        local_resources: list[dict[str, Any]] = []
        try:
            steps = scenario.get("steps", [])
            if not steps:
                self.add_check(
                    f"rpa84-{safe_slug(scenario_id)}",
                    f"RPA84：{name}",
                    "warn",
                    "已建立需求項目，但尚未設定自動化步驟",
                    start,
                    evidence,
                )
                return

            page = context.new_page()
            page.set_default_timeout(self.timeout_ms)
            local_resources = self.attach_page_listeners(page, f"RPA84：{name}")
            for step in steps:
                self.run_scenario_step(page, scenario, step, evidence)

            status = "pass"
            detail = "流程完成並符合設定驗收條件"
            if local_resources:
                status = "fail"
                detail += f"；流程中有壞掉物件 {len(local_resources)} 個"
                evidence["broken_resources"] = local_resources[:10]
            self.add_check(f"rpa84-{safe_slug(scenario_id)}", f"RPA84：{name}", status, detail, start, evidence)
        except Exception as exc:
            evidence.update(exception_evidence(exc))
            if local_resources:
                evidence["broken_resources"] = local_resources[:10]
            self.add_check(
                f"rpa84-{safe_slug(scenario_id)}",
                f"RPA84：{name}",
                "fail",
                exception_detail(f"RPA84：{name}", exc),
                start,
                evidence,
            )
        finally:
            self.close_quietly(page, f"rpa84-{scenario_id}")

    def run_rpa84_scenarios(self, context: Any) -> None:
        rpa_cfg = self.config.get("rpa84", {})
        if not rpa_cfg.get("enabled", False):
            return
        start = time.monotonic()
        try:
            scenarios = self.load_rpa84_scenarios()
        except Exception as exc:
            self.add_check(
                "rpa84-config",
                "RPA84 場景設定",
                "fail",
                exception_detail("RPA84 場景設定", exc),
                start,
                exception_evidence(exc),
            )
            return

        enabled = [item for item in scenarios if item.get("enabled", False)]
        self.add_check(
            "rpa84-inventory",
            "RPA84 需求清單",
            "pass" if enabled else "warn",
            f"已載入 {len(scenarios)} 個需求項目，啟用 {len(enabled)} 個自動化場景",
            start,
            {"total": len(scenarios), "enabled": len(enabled)},
        )
        for scenario in enabled:
            self.run_rpa84_scenario(context, scenario)

    def run_search_check(self, context: Any) -> None:
        search_cfg = self.config.get("search_check", {})
        if not search_cfg.get("enabled", True):
            return
        start = time.monotonic()
        query = search_cfg.get("query", "壽險")
        evidence: dict[str, Any] = {"query": query}
        page = None
        local_resources: list[dict[str, Any]] = []
        try:
            page = context.new_page()
            page.set_default_timeout(self.timeout_ms)
            local_resources = self.attach_page_listeners(page, "站內搜尋")
            self.retry_call(
                "搜尋頁載入",
                lambda: page.goto(self.base_url, wait_until="domcontentloaded", timeout=self.timeout_ms),
            )
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

            trigger = self.find_first_visible(page, search_cfg.get("trigger_selectors", []), 2500)
            if trigger:
                try:
                    trigger.click(timeout=5000)
                    page.wait_for_timeout(800)
                except Exception:
                    pass

            input_box = self.find_first_visible(page, search_cfg.get("input_selectors", []), 3500)
            if not input_box:
                if local_resources:
                    evidence["broken_resources"] = local_resources[:10]
                self.add_check(
                    "search",
                    "站內搜尋功能",
                    "fail",
                    "找不到可輸入的搜尋框",
                    start,
                    evidence,
                )
                return

            before_url = page.url
            self.retry_call("搜尋輸入", lambda: input_box.fill(query))
            try:
                self.retry_call("搜尋送出", lambda: input_box.press("Enter"))
            except Exception:
                button = self.find_first_visible(page, search_cfg.get("submit_selectors", []), 2000)
                if button:
                    self.retry_call("搜尋按鈕點擊", lambda: button.click(timeout=5000))
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                page.wait_for_timeout(2500)

            body_text = page.locator("body").inner_text(timeout=5000)
            title = page.title()
            evidence.update({"before_url": before_url, "after_url": page.url, "title": title})
            expected = search_cfg.get("expected_any_text", [query, "搜尋結果"])
            matched = [text for text in expected if text in body_text or text in title or text in page.url]
            status = "pass" if matched else "fail"
            detail = "搜尋有回應：" + ", ".join(matched) if matched else "搜尋後未看到預期結果文字"
            if local_resources:
                status = worst_status(status, "fail")
                detail += f"; 搜尋過程有壞掉物件 {len(local_resources)} 個"
                evidence["broken_resources"] = local_resources[:10]

            screenshot_name = f"{self.run_id}_search.png"
            screenshot, screenshot_error = self.capture_screenshot(page, screenshot_name, full_page=False)
            if screenshot:
                evidence["screenshot"] = screenshot
            if screenshot_error:
                status = worst_status(status, "warn")
                detail += "; 截圖失敗"
                evidence["screenshot_error"] = screenshot_error
            self.add_check("search", "站內搜尋功能", status, detail, start, evidence)
        except Exception as exc:
            evidence.update(exception_evidence(exc))
            if local_resources:
                evidence["broken_resources"] = local_resources[:10]
            self.add_check(
                "search",
                "站內搜尋功能",
                "fail",
                exception_detail("站內搜尋功能", exc),
                start,
                evidence,
            )
        finally:
            self.close_quietly(page, "search-page")

    def collect_links(self, context: Any) -> tuple[list[str], list[dict[str, Any]]]:
        crawl_cfg = self.config.get("link_crawl", {})
        start_pages = crawl_cfg.get("seed_paths") or [page.get("path", "/") for page in self.config.get("pages", [])]
        include_hosts = set(crawl_cfg.get("include_hosts") or self.config.get("allowed_hosts", []))
        ignore_patterns = self.config.get("ignore_url_keywords", []) + crawl_cfg.get("ignore_url_keywords", [])
        links: set[str] = set()
        seed_errors: list[dict[str, Any]] = []
        for path in start_pages:
            page = None
            seed_url = urljoin(self.base_url, path)
            try:
                page = context.new_page()
                page.set_default_timeout(self.timeout_ms)
                self.retry_call(
                    f"連結種子頁載入：{seed_url}",
                    lambda: page.goto(seed_url, wait_until="domcontentloaded", timeout=self.timeout_ms),
                )
                raw_links = page.locator("a[href]").evaluate_all("els => els.map(a => a.href)")
                for raw in raw_links:
                    url = normalize_url(self.base_url, raw)
                    if not url or ignored(url, ignore_patterns):
                        continue
                    host = urlparse(url).hostname or ""
                    if include_hosts and host not in include_hosts:
                        continue
                    links.add(url)
            except Exception as exc:
                seed_errors.append({"url": seed_url, **exception_evidence(exc)})
                continue
            finally:
                self.close_quietly(page, "link-seed-page")
        return sorted(links), seed_errors

    def run_link_crawl(self, context: Any) -> None:
        crawl_cfg = self.config.get("link_crawl", {})
        if not crawl_cfg.get("enabled", True):
            return
        start = time.monotonic()
        max_links = int(crawl_cfg.get("max_links", 120))
        links, seed_errors = self.collect_links(context)
        links = links[:max_links]
        timeout = int(crawl_cfg.get("request_timeout_ms", 25000))
        evidence: dict[str, Any] = {"checked": len(links), "max_links": max_links}
        if seed_errors:
            evidence["seed_errors"] = seed_errors[:10]
            evidence["seed_error_count"] = len(seed_errors)
        for url in links:
            try:
                response = self.retry_call(
                    f"連結檢查：{url}",
                    lambda: context.request.get(url, timeout=timeout, max_redirects=5),
                )
                if has_bad_status(response.status):
                    item = {"url": sanitize_url(url), "status": response.status}
                    self.broken_links.append(item)
            except Exception as exc:
                data = exception_evidence(exc)
                self.broken_links.append(
                    {
                        "url": sanitize_url(url),
                        "status": "error",
                        "error_type": data["error_type"],
                        "error": data["error_label"],
                        "operator_hint": data["operator_hint"],
                        "error_message": data["error_message"],
                    }
                )

        if self.broken_links:
            evidence["broken_links"] = self.broken_links[:25]
            detail = f"抽查 {len(links)} 個內部連結，異常 {len(self.broken_links)} 個"
            self.add_check("link-crawl", "內部連結可用性", "fail", detail, start, evidence)
        elif not links and seed_errors:
            detail = f"無法收集內部連結，種子頁異常 {len(seed_errors)} 個"
            self.add_check("link-crawl", "內部連結可用性", "fail", detail, start, evidence)
        elif seed_errors:
            detail = f"抽查 {len(links)} 個內部連結皆可用；但種子頁異常 {len(seed_errors)} 個"
            self.add_check("link-crawl", "內部連結可用性", "warn", detail, start, evidence)
        else:
            self.add_check("link-crawl", "內部連結可用性", "pass", f"抽查 {len(links)} 個內部連結皆可用", start, evidence)

    def run_browser_checks(self) -> None:
        start = time.monotonic()
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.add_check(
                "playwright",
                "瀏覽器依賴",
                "fail",
                "尚未安裝 Playwright，請執行 pip install -r requirements.txt 與 playwright install chromium",
                start,
            )
            return

        browser_cfg = self.config.get("browser", {})
        try:
            with sync_playwright() as playwright:
                browser = None
                context = None
                try:
                    launch_kwargs: dict[str, Any] = {
                        "headless": bool(browser_cfg.get("headless", True)),
                        "args": browser_cfg.get(
                            "args",
                            [
                                "--no-sandbox",
                                "--disable-setuid-sandbox",
                                "--disable-dev-shm-usage",
                                "--disable-gpu",
                            ],
                        ),
                    }
                    executable_path = os.environ.get(
                        "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", ""
                    ) or browser_cfg.get("executable_path", "")
                    if executable_path:
                        launch_kwargs["executable_path"] = executable_path
                    browser = playwright.chromium.launch(**launch_kwargs)
                except Exception as exc:
                    self.add_check(
                        "browser-launch",
                        "瀏覽器啟動",
                        "fail",
                        exception_detail("瀏覽器啟動", exc),
                        start,
                        exception_evidence(exc),
                    )
                    return

                try:
                    context = browser.new_context(
                        viewport=browser_cfg.get("viewport", {"width": 1920, "height": 1080}),
                        locale=browser_cfg.get("locale", "zh-TW"),
                        timezone_id=browser_cfg.get("timezone_id", "Asia/Taipei"),
                        user_agent=browser_cfg.get("user_agent"),
                        ignore_https_errors=bool(browser_cfg.get("ignore_https_errors", False)),
                        extra_http_headers=browser_cfg.get("extra_http_headers", {}),
                    )
                except Exception as exc:
                    self.add_check(
                        "browser-context",
                        "瀏覽器 Context 建立",
                        "fail",
                        exception_detail("瀏覽器 Context 建立", exc),
                        start,
                        exception_evidence(exc),
                    )
                    self.close_quietly(browser, "browser")
                    return

                try:
                    for page_cfg in self.config.get("pages", []):
                        try:
                            self.run_page_check(context, page_cfg)
                        except Exception as exc:
                            self.add_check(
                                page_cfg.get("id", safe_slug(page_cfg.get("name", "page"))),
                                f"頁面巡檢：{page_cfg.get('name', page_cfg.get('path', '未命名頁面'))}",
                                "fail",
                                exception_detail("頁面巡檢", exc),
                                start,
                                {"url": urljoin(self.base_url, page_cfg.get("path", "/")), **exception_evidence(exc)},
                            )
                    try:
                        self.run_search_check(context)
                    except Exception as exc:
                        self.add_check(
                            "search",
                            "站內搜尋功能",
                            "fail",
                            exception_detail("站內搜尋功能", exc),
                            start,
                            exception_evidence(exc),
                        )
                    try:
                        self.run_rpa84_scenarios(context)
                    except Exception as exc:
                        self.add_check(
                            "rpa84",
                            "RPA84 功能流程",
                            "fail",
                            exception_detail("RPA84 功能流程", exc),
                            start,
                            exception_evidence(exc),
                        )
                    try:
                        self.run_link_crawl(context)
                    except Exception as exc:
                        self.add_check(
                            "link-crawl",
                            "內部連結可用性",
                            "fail",
                            exception_detail("內部連結可用性", exc),
                            start,
                            exception_evidence(exc),
                        )
                finally:
                    self.close_quietly(context, "browser-context")
                    self.close_quietly(browser, "browser")
        except Exception as exc:
            self.add_check(
                "playwright-runtime",
                "Playwright 執行",
                "fail",
                exception_detail("Playwright 執行", exc),
                start,
                exception_evidence(exc),
            )

    def summary(self) -> dict[str, int]:
        return {
            "total": len(self.checks),
            "pass": sum(1 for item in self.checks if item.status == "pass"),
            "warn": sum(1 for item in self.checks if item.status == "warn"),
            "fail": sum(1 for item in self.checks if item.status == "fail"),
        }

    def build_report(self, started_at: datetime, duration_seconds: float) -> dict[str, Any]:
        summary = self.summary()
        return {
            "schema_version": "1.0",
            "run_id": self.run_id,
            "target_name": self.config.get("target_name", "台灣人壽官網"),
            "base_url": self.base_url,
            "scheduler": self.config.get("_runtime_scheduler", "manual"),
            "started_at": started_at.isoformat(),
            "finished_at": taipei_now().isoformat(),
            "duration_seconds": round(duration_seconds, 2),
            "ok": summary["fail"] == 0,
            "summary": summary,
            "checks": [item.as_dict() for item in self.checks],
            "broken_resources": self.broken_resources[:100],
            "broken_links": self.broken_links[:100],
            "console_errors": self.console_errors[:50],
            "page_errors": self.page_errors[:50],
            "screenshots": self.screenshots,
        }

    def write_markdown(self, report: dict[str, Any], path: Path) -> None:
        lines = [
            f"# {report['target_name']}巡檢報告",
            "",
            f"- 執行時間：{report['started_at']}",
            f"- 目標網址：{report['base_url']}",
            f"- 總耗時：{report['duration_seconds']} 秒",
            f"- 結果：PASS {report['summary']['pass']} / WARN {report['summary']['warn']} / FAIL {report['summary']['fail']}",
            "",
            "## 檢查明細",
            "",
            "| ID | 項目 | 狀態 | 耗時(ms) | 細節 |",
            "|---|---|---|---:|---|",
        ]
        for item in report["checks"]:
            detail = str(item["detail"]).replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| {item['id']} | {item['name']} | {item['status'].upper()} | {item['elapsed_ms']} | {detail} |"
            )
        if report["broken_resources"]:
            lines.extend(["", "## 壞掉的頁面物件", ""])
            for item in report["broken_resources"][:25]:
                lines.append(f"- {item.get('status')} {item.get('type')} {item.get('url')}")
        if report["broken_links"]:
            lines.extend(["", "## 異常連結", ""])
            for item in report["broken_links"][:25]:
                lines.append(f"- {item.get('status')} {item.get('url')}")
        if report["screenshots"]:
            lines.extend(["", "## 截圖", ""])
            for screenshot in report["screenshots"]:
                lines.append(f"- {screenshot}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        chmod_quietly(path, 0o640)

    def cleanup_old_outputs(self) -> None:
        retention = self.config.get("retention", {})
        if not retention.get("enabled", True):
            return

        result_days = int(retention.get("result_days", 90))
        screenshot_days = int(retention.get("screenshot_days", 30))
        now = time.time()

        def cleanup_dir(directory: Path, days: int, patterns: tuple[str, ...]) -> int:
            if days <= 0:
                return 0
            cutoff = now - (days * 86400)
            removed = 0
            for pattern in patterns:
                for path in directory.glob(pattern):
                    try:
                        if not path.is_file():
                            continue
                        if path.name.startswith("latest."):
                            continue
                        if path.stat().st_mtime < cutoff:
                            path.unlink()
                            removed += 1
                    except Exception:
                        continue
            return removed

        removed_results = cleanup_dir(self.results_dir, result_days, ("*.json", "*.md"))
        removed_screenshots = cleanup_dir(self.screenshot_dir, screenshot_days, ("*.png", "*.jpg", "*.jpeg"))
        if removed_results or removed_screenshots:
            start = time.monotonic()
            self.add_check(
                "retention-cleanup",
                "報表保留期限清理",
                "pass",
                f"已清理歷史報表 {removed_results} 個、截圖 {removed_screenshots} 個",
                start,
            )

    def run(self) -> tuple[dict[str, Any], Path, Path]:
        started_at = taipei_now()
        start = time.monotonic()
        self.run_ssl_check()
        self.run_browser_checks()
        self.cleanup_old_outputs()
        report = self.build_report(started_at, time.monotonic() - start)
        json_path = self.results_dir / f"{self.run_id}.json"
        md_path = self.results_dir / f"{self.run_id}.md"
        write_json(json_path, report)
        self.write_markdown(report, md_path)
        (self.output_dir / "latest.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (self.output_dir / "latest.md").write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
        chmod_quietly(self.output_dir / "latest.json", 0o640)
        chmod_quietly(self.output_dir / "latest.md", 0o640)
        return report, json_path, md_path


def send_email_alert(report: dict[str, Any], md_path: Path, json_path: Path, config: dict[str, Any], always: bool = False) -> bool:
    email_cfg = config.get("alerts", {}).get("email", {})
    email_enabled = bool(email_cfg.get("enabled", False))
    env_email_enabled = truthy_env("ALERT_EMAIL_ENABLED")
    if env_email_enabled is not None:
        email_enabled = env_email_enabled
    if not email_enabled:
        return False
    summary = report.get("summary", {})
    has_problem = int(summary.get("fail", 0)) > 0 or int(summary.get("warn", 0)) > 0
    if not has_problem and not always:
        return False

    host = env_or_value(email_cfg.get("host"), email_cfg.get("host_env"), "localhost")
    port = int(env_or_value(str(email_cfg.get("port", 25)), email_cfg.get("port_env"), "25"))
    username = env_or_value(email_cfg.get("username"), email_cfg.get("username_env"))
    password = env_or_value(email_cfg.get("password"), email_cfg.get("password_env"))
    sender = env_or_value(email_cfg.get("from"), email_cfg.get("from_env"))
    to_value = env_or_value(email_cfg.get("to"), email_cfg.get("to_env"))
    recipients = split_emails(to_value)
    if not sender or not recipients:
        raise ValueError("Email alert needs sender and recipients. Check ALERT_FROM and ALERT_TO.")

    status_label = "OK"
    if int(summary.get("fail", 0)) > 0:
        status_label = "FAIL"
    elif int(summary.get("warn", 0)) > 0:
        status_label = "WARN"
    subject_prefix = email_cfg.get("subject_prefix", "[台壽官網巡檢]")
    subject = (
        f"{subject_prefix} {status_label} "
        f"fail={summary.get('fail', 0)} warn={summary.get('warn', 0)}"
    )
    markdown = md_path.read_text(encoding="utf-8")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(markdown)
    msg.add_attachment(
        json_path.read_bytes(),
        maintype="application",
        subtype="json",
        filename=json_path.name,
    )

    timeout = int(email_cfg.get("timeout_seconds", 20))
    use_starttls = bool(email_cfg.get("starttls", True))
    with smtplib.SMTP(host, port, timeout=timeout) as smtp:
        if use_starttls:
            smtp.starttls(context=ssl.create_default_context())
        if username:
            smtp.login(username, password)
        smtp.send_message(msg)
    return True


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="台灣人壽官網自動巡檢工具")
    parser.add_argument("--config", default="config/taiwanlife.json", help="監控設定 JSON")
    parser.add_argument("--output-dir", default="reports", help="報表輸出資料夾")
    parser.add_argument("--scheduler", default=os.environ.get("MONITOR_SCHEDULER", "manual"), help="排程來源標籤，例如 windows-task-scheduler、power-automate、n8n")
    parser.add_argument("--enable-rpa84", action="store_true", help="啟用 RPA84 功能場景")
    parser.add_argument("--health-check", action="store_true", help="只輸出工具健康狀態，不執行巡檢")
    parser.add_argument("--email-on-fail", action="store_true", help="異常時透過 SMTP 寄送警示")
    parser.add_argument("--always-email", action="store_true", help="不論成功或失敗都寄送 Email")
    parser.add_argument("--fail-exit-code", action="store_true", help="發現 fail 時以 exit code 2 結束")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.health_check:
        payload = {
            "status": "ok",
            "version": VERSION,
            "timestamp": taipei_now().isoformat(),
            "python": sys.version.split()[0],
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    try:
        config_path = Path(args.config)
        config = load_json(config_path)
        config["_config_dir"] = str(config_path.resolve().parent)
        config["_runtime_scheduler"] = args.scheduler
        env_enable_rpa84 = truthy_env("MONITOR_ENABLE_RPA84")
        if args.enable_rpa84 or env_enable_rpa84:
            config.setdefault("rpa84", {})["enabled"] = True
        monitor = TaiwanLifeMonitor(config, Path(args.output_dir))
        report, json_path, md_path = monitor.run()

        email_sent = False
        email_error: dict[str, str] | None = None
        if args.email_on_fail or args.always_email:
            try:
                email_sent = send_email_alert(report, md_path, json_path, config, always=args.always_email)
            except Exception as exc:
                email_error = exception_evidence(exc)

        n8n_payload = {
            "ok": report["ok"],
            "run_id": report["run_id"],
            "target_name": report["target_name"],
            "scheduler": report.get("scheduler", args.scheduler),
            "summary": report["summary"],
            "problem_checks": problem_checks_from_report(report),
            "latest_json": str(json_path),
            "latest_md": str(md_path),
            "screenshots": report.get("screenshots", []),
            "email_sent": email_sent,
            "summary_text": (
                f"{report['target_name']} {report['started_at']} "
                f"PASS={report['summary']['pass']} WARN={report['summary']['warn']} FAIL={report['summary']['fail']}"
            ),
        }
        if email_error:
            n8n_payload["email_error"] = email_error
        print(json.dumps(n8n_payload, ensure_ascii=False))
        if args.fail_exit_code and report["summary"]["fail"] > 0:
            return 2
        return 0
    except Exception as exc:
        now = taipei_now()
        error = exception_evidence(exc)
        payload = {
            "ok": False,
            "run_id": now.strftime("%Y%m%d_%H%M%S"),
            "target_name": "台灣人壽官網",
            "scheduler": args.scheduler,
            "summary": {"total": 1, "pass": 0, "warn": 0, "fail": 1},
            "problem_checks": [
                {
                    "id": "runtime",
                    "name": "巡檢執行",
                    "status": "fail",
                    "detail": error["error_message"],
                }
            ],
            "latest_json": "",
            "latest_md": "",
            "screenshots": [],
            "email_sent": False,
            "error": error,
            "summary_text": f"台灣人壽官網 {now.isoformat()} PASS=0 WARN=0 FAIL=1",
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 2 if args.fail_exit_code else 1


if __name__ == "__main__":
    raise SystemExit(main())
