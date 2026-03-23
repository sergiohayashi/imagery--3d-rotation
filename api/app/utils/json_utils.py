import json
import traceback


def parser_json(answer: str) -> dict:
    answer = answer.replace("```json", "").replace("```", "").strip()
    try:
        obj = json.loads(answer, strict=False)
    except Exception as e:
        print(f"Error parsing json string: type(e)={type(e)}. Error occurred: {e}")
        print(f"text to parse: \n{answer}")
        traceback.print_exc()
        obj = answer

    return obj
