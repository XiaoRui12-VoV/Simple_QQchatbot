from flask import Flask, request, jsonify
import re
import requests
import html
import base64
from playwright.sync_api import sync_playwright
from io import BytesIO
from openai import OpenAI

app = Flask(__name__)
client = OpenAI()
NAPCAT_API_URL = "http://127.0.0.1:8081/send_msg"

def send_reply_to_qq(result, message_type, group_id=None, user_id=None):
    payload = {
        "message_type": message_type,
        "message": result
    }

    if message_type == "group":
        payload["group_id"] = group_id
    elif message_type == "private":
        payload["user_id"] = user_id
    else:
        print("❌ 不支持的消息类型")
        return

    try:
        resp = requests.post(NAPCAT_API_URL, json=payload)
        print("📤 消息已发送，状态：", resp.status_code)
    except Exception as e:
        print("❌ 回传失败：", e)

# 提取图片 URL（从 CQ码中）
def extract_image_url(cq_msg):
    match = re.search(r'\[CQ:image,[^\]]*url=([^\],]+)', cq_msg)
    if match:
        return match.group(1)
    return None

# 下载图片为内存 BytesIO 对象
def download_image_to_memory(url):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context()
            page = context.new_page()
            print("🌐 模拟浏览器访问图片...")
            response = page.goto(url)
            content = response.body()
            browser.close()
            print("✅ 图片已用浏览器方式下载")
            return BytesIO(content)
    except Exception as e:
        print("❌ 浏览器模拟下载失败：", e)
    return None

# 转换图片为 base64 字符串
def encode_image_bytes(image_io: BytesIO) -> str:
    return base64.b64encode(image_io.getvalue()).decode("utf-8")

# 发送给 GPT 识图
def ask_gpt_with_image(image_base64: str, question):
    try:
        print(question)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        { "type": "text", "text": question },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print("❌ GPT 请求失败：", e)
        return "（识图失败）"

# Flask 接收 QQ 消息
@app.route("/", methods=["POST"])
def handle_message():
    data = request.json
    print("✅ 收到消息")

    if data.get("post_type") != "message":
        return jsonify({"status": "ignored"})

    raw_msg = data.get("raw_message", "")
    if "[CQ:image" in raw_msg:
        image_url = extract_image_url(raw_msg)
        image_url = html.unescape(image_url)
        if image_url:
            print("📸 获取到图片 URL：", image_url)
            image_io = download_image_to_memory(image_url)
            if image_io:
                base64_img = encode_image_bytes(image_io)
                result = ask_gpt_with_image(base64_img, "Please describe this image in detail. Respond in English only.")
                print("🤖 GPT 识图结果：", result)
                message_type = data.get("message_type")
                if message_type == "group":
                    send_reply_to_qq(result, "group", group_id=data.get("group_id"))
                elif message_type == "private":
                    send_reply_to_qq(result, "private", user_id=data.get("user_id"))
            else:
                print("❌ 图片下载失败")
        else:
            print("❌ 没有找到图片 URL")
    else:
        print("📭 非图片消息，忽略")

    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(port=8080)
