"""
worldbox_realworld.py
------------------------------------
Stylized "WorldBox-like" world generator.
Each country appears as a regular polygon (square, hexagon, etc.)
centered roughly at its real-world location, with population rounded
up to the nearest million.

Usage:
    pip install geopandas shapely matplotlib pandas fuzzywuzzy python-levenshtein requests
    python worldbox_realworld.py

Output:
    - worldbox_map.png     (the generated world map)
    - worldbox_state.json  (country data)
"""

import math
import json
import requests
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
from fuzzywuzzy import process
from math import ceil

POP_DATA_URL = "https://datahub.io/core/population/r/population.csv"
POP_YEAR = 2023
MAP_FILE = "worldbox_map.png"
STATE_FILE = "worldbox_state.json"

def download_population_data():
    """Download global population CSV (World Bank / DataHub mirror)."""
    r = requests.get(POP_DATA_URL, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(pd.compat.StringIO(r.text))
    if "Country Name" in df.columns:
        name_col = "Country Name"
    else:
        name_col = df.columns[0]
    if "Year" in df.columns:
        year_col = "Year"
    else:
        year_col = [c for c in df.columns if "year" in c.lower()][0]
    val_col = [c for c in df.columns if c.lower() in ("value", "population")][0]
    if POP_YEAR in df[year_col].unique():
        df = df[df[year_col] == POP_YEAR]
    else:
        df = df.sort_values(by=[name_col, year_col]).groupby(name_col).tail(1)
    df = df.rename(columns={name_col: "country", val_col: "population"})
    df["population"] = pd.to_numeric(df["population"], errors="coerce")
    return df.dropna()

def make_regular_polygon(cx, cy, radius, sides, rotation=0):
    """Return a regular polygon as a shapely Polygon."""
    pts = []
    for i in range(sides):
        ang = rotation + 2 * math.pi * i / sides
        pts.append((cx + radius * math.cos(ang), cy + radius * math.sin(ang)))
    return Polygon(pts)

def main():
    print("🌍 Loading base geography (Natural Earth)...")
    world = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))[["name", "geometry", "iso_a3"]]
    world = world.rename(columns={"name": "country", "iso_a3": "iso3"})

    print("📈 Downloading population data...")
    pop_df = download_population_data()
    pop_names = list(pop_df["country"].unique())

    print("🔍 Matching populations to countries...")
    pop_map = {}
    for _, row in world.iterrows():
        cname = row["country"]
        match = pop_df[pop_df["country"].str.lower() == cname.lower()]
        if not match.empty:
            pop_map[cname] = match["population"].iloc[0]
        else:
            best, score = process.extractOne(cname, pop_names)
            if score > 85:
                pop_map[cname] = pop_df[pop_df["country"] == best]["population"].iloc[0]
            else:
                pop_map[cname] = None

    print("🧱 Building regular-polygon world...")
    fig, ax = plt.subplots(figsize=(18, 9))
    ax.set_facecolor("#cfeef2")
    countries = []

    for _, row in world.iterrows():
        geom = row["geometry"]
        if geom is None or geom.is_empty:
            continue
        centroid = geom.representative_point()
        cx, cy = centroid.x, centroid.y
        area = geom.area
        radius = max(0.5, (area ** 0.5) * 0.6)
        sides = 4 if radius < 0.8 else (6 if radius < 2.0 else (8 if radius < 4.0 else 12))
        poly = make_regular_polygon(cx, cy, radius, sides, rotation=0.5)
        gpd.GeoSeries([poly]).plot(ax=ax, edgecolor="black", linewidth=0.4, alpha=0.9)

        pop_val = pop_map.get(row["country"], None)
        pop_millions = int(ceil(pop_val / 1_000_000)) if pop_val else None
        countries.append({
            "country": row["country"],
            "iso3": row["iso3"],
            "population_raw": pop_val,
            "population_millions": pop_millions
        })

    ax.set_title(f"WorldBox-style Regular Polygons — Population (Millions, {POP_YEAR})")
    ax.set_xlim(-180, 180)
    ax.set_ylim(-60, 90)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(MAP_FILE, dpi=220)
    print(f"🖼️  Saved map to {MAP_FILE}")

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"year": POP_YEAR, "countries": countries}, f, indent=2, ensure_ascii=False)
    print(f"📁  Saved world state to {STATE_FILE}")
    print("✅ Done!")

if __name__ == "__main__":
    main()
