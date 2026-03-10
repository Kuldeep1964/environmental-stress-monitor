from flask import Flask, render_template, request, jsonify
import requests
import json
import os
import sqlite3
import random
from datetime import datetime
import threading
import time

scan_interval = 2400  # default 1 minute
event_triggered = False

app = Flask(__name__)

THRESHOLD_FILE = "thresholds.json"

# -----------------------------
# Load thresholds
# -----------------------------
def load_thresholds():
    if os.path.exists(THRESHOLD_FILE):
        with open(THRESHOLD_FILE, "r") as file:
            return json.load(file)
    return {"temperature": 30, "aqi": 400, "people": 10}


# -----------------------------
# Save thresholds
# -----------------------------
def save_thresholds(data):
    with open(THRESHOLD_FILE, "w") as file:
        json.dump(data, file, indent=4)

# -----------------------------
# Global Storage
# -----------------------------
sensor_data = {
    "temperature": 0,
    "humidity": 0,
    "air": 0,
    "people": 0,
    "stress": "LOW",
    "alerts": [],
    "suggestion": "",
    "time": ""
}
weather_cache = {
    "data": None,
    "last_updated": None
}

#people count based dynamic sampling interval
@app.route('/update-people', methods=['POST'])
def update_people():

    global sensor_data, event_triggered

   
    data = request.json or {}
    people_count = data.get("people", 0)
    sensor_data["people"] = people_count

    thresholds = load_thresholds()

    # Event trigger if threshold crossed
    if data["people"] > thresholds["people"]:
        event_triggered = True
        print(" People threshold crossed! Immediate stress recalculation.")

    return jsonify({"message": "People count updated"})
#weather caching mechanism to reduce API calls

def get_weather_data():
    global weather_cache

    if weather_cache["data"] and weather_cache["last_updated"]:
        if (datetime.now() - weather_cache["last_updated"]).total_seconds() < 3600:
            return weather_cache["data"]

    weather = fetch_weather()

    if weather:
        weather_cache["data"] = weather
        weather_cache["last_updated"] = datetime.now()

    return weather


OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
CITY = "Ahmedabad"

def fetch_weather():
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={OPENWEATHER_API_KEY}&units=metric"
        response = requests.get(url)
        data = response.json()

        return {
            "outdoor_temp": data["main"]["temp"],
            "outdoor_humidity": data["main"]["humidity"],
            "weather": data["weather"][0]["description"],
            "wind_speed": data["wind"]["speed"]
        }

    except:
        return None
# -----------------------------
# Stress Engine
# -----------------------------
def calculate_stress(data, weather=None):

    thresholds = load_thresholds()
    alerts = []
    score = 0
    suggestion = ""

    # Indoor checks
    if data["temperature"] > thresholds["temperature"]:
        alerts.append("High Temperature")
        score += 1

    if data["air"] > thresholds["aqi"]:
        alerts.append("Poor Air Quality")
        score += 1

    if data["people"] > thresholds["people"]:
        alerts.append("Overcrowding")
        score += 1

    # Silent weather influence
    if weather:
        outdoor_temp = weather.get("outdoor_temp")

        if outdoor_temp:
            temp_diff = data["temperature"] - outdoor_temp

            if temp_diff > 8:
                score += 1
                suggestion += "Indoor temperature much higher than outdoor. Improve ventilation. "

    # Stress Level
    if score == 0:
        stress = "LOW"
        suggestion = suggestion or "Environment stable and balanced."

    elif score == 1:
        stress = "MEDIUM"
        suggestion = suggestion or "Moderate environmental stress detected."

    else:
        stress = "HIGH"
        suggestion = suggestion or "Immediate corrective action required."

    return stress, alerts, suggestion
# -----------------------------
# Database
# -----------------------------
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            temperature REAL,
            humidity REAL,
            air REAL,
            people INTEGER,
            stress TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

# -----------------------------
# Routes
# -----------------------------

@app.route('/')
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/analytics')
def analytics():
    return render_template('analytics.html')

@app.route('/history-page')
def history_page():
    return render_template('history.html')

@app.route('/settings')
def settings():
    return render_template('settings.html')

@app.route('/get-thresholds')
def get_thresholds():
    return jsonify(load_thresholds())

@app.route('/update-thresholds', methods=['POST'])
def update_thresholds():
    save_thresholds(request.json)
    return jsonify({"message": "Thresholds updated successfully"})

@app.route('/update', methods=['POST'])
def update_sensor():
    global sensor_data
    data = request.json

    weather = get_weather_data()
    stress, alerts, suggestion = calculate_stress(data, weather)

    sensor_data.update({
        "temperature": data["temperature"],
        "humidity": data["humidity"],
        "air": data["air"],
        "people": data["people"],
        "stress": stress,
        "alerts": alerts,
        "suggestion": suggestion,
        "time": datetime.now().strftime("%H:%M:%S")
    })

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO logs (temperature, humidity, air, people, stress, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        sensor_data["temperature"],
        sensor_data["humidity"],
        sensor_data["air"],
        sensor_data["people"],
        sensor_data["stress"],
        sensor_data["time"]
    ))
    conn.commit()
    conn.close()

    return jsonify({"message": "Sensor data updated"})

    

@app.route('/data')
def get_data():
    return jsonify(sensor_data)

# -----------------------------
# JSON API - History Data
# -----------------------------
@app.route('/history')
def history():

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row   # Allows column access by name
    cursor = conn.cursor()

    cursor.execute("""
        SELECT temperature, humidity, air, people, stress, timestamp
        FROM logs
        ORDER BY id DESC
        LIMIT 20
    """)

    rows = cursor.fetchall()
    conn.close()

    history_data = []

    for row in rows:
        history_data.append({
            "temperature": row["temperature"],
            "humidity": row["humidity"],
            "air": row["air"],
            "people": row["people"],
            "stress": row["stress"],
            "time": row["timestamp"]
        })

    return jsonify(history_data)

@app.route('/api/weather')
def get_weather():
    weather = fetch_weather()
    return jsonify(weather)

#-----------------------------
# Simulation Route (Dummy Data)
# -----------------------------
@app.route('/simulate')
def simulate():

    global sensor_data

    # Generate realistic random data
    sample = {
        "temperature": round(random.uniform(24, 40), 1),
        "humidity": round(random.uniform(40, 75), 1),
        "air": round(random.uniform(250, 500), 1),
        "people": random.randint(1, 20)
    }

    weather = get_weather_data()    

    stress, alerts, suggestion = calculate_stress(sample, weather)

    sensor_data.update({
        "temperature": sample["temperature"],
        "humidity": sample["humidity"],
        "air": sample["air"],
        "people": sample["people"],
        "stress": stress,
        "alerts": alerts,
        "suggestion": suggestion,
        "time": datetime.now().strftime("%H:%M:%S")
    })

    # Insert into database
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO logs (temperature, humidity, air, people, stress, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        sensor_data["temperature"],
        sensor_data["humidity"],
        sensor_data["air"],
        sensor_data["people"],
        sensor_data["stress"],
        sensor_data["time"]
    ))
    conn.commit()
    conn.close()

    return jsonify({
        "message": "Simulation successful",
        "data": sensor_data
    })

def background_monitor():

    global event_triggered, sensor_data

    while True:

        if event_triggered:
            print("Immediate event-based scan")
            event_triggered = False
        else:
            print("Scheduled 40-minute scan")

        # Only refresh environmental sensors here
        sample = {
            "temperature": round(random.uniform(24, 40), 1),
            "humidity": round(random.uniform(40, 75), 1),
            "air": round(random.uniform(250, 500), 1),
            "people": sensor_data["people"]  # keep real-time people count
        }

        weather = get_weather_data()

        stress, alerts, suggestion = calculate_stress(sample, weather)

        sensor_data.update({
            "temperature": sample["temperature"],
            "humidity": sample["humidity"],
            "air": sample["air"],
            "stress": stress,
            "alerts": alerts,
            "suggestion": suggestion,
            "time": datetime.now().strftime("%H:%M:%S")
        })

        # Save to DB
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO logs (temperature, humidity, air, people, stress, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            sensor_data["temperature"],
            sensor_data["humidity"],
            sensor_data["air"],
            sensor_data["people"],
            sensor_data["stress"],
            sensor_data["time"]
        ))
        conn.commit()
        conn.close()

        for _ in range(scan_interval):
            if event_triggered:
                break
        time.sleep(40)  # Sleep for 400 seconds (6.67 minutes) before next check


if __name__ == '__main__':
    init_db()

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        monitor_thread = threading.Thread(target=background_monitor)
        monitor_thread.daemon = True
        monitor_thread.start()

    app.run(debug=True)