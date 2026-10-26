import sys
import cv2

# Intentar cargar las variables desde config.py
try:
    from config import RTSP_URL, DB_URL
except ImportError:
    print("❌ Error: No se pudo importar 'config.py'. Ejecuta el script desde la carpeta del proyecto.")
    sys.exit(1)


def probar_camara():
    print("\n--- 🎥 Probando conexión con la Cámara RTSP ---")
    print(f"Conectando a: {RTSP_URL}")
    
    cap = cv2.VideoCapture(RTSP_URL)
    if not cap.isOpened():
        print("❌ ERROR: No se pudo abrir la transmisión RTSP.")
        print("   -> Verifica la dirección IP, usuario, contraseña o la red Wi-Fi.")
        return False

    ret, frame = cap.read()
    cap.release()

    if ret and frame is not None:
        h, w, _ = frame.shape
        print(f"✅ ¡Cámara conectada exitosamente!")
        print(f"   Resolución del video: {w}x{h} píxeles")
        return True
    else:
        print("❌ ERROR: La cámara abrió la transmisión pero no entregó ningún fotograma.")
        return False


def probar_bd():
    print("\n--- 🗄️ Probando conexión con la Base de Datos (Supabase) ---")
    
    # Intento de conexión usando psycopg2
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL, connect_timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        cursor.close()
        conn.close()
        print("✅ ¡Conexión a la base de datos exitosa!")
        return True
    except ImportError:
        # Alternativa si usan psycopg (v3)
        try:
            import psycopg
            with psycopg.connect(DB_URL, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
            print("✅ ¡Conexión a la base de datos exitosa!")
            return True
        except ImportError:
            print("⚠️ No se encontró la librería 'psycopg2' ni 'psycopg'.")
            print("   Instálala en tu entorno con: pip install psycopg2-binary")
            return False
    except Exception as e:
        print(f"❌ ERROR de conexión a la Base de Datos:")
        print(f"   {e}")
        return False


if __name__ == "__main__":
    print("==========================================")
    print("   VERIFICACIÓN DE CONEXIONES DEL SISTEMA ")
    print("==========================================")
    
    camara_ok = probar_camara()
    bd_ok = probar_bd()
    
    print("\n==========================================")
    if camara_ok and bd_ok:
        print("🎉 RESULTADO: Ambas conexiones responden correctamente.")
    else:
        print("⚠️ RESULTADO: Hay fallos en la conexión. Revisa las URL en config.py o en tus variables de entorno.")
    print("==========================================\n")