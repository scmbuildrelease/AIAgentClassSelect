from flask import Flask, jsonify
import os
import json

app = Flask(__name__)
DATA_FILE = os.path.join("..", "data", "courses_latest.json")

@app.route("/courses")
def get_courses():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    return jsonify([])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
