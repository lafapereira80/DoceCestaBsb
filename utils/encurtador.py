"""
Link curto PRÓPRIO para o pagamento (sem is.gd / clck.ru / tinyurl).

O link oficial da InfinitePay é longo (https://checkout.infinitepay.io/<handle>?lenc=<token>). O Cloudflare
Worker do projeto (infinitepay-webhook) responde em  <BASE>/<codigo>  e redireciona para o link oficial salvo
no banco (pedidos.infinitepay_url). O código são os 8 primeiros caracteres do ID do pedido.

Secret (Streamlit / .streamlit/secrets.toml da VM) - sempre ANTES de qualquer [bloco]:
    LINK_CURTO_BASE = "https://pagamento.docecestabrasilia.com.br"
    ->  https://pagamento.docecestabrasilia.com.br/abcd1234
Sem o secret, usa o endereço workers.dev do webhook:  <workers.dev>/p/abcd1234
"""
import re
import requests
import streamlit as st

BASE_PADRAO = "https://infinitepay-webhook.lafapereira.workers.dev"
_UA = {"User-Agent": "Mozilla/5.0 (compatible; DoceCestaBot/1.0)"}


def _secret_base():
    try:
        return str(st.secrets.get("LINK_CURTO_BASE", "") or "").strip().rstrip("/")
    except Exception:
        return ""


def secret_configurado():
    return bool(_secret_base())


def _base():
    return _secret_base() or BASE_PADRAO


def codigo_do_pedido(pedido_id):
    """8 primeiros caracteres hexadecimais do UUID do pedido."""
    cod = re.sub(r"[^0-9a-fA-F]", "", str(pedido_id or ""))[:8].lower()
    return cod if len(cod) == 8 else ""


def link_curto_do_pedido(pedido_id):
    cod = codigo_do_pedido(pedido_id)
    if not cod:
        return ""
    base = _base()
    # domínio próprio: pagamento.docecestabrasilia.com.br/<codigo>  |  workers.dev: <base>/p/<codigo>
    return f"{base}/p/{cod}" if "workers.dev" in base else f"{base}/{cod}"


def diagnosticar(pedido_id, link_longo):
    """Consulta o link curto e explica, em português, o que aconteceu."""
    curto = link_curto_do_pedido(pedido_id)
    res = {"curto": curto, "base": _base(), "secret": secret_configurado(), "status": None, "location": "", "ok": False, "mensagem": ""}
    if not curto:
        res["mensagem"] = "Não foi possível montar o código do pedido (o ID do pedido não tem 8 caracteres hexadecimais)."
        return res
    try:
        r = requests.get(curto, allow_redirects=False, timeout=6, headers=_UA)
    except requests.exceptions.SSLError:
        res["mensagem"] = "Erro de certificado SSL. Se o domínio acabou de ser criado, aguarde alguns minutos."
        return res
    except requests.exceptions.ConnectionError:
        res["mensagem"] = "Não foi possível conectar. Confira se o domínio/DNS está ativo na Cloudflare e se o Worker foi publicado (npx wrangler deploy)."
        return res
    except requests.exceptions.Timeout:
        res["mensagem"] = "O Worker demorou demais para responder."
        return res
    except Exception as e:  # noqa: BLE001
        res["mensagem"] = f"Falha inesperada ao testar: {e}"
        return res

    res["status"] = r.status_code
    res["location"] = r.headers.get("Location", "")
    if r.status_code in (301, 302, 303, 307, 308):
        if res["location"].strip() == str(link_longo).strip():
            res["ok"] = True
            res["mensagem"] = "Link curto funcionando: redireciona para o link oficial da InfinitePay."
        else:
            res["mensagem"] = "O Worker redireciona para um endereço diferente do salvo neste pedido. Gere o link novamente."
    elif r.status_code == 200:
        res["ok"] = True
        res["mensagem"] = "Worker no ar (o pedido consta como pago)."
    elif r.status_code == 404:
        res["mensagem"] = "Worker no ar, mas não encontrou este pedido. Confira o DATABASE_URL do Worker (precisa ler a tabela pedidos) e se o link foi salvo."
    elif r.status_code in (403, 429, 503):
        res["mensagem"] = ("A Cloudflare bloqueou esta consulta feita pelo servidor (proteção contra robôs). "
                           "O link funciona para clientes em navegador; se quiser testar daqui, desative o 'Bot Fight Mode' ou crie uma regra de exceção.")
    elif r.status_code >= 500:
        res["mensagem"] = "O Worker respondeu com erro interno. Provavelmente não consegue acessar o banco: refaça 'npx wrangler secret put DATABASE_URL'."
    else:
        res["mensagem"] = f"Resposta inesperada do Worker (HTTP {r.status_code})."
    return res


@st.cache_data(ttl=120, show_spinner=False)
def _funciona(link_curto, link_longo, pedido_id):
    return diagnosticar(pedido_id, link_longo)["ok"]


def link_para_cliente(pedido_id, link_longo):
    """Link curto próprio. Se o secret LINK_CURTO_BASE existe, ele é SEMPRE usado (configuração explícita);
    sem o secret, só é usado quando o Worker confirma que está no ar."""
    if not link_longo:
        return link_longo
    curto = link_curto_do_pedido(pedido_id)
    if not curto:
        return link_longo
    if secret_configurado():
        return curto
    return curto if _funciona(curto, link_longo, str(pedido_id)) else link_longo
