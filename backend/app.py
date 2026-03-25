from flask import Flask, jsonify
from flask_cors import CORS
import os
import json

app = Flask(__name__)
CORS(app)

DATA_FILE = "/data/courses_latest.json"

@app.route("/courses")
def get_courses():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify([])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
