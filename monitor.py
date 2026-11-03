import os
import requests
from bs4 import BeautifulSoup

# 專門監控原網址 Z0277
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

def check_stock():
    print(f"正在檢查商品網址：{TARGET_URL} ...")
    
    try:
        res = requests.get(TARGET_URL, headers=HEADERS, timeout=15, allow_redirects=True)
        res.encoding = res.apparent_encoding
        
        # 僅在伺服器真實下發 HTTP 轉址跳回分類頁時才判定為隱藏
        if "box_list.php" in res.url:
            print("目前網址被伺服器轉址回分類頁，商品處於暫時隱藏狀態。")
            return

        soup = BeautifulSoup(res.text, "html.parser")
        
        # 搜尋範圍涵蓋 td、font、span、a、button、div、b 等所有可能包覆狀態的標籤
        search_tags = ['td', 'font', 'span', 'a', 'button', 'input', 'div', 'b', 'strong']

        # 1. 尋找「兌換」按鈕
        redeem_elem = soup.find(lambda el: el.name in search_tags and (
            el.get_text(strip=True).replace('\xa0', '') == "兌換" or
            el.get('value', '').strip() == "兌換"
        ))

        # 2. 尋找「售完」按鈕
        soldout_elem = soup.find(lambda el: el.name in search_tags and (
            el.get_text(strip=True).replace('\xa0', '') == "售完" or
            el.get('value', '').strip() == "售完"
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
            print("狀態正常：商品頁 (Z0277) 連線正常，目前顯示為黃色【售完】。")
        else:
            print("商品頁存在，但尚未匹配到「兌換」或「售完」文字。")
            # 輔助印出目前抓到的相關文字
            candidates = [el.get_text(strip=True) for el in soup.find_all(['td', 'font', 'span']) if el.get_text(strip=True)]
            print("相關文字片段：", [c for c in candidates if any(k in c for k in ['點', '售', '兌', 'Z0277'])][:10])

    except Exception as e:
        print(f"監控檢查時發生錯誤: {e}")

if __name__ == "__main__":
    check_stock()
