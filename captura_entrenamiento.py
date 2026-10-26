import os
import time

import cv2
import numpy as np

from config import (
    DATA_DIR, MODEL_PATH, FOTOS_POR_PERFIL, TAM_ROSTRO,
    ANCHO_PROCESAMIENTO, TIEMPO_MAX_CAPTURA_SEG,
)
import db

detector = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


def redimensionar(frame):
    alto, ancho = frame.shape[:2]
    nuevo_alto = int(alto * ANCHO_PROCESAMIENTO / ancho)
    return cv2.resize(frame, (ANCHO_PROCESAMIENTO, nuevo_alto), interpolation=cv2.INTER_AREA)


def capturar_perfil(camara, perfil):
    carpeta = os.path.join(DATA_DIR, str(perfil["etiqueta"]))
    os.makedirs(carpeta, exist_ok=True)

    existentes = [
        int(f[7:-4]) for f in os.listdir(carpeta)
        if f.startswith("rostro_") and f[7:-4].isdigit()
    ]
    siguiente = max(existentes) + 1 if existentes else 0

    capturadas = 0
    inicio = time.time()
    print(f"Capturando fotos de {perfil['nombre']}. Mírese a la cámara.")

    while capturadas < FOTOS_POR_PERFIL:
        if time.time() - inicio > TIEMPO_MAX_CAPTURA_SEG:
            raise TimeoutError("No se capturaron suficientes fotos a tiempo")

        frame = camara.leer()
        if frame is None:
            time.sleep(0.05)
            continue

        frame = redimensionar(frame)
        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        caras = detector.detectMultiScale(gris, 1.3, 5, minSize=(60, 60))

        # Solo se guarda si hay exactamente una cara: así no entra otra persona en la carpeta
        if len(caras) != 1:
            time.sleep(0.1)
            continue

        x, y, w, h = caras[0]
        rostro = cv2.resize(gris[y:y + h, x:x + w], TAM_ROSTRO, interpolation=cv2.INTER_CUBIC)
        cv2.imwrite(os.path.join(carpeta, f"rostro_{siguiente}.jpg"), rostro)

        siguiente += 1
        capturadas += 1
        if capturadas % 50 == 0:
            print(f"  {capturadas}/{FOTOS_POR_PERFIL}")
        time.sleep(0.15)  # evita guardar casi el mismo cuadro muchas veces

    print("Captura terminada")


def entrenar():
    etiquetas_validas = [int(p["etiqueta"]) for p in db.perfiles_para_entrenar()]

    imagenes, etiquetas = [], []
    for etiqueta in etiquetas_validas:
        carpeta = os.path.join(DATA_DIR, str(etiqueta))
        if not os.path.isdir(carpeta):
            raise RuntimeError(f"Falta la carpeta de la etiqueta {etiqueta}")
        for nombre in os.listdir(carpeta):
            img = cv2.imread(os.path.join(carpeta, nombre), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                imagenes.append(img)
                etiquetas.append(etiqueta)

    if not imagenes:
        raise RuntimeError("No hay imágenes para entrenar")

    modelo = cv2.face.LBPHFaceRecognizer_create()
    modelo.train(imagenes, np.array(etiquetas, dtype=np.int32))

    # Se escribe en un archivo temporal y luego se reemplaza: el reconocimiento
    # nunca lee un modelo a medio escribir
    temporal = MODEL_PATH.replace(".xml", "_tmp.xml")
    modelo.write(temporal)
    os.replace(temporal, MODEL_PATH)

    print(f"Modelo entrenado: {len(set(etiquetas))} personas, {len(imagenes)} imágenes")