import pytest

from lychsim.api import LychSim


def pytest_addoption(parser):
    parser.addoption("--server_name", type=str, default="localhost")
    parser.addoption("--port", type=int, default=9000)


@pytest.fixture(scope="session")
def server_name(request):
    return request.config.getoption("--server_name")


@pytest.fixture(scope="session")
def port(request):
    return request.config.getoption("--port")


@pytest.fixture(scope="session")
def sim(server_name, port):
    simulation = LychSim(server_name=server_name, port=port, width=1920, height=1080)
    yield simulation
    simulation.close()
    print("Simulation connection closed.")
