import os


def ask_ai(
        input: "dict[str, str] | str",
        *,
        model: str = "gpt-3.5-turbo",
        api_key: str = os.getenv("OPENAI_API_KEY"),
) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("OpenAI dependency missing. Install with `pip install openai`.") from exc

    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY.")

    client = OpenAI(api_key=api_key)
    response = client.responses.create(model=model, input=input)
    return response.output_text
