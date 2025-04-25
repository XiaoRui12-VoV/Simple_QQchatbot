from flask import Flask, request, jsonify
import re
import requests
from PIL import Image
from io import BytesIO
import os
import html

app = Flask(__name__)

# 提取图片 CQ码中的 URL
def extract_image_url(cq_msg):
    match = re.search(r'\[CQ:image,[^\]]*url=([^\],]+)', cq_msg)
    if match:
        return match.group(1)
    return None

def download_image_to_memory(url):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://qq.com"
    }
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            print("✅ 图片已下载到内存")
            # 用 BytesIO 包裹内容，返回内存中的“文件对象”
            return BytesIO(resp.content)
        else:
            print("❌ 下载失败：", resp.status_code)
    except Exception as e:
        print("❌ 下载异常：", e)
    return None

def show_image_from_memory(image_bytes_io):
    try:
        img = Image.open(image_bytes_io)
        img.show()
        print("✅ 已显示图片（内存）")
    except Exception as e:
        print("❌ 打开失败：", e)

# 接收 Napcat 消息
@app.route("/", methods=["POST"])
def handle_message():
    data = request.json
    print("✅ 收到消息")

    if data.get("post_type") != "message":
        return jsonify({"status": "ignored"})

    raw_msg = data.get("raw_message", "")

    # 检查是否是图片消息
    if "[CQ:image" in raw_msg:
        url = extract_image_url(raw_msg)
        url = html.unescape(url)
        print(url)
        if url:
            image_io = download_image_to_memory(url)
            if image_io:
                show_image_from_memory(image_io)

    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(port=8080)
