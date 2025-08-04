import json
import markdown
import yaml
from pathlib import Path
from time import sleep
from geopy import Nominatim
import folium
import logging

# === Config ===
TALKS_DIR = "talks"
CACHE_FILE = "_cache/geocache.json"
OUTPUT_MAP = "_site/talk_map.html"


def talkmap(
    talks_dir: str = TALKS_DIR,
    cache_file: str = CACHE_FILE,
    output_map: str = OUTPUT_MAP,
    user_agent: str = "talk_map_folium",
    sleep_seconds: float = 1.0,
):
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    cache_path = Path(cache_file)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if cache_path.exists():
        with cache_path.open("r", encoding="utf-8") as f:
            cache = json.load(f)
    else:
        cache = {}

    geocoder = Nominatim(user_agent=user_agent)
    locations_with_meta = []

    for md_file in Path(talks_dir).glob("*.qmd"):
        text = md_file.read_text(encoding="utf-8")
        if text.startswith("---"):
            end = text.find("---", 3)
            if end != -1:
                yaml_text = text[3:end].strip()
                meta = yaml.safe_load(yaml_text)
                location = meta.get("location", "").strip()
                if not location:
                    continue
            else:
                continue
        else:
            continue

        # Use cache or geocode
        if location in cache:
            geo = cache[location]
            lat, lon = geo["latitude"], geo["longitude"]
        else:
            try:
                geo_info = geocoder.geocode(location)
                if not geo_info:
                    logger.warning(f"⚠️ Not found: {location}")
                    continue
                lat, lon = geo_info.latitude, geo_info.longitude
                cache[location] = {
                    "latitude": lat,
                    "longitude": lon,
                    "address": geo_info.address,
                }
                sleep(sleep_seconds)  # Respect rate limits
            except Exception as e:
                logger.error(f"❌ Error geocoding {location}: {e}")
                continue

        locations_with_meta.append((lat, lon, meta))

    with cache_path.open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

    if locations_with_meta:
        avg_lat = sum(lat for lat, _, _ in locations_with_meta) / len(
            locations_with_meta,
        )
        avg_lon = sum(lon for _, lon, _ in locations_with_meta) / len(
            locations_with_meta,
        )
        default_center = [avg_lat, avg_lon]
    else:
        default_center = [0, 0]

    m = folium.Map(location=default_center, zoom_start=2)

    for lat, lon, meta in locations_with_meta:
        title = f"<b>{meta.get('title', 'No title')}</b>"
        venue = f"Venue: {meta.get('venue')}" if meta.get("venue") else ""
        date = f"Date: {meta.get('date')}" if meta.get("date") else ""
        desc = markdown.markdown(
            meta.get("description", ""),
            output_format="html",
        ).strip()

        popup_html = f"{title}<br>{venue}<br>{date}<br><br>{desc}".strip()
        popup_html = "<br>".join(
            [line for line in popup_html.split("<br>") if line.strip()],
        )

        folium.Marker([lat, lon], popup=folium.Popup(popup_html, max_width=300)).add_to(
            m,
        )

    m.save(output_map)
    logger.info(f"Map saved to {output_map}")


def main():
    talkmap()


if __name__ == "__main__":
    main()
