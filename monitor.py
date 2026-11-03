import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

PRIMARY_PRODUCT_URL = "https://www.gopower.tw/goodsview.php?g_id=Z0277"
CATEGORY_URL = "https://www.gopower.tw/box_list.php?zId=Z8"
KEYWORD_TITLE = "終獎次元突破造型"
KEYWORD_POINT = "現金"

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

def parse_button_status(soup, page_text):
    """解析網頁按鈕狀態與內容特徵"""
    # 1. 檢查是否有頁面下架/失效的提示
    if any(k in page_text for k in ["查無此商品", "此商品已下架", "商品不存在", "無此商品"]):
        return "NOT_FOUND"

    # 2. 尋找「兌換」按鈕（支援文字、value、alt 或圖片檔名）
    redeem_elem = soup.find(lambda el: el.name in ['a', 'button', 'input', 'span', 'div', 'img'] and (
        el.get_text(strip=True).replace('\xa0', '') == "兌換" or
        el.get('value', '').strip() == "兌換" or
        el.get('alt', '').strip() == "兌換" or
        "btn_exchange" in el.get('src', '').lower()
    ))
    if redeem_elem:
        return "REDEEM"

    # 3. 尋找「售完」按鈕（支援多種常見關鍵字與屬性）
    soldout_keywords = ["售完", "已售完", "已兌畢", "已兌換完畢", "缺貨", "soldout"]
    sold_out_elem = soup.find(lambda el: el.name in ['a', 'button', 'input', 'span', 'div', 'img'] and any(
        k in el.get_text(strip=True).replace('\xa0', '') or 
        k in el.get('value', '').strip() or 
        k in el.get('alt', '').strip() or 
        k in el.get('src', '').lower()
        for k in soldout_keywords
    ))
    if sold_out_elem:
        return "SOLDOUT"

    return "UNKNOWN"

def check_stock():
    print(f"步驟一：檢查歷史網址 {PRIMARY_PRODUCT_URL} ...")
    
    try:
        res = requests.get(PRIMARY_PRODUCT_URL, headers=HEADERS, timeout=12, allow_redirects=True)
        res.encoding = res.apparent_encoding
        
        # 判斷是否被導向回分類頁
        is_redirected = (
            "box_list.php" in res.url or 
            res.url != PRIMARY_PRODUCT_URL or 
            ("box_list.php" in res.text and ("location" in res.text or "replace" in res.text))
        )

        soup = BeautifulSoup(res.text, "html.parser")
        page_text = soup.get_text()

        # ----------------------------------------------------
        # 情況 A：網址 Z0277 存在
        # ----------------------------------------------------
        if not is_redirected:
            status = parse_button_status(soup, page_text)
            
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
                print("狀態正常：商品頁 Z0277 正常連線，目前顯示為【售完】。")
                return
            elif status == "NOT_FOUND":
                print("網頁顯示商品已下架/查無商品，切換至備援機制...")
            else:
                # 依然未辨識出時，印出頁面資訊以便對齊
                print("【除錯訊息】商品頁存在但未辨別出按鈕，擷取頁面元件如下：")
                btn_candidates = [
                    el.get_text(strip=True) or el.get('value') or el.get('alt') or el.get('src')
                    for el in soup.find_all(['button', 'input', 'a', 'img'])
                ]
                btn_candidates = [b for b in btn_candidates if b and len(b) < 30]
                print(f"頁面元件文字/路徑：{btn_candidates[:12]}")

        # ----------------------------------------------------
        # 情況 B：Z0277 隱藏或判定下架，啟動分類頁掃描
        # ----------------------------------------------------
        print("啟動步驟二：掃描分類列表頁...")
        cat_res = requests.get(CATEGORY_URL, headers=HEADERS, timeout=12)
        cat_res.encoding = cat_res.apparent_encoding
        cat_soup = BeautifulSoup(cat_res.text, "html.parser")

        found_products = []
        for a_tag in cat_soup.find_all("a", href=True):
            text = a_tag.get_text(strip=True)
            href = a_tag["href"]
            if KEYWORD_TITLE in text and KEYWORD_POINT in text and "goodsview.php" in href:
                full_url = urljoin(CATEGORY_URL, href)
                found_products.append((text, full_url))

        unique_targets = list({url: title for title, url in found_products}.items())

        if not unique_targets:
            print(f"分類頁中無「{KEYWORD_TITLE}」相關的現金兌換品項，目前完全缺貨/下架。")
            return

        for url, title in unique_targets:
            print(f"在分類頁發現匹配項目：{title} ({url})")
            item_res = requests.get(url, headers=HEADERS, timeout=10)
            item_res.encoding = item_res.apparent_encoding
            item_soup = BeautifulSoup(item_res.text, "html.parser")
            
            item_status = parse_button_status(item_soup, item_soup.get_text())
            if item_status == "REDEEM":
                print("🔥 發現新網址且顯示紅色【兌換】！發送推播！")
                send_telegram(
                    f"🚨 <b>動感活利網【補貨通知 (新網址)】</b>\n\n"
                    f"<b>品項名稱：</b>\n{title}\n\n"
                    f"狀態：🔴 <b>開放兌換中</b>\n"
                    f"🔗 快速前往：{url}"
                )
            elif item_status == "SOLDOUT":
                print("  該新品項目前顯示為【售完】。")

    except Exception as e:
        print(f"監控檢查時發生錯誤: {e}")

if __name__ == "__main__":
    check_stock()
