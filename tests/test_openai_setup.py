# tests/test_openai_setup.py

import os
import json
import pytest
from openai import OpenAI

@pytest.fixture
def openai_client():
    """Return an OpenAI client if API key exists, else skip tests."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set. Skipping OpenAI SDK test.")
    return OpenAI(api_key=api_key)

def test_openai_sdk_compatibility(openai_client):
    """
    Verify that the OpenAI SDK and API are working and support response_format=json_object.
    """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Output ONLY a JSON object."},
                {"role": "user", "content": "Say hello in a JSON object with the key 'message'."}
            ],
            response_format={"type": "json_object"},
            temperature=0
        )

        content = response.choices[0].message.content

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            pytest.fail(f"❌ JSON parsing failed. Content received: {content}")

        assert "message" in data, f"❌ 'message' key not found in JSON: {data}"
        print(f"✅ SUCCESS: SDK and API working. AI says: {data['message']}")

    except TypeError as e:
        pytest.fail(f"❌ SDK ERROR: Installed OpenAI SDK too old. Error: {e}")
    except Exception as e:
        pytest.fail(f"❌ GENERAL ERROR: {e}")
