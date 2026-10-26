import os
import re
import threading
import time

import cv2

from config import (
    MODEL_PATH, UMBRAL_RECONOCIMIENTO, TAM_ROSTRO,
    MAX_INTENTOS_PIN, BLOQUEO_PIN_SEG, TIMEOUT_PIN_SEG,
)
import db
from camara import CamaraRTSP
from ble_esp32 import BLEEsp32
from ble_simulado import BLESimulado
from captura_entrenamiento import capturar_perfil, entrenar, detector, redimensionar

PIN_VALIDO = re.compile(r"^[0-9]{4,8}$")


class Servidor:
    def __init__(self):
        self.camara = CamaraRTSP()
        self.dispositivo_id = db.dispositivo_id()

        if os.environ.get("MODO_SIMULADO") == "1":
            self.ble = BLESimulado(on_mensaje=self.on_mensaje_ble)
        else:
            self.ble = BLEEsp32(on_mensaje=self.on_mensaje_ble)
        
        self.lock = threading.Lock()
        self.reconocedor = None
        self.mtime_modelo = None
        self.pausado = False        # durante captura y entrenamiento no se abre nada
        self.esperando = None       # rostro autorizado a la espera del PIN
        self.fallos = 0
        self.bloqueado_hasta = 0
        self.ultimo_intento = 0
        self.ultimo_log_desconocido = 0

    # MODELO

    def cargar_modelo(self):
        if not os.path.exists(MODEL_PATH):
            return
        mtime = os.path.getmtime(MODEL_PATH)
        if mtime != self.mtime_modelo:
            modelo = cv2.face.LBPHFaceRecognizer_create()
            modelo.read(MODEL_PATH)
            self.reconocedor = modelo
            self.mtime_modelo = mtime
            print("Modelo cargado")

    # RECONOCIMIENTO

    def reconocer(self, frame):
        frame = redimensionar(frame)
        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        caras = detector.detectMultiScale(gris, 1.3, 5, minSize=(60, 60))

        for (x, y, w, h) in caras:
            rostro = cv2.resize(gris[y:y + h, x:x + w], TAM_ROSTRO, interpolation=cv2.INTER_CUBIC)
            etiqueta, confianza = self.reconocedor.predict(rostro)
            if confianza < UMBRAL_RECONOCIMIENTO:
                self.intentar_abrir(int(etiqueta), confianza)
            else:
                self.registrar_desconocido(confianza)

    def intentar_abrir(self, etiqueta, confianza):
        ahora = time.time()
        with self.lock:
            if self.esperando is not None or ahora - self.ultimo_intento < 2:
                return
            self.ultimo_intento = ahora

        # Se consulta la base en cada intento: si desactivaron a la persona, no pasa
        perfil = db.perfil_por_etiqueta(etiqueta)
        if perfil is None or perfil["estado"] != "activa":
            db.registrar(
                self.dispositivo_id,
                perfil["id"] if perfil else None,
                "Rostro no habilitado",
                "Acceso denegado",
                "rostro_sin_habilitar",
                confianza,
            )
            return

        with self.lock:
            if self.esperando is not None:
                return
            self.esperando = {
                "perfil_id": perfil["id"],
                "nombre": perfil["nombre"],
                "confianza": confianza,
                "desde": ahora,
            }

        if self.ble.enviar("ROSTRO_OK"):
            print(f"Rostro reconocido: {perfil['nombre']}. Esperando PIN en el teclado.")
        else:
            with self.lock:
                self.esperando = None
            print("ESP32 no conectado por Bluetooth")

    def registrar_desconocido(self, confianza):
        ahora = time.time()
        if ahora - self.ultimo_log_desconocido < 30:
            return
        self.ultimo_log_desconocido = ahora
        db.registrar(
            self.dispositivo_id, None, "Rostro desconocido",
            "Acceso denegado", "desconocido", confianza,
        )

    def revisar_timeout(self):
        with self.lock:
            if self.esperando and time.time() - self.esperando["desde"] > TIMEOUT_PIN_SEG:
                print("Tiempo para introducir el PIN agotado")
                self.esperando = None

    # PIN (llega por BLE desde el ESP32)

    def on_mensaje_ble(self, mensaje):
        if mensaje == "LISTO":
            with self.lock:
                self.esperando = None
            print("Listo para otro rostro")
        elif mensaje.startswith("PIN:"):
            self.procesar_pin(mensaje[4:].strip())

    def procesar_pin(self, pin):
        with self.lock:
            contexto = self.esperando
            if contexto is None:
                return
            bloqueado = time.time() < self.bloqueado_hasta

        if bloqueado or not PIN_VALIDO.match(pin):
            correcto = False
        else:
            correcto = db.verificar_pin(self.dispositivo_id, pin)
        pin = None  # el PIN no se conserva en memoria

        with self.lock:
            if correcto:
                self.fallos = 0
            else:
                self.fallos += 1
                if self.fallos >= MAX_INTENTOS_PIN:
                    self.bloqueado_hasta = time.time() + BLOQUEO_PIN_SEG
                    self.fallos = 0
            self.esperando = None

        if correcto:
            self.ble.enviar("ABRIR")
            db.registrar(
                self.dispositivo_id, contexto["perfil_id"],
                f"Acceso: {contexto['nombre']}", "Puerta abierta",
                "autorizado", contexto["confianza"],
            )
            print(f"Acceso autorizado: {contexto['nombre']}")
        else:
            self.ble.enviar("PIN_MAL")
            db.registrar(
                self.dispositivo_id, contexto["perfil_id"],
                f"PIN incorrecto: {contexto['nombre']}", "Acceso denegado",
                "pin_incorrecto", contexto["confianza"],
            )
            print("PIN incorrecto")

    # GESTIÓN DE PERFILES (captura y entrenamiento)

    def gestionar_perfiles(self):
        while True:
            try:
                for perfil in db.perfiles_pendientes():
                    self.registrar_perfil(perfil)
            except Exception as e:
                print(f"Error consultando perfiles: {e}")
            time.sleep(5)

    def registrar_perfil(self, perfil):
        with self.lock:
            self.pausado = True
            self.esperando = None
        try:
            db.cambiar_estado(perfil["id"], "capturando")
            capturar_perfil(self.camara, perfil)
            db.cambiar_estado(perfil["id"], "entrenando")
            entrenar()
            db.cambiar_estado(perfil["id"], "activa")
            print(f"{perfil['nombre']} registrado y activo")
        except Exception as e:
            print(f"Registro fallido para {perfil['nombre']}: {e}")
            db.cambiar_estado(perfil["id"], "pendiente_captura")
        finally:
            with self.lock:
                self.pausado = False

    # BUCLE PRINCIPAL

    def ejecutar(self):
        self.ble.iniciar()
        threading.Thread(target=self.gestionar_perfiles, daemon=True).start()
        print("Servidor iniciado. Ctrl+C para salir.")

        try:
            while True:
                self.cargar_modelo()
                self.revisar_timeout()

                with self.lock:
                    pausado = self.pausado
                frame = self.camara.leer()

                if frame is not None and self.reconocedor is not None and not pausado:
                    self.reconocer(frame)

                time.sleep(0.05)
        except KeyboardInterrupt:
            print("Servidor detenido")
        finally:
            self.camara.cerrar()


if __name__ == "__main__":
    Servidor().ejecutar()