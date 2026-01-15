"""
Talk map generator using Folium.

Generates an interactive map of talk locations with metadata from QMD files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from time import sleep
from typing import Dict, List, Tuple

import folium
import markdown
from geopy import Nominatim

# Add parent directory to path for infrastructure imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure import YamlLoader, get_logger

logger = get_logger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

DEFAULT_TALKS_DIR = "talks"
DEFAULT_CACHE_FILE = "_cache/geocache.json"
DEFAULT_OUTPUT_MAP = "_site/talk_map.html"
DEFAULT_USER_AGENT = "talk_map_folium"
DEFAULT_SLEEP_SECONDS = 1.0


# ============================================================================
# GEOCODING
# ============================================================================


class GeoCache:
    """Manages geocoding cache for talk locations."""

    def __init__(self, cache_path: Path):
        """Initialize geocache.

        Args:
            cache_path: Path to cache JSON file
        """
        self.cache_path = cache_path
        self.cache: Dict[str, Dict] = {}
        self._load()

    def _load(self) -> None:
        """Load cache from disk."""
        if self.cache_path.exists():
            try:
                with self.cache_path.open("r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                logger.info(f"Loaded geocache with {len(self.cache)} locations")
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
                self.cache = {}
        else:
            self.cache = {}
            # Ensure cache directory exists
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        """Save cache to disk."""
        try:
            with self.cache_path.open("w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved geocache with {len(self.cache)} locations")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def get(self, location: str) -> Dict | None:
        """Get cached geocoding result.

        Args:
            location: Location string

        Returns:
            Cached geocoding data or None
        """
        return self.cache.get(location)

    def set(
        self, location: str, latitude: float, longitude: float, address: str
    ) -> None:
        """Cache geocoding result.

        Args:
            location: Location string
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            address: Full address from geocoder
        """
        self.cache[location] = {
            "latitude": latitude,
            "longitude": longitude,
            "address": address,
        }


def geocode_location(
    location: str,
    geocoder: Nominatim,
    cache: GeoCache,
    sleep_seconds: float = 1.0,
) -> Tuple[float, float] | None:
    """Geocode a location string to coordinates.

    Args:
        location: Location string to geocode
        geocoder: Nominatim geocoder instance
        cache: GeoCache instance
        sleep_seconds: Sleep time between API calls

    Returns:
        Tuple of (latitude, longitude) or None if geocoding failed
    """
    # Check cache first
    cached = cache.get(location)
    if cached:
        return (cached["latitude"], cached["longitude"])

    # Geocode with API
    try:
        geo_info = geocoder.geocode(location)
        if not geo_info:
            logger.warning(f"⚠️  Location not found: {location}")
            return None

        lat, lon = geo_info.latitude, geo_info.longitude
        cache.set(location, lat, lon, geo_info.address)

        # Respect rate limits
        sleep(sleep_seconds)

        return (lat, lon)

    except Exception as e:
        logger.error(f"❌ Error geocoding '{location}': {e}")
        return None


# ============================================================================
# TALK PROCESSING
# ============================================================================


def extract_talks_metadata(
    talks_dir: Path,
    yaml_loader: YamlLoader,
    geocoder: Nominatim,
    cache: GeoCache,
    sleep_seconds: float = 1.0,
) -> List[Tuple[float, float, Dict]]:
    """Extract talk metadata with geocoded locations.

    Args:
        talks_dir: Directory containing talk QMD files
        yaml_loader: YamlLoader instance
        geocoder: Nominatim geocoder instance
        cache: GeoCache instance
        sleep_seconds: Sleep time between API calls

    Returns:
        List of tuples: (latitude, longitude, metadata_dict)
    """
    locations_with_meta = []

    for qmd_file in talks_dir.glob("*.qmd"):
        try:
            # Load metadata
            meta = yaml_loader.load_from_path(qmd_file)
            if not meta:
                logger.debug(f"No metadata in {qmd_file.name}")
                continue

            location = meta.get("location", "").strip()
            if not location:
                logger.debug(f"No location in {qmd_file.name}")
                continue

            # Geocode location
            coords = geocode_location(location, geocoder, cache, sleep_seconds)
            if coords:
                lat, lon = coords
                locations_with_meta.append((lat, lon, meta))
                logger.debug(f"✓ Processed {qmd_file.name}: {location}")

        except Exception as e:
            logger.error(f"Failed to process {qmd_file.name}: {e}")
            continue

    return locations_with_meta


# ============================================================================
# MAP GENERATION
# ============================================================================


def calculate_map_center(locations: List[Tuple[float, float, Dict]]) -> List[float]:
    """Calculate center point for map based on all locations.

    Args:
        locations: List of (lat, lon, metadata) tuples

    Returns:
        [latitude, longitude] for map center
    """
    if not locations:
        return [0, 0]

    avg_lat = sum(lat for lat, _, _ in locations) / len(locations)
    avg_lon = sum(lon for _, lon, _ in locations) / len(locations)
    return [avg_lat, avg_lon]


def create_popup_html(meta: Dict) -> str:
    """Create HTML popup content from talk metadata.

    Args:
        meta: Talk metadata dictionary

    Returns:
        HTML string for popup
    """
    title = f"<b>{meta.get('title', 'No title')}</b>"
    venue = f"Venue: {meta.get('venue')}" if meta.get("venue") else ""
    date = f"Date: {meta.get('date')}" if meta.get("date") else ""

    # Convert markdown description to HTML
    desc = ""
    if meta.get("description"):
        desc = markdown.markdown(
            meta.get("description", ""),
            output_format="html",
        ).strip()

    # Combine and clean up
    popup_html = f"{title}<br>{venue}<br>{date}<br><br>{desc}".strip()
    popup_html = "<br>".join(
        [line for line in popup_html.split("<br>") if line.strip()]
    )

    return popup_html


def generate_map(
    locations: List[Tuple[float, float, Dict]],
    output_path: Path,
) -> None:
    """Generate Folium map with talk locations.

    Args:
        locations: List of (lat, lon, metadata) tuples
        output_path: Path to save HTML map
    """
    if not locations:
        logger.warning("No locations to map")
        return

    # Calculate center
    center = calculate_map_center(locations)

    # Create map
    m = folium.Map(location=center, zoom_start=2)

    # Add markers
    for lat, lon, meta in locations:
        popup_html = create_popup_html(meta)
        folium.Marker(
            [lat, lon],
            popup=folium.Popup(popup_html, max_width=300),
        ).add_to(m)

    # Save map
    output_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output_path))
    logger.info(f"✓ Map saved to {output_path}")


# ============================================================================
# MAIN FUNCTION
# ============================================================================


def talkmap(
    talks_dir: str = DEFAULT_TALKS_DIR,
    cache_file: str = DEFAULT_CACHE_FILE,
    output_map: str = DEFAULT_OUTPUT_MAP,
    user_agent: str = DEFAULT_USER_AGENT,
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
) -> None:
    """Generate interactive map of talk locations.

    Args:
        talks_dir: Directory containing talk QMD files
        cache_file: Path to geocoding cache JSON file
        output_map: Path to output HTML map file
        user_agent: User agent for geocoding API
        sleep_seconds: Sleep time between API calls
    """
    logger.info("=" * 80)
    logger.info("Generating talk map")
    logger.info("=" * 80)

    # Initialize components
    project_root = Path.cwd()
    yaml_loader = YamlLoader()
    cache = GeoCache(Path(cache_file))
    geocoder = Nominatim(user_agent=user_agent)

    # Process talks
    talks_path = project_root / talks_dir
    if not talks_path.exists():
        logger.error(f"Talks directory not found: {talks_path}")
        return

    logger.info(f"Processing talks from {talks_dir}/")
    locations = extract_talks_metadata(
        talks_path,
        yaml_loader,
        geocoder,
        cache,
        sleep_seconds,
    )

    logger.info(f"Found {len(locations)} geolocated talks")

    # Save cache
    cache.save()

    # Generate map
    if locations:
        generate_map(locations, project_root / output_map)
        logger.info("=" * 80)
        logger.info("Talk map generation complete")
        logger.info("=" * 80)
    else:
        logger.warning("No locations found - map not generated")


def main() -> None:
    """CLI entry point."""
    talkmap()


if __name__ == "__main__":
    main()
