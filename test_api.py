#!/usr/bin/env python
"""
Test API functionality
"""
import requests
import json

BASE_URL = "http://localhost:5000"

def test_api():
    print("Testing RANSHI_KUN API...")
    
    # Test 1: List individuals
    print("\n1. Getting individuals list...")
    response = requests.get(f"{BASE_URL}/api/v1/individuals")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # Test 2: Create new individual
    print("\n2. Creating new individual...")
    data = {"uid": "test_user"}
    response = requests.post(f"{BASE_URL}/api/v1/individuals", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # Test 3: Register data for user
    print("\n3. Registering data...")
    register_data = {
        "datetime": "2026-03-10 20:50:00",
        "gym": 2,
        "absent": 0,
        "pain": 3,
        "headache": 1,
        "tone_pressure": 2,
        "cough": 1,
        "toilet_times": [
            {"time": "08:00", "duration_min": 5},
            {"time": "14:30", "duration_min": 3}
        ],
        "meds": [
            {"name": "アセトアミノフェン", "category": "日用でも生理でも使う薬", "time": "09:00"}
        ]
    }
    response = requests.post(f"{BASE_URL}/api/v1/register/test_user", json=register_data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # Test 4: Predict for user
    print("\n4. Making prediction...")
    predict_data = {
        "date": "2026-03-10",
        "gym": 2,
        "absent": 0,
        "pain": 3,
        "headache": 1,
        "tone": 2,
        "cough": 1,
        "toilet_times": [
            {"time": "08:00", "duration_min": 5},
            {"time": "14:30", "duration_min": 3}
        ],
        "meds": [
            {"name": "アセトアミノフェン", "category": "日用でも生理でも使う薬", "time": "09:00"}
        ]
    }
    response = requests.post(f"{BASE_URL}/api/v1/predict/test_user", json=predict_data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

if __name__ == "__main__":
    test_api()
