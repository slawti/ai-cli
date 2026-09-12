import os
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    print("Error: OPENROUTER_API_KEY is not set.")
    exit(1)


client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)


MODEL = "nvidia/nemotron-3-embed-1b:free"

messages = []


while True:
    user_input = input("\nYou: ")

    if user_input.lower() == "exit":
        print("Goodbye!")
        break

    messages.append({
        "role": "user",
        "content": user_input,
    })

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
    )

    answer = response.choices[0].message.content

    messages.append({
        "role": "assistant",
        "content": answer,
    })

    print(f"\nAI: {answer}")