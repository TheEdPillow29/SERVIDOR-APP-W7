# WEA-APP-W7
# Smarthome: control de acceso con reconocimiento facial

Sistema de control de acceso para una cerradura, formado por tres partes:

1. **App Android** (Jetpack Compose + Supabase): administración de la cerradura, perfiles de rostro, PIN y registro de actividad.
2. **Servidor en computadora** (Python + OpenCV): captura y entrenamiento de rostros, reconocimiento en vivo, verificación del PIN y comunicación con el ESP32.
3. **Base de datos en Supabase**: fuente de verdad del estado de la cerradura, perfiles, PIN (como hash) y actividad.

El ESP32 y su firmware todavía no están incluidos en el repositorio.

> **Estado:** prototipo en desarrollo. Parte de la lógica está probada y parte no. Ver [Estado actual](#estado-actual).

---

## Estructura del repositorio

```
/app            Aplicación Android (Kotlin, Jetpack Compose)
/servidor       Servidor de reconocimiento (Python)
/supabase       Esquema SQL, funciones y políticas RLS
/a9-v720        Librería de la cámara A9 (referencia, no usada por el servidor actual)
/firmware       Pendiente: código del ESP32
```

---

## Arquitectura

```
                 ┌──────────────────────────┐
  App Android ──▶│        Supabase          │◀── Servidor (Python)
  (admin)        │  dispositivos            │    (DB directa, psycopg2)
                 │  perfiles_rostro         │
                 │  pin_dispositivo (hash)  │
                 │  actividades             │
                 └──────────────────────────┘
                                                      │ BLE
  Cámara Wansview ── RTSP ──▶ Servidor ──────────▶ ESP32 ──▶ Relé / cerradura
                                                  (teclado: PIN)
```

- La **app** no controla la cámara ni recibe imágenes. Crea perfiles, cambia el estado de la cerradura, cambia el PIN y consulta la actividad.
- El **servidor** lee la cámara por RTSP, detecta y reconoce rostros, verifica el PIN y actualiza la base.
- El **ESP32** recibe órdenes por BLE y lee el teclado. No conoce el PIN ni el hash.

---

## Flujos principales

### 1. Registro de una persona

1. El administrador crea un perfil en la app (nombre + casilla de consentimiento). Queda en `pendiente_captura`.
2. El servidor detecta el perfil en su revisión periódica (cada 5 s) y cambia el estado a `capturando`.
3. La persona se pone frente a la cámara. El servidor guarda hasta 300 recortes de rostro en `Data/<etiqueta>/`, solo cuando hay **una sola cara** en el cuadro.
4. El estado pasa a `entrenando`. El servidor reentrena LBPH con todas las personas `activa` y el nuevo perfil, y reemplaza el modelo de forma atómica.
5. El estado pasa a `activa`.

Las imágenes nunca salen de la computadora ni pasan por la base de datos.

### 2. Acceso

1. La cámara muestra a una persona. El servidor la reconoce con LBPH y confianza menor que 70.
2. Comprueba en la base que el perfil esté `activa`. Si no, registra `rostro_sin_habilitar`.
3. Envía `ROSTRO_OK` al ESP32 por BLE.
4. La persona escribe el PIN en el teclado. El ESP32 lo envía como `PIN:xxxx`.
5. El servidor compara el PIN con el hash en `pin_dispositivo`.
   - Correcto: responde `ABRIR`, registra `autorizado`.
   - Incorrecto: responde `PIN_MAL`, registra `pin_incorrecto`.
6. Tras 3 fallos seguidos, el servidor bloquea el teclado 60 segundos.
7. El ESP32 responde `LISTO` al terminar.

### 3. Control de la cerradura desde la app

El botón de la app cambia `is_locked` en `dispositivos` y registra la acción en `actividades`. El ESP32 debe leer ese valor y accionar el relé en consecuencia.

> Pendiente: el firmware que consulta `is_locked` en Supabase.

### 4. Cambio de PIN

La app llama a la función `set_pin()` en Supabase. Solo administradores pueden ejecutarla. La función guarda el PIN como hash bcrypt en `pin_dispositivo`. Nadie puede leer el hash desde la app, porque esa tabla no tiene políticas.

---

## Base de datos (Supabase)

El esquema completo está en `/supabase/schema.sql`.

| Tabla | Contenido | Acceso |
|---|---|---|
| `dispositivos` | Cerraduras. `is_locked`, `estado` | Admin lee y cambia. Clave pública puede leer solo `Puerta principal` |
| `perfiles_rostro` | Personas registrables. `etiqueta` (número LBPH), `estado`, consentimiento | Admin gestiona |
| `pin_dispositivo` | Hash del PIN por dispositivo | Sin políticas: solo el servidor |
| `actividades` | Historial de accesos y acciones manuales | Admin lee y registra |

**Estados de perfil:** `pendiente_captura` → `capturando` → `entrenando` → `activa` ↔ `desactivada`.

**Administrador:** la primera cuenta creada recibe `role = admin` en `app_metadata` mediante un trigger. El registro público debe estar desactivado en Authentication. Las cuentas siguientes no son administradoras.

---

## Requisitos

**App Android**
- Android Studio reciente, JDK 17 o superior
- Proyecto Supabase con el esquema aplicado
- Teléfono con Android 7.0 o superior (minSdk según `build.gradle.kts`)

**Servidor**
- Python 3.12 de 64 bits
- Bluetooth en la computadora (solo con ESP32 real)
- Cámara Wansview con RTSP activado, en la misma red local
- Dependencias: `opencv-contrib-python`, `numpy`, `bleak`, `psycopg2-binary`

> `opencv-contrib-python` es necesario: el reconocedor LBPH está en el módulo `contrib`.

---

## Configuración

### Supabase
1. Crear el proyecto y ejecutar `supabase/schema.sql` en el SQL Editor.
2. Crear tu cuenta de administrador en **Authentication > Users**, con **Auto Confirm User** activado.
3. Comprobar el rol:
   ```sql
   select email, raw_app_meta_data ->> 'role' as rol from auth.users;
   ```
4. Desactivar **Allow new users to sign up** en **Authentication > Settings**.
5. Crear el bucket privado `rostros` si se usará Storage (no es necesario con el flujo actual).

### App Android
Editar `data/SupabaseClient.kt` con la URL y la clave **pública** del proyecto:

```kotlin
object SupabaseConfig {
    const val SUPABASE_URL = "https://TU-PROYECTO.supabase.co"
    const val SUPABASE_KEY = "TU_CLAVE_PUBLICA"
}
```

Editar `config/CameraConfig.kt` con la URL RTSP de la cámara. Esta URL se usa en la pestaña **Cámaras** y solo funciona si el teléfono está en la misma red Wi-Fi.

```kotlin
object CameraConfig {
    const val RTSP_URL = "rtsp://usuario:clave@IP_CAMARA:554/live/ch0"
}
```

### Servidor
Variables de entorno (no van en el código):

| Variable | Obligatoria | Descripción |
|---|---|---|
| `CAMARA_RTSP` | Sí | URL RTSP de la cámara |
| `SUPABASE_DB_URL` | Sí | Cadena de conexión a Postgres (Project Settings > Database) |
| `DISPOSITIVO_NOMBRE` | No | Por defecto `Puerta principal` |
| `MODO_SIMULADO` | No | `1` para usar el simulador de ESP32 desde la terminal |

En PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install opencv-contrib-python numpy bleak psycopg2-binary

$env:CAMARA_RTSP = "rtsp://usuario:clave@IP_CAMARA:554/live/ch0"
$env:SUPABASE_DB_URL = "postgresql://postgres:CLAVE@HOST:5432/postgres"
$env:MODO_SIMULADO = "1"
python servidor.py
```

Si la conexión directa a la base falla por IPv6, usa la cadena **Session pooler** del botón **Connect** del panel.

---

## Módulos del servidor

| Archivo | Función |
|---|---|
| `config.py` | Variables de entorno y parámetros (umbral, fotos por perfil, tiempos de PIN) |
| `db.py` | Consultas a Postgres: perfiles, PIN, actividades |
| `camara.py` | Lectura continua del RTSP en un hilo, con reconexión |
| `captura_entrenamiento.py` | Captura de fotos y entrenamiento LBPH |
| `ble_esp32.py` | Comunicación BLE con el ESP32 |
| `ble_simulado.py` | Simulador de ESP32 desde la terminal |
| `servidor.py` | Flujo principal: reconocimiento, PIN, bloqueos, gestión de perfiles |

---

## Protocolo BLE

| Mensaje | Dirección | Significado |
|---|---|---|
| `ROSTRO_OK` | Servidor → ESP32 | Rostro reconocido. Pedir PIN |
| `PIN:xxxx` | ESP32 → Servidor | PIN introducido en el teclado |
| `ABRIR` | Servidor → ESP32 | PIN correcto. Activar relé |
| `PIN_MAL` | Servidor → ESP32 | PIN incorrecto o bloqueado |
| `LISTO` | ESP32 → Servidor | Ciclo terminado |

Característica BLE: `abcd1234-5678-1234-5678-abcdef123456`, nombre `ESP32_ACCESO`. El ESP32 debe aceptar escritura y enviar notificaciones.

---

## Estado actual

| Componente | Estado |
|---|---|
| Login y gestión de sesión | Funciona. El login muestra error si las credenciales son incorrectas |
| Cerradura desde la app (`is_locked`) | Escribe en la base. Falta el firmware que la lee |
| Cambio de PIN desde la app | Implementado con `set_pin()`. Verificar en la base |
| Perfiles desde la app | Pendiente de adaptar `ViewModel` y `HomeScreen` al esquema nuevo |
| Cámara en la app (RTSP con libVLC) | Funciona con la red local |
| Captura y entrenamiento en el servidor | Implementado. Pendiente de pruebas con la cámara |
| Reconocimiento y verificación de PIN | Implementado. Probado con simulador |
| Comunicación BLE con el ESP32 | Implementada. No probada con hardware |
| Firmware del ESP32 | **No existe todavía** |

---

## Pendientes

- Adaptar `SmarthomeViewModel.kt` y `HomeScreen.kt` al esquema nuevo (`PerfilRostro`, sin `usuarios` ni `user_preferences`).
- Firmware del ESP32: BLE, teclado, relé, lectura de `is_locked` en Supabase y protocolo de la sección anterior.
- Emparejamiento o cifrado BLE para proteger el PIN en el aire.
- Migrar o recapturar las personas: las carpetas actuales de `Data/` son de la A9 y no están en la base.
- Límites de intentos y bloqueos persistentes (ahora están en memoria).
- Acceso remoto a la cámara desde fuera de casa (VPN u otra solución).

---

## Seguridad y privacidad

- **No subir al repositorio:** `.env`, `local.properties`, `Data/`, `modeloLBPHFace.xml`, `.venv/`, `__pycache__/`. El `.gitignore` debe incluirlos.
- **Clave de la base de datos y `service_role`:** solo en variables de entorno del servidor. Nunca en la app ni en el firmware.
- **Clave pública en la app:** es visible dentro del APK. La protección real la dan las políticas RLS.
- **Datos biométricos:** son datos personales sensibles. Obtén consentimiento y revisa la normativa aplicable (por ejemplo, la Ley 81 de 2019 de protección de datos personales en Panamá).
- **Credenciales expuestas:** si la contraseña de la cámara o alguna clave se compartieron en algún chat o archivo, cámbialas antes de publicar el repositorio.
- **Suplantación:** LBPH no detecta fotos ni vídeos. Un PIN corto y un teclado sin límite de intentos no son suficientes por sí solos. Por eso el servidor bloquea tras 3 fallos.

---

## Créditos

- Librería de la cámara A9: proyecto `a9-v720`, usada como referencia del protocolo. No la usa el servidor actual.
