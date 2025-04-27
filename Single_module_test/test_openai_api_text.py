from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-4o",
    input="hello"
)

print(response.output_text)
