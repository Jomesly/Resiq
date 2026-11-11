"""A warm OCR child, forcibly replaceable when native inference hangs."""

import multiprocessing as mp

from app.config import Settings
from app.vision.ocr import create_engine
from app.worker.pipeline import process


def child_main(connection, settings):
    try:
        engine = create_engine(settings)
        connection.send(("ready", None))
        while True:
            data = connection.recv()
            if data is None:
                break
            try:
                connection.send(("result", process(data, settings, engine)))
            except Exception as exc:
                connection.send(("error", type(exc).__name__))
    except Exception as exc:
        connection.send(("error", type(exc).__name__))
    finally:
        connection.close()


class OcrSupervisor:
    def __init__(self, settings: Settings, target=child_main):
        context = mp.get_context("spawn")
        self.connection, child = context.Pipe()
        self.process = context.Process(target=target, args=(child, settings), daemon=True)
        self.settings = settings
        self.process.start()
        child.close()

    def receive(self, timeout: float):
        if not self.connection.poll(timeout):
            self.close()
            raise TimeoutError("OCR exceeded its execution deadline.")
        kind, value = self.connection.recv()
        if kind == "error":
            raise RuntimeError(f"OCR child failed: {value}")
        return kind, value

    def ready(self):
        kind, _ = self.receive(300)
        if kind != "ready":
            raise RuntimeError("OCR child did not become ready.")

    def run(self, data: bytes):
        self.connection.send(data)
        kind, value = self.receive(self.settings.ocr_timeout_s)
        if kind != "result":
            raise RuntimeError("Unexpected OCR child response.")
        return value

    def close(self):
        if self.process.is_alive():
            self.process.terminate()
        self.process.join(timeout=5)
        if self.process.is_alive():
            self.process.kill()
            self.process.join(timeout=5)
        self.connection.close()
