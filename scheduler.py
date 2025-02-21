#! /usr/bin/python

#
# Description:
# ================================================================
# Time-stamp: "2025-02-18 23:41:50 trottar"
# ================================================================
#
# Author:  Richard L. Trotta III <trotta@cua.edu>
#
# Copyright (c) trottar
#
import json
import datetime
import re
import shutil
import os

# Constants
TOTAL_HOURS = 24

# Load the schedule from the JSON file
def load_schedule(filename="winter2025.json"):
    """Loads the schedule and ensures it is sorted with 5:00 AM as the new day start."""
    with open(filename, "r") as file:
        schedule = json.load(file)
    
    expanded_schedule = expand_schedule(schedule)  # Keep MW/TTh logic intact
    return sort_schedule(expanded_schedule)  # Apply sorting without breaking aliasing

def sort_schedule(schedule):
    """Sorts each day's events chronologically, treating 5:00 AM as the new day start."""
    time_format = "%I:%M %p"
    
    for day in schedule:
        if not isinstance(schedule[day], list):  # Skip MW/TTh aliasing keys
            continue
        
        def event_key(event):
            start_time = event[0].split(" - ")[0].strip()
            dt = datetime.datetime.strptime(start_time, time_format)
            
            # Shift pre-5 AM events to the end of the day
            if dt.hour < 5:
                dt += datetime.timedelta(days=1)

            return dt
        
        schedule[day] = sorted(schedule[day], key=event_key)  # Maintain existing structure
    
    return schedule

def backup_schedule():
    """Creates a backup of winter2025.json before making changes and maintains multiple versions."""
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)  # Ensure backup directory exists

    # Limit backup history to the last 5 versions
    existing_backups = sorted(
        [f for f in os.listdir(backup_dir) if f.startswith("winter2025_backup")],
        reverse=True
    )
    
    if len(existing_backups) >= 5:
        os.remove(os.path.join(backup_dir, existing_backups[-1]))  # Remove oldest backup

    backup_file = os.path.join(backup_dir, f"winter2025_backup_{len(existing_backups)+1}.json")
    original_file = "winter2025.json"

    try:
        shutil.copyfile(original_file, backup_file)
        print(f"✅ Backup created: {backup_file}")
    except Exception as e:
        print(f"⚠ Failed to create backup: {e}")

# Call this at the start of update_json_schedule()
backup_schedule()

def update_json_schedule(day, old_start, new_start, new_end, new_activity):
    """Updates an event while ensuring overlaps are resolved and sorting is applied."""
    filename = "winter2025.json"

    # Load current schedule
    with open(filename, "r") as file:
        schedule = json.load(file)

    # Resolve MW/TTh aliasing
    if day in ["Monday", "Wednesday"]:
        actual_day = "MW"
    elif day in ["Tuesday", "Thursday"]:
        actual_day = "TTh"
    else:
        actual_day = day  # Keep the day unchanged if it's not aliased

    # Expand MW/TTh before modifying
    expanded_schedule = expand_schedule(schedule)

    # Ensure MW/TTh templates remain accessible
    if "MW" in schedule and "MW" not in expanded_schedule:
        expanded_schedule["MW"] = schedule["MW"]
    if "TTh" in schedule and "TTh" not in expanded_schedule:
        expanded_schedule["TTh"] = schedule["TTh"]

    # Ensure day exists
    if actual_day not in expanded_schedule:
        print(f"⚠ Error: {actual_day} is not properly expanded in the schedule.")
        return

    events = expanded_schedule[actual_day]

    # **Step 1: Remove the old event before inserting the new one**
    deleted_event = None
    for i, entry in enumerate(events):
        event_start = entry[0].split(" - ")[0].strip()

        if old_start.strip() == event_start:
            deleted_event = events.pop(i)  # Remove the event
            print(f"🗑 Deleted event: {deleted_event}")
            break
    else:
        print(f"⚠ No matching event found for {old_start} on {day} ({actual_day}). No changes made.")
        return

    # **Step 2: Call `check_for_overlap()` BEFORE inserting the new event**
    check_for_overlap(actual_day, new_start, new_end, expanded_schedule)

    # **Step 3: Insert the modified event while ensuring conflicts are resolved**
    events.append([f"{new_start} - {new_end}", new_activity])

    # **Step 4: Call `check_for_overlap()` again AFTER inserting the new event**
    check_for_overlap(actual_day, new_start, new_end, expanded_schedule)

    # **Step 5: Ensure sorting is applied after modifications**
    expanded_schedule[actual_day] = sort_schedule({actual_day: events})[actual_day]

    # Save the modified schedule back to JSON
    schedule[actual_day] = expanded_schedule[actual_day]
    with open(filename, "w") as file:
        json.dump(schedule, file, indent=4)

    print(f"✅ Updated event on {actual_day}, adjusted overlaps correctly, and ensured correct ordering.")

def add_event_to_json(day, new_start, new_end, new_activity):
    """Adds a new event while ensuring correct MW/TTh aliasing, conflict resolution, and sorting."""
    filename = "winter2025.json"

    # Backup before making changes
    backup_schedule()

    # Load current schedule
    with open(filename, "r") as file:
        schedule = json.load(file)

    # Resolve MW/TTh aliasing
    if day in ["Monday", "Wednesday"]:
        actual_day = "MW"
    elif day in ["Tuesday", "Thursday"]:
        actual_day = "TTh"
    else:
        actual_day = day

    # Expand schedule before modifying
    expanded_schedule = expand_schedule(schedule)

    # Ensure MW/TTh templates remain accessible
    if "MW" in schedule and "MW" not in expanded_schedule:
        expanded_schedule["MW"] = schedule["MW"]
    if "TTh" in schedule and "TTh" not in expanded_schedule:
        expanded_schedule["TTh"] = schedule["TTh"]

    # Ensure day exists
    if actual_day not in expanded_schedule:
        expanded_schedule[actual_day] = []

    # **Call check_for_overlap() to handle conflicts before adding**
    overlap_detected = check_for_overlap(actual_day, new_start, new_end, expanded_schedule)
    if overlap_detected:
        print(f"⚠ Overlap detected. Adjusting conflicting events in the schedule.")

    # Insert the new event
    expanded_schedule[actual_day].append([f"{new_start} - {new_end}", new_activity])

    # **Sort and finalize the schedule**
    expanded_schedule[actual_day] = sort_schedule({actual_day: expanded_schedule[actual_day]})[actual_day]

    # Save back to JSON
    schedule[actual_day] = expanded_schedule[actual_day]
    with open(filename, "w") as file:
        json.dump(schedule, file, indent=4)

    print(f"✅ Added new event to {actual_day}: {new_start} - {new_end}, {new_activity}")

def check_for_overlap(day, start, end, schedule):
    """Removes fully overlapped events, pushes forward future events, and shortens past events."""

    time_format = "%I:%M %p"
    start_dt = datetime.datetime.strptime(start, time_format)
    end_dt = datetime.datetime.strptime(end, time_format)

    modified = False  # Track if changes were made

    print(f"\n🔎 Running Full Overlap Verification on {day}: Editing {start} - {end}\n")

    i = 0  # Use index tracking to avoid issues when modifying list
    while i < len(schedule[day]):
        entry = schedule[day][i]
        event_time = entry[0].strip()

        # Skip single-time events
        if " - " not in event_time:
            i += 1
            continue

        entry_start, entry_end = event_time.split(" - ")
        entry_start_dt = datetime.datetime.strptime(entry_start.strip(), time_format)
        entry_end_dt = datetime.datetime.strptime(entry_end.strip(), time_format)

        # **CASE 1: The new event fully overlaps an existing one → DELETE**
        if start_dt <= entry_start_dt and end_dt >= entry_end_dt:
            print(f"🗑 Removing '{entry[1]}' as it is fully within {start} - {end}.")
            schedule[day].pop(i)  # Remove the fully overlapped event
            modified = True
            continue  # Don't increment i, as we removed an element

        # **CASE 2: The new event STARTS during an existing event → SHORTEN PAST EVENT**
        elif entry_start_dt < start_dt < entry_end_dt:
            print(f"🔄 Shortening '{entry[1]}' end time from {entry_end} to {start} to prevent overlap.")
            schedule[day][i][0] = f"{entry_start} - {start}"  # Adjust event to end before new start
            modified = True

        # **CASE 3: The new event ENDS during an existing event → PUSH FUTURE EVENT FORWARD**
        elif entry_start_dt < end_dt < entry_end_dt:
            print(f"🔄 Adjusting '{entry[1]}' start time from {entry_start} to {end} to prevent overlap.")
            schedule[day][i][0] = f"{end} - {entry_end}"  # Move event forward
            modified = True
            
        # **CASE 4: Adjust Only the Next Event's Start Time**
        elif entry_start_dt >= end_dt:
            new_start_str = end_dt.strftime(time_format)
            print(f"⏩ Adjusting '{entry[1]}' start time from {entry_start} to {new_start_str}.")
            schedule[day][i][0] = f"{new_start_str} - {entry_end}"  # Only adjust start, keep end unchanged
            modified = True
            break  # Stop adjusting further events          

        i += 1  # Move to next event

    return modified

# Function to expand schedule templates (MW & TTh)
def expand_schedule(schedule):
    """Expands MW and TTh placeholders to actual schedules, handling missing templates safely."""
    expanded_schedule = {}

    # Provide safe fallbacks in case MW/TTh do not exist in JSON
    mw_template = schedule.get("MW", [])
    tth_template = schedule.get("TTh", [])

    # Iterate over the schedule, replacing template placeholders
    for day, tasks in schedule.items():
        if day in ["MW", "TTh"]:
            continue  # Skip template days themselves

        if tasks == "MW":
            expanded_schedule[day] = list(mw_template)  # Ensure it's a new copy, not a reference
        elif tasks == "TTh":
            expanded_schedule[day] = list(tth_template)  # Avoid modifying the template itself
        else:
            expanded_schedule[day] = tasks  # Keep regular days unchanged

    return expanded_schedule

# Function to parse time string and calculate duration (handling overnight cases)
def calculate_duration(start, end):
    time_format = "%I:%M %p"
    start_time = datetime.datetime.strptime(start, time_format)
    end_time = datetime.datetime.strptime(end, time_format)

    # Handle overnight cases (e.g., "7:30 PM - 2:00 AM")
    if end_time <= start_time:
        end_time += datetime.timedelta(days=1)

    duration = (end_time - start_time).total_seconds() / 3600  # Convert seconds to hours
    return round(duration, 2)

# Function to adjust schedule by calculating missing end times and handling overnight durations
def adjust_schedule(schedule):
    days = list(schedule.keys())  # Ordered list of days
    adjusted_schedule = {}

    for i, day in enumerate(days):
        day_schedule = schedule[day]
        next_day = days[(i + 1) % len(days)]  # Get next day in cycle

        adjusted_day_schedule = []
        for j, entry in enumerate(day_schedule):
            time_range, activity = entry[:2]  # Extract time range and activity
            start_time, *end_time = map(str.strip, time_range.split('-'))

            if end_time:
                duration = calculate_duration(start_time, end_time[0])
            else:
                # If no end time, find the first start time of the next day
                if schedule[next_day]:
                    next_day_start = schedule[next_day][0][0].split('-')[0].strip()
                    duration = calculate_duration(start_time, next_day_start)
                else:
                    duration = TOTAL_HOURS  # Assume max duration if next day is empty

            adjusted_day_schedule.append((start_time, end_time[0] if end_time else None, activity, duration))

        adjusted_schedule[day] = adjusted_day_schedule

    return adjusted_schedule

# Function to calculate free time per day
def calculate_hours(schedule):
    total_allocated = sum([entry[3] for entry in schedule])
    free_time = TOTAL_HOURS - total_allocated
    return free_time

# Function to print today's schedule
def print_today_schedule(schedule):
    today = datetime.datetime.today().strftime("%A")
    today_schedule = schedule.get(today, [])

    print(f"\n📅 **Hourly Schedule for {today}** 📅")
    print("-" * 50)
    for start, end, activity, duration in today_schedule:
        end_str = f"- {end}" if end else ""
        print(f"{start} {end_str}: {activity} ({duration:.2f} hours)")
    print("-" * 50)

    free_time = calculate_hours(today_schedule)
    print(f"✅ Total Allocated Time: {TOTAL_HOURS - free_time:.2f} / {TOTAL_HOURS} hours")
    print(f"🕒 Free Time Left: {free_time:.2f} hours\n")

# Function to summarize total weekly hours per activity
def get_weekly_summary(schedule):
    category_totals = {}

    for day_schedule in schedule.values():
        for _, _, activity, duration in day_schedule:
            category_totals[activity] = category_totals.get(activity, 0) + duration

    return category_totals  # ✅ Return the summary instead of just printing

# Run the script
if __name__ == "__main__":
    schedule_data = load_schedule()
    expanded_schedule = expand_schedule(schedule_data)  # Expand MW and TTh templates
    adjusted_schedule = adjust_schedule(expanded_schedule)  # Adjust schedule to calculate durations
    print_today_schedule(adjusted_schedule)
    get_weekly_summary(adjusted_schedule)
