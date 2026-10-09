import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discordbot as bot
import managedb as db


class WeeklySettingsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch.object(db, 'DB_PATH', Path(directory.name) / 'test.db')
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ctx = SimpleNamespace(
            channel=SimpleNamespace(id=bot.CHANNEL_ID, send=AsyncMock()),
            guild=object(),
            author=SimpleNamespace(guild_permissions=SimpleNamespace(manage_guild=True)),
        )

    async def test_toggle_and_disabled_report(self):
        self.assertTrue(db.weekly_notifications_enabled())
        await bot.weekly_settings.callback(self.ctx, 'off')
        self.assertFalse(db.weekly_notifications_enabled())
        with patch.object(bot.weekly, 'prepare_report') as prepare:
            await bot.weekly_report.coro()
            prepare.assert_not_called()
        await bot.weekly_settings.callback(self.ctx)
        self.assertFalse(db.weekly_notifications_enabled())
        await bot.weekly_settings.callback(self.ctx, 'ON')
        self.assertTrue(db.weekly_notifications_enabled())

    async def test_permissions_channel_and_invalid_mode(self):
        self.ctx.author.guild_permissions.manage_guild = False
        await bot.weekly_settings.callback(self.ctx, 'off')
        self.assertTrue(db.weekly_notifications_enabled())
        self.ctx.author.guild_permissions.manage_guild = True
        await bot.weekly_settings.callback(self.ctx, 'invalid')
        self.assertTrue(db.weekly_notifications_enabled())
        self.ctx.channel.id = -1
        await bot.weekly_settings.callback(self.ctx, 'off')
        self.assertTrue(db.weekly_notifications_enabled())

    async def test_disable_during_report_preparation(self):
        def prepare():
            db.set_weekly_notifications(False)
            return 1, [(0, 'report')]
        channel = SimpleNamespace(send=AsyncMock())
        with patch.object(bot.weekly, 'prepare_report', side_effect=prepare), patch.object(bot.bot, 'get_channel', return_value=channel):
            await bot.weekly_report.coro()
        channel.send.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
