import openai
import os
openai.api_key = os.getenv("OPENAI_API_KEY")

try:
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt="Hello",
        max_tokens=5
    )
    print("Key is valid! Response:", response)
except Exception as e:
    print("Key failed:", e)
