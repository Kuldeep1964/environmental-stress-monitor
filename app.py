from flask import Flask, render_template, request, jsonify
import requests
import json
import os
import sqlite3
import random
from datetime import datetime
import threading
import time
import pytz

scan_interval = 2400  # 40 minutes
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

# -----------------------------
# Weather Cache
# -----------------------------
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

    temp = float(data.get("temperature", 0))
    air = float(data.get("air", 0))
    people = int(data.get("people", 0))

    if temp > thresholds["temperature"]:
        alerts.append("High Temperature")
        score += 1

    if air > thresholds["aqi"]:
        alerts.append("Poor Air Quality")
        score += 1

    if people > thresholds["people"]:
        alerts.append("Overcrowding")
        score += 1

    if weather:
        outdoor_temp = weather.get("outdoor_temp")
        if outdoor_temp:
            temp_diff = temp - outdoor_temp
            if temp_diff > 8:
                score += 1
                suggestion += "Indoor temperature much higher than outdoor. Improve ventilation. "

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

# -----------------------------
# Page Routes
# -----------------------------
@app.route('/analytics')
def analytics():
    return render_template('analytics.html')

@app.route('/history-page')
def history_page():
    return render_template('history.html')

@app.route('/settings')
def settings():
    return render_template('settings.html')

@app.route('/update', methods=['POST'])
def update_sensor():
    global sensor_data
    data = request.json or {}

    weather = get_weather_data()
    stress, alerts, suggestion = calculate_stress(data, weather)

    ist = pytz.timezone("Asia/Kolkata")

    sensor_data.update({
        "temperature": float(data.get("temperature", 0)),
        "humidity": float(data.get("humidity", 0)),
        "air": float(data.get("air", 0)),
        "people": int(data.get("people", 0)),
        "stress": stress,
        "alerts": alerts,
        "suggestion": suggestion,
        "time": datetime.now(ist).strftime("%H:%M:%S")
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
# History API
# -----------------------------
@app.route('/history')
def history():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
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

# -----------------------------
# Main
# -----------------------------
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
