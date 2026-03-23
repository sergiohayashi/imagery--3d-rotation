from pathlib import Path

cache_prompts = {}


def get_prompt(filename: str):
    if not filename in cache_prompts:
        with open(
            Path(Path(__file__).resolve().parent, "prompts", filename),
            "r",
            encoding="utf-8",
        ) as f:
            cache_prompts[filename] = f.read()

    return cache_prompts[filename]
