import logging


def test_connection(sim):
    status_message = sim.get_status()
    assert "Client Connected" in status_message, status_message
    logging.info(f"Status:\n{status_message}")
