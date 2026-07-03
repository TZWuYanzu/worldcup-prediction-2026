"""macOS Calendar CRUD operations via AppleScript."""

import subprocess
from typing import Optional


def _run_applescript(script: str) -> tuple[bool, str]:
    """Execute an AppleScript and return (success, stdout_or_stderr)."""
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True
    )
    if result.returncode != 0:
        return False, result.stderr.strip()
    return True, result.stdout.strip()


def _escape(text: str) -> str:
    """Escape text for embedding in AppleScript double-quoted strings."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


# ---------------------------------------------------------------------------
# Calendar-level operations
# ---------------------------------------------------------------------------

def create_calendar(name: str, rgb: tuple[int, int, int]) -> bool:
    """Create a named calendar with the given RGB color (0-65535 per channel)."""
    r, g, b = rgb
    script = f'''tell application "Calendar"
    set newCal to make new calendar with properties {{name:"{_escape(name)}", color:{{{r}, {g}, {b}}}}}
end tell'''
    ok, msg = _run_applescript(script)
    if not ok:
        print(f"  ERROR creating calendar '{name}': {msg}")
    return ok


def delete_calendar(name: str) -> bool:
    """Delete a calendar by name if it exists. Silently succeeds if not found."""
    script = f'''tell application "Calendar"
    try
        delete (every calendar whose name is "{_escape(name)}")
    end try
end tell'''
    ok, msg = _run_applescript(script)
    return ok


def ensure_calendars(names_and_colors: list[tuple[str, tuple[int, int, int]]]) -> bool:
    """Delete then recreate a set of calendars. Returns True if all succeeded."""
    for name, _ in names_and_colors:
        delete_calendar(name)
    all_ok = True
    for name, rgb in names_and_colors:
        if not create_calendar(name, rgb):
            all_ok = False
    return all_ok


# ---------------------------------------------------------------------------
# Event operations
# ---------------------------------------------------------------------------

def add_event(
    calendar_name: str,
    title: str,
    start: tuple[int, int, int, int, int],  # (year, month, day, hour, min)
    end: tuple[int, int, int, int, int],
    location: str = "",
    notes: str = "",
) -> Optional[str]:
    """Add a calendar event. Returns the event UID on success, None on failure."""
    sy, sm, sd, sh, smin = start
    ey, em, ed, eh, emin = end

    script = f'''tell application "Calendar"
    set targetCal to first calendar whose name is "{_escape(calendar_name)}"
    set startDate to current date
    set day of startDate to 1
    set year of startDate to {sy}
    set month of startDate to {sm}
    set day of startDate to {sd}
    set hours of startDate to {sh}
    set minutes of startDate to {smin}
    set seconds of startDate to 0

    set endDate to current date
    set day of endDate to 1
    set year of endDate to {ey}
    set month of endDate to {em}
    set day of endDate to {ed}
    set hours of endDate to {eh}
    set minutes of endDate to {emin}
    set seconds of endDate to 0

    tell targetCal
        set newEvent to make new event with properties {{summary:"{_escape(title)}", start date:startDate, end date:endDate, location:"{_escape(location)}", description:"{_escape(notes)}"}}
        return uid of newEvent
    end tell
end tell'''

    ok, result = _run_applescript(script)
    if not ok:
        print(f"    ERROR: {result}")
        return None
    return result


# ---------------------------------------------------------------------------
# Stub operations for future features
# ---------------------------------------------------------------------------

def update_event_notes(
    calendar_name: str, uid: str, new_notes: str
) -> bool:
    """Update the description/notes of an existing event by UID."""
    script = f'''tell application "Calendar"
    set targetCal to first calendar whose name is "{_escape(calendar_name)}"
    tell targetCal
        set matchingEvents to (every event whose uid is "{_escape(uid)}")
        if (count of matchingEvents) > 0 then
            set description of item 1 of matchingEvents to "{_escape(new_notes)}"
            return "ok"
        else
            return "not_found"
        end if
    end tell
end tell'''
    ok, result = _run_applescript(script)
    if not ok:
        print(f"    ERROR updating notes: {result}")
    return ok and result == "ok"


def update_event_summary(
    calendar_name: str, uid: str, new_summary: str
) -> bool:
    """Update the summary/title of an existing event by UID."""
    script = f'''tell application "Calendar"
    set targetCal to first calendar whose name is "{_escape(calendar_name)}"
    tell targetCal
        set matchingEvents to (every event whose uid is "{_escape(uid)}")
        if (count of matchingEvents) > 0 then
            set summary of item 1 of matchingEvents to "{_escape(new_summary)}"
            return "ok"
        else
            return "not_found"
        end if
    end tell
end tell'''
    ok, result = _run_applescript(script)
    if not ok:
        print(f"    ERROR updating summary: {result}")
    return ok and result == "ok"


def find_event_by_teams(
    calendar_name: str, team1_cn: str, team2_cn: str
) -> Optional[str]:
    """Find an event whose summary contains both team names. Returns UID or None.
    Works regardless of title format (\"vs\" or score like \"2-0\").
    """
    script = f'''tell application "Calendar"
    try
        set targetCal to first calendar whose name is "{_escape(calendar_name)}"
        set evts to every event of targetCal whose summary contains "{_escape(team1_cn)}"
        repeat with e in evts
            if summary of e contains "{_escape(team2_cn)}" then
                return uid of e
            end if
        end repeat
    end try
    return "not_found"
end tell'''
    ok, result = _run_applescript(script)
    if ok and result and result != "not_found":
        return result
    return None


def update_event_by_uid_or_title(
    calendar_name: str,
    uid: Optional[str],
    team1_cn: str,
    team2_cn: str,
    new_summary: str,
    new_notes: str,
) -> tuple[bool, Optional[str]]:
    """Try to update event by UID; if not found, fall back to team name search.
    Returns (success, resolved_uid).
    """
    if uid:
        ok1 = update_event_summary(calendar_name, uid, new_summary)
        if ok1:
            update_event_notes(calendar_name, uid, new_notes)
            return True, uid

    resolved = find_event_by_teams(calendar_name, team1_cn, team2_cn)
    if not resolved:
        return False, None

    ok1 = update_event_summary(calendar_name, resolved, new_summary)
    ok2 = update_event_notes(calendar_name, resolved, new_notes)
    return (ok1 or ok2), resolved
