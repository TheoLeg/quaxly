"""Country map image generation.

Renders with matplotlib only. The country borders are pulled at runtime as a
lightweight GeoJSON (Natural Earth 50m) and cached under data/quiz_map_cache, so
the image ships without the heavy geopandas/GDAL stack.
"""

import asyncio
import io
import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon as MplPolygon

GEOJSON_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_50m_admin_0_countries.geojson"
)

_executor = ThreadPoolExecutor(max_workers=2)
_features: list | None = None

CACHE_DIR = os.path.join(os.getcwd(), "data", "quiz_map_cache")
CACHE_FILE = os.path.join(CACHE_DIR, "ne_50m_admin_0_countries.geojson")

# Our country names follow Natural Earth's abbreviated NAME field; a few differ
# between dataset revisions, so map those to what the 50m file actually uses.
NAME_ALIASES: dict[str, list[str]] = {
    "S. Korea": ["South Korea"],
    "N. Korea": ["North Korea"],
    "Macedonia": ["North Macedonia"],
    "Turkey": ["Türkiye"],
}

_MATCH_FIELDS = ("NAME", "ADMIN", "NAME_LONG", "BRK_NAME", "NAME_EN")


def _load_world() -> list:
    global _features
    if _features is not None:
        return _features

    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
    else:
        with urllib.request.urlopen(GEOJSON_URL, timeout=60) as resp:
            raw = resp.read()
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "wb") as f:
            f.write(raw)
        data = json.loads(raw)

    _features = data["features"]
    return _features


def _exterior_rings(geometry: dict):
    """Yield each polygon's exterior ring as a list of [lon, lat] points."""
    gtype = geometry["type"]
    coords = geometry["coordinates"]
    if gtype == "Polygon":
        yield coords[0]
    elif gtype == "MultiPolygon":
        for polygon in coords:
            yield polygon[0]


def _find_country(features: list, name: str) -> dict | None:
    targets = {name.lower(), *(a.lower() for a in NAME_ALIASES.get(name, []))}
    for feature in features:
        props = feature["properties"]
        values = {
            props[k].lower() for k in _MATCH_FIELDS if props.get(k)
        }
        if targets & values:
            return feature
    return None


def _generate_map_sync(country_name_en: str) -> bytes:
    features = _load_world()
    target = _find_country(features, country_name_en)
    if target is None:
        raise ValueError(f"country '{country_name_en}' not found")

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.set_facecolor("#0d2137")
    fig.patch.set_facecolor("#06111e")

    background = [
        MplPolygon(ring, closed=True)
        for feature in features
        for ring in _exterior_rings(feature["geometry"])
    ]
    ax.add_collection(
        PatchCollection(
            background, facecolor="#1e3d20", edgecolor="#3a6e3a", linewidths=0.35
        )
    )

    target_patches = []
    xs: list[float] = []
    ys: list[float] = []
    for ring in _exterior_rings(target["geometry"]):
        target_patches.append(MplPolygon(ring, closed=True))
        for x, y in ring:
            xs.append(x)
            ys.append(y)
    ax.add_collection(
        PatchCollection(
            target_patches, facecolor="#e63946", edgecolor="#ff8fa3", linewidths=1.5
        )
    )

    minx, miny, maxx, maxy = min(xs), min(ys), max(xs), max(ys)
    pad = max(maxx - minx, maxy - miny, 10.0) * 2.0
    xlim = (max(-180.0, minx - pad), min(180.0, maxx + pad))
    ylim = (max(-90.0, miny - pad), min(90.0, maxy + pad))

    xr = xlim[1] - xlim[0]
    yr = ylim[1] - ylim[0]
    if xr / max(yr, 0.1) > 3.0:
        mid = (ylim[0] + ylim[1]) / 2
        half = xr / 3.0 / 2
        ylim = (max(-90.0, mid - half), min(90.0, mid + half))
    elif yr / max(xr, 0.1) > 3.0:
        mid = (xlim[0] + xlim[1]) / 2
        half = yr * 3.0 / 2
        xlim = (max(-180.0, mid - half), min(180.0, mid + half))

    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_aspect("equal")
    ax.axis("off")

    buf = io.BytesIO()
    plt.savefig(
        buf,
        format="png",
        dpi=130,
        bbox_inches="tight",
        facecolor=fig.get_facecolor(),
        edgecolor="none",
    )
    buf.seek(0)
    plt.close(fig)
    return buf.getvalue()


async def generate_country_map(country_name_en: str) -> io.BytesIO:
    loop = asyncio.get_event_loop()
    img_bytes = await loop.run_in_executor(
        _executor, _generate_map_sync, country_name_en
    )
    return io.BytesIO(img_bytes)
