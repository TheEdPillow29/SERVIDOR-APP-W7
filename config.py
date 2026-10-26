import os

# Cámara Wansview (RTSP)
RTSP_URL = "rtsp://CAzbDQHA:Memorias123@192.168.137.208:554/live/ch0"

# Conexión directa a Postgres (Project Settings > Database > Connection string)
DB_URL = "postgresql://postgres.hauzdxvdhgniejcsejdr:CasaSegura29%23@aws-1-ca-central-1.pooler.supabase.com:5432/postgres"

DISPOSITIVO_NOMBRE = os.environ.get("DISPOSITIVO_NOMBRE", "Puerta principal")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "Data")
MODEL_PATH = os.path.join(BASE_DIR, "modeloLBPHFace.xml")

# Reconocimiento
UMBRAL_RECONOCIMIENTO = 70.0
TAM_ROSTRO = (150, 150)
ANCHO_PROCESAMIENTO = 480

# Captura
FOTOS_POR_PERFIL = 300
TIEMPO_MAX_CAPTURA_SEG = 180

# PIN
MAX_INTENTOS_PIN = 3
BLOQUEO_PIN_SEG = 60
TIMEOUT_PIN_SEG = 30

# BLE (ESP32)
BLE_NOMBRE = "ESP32_ACCESO"
BLE_CARACTERISTICA = "abcd1234-5678-1234-5678-abcdef123456"