import json
import re
import urllib.request
from bs4 import BeautifulSoup

URL = "https://koikeya.co.jp/allergie/list.html"
OUTPUT_FILE = "koikeya_allergens.json"

# Authoritative allergen sequence used across Koikeya's official table
STANDARD_ALLERGENS = [
    "卵", "乳", "小麦", "そば", "落花生", "えび", "かに", "くるみ",
    "アーモンド", "あわび", "いか", "いくら", "オレンジ", "カシューナッツ", "キウイ",
    "牛肉", "ごま", "さけ", "さば", "大豆", "鶏肉", "豚肉", "バナナ", "まつたけ",
    "もも", "やまいも", "りんご", "ゼラチン", "魚介類"
]

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

# --- Step 1: Dynamically extract allergen headers without '商品名' ---
allergen_headers = []
for row in rows[:10]:
    cell_texts = [c.get_text(strip=True).replace("\n", "").replace("\r", "") for c in row.find_all(["th", "td"])]
    if "卵" in cell_texts and "小麦" in cell_texts:
        for c in row.find_all(["th", "td"]):
            txt = c.get_text(strip=True).replace("\n", "").replace("\r", "").strip()
            # Exclude header labels
            if txt and txt not in ["商品名", "特定原材料", "特定原材料に準ずるもの", "アレルギー情報一覧表"]:
                allergen_headers.append(txt)
        break

# Fallback to standard 29-allergen list if dynamic extraction fails
if len(allergen_headers) < 20:
    allergen_headers = STANDARD_ALLERGENS

print(f"Loaded {len(allergen_headers)} allergen columns:")
print(" ->", ", ".join(allergen_headers[:8]), "...")

products = []
current_brand = "その他"

# --- Step 2: Strict 1-to-1 Cell-to-Allergen Alignment ---
for row in rows:
    cells = row.find_all(["td", "th"])
    if not cells:
        continue

    # Skip top banner/table header rows
    first_text = cells[0].get_text(strip=True)
    if any(h in first_text for h in ["アレルギー情報一覧表", "商品名", "特定原材料", "特定原材料に準ずるもの"]):
        continue

    # Brand header row (yellow section divider)
    if len(cells) == 1 or (cells[0].has_attr("colspan") and int(cells[0].get("colspan", 1)) > 5):
        if first_text:
            current_brand = first_text
        continue

    # Product Flavor Name
    flavor_name = first_text.replace('\u3000', ' ')
    if not flavor_name:
        continue

    # Discontinued icon (allergie_icon01.gif)
    is_discontinued = bool(cells[0].find("img", src=re.compile(r"allergie_icon01\.gif")))

    # The allergen checkboxes start strictly at cells[1]
    allergen_cells = cells[1:]
    matched_allergens = []

    # Direct 1-to-1 index pairing:
    # allergen_cells[0] corresponds to allergen_headers[0] ('卵')
    # allergen_cells[1] corresponds to allergen_headers[1] ('乳')
    # allergen_cells[2] corresponds to allergen_headers[2] ('小麦')
    # allergen_cells[19] corresponds to allergen_headers[19] ('大豆')
    for idx, cell in enumerate(allergen_cells):
        if idx >= len(allergen_headers):
            break

        has_img = bool(cell.find("img", src=re.compile(r"allergie_mark\.gif")))
        text_mark = cell.get_text(strip=True)
        has_symbol = any(s in text_mark for s in ["●", "〇", "○", "1", "含む"])
