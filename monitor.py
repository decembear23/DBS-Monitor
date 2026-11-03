import os
import requests
from bs4 import BeautifulSoup

TARGET_URL = "https://www.gopower.tw/goodsview.php?g_id=Z0277"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.gopower.tw/"
}

def send_telegram(message):
    """發送 Telegram 推播至 iPhone"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("未設定 Telegram Token 或 Chat ID，略過推播。")
        return
        
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        res = requests.post(api_url, json=payload, timeout=10)
        res.raise_for_status()
        print("Telegram 推播已成功發送！")
    except Exception as e:
        print(f"推播發送失敗: {e}")

def clean_text(text):
    """移除所有空白字元（包含一般空格、全形空格與換行）"""
    if not text:
        return ""
    return "".join(text.split())

def check_stock():
    print(f"正在檢查商品網址：{TARGET_URL} ...")
    
    try:
        res = requests.get(TARGET_URL, headers=HEADERS, timeout=15, allow_redirects=True)
        res.encoding = res.apparent_encoding
        
        # 判斷是否被伺服器轉址回分類清單
        if "box_list.php" in res.url:
            print("目前網址被伺服器轉址回分類頁，商品處於暫時隱藏狀態。")
            return

        soup = BeautifulSoup(res.text, "html.parser")
        search_tags = ['td', 'font', 'span', 'a', 'button', 'input', 'div', 'b', 'strong']

        # 1. 尋找「兌換」（同時相容「兌換」與「兌 換」）
        redeem_elem = soup.find(lambda el: el.name in search_tags and (
            clean_text(el.get_text()) == "兌換" or
            clean_text(el.get('value', '')) == "兌換"
        ))

        # 2. 尋找「售完」（同時相容「售完」與「售 完」）
        soldout_elem = soup.find(lambda el: el.name in search_tags and (
            clean_text(el.get_text()) == "售完" or
            clean_text(el.get('value', '')) == "售完"
        ))

        if redeem_elem:
            print("🔥 偵測到紅色【兌換】狀態！立即發送推播通知！")
            send_telegram(
                f"🚨 <b>動感活利網【補貨通知】</b>\n\n"
                f"<b>品項：</b>終獎次元突破造型 (Z0277)\n"
                f"狀態：🔴 <b>開放兌換中</b>\n\n"
                f"🔗 快速前往：{TARGET_URL}"
            )
        elif soldout_elem:
            print("狀態正常：商品頁 (Z0277) 連線正常，目前顯示為黃色【售 完】。")
        else:
            print("未能辨識狀態，請檢查網頁。")

    except Exception as e:
        print(f"監控檢查時發生錯誤: {e}")

if __name__ == "__main__":
    check_stock()
