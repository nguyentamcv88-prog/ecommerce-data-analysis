#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETSY SPY — Cong cu nghien cuu niche tren Etsy
==============================================
Lay du lieu that tu Etsy API, TU PHAN LOAI NICHE tu ten san pham,
toi uu toc do & quota.
Khi xong: tao 1 FOLDER moi ten "spy etsy YYYY-MM-DD", ben trong co:
   - 1 file Excel TONG HOP (nhieu sheet, co phan tich theo NICHE)
   - cac file CSV TUNG PHAN trong thu muc con

CACH CHAY:
    pip install requests pandas openpyxl
    python etsy_spy.py
"""

import requests, pandas as pd, time, os, re, html
from datetime import datetime, timezone

# ============== CAU HINH — CHI SUA PHAN NAY ==============
API_KEY = "amx6ki0pfya7noa2vpdmi01f"
SHARED_SECRET = "q6zblbr345"

# Tu khoa de TIM KIEM tren Etsy (con NICHE se duoc phan loai tu ten SP)
KEYWORDS = [
    "funny dad shirt", "raccoon shirt", "mama shirt", "hunting shirt",
    "cat lover shirt", "teacher shirt", "christian shirt", "retro vintage shirt",
    "halloween shirt", "nurse shirt",
]

LISTINGS_PER_KEYWORD = 3000   # so san pham moi tu khoa
SHOPS_TO_ANALYZE     = 50
QPS_PAUSE            = 0.12
QUOTA_SAFETY         = 50
OUTPUT_BASE          = "."
# =========================================================

BASE = "https://openapi.etsy.com/v3/application"
HEADERS = {"x-api-key": f"{API_KEY}:{SHARED_SECRET}"}
quota_remaining = [99999]


# ============== PHAN LOAI NICHE TU TEN SAN PHAM ==============
def classify_niche(title):
    s = str(title).lower()
    rules = [
        (r"custom|personalized|photo|your name|your photo", "Ca nhan hoa (Custom)"),
        (r"father|dad|papa|grandpa|daddy|pops|pawpaw", "Father's Day / Dad"),
        (r"mama|mom|mother|mommy|grandma|mimi|nana|wife|wifey", "Mom / Family"),
        (r"jesus|faith|christian|bible|god|blessed|prayer|psalm|church", "Christian / Faith"),
        (r"camo|hunting|fishing|deer|duck|mallard|outdoor|mossy|buck|waterfowl", "Hunting / Outdoor"),
        (r"raccoon|trash panda|opossum|possum", "Raccoon / Meme thu"),
        (r"cat|kitten|kitty|meow|feline", "Cat lover"),
        (r"dog|puppy|doggo|pup|canine", "Dog lover"),
        (r"teacher|teaching|classroom|educator|school", "Teacher / Giao vien"),
        (r"nurse|nursing|rn |medical|hospital|scrub", "Nurse / Y te"),
        (r"halloween|spooky|ghost|pumpkin|witch|skeleton", "Halloween"),
        (r"christmas|santa|xmas|holiday|merry", "Christmas / Le"),
        (r"\btour\b|concert|setlist|on tour|world tour|eras tour|live tour|band merch", "Concert / Band Tour"),
        (r"retro|vintage|y2k|90s|80s|nostalgia|washed", "Retro / Vintage"),
        (r"funny|sarcastic|humor|meme|silly|sassy|snarky", "Funny / Humor"),
        (r"anime|manga|otaku|kawaii|saiyan", "Anime"),
        (r"usa|america|patriot|freedom|veteran|flag|4th of july", "Patriotic / USA"),
        (r"beach|coastal|summer|ocean|lake|nautical|salty", "Beach / Coastal"),
        (r"football|basketball|baseball|soccer|sports|team|game day", "Sports / Team"),
    ]
    for pat, name in rules:
        if re.search(pat, s):
            return name
    return "Khac / Other"
# =============================================================


def _get(url, params=None):
    for _ in range(3):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        except Exception as e:
            print(f"  ! Loi ket noi: {e}"); time.sleep(3); continue
        rem = r.headers.get("X-RateLimit-Remaining")
        if rem is not None:
            try: quota_remaining[0] = int(rem)
            except: pass
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            print("  ... cham gioi han, cho 10 giay"); time.sleep(10); continue
        print(f"  ! Loi HTTP {r.status_code}: {r.text[:150]}")
        return None
    return None


def ts_to_date(ts):
    if not ts: return ""
    try: return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except: return ""


def days_since(ts):
    if not ts: return None
    try:
        d = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        return max((datetime.now(timezone.utc) - d).days, 1)
    except: return None


def quota_ok():
    if quota_remaining[0] < QUOTA_SAFETY:
        print(f"\n!  Quota gan het (con {quota_remaining[0]}). Dung lai.")
        return False
    return True


def search_listings(keyword, total):
    print(f"\n[Tim] '{keyword}' (muc tieu {total})...")
    rows, offset = [], 0
    while len(rows) < total:
        if not quota_ok() or offset >= 50000:
            break
        data = _get(f"{BASE}/listings/active",
                    {"keywords": keyword, "limit": 100, "offset": offset, "sort_on": "score"})
        if not data or not data.get("results"):
            break
        for it in data["results"]:
            price = it.get("price") or {}
            amt = price.get("amount")
            created = it.get("original_creation_timestamp") or it.get("created_timestamp")
            age = days_since(created); favs = it.get("num_favorers", 0) or 0
            title = html.unescape((it.get("title") or "")[:140])
            rows.append({
                "search_keyword": keyword,
                "niche": classify_niche(title),     # NICHE phan loai tu ten
                "listing_id": it.get("listing_id"),
                "title": title,
                "price": round(amt / price.get("divisor", 100), 2) if amt is not None else None,
                "currency": price.get("currency_code", ""), "shop_id": it.get("shop_id"),
                "num_favorers": favs, "views": it.get("views", 0), "quantity": it.get("quantity", 0),
                "created_date": ts_to_date(created), "age_days": age,
                "fav_per_day": round(favs / age, 3) if age else None,
                "tags": ", ".join((it.get("tags") or [])[:13]), "url": it.get("url", ""),
            })
        got = len(data["results"]); offset += got
        print(f"  -> {len(rows)} sp (quota con {quota_remaining[0]})")
        if got < 100:
            break
        time.sleep(QPS_PAUSE)
    return rows[:total]


def get_shop(shop_id):
    data = _get(f"{BASE}/shops/{shop_id}")
    if not data: return None
    created = data.get("create_date") or data.get("creation_tsz")
    return {
        "shop_id": shop_id, "shop_name": data.get("shop_name", ""),
        "total_sales": data.get("transaction_sold_count", 0),
        "num_listings": data.get("listing_active_count", 0),
        "review_count": data.get("review_count", 0),
        "review_average": data.get("review_average", 0),
        "num_favorers": data.get("num_favorers", 0),
        "opened_date": ts_to_date(created), "shop_age_days": days_since(created),
        "url": data.get("url", ""),
    }


def main():
    # === Tao folder ket qua ten "spy etsy 01" (tu tang so neu da co) ===
    n = 1
    while True:
        folder = os.path.join(OUTPUT_BASE, f"spy etsy {n:02d}")
        if not os.path.exists(folder):
            break
        n += 1
    os.makedirs(folder, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    parts = os.path.join(folder, "tung_phan")
    os.makedirs(parts, exist_ok=True)
    print(f"Folder ket qua: {folder}")

    # === Lay du lieu ===
    all_listings = []
    for kw in KEYWORDS:
        if not quota_ok(): break
        all_listings += search_listings(kw, LISTINGS_PER_KEYWORD)

    df = pd.DataFrame(all_listings)
    if df.empty:
        print("\nKhong lay duoc du lieu."); return
    print(f"\n>>> Tong {len(df)} san pham, phan thanh {df['niche'].nunique()} niche")

    # === Lay shop ===
    shops = []
    if quota_ok():
        top_ids = df["shop_id"].dropna().value_counts().head(SHOPS_TO_ANALYZE).index.tolist()
        print(f"\n[Shop] lay {len(top_ids)} shop...")
        for sid in top_ids:
            if not quota_ok(): break
            info = get_shop(int(sid))
            if info:
                shops.append(info)
                print(f"  - {info['shop_name']:<24} | {info['total_sales']:>8,} ban")
            time.sleep(QPS_PAUSE)
    df_shops = pd.DataFrame(shops)
    if not df_shops.empty:
        df_shops = df_shops.sort_values("total_sales", ascending=False)

    # === Tong hop theo NICHE (phan loai tu ten SP) ===
    niche_sum = (df.groupby("niche").agg(
                    so_sp=("listing_id", "count"), gia_tb=("price", "mean"),
                    fav_tong=("num_favorers", "sum"), fav_tb=("num_favorers", "mean"),
                    views_tb=("views", "mean"), fav_per_day_tb=("fav_per_day", "mean"))
                 .round(2).sort_values("fav_tong", ascending=False).reset_index())

    # === Xuat file RIENG (CSV) — moi NICHE mot file ===
    df_clean = df.copy()
    df_clean = df_clean[(df_clean["price"] > 0) & (df_clean["price"] < 500)]  # loc gia loi
    for nm in df_clean["niche"].unique():
        safe = re.sub(r"[^\w]+", "_", nm).strip("_")
        df_clean[df_clean["niche"] == nm].sort_values("num_favorers", ascending=False)\
            .to_csv(os.path.join(parts, f"niche_{safe}.csv"), index=False)
    niche_sum.to_csv(os.path.join(parts, "00_tong_quan_niche.csv"), index=False)
    if not df_shops.empty:
        df_shops.to_csv(os.path.join(parts, "00_shop_so_ban.csv"), index=False)
    df_clean.sort_values("num_favorers", ascending=False)\
        .to_csv(os.path.join(parts, "00_tat_ca_san_pham.csv"), index=False)

    # === Xuat file Excel TONG HOP ===
    excel_path = os.path.join(folder, f"TONG_HOP_spy_etsy_{today}.xlsx")
    with pd.ExcelWriter(excel_path, engine="openpyxl") as xl:
        niche_sum.to_excel(xl, sheet_name="Tong quan NICHE", index=False)
        if not df_shops.empty:
            df_shops.to_excel(xl, sheet_name="Shop (so ban)", index=False)
        df_clean.sort_values("fav_per_day", ascending=False).to_excel(xl, sheet_name="SP (toc do hot)", index=False)
        df_clean.sort_values("num_favorers", ascending=False).to_excel(xl, sheet_name="SP (luot thich)", index=False)

    print(f"\n=== XONG ===")
    print(f"Folder: {folder}")
    print(f"  - File tong hop: TONG_HOP_spy_etsy_{today}.xlsx")
    print(f"  - Thu muc 'tung_phan': {df_clean['niche'].nunique()} file niche + 3 file tong")
    print(f"  {len(df)} san pham | {df['niche'].nunique()} niche | {len(df_shops)} shop | quota con {quota_remaining[0]}")


if __name__ == "__main__":
    main()
