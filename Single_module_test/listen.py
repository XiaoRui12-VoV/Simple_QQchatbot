from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/', methods=['POST'])
def listen():
    data = request.json
    print("收到 Napcat 消息：")
    print(data)

    # 返回 JSON 格式响应，而不是字符串
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080)
