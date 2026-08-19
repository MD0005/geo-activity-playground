import datetime
import json
import logging
import zoneinfo

import pandas as pd
import requests
import timezonefinder

from .paths import USER_CACHE_DIR

logger = logging.getLogger(__name__)


def sanitize_datetime(
    dt: datetime.datetime, fallback_from: str, fallback_to: str
) -> datetime.datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=zoneinfo.ZoneInfo(fallback_from))
    return dt.astimezone(zoneinfo.ZoneInfo(fallback_to))


def local_ymd_from_utc(
    event_time: datetime.datetime | pd.Timestamp | None,
    activity_start: datetime.datetime | pd.Timestamp | None,
    iana_timezone: str | None,
) -> tuple[int | None, int | None, int | None]:
    """Calendar date an event falls on in the recording activity's timezone.

    Times are stored in UTC, so a late evening ride would otherwise be filed
    under the following day east of Greenwich. The activity start stands in
    when the event itself carries no time.
    """
    if event_time is None or pd.isna(event_time):
        if activity_start is None or pd.isna(activity_start):
            return None, None, None
        timestamp = pd.Timestamp(activity_start)
    else:
        timestamp = pd.Timestamp(event_time)
    if timestamp.tz is None:
        timestamp = timestamp.tz_localize(zoneinfo.ZoneInfo("UTC"))

    timezone_name = "UTC" if iana_timezone is None else iana_timezone
    try:
        timezone = zoneinfo.ZoneInfo(timezone_name)
    except zoneinfo.ZoneInfoNotFoundError:
        timezone = zoneinfo.ZoneInfo("UTC")
    local = timestamp.tz_convert(timezone)
    return int(local.year), int(local.month), int(local.day)


def local_date_from_utc(
    event_time: datetime.datetime | pd.Timestamp | None,
    activity_start: datetime.datetime | pd.Timestamp | None,
    iana_timezone: str | None,
) -> datetime.date | None:
    year, month, day = local_ymd_from_utc(event_time, activity_start, iana_timezone)
    if year is None or month is None or day is None:
        return None
    return datetime.date(year, month, day)


def get_country_timezone(latitude: float, longitude: float) -> tuple[str, str]:
    cache_file = USER_CACHE_DIR / "geotimezone" / f"{latitude:.5f}-{longitude:.5f}.json"
    data = {}
    if cache_file.exists():
        try:
            with open(cache_file) as f:
                data = json.load(f)
        except json.decoder.JSONDecodeError as e:
            logger.warning(
                f"'{cache_file}' could not be parsed ('{e}'). Deleting and trying again."
            )
            cache_file.unlink()

    if not cache_file.exists():
        url = f"https://api.geotimezone.com/public/timezone?latitude={latitude}&longitude={longitude}"
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        cache_file.parent.mkdir(exist_ok=True, parents=True)
        with open(cache_file, "w") as f:
            json.dump(data, f)
    return data["location"], data["iana_timezone"]


def get_timezone(latitude: float, longitude: float) -> str | None:
    tf = timezonefinder.TimezoneFinder()  # reuse
    return tf.timezone_at(lng=longitude, lat=latitude)
