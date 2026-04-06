"""Tests for Telegram webhook schema parsing."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.schemas.telegram import TelegramUpdate


class TestTelegramUpdateParsing:
    def test_parse_full_message(self):
        raw = {
            "update_id": 123456,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 12345,
                    "is_bot": False,
                    "first_name": "Maria",
                },
                "chat": {
                    "id": 12345,
                    "type": "private",
                },
                "date": 1700000000,
                "text": "Oi, bom dia!",
            },
        }
        update = TelegramUpdate(**raw)
        assert update.update_id == 123456
        assert update.has_text is True
        assert update.text == "Oi, bom dia!"
        assert str(update.user_id) == "12345"
        assert str(update.chat_id) == "12345"
        assert update.user_first_name == "Maria"

    def test_parse_no_text(self):
        raw = {
            "update_id": 123457,
            "message": {
                "message_id": 2,
                "from": {"id": 12345, "is_bot": False, "first_name": "Maria"},
                "chat": {"id": 12345, "type": "private"},
                "date": 1700000000,
            },
        }
        update = TelegramUpdate(**raw)
        assert update.has_text is False

    def test_parse_no_message(self):
        raw = {"update_id": 123458}
        update = TelegramUpdate(**raw)
        assert update.has_text is False
        assert update.text is None

    def test_from_field_alias(self):
        """Ensure 'from' (reserved word) is handled via alias."""
        raw = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "from": {"id": 999, "is_bot": False, "first_name": "Test"},
                "chat": {"id": 999, "type": "private"},
                "date": 1,
                "text": "test",
            },
        }
        update = TelegramUpdate(**raw)
        assert update.message.from_user.id == 999
