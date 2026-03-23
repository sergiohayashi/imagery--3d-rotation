import re


def extract_code_blocks(text: str):
    """
    Extracts code blocks delimited by triple backticks (```),
    optionally followed by a language name.

    Returns a list of code strings.
    """
    pattern = r"```(?:\w+)?\n(.*?)```"
    return "".join(re.findall(pattern, text, re.DOTALL))
