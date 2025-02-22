#! /usr/bin/python

#
# Description:
# ================================================================
# Time-stamp: "2025-02-18 23:42:27 trottar"
# ================================================================
#
# Author:  Richard L. Trotta III <trotta@cua.edu>
#
# Copyright (c) trottar
#
import json
import datetime
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import scheduler  # Importing the scheduler script to fetch the expanded schedule
import sys
import os
import atexit
import re
import shutil

LOCK_FILE = "schedule_gui.lock"
days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Function to check for an existing lock file (prevents multiple instances)
def check_running_instance():
    if os.path.exists(LOCK_FILE):
        print("Another instance is already running. Exiting.")
        sys.exit(0)
    else:
        with open(LOCK_FILE, "w") as lock:
            lock.write(str(os.getpid()))

# Ensure only one instance runs
check_running_instance()

# Function to remove the lock file on exit
def remove_lock_file():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

# Ensure the lock file is removed when the script exits
atexit.register(remove_lock_file)

# Load user preferences
def load_preferences():
    try:
        with open("config.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {"dark_mode": False}  # Default to Light Mode

# Save user preferences
def save_preferences(preferences):
    with open("config.json", "w") as file:
        json.dump(preferences, file)

# Toggle Dark Mode
def toggle_dark_mode(root):
    preferences = load_preferences()
    dark_mode = not preferences["dark_mode"]  # Flip the state

    # Apply styles based on mode
    apply_dark_mode(root, dark_mode)

    # Save user preference
    preferences["dark_mode"] = dark_mode
    save_preferences(preferences)

    # Update button text
    if "dark_mode_button" in globals():
        dark_mode_button.config(text="☀ Light Mode" if dark_mode else "🌙 Dark Mode")

def apply_dark_mode(root, dark_mode):
    """Applies dark or light mode dynamically."""
    # Ensure style is initialized
    style = ttk.Style()
    if dark_mode:
        root.tk_setPalette(background="#1e1e1e", foreground="white")
        style.configure("TFrame", background="#1e1e1e")
        style.configure("TLabel", background="#1e1e1e", foreground="white")
        style.configure("TButton", background="#333", foreground="white")
        style.configure("Past.TButton", foreground="gray")
        style.configure("Ongoing.TButton", foreground="red")
        style.configure("Future.TButton", foreground="white")
    else:
        root.tk_setPalette(background="white", foreground="black")
        style.configure("TFrame", background="white")
        style.configure("TLabel", background="white", foreground="black")
        style.configure("TButton", background="white", foreground="black")
        style.configure("Past.TButton", foreground="gray")
        style.configure("Ongoing.TButton", foreground="red")
        style.configure("Future.TButton", foreground="black")

    # Refresh UI
    update_schedule()

# Function to allow dragging the window smoothly from anywhere
def start_move(event):
    header_frame.x_offset = event.x
    header_frame.y_offset = event.y

def move_window(event):
    x = header_frame.winfo_x() + (event.x - header_frame.x_offset)
    y = header_frame.winfo_y() + (event.y - header_frame.y_offset)
    header_frame.geometry(f"+{x}+{y}")

# Function to determine if an event is past, ongoing, or future
def get_event_status(start_time, end_time, selected_day):
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    start_dt = datetime.datetime.strptime(f"{today_str} {start_time}", "%Y-%m-%d %I:%M %p")
    if not end_time or end_time.strip() == "":
        # If no explicit end time (e.g., "Bedtime"), assume it's a future event unless it's already passed
        end_dt = None
        if selected_day == datetime.datetime.today().strftime("%A"):  # If it's today
            return "future"         
    else:
        end_dt = datetime.datetime.strptime(f"{today_str} {end_time}", "%Y-%m-%d %I:%M %p")

    if end_time and end_dt <= start_dt:
        end_dt = datetime.datetime.strptime(f"{tomorrow_str} {end_time}", "%Y-%m-%d %I:%M %p")

    if now > (end_dt if end_dt else start_dt):
        return "past"
    elif start_dt <= now <= (end_dt if end_dt else start_dt):
        return "ongoing"
    return "future"

def validate_time_format(time_str):
    time_pattern = r"^(0?[1-9]|1[0-2]):[0-5][0-9] (AM|PM)$"
    return bool(re.match(time_pattern, time_str))

def calculate_duration(start, end=None):
    time_format = "%I:%M %p"

    #print(f"🔍 Debug: Received start='{start}', end='{end}'")  # Debugging output

    # If end time is missing or invalid, return 0.0 instead of breaking
    if not end or end.strip() == "" or end == "DYNAMIC" or len(end) < 4:
        return 0.0  # Just return without printing warnings

    try:
        start_time = datetime.datetime.strptime(start, time_format)
        end_time = datetime.datetime.strptime(end, time_format)
    except ValueError as e:
        print(f"❌ ERROR: Invalid time format! Start='{start}', End='{end}'")
        return 0.0  # Instead of raising an exception, default to 0.0 duration

    if end_time <= start_time:
        end_time += datetime.timedelta(days=1)  # Handle times crossing midnight

    duration = (end_time - start_time).total_seconds() / 3600  # Convert to hours
    return round(duration, 2)

# Function to find the first start time of the next day
def get_next_day_start_time(schedule, current_day):
    """Returns the first event start time of the next day, or None if no event exists."""    

    if current_day not in days_of_week:
        return None  # Safety check

    next_day_index = (days_of_week.index(current_day) + 1) % len(days_of_week)  # Cycle to next day
    next_day = days_of_week[next_day_index]

    if next_day in schedule and schedule[next_day]:
        first_event_start = schedule[next_day][0][0].split(" - ")[0]  # Extract start time
        #print(f"⏭ Next day's first event: {first_event_start} on {next_day}")
        return first_event_start

    print(f"⏭ No events found for {next_day}, returning None.")
    return None  # No next-day event found

def undo_last_change():
    """Restores the most recent backup available, allowing multiple undos."""
    backup_dir = "backups"
    existing_backups = sorted(
        [f for f in os.listdir(backup_dir) if f.startswith("winter2025_backup")],
        reverse=True
    )

    if not existing_backups:
        print("⚠ No backups found! Undo is not possible.")
        return

    latest_backup = os.path.join(backup_dir, existing_backups[0])
    original_file = "winter2025.json"

    # Extract the timestamp from the filename
    try:
        timestamp_str = existing_backups[0].split('_')[-1].split('.')[0]
        backup_datetime = datetime.datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
        formatted_datetime = backup_datetime.strftime("%A, %B %d, %Y at %I:%M:%S %p")
    except ValueError:
        formatted_datetime = "an unknown date"

    confirm = messagebox.askyesno(
        "Undo Changes",
        f"Are you sure you want to revert to the backup from {formatted_datetime}?"
    )
    if confirm:
        try:
            shutil.copyfile(latest_backup, original_file)
            os.remove(latest_backup)  # Remove used backup
            print(f"✅ Undo successful! Reverted to {latest_backup}")

            # Refresh the GUI to reflect the restored schedule
            update_schedule()

        except Exception as e:
            print(f"⚠ Undo failed: {e}")
            
def open_add_event_dialog(selected_day):
    """Opens a dialog to add a new event."""

    add_window = tk.Toplevel(header_frame)
    add_window.title("Add Event")
    add_window.geometry("300x200")

    ttk.Label(add_window, text="Start Time (HH:MM AM/PM):").pack()
    start_time_entry = ttk.Entry(add_window)
    start_time_entry.pack()

    ttk.Label(add_window, text="End Time (HH:MM AM/PM):").pack()
    end_time_entry = ttk.Entry(add_window)
    end_time_entry.pack()

    ttk.Label(add_window, text="Activity:").pack()
    activity_entry = ttk.Entry(add_window)
    activity_entry.pack()
    
    def save_new_event():
        new_start = start_time_entry.get().strip()
        new_end = end_time_entry.get().strip()
        new_activity = activity_entry.get().strip()

        if not validate_time_format(new_start) or not validate_time_format(new_end) or not new_activity:
            messagebox.showerror("Invalid Input", "Please enter a valid start time, end time, and activity.")
            return

        if new_start >= new_end:
            messagebox.showerror("Time Error", "End time must be later than start time.")
            return

        # Backup before making changes
        scheduler.backup_schedule()

        # Add event to JSON and update GUI
        scheduler.add_event_to_json(selected_day, new_start, new_end, new_activity)
        add_window.destroy()
        update_schedule(selected_day)
    

    ttk.Button(add_window, text="Save", command=save_new_event).pack(pady=5)
    ttk.Button(add_window, text="Cancel", command=add_window.destroy).pack(pady=5)

def create_dropdown_header(current_day):
    today = datetime.datetime.today().strftime("%A")  # Ensure today is defined   

    # Use a tk.StringVar to store the selected day
    selected_day_var = tk.StringVar(value=current_day)

    # Create a frame to hold the dropdown
    header_frame = ttk.Frame(frame_inner)
    header_frame.pack(pady=10)

    # Create the dropdown with all days of the week
    day_dropdown = ttk.Combobox(header_frame, textvariable=selected_day_var, values=days_of_week, state="readonly")
    day_dropdown.pack(side="left", padx=5)

    # Function to update schedule when dropdown changes
    def on_day_selected(event):
        update_schedule(selected_day_var.get())

    day_dropdown.bind("<<ComboboxSelected>>", on_day_selected)

    initial_button_pos = 10
    # Reset button to go back to today’s schedule
    reset_button = ttk.Button(header_frame, text="Reset to Today", command=lambda: update_schedule(today))
    reset_button.pack(side="right", padx=initial_button_pos)

    # Style dropdown to highlight today
    if current_day == today:
        day_dropdown.configure(foreground="black")  # Bold and black for today
    else:
        day_dropdown.configure(foreground="gray")   # Greyed out for non-today days

    # Ensure Undo button is created only once
    if not hasattr(header_frame, "undo_button"):
        # Add "+ Add Event" button
        add_event_button = ttk.Button(header_frame, text="+ Add Event", command=lambda: open_add_event_dialog(selected_day_var.get()))
        add_event_button.pack(side="right", padx=initial_button_pos+5)   
        
        undo_button = ttk.Button(header_frame, text="Undo Last Change", command=undo_last_change)
        undo_button.pack(side="right", padx=initial_button_pos+10)
        
        # Dark Mode Toggle Button
        global dark_mode_button
        dark_mode_button = ttk.Button(header_frame, text="🌙 Dark Mode", command=lambda: toggle_dark_mode(header_frame))
        dark_mode_button.pack(side="right", padx=initial_button_pos+15)     

def open_edit_dialog(day, start_time, end_time, activity):
    
    aliases = scheduler.load_aliases()  # Load alias mappings

    # Resolve alias dynamically
    actual_day = day
    for alias, mapped_days in aliases.items():
        if day in mapped_days:
            actual_day = alias
            break  # Stop checking once an alias is found
            
    edit_window = tk.Toplevel(header_frame)
    edit_window.title("Edit Event")
    edit_window.geometry("300x200")

    ttk.Label(edit_window, text="Start Time:").pack()
    start_time_entry = ttk.Entry(edit_window)
    start_time_entry.insert(0, start_time)
    start_time_entry.pack()

    ttk.Label(edit_window, text="End Time:").pack()
    end_time_entry = ttk.Entry(edit_window)
    end_time_entry.insert(0, end_time)
    end_time_entry.pack()

    ttk.Label(edit_window, text="Activity:").pack()
    activity_entry = ttk.Entry(edit_window)
    activity_entry.insert(0, activity)
    activity_entry.pack()

    def save_changes():
        new_start = start_time_entry.get().strip()
        new_end = end_time_entry.get().strip()
        new_activity = activity_entry.get().strip()

        if validate_time_format(new_start) and validate_time_format(new_end) and new_activity:            
            scheduler.update_json_schedule(day, start_time, new_start, new_end, new_activity)  # Ensure JSON updates
            edit_window.destroy()
            header_frame.after(100, lambda: update_schedule(day))  # Delay refresh slightly         
        else:
            ttk.Label(edit_window, text="Invalid input!", foreground="red").pack()
            
    def delete_this_event(start_time):
        """Deletes the event after confirmation."""
        confirm = messagebox.askyesno("Delete Event", "Are you sure you want to delete this event?")
        if confirm:
            scheduler.delete_event(day, start_time)  # Use start_time instead of old_start
            edit_window.destroy()
            update_schedule(day)  # Refresh GUI

    # Create a frame for buttons to align them horizontally
    button_frame = ttk.Frame(edit_window)
    button_frame.pack(pady=5, fill="x")

    # Save Button
    save_button = ttk.Button(button_frame, text="Save", command=save_changes)
    save_button.pack(side="left", padx=5, expand=True)

    # Delete Button (❌)    
    delete_button = ttk.Button(button_frame, text="❌ Delete", command=lambda: delete_this_event(start_time)) 
    delete_button.pack(side="right", padx=5, expand=True)

    # Cancel Button (placed below the row)
    ttk.Button(edit_window, text="Cancel", command=edit_window.destroy).pack(pady=5)

def update_schedule(selected_day=None):
    """Refreshes the schedule display with improved formatting."""
    
    # Define button styles for different event statuses
    style = ttk.Style()
    style.configure("Past.TButton", foreground="gray")  # Past events gray
    style.configure("Ongoing.TButton", foreground="red", font=("Arial", 10, "bold"))  # Bold text for ongoing
    style.configure("Future.TButton", foreground="black")

    # Separate background styles to make ongoing events stand out
    style.configure("OngoingFrame.TFrame", background="#ffe6e6")  # Light red background for ongoing
    style.configure("DefaultFrame.TFrame", background="#f0f0f0")  # Alternating background
    
    today = datetime.datetime.today().strftime("%A")

    if selected_day is None:
        selected_day = today

    full_schedule = scheduler.load_schedule()
    today_schedule = full_schedule.get(selected_day, [])

    # Clear previous entries
    for widget in frame_inner.winfo_children():
        widget.destroy()

    # Create the dropdown header
    create_dropdown_header(selected_day)    

    for i, entry in enumerate(today_schedule):
        if len(entry) < 2:
            continue

        time_range, activity = entry[:2]
        start_time, *end_time = map(str.strip, time_range.split('-'))
        end_time = end_time[0] if end_time and end_time[0].strip() else ""

        duration = calculate_duration(start_time, end_time)
        status = get_event_status(start_time, end_time, selected_day)

        # Improve text spacing & styling
        time_text = f"{start_time} - {end_time}"
        event_text = f"{time_text:<18} {activity} ({duration:.2f} hrs)"        

        # Create a frame to better align elements
        frame = ttk.Frame(frame_inner, padding=(10, 5))
        frame.pack(fill="x", padx=15, pady=2)

        # Clickable edit button with improved text formatting
        edit_button = ttk.Button(
            frame,
            text=event_text,
            command=lambda s=selected_day, st=start_time, et=end_time, a=activity: open_edit_dialog(s, st, et, a),
            style="TButton"
        )
        edit_button.pack(side="left", fill="x", expand=True)
                
        # Get today's name
        today = datetime.datetime.today().strftime("%A")

        # If the selected day is NOT today, everything is gray
        # Define background colors for better contrast
        bg_color = "#f0f0f0" if i % 2 == 0 else "#ffffff"  # Alternating row colors

        if selected_day != today:
            edit_button.configure(style="Past.TButton")  # Everything gray
            frame_style = f"CustomFrame{bg_color.replace('#', '')}.TFrame"
            style = ttk.Style()
            style.configure(frame_style, background=bg_color)
            frame.configure(style=frame_style)            
        else:
            if status == "past":
                edit_button.configure(style="Past.TButton")  # Past = Gray
            elif status == "ongoing":
                edit_button.configure(style="Ongoing.TButton")  # Ongoing = Red                
                frame.configure(style="OngoingFrame.TFrame")  # Apply light red background
            else:
                edit_button.configure(style="Future.TButton")  # Future = Black
                frame.configure(style="DefaultFrame.TFrame")  # Apply normal background

    # Add weekly summary
    display_weekly_summary()
    header_frame.after(60000, lambda: update_schedule(selected_day))  # Auto-refresh

# Function to display weekly summary with fixed end time handling
def display_weekly_summary():
    expanded_schedule = load_schedule()
    weekly_summary = {}

    for day, day_schedule in expanded_schedule.items():
        for entry in day_schedule:
            if len(entry) < 2:
                continue

            time_range, activity = entry[:2]
            start_time, *end_time = map(str.strip, time_range.split('-'))
            end_time = end_time[0] if end_time else get_next_day_start_time(expanded_schedule, day)
            duration = calculate_duration(start_time, end_time)

            weekly_summary[activity] = weekly_summary.get(activity, 0) + duration

    ttk.Label(frame_inner, text="\n📊 Weekly Summary 📊", font=("Arial", 14, "bold")).pack(pady=10)

    for activity, total_hours in sorted(weekly_summary.items(), key=lambda x: -x[1]):
        frame = ttk.Frame(frame_inner)
        frame.pack(fill="x", padx=10)

        ttk.Label(frame, text=f"{activity}: ", font=("Arial", 12, "bold")).pack(side="left", padx=20)
        ttk.Label(frame, text=f"{total_hours:.2f} hours/week", font=("Arial", 12)).pack(side="right", padx=20)

# Function to scroll using the mouse wheel
def on_mouse_scroll(event):
    canvas.yview_scroll(-1 * (event.delta // 120), "units")

# Load schedule from scheduler.py
def load_schedule():
    schedule_data = scheduler.load_schedule()
    expanded_schedule = scheduler.expand_schedule(schedule_data)
    return expanded_schedule

# Function to get today's schedule
def get_today_schedule():
    today = datetime.datetime.today().strftime("%A")
    schedule = load_schedule().get(today, [])
    return today, schedule

# Initialize Tkinter GUI
header_frame = tk.Tk()
header_frame.title("Daily Schedule Viewer")
header_frame.geometry("800x600")

header_frame.bind("<ButtonPress-1>", start_move)
header_frame.bind("<B1-Motion>", move_window)

canvas = tk.Canvas(header_frame)
canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

scrollbar = ttk.Scrollbar(header_frame, orient="vertical", command=canvas.yview)
scrollbar.pack(side=tk.RIGHT, fill="y")

frame_inner = ttk.Frame(canvas)
canvas.create_window((0, 0), window=frame_inner, anchor="nw")

frame_inner.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
canvas.configure(yscrollcommand=scrollbar.set)

canvas.bind("<MouseWheel>", on_mouse_scroll)
canvas.bind("<Button-4>", lambda event: canvas.yview_scroll(-1, "units"))
canvas.bind("<Button-5>", lambda event: canvas.yview_scroll(1, "units"))

update_schedule()

# Load user preferences and apply Dark Mode if needed
preferences = load_preferences()
apply_dark_mode(header_frame, preferences["dark_mode"])

# Set the correct text for the button on startup
if "dark_mode_button" in globals():
    dark_mode_button.config(text="☀ Light Mode" if preferences["dark_mode"] else "🌙 Dark Mode")

header_frame.mainloop()
