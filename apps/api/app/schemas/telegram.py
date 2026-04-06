from __future__ import annotations

from pydantic import BaseModel, Field


class TelegramUser(BaseModel):
    id: int
    is_bot: bool = False
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None


class TelegramChat(BaseModel):
    id: int
    type: str
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


class TelegramMessage(BaseModel):
    message_id: int
    from_user: TelegramUser | None = Field(default=None, alias="from")
    chat: TelegramChat
    date: int
    text: str | None = None

    model_config = {"populate_by_name": True}


class TelegramUpdate(BaseModel):
    update_id: int
    message: TelegramMessage | None = None

    @property
    def has_text(self) -> bool:
        return self.message is not None and self.message.text is not None

    @property
    def user_id(self) -> str | None:
        if self.message and self.message.from_user:
            return str(self.message.from_user.id)
        return None

    @property
    def chat_id(self) -> str | None:
        if self.message:
            return str(self.message.chat.id)
        return None

    @property
    def text(self) -> str | None:
        if self.message:
            return self.message.text
        return None

    @property
    def user_first_name(self) -> str | None:
        if self.message and self.message.from_user:
            return self.message.from_user.first_name
        return None
