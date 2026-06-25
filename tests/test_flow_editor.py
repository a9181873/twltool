import json
import tempfile
import unittest
from pathlib import Path

from taiwanlife_monitor.flow_editor import (
    FlowValidationError,
    delete_flow,
    delete_page,
    editor_payload,
    inventory,
    load_config,
    save_config,
    update_link_crawl,
    update_search_check,
    update_ssl,
    upsert_flow,
    upsert_page,
)


def base_config():
    return {
        "target_name": "Demo",
        "base_url": "https://example.com/",
        "rpa84": {"enabled": False, "scenarios": []},
    }


class FlowEditorTests(unittest.TestCase):
    def test_upsert_flow_normalizes_steps_for_button_check(self):
        config = base_config()
        saved = upsert_flow(
            config,
            {
                "id": "button-check",
                "group": "功能",
                "name": "按鈕檢查",
                "enabled": True,
                "input": {"keyword": "保單"},
                "acceptance": "看到結果\n留下截圖",
                "steps": [
                    {"action": "goto", "path": "/"},
                    {
                        "action": "click_first",
                        "selectors": "button:has-text('搜尋')\n[data-testid='search']",
                    },
                    {
                        "action": "assert_any_text",
                        "texts": ["搜尋結果", "保單"],
                    },
                    {"action": "screenshot", "full_page": True},
                ],
            },
        )

        self.assertEqual(saved["id"], "button-check")
        self.assertTrue(saved["enabled"])
        self.assertEqual(saved["acceptance"], ["看到結果", "留下截圖"])
        self.assertEqual(saved["steps"][1]["selectors"], ["button:has-text('搜尋')", "[data-testid='search']"])
        self.assertTrue(saved["steps"][3]["full_page"])
        self.assertEqual(config["rpa84"]["scenarios"][0], saved)

    def test_upsert_rejects_unknown_step_action(self):
        config = base_config()
        with self.assertRaises(FlowValidationError):
            upsert_flow(
                config,
                {
                    "id": "bad-flow",
                    "name": "Bad",
                    "steps": [{"action": "drag_magic"}],
                },
            )

    def test_delete_flow_and_editor_payload(self):
        config = base_config()
        upsert_flow(
            config,
            {
                "id": "check-one",
                "name": "Check One",
                "steps": [{"action": "goto", "path": "/"}],
            },
        )

        payload = editor_payload(config)
        self.assertEqual(payload["summaries"][0]["step_count"], 1)
        self.assertTrue(delete_flow(config, "check-one"))
        self.assertFalse(delete_flow(config, "missing"))
        self.assertEqual(config["rpa84"]["scenarios"], [])

    def test_save_config_creates_backup_on_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "taiwanlife.json"
            path.write_text(json.dumps(base_config(), ensure_ascii=False), encoding="utf-8")
            config = load_config(path)
            upsert_flow(
                config,
                {
                    "id": "saved-flow",
                    "name": "Saved Flow",
                    "steps": [{"action": "goto", "path": "/"}],
                },
            )

            backup = save_config(path, config)

            self.assertIsNotNone(backup)
            self.assertTrue(backup.exists())
            reloaded = load_config(path)
            self.assertEqual(reloaded["rpa84"]["scenarios"][0]["id"], "saved-flow")

    def test_upsert_page_and_section_settings(self):
        config = base_config()
        page = upsert_page(
            config,
            {
                "id": "home-page",
                "name": "Home",
                "path": "/",
                "expected_title_contains": "Demo",
                "required_texts": "A\nB",
                "full_page_screenshot": True,
            },
        )
        self.assertEqual(page["required_texts"], ["A", "B"])
        self.assertTrue(page["full_page_screenshot"])

        search = update_search_check(
            config,
            {
                "enabled": True,
                "query": "policy",
                "trigger_selectors": "button:has-text('Search')",
                "input_selectors": "input[type='search']",
                "submit_selectors": "",
                "expected_any_text": "Result",
            },
        )
        self.assertTrue(search["enabled"])
        self.assertEqual(search["expected_any_text"], ["Result"])

        link = update_link_crawl(
            config,
            {
                "enabled": True,
                "max_links": "25",
                "request_timeout_ms": "9000",
                "seed_paths": "/\n/news",
                "ignore_url_keywords": "mailto:",
            },
        )
        self.assertEqual(link["max_links"], 25)
        self.assertEqual(link["seed_paths"], ["/", "/news"])

        ssl = update_ssl(
            config,
            {
                "enabled": True,
                "port": "443",
                "warn_days": "20",
                "fail_days": "5",
                "hosts": "example.com",
            },
        )
        self.assertEqual(ssl["hosts"], ["example.com"])
        self.assertTrue(delete_page(config, "home-page"))

    def test_editor_payload_includes_management_inventory(self):
        config = base_config()
        upsert_page(config, {"id": "home", "name": "Home", "path": "/"})
        upsert_flow(config, {"id": "flow-one", "name": "Flow One", "steps": [{"action": "goto", "path": "/"}]})

        payload = editor_payload(config)
        names = [item["id"] for item in payload["inventory"]]

        self.assertIn("pages", names)
        self.assertIn("flows", names)
        self.assertEqual(payload["page_summaries"][0]["id"], "home")
        self.assertEqual(inventory(config)[0]["count"], 1)


if __name__ == "__main__":
    unittest.main()
