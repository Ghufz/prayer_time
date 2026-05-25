#!/usr/bin/env python
"""Fetch daily Salah times from the AlAdhan prayer times API."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime, time, timedelta, tzinfo
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - zoneinfo is available on supported Python versions.
    ZoneInfo = None  # type: ignore[assignment]


API_BASE_URL = "https://api.aladhan.com/v1/timingsByAddress"

PRAYERS = ("Fajr", "Dhuhr", "Asr", "Maghrib", "Isha")
SALAH_PRAYERS = PRAYERS

METHODS = {
    0: "Shia Ithna-Ashari",
    1: "University of Islamic Sciences, Karachi",
    2: "Islamic Society of North America",
    3: "Muslim World League",
    4: "Umm Al-Qura University, Makkah",
    5: "Egyptian General Authority of Survey",
    7: "Institute of Geophysics, University of Tehran",
    8: "Gulf Region",
    9: "Kuwait",
    10: "Qatar",
    11: "Majlis Ugama Islam Singapura",
    12: "Union Organization Islamic de France",
    13: "Diyanet Isleri Baskanligi, Turkey",
    14: "Spiritual Administration of Muslims of Russia",
    15: "Moonsighting Committee Worldwide",
    16: "Dubai",
    99: "Custom",
}


@dataclass(frozen=True)
class UpcomingSalah:
    name: str
    display_time: str
    occurs_at: datetime


def normalize_date(value: str | None) -> str:
    """Return a date in DD-MM-YYYY format accepted by AlAdhan."""
    if not value:
        return datetime.now().strftime("%d-%m-%Y")

    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%d-%m-%Y")
        except ValueError:
            pass

    raise ValueError("Date must be in DD-MM-YYYY or YYYY-MM-DD format.")


def fetch_timings(
    address: str,
    date: str,
    method: int | None,
    school: int | None,
) -> dict[str, Any]:
    query: dict[str, str | int] = {"address": address}

    if method is not None:
        query["method"] = method
    if school is not None:
        query["school"] = school

    url = f"{API_BASE_URL}/{date}?{urlencode(query)}"
    request = Request(url, headers={"User-Agent": "salah-times-python-cli/1.0"})

    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"API request failed with HTTP {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error while contacting AlAdhan: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("Network timeout while contacting AlAdhan.") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("AlAdhan returned a response that was not valid JSON.") from exc

    if payload.get("code") != 200 or payload.get("status") != "OK":
        message = payload.get("data") or payload.get("status") or "Unknown API error"
        raise RuntimeError(f"AlAdhan API error: {message}")

    return payload


def print_method_list() -> None:
    for method_id, name in METHODS.items():
        print(f"{method_id:>2}  {name}")


def resolve_timezone(timezone_name: str) -> tzinfo:
    if ZoneInfo is not None:
        try:
            return ZoneInfo(timezone_name)
        except Exception:
            pass

    local_timezone = datetime.now().astimezone().tzinfo
    if local_timezone is None:
        raise RuntimeError("Could not determine a timezone for upcoming salah calculation.")
    return local_timezone


def payload_gregorian_day(payload: dict[str, Any]) -> date_cls | None:
    date = payload.get("data", {}).get("date", {})
    gregorian = date.get("gregorian", {})
    candidates = (
        gregorian.get("date"),
        date.get("readable"),
    )

    for candidate in candidates:
        if not candidate:
            continue
        for fmt in ("%d-%m-%Y", "%d %b %Y", "%d %B %Y"):
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                pass

    return None


def parse_timing(value: str) -> time | None:
    match = re.search(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)", value)
    if not match:
        return None

    return time(hour=int(match.group(1)), minute=int(match.group(2)))


def find_upcoming_salah(payload: dict[str, Any], now: datetime) -> UpcomingSalah | None:
    data = payload["data"]
    timings = data["timings"]
    day = payload_gregorian_day(payload)
    if day is None:
        return None

    for prayer in SALAH_PRAYERS:
        display_time = str(timings.get(prayer, ""))
        parsed_time = parse_timing(display_time)
        if parsed_time is None:
            continue

        occurs_at = datetime.combine(day, parsed_time, tzinfo=now.tzinfo)
        if occurs_at >= now:
            return UpcomingSalah(prayer, display_time, occurs_at)

    return None


def format_time_until(target: datetime, now: datetime) -> str:
    seconds = int((target - now).total_seconds())
    if seconds <= 0:
        return "now"

    minutes = (seconds + 59) // 60
    hours, minutes = divmod(minutes, 60)
    if hours and minutes:
        return f"in {hours}h {minutes}m"
    if hours:
        return f"in {hours}h"
    return f"in {minutes}m"


def format_day_note(target: datetime, now: datetime) -> str:
    if target.date() == now.date():
        return ""
    if target.date() == now.date() + timedelta(days=1):
        return " tomorrow"
    return f" on {target:%Y-%m-%d}"


def print_table(
    payload: dict[str, Any],
    address: str,
    upcoming: UpcomingSalah | None,
    now: datetime,
) -> None:
    data = payload["data"]
    timings = data["timings"]
    date = data.get("date", {})
    meta = data.get("meta", {})

    gregorian = date.get("readable", "Unknown date")
    hijri = date.get("hijri", {}).get("date", "Unknown Hijri date")
    timezone = meta.get("timezone", "Unknown timezone")
    method = meta.get("method", {}).get("name", "Auto/unknown method")

    print()
    print(f"Salah times for {address}")
    print(f"Date: {gregorian} | Hijri: {hijri}")
    print(f"Timezone: {timezone}")
    print(f"Method: {method}")
    print()

    widest = max(len(name) for name in PRAYERS)
    time_width = max(len(str(timings.get(prayer, "-"))) for prayer in PRAYERS)
    print(f"{'Salah':<{widest}}  {'Time':<{time_width}}  Status")
    schedule_day = payload_gregorian_day(payload)
    for prayer in PRAYERS:
        display_time = str(timings.get(prayer, "-"))
        status = (
            "Upcoming"
            if upcoming
            and upcoming.name == prayer
            and schedule_day == upcoming.occurs_at.date()
            else ""
        )
        print(f"{prayer:<{widest}}  {display_time:<{time_width}}  {status}")

    print()
    if upcoming is None:
        print("Next salah: No upcoming salah found in this schedule.")
    else:
        note = format_day_note(upcoming.occurs_at, now)
        remaining = format_time_until(upcoming.occurs_at, now)
        print(f"Next salah: {upcoming.name} at {upcoming.display_time}{note} ({remaining})")

    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Get daily Salah times for a city or address.",
        epilog=(
            "Examples:\n"
            "  py salah_times.py \"New York, USA\"\n"
            "  py salah_times.py \"Hyderabad, India\" --method 1 --school 1\n"
            "  py salah_times.py \"London, UK\" --date 2026-05-25\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "address",
        nargs="*",
        help="City or full address, for example: Hyderabad, India",
    )
    parser.add_argument(
        "--date",
        help="Date as DD-MM-YYYY or YYYY-MM-DD. Defaults to today.",
    )
    parser.add_argument(
        "--method",
        type=int,
        choices=sorted(METHODS),
        help="Calculation method ID. Omit this to let the API choose by location.",
    )
    parser.add_argument(
        "--school",
        type=int,
        choices=(0, 1),
        help="Asr juristic school: 0 = Shafi/Maliki/Hanbali, 1 = Hanafi.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full API response as JSON.",
    )
    parser.add_argument(
        "--methods",
        action="store_true",
        help="List calculation methods and exit.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.methods:
        print_method_list()
        return 0

    address = " ".join(args.address).strip()
    if not address:
        parser.error("Please provide a city or address.")

    try:
        date = normalize_date(args.date)
        payload = fetch_timings(address, date, args.method, args.school)
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        timezone = payload.get("data", {}).get("meta", {}).get("timezone", "")
        now = datetime.now(resolve_timezone(timezone))
        upcoming = find_upcoming_salah(payload, now)

        if upcoming is None and payload_gregorian_day(payload) == now.date():
            tomorrow = (now + timedelta(days=1)).strftime("%d-%m-%Y")
            try:
                tomorrow_payload = fetch_timings(address, tomorrow, args.method, args.school)
                upcoming = find_upcoming_salah(tomorrow_payload, now)
            except RuntimeError:
                pass

        print_table(payload, address, upcoming, now)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
