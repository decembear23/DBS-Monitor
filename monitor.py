import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# 1. 優先檢查的原網址
PRIMARY_PRODUCT_URL = "https://www.gopower.tw/goodsview.php?g_id=Z0277"

# 2. 備援分類頁網址與匹配關鍵字
CATEGORY_URL = "https://www.gopower.tw/box_list.php?zId=Z8"
KEYWORD_TITLE = "終獎次元突破造型"
KEYWORD_POINT = "現金"

# 讀取環境變數並過濾空白
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

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
    """去除所有空白、換行與特殊空格"""
    if not text:
        return ""
    return "".join(text.split())

def parse_button_status(soup):
    """檢查頁面按鈕是否為【兌換】或【售完】"""
    search_tags = ['td', 'font', 'span', 'a', 'button', 'input', 'div', 'b', 'strong']

    # 尋找「兌換」
    redeem_elem = soup.find(lambda el: el.name in search_tags and (
        clean_text(el.get_text()) == "兌換" or
        clean_text(el.get('value', '')) == "兌換"
    ))
    if redeem_elem:
        return "REDEEM"

    # 尋找「售完」
    soldout_elem = soup.find(lambda el: el.name in search_tags and (
        clean_text(el.get_text()) == "售完" or
        clean_text(el.get('value', '')) == "售完"
    ))
    if soldout_elem:
        return "SOLDOUT"

    return "UNKNOWN"

def check_stock():
    print(f"步驟一：檢查商品原網址 {PRIMARY_PRODUCT_URL} ...")
    
    try:
        res = requests.get(PRIMARY_PRODUCT_URL, headers=HEADERS, timeout=15, allow_redirects=True)
        res.encoding = res.apparent_encoding
        
        # 判斷是否被轉址回分類頁
        is_redirected = "box_list.php" in res.url

        # ------------------------------------------------------------------
        # 情況 A：Z0277 正常存在，未被隱藏轉址
        # ------------------------------------------------------------------
        if not is_redirected:
            soup = BeautifulSoup(res.text, "html.parser")
            status = parse_button_status(soup)
            
            if status == "REDEEM":
                print("🔥 原商品頁 (Z0277) 開放兌換！發送推播！")
                send_telegram(
                    f"🚨 <b>動感活利網【補貨通知】</b>\n\n"
                    f"<b>品項：</b>終獎次元突破造型 (Z0277)\n"
                    f"狀態：🔴 <b>開放兌換中</b>\n\n"
                    f"🔗 快速前往：{PRIMARY_PRODUCT_URL}"
                )
                return
            elif status == "SOLDOUT":
                print("狀態正常：商品頁 (Z0277) 目前顯示為黃色【售 完】。")
                return
            else:
                print("原網址未被轉址，但未能識別按鈕文字，切換至備援機制確認...")

        # ------------------------------------------------------------------
        # 情況 B：Z0277 被隱藏轉址，自動啟動備援掃描
        # ------------------------------------------------------------------
        print("原網址被轉址/隱藏。啟動步驟二：自動掃描分類頁尋找目標品項...")
        cat_res = requests.get(CATEGORY_URL, headers=HEADERS, timeout=15)
        cat_res.encoding = cat_res.apparent_encoding
        cat_soup = BeautifulSoup(cat_res.text, "html.parser")

        # 找出分類清單中所有符合關鍵字的商品連結
        found_links = {}
        for a_tag in cat_soup.find_all("a", href=True):
            text = a_tag.get_text(strip=True)
            href = a_tag["href"]
            if KEYWORD_TITLE in text and KEYWORD_POINT in text and "goodsview.php" in href:
                full_url = urljoin(CATEGORY_URL, href)
                found_links[full_url] = text

        if not found_links:
            print(f"分類頁中目前未出現「{KEYWORD_TITLE}」商品，全站徹底缺貨/下架中。")
            return

        # 自動前往新商品頁檢查狀態
        for target_url, title in found_links.items():
            print(f"在分類頁發現對應商品：{title}")
            print(f"正在前往查看庫存：{target_url} ...")
            
            item_res = requests.get(target_url, headers=HEADERS, timeout=15)
            item_res.encoding = item_res.apparent_encoding
            item_soup = BeautifulSoup(item_res.text, "html.parser")
            
            item_status = parse_button_status(item_soup)
            if item_status == "REDEEM":
                print("🔥 發現補貨開放兌換！發送推播通知！")
                send_telegram(
                    f"🚨 <b>動感活利網【補貨通知 (新網址)】</b>\n\n"
                    f"<b>品項名稱：</b>\n{title}\n\n"
                    f"狀態：🔴 <b>開放兌換中</b>\n"
                    f"🔗 快速前往：{target_url}"
                )
            elif item_status == "SOLDOUT":
                print(f"  該品項目前顯示為黃色【售 完】。")
            else:
                print(f"  未能辨識按鈕狀態 ({item_status})。")

    except Exception as e:
        print(f"監控檢查時發生錯誤: {e}")

if __name__ == "__main__":
    check_stock()
