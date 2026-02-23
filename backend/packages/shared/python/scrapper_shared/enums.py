from enum import Enum

BUCHAREST_COORDS = (44.4268, 26.1025)


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class RadiusOption(str, Enum):
    bucharest = "Bucuresti"
    km_50 = "50"
    km_100 = "100"
    km_200 = "200"
    all_ro = "All Romania"


RADIUS_KM = {
    RadiusOption.bucharest: 15,
    RadiusOption.km_50: 50,
    RadiusOption.km_100: 100,
    RadiusOption.km_200: 200,
}
