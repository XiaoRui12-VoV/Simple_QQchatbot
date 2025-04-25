import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

NAPCAT_API_URL = "http://127.0.0.1:8081/send_msg"
GNEWS_API_KEY = "0c87e4a071b6394b5beb84b43b62e14a"  # <<< 请替换为你的 KEY

# 新闻指令处理函数
def handle_news_command(message_type, group_id=None, user_id=None):
    url = f"https://gnews.io/api/v4/top-headlines?lang=ja&token={GNEWS_API_KEY}"
    try:
        news_resp = requests.get(url)
        news_resp.raise_for_status()
        articles = news_resp.json().get("articles", [])[:3]

        if not articles:
            reply = [{"type": "text", "data": {"text": "\u26a0\ufe0f \u73fe\u5728\u30cb\u30e5\u30fc\u30b9\u3092\u53d6\u5f97\u3067\u304d\u307e\u305b\u3093\u3067\u3057\u305f\u3002"}}]
        else:
            reply = []
            for a in articles:
                title = a.get("title", "")
                content = a.get("content", "")
                url = a.get("url", "")
                image_url = a.get("image", "")

                if image_url:
                    reply.append({"type": "image", "data": {"url": image_url}})

                text_part = f"\U0001f4f0 {title}\n\U0001f4c4 {content}\n\U0001f517 {url}\n"
                reply.append({"type": "text", "data": {"text": text_part}})

    except Exception as e:
        reply = [{"type": "text", "data": {"text": f"\u274c \u30cb\u30e5\u30fc\u30b9\u53d6\u5f97\u4e2d\u306b\u30a8\u30e9\u30fc\u304c\u767a\u751f\u3057\u307e\u3057\u305f\uff1a{e}"}}]

    # 发送回 QQ
    payload = {
        "message_type": message_type,
        "message": reply
    }
    if message_type == "group":
        payload["group_id"] = group_id
    elif message_type == "private":
        payload["user_id"] = user_id

    try:
        resp = requests.post(NAPCAT_API_URL, json=payload)
        print("\ud83d\udce2 \u65b0\u95fb\u5df2\u53d1\u9001\uff0c\u72b6\u6001：", resp.status_code)
    except Exception as e:
        print("\u274c \u65b0\u95fb\u53d1\u9001\u5931\u6557：", e)

    return jsonify({"status": "ok"})

# 接收新闻指令格式
@app.route("/", methods=["POST"])
def handle():
    data = request.json
    raw_msg = data.get("raw_message", "").strip()
    message_type = data.get("message_type")
    group_id = data.get("group_id")
    user_id = data.get("user_id")

    if raw_msg == "/\u65b0\u805e":  # /\u65b0\u805e = "/\u65b0聞"
        return handle_news_command(message_type, group_id, user_id)

    return jsonify({"status": "ignored"})

if __name__ == "__main__":
    app.run(port=8080, debug=True)
