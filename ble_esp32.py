import asyncio
import threading

from bleak import BleakClient, BleakScanner
from config import BLE_NOMBRE, BLE_CARACTERISTICA


class BLEEsp32:
    def __init__(self, on_mensaje):
        self.on_mensaje = on_mensaje
        self.loop = asyncio.new_event_loop()
        self.cliente = None
        self.conectado = threading.Event()

    def iniciar(self):
        threading.Thread(target=self._hilo, daemon=True).start()

    def _hilo(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._mantener())

    async def _mantener(self):
        while True:
            try:
                dispositivo = await BleakScanner.find_device_by_name(BLE_NOMBRE, timeout=5.0)
                if dispositivo is None:
                    await asyncio.sleep(2)
                    continue

                cliente = BleakClient(
                    dispositivo,
                    disconnected_callback=lambda _: self.conectado.clear(),
                )
                await cliente.connect()
                await cliente.start_notify(BLE_CARACTERISTICA, self._recibir)

                self.cliente = cliente
                self.conectado.set()
                print("ESP32 conectado por Bluetooth")

                while cliente.is_connected:
                    await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Bluetooth: {e}")

            self.conectado.clear()
            self.cliente = None
            await asyncio.sleep(2)

    def _recibir(self, _, datos):
        mensaje = bytes(datos).decode("utf-8", errors="ignore").strip()
        # Se procesa en otro hilo: si se hiciera aquí, enviar() se bloquearía
        # esperando al mismo bucle de eventos
        threading.Thread(target=self.on_mensaje, args=(mensaje,), daemon=True).start()

    def enviar(self, texto):
        if not self.conectado.is_set() or self.cliente is None:
            return False
        futuro = asyncio.run_coroutine_threadsafe(self._escribir(texto), self.loop)
        try:
            return futuro.result(timeout=4)
        except Exception:
            return False

    async def _escribir(self, texto):
        await self.cliente.write_gatt_char(
            BLE_CARACTERISTICA, texto.encode("utf-8"), response=True
        )
        return True