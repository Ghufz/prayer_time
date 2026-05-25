# Salah Times Tool

This is a small Windows-friendly Python command-line tool for the five daily
Salah times. It uses the AlAdhan prayer times API and does not require any
extra pip packages. The normal table output marks the upcoming salah and also
shows how long remains until that time.

## Usage

From this folder:

```powershell
py salah_times.py "Hyderabad, India"
```

Open the HTML version in a browser:

```powershell
.\salah_times.html
```

The HTML page includes a city dropdown, an other-city text box, a formatted
table for the five salah times, and an upcoming salah status.

## Install On Mobile

The HTML page is also a small installable web app. You can host this folder
with GitHub Pages and open the HTTPS URL on your phone:

```text
https://YOUR-GITHUB-USERNAME.github.io/PrayerTime/
```

On Android Chrome, open the page and tap **Install App** if the button appears,
or use the browser menu and choose **Add to Home screen**.

On iPhone Safari, open the page, tap Share, then choose **Add to Home Screen**.

Opening `salah_times.html` directly as a `file:///` page is useful for testing
on this computer, but mobile install needs an HTTPS URL.

For the United States, ISNA is commonly used:

```powershell
py salah_times.py "New York, USA" --method 2
```

For Hanafi Asr:

```powershell
py salah_times.py "Hyderabad, India" --method 1 --school 1
```

For a specific date:

```powershell
py salah_times.py "London, UK" --date 2026-05-25
```

List available calculation methods:

```powershell
py salah_times.py --methods
```

Get the raw API response:

```powershell
py salah_times.py "Makkah, Saudi Arabia" --json
```

## Notes

Prayer times can differ from your local mosque because mosques may use custom
adjustments, local authority calendars, or manually tuned times.
