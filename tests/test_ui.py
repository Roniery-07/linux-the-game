"""Tests for Textual UI components and App mounting."""

import asyncio
import pytest
from lfs_game.core.engine import GameEngine
from lfs_game.ui.app import LFSGameApp


def test_app_mount_and_widgets():
    async def _run():
        engine = GameEngine()
        app = LFSGameApp(engine=engine)
        async with app.run_test() as pilot:
            assert app.query_one("#terminal-log") is not None
            assert app.query_one("#terminal-input") is not None
            assert app.query_one("#story-view") is not None
            assert app.query_one("#status-view") is not None
            assert app.query_one("#inventory-view") is not None
            assert app.engine.fs.current_user == "root"

    asyncio.run(_run())

