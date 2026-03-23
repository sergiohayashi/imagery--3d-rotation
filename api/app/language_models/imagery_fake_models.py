from __future__ import annotations

from typing import List, Union

from .LLMBase import LLMBase
from .types.LLMNames import LLMNames
from .types.models import ModelDeclaration
from .types.opboos_chat_completion import OpBoostChatCompletion, OpBoostChatMessage


class ImageryFakeModel(LLMBase):

    async def achat(
        self,
        messages: Union[list[OpBoostChatMessage], list[dict]],
        model: str,
        options: dict = None,
    ) -> (dict | str, OpBoostChatCompletion):
        raise Exception("Not implemented")

    # -----
    models: List[ModelDeclaration] = [
        ModelDeclaration(
            name="imagery",
            company=LLMNames.OPENAI,
            input_price=0,
            output_price=0,
            eligible=True,
            input_modality="T",
            output_modality="T",
        ),
        ModelDeclaration(
            name="tools-based-imagery",
            company=LLMNames.OPENAI,
            input_price=0,
            output_price=0,
            eligible=True,
            input_modality="T",
            output_modality="T",
        ),
        ModelDeclaration(
            name="incremental-tools-based-imagery",
            company=LLMNames.OPENAI,
            input_price=0,
            output_price=0,
            eligible=True,
            input_modality="T",
            output_modality="T",
        ),
        ModelDeclaration(
            name="tools-based-imagery--mental-rotation-1",
            company=LLMNames.OPENAI,
            input_price=0,
            output_price=0,
            eligible=True,
            input_modality="T",
            output_modality="T",
        ),
        ModelDeclaration(
            name="tools-based-imagery--mental-rotation-2",
            company=LLMNames.OPENAI,
            input_price=0,
            output_price=0,
            eligible=True,
            input_modality="T",
            output_modality="T",
        ),
        ModelDeclaration(
            name="tools-based-imagery--mental-rotation-3",
            company=LLMNames.OPENAI,
            input_price=0,
            output_price=0,
            eligible=True,
            input_modality="T",
            output_modality="T",
        ),
    ]

    @staticmethod
    def is_imagery_model(model_name):
        for m in ImageryFakeModel.models:
            if m.name == model_name:
                return True
        return False
