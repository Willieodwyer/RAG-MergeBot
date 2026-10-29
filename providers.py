
import os
import requests

url = "https://router.huggingface.co/v1/models"

response = requests.get(
    url,
    headers={
        "Authorization": f"Bearer {os.environ['HF_TOKEN']}"
    },
    timeout=30,
)
response.raise_for_status()

models = response.json().get("data", [])

for model in models:
    providers = model.get("providers", [])

    for provider in providers:
        if (
            provider.get("supports_tools") is True
            and provider.get("status") == "live"
        ):
            print(
                f"Model:    {model.get('id')}\n"
                f"Provider: {provider.get('provider')}\n"
                f"Context:  {provider.get('context_length')}\n"
                f"---"
            )

