"""
Configuración del bot: qué canales se leen, qué ofertas pasan y adónde se mandan.

Cómo escribir las palabras de los filtros (da igual mayúsculas y tildes):
    "nike"        busca la palabra entera (no pilla "nikelado")
    "juegos*"     con asterisco, palabras que EMPIECEN así ("juegos", "#JuegosPS5")
    "north face"  también vale una frase
"""

# Videojuegos: si una oferta habla de juegos o consolas, solo pasa si es de alguna de estas plataformas
PALABRAS_JUEGOS = [
    "juegos*", "videojuego*", "playstation", "ps4", "ps5", "xbox", "nintendo",
    "switch", "steam", "dualsense", "game pass", "ps plus",
]
JUEGOS_PERMITIDOS = ["ps5", "steam"]

# Nunca se manda, venga del canal que venga
EXCLUIR_SIEMPRE = [
    # Móviles
    "movil*", "smartphone*", "iphone*", "telefono movil",
    # Auriculares
    "auricular*", "cascos", "headphone*", "earbuds", "airpods", "buds", "freebuds",
]

# Precio máximo por tipo de producto: (palabras, euros)
PRECIO_MAXIMO_POR_PRODUCTO = [
    (["altavoz", "altavoces", "speaker*", "barra de sonido"], 50),
]

# Canales de Telegram (deben ser públicos: t.me/<nombre>)
#   webhook        nombre del secreto de GitHub con el webhook del canal de Discord de destino
#   incluir        si está vacío pasa todo; si no, solo las ofertas que contengan alguna palabra
#   excluir        se descartan las ofertas que contengan alguna palabra
#   precio_maximo  en euros, o None para no limitar
#   color          color del borde de la tarjeta en Discord
CANALES = {
    "imartzofertas": {
        "webhook": "DISCORD_WEBHOOK",
        "incluir": [],
        "excluir": [],
        "precio_maximo": None,
        "color": 0xF57C00,
    },
    "chollometro": {
        "webhook": "DISCORD_WEBHOOK_CHOLLOMETRO",
        "incluir": [
            # Viajes
            "viaje*", "vuelo*", "hotel*", "escapada*", "crucero*", "vacaciones",
            "alojamiento*", "ryanair", "vueling", "iberia", "booking", "airbnb",
            "renfe", "ouigo", "iryo", "tren", "trenes",
            # Informática
            "informatica", "ordenador*", "portatil*", "pc", "sobremesa", "monitor*",
            "ssd", "nvme", "disco duro", "ram", "ddr4", "ddr5", "grafica*", "rtx",
            "radeon", "nvidia", "ryzen", "intel", "procesador*", "placa base",
            "raton*", "teclado*", "pendrive*", "memoria usb", "router*", "tablet*",
            "ipad", "macbook", "pccomponentes", "impresora*", "webcam*",
            # Videojuegos
            "ps5", "steam",
            # Ropa de marca
            "nike", "adidas", "north face", "thenorthface",
            # Suscripciones
            "suscripcion*", "spotify", "netflix", "disney*", "hbo", "prime video",
            "amazon prime", "youtube premium", "crunchyroll", "dazn",
            "meses gratis", "mes gratis", "prueba gratis",
        ],
        "excluir": ["juegos de mesa", "juegosdemesa*"],
        "precio_maximo": None,
        "color": 0xE53935,
    },
}

# Lista de deseados de Steam (el perfil y la lista tienen que ser públicos)
STEAM_ID = "76561198406348210"
STEAM_WEBHOOK = "DISCORD_WEBHOOK_STEAM"   # si no existe, se usa DISCORD_WEBHOOK
STEAM_PAIS = "es"

# Ofertas repetidas: cuántos días se recuerda lo ya enviado
DIAS_RECORDAR = 3

ZONA_HORARIA = "Europe/Madrid"
