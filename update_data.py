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

# Koikeya's website uses Japanese Shift_JIS / CP932
html = None
for enc in ["cp932", "shift_jis", "euc-jp", "utf-8"]:
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

# 1. Allergen header columns
headers = []
for cell in rows[0].find_all(["th", "td"]):
    text = cell.get_text(strip=True)
    if text and text not in ["商品名", "ブランド"]:
        headers.append(text)

products = []
current_brand = "その他"

# 2. Extract rows
for row in rows[1:]:
    th_cells = row.find_all("th")
    td_cells = row.find_all("td")

    if len(td_cells) == 0 and len(th_cells) == 1:
        current_brand = th_cells[0].get_text(strip=True)
        continue
    if len(td_cells) == 1 and td_cells[0].has_attr("colspan"):
        current_brand = td_cells[0].get_text(strip=True)
        continue

    cells = row.find_all(["td", "th"])
    if not cells or len(cells) < 2:
        continue

    name_cell = cells[0]
    flavor_name = name_cell.get_text(strip=True)
    if not flavor_name or flavor_name == "商品名":
        continue

    is_discontinued = bool(name_cell.find("img", src=re.compile(r"allergie_icon01\.gif")))

    allergens = []
    for idx, c in enumerate(cells[1:]):
        if c.find("img", src=re.compile(r"allergie_mark\.gif")) and idx < len(headers):
            allergens.append(headers[idx])

    products.append({
        "brand": current_brand,
        "name": flavor_name,
        "discontinued": is_discontinued,
        "allergens": allergens
    })

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(products, f, ensure_ascii=False, indent=2)

print(f"Successfully parsed {len(products)} products.")
