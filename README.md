# Bot de ofertas

Bot que lee canales públicos de Telegram con chollos, filtra las ofertas que interesan y las publica en Discord. También avisa cuando un juego de la lista de deseados de Steam se pone en oferta.

Se ejecuta solo con **GitHub Actions** cada 10 minutos, sin servidor y sin necesidad de tener el ordenador encendido.

## Qué hace

- **Lee canales de Telegram** a través de su página pública (`t.me/s/<canal>`), sin cuenta ni claves de Telegram.
- **Filtra por canal**: palabras que deben aparecer, palabras excluidas y precio máximo.
- **Filtros generales**: categorías que nunca se envían, precio máximo por tipo de producto y videojuegos solo de las plataformas elegidas.
- **Evita repetidos**: si el mismo producto aparece en varios canales, solo se publica una vez.
- **Publica en Discord** como tarjetas con título, descripción y foto del producto, cada canal de Telegram en su propio canal de Discord.
- **Lista de deseados de Steam**: avisa cuando un juego está rebajado y vuelve a avisar si baja más.

## Cómo funciona

```
Telegram (t.me/s/…) ──► ofertas.py ──► filtros ──► Discord (webhooks)
Steam (lista de deseados) ───┘
```

1. GitHub Actions ejecuta `ofertas.py` cada 10 minutos.
2. El script descarga los mensajes nuevos de cada canal desde la última ejecución.
3. Aplica los filtros de `config.py` y descarta los repetidos.
4. Publica las ofertas que pasan en el webhook de Discord correspondiente.
5. Guarda el progreso en `estado.json`, que se conserva en la caché de GitHub Actions (no se sube al repositorio).

## Configuración

Todo lo que se puede ajustar está en [`config.py`](config.py):

| Opción | Para qué sirve |
| --- | --- |
| `CANALES` | Canales de Telegram, sus filtros y el webhook de Discord de destino |
| `EXCLUIR_SIEMPRE` | Productos que no se envían nunca |
| `PRECIO_MAXIMO_POR_PRODUCTO` | Precio máximo para ciertos productos |
| `PALABRAS_JUEGOS` / `JUEGOS_PERMITIDOS` | Qué ofertas de videojuegos pasan |
| `STEAM_ID` | Perfil de Steam cuya lista de deseados se vigila |

Las palabras de los filtros no distinguen mayúsculas ni tildes. Con `*` al final se buscan palabras que empiecen así (`"juegos*"` encuentra `#JuegosPS5`).

### Secretos de GitHub

En **Settings → Secrets and variables → Actions**:

| Secreto | Obligatorio | Descripción |
| --- | --- | --- |
| `DISCORD_WEBHOOK` | Sí | Webhook por defecto |
| `DISCORD_WEBHOOK_CHOLLOMETRO` | No | Webhook del canal de Chollometro |
| `DISCORD_WEBHOOK_STEAM` | No | Webhook para los avisos de Steam |

Si falta un webhook opcional, se usa el de por defecto.

## Ejecución manual

Desde la pestaña **Actions → Ofertas a Discord → Run workflow**. El campo opcional `desde` (por ejemplo `2026-11-01 00:01`) reenvía las ofertas publicadas desde esa fecha.

En local:

```bash
pip install -r requirements.txt
export DISCORD_WEBHOOK="https://discord.com/api/webhooks/..."
python ofertas.py
```

## Estructura

```
├── .github/workflows/ofertas.yml   Ejecución programada en GitHub Actions
├── config.py                       Canales, filtros y ajustes
├── ofertas.py                      Lógica del bot
└── requirements.txt                Dependencias
```
