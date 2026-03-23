import datetime
import os
import pprint
from typing import Optional

from openai import OpenAI
from pydantic import BaseModel


class HFModelPricing(BaseModel):
    input: float  # input price
    output: float  # output price


class HFModelProviders(BaseModel):
    provider: str  # provider name
    pricing: Optional[HFModelPricing] = None
    status: Optional[str] = None
    context_length: Optional[float] = None


class HFModelDecl(BaseModel):
    id: str  # name of the model  <company>/<name>
    company: str  # model company
    name: str  # model name
    owned_by: str
    providers: list[HFModelProviders]
    best_provider: Optional[HFModelProviders] = None


class HuggingFaceModels:
    # cached models list
    models_list: list[HFModelDecl] = []
    models_list_expires_in = None
    models_map = {}

    @staticmethod
    def load_models():
        def to_model(m):
            decl = HFModelDecl(
                id=m["id"],
                company=m["id"].split("/")[0],
                name=m["id"].split("/")[1],
                owned_by=m["owned_by"],
                providers=[
                    HFModelProviders(
                        provider=p["provider"],
                        pricing=(
                            HFModelPricing(
                                input=p.get("pricing", {}).get("input"),
                                output=p.get("pricing", {}).get("output"),
                            )
                            if "pricing" in p
                            else None
                        ),
                        status=p["status"],
                    )
                    for p in m["providers"]
                ],
            )
            best_provider = None
            for p in m.get("providers"):
                if p.get("status") != "live":
                    continue
                input_value = p.get("pricing", {}).get("input", 0)
                if input_value != 0:
                    if not best_provider or input_value < best_provider.pricing.input:
                        best_provider = HFModelProviders(
                            pricing=HFModelPricing(
                                input=input_value,
                                output=p.get("pricing", {}).get("output", 0),
                            ),
                            provider=p.get("provider"),
                            context_length=p.get("context_length"),
                        )
            decl.best_provider = best_provider
            return decl if best_provider else None

        # ---
        api_key = os.getenv("HF_API_TOKEN")
        if not api_key:
            return []
        client = OpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=os.getenv("HF_API_TOKEN"),
        )
        models = client.models.list().to_dict().get("data")
        # pprint.pprint(models, indent=2)
        filtered = []
        for m in models:
            fm = to_model(m)
            if fm:
                filtered.append(fm)
        return filtered

    @classmethod
    def get_models(cls) -> list[HFModelDecl]:
        if (
            not cls.models_list_expires_in
            or datetime.datetime.now() > cls.models_list_expires_in
        ):
            cls.models_list = sorted(cls.load_models(), key=lambda m: m.id)
            cls.models_list_expires_in = datetime.datetime.now() + datetime.timedelta(
                days=1
            )
            cls.models_map = {m.name: m for m in cls.models_list}

        return cls.models_list

    @classmethod
    def get_model(cls, name):
        cls.get_models()  # force load
        info = cls.models_map.get(name)
        return info
