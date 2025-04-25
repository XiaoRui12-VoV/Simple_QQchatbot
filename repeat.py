from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

NAPCAT_API_URL = "http://127.0.0.1:8081/send_msg"  # 根据你的设置来

@app.route("/", methods=["POST"])
def handle_message():
    data = request.json
    print("✅ 收到消息：", data)

    # 只处理 message 类型事件
    if data.get("post_type") != "message":
        return jsonify({"status": "ignored"})

    msg = data.get("raw_message", "")
    message_type = data.get("message_type")
    payload = {"message": msg}
    print("\n", msg, "\n")
    print("\n", payload, "\n")

    if message_type == "group":
        payload["group_id"] = data.get("group_id")
    elif message_type == "private":
        payload["user_id"] = data.get("user_id")
    else:
        return jsonify({"status": "ignored"})

    # 发送消息
    try:
        resp = requests.post(NAPCAT_API_URL, json=payload)
        print("✅ 发送结果：", resp.status_code, resp.text)
    except Exception as e:
        print("❌ 发送出错：", e)

    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(port=8080)
