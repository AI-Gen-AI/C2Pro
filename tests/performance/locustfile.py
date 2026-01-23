import os
import random
from locust import HttpUser, task, between, LoadTestShape

class ProjectManagerUser(HttpUser):
    """
    Simulates a Project Manager user journey.
    - Logs in and gets a JWT token.
    - Browses projects.
    - Views project details.
    - Occasionally creates a new project.
    """
    wait_time = between(1, 5)  # Simulates human-like pauses
    
    def on_start(self):
        """
        Called when a user starts. Performs login to get a JWT token.
        """
        # Credentials should be stored in environment variables for security
        email = os.getenv("C2PRO_TEST_USER", "test@example.com")
        password = os.getenv("C2PRO_TEST_PASSWORD", "password")

        with self.client.post("/api/auth/login", json={"email": email, "password": password}, name="/api/auth/login") as response:
            if response.status_code == 200:
                self.token = response.json().get("access_token")
                if self.token:
                    self.client.headers["Authorization"] = f"Bearer {self.token}"
                else:
                    response.failure("Could not extract access_token from login response")
            else:
                response.failure(f"Login failed with status {response.status_code}")
        
        self.project_ids = []

    @task(5)
    def list_projects(self):
        """
        Task to list all available projects for the tenant.
        High frequency task.
        """
        with self.client.get("/api/projects", name="/api/projects") as response:
            if response.status_code != 200:
                response.failure(f"Failed to get projects, status code: {response.status_code}")
            elif response.elapsed.total_seconds() > 2.0:
                response.failure(f"Request took too long: {response.elapsed.total_seconds():.2f}s")
            else:
                # Save project IDs for other tasks
                try:
                    data = response.json()
                    if data and isinstance(data, list) and len(data) > 0:
                        self.project_ids = [p["uuid"] for p in data if "uuid" in p]
                except Exception as e:
                    response.failure(f"Could not parse project list response: {e}")

    @task(2)
    def view_project_detail(self):
        """
        Task to view a specific project's details.
        Medium frequency task.
        """
        if not self.project_ids:
            return

        project_id = random.choice(self.project_ids)
        with self.client.get(f"/api/projects/{project_id}", name="/api/projects/[uuid]") as response:
            if response.status_code != 200:
                response.failure(f"Failed to get project detail, status code: {response.status_code}")
            elif response.elapsed.total_seconds() > 2.0:
                response.failure(f"Request took too long: {response.elapsed.total_seconds():.2f}s")

    @task(1)
    def create_project(self):
        """
        Task to create a new project.
        Low frequency task.
        """
        project_data = {
            "name": f"Locust Project {random.randint(1, 10000)}",
            "description": "This is a test project created by Locust."
        }
        with self.client.post("/api/projects", json=project_data, name="/api/projects (create)") as response:
            if response.status_code != 201:
                response.failure(f"Failed to create project, status code: {response.status_code}")
            elif response.elapsed.total_seconds() > 2.0:
                response.failure(f"Request took too long: {response.elapsed.total_seconds():.2f}s")


class C2ProLoadShape(LoadTestShape):
    """
    Custom load shape to simulate a ramp-up scenario.
    
    - Phase 1 (Warm up): 10 users for 1 minute.
    - Phase 2 (Load): Ramp up to 50 users over the next 3 minutes.
    - Phase 3 (Stress): Ramp up to 100 users over the final minute.
    """
    
    stages = [
        {"duration": 60, "users": 10, "spawn_rate": 10},       # Warm up
        {"duration": 240, "users": 50, "spawn_rate": 5},      # Load (3 minutes duration)
        {"duration": 300, "users": 100, "spawn_rate": 10},     # Stress (1 minute duration)
    ]

    def tick(self):
        """
        Returns the (user_count, spawn_rate) for the current time.
        """
        run_time = self.get_run_time()

        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])

        return None  # End of test
