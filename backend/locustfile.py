"""Load test.

    locust -f locustfile.py --host http://localhost:8000 --headless -u 50 -r 10 -t 1m

Each simulated user signs up, then mixes map browsing, point forecasts and
route assessments in roughly the ratio seen in normal use.
"""

import random
import uuid
from datetime import datetime, timedelta, timezone

from locust import HttpUser, between, task

SPOTS = [(12.9352, 77.6245), (12.9172, 77.6229), (13.0294, 77.5859), (12.9716, 77.5946),
         (28.6286, 77.2410), (19.0596, 72.8295), (12.3080, 76.6520)]


class Commuter(HttpUser):
    wait_time = between(1, 4)

    def on_start(self):
        email = f"load-{uuid.uuid4().hex[:10]}@example.com"
        r = self.client.post("/api/auth/register", json={"email": email, "name": "Load", "password": "load-test-123"},
                             name="/api/auth/register")
        self.h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    @task(5)
    def stations(self):
        self.client.get(f"/api/air/stations?hour={random.randint(0, 24)}", name="/api/air/stations")

    @task(5)
    def here(self):
        lat, lon = random.choice(SPOTS)
        self.client.get(f"/api/me/here?lat={lat + random.uniform(-0.02, 0.02)}&lon={lon + random.uniform(-0.02, 0.02)}",
                        headers=self.h, name="/api/me/here")

    @task(2)
    def grid(self):
        lat, lon = random.choice(SPOTS)
        self.client.get(f"/api/air/grid?south={lat - .1}&west={lon - .15}&north={lat + .1}&east={lon + .15}&cells=32",
                        name="/api/air/grid")

    @task(1)
    def assess(self):
        (a, b), (c, d) = random.sample(SPOTS[:4], 2)
        dep = (datetime.now(timezone.utc) + timedelta(minutes=random.randint(10, 600))).isoformat()
        self.client.post("/api/trips/assess", headers=self.h, name="/api/trips/assess", json={
            "origin": {"name": "A", "lat": a, "lon": b}, "destination": {"name": "B", "lat": c, "lon": d},
            "depart_at": dep, "mode": random.choice(["two_wheeler", "driving", "bus", "cycling"])})
