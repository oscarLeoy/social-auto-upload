import unittest
from unittest.mock import AsyncMock, MagicMock

from uploader.douyin_uploader.main import DOUYIN_MANAGE_URL, DouyinSubmissionUnknown, _publish_once


class DouyinPublishOnceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.button = MagicMock(click=AsyncMock())
        self.search = MagicMock(fill=AsyncMock(), press=AsyncMock())
        self.page = MagicMock(wait_for_url=AsyncMock(), goto=AsyncMock(), wait_for_function=AsyncMock())
        self.page.get_by_role.return_value = self.button
        self.page.get_by_placeholder.return_value = self.search

    def assert_single_click(self):
        self.page.get_by_role.assert_called_once_with("button", name="发布", exact=True)
        self.button.click.assert_awaited_once_with(timeout=5000)
        self.page.wait_for_url.assert_awaited_once_with(f"{DOUYIN_MANAGE_URL}**", timeout=30000)

    async def test_redirect_succeeds_without_search(self):
        await _publish_once(self.page, "原稿标题", "图文")
        self.assert_single_click()
        self.page.goto.assert_not_awaited()

    async def test_slow_redirect_succeeds_when_search_finds_work(self):
        self.page.wait_for_url.side_effect = TimeoutError()
        await _publish_once(self.page, "原稿标题", "图文")
        self.assert_single_click()
        self.page.goto.assert_awaited_once_with(DOUYIN_MANAGE_URL, wait_until="domcontentloaded", timeout=10000)
        self.search.fill.assert_awaited_once_with("原稿标题", timeout=5000)
        self.search.press.assert_awaited_once_with("Enter", timeout=5000)
        self.assertEqual(self.page.wait_for_function.call_args.kwargs["arg"]["kind"], "图文")

    async def test_missing_work_is_unknown_without_another_click(self):
        self.page.wait_for_url.side_effect = TimeoutError()
        self.page.wait_for_function.side_effect = TimeoutError()
        with self.assertRaisesRegex(DouyinSubmissionUnknown, "UNKNOWN: 抖音图文"):
            await _publish_once(self.page, "原稿标题", "图文")
        self.assert_single_click()

    async def test_video_click_error_still_allows_verification_and_search_only(self):
        self.button.click.side_effect = TimeoutError()
        self.page.wait_for_url.side_effect = TimeoutError()
        verify_sms = AsyncMock()
        await _publish_once(self.page, "原稿标题", "视频", after_click=verify_sms)
        self.assert_single_click()
        verify_sms.assert_called_once_with(self.page)
        self.assertEqual(self.page.wait_for_function.call_args.kwargs["arg"]["kind"], "视频")
