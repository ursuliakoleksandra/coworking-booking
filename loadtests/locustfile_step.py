from locust import LoadTestShape
from locustfile import CoworkingUser, PeakUser  # noqa: F401  (класи користувачів для Locust)

STAGES = [  # (кінець етапу, с від старту; користувачів)
    (60, 25),
    (120, 50),
    (180, 100),
    (240, 150),
    (300, 200),
]


class StepLoad(LoadTestShape):
    spawn_rate = 10

    def tick(self):
        run_time = self.get_run_time()
        for end, users in STAGES:
            if run_time < end:
                return users, self.spawn_rate
        return None
