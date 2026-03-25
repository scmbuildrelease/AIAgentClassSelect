from fastapi import FastAPI
from pydantic import BaseModel
import json

app = FastAPI()

class User(BaseModel):
    email: str
    preferences: list[str]

def load_courses():
    try:
        with open("/data/courses_latest.json") as f:
            return json.load(f)
    except:
        return []

@app.get("/courses")
def get_courses():
    return load_courses()

@app.post("/recommend")
def recommend(user: User):
    courses = load_courses()
    return [c for c in courses if c["category"] in user.preferences][:10]
