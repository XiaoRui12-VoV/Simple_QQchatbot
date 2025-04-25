from flask import Flask, request, jsonify
import re
import requests
import html
import base64
from io import BytesIO
from collections import defaultdict
from playwright.sync_api import sync_playwright
from openai import OpenAI

app = Flask(__name__)
client = OpenAI()
NAPCAT_API_URL = "http://127.0.0.1:8081/send_msg"

# 机器人自己的QQ号（用于判断是否被@）
SELF_QQ_ID = None

# 聊天历史：每个用户或群对应一个消息列表
history_dict = defaultdict(list)
MAX_HISTORY = 6  # 保留最近 6 条（3轮对话）

# 发送消息到 QQ（群 or 私聊）
def send_reply_to_qq(result, message_type, group_id=None, user_id=None):
    payload = {
        "message_type": message_type,
        "message": result
    }
    if message_type == "group":
        payload["group_id"] = group_id
    elif message_type == "private":
        payload["user_id"] = user_id
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

# 浏览器方式下载图片（规避 SSL 问题）
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

# 图片转 base64
def encode_image_bytes(image_io: BytesIO) -> str:
    return base64.b64encode(image_io.getvalue()).decode("utf-8")

# GPT 图像识别（单轮）
def ask_gpt_with_image(image_base64: str, question: str):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}" }}
                    ]
                }
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print("❌ GPT 图像请求失败：", e)
        return "（识图失败）"

# GPT 文本对话（带历史）
def ask_gpt_text(message: str, session_key: str):
    history = history_dict[session_key][-MAX_HISTORY:]  # 最近历史
    history.append({"role": "user", "content": message})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=history
        )
        reply = response.choices[0].message.content

        # 加入历史
        history.append({"role": "assistant", "content": reply})
        history_dict[session_key] = history  # 覆盖更新
        return reply

    except Exception as e:
        print("❌ GPT 文本请求失败：", e)
        return "（文本回复失败）"

# Flask 接收 QQ 消息
@app.route("/", methods=["POST"])
def handle_message():
    global SELF_QQ_ID

    data = request.json
    print("✅ 收到消息")

    if data.get("post_type") != "message":
        return jsonify({"status": "ignored"})

    message_type = data.get("message_type")
    user_id = data.get("user_id")
    group_id = data.get("group_id")
    raw_msg = data.get("raw_message", "")
    msg_segments = data.get("message", [])
    session_key = str(group_id or user_id)

    # 提取机器人自己的QQ号（仅首次）
    if SELF_QQ_ID is None:
        SELF_QQ_ID = str(data.get("self_id"))
        print(f"🤖 机器人 QQ号 已识别为：{SELF_QQ_ID}")

    # ✅ 群聊且未@机器人 → 忽略
    if message_type == "group":
        if not any(seg["type"] == "at" and str(seg["data"].get("qq")) == SELF_QQ_ID for seg in msg_segments):
            print("🙈 群聊未@机器人，忽略")
            return jsonify({"status": "ignored"})

    # ========== 图片消息 ==========
    if "[CQ:image" in raw_msg:
        image_url = extract_image_url(raw_msg)
        image_url = html.unescape(image_url)
        if image_url:
            print("📸 获取到图片 URL：", image_url)
            image_io = download_image_to_memory(image_url)
            if image_io:
                base64_img = encode_image_bytes(image_io)
                result = ask_gpt_with_image(
                    base64_img,
                    "Please describe this image in detail. Respond in English only."
                )
                print("🤖 GPT 图像回复：", result)
                send_reply_to_qq(result, message_type, group_id, user_id)
            else:
                print("❌ 图片下载失败")
        else:
            print("❌ 没有找到图片 URL")

    # ========== 文本消息 ==========
    else:
        print("💬 文本消息：", raw_msg)

        # 重置指令
        if raw_msg.strip().lower() in ["/reset", "重置", "clear"]:
            history_dict.pop(session_key, None)
            send_reply_to_qq("🧹 已重置你的对话历史。", message_type, group_id, user_id)
            return jsonify({"status": "ok"})

        reply = ask_gpt_text(raw_msg, session_key)
        print("🤖 GPT 文本回复：", reply)
        send_reply_to_qq(reply, message_type, group_id, user_id)

    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(port=8080, debug=False)
