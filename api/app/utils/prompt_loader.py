from pathlib import Path

cache_prompts = {}


# parent = Path(__file__).resolve().parent
def get_prompt(parent, filename: str):
    if not filename in cache_prompts:
        with open(Path(parent, "prompts", filename), "r", encoding="utf-8") as f:
            cache_prompts[filename] = f.read()

    return cache_prompts[filename]
