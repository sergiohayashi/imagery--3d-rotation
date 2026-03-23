from ..llm_services.any_model import AnyModel


class LLMTaskServices:
    @staticmethod
    async def translate(prompt):
        result, _ = await AnyModel().translate(prompt)
        return result

    @staticmethod
    async def improve_prompt(prompt):
        result, _ = await AnyModel().improve_prompt(prompt)
        return result

    @staticmethod
    async def improve_text(prompt):
        result, _ = await AnyModel().improve_text(prompt)
        return result
