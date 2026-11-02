"""
Bot de ofertas: lee canales públicos de Telegram, filtra las ofertas y las publica en Discord.
También avisa cuando un juego de la lista de deseados de Steam está rebajado.

Uso:
    pip install -r requirements.txt
    DISCORD_WEBHOOK="https://discord.com/api/webhooks/..." python ofertas.py

Variables de entorno:
    DISCORD_WEBHOOK               webhook por defecto (obligatorio)
    DISCORD_WEBHOOK_CHOLLOMETRO   y el resto de webhooks definidos en config.py (opcionales)
    DESDE                         opcional, "AAAA-MM-DD HH:MM": reenvía las ofertas desde esa fecha

El progreso (último mensaje leído de cada canal, ofertas recientes y avisos de Steam)
se guarda en estado.json.
"""

import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

import config

ESTADO = Path(__file__).with_name("estado.json")
ZONA = ZoneInfo(config.ZONA_HORARIA)
CABECERAS = {"User-Agent": "Mozilla/5.0 (bot-ofertas)"}
WEBHOOK_POR_DEFECTO = os.environ.get("DISCORD_WEBHOOK", "").strip()
DESDE = os.environ.get("DESDE", "").strip()

PATRON_PRECIO = re.compile(r"(\d[\d.,]*)\s?€|€\s?(\d[\d.,]*)")
PATRON_URL_CSS = re.compile(r"url\(['\"]?(.*?)['\"]?\)")
LINEAS_DE_RELLENO = ("compartido por", "ofertas mas de", "mas chollos:", "ponte alertas")
PALABRAS_VACIAS = {
    "solo", "con", "para", "por", "del", "los", "las", "una", "uno", "desde", "sin",
    "aranceles", "espana", "envio", "oferta", "chollo", "ahorra", "cupon", "codigo",
    "precio", "minimo", "historico", "rebaja", "rebajado",
}


# ---------------------------------------------------------------- texto y filtros

def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes."""
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def patron(palabra: str) -> re.Pattern:
    p = normalizar(palabra)
    if p.endswith("*"):
        return re.compile(r"(?<![a-z0-9])" + re.escape(p[:-1]))
    return re.compile(r"(?<![a-z0-9])" + re.escape(p) + r"(?![a-z0-9])")


def contiene_alguna(texto_normalizado: str, palabras: list[str]) -> bool:
    return any(patron(p).search(texto_normalizado) for p in palabras)


def a_numero(txt: str) -> float:
    txt = txt.strip(".,")
    if "," in txt:                                   # 1.299,99 -> 1299.99
        txt = txt.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", txt):    # 1.299 -> 1299
        txt = txt.replace(".", "")
    return float(txt)


def precios_en(texto: str) -> list[float]:
    precios = []
    for m in PATRON_PRECIO.finditer(texto):
        try:
            precios.append(a_numero(m.group(1) or m.group(2)))
        except ValueError:
            pass
    return precios


def supera_precio(texto: str, limite: float) -> bool:
    """El precio de oferta suele ser el más bajo del mensaje (el otro es el de antes)."""
    precios = precios_en(texto)
    return bool(precios) and min(precios) > limite


def pasa_filtro(texto: str, filtros: dict) -> bool:
    t = normalizar(texto)
    if contiene_alguna(t, config.PALABRAS_JUEGOS) and not contiene_alguna(t, config.JUEGOS_PERMITIDOS):
        return False
    if contiene_alguna(t, config.EXCLUIR_SIEMPRE):
        return False
    for palabras, limite in config.PRECIO_MAXIMO_POR_PRODUCTO:
        if contiene_alguna(t, palabras) and supera_precio(texto, limite):
            return False
    if filtros["excluir"] and contiene_alguna(t, filtros["excluir"]):
        return False
    if filtros["incluir"] and not contiene_alguna(t, filtros["incluir"]):
        return False
    if filtros.get("precio_maximo") is not None and supera_precio(texto, filtros["precio_maximo"]):
        return False
    return True


def separar_titulo(texto: str) -> tuple[str, str]:
    """El título es la línea del producto (la que lleva 🔹 o, si no hay, la primera)."""
    lineas = texto.split("\n")
    i = next((n for n, linea in enumerate(lineas) if "🔹" in linea), 0)
    titulo = lineas[i].replace("🔹", "").strip()
    resto = "\n".join(lineas[:i] + lineas[i + 1:]).strip()
    return titulo, re.sub(r"\n{3,}", "\n\n", resto)


# ---------------------------------------------------------------- Telegram

def buscar_imagen(mensaje) -> str | None:
    """Foto del producto: la del mensaje, la de la vista previa del enlace o un enlace a imagen."""
    for selector in (".tgme_widget_message_photo_wrap", ".link_preview_image",
                     ".link_preview_right_image"):
        el = mensaje.select_one(selector)
        if el and el.get("style"):
            encontrado = PATRON_URL_CSS.search(el["style"])
            if encontrado:
                url = encontrado.group(1)
                return "https:" + url if url.startswith("//") else url
    cuerpo = mensaje.select_one(".tgme_widget_message_text")
    if cuerpo:
        for a in cuerpo.find_all("a", href=True):
            if re.search(r"\.(png|jpe?g|webp)(\?|$)", a["href"], re.I):
                return a["href"].replace("http://", "https://", 1)
    return None


def limpiar_texto(texto: str) -> str:
    lineas = [l for l in texto.split("\n")
              if not any(r in normalizar(l) for r in LINEAS_DE_RELLENO)]
    return "\n".join(lineas).strip()


def leer_pagina(html: str) -> list[tuple[int, str, str | None, datetime | None]]:
    """Devuelve [(id, texto, imagen, fecha)] de una página pública t.me/s/<canal>."""
    sopa = BeautifulSoup(html, "html.parser")
    mensajes = []
    for m in sopa.select("div.tgme_widget_message[data-post]"):
        post = m["data-post"]
        try:
            num = int(post.rsplit("/", 1)[1])
        except (IndexError, ValueError):
            continue
        cuerpo = m.select_one(".tgme_widget_message_text")
        if not cuerpo:
            continue
        imagen = buscar_imagen(m)
        for br in cuerpo.find_all("br"):
            br.replace_with("\n")
        texto = limpiar_texto(cuerpo.get_text())
        fecha = None
        t = m.select_one(".tgme_widget_message_date time[datetime]")
        if t:
            try:
                fecha = datetime.fromisoformat(t["datetime"])
            except ValueError:
                pass
        if texto:
            mensajes.append((num, texto, imagen, fecha))
    return sorted(mensajes, key=lambda x: x[0])


def descargar(url: str) -> list[tuple[int, str, str | None, datetime | None]]:
    r = requests.get(url, headers=CABECERAS, timeout=30)
    r.raise_for_status()
    return leer_pagina(r.text)


def mensajes_recientes(canal: str) -> list[tuple[int, str, str | None]]:
    return [(n, t, i) for n, t, i, _ in descargar(f"https://t.me/s/{canal}")]


def mensajes_desde(canal: str, desde: datetime, hasta_id: int) -> list[tuple[int, str, str | None]]:
    """Recorre el canal hacia atrás y devuelve los mensajes con fecha >= desde e id <= hasta_id."""
    encontrados = {}
    url = f"https://t.me/s/{canal}?before={hasta_id + 1}"
    for _ in range(100):
        pagina = descargar(url)
        if not pagina:
            break
        for num, texto, imagen, fecha in pagina:
            if num <= hasta_id and fecha and fecha >= desde:
                encontrados[num] = (num, texto, imagen)
        fechas = [f for *_, f in pagina if f]
        if fechas and min(fechas) < desde:
            break
        url = f"https://t.me/s/{canal}?before={pagina[0][0]}"
        time.sleep(1)
    return [encontrados[k] for k in sorted(encontrados)]


# ---------------------------------------------------------------- Discord

def webhook(nombre_secreto: str) -> str:
    return os.environ.get(nombre_secreto, "").strip() or WEBHOOK_POR_DEFECTO


def publicar(url_webhook: str, tarjeta: dict) -> None:
    # La tarjeta (embed) evita las vistas previas automáticas de los enlaces;
    # el carácter en blanco deja una línea de separación entre ofertas.
    datos = {"content": "⠀", "embeds": [tarjeta]}
    for _ in range(3):
        r = requests.post(url_webhook, json=datos, timeout=30)
        if r.status_code == 429:
            time.sleep(float(r.json().get("retry_after", 2)))
            continue
        r.raise_for_status()
        return


def publicar_oferta(canal: str, texto: str, imagen: str | None) -> None:
    ajustes = config.CANALES[canal]
    titulo, resto = separar_titulo(texto)
    tarjeta = {"title": titulo[:256], "description": resto[:4000], "color": ajustes.get("color", 0x5865F2)}
    if imagen:
        tarjeta["thumbnail"] = {"url": imagen}
    publicar(webhook(ajustes.get("webhook", "DISCORD_WEBHOOK")), tarjeta)


# ---------------------------------------------------------------- ofertas repetidas

def huella(texto: str) -> set[str]:
    """Palabras importantes del nombre del producto, sin precios ni relleno."""
    titulo, _ = separar_titulo(texto)
    t = normalizar(PATRON_PRECIO.sub(" ", titulo))
    return {p for p in re.findall(r"[a-z0-9]+", t) if len(p) >= 3 and p not in PALABRAS_VACIAS}


def es_repetida(texto: str, vistos: list) -> bool:
    h = huella(texto)
    if len(h) < 2:
        return False
    numeros_h = {p for p in h if any(c.isdigit() for c in p)}
    for v in vistos:
        otra = set(v["p"])
        numeros_o = {p for p in otra if any(c.isdigit() for c in p)}
        # Modelos o capacidades distintas (2TB / 4TB) no son el mismo producto
        if not (numeros_h <= numeros_o or numeros_o <= numeros_h):
            continue
        comunes = len(h & otra)
        if otra and comunes >= 3 and comunes / min(len(h), len(otra)) >= 0.75:
            return True
    return False


def recordar(texto: str, vistos: list) -> None:
    vistos.append({"t": datetime.now(ZONA).isoformat(timespec="minutes"), "p": sorted(huella(texto))})


def vistos_recientes(vistos: list) -> list:
    ahora = datetime.now(ZONA)
    return [v for v in vistos
            if (ahora - datetime.fromisoformat(v["t"])).days < config.DIAS_RECORDAR][-500:]


def procesar(canal: str, texto: str, imagen: str | None, vistos: list) -> bool:
    """Filtra, descarta repetidas y publica. Devuelve True si se ha publicado."""
    if not pasa_filtro(texto, config.CANALES[canal]):
        return False
    if es_repetida(texto, vistos):
        print(f"🔁 [{canal}] repetida: {texto[:50]!r}")
        return False
    publicar_oferta(canal, texto, imagen)
    recordar(texto, vistos)
    time.sleep(1)
    return True


# ---------------------------------------------------------------- Steam

def revisar_steam(estado: dict) -> None:
    """Avisa cuando un juego de la lista de deseados está rebajado (una vez por cada precio)."""
    r = requests.get("https://api.steampowered.com/IWishlistService/GetWishlist/v1/",
                     params={"steamid": config.STEAM_ID}, timeout=30)
    r.raise_for_status()
    appids = [str(i["appid"]) for i in r.json().get("response", {}).get("items", [])]
    avisados = estado.setdefault("_steam", {})

    precios = {}
    for i in range(0, len(appids), 50):
        r = requests.get("https://store.steampowered.com/api/appdetails",
                         params={"appids": ",".join(appids[i:i + 50]), "cc": config.STEAM_PAIS,
                                 "filters": "price_overview"}, timeout=30)
        r.raise_for_status()
        for appid, info in r.json().items():
            if info.get("success") and isinstance(info.get("data"), dict):
                precios[appid] = info["data"].get("price_overview")

    for appid, p in precios.items():
        if not p or p.get("discount_percent", 0) <= 0:
            avisados.pop(appid, None)
            continue
        if avisados.get(appid) == p["final"]:
            continue
        nombre = appid
        try:
            d = requests.get("https://store.steampowered.com/api/appdetails",
                             params={"appids": appid, "cc": config.STEAM_PAIS, "filters": "basic"},
                             timeout=30).json()
            nombre = d[appid]["data"]["name"]
        except Exception:
            pass
        antes, ahora = p["initial"] / 100, p["final"] / 100
        publicar(webhook(config.STEAM_WEBHOOK), {
            "title": f"🎮 {nombre} -{p['discount_percent']}%",
            "url": f"https://store.steampowered.com/app/{appid}/",
            "description": f"**{ahora:.2f} €** (antes {antes:.2f} €)\nEstá en tu lista de deseados de Steam",
            "color": 0x66C0F4,
            "thumbnail": {"url": f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"},
        })
        print(f"🎮 [steam] {nombre} -{p['discount_percent']}% {ahora:.2f}€")
        avisados[appid] = p["final"]
        time.sleep(1)


# ---------------------------------------------------------------- principal

def main() -> int:
    if not WEBHOOK_POR_DEFECTO:
        print("Falta la variable DISCORD_WEBHOOK.")
        return 1

    estado = json.loads(ESTADO.read_text()) if ESTADO.exists() else {}
    vistos = vistos_recientes(estado.get("_vistos", []))

    if DESDE:
        desde = datetime.fromisoformat(DESDE).replace(tzinfo=ZONA)
        print(f"Reenviando ofertas desde {desde:%d/%m/%Y %H:%M}")
        for canal in config.CANALES:
            hasta = estado.get(canal)
            if hasta is None:
                continue
            try:
                antiguas = mensajes_desde(canal, desde, hasta)
            except Exception as e:
                print(f"[{canal}] No se pudo leer el historial: {e}")
                continue
            enviadas = sum(procesar(canal, t, i, vistos) for _, t, i in antiguas)
            print(f"[{canal}] {len(antiguas)} ofertas desde esa fecha, {enviadas} publicadas")

    for canal in config.CANALES:
        try:
            mensajes = mensajes_recientes(canal)
        except Exception as e:
            print(f"[{canal}] No se pudo leer: {e}")
            continue
        if not mensajes:
            continue

        ultimo = estado.get(canal)
        if ultimo is None:
            # Primera ejecución: se empieza desde el último mensaje, sin enviar el historial
            estado[canal] = mensajes[-1][0]
            print(f"[{canal}] Primera ejecución, empiezo en el mensaje {mensajes[-1][0]}")
            continue

        for num, texto, imagen in mensajes:
            if num <= ultimo:
                continue
            marca = "✅" if procesar(canal, texto, imagen, vistos) else "⛔"
            print(f"{marca} [{canal}] {texto[:60].replace(chr(10), ' ')}")
            estado[canal] = num

    try:
        revisar_steam(estado)
    except Exception as e:
        print(f"[steam] No se pudo revisar la lista de deseados: {e}")

    estado["_vistos"] = vistos
    ESTADO.write_text(json.dumps(estado, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
