# Language: 中文
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from uploader.douyin_uploader import main as douyin_main
from uploader.douyin_uploader.main import DouYinVideo


class DouyinDeclarationTests(unittest.TestCase):
    def test_upload_only_sets_explicit_declaration(self):
        video = DouYinVideo(
            "标题", "/tmp/demo.mp4", [], 0, "/tmp/cookie.json",
            declaration="已确认声明原文",
        )
        self.assertEqual(video.declaration, "已确认声明原文")

    def test_missing_declaration_does_not_fall_back_to_personal_opinion(self):
        video = DouYinVideo("标题", "/tmp/demo.mp4", [], 0, "/tmp/cookie.json")
        self.assertIsNone(video.declaration)

    def test_legacy_positional_runtime_flags_keep_their_meaning(self):
        video = DouYinVideo(
            "标题", "/tmp/demo.mp4", [], 0, "/tmp/cookie.json",
            None, "", "", None, "",
            "scheduled", False, False,
        )
        self.assertEqual(video.publish_strategy, "scheduled")
        self.assertFalse(video.debug)
        self.assertFalse(video.headless)
        self.assertIsNone(video.declaration)

        video = DouYinVideo(
            "标题", "/tmp/demo.mp4", [], 0, "/tmp/cookie.json",
            None, "", "", None, "",
            "scheduled", False, False, "明确声明",
            collection_name="合集",
        )
        self.assertEqual(video.declaration, "明确声明")
        self.assertEqual(video.collection_name, "合集")

    def test_apply_declaration_skips_when_unspecified(self):
        video = DouYinVideo("标题", "/tmp/demo.mp4", [], 0, "/tmp/cookie.json")
        video.set_self_declaration = AsyncMock()
        asyncio.run(video.apply_self_declaration(object()))
        video.set_self_declaration.assert_not_awaited()

    def test_apply_declaration_uses_exact_explicit_text(self):
        page = object()
        video = DouYinVideo(
            "标题", "/tmp/demo.mp4", [], 0, "/tmp/cookie.json",
            declaration="已确认声明原文",
        )
        video.set_self_declaration = AsyncMock(return_value=True)
        asyncio.run(video.apply_self_declaration(page))
        video.set_self_declaration.assert_awaited_once_with(page, "已确认声明原文")

    def test_explicit_declaration_failure_blocks_publish(self):
        video = DouYinVideo(
            "标题", "/tmp/demo.mp4", [], 0, "/tmp/cookie.json",
            declaration="已确认声明原文",
        )
        video.set_self_declaration = AsyncMock(return_value=False)
        with self.assertRaisesRegex(RuntimeError, "自主声明"):
            asyncio.run(video.apply_self_declaration(object()))

    def test_declaration_failure_closes_browser_resources(self):
        video = DouYinVideo(
            "标题", "/tmp/demo.mp4", [], 0, "/tmp/cookie.json",
            declaration="已确认声明原文",
        )
        video.validate_upload_args = AsyncMock()
        video.fill_title_and_description = AsyncMock()
        video.set_thumbnail = AsyncMock()
        video.apply_self_declaration = AsyncMock(side_effect=RuntimeError("抖音自主声明设置失败"))

        locator = MagicMock()
        locator.set_input_files = AsyncMock()
        locator.count = AsyncMock(return_value=1)
        locator.wait_for = AsyncMock()
        locator.first = locator
        page = MagicMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.wait_for_url = AsyncMock()
        page.wait_for_selector = AsyncMock()
        page.locator.return_value = locator

        context = MagicMock()
        context.new_page = AsyncMock(return_value=page)
        context.close = AsyncMock(side_effect=OSError("close failed"))
        browser = MagicMock()
        browser.new_context = AsyncMock(return_value=context)
        browser.close = AsyncMock(side_effect=OSError("browser close failed"))
        playwright = MagicMock()
        playwright.chromium.launch = AsyncMock(return_value=browser)

        with (
            patch.object(douyin_main, "set_init_script", AsyncMock(return_value=context)),
            patch.object(douyin_main.asyncio, "sleep", AsyncMock()),
            self.assertRaisesRegex(RuntimeError, "自主声明"),
        ):
            asyncio.run(video.upload(playwright))

        context.close.assert_awaited_once()
        browser.close.assert_awaited_once()

    def test_successful_upload_closes_both_and_preserves_cleanup_failure(self):
        for context_error, browser_error, expected in (
            (None, None, None),
            (OSError("context close"), OSError("browser close"), "context close"),
            (None, OSError("browser close"), "browser close"),
        ):
            with self.subTest(expected=expected):
                video = DouYinVideo("标题", "/tmp/demo.mp4", [], 0, "/tmp/cookie.json")
                video.validate_upload_args = AsyncMock()
                video.fill_title_and_description = AsyncMock()
                video.apply_self_declaration = AsyncMock()
                video.apply_collection = AsyncMock()
                video.set_thumbnail = AsyncMock()

                locator = MagicMock()
                locator.first = locator
                locator.count = AsyncMock(return_value=1)
                locator.set_input_files = AsyncMock()
                locator.wait_for = AsyncMock()
                locator.is_visible = AsyncMock(return_value=False)
                button = MagicMock()
                button.count = AsyncMock(return_value=1)
                button.click = AsyncMock()
                page = MagicMock()
                page.locator.return_value = locator
                page.get_by_role.return_value = button
                page.goto = AsyncMock()
                page.wait_for_url = AsyncMock()
                page.wait_for_timeout = AsyncMock()
                page.evaluate = AsyncMock()
                page.eval_on_selector = AsyncMock(return_value="semi-switch-checked")

                context = MagicMock()
                context.new_page = AsyncMock(return_value=page)
                context.storage_state = AsyncMock()
                context.close = AsyncMock(side_effect=context_error)
                browser = MagicMock()
                browser.new_context = AsyncMock(return_value=context)
                browser.close = AsyncMock(side_effect=browser_error)
                playwright = MagicMock()
                playwright.chromium.launch = AsyncMock(return_value=browser)

                with (
                    patch.object(douyin_main, "set_init_script", AsyncMock(return_value=context)),
                    patch.object(douyin_main.asyncio, "sleep", AsyncMock()),
                ):
                    if expected:
                        with self.assertRaisesRegex(OSError, expected):
                            asyncio.run(video.upload(playwright))
                    else:
                        asyncio.run(video.upload(playwright))

                context.storage_state.assert_awaited_once()
                context.close.assert_awaited_once()
                browser.close.assert_awaited_once()

    def test_context_creation_failure_closes_browser_without_masking_error(self):
        video = DouYinVideo("标题", "/tmp/demo.mp4", [], 0, "/tmp/cookie.json")
        video.validate_upload_args = AsyncMock()
        browser = MagicMock()
        browser.new_context = AsyncMock(side_effect=RuntimeError("创建上下文失败"))
        browser.close = AsyncMock(side_effect=OSError("关闭浏览器失败"))
        playwright = MagicMock()
        playwright.chromium.launch = AsyncMock(return_value=browser)

        with self.assertRaisesRegex(RuntimeError, "创建上下文失败"):
            asyncio.run(video.upload(playwright))
        browser.close.assert_awaited_once()

    def test_cancelled_context_initialization_closes_browser(self):
        video = DouYinVideo("标题", "/tmp/demo.mp4", [], 0, "/tmp/cookie.json")
        video.validate_upload_args = AsyncMock()
        browser = MagicMock()
        browser.new_context = AsyncMock(side_effect=asyncio.CancelledError())
        browser.close = AsyncMock()
        playwright = MagicMock()
        playwright.chromium.launch = AsyncMock(return_value=browser)

        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(video.upload(playwright))
        browser.close.assert_awaited_once()

    def test_init_script_failure_closes_context_and_browser(self):
        video = DouYinVideo("标题", "/tmp/demo.mp4", [], 0, "/tmp/cookie.json")
        video.validate_upload_args = AsyncMock()
        context = MagicMock()
        context.close = AsyncMock()
        browser = MagicMock()
        browser.new_context = AsyncMock(return_value=context)
        browser.close = AsyncMock()
        playwright = MagicMock()
        playwright.chromium.launch = AsyncMock(return_value=browser)

        with (
            patch.object(douyin_main, "set_init_script", AsyncMock(side_effect=RuntimeError("初始化失败"))),
            self.assertRaisesRegex(RuntimeError, "初始化失败"),
        ):
            asyncio.run(video.upload(playwright))
        context.close.assert_awaited_once()
        browser.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
