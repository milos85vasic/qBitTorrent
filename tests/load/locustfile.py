from locust import HttpUser, task, between


class MergeSearchUser(HttpUser):
    host = "http://localhost:7187"
    wait_time = between(1, 3)

    @task(3)
    def search(self):
        self.client.get("/api/v1/search?q=ubuntu&trackers=nyaa")

    @task(1)
    def health(self):
        self.client.get("/health")

    @task(2)
    def dashboard(self):
        self.client.get("/")
