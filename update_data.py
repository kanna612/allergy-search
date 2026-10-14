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

# 湖池屋のShift_JISエンコーディング対応
html = None
for enc in ["cp932", "shift_jis", "utf-8"]:
    try:
        html = raw_bytes.decode(enc)
        break
    except UnicodeDecodeError:
        continue

if not html:
    html = raw_bytes.decode("cp932", errors="replace")

soup = BeautifulSoup(html, "html.parser")
table = soup.find("table")
if not table:
    raise Exception("Allergen table not found.")

rows = table.find_all("tr")

# 1. アレルゲンヘッダーを厳密に取得してリスト化
headers = []
header_cells = rows[0].find_all(["th", "td"])
for cell in header_cells:
    text = cell.get_text(strip=True)
    headers.append(text)

# "商品名"の次の列からがアレルゲン（卵、乳、小麦...）となるため、
# アレルゲンの開始インデックスを特定
try:
    allergen_start_idx = headers.index("商品名") + 1
except ValueError:
    allergen_start_idx = 1 # 見つからなければデフォルトで1列目から

products = []
current_brand = "その他"

# 2. データの解析（行のズレを防止）
for row in rows[1:]:
    cells = row.find_all(["td", "th"])
    if not cells:
        continue
    
    # --- ブランド行（黄色の行）の判定 ---
    # パターン1: thタグが1つだけの行
    if len(cells) == 1 and row.find("th"):
        current_brand = cells[0].get_text(strip=True)
        continue
    # パターン2: colspanが設定されている行
    if len(cells) == 1 and cells[0].has_attr("colspan"):
        current_brand = cells[0].get_text(strip=True)
        continue
        
    # --- 通常の商品行の判定 ---
    # セル数がヘッダー数と大きく異なる場合は無視（レイアウト崩れ対策）
    if len(cells) < allergen_start_idx:
        continue

    name_cell = cells[0]
    flavor_name = name_cell.get_text(strip=True)
    
    # "商品名"という行自体や、空文字は無視
    if not flavor_name or flavor_name == "商品名" or flavor_name in headers:
        continue

    # 終売アイコンのチェック
    is_discontinued = bool(name_cell.find("img", src=re.compile(r"allergie_icon01\.gif")))

    allergens = []
    
    # 実際のセルとヘッダー列の対応を厳密に取る
    # 商品名が 0 番目、アレルゲンは 1 番目以降（allergen_start_idx から開始）
    for i in range(allergen_start_idx, min(len(cells), len(headers))):
        cell = cells[i]
        # アレルゲンマーク（allergie_mark.gif）、または「●」などの文字があるか判定
        has_img_mark = bool(cell.find("img", src=re.compile(r"allergie_mark\.gif")))
        text_mark = cell.get_text(strip=True)
        
        if has_img_mark or "●" in text_mark or "〇" in text_mark:
            allergen_name = headers[i]
            # 空白や改行が含まれる場合があるのでクリーンアップ
            allergen_name = allergen_name.replace('\n', '').replace('\r', '').strip()
            if allergen_name:
                allergens.append(allergen_name)

    products.append({
        "brand": current_brand,
        "name": flavor_name,
        "discontinued": is_discontinued,
        "allergens": allergens
    })

# JSON保存
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(products, f, ensure_ascii=False, indent=2)

print(f"Successfully parsed {len(products)} products with strict alignment.")
