from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-4o",
    input="你好吗"
)

print(response.output_text)