import psycopg2
from config import DB_URL, DISPOSITIVO_NOMBRE

_conexion = None


def _conn():
    global _conexion
    if _conexion is None or _conexion.closed:
        _conexion = psycopg2.connect(DB_URL)
        _conexion.autocommit = True
    return _conexion


def _consulta(sql, params=()):
    with _conn().cursor() as cur:
        cur.execute(sql, params)
        if cur.description is None:
            return []
        columnas = [c[0] for c in cur.description]
        return [dict(zip(columnas, fila)) for fila in cur.fetchall()]


def dispositivo_id():
    filas = _consulta(
        "select id from public.dispositivos where nombre = %s",
        (DISPOSITIVO_NOMBRE,),
    )
    if not filas:
        raise RuntimeError(f"No existe el dispositivo '{DISPOSITIVO_NOMBRE}'")
    return str(filas[0]["id"])


def perfiles_pendientes():
    return _consulta(
        """select id, nombre, etiqueta, estado
           from public.perfiles_rostro
           where estado = 'pendiente_captura'
           order by created_at"""
    )


def cambiar_estado(perfil_id, estado):
    _consulta(
        "update public.perfiles_rostro set estado = %s where id = %s",
        (estado, perfil_id),
    )


def perfiles_para_entrenar():
    return _consulta(
        """select etiqueta from public.perfiles_rostro
           where estado in ('activa', 'entrenando')
           order by etiqueta"""
    )


def perfil_por_etiqueta(etiqueta):
    filas = _consulta(
        "select id, nombre, estado from public.perfiles_rostro where etiqueta = %s",
        (etiqueta,),
    )
    return filas[0] if filas else None


def verificar_pin(dispositivo_id, pin):
    filas = _consulta(
        """select extensions.crypt(%s, pin_hash) = pin_hash as ok
           from public.pin_dispositivo
           where dispositivo_id = %s""",
        (pin, dispositivo_id),
    )
    return bool(filas and filas[0]["ok"])


def registrar(dispositivo_id, perfil_id, titulo, estado, resultado, confianza=None):
    _consulta(
        """insert into public.actividades
           (dispositivo_id, perfil_id, titulo, estado, resultado, confianza)
           values (%s, %s, %s, %s, %s, %s)""",
        (dispositivo_id, perfil_id, titulo, estado, resultado, confianza),
    )