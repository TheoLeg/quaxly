"""Country map image generation with geopandas + matplotlib.

Natural Earth data is downloaded once and cached under data/quiz_map_cache.
"""

import asyncio
import io
import os
import warnings
from concurrent.futures import ThreadPoolExecutor

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

_executor = ThreadPoolExecutor(max_workers=2)
_world_data = None

CACHE_DIR = os.path.join(os.getcwd(), "data", "quiz_map_cache")
CACHE_FILE = os.path.join(CACHE_DIR, "countries.shp")

GEOPANDAS_ALIASES: dict[str, list[str]] = {
    "Turkey": ["Turkey", "Türkiye"],
    "S. Korea": ["S. Korea", "South Korea"],
    "N. Korea": ["N. Korea", "North Korea"],
    "Czechia": ["Czechia", "Czech Republic"],
    "Macedonia": ["Macedonia", "North Macedonia"],
    "United States of America": ["United States of America", "United States"],
    "Dem. Rep. Congo": ["Dem. Rep. Congo", "Democratic Republic of the Congo"],
    "Bosnia and Herz.": ["Bosnia and Herz.", "Bosnia and Herzegovina"],
}


def _load_world():
    global _world_data
    if _world_data is not None:
        return _world_data

    import geopandas as gpd

    if os.path.exists(CACHE_FILE):
        _world_data = gpd.read_file(CACHE_FILE)
        return _world_data

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            _world_data = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
            return _world_data
        except Exception:
            pass

    url = (
        "https://naciscdn.org/naturalearth/10m/cultural/"
        "ne_10m_admin_0_countries.zip"
    )
    _world_data = gpd.read_file(url)
    os.makedirs(CACHE_DIR, exist_ok=True)
    _world_data.to_file(CACHE_FILE)
    return _world_data


def _find_country(world, name: str):
    result = world[world["NAME"] == name]
    if not result.empty:
        return result
    for alias in GEOPANDAS_ALIASES.get(name, []):
        result = world[world["NAME"] == alias]
        if not result.empty:
            return result
    return world[world["NAME"].str.lower() == name.lower()]


def _generate_map_sync(country_name_en: str) -> bytes:
    world = _load_world()
    target = _find_country(world, country_name_en)

    if target.empty:
        raise ValueError(f"country '{country_name_en}' not found")

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.set_facecolor("#0d2137")
    fig.patch.set_facecolor("#06111e")

    world.plot(ax=ax, color="#1e3d20", edgecolor="#3a6e3a", linewidth=0.35)
    target.plot(ax=ax, color="#e63946", edgecolor="#ff8fa3", linewidth=1.5)

    # Frame the view on the largest landmass, not the union of every part: many
    # countries (France, USA, Chile, Ecuador…) have far-flung overseas
    # territories whose total bounds would zoom the map out to the whole world.
    polygons = []
    for geom in target.geometry:
        if geom is None:
            continue
        if geom.geom_type == "MultiPolygon":
            polygons.extend(geom.geoms)
        else:
            polygons.append(geom)
    main = max(polygons, key=lambda g: g.area)
    bounds = main.bounds

    w = bounds[2] - bounds[0]
    h = bounds[3] - bounds[1]
    pad = max(w, h, 10.0) * 2.0

    xlim = (max(-180.0, bounds[0] - pad), min(180.0, bounds[2] + pad))
    ylim = (max(-90.0, bounds[1] - pad), min(90.0, bounds[3] + pad))

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
