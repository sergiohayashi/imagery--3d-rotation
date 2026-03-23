from typing import List, Dict

from .types.models import ModelDeclaration


class LLMModelDeclaration:
    _all_models: List[ModelDeclaration] = []

    @classmethod
    def add_models(cls, model_list: List[ModelDeclaration]):
        cls._all_models.extend(model_list)

    @classmethod
    def get_all_models(cls) -> List[ModelDeclaration]:
        return cls._all_models

    @classmethod
    def get_all_models_as_dict(cls) -> Dict[str, ModelDeclaration]:
        models = cls.get_all_models()
        models_dict = {m.name: m for m in models}
        return models_dict

    @classmethod
    def get_model(cls, model_name: str, *args, **kwargs) -> ModelDeclaration:
        return cls.get_all_models_as_dict()[model_name]
