from flask import Flask, request, jsonify
import re
import base64
from io import BytesIO
import requests
import random
import html
from playwright.sync_api import sync_playwright
from openai import OpenAI
from collections import defaultdict

# 配置与初始化
GNEWS_API_KEY = "0c87e4a071b6394b5beb84b43b62e14a"
NAPCAT_API_URL = "http://127.0.0.1:8081/send_msg"
MAX_HISTORY = 6  # 保留最近 6 条（3轮对话）
SELF_QQ_ID = None  # 机器人QQ号
history_dict = defaultdict(list)

client = OpenAI()
app = Flask(__name__)

# 发送消息到 QQ（群或私聊）
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
        history_dict[session_key] = history  # 更新历史
        return reply

    except Exception as e:
        print("❌ GPT 文本请求失败：", e)
        return "（文本回复失败）"

# 获取新闻并发送
def get_news_and_send(message_type, group_id, user_id, language="zh"):
    try:
        # 从 GNews API 获取新闻
        news_resp = requests.get(f"https://gnews.io/api/v4/top-headlines?lang={language}&token={GNEWS_API_KEY}")
        articles = news_resp.json().get("articles", [])

        if not articles:
            send_reply_to_qq("⚠️ 当前没有获取到新闻。", message_type, group_id, user_id)
            return

        # 只取第一条新闻
        article = articles[random.randint(0, 9)]
        title = article.get("title", "")
        description = article.get("description", "")
        content = article.get("content", "")
        image_url = article.get("image", "")
        published_at = article.get("publishedAt", "")

        # 选择使用 description 作为摘要，如果没有则使用 content，并且对 content 进行截断处理
        if description:
            summary = description
        else:
            # 如果 content 太长，则进行截断
            summary = content[:500] + "..." if content and len(content) > 500 else content

        print(summary)
        print(image_url)

        # 格式化发布时间
        published_at_formatted = published_at[:19] if published_at else "未知"

        # 构建新闻消息
        news_messages = [
            {"type": "text", "data": {"text": f"📰 {title}\n\n{summary}\n\n📅 发布于: {published_at_formatted}"}}
        ]

        # 如果有图片，添加图片到消息的最后
        if image_url:
            img_resp = requests.get(image_url, timeout=10)
            if img_resp:
                news_messages.append({"type": "image", "data": {"url": image_url}})

        # 构建 payload 发送图文消息
        payload = {
            "message_type": message_type,
            "message": news_messages
        }

        print(payload)

        if message_type == "group":
            payload["group_id"] = group_id
        elif message_type == "private":
            payload["user_id"] = user_id

        # 发送消息
        requests.post(NAPCAT_API_URL, json=payload)

    except Exception as e:
        send_reply_to_qq(f"❌ 获取新闻失败：{e}", message_type, group_id, user_id)

# 解码 HTML 实体字符
def decode_html_entity(text: str) -> str:
    return html.unescape(text)

# 去除raw_msg当中的cq方式@
def clean_message_cq_at(raw_msg):
    cleaned_msg = re.sub(r'\[CQ:at,qq=\d+\]', '', raw_msg.strip())
    return cleaned_msg

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
    raw_msg = data.get("raw_message", "").strip()  # 去掉两端空白
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

    # 去除cq开头的@
    cleaned_msg = clean_message_cq_at(raw_msg)

    # 处理图像消息
    if "[CQ:image" in cleaned_msg:
        image_url = extract_image_url(cleaned_msg)
        image_url = decode_html_entity(image_url)
        if image_url:
            print("📸 获取到图片 URL：", image_url)
            image_io = download_image_to_memory(image_url)
            if image_io:
                base64_img = encode_image_bytes(image_io)
                result = ask_gpt_with_image(base64_img, "Please describe this image in detail. Respond in English only.")
                print("🤖 GPT 图像回复：", result)
                send_reply_to_qq(result, message_type, group_id, user_id)
            else:
                print("❌ 图片下载失败")
        else:
            print("❌ 没有找到图片 URL")

    # 处理文本消息
    elif cleaned_msg.strip() == "/news":
        get_news_and_send(message_type, group_id, user_id)
        return jsonify({"status": "ok"})

    elif cleaned_msg.strip().startswith("/news"):
        # 提取语言参数（默认为 zh）
        language = "zh"  # 默认语言是中文
        if len(cleaned_msg.split()) > 1:
            language = cleaned_msg.split()[1].lower()  # 获取指令后面的语言参数

        # 检查语言是否有效
        if language not in ["zh", "ja", "en"]:
            send_reply_to_qq("⚠️ 不支持的语言。请使用 /news zh, /news ja, /news en", message_type, group_id, user_id)
            return jsonify({"status": "ok"})

        # 获取并发送指定语言的新闻
        get_news_and_send(message_type, group_id, user_id, language)
        return jsonify({"status": "ok"})

    elif cleaned_msg.strip().lower() in ["/reset", "重置", "clear"]:
        history_dict.pop(session_key, None)
        send_reply_to_qq("🧹 已重置你的对话历史。", message_type, group_id, user_id)
        return jsonify({"status": "ok"})

    else:
        reply = ask_gpt_text(cleaned_msg, session_key)
        print("🤖 GPT 文本回复：", reply)
        send_reply_to_qq(reply, message_type, group_id, user_id)

    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(port=8080, debug=False)
