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

# --- 1. Map the true allergen headers accurately ---
headers = []
header_row_index = 0

for i, row in enumerate(rows[:10]):
    cell_texts = [c.get_text(strip=True).replace("\n", "").replace("\r", "") for c in row.find_all(["th", "td"])]
    # Look for the row that actually contains the allergen names
    if "卵" in cell_texts and "小麦" in cell_texts:
        header_row_index = i
        # Expand any colspans just in case, though subheaders rarely have them
        for cell in row.find_all(["th", "td"]):
            txt = cell.get_text(strip=True).replace("\n", "").replace("\r", "").strip()
            colspan = int(cell.get("colspan", 1))
            for _ in range(colspan):
                headers.append(txt)
        break

# The header row we extracted might be missing the "商品名" (Product Name) at index 0 
# because it was merged (rowspan) from the row above it.
if headers and headers[0] == "卵":
    headers.insert(0, "商品名")

print("Mapped Header Indices:")
for idx, h in enumerate(headers):
    print(f"  Col {idx}: {h}")

products = []
current_brand = "その他"

# --- 2. Process product rows with strict index alignment ---
for row in rows[header_row_index + 1:]:
    cells = row.find_all(["td", "th"])
    if not cells:
        continue

    # Identify brand section headers (yellow rows)
    # They usually have 1 cell with a large colspan, or just a single th element
    if len(cells) == 1 or (cells[0].has_attr("colspan") and int(cells[0].get("colspan", 1)) > 5):
        brand_text = cells[0].get_text(strip=True)
        if brand_text and "商品名" not in brand_text:
            current_brand = brand_text
        continue

    # The first cell of a product row is the product name
    name_cell = cells[0]
    flavor_name = name_cell.get_text(strip=True).replace('\u3000', ' ')
    
    # Skip if it's a repeated header row
    if not flavor_name or flavor_name == "商品名" or "特定原材料" in flavor_name:
        continue

    is_discontinued = bool(name_cell.find("img", src=re.compile(r"allergie_icon01\.gif")))

    allergens = []
    
    # In product rows, index 0 is always the product name.
    # Therefore, the data cells start at index 1.
    # We loop through the remaining cells and map them to headers[1], headers[2], etc.
    data_cells = cells[1:]
    
    # We must track the logical column index to account for any data colspans
    logical_col_idx = 1 
    
    for cell in data_cells:
        colspan = int(cell.get("colspan", 1))
        
        if logical_col_idx < len(headers):
            has_img_mark = bool(cell.find("img", src=re.compile(r"allergie_mark\.gif")))
            text_val = cell.get_text(strip=True)
            has_text_mark = any(m in text_val for m in ["●", "〇", "○", "1", "含む"])

            if has_img_mark or has_text_mark:
                allergen_name = headers[logical_col_idx]
                if allergen_name and allergen_name not in ["商品名", "ブランド"]:
                    allergens.append(allergen_name)
                    
        logical_col_idx += colspan

    products.append({
        "brand": current_brand,
        "name": flavor_name,
        "discontinued": is_discontinued,
        "allergens": list(dict.fromkeys(allergens)) # remove duplicates, preserve order
    })

# Save output
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(products, f,ensure_ascii=False, indent=2)

print(f"Successfully processed {len(products)} products.")
