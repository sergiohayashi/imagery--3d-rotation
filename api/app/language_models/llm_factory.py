from app.language_models.xai_llm_response_stream import xAILLM_ResponseApiStream
from .LLMBase import LLMBase
from .LLMModelDeclaration import LLMModelDeclaration
from .anthropic_llm import AnthropicLLM
from .gemini_llm_genai import GeminiLLM_genai
from .gemini_llm_genai_video import GeminiLLM_genai_video
from .imagery_fake_models import ImageryFakeModel
from .openai_llm_image_generation import OpenAILLM_ImageGenerate
from .openai_llm_response_stream import OpenAILLM_ResponseApiStream
from .openai_xai_image_generation import xAILLM_ImageGenerate
from .types.LLMNames import LLMNames
from ..config.config import config


class LLMFactory:
    _registry = {}
    _registry_by_model = {}

    @classmethod
    def register(cls, name: LLMNames, llm_class: LLMBase):
        cls._registry[name] = llm_class
        LLMModelDeclaration.add_models(llm_class.get_models())
        cls._registry_by_model.update(
            {m.name: llm_class for m in llm_class.get_models()}
        )

    @classmethod
    def create(cls, name: LLMNames, *args, **kwargs) -> LLMBase:
        if name not in cls._registry:
            raise ValueError(
                f"No LLM class registered under the name {name}, {cls._registry}"
            )
        return cls._registry[name](*args, **kwargs)

    @classmethod
    def create_by(cls, model_name: str, *args, **kwargs) -> LLMBase:
        klass = cls._registry_by_model[model_name]
        return klass(*args, **kwargs)


LLMFactory.register(LLMNames.OPENAI, ImageryFakeModel)
LLMFactory.register(LLMNames.OPENAI, OpenAILLM_ResponseApiStream)
LLMFactory.register(LLMNames.OPENAI, OpenAILLM_ImageGenerate)
LLMFactory.register(LLMNames.GEMINI, GeminiLLM_genai)
LLMFactory.register(LLMNames.GEMINI, GeminiLLM_genai_video)
LLMFactory.register(LLMNames.XAI, xAILLM_ResponseApiStream)
LLMFactory.register(LLMNames.XAI, xAILLM_ImageGenerate)
LLMFactory.register(LLMNames.ANTHROPIC, AnthropicLLM)

