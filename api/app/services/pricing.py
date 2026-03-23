# from .pricing_data import pricing_data
from typing import Union

from ..language_models.LLMModelDeclaration import LLMModelDeclaration
from ..config.config import config
from ..language_models.hugging_face_models import HFModelDecl


def calculate_estimate_price_for_hf(model_spec: HFModelDecl, usage: dict):
    input_tokens = usage["prompt_tokens"]
    output_tokens = usage["completion_tokens"]
    price = (
        model_spec.best_provider.pricing.input * input_tokens / 1000000.0
        + model_spec.best_provider.pricing.output * output_tokens / 1000000.0
    )
    return round(price, 4), input_tokens, output_tokens


def calculate_estimate_price(model: str, usage: Union[dict, any], containers: int = 0):
    print("pricing for: ", model, usage)
    usage = usage if isinstance(usage, dict) else usage.model_dump()
    model_dict = LLMModelDeclaration.get_all_models_as_dict()
    if model not in model_dict:
        print(f"MODEL {model} NOT FOUND IN MODEL_DICT! TRY FALLBACK")
        if "vision" in model:
            model = config.default_vision_model
        if model.startswith("gpt-3.5"):
            model = config.default_cheaper_model
        elif model.startswith("gpt-4"):
            model = config.default_model
        elif model.startswith("o1"):
            print(f"calculate_estimate_price: Unknown model: {model}, uses o1")
            model = model_dict.get("o1")
        else:
            print("calculate_estimate_price: Unknown model: " + model)
            return None

    input_tokens = 0
    if "prompt_tokens" in usage:
        input_tokens = usage["prompt_tokens"]
    elif "prompt_token_count" in usage:
        input_tokens = usage["prompt_token_count"]
    elif "input_tokens" in usage:
        input_tokens = usage["input_tokens"]

    output_tokens = 0
    if "completion_tokens" in usage:
        output_tokens = usage["completion_tokens"]
    elif "candidates_token_count" in usage:
        output_tokens = usage["candidates_token_count"]
    elif "output_tokens" in usage:
        output_tokens = usage["output_tokens"]
    if output_tokens is None:
        output_tokens = 0

    price = (
        model_dict[model].input_price * input_tokens / 1000000.0
        + model_dict[model].output_price * output_tokens / 1000000.0
    )
    if containers and "code_interpreter_price_per_container" in model_dict:
        price += containers * (model_dict["code_interpreter_price_per_container"])

    # print( 'input', model_dict[model].input_price, usage['prompt_tokens'], model_dict[model].input_price * usage['prompt_tokens'] / 1000000.0)
    # print( 'output', model_dict[model].output_price, usage['completion_tokens'], model_dict[model].output_price * usage['completion_tokens'] / 1000000.0)
    # print('price', price, round(price, 8))
    return round(price, 4), input_tokens, output_tokens


def calculate_estimate_price_for_image(model: str, meta: dict):
    return LLMModelDeclaration.get_model(model).unit_price
