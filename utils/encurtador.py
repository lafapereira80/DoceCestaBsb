import requests
import urllib.parse


def _link_valido(texto):
    """Garante que a resposta do encurtador é realmente uma URL, e não uma mensagem de erro."""
    t = str(texto or "").strip()
    return (
        t.startswith("https://")
        and " " not in t
        and "\n" not in t
        and "error" not in t.lower()
        and len(t) < 200
    )


def encurtar_link(link_longo):
    """
    Recebe um link longo e retorna a versão curta (Is.gd -> Clck.ru -> TinyURL).
    Se qualquer encurtador falhar ou devolver algo inválido, retorna o link
    original (que sempre funciona), nunca um link quebrado.
    """
    if not link_longo or not str(link_longo).startswith("http"):
        return link_longo

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    codificado = urllib.parse.quote(str(link_longo), safe="")

    servicos = [
        f"https://is.gd/create.php?format=simple&url={codificado}",
        f"https://clck.ru/--?url={codificado}",
        f"https://tinyurl.com/api-create.php?url={codificado}",
    ]

    for url in servicos:
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200 and _link_valido(res.text):
                return res.text.strip()
        except Exception:
            continue

    return link_longo
