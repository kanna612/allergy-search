import json
import re
import urllib.request
from bs4 import BeautifulSoup

URL = "https://koikeya.co.jp/allergie/list.html"
OUTPUT_FILE = "koikeya_allergens.json"

req = urllib.request.Request(
    URL,
    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
)

response = urllib.request.urlopen(req, timeout=15)
raw_bytes = response.read()

# 【文字化け対策の決定版】
# 自動判別ではなく、BeautifulSoupの文字コード自動変換機能（UnicodeDammit）に委ねる
soup = BeautifulSoup(raw_bytes, "html.parser", from_encoding="utf-8")
if not soup.find("table"):
    soup = BeautifulSoup(raw_bytes, "html.parser", from_encoding="cp932")

table = soup.find("table")
if not table:
    raise Exception("Allergen table not found.")

rows = table.find_all("tr")

# --- アレルゲンヘッダーの正確な抽出 ---
headers = []
# 1行目の th/td をすべて取得
header_cells = rows[0].find_all(["th", "td"])
for cell in header_cells:
    text = cell.get_text(strip=True).replace("\n", "").replace("\r", "").replace(" ", "")
    # colspanが設定されている場合は、その数だけヘッダーを複製（ズレ防止の要）
    colspan = int(cell.get("colspan", 1))
    for _ in range(colspan):
        headers.append(text)

products = []
current_brand = "その他"

# --- データ行の解析 ---
for row in rows[1:]:
    cells = row.find_all(["td", "th"])
    if not cells:
        continue
    
    # ブランド行（黄色い行）の判定
    if len(cells) == 1 or (len(cells) > 0 and cells[0].has_attr("colspan") and int(cells[0].get("colspan", 1)) > 5):
        current_brand = cells[0].get_text(strip=True)
        continue

    # 商品列の取得
    name_cell = cells[0]
    flavor_name = name_cell.get_text(strip=True).replace('\u3000', ' ') # 全角スペースを半角に変換
    
    if not flavor_name or "商品名" in flavor_name:
        continue

    # 終売アイコン
    is_discontinued = bool(name_cell.find("img", src=re.compile(r"allergie_icon01\.gif")))

    allergens = []
    
    # 【アレルゲン列ズレ対策の決定版】
    # HTML上のセルの位置（colspanを考慮）とヘッダーの位置を計算しながらマッピングする
    current_col_index = 0
    
    for cell in cells:
        colspan = int(cell.get("colspan", 1))
        
        # 商品名の列（通常は先頭の列）はアレルゲンチェックから除外
        is_name_col = ("商品名" in headers[current_col_index] if current_col_index < len(headers) else False)
        
        if not is_name_col and current_col_index < len(headers):
            has_img_mark = bool(cell.find("img", src=re.compile(r"allergie_mark\.gif")))
            text_mark = cell.get_text(strip=True)
            
            # マークがあれば、該当する列のヘッダー名を取得
            if has_img_mark or "●" in text_mark or "〇" in text_mark:
                allergen_name = headers[current_col_index]
                if allergen_name and allergen_name not in ["ブランド", "商品名"]:
                    allergens.append(allergen_name)
                    
        current_col_index += colspan

    products.append({
        "brand": current_brand,
        "name": flavor_name,
        "discontinued": is_discontinued,
        "allergens": list(set(allergens)) # 重複を除外
    })

# JSON保存（UTF-8で強制保存し、ブラウザ側での文字化けを防ぐ）
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(products, f, ensure_ascii=False, indent=2)

print(f"Successfully parsed {len(products)} products.")
