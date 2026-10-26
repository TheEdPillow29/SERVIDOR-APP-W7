import threading
import time
import cv2
from config import RTSP_URL


class CamaraRTSP:
    def __init__(self, url=RTSP_URL):
        self.url = url
        self._frame = None
        self._lock = threading.Lock()
        self._activa = True
        threading.Thread(target=self._bucle, daemon=True).start()

    def _bucle(self):
        while self._activa:
            captura = cv2.VideoCapture(self.url)
            captura.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if not captura.isOpened():
                print("No se pudo abrir la cámara. Reintentando...")
                time.sleep(2)
                continue

            print("Cámara conectada")
            while self._activa:
                ok, frame = captura.read()
                if not ok:
                    break
                with self._lock:
                    self._frame = frame

            captura.release()
            print("Se perdió el flujo de vídeo. Reconectando...")
            time.sleep(2)

    def leer(self):
        with self._lock:
            return None if self._frame is None else self._frame.copy()

    def cerrar(self):
        self._activa = False