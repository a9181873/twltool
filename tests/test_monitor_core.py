import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from taiwanlife_monitor.monitor import (
    CheckResult,
    TAIPEI_TZ,
    TaiwanLifeMonitor,
    env_or_value,
    has_bad_status,
    load_json,
    normalize_url,
    safe_slug,
    send_email_alert,
    split_emails,
    worst_status,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]


class FakePage:
    def __init__(self):
        self.handlers = {}

    def on(self, event_name, handler):
        self.handlers[event_name] = handler


class FakeRequest:
    def __init__(self, url, resource_type="document", failure="net::ERR_FAILED"):
        self.url = url
        self.resource_type = resource_type
        self._failure = failure

    def failure(self):
        return self._failure


class FakeResponse:
    def __init__(self, url, status, resource_type="document"):
        self.url = url
        self.status = status
        self.request = FakeRequest(url, resource_type=resource_type)


class FakeConsoleMessage:
    def __init__(self, message_type, text):
        self.type = message_type
        self.text = text


class RecordingSMTP:
    instances = []

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.login_args = None
        self.sent_messages = []
        RecordingSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def starttls(self, context=None):
        self.started_tls = True

    def login(self, username, password):
        self.login_args = (username, password)

    def send_message(self, message):
        self.sent_messages.append(message)


def make_monitor(config=None):
    base_config = {
        "target_name": "測試站",
        "base_url": "https://example.com/app",
        "ignore_url_keywords": ["ignored-cdn"],
        "browser": {"timeout_ms": 12345},
    }
    if config:
        base_config.update(config)
    tmp = tempfile.TemporaryDirectory()
    monitor = TaiwanLifeMonitor(base_config, Path(tmp.name))
    return tmp, monitor


class HelperFunctionTests(unittest.TestCase):
    def test_url_status_and_recipient_helpers(self):
        self.assertEqual(safe_slug("首頁 / Product_01"), "product_01")
        self.assertEqual(safe_slug("中文頁面"), "page")
        self.assertTrue(has_bad_status(0))
        self.assertTrue(has_bad_status(500))
        self.assertFalse(has_bad_status(399))
        self.assertEqual(worst_status("pass", "warn", "fail"), "fail")
        self.assertEqual(split_emails("a@example.com; b@example.com, c@example.com"), [
            "a@example.com",
            "b@example.com",
            "c@example.com",
        ])

    def test_env_value_prefers_environment_when_present(self):
        with patch.dict(os.environ, {"SMTP_PORT": "2525"}):
            self.assertEqual(env_or_value("25", "SMTP_PORT", "25"), "2525")
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(env_or_value("25", "SMTP_PORT", "25"), "25")
            self.assertEqual(env_or_value(None, "MISSING_VALUE", "fallback"), "fallback")

    def test_normalize_url_accepts_http_links_only_and_drops_fragments(self):
        self.assertEqual(
            normalize_url("https://example.com/base/", "../news#top"),
            "https://example.com/news",
        )
        self.assertIsNone(normalize_url("https://example.com/", "mailto:test@example.com"))
        self.assertIsNone(normalize_url("https://example.com/", "javascript:void(0)"))
        self.assertIsNone(normalize_url("https://example.com/", "ftp://example.com/file"))


class ConfigLoadingTests(unittest.TestCase):
    def test_loads_default_config_without_browser_or_network(self):
        config = load_json(ROOT / "config" / "taiwanlife.json")

        self.assertEqual(config["target_name"], "台灣人壽官網")
        self.assertEqual(config["base_url"], "https://www.taiwanlife.com/")
        self.assertGreaterEqual(len(config["pages"]), 1)
        self.assertIn("alerts", config)
        self.assertIn("email", config["alerts"])

        with tempfile.TemporaryDirectory() as tmp:
            monitor = TaiwanLifeMonitor(config, Path(tmp))
            self.assertEqual(monitor.base_url, "https://www.taiwanlife.com/")
            self.assertEqual(monitor.timeout_ms, 45000)
            self.assertTrue((Path(tmp) / "results").is_dir())
            self.assertTrue((Path(tmp) / "screenshots").is_dir())


class ListenerRegressionTests(unittest.TestCase):
    def test_attach_page_listeners_records_failures_and_ignores_configured_urls(self):
        tmp, monitor = make_monitor()
        self.addCleanup(tmp.cleanup)
        page = FakePage()

        local_resources = monitor.attach_page_listeners(page, "首頁")
        page.handlers["response"](FakeResponse("https://example.com/app.js", 404, "script"))
        page.handlers["response"](FakeResponse("https://ignored-cdn.example.com/pixel.gif", 500, "image"))
        page.handlers["requestfailed"](FakeRequest("https://example.com/style.css", "stylesheet"))
        page.handlers["console"](FakeConsoleMessage("error", "x" * 600))
        page.handlers["pageerror"](RuntimeError("client boom"))

        self.assertEqual(len(local_resources), 2)
        self.assertEqual(len(monitor.broken_resources), 2)
        self.assertEqual(local_resources[0]["status"], 404)
        self.assertEqual(local_resources[1]["status"], "request_failed")
        self.assertLessEqual(len(monitor.console_errors[0]["text"]), 500)
        self.assertTrue(monitor.console_errors[0]["text"].startswith("x" * 100))
        self.assertIn("已截斷", monitor.console_errors[0]["text"])
        self.assertEqual(monitor.page_errors[0]["text"], "client boom")


class ReportRegressionTests(unittest.TestCase):
    def test_build_report_and_markdown_are_stable_and_json_serializable(self):
        tmp, monitor = make_monitor()
        self.addCleanup(tmp.cleanup)
        monitor.run_id = "20260619_120000"
        monitor.checks = [
            CheckResult("home", "首頁", "pass", "HTTP 200", elapsed_ms=10),
            CheckResult("api", "API", "fail", "HTTP 500 | broken\nline", elapsed_ms=25),
        ]
        monitor.broken_resources = [
            {"source": "首頁", "url": "https://example.com/app.js", "status": 404, "type": "script"}
        ]
        monitor.broken_links = [{"url": "https://example.com/missing", "status": 404}]
        monitor.screenshots = ["reports/screenshots/home.png"]

        started_at = datetime(2026, 6, 19, 12, 0, tzinfo=TAIPEI_TZ)
        report = monitor.build_report(started_at, 1.236)

        self.assertEqual(report["schema_version"], "1.0")
        self.assertFalse(report["ok"])
        self.assertEqual(report["summary"], {"total": 2, "pass": 1, "warn": 0, "fail": 1})
        self.assertEqual(report["duration_seconds"], 1.24)
        self.assertEqual(report["checks"][1]["detail"], "HTTP 500 | broken\nline")

        report_path = Path(tmp.name) / "report.json"
        write_json(report_path, report)
        self.assertEqual(json.loads(report_path.read_text(encoding="utf-8"))["run_id"], "20260619_120000")

        markdown_path = Path(tmp.name) / "report.md"
        monitor.write_markdown(report, markdown_path)
        markdown = markdown_path.read_text(encoding="utf-8")
        self.assertIn("# 測試站巡檢報告", markdown)
        self.assertIn("結果：PASS 1 / WARN 0 / FAIL 1", markdown)
        self.assertIn("HTTP 500 \\| broken line", markdown)
        self.assertIn("## 壞掉的頁面物件", markdown)
        self.assertIn("## 異常連結", markdown)
        self.assertIn("## 截圖", markdown)


class EmailGatingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.md_path = Path(self.tmp.name) / "report.md"
        self.json_path = Path(self.tmp.name) / "report.json"
        self.md_path.write_text("# report\n", encoding="utf-8")
        self.json_path.write_text('{"ok": false}\n', encoding="utf-8")
        self.report_ok = {
            "ok": True,
            "summary": {"fail": 0, "warn": 0},
        }
        self.report_fail = {
            "ok": False,
            "summary": {"fail": 1, "warn": 0},
        }
        self.enabled_email_config = {
            "alerts": {
                "email": {
                    "enabled": True,
                    "host": "smtp.example.com",
                    "port": 2525,
                    "from": "monitor@example.com",
                    "to": "ops@example.com, dev@example.com",
                    "starttls": False,
                    "timeout_seconds": 7,
                    "subject_prefix": "[巡檢]",
                }
            }
        }

    def test_email_disabled_and_ok_report_do_not_open_smtp(self):
        with patch("taiwanlife_monitor.monitor.smtplib.SMTP") as smtp_factory:
            self.assertFalse(
                send_email_alert(
                    self.report_fail,
                    self.md_path,
                    self.json_path,
                    {"alerts": {"email": {"enabled": False}}},
                )
            )
            self.assertFalse(
                send_email_alert(
                    self.report_ok,
                    self.md_path,
                    self.json_path,
                    self.enabled_email_config,
                )
            )

        smtp_factory.assert_not_called()

    def test_failed_report_sends_email_with_markdown_body_and_json_attachment(self):
        RecordingSMTP.instances = []
        with patch("taiwanlife_monitor.monitor.smtplib.SMTP", RecordingSMTP):
            sent = send_email_alert(
                self.report_fail,
                self.md_path,
                self.json_path,
                self.enabled_email_config,
            )

        self.assertTrue(sent)
        smtp = RecordingSMTP.instances[0]
        self.assertEqual((smtp.host, smtp.port, smtp.timeout), ("smtp.example.com", 2525, 7))
        self.assertFalse(smtp.started_tls)
        self.assertEqual(len(smtp.sent_messages), 1)
        message = smtp.sent_messages[0]
        self.assertEqual(message["From"], "monitor@example.com")
        self.assertEqual(message["To"], "ops@example.com, dev@example.com")
        self.assertIn("[巡檢] FAIL fail=1 warn=0", message["Subject"])
        self.assertEqual(message.get_body(preferencelist=("plain",)).get_content(), "# report\n")
        attachments = list(message.iter_attachments())
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].get_filename(), "report.json")

    def test_email_requires_sender_and_recipient_when_it_would_send(self):
        bad_config = {
            "alerts": {
                "email": {
                    "enabled": True,
                    "host": "smtp.example.com",
                    "to": "",
                    "from": "",
                }
            }
        }

        with self.assertRaisesRegex(ValueError, "sender and recipients"):
            send_email_alert(self.report_fail, self.md_path, self.json_path, bad_config)


if __name__ == "__main__":
    unittest.main()
