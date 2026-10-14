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

# Auto-detect encoding
soup = BeautifulSoup(raw_bytes, "html.parser", from_encoding="cp932")
if not soup.find("table"):
    soup = BeautifulSoup(raw_bytes, "html.parser", from_encoding="utf-8")

table = soup.find("table")
if not table:
    raise Exception("Allergen table not found.")

rows = table.find_all("tr")

# --- Step A: Find the true allergen names header row ---
headers = []
for row in rows[:10]:
    cell_texts = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
    # The true allergen row contains '卵' and '小麦'
    if any(t == "卵" for t in cell_texts) and any(t == "小麦" for t in cell_texts):
        for cell in row.find_all(["th", "td"]):
            txt = cell.get_text(strip=True).replace("\n", "").replace("\r", "").strip()
            colspan = int(cell.get("colspan", 1))
            for _ in range(colspan):
                headers.append(txt)
        break

# If the header row omitted '商品名' due to rowspan, prepend it
if headers and headers[0] != "商品名":
    headers.insert(0, "商品名")

# Fallback if table layout changes unexpectedly
if not headers:
    headers = [
        "商品名", "卵", "乳", "小麦", "そば", "落花生", "えび", "かに", "くるみ",
        "アーモンド", "あわび", "いか", "いくら", "オレンジ", "カシューナッツ", "キウイ",
        "牛肉", "ごま", "さけ", "さば", "大豆", "鶏肉", "豚肉", "バナナ", "まつたけ",
        "もも", "やまいも", "りんご", "ゼラチン", "魚介類"
    ]

print("Detected allergen columns:", headers[1:])

products = []
current_brand = "その他"

# --- Step B: Parse all products and align allergen marks ---
for row in rows:
    cells = row.find_all(["td", "th"])
    if not cells:
        continue

    cell_texts = [c.get_text(strip=True) for c in cells]

    # Skip header rows
    if any(t in ["特定原材料", "特定原材料に準ずるもの"] for t in cell_texts):
        continue
    if any(t == "卵" for t in cell_texts) and any(t == "小麦" for t in cell_texts):
        continue

    # Identify brand rows (yellow section headers)
    if len(cells) == 1 or (cells[0].has_attr("colspan") and int(cells[0].get("colspan", 1)) > 5):
        brand_text = cells[0].get_text(strip=True)
        if brand_text and brand_text not in ["商品名", "アレルギー情報一覧表"]:
            current_brand = brand_text
        continue

    # Product Flavor Name
    name_cell = cells[0]
    flavor_name = name_cell.get_text(strip=True).replace('\u3000', ' ')
    if not flavor_name or flavor_name in ["商品名", "アレルギー情報一覧表"]:
        continue

    # Check for discontinued icon (allergie_icon01.gif)
    is_discontinued = bool(name_cell.find("img", src=re.compile(r"allergie_icon01\.gif")))

    # Check for allergen marks (allergie_mark.gif or text symbols)
    allergens = []
    col_idx = 0

    for cell in cells:
        colspan = int(cell.get("colspan", 1))

        # Ignore the first column (Product Name)
        if col_idx > 0 and col_idx < len(headers):
            has_img_mark = bool(cell.find("img", src=re.compile(r"allergie_mark\.gif")))
            text_val = cell.get_text(strip=True)
            has_text_mark = any(m in text_val for m in ["●", "〇", "○", "1", "含む"])

            if has_img_mark or has_text_mark:
                allergen_name = headers[col_idx]
                if allergen_name and allergen_name not in ["商品名", "特定原材料", "特定原材料に準ずるもの"]:
                    allergens.append(allergen_name)

        col_idx += colspan

    products.append({
        "brand": current_brand,
        "name": flavor_name,
        "discontinued": is_discontinued,
        "allergens": list(dict.fromkeys(allergens)) # remove duplicates while preserving order
    })

# Save as UTF-8 JSON
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(products, f, ensure_ascii=False, indent=2)

print(f"Successfully processed {len(products)} products with accurate allergens.")
