import requests

def send_group_msg(group_id, text):
    url = "http://127.0.0.1:8081/send_msg"
    payload = {
        "group_id": group_id,
        "message": text
    }
    resp = requests.post(url, json=payload)
    print("发送结果：", resp.status_code, resp.text)

send_group_msg(1033822500, "测试一下，Napcat 在吗？👋")
