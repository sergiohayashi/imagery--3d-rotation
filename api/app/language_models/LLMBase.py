from __future__ import annotations

from abc import abstractmethod, ABC
from typing import List, Union, Optional

from pydantic import BaseModel, Field, validator

from .types.models import ModelDeclaration
from .types.opboos_chat_completion import OpBoostChatCompletion, OpBoostChatMessage


class LLMBase(ABC):
    models: List[ModelDeclaration] = []

    @abstractmethod
    async def achat(
        self,
        messages: Union[list[OpBoostChatMessage], list[dict]],
        model: str,
        options: dict = None,
        # temperature: Optional[float] = None
    ) -> tuple[
        dict | str | None,
        list | str | None,
        list | str | None,
        OpBoostChatCompletion | dict | None,
    ]:
        return None, None, None, None

    @classmethod
    def get_models(cls) -> list[ModelDeclaration]:
        return cls.models
