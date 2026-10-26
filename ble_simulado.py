import sys
import threading


class BLESimulado:
    """Imita BLEEsp32 desde la terminal.
    Escribe 'PIN 1234' para simular el teclado y 'LISTO' para cerrar el ciclo."""

    def __init__(self, on_mensaje):
        self.on_mensaje = on_mensaje

    def iniciar(self):
        print("Modo simulado: sin ESP32.")
        print("Escribe 'PIN 1234' o 'LISTO' y pulsa Enter.")
        threading.Thread(target=self._leer_teclado, daemon=True).start()

    def _leer_teclado(self):
        for linea in sys.stdin:
            texto = linea.strip()
            if texto.upper().startswith("PIN "):
                self.on_mensaje("PIN:" + texto[4:].strip())
            elif texto.upper() == "LISTO":
                self.on_mensaje("LISTO")

    def enviar(self, texto):
        print(f"[ESP32 simulado] recibió: {texto}")
        return True