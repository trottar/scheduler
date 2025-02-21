#! /usr/bin/python

#
# Description:
# ================================================================
# Time-stamp: "2025-02-19 00:07:22 trottar"
# ================================================================
#
# Author:  Richard L. Trotta III <trotta@cua.edu>
#
# Copyright (c) trottar
#
from flask import Flask, render_template
import scheduler  # Import your schedule logic
import datetime

app = Flask(__name__)

# Function to get today's schedule
def get_today_schedule():
    today = datetime.datetime.today().strftime("%A")
    expanded_schedule = scheduler.expand_schedule(scheduler.load_schedule())
    return expanded_schedule.get(today, [])

@app.route("/")
def home():
    today_schedule = get_today_schedule()
    
    # Get current datetime for comparison
    now = datetime.datetime.now()
    
    processed_schedule = []
    
    for time_range, task, _ in today_schedule:
        start_time_str = time_range.split('-')[0].strip()  # Extract start time (e.g., "9:00 AM")

        # Convert event time to full datetime object using today's date
        try:
            event_time = datetime.datetime.strptime(start_time_str, "%I:%M %p")

            # Handle post-midnight (e.g., 12:30 AM - 2:00 AM should belong to "tonight")
            if event_time.hour < 5:  # If between 12:00 AM - 4:59 AM, treat it as next day
                event_time = event_time.replace(
                    year=now.year, month=now.month, day=now.day + 1
                )
            else:
                event_time = event_time.replace(
                    year=now.year, month=now.month, day=now.day
                )

        except ValueError:
            continue  # Skip if there's an error in time format

        # Determine if event is past or future
        status = "past" if event_time < now else "future"

        # Append to processed schedule
        processed_schedule.append((time_range, task, status))

    return render_template("schedule.html", today_schedule=processed_schedule)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
