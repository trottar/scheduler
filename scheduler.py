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
filename = "winter2025.json"

def load_aliases():
    """Loads alias mappings from config.json."""
    try:
        with open("config.json", "r") as file:
            config = json.load(file)
            return config.get("aliases", {})  # Default to empty if missing
    except FileNotFoundError:
        return {}  # Safe fallback if config.json is missing

# Load the schedule from the JSON file
def load_schedule(filename="winter2025.json"):
    """Loads the schedule and ensures it is sorted with 5:00 AM as the new day start."""
    with open(filename, "r") as file:
        schedule = json.load(file)

    aliases = load_aliases()  # Load dynamic alias mappings
    expanded_schedule = expand_schedule(schedule)

    # Ensure alias-mapped days retrieve the correct schedule dynamically
    final_schedule = {}
    for day, tasks in expanded_schedule.items():
        actual_day = day
        for alias, mapped_days in aliases.items():
            if day in mapped_days:
                actual_day = alias
                break
        final_schedule[day] = expanded_schedule.get(actual_day, tasks)

    return sort_schedule(final_schedule)  # Apply sorting

def sort_schedule(schedule):
    """Sorts each day's events chronologically, treating 5:00 AM as the new day start."""
    time_format = "%I:%M %p"

    for day in schedule:
        def event_key(event):
            start_time = event[0].split(" - ")[0].strip()
            dt = datetime.datetime.strptime(start_time, time_format)

            # ✅ If an event is before 5 AM, it is still part of the previous day for sorting
            if dt.hour < 5:
                dt += datetime.timedelta(days=1)  # Moves pre-5 AM events to correct order

            return dt

        # ✅ Sort strictly by start time
        schedule[day] = sorted(schedule[day], key=event_key)

    return schedule

def backup_schedule():
    """Creates a timestamped backup of winter2025.json and maintains a history."""
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)  # Ensure backup directory exists

    # Create a timestamped backup filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    backup_file = os.path.join(backup_dir, f"winter2025_backup_{timestamp}.json")
    original_file = "winter2025.json"

    try:
        shutil.copyfile(original_file, backup_file)
        print(f"✅ Backup created: {backup_file}")
    except Exception as e:
        print(f"⚠ Failed to create backup: {e}")

    # Maintain only the latest 5 backups
    existing_backups = sorted(
        [f for f in os.listdir(backup_dir) if f.startswith("winter2025_backup")],
        reverse=True
    )
    if len(existing_backups) > 5:
        for old_backup in existing_backups[5:]:
            os.remove(os.path.join(backup_dir, old_backup))
            
# Call this at the start of update_json_schedule()
backup_schedule()

def get_next_day_start_time(schedule, current_day):
    """Returns the first event start time of the next day, or None if no event exists."""    

    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    if current_day not in days_of_week:
        return None  # Safety check

    next_day_index = (days_of_week.index(current_day) + 1) % len(days_of_week)  # Cycle to next day
    next_day = days_of_week[next_day_index]

    if next_day in schedule and schedule[next_day]:
        first_event_start = schedule[next_day][0][0].split(" - ")[0]  # Extract start time
        print(f"⏭ Next day's first event: {first_event_start} on {next_day}")
        return first_event_start

    print(f"⏭ No events found for {next_day}, returning None.")
    return None  # No next-day event found

def update_json_schedule(day, old_start, new_start, new_end, new_activity):
    """Updates an event while ensuring overlaps are resolved and sorting is applied."""
    
    backup_schedule()  # Create a backup before making changes       

    # Load current schedule
    with open(filename, "r") as file:
        schedule = json.load(file)

    aliases = load_aliases()  # Load aliases dynamically

    # Resolve MW/TTh aliasing dynamically
    actual_day = day
    for alias, mapped_days in aliases.items():
        if day in mapped_days:
            actual_day = alias
            break  # Stop checking once an alias is found

    # Expand MW/TTh before modifying
    expanded_schedule = expand_schedule(schedule)

    # Ensure alias templates remain accessible dynamically
    for alias in aliases:
        if alias in schedule and alias not in expanded_schedule:
            expanded_schedule[alias] = schedule[alias]

    # Ensure day exists
    if actual_day not in expanded_schedule:
        print(f"⚠ Error: {actual_day} is not properly expanded in the schedule.")
        return

    events = expanded_schedule[actual_day]
    
    # ✅ Step 1: First, insert the new event with a temporary flag
    temp_marker = "##TEMP##"
    events.append([f"{new_start} - {new_end}", f"{new_activity} {temp_marker}"])
    print(f"✔ Inserted temporary event: {new_start} - {new_end} ({new_activity})")

    # ✅ Step 2: Run overlap detection, which will handle deletion
    check_for_overlap(actual_day, new_start, new_end, expanded_schedule)

    # ✅ Step 3: Remove the temporary marker to finalize insertion
    for i, entry in enumerate(events):
        if temp_marker in entry[1]:
            events[i][1] = entry[1].replace(temp_marker, "").strip()
            print(f"✅ Finalized event: {events[i][0]} {events[i][1]}")

    # **Step 2: Call `check_for_overlap()` BEFORE inserting the new event**
    check_for_overlap(actual_day, new_start, new_end, expanded_schedule)

    # **Step 3: Insert the modified event while ensuring conflicts are resolved**
    events.append([f"{new_start} - {new_end}", new_activity])

    # **Step 4: Call `check_for_overlap()` again AFTER inserting the new event**
    check_for_overlap(actual_day, new_start, new_end, expanded_schedule)

    # **Step 5: Ensure sorting is applied after modifications**
    expanded_schedule[actual_day] = sort_schedule({actual_day: events})[actual_day]

    # Restore MW/TTh placeholders after modification
    for alias, mapped_days in aliases.items():
        if all(day in expanded_schedule for day in mapped_days):
            schedule[alias] = expanded_schedule[mapped_days[0]]  # Assign first day's events to alias

    # Save the modified schedule back to JSON
    schedule[actual_day] = expanded_schedule[actual_day]
    with open(filename, "w") as file:
        json.dump(schedule, file, indent=4)

    print(f"✅ Updated event on {actual_day}, adjusted overlaps correctly, and ensured correct ordering.")

def add_event_to_json(day, new_start, new_end, new_activity):   
    """Adds a new event while ensuring correct MW/TTh aliasing, conflict resolution, and sorting."""
    
    backup_schedule()  # Create a backup before making changes

    # Load current schedule
    with open(filename, "r") as file:
        schedule = json.load(file)

    aliases = load_aliases()  # Load aliases dynamically

    actual_day = day
    for alias, mapped_days in aliases.items():
        if day in mapped_days:
            actual_day = alias
            break

    # Expand schedule before modifying
    expanded_schedule = expand_schedule(schedule)

    # Ensure alias templates remain accessible dynamically
    for alias in aliases:
        if alias in schedule and alias not in expanded_schedule:
            expanded_schedule[alias] = schedule[alias]

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

    # Restore MW/TTh placeholders after modification
    for alias, mapped_days in aliases.items():
        if all(day in expanded_schedule for day in mapped_days):
            schedule[alias] = expanded_schedule[mapped_days[0]]  # Assign first day's events to alias

    # Save back to JSON
    schedule[actual_day] = expanded_schedule[actual_day]
    with open(filename, "w") as file:
        json.dump(schedule, file, indent=4)

    print(f"✅ Added new event to {actual_day}: {new_start} - {new_end}, {new_activity}")

def delete_event(day, start):
    """Deletes an event and adjusts times correctly while preserving first/last event logic."""
    
    backup_schedule()  # Create a backup before making changes

    # Load current schedule
    with open(filename, "r") as file:
        schedule = json.load(file)

    aliases = load_aliases()
    actual_day = day
    for alias, mapped_days in aliases.items():
        if day in mapped_days:
            actual_day = alias
            break  # Stop once an alias is found

    if actual_day not in schedule:
        print(f"⚠ No schedule found for {day} ({actual_day}).")
        return

    events = schedule[actual_day]

    # Find and remove the event
    deleted_event = None
    for i, entry in enumerate(events):
        event_start = entry[0].split(" - ")[0].strip()

        if start.strip() == event_start:
            if "-" not in entry[0]:  # ✅ Ensures single-time events are never removed
                print(f"⚠ Skipping deletion of single-time event: {entry[1]}")
                continue

            deleted_event = events.pop(i)
            print(f"🗑 Deleted event: {deleted_event}")
            break

    else:
        print(f"⚠ No matching event found for {start} on {day} ({actual_day}). No changes made.")
        return

    # If there's a next event, adjust its start time safely
    if i < len(events) - 1:  # ✅ Ensure there's another event after this one
        next_event = events[i]
        next_start = next_event[0].split(" - ")[0].strip()

        if start != next_start:  # ✅ Ensure valid update
            events[i][0] = f"{start} - {next_event[0].split(' - ')[1]}"
    elif i == len(events) - 1:  # ✅ If this is the last event, do nothing
        print(f"⚠ No valid next event after deleting {start}. Skipping adjustment.")

    # If there's a previous event, extend its end time to match the deleted event’s start time
    if i > 0:
        prev_event = events[i - 1]
        prev_start = prev_event[0].split(" - ")[0].strip()

        if prev_start != start:  # Ensure valid update
            prev_end = start  # Extend previous event to fill the gap
            events[i - 1][0] = f"{prev_start} - {prev_end}"

    # Ensure "Bedtime" remains dynamically handled by GUI
    if events and events[-1][1].lower() == "bedtime":
        last_start = events[-1][0].split(" - ")[0].strip()
        events[-1] = [last_start, "Bedtime"]  # Preserve Bedtime format

    # Save the modified schedule back to JSON
    schedule[actual_day] = events
    with open(filename, "w") as file:
        json.dump(schedule, file, indent=4)

    print(f"✅ Deleted event on {actual_day} and adjusted times correctly.")

def check_for_overlap(day, start, end, schedule):
    """Removes fully overlapped events, pushes forward future events, and shortens past events."""

    print(f"\n🔎 Running Full Overlap Verification on {day}: Editing {start} - {end}\n")

    time_format = "%I:%M %p"
    start_dt = datetime.datetime.strptime(start, time_format)
    end_dt = datetime.datetime.strptime(end, time_format)

    # ✅ Handle cases where the event occurs after midnight but should belong to the same day
    if start_dt.hour < 5:
        start_dt += datetime.timedelta(days=1)  # Move it forward to stay in the correct logical day
    if end_dt.hour < 5:
        end_dt += datetime.timedelta(days=1)

    i = 0
    while i < len(schedule[day]):
        entry = schedule[day][i]
        event_time = entry[0].strip()

        if " - " not in event_time:
            i += 1
            continue

        entry_start, entry_end = event_time.split(" - ")
        entry_start_dt = datetime.datetime.strptime(entry_start.strip(), time_format)
        entry_end_dt = datetime.datetime.strptime(entry_end.strip(), time_format)

        # ✅ Handle cases where the event occurs after midnight but belongs to the same logical day
        if entry_start_dt.hour < 5:
            entry_start_dt += datetime.timedelta(days=1)  # Move it forward to align with the correct day
        if entry_end_dt.hour < 5:
            entry_end_dt += datetime.timedelta(days=1)

        print(f"🔍 Checking: {entry_start} - {entry_end} ({entry[1]})")

        # **CASE 1: The new event fully overlaps an existing one → DELETE**
        if start_dt <= entry_start_dt and end_dt >= entry_end_dt:            
            print(f"🗑 Removing '{entry[1]}' because it is fully within {start} - {end}.")
            del schedule[day][i]
            continue  # Skip incrementing i because we removed an entry

        # **CASE 2: The new event STARTS during an existing event → SHORTEN PAST EVENT**
        elif entry_start_dt < start_dt < entry_end_dt:
            print(f"🔄 Shortening '{entry[1]}' end time from {entry_end} to {start} to prevent overlap.")
            schedule[day][i][0] = f"{entry_start} - {start}"

        # **CASE 3: The new event ENDS during an existing event → PUSH FUTURE EVENT FORWARD**
        elif entry_start_dt < end_dt < entry_end_dt:
            print(f"🔄 Adjusting '{entry[1]}' start time from {entry_start} to {end} to prevent overlap.")
            schedule[day][i][0] = f"{end} - {entry_end}"

        # **CASE 4: Adjust Only the Next Event's Start Time**
        elif entry_start_dt >= end_dt:
            # ✅ Only adjust if the event is actually part of the same overnight sequence
            if entry_start_dt.hour < 5 and end_dt.hour > 18:
                new_start_str = end_dt.strftime(time_format)
                print(f"⏩ Adjusting overnight event '{entry[1]}' start time from {entry_start} to {new_start_str}.")
                schedule[day][i][0] = f"{new_start_str} - {entry_end}"
                modified = True
            else:
                print(f"⚠ Skipping adjustment for '{entry[1]}' (morning event) to avoid breaking schedule.")

            break  # Stop adjusting further events

        i += 1  # Move to next event

    print("\n✅ Final Schedule After Overlap Check:")
    for event in schedule[day]:
        print(f" - {event[0]} {event[1]}")

# Function to expand schedule templates (MW & TTh)
def expand_schedule(schedule):
    """Expands MW and TTh placeholders to actual schedules, handling missing templates safely."""
    expanded_schedule = {}

    aliases = load_aliases()  # Load aliases dynamically

    # Initialize template storage dynamically
    templates = {alias: schedule.get(alias, []) for alias in aliases}

    # Dynamically expand alias-based schedules instead of hardcoding MW/TTh
    for day, tasks in schedule.items():
        if day in aliases:  # Skip alias template days themselves
            continue

        # Dynamically replace mapped days with their alias data
        for alias, mapped_days in aliases.items():
            if tasks == alias:
                expanded_schedule[day] = list(schedule.get(alias, []))  # Ensure a deep copy
                break
        else:
            expanded_schedule[day] = tasks  # Keep normal days unchanged

    # Preserve alias templates after modification
    for alias, mapped_days in aliases.items():
        if all(day in expanded_schedule for day in mapped_days):
            schedule[alias] = expanded_schedule[mapped_days[0]]  # Assign first mapped day's events to alias

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
    aliases = load_aliases()  # Load alias mappings
    days = list(schedule.keys())  # Ordered list of days
    adjusted_schedule = {}

    for i, day in enumerate(days):
        actual_day = day
        for alias, mapped_days in aliases.items():
            if day in mapped_days:
                actual_day = alias
                break

        day_schedule = schedule.get(actual_day, [])
        next_day_index = (i + 1) % len(days)
        next_day = days[next_day_index]

        # Resolve alias for the next day
        for alias, mapped_days in aliases.items():
            if next_day in mapped_days:
                next_day = alias
                break

        adjusted_day_schedule = []
        for j, entry in enumerate(day_schedule):
            time_range, activity = entry[:2]  
            start_time, *end_time = map(str.strip, time_range.split('-'))

            # 🔍 Debug: Before modification
            print(f"🔍 Checking event: {start_time} - {end_time if end_time else 'No End Time'} ({activity}) on {day}")

            # ✅ If event already has an end time, do nothing
            if end_time:
                adjusted_day_schedule.append((start_time, end_time[0], activity))
                continue  

            # ✅ If the event is "Bedtime," dynamically assign an end time
            if activity.lower() == "bedtime":
                next_day_start = get_next_day_start_time(schedule, day)
                
                if next_day_start:
                    end_time = next_day_start  
                else:
                    end_time = "5:00 AM"  

                print(f"✅ Adjusted 'Bedtime' on {day}: {start_time} - {end_time}")
            
            else:
                # If no end time, default to 1 hour after start
                end_time = (datetime.datetime.strptime(start_time, "%I:%M %p") + datetime.timedelta(hours=1)).strftime("%I:%M %p")
                print(f"⏳ Defaulted missing end time: {start_time} - {end_time} for {activity}")

            adjusted_day_schedule.append((start_time, end_time, activity))

        adjusted_schedule[actual_day] = adjusted_day_schedule

    return adjusted_schedule

# Function to calculate free time per day
def calculate_hours(schedule):
    aliases = load_aliases()  # Load dynamic alias mappings

    total_allocated = 0

    for day, events in schedule.items():
        # Skip alias template days dynamically
        if day in aliases:
            continue
        
        total_allocated += sum([entry[3] for entry in events])

    free_time = TOTAL_HOURS - total_allocated
    return free_time

# Function to print today's schedule
def print_today_schedule(schedule):
    today = datetime.datetime.today().strftime("%A")
    aliases = load_aliases()  # Load alias mappings

    # Dynamically resolve alias for today
    actual_day = today
    for alias, mapped_days in aliases.items():
        if today in mapped_days:
            actual_day = alias
            break  # Stop checking once an alias is found

    today_schedule = schedule.get(actual_day, [])

    print(f"\n📅 **Hourly Schedule for {today} ({actual_day})** 📅")
    print("-" * 50)
    for start, end, activity, duration in today_schedule:
        end_str = f"- {end}" if end else ""
        print(f"{start} {end_str}: {activity} ({duration:.2f} hours)")
    print("-" * 50)

    free_time = calculate_hours({actual_day: today_schedule})
    print(f"✅ Total Allocated Time: {TOTAL_HOURS - free_time:.2f} / {TOTAL_HOURS} hours")
    print(f"🕒 Free Time Left: {free_time:.2f} hours\n")

# Function to summarize total weekly hours per activity
def get_weekly_summary(schedule):
    aliases = load_aliases()  # Load dynamic alias mappings
    category_totals = {}

    for day, day_schedule in schedule.items():
        # Skip alias template days dynamically
        if day in aliases:
            continue

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
