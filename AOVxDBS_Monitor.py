import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# 1. 歷史固定商品網址
PRIMARY_PRODUCT_URL = "https://www.gopower.tw/goodsview.php?g_id=Z0277"

# 2. 備援分類頁網址與品項特徵關鍵字
CATEGORY_URL = "https://www.gopower.tw/box_list.php?zId=Z8"
KEYWORD_TITLE = "終獎次元突破造型"
KEYWORD_POINT = "現金"  # 鎖定「現金積點/現金紅利」類別

# 從環境變數讀取 Telegram 金鑰
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

def parse_button_status(soup):
    """精確解析網頁上的按鈕狀態"""
    redeem_elem = soup.find(lambda el: el.name in ['a', 'button', 'input', 'span', 'div'] and (
        el.text.strip() == "兌換" or el.get('value', '').strip() == "兌換"
    ))
    sold_out_elem = soup.find(lambda el: el.name in ['a', 'button', 'input', 'span', 'div'] and (
        el.text.strip() == "售完" or el.get('value', '').strip() == "售完"
    ))
    
    if redeem_elem:
        return "REDEEM"    # 紅色【兌換】
    if sold_out_elem:
        return "SOLDOUT"   # 黃色【售完】
    return "UNKNOWN"

def check_stock():
    print(f"步驟一：檢查歷史網址 {PRIMARY_PRODUCT_URL} ...")
    
    try:
        res = requests.get(PRIMARY_PRODUCT_URL, headers=HEADERS, timeout=12, allow_redirects=True)
        res.encoding = res.apparent_encoding
        
        # 判斷是否被伺服器跳轉隱藏 (包含 302 重導向或前端 JS 跳轉)
        is_redirected = (
            "box_list.php" in res.url or 
            res.url != PRIMARY_PRODUCT_URL or 
            ("box_list.php" in res.text and "location.href" in res.text)
        )

        # ----------------------------------------------------
        # 情況 A：網址 Z0277 解除隱藏，恢復上架
        # ----------------------------------------------------
        if not is_redirected:
            soup = BeautifulSoup(res.text, "html.parser")
            status = parse_button_status(soup)
            
            if status == "REDEEM":
                print("🔥 原商品頁 Z0277 開放兌換！發送推播！")
                send_telegram(
                    f"🚨 <b>動感活利網【補貨通知】</b>\n\n"
                    f"<b>品項：</b>終獎次元突破造型 (現金積點/現金紅利)\n"
                    f"狀態：🔴 <b>開放兌換中</b>\n\n"
                    f"🔗 快速前往：{PRIMARY_PRODUCT_URL}"
                )
                return
            elif status == "SOLDOUT":
                print("商品頁 Z0277 已重新上架，但按鈕仍顯示黃色【售完】。")
                return
            else:
                print("商品頁存在，但未能確認按鈕狀態，請手動確認。")
                return

        # ----------------------------------------------------
        # 情況 B：Z0277 仍處於隱藏跳轉狀態，啟動備援機制掃描分類頁
        # ----------------------------------------------------
        print("商品頁 Z0277 仍被隱藏跳轉。啟動步驟二：掃描分類列表頁...")
        cat_res = requests.get(CATEGORY_URL, headers=HEADERS, timeout=12)
        cat_res.encoding = cat_res.apparent_encoding
        cat_soup = BeautifulSoup(cat_res.text, "html.parser")

        # 搜尋所有商品連結
        found_products = []
        for a_tag in cat_soup.find_all("a", href=True):
            text = a_tag.get_text(strip=True)
            href = a_tag["href"]
            # 同時符合「終獎次元突破造型」且屬於「現金」兌換通道
            if KEYWORD_TITLE in text and KEYWORD_POINT in text and "goodsview.php" in href:
                full_url = urljoin(CATEGORY_URL, href)
                found_products.append((text, full_url))

        # 去除重複網址
        unique_targets = list({url: title for title, url in found_products}.items())

        if not unique_targets:
            print(f"分類頁中無「{KEYWORD_TITLE}」相關的現金兌換品項，目前完全缺貨/下架。")
            return

        # 若在分類頁發現新商品，逐一進去檢查狀態
        for url, title in unique_targets:
            print(f"在分類頁發現匹配項目：{title} ({url})")
            item_res = requests.get(url, headers=HEADERS, timeout=10)
            item_res.encoding = item_res.apparent_encoding
            item_soup = BeautifulSoup(item_res.text, "html.parser")
            
            item_status = parse_button_status(item_soup)
            if item_status == "REDEEM":
                print("🔥 發現新網址且顯示紅色【兌換】！發送推播！")
                send_telegram(
                    f"🚨 <b>動感活利網【補貨通知 (新網址)】</b>\n\n"
                    f"<b>品項名稱：</b>\n{title}\n\n"
                    f"狀態：🔴 <b>開放兌換中</b>\n"
                    f"🔗 快速前往：{url}"
                )
            elif item_status == "SOLDOUT":
                print("  該新品項目前顯示黃色【售完】。")

    except Exception as e:
        print(f"監控檢查時發生錯誤: {e}")

if __name__ == "__main__":
    check_stock()