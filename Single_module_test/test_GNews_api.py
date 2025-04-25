import requests
from io import BytesIO
from PIL import Image
import json

API_KEY = "0c87e4a071b6394b5beb84b43b62e14a"

def fetch_news_with_images(max_articles=3):
    url = f"https://gnews.io/api/v4/top-headlines?lang=ja&token={API_KEY}"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()

        if "articles" not in data:
            print("❌ 返回异常：", data)
            return

        articles = data["articles"][:max_articles]
        for i, article in enumerate(articles, 1):
            title = article.get("title", "（无标题）")
            url = article.get("url", "")
            content = article.get("content", "").strip()
            image_url = article.get("image")

            #branch test                    

            print(f"\n📰 {i}. {title}")
            print(f"📄 内容：{content}")
            print(f"🔗 链接：{url}")
            print(f"🖼️ 图片地址：{image_url}")
 
            # 下载图片并显示
            if image_url:
                try:
                    img_resp = requests.get(image_url, timeout=10)
                    img_resp.raise_for_status()
                    img_io = BytesIO(img_resp.content)

                    # 显示图片（开发时用）
                    img = Image.open(img_io)
                    img.show()
                    print("✅ 图片已成功打开预览")

                except Exception as img_err:
                    print(f"❌ 图片下载失败：{img_err}")
            else:
                print("⚠️ 无图片链接")

    except Exception as e:
        print("❌ 请求失败：", e)

# 运行测试
if __name__ == "__main__":
    fetch_news_with_images()
