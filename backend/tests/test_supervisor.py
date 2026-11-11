import time

import pytest

from app.config import Settings
from app.worker.supervisor import OcrSupervisor


def hanging_child(connection, settings):
    connection.send(("ready", None))
    connection.recv()
    time.sleep(60)


def test_hung_native_child_is_terminated():
    supervisor = OcrSupervisor(
        Settings(environment="test", ocr_engine="fake"), target=hanging_child
    )
    try:
        supervisor.ready()
        supervisor.connection.send(b"photo")
        with pytest.raises(TimeoutError):
            supervisor.receive(0.1)
        assert not supervisor.process.is_alive()
    finally:
        supervisor.close()
