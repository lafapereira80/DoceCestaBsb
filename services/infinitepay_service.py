import re
import requests
import streamlit as st

URL_API = "https://api.checkout.infinitepay.io/links"


def _secret(chave, padrao=""):
    try:
        return st.secrets.get(chave, padrao)
    except Exception:
        return padrao


def _formatar_telefone(telefone):
    """Normaliza para E.164 brasileiro (+55DDDNUMERO). Retorna '' se inválido."""
    digitos = re.sub(r"\D", "", str(telefone or ""))
    if not digitos:
        return ""
    if digitos.startswith("00"):
        digitos = digitos[2:]
    if digitos.startswith("55") and len(digitos) in (12, 13):
        return f"+{digitos}"
    if len(digitos) in (10, 11):
        return f"+55{digitos}"
    return ""


def _extrair_url(dados):
    """Procura a URL do checkout na resposta, em qualquer formato conhecido."""
    if isinstance(dados, str) and dados.startswith("http"):
        return dados
    if not isinstance(dados, dict):
        return None
    for chave in ("url", "checkout_url", "link", "payment_url", "invoice_url"):
        valor = dados.get(chave)
        if isinstance(valor, str) and valor.startswith("http"):
            return valor
    for chave in ("data", "link", "checkout", "result"):
        interno = dados.get(chave)
        if isinstance(interno, (dict, str)):
            achado = _extrair_url(interno)
            if achado:
                return achado
    return None


def gerar_link_checkout_infinitepay(pedido_id: str, valor_total: float, cliente_nome: str = "", cliente_tel: str = "", cliente_email: str = "", cliente_endereco: str = ""):
    """
    Gera o link de pagamento na InfinitePay (Checkout Integrado).

    - Retorna o link OFICIAL da InfinitePay (sem encurtadores de terceiros).
    - Webhook no formato atual: "webhook": {"url": ..., "events": [...]}
    - Autenticação por X-Api-Key quando INFINITEPAY_API_KEY existir nos secrets
      (opcional: sem ela, usa a handle).
    - Telefone normalizado em E.164 (+55...).
    - Se a API recusar o payload completo, tenta variações mais simples antes
      de desistir, para o cliente nunca ficar sem link por causa de um campo opcional.
    """
    try:
        handle = _secret("INFINITEPAY_HANDLE", "vanessa-hagen")
        webhook_url = _secret("INFINITEPAY_WEBHOOK", "https://infinitepay-webhook.lafapereira.workers.dev/")
        api_key = _secret("INFINITEPAY_API_KEY", "")
        redirect_url = _secret("INFINITEPAY_REDIRECT_URL", "")

        try:
            valor_total = float(valor_total or 0)
        except (TypeError, ValueError):
            valor_total = 0.0

        if valor_total < 1.00:
            st.warning("⚠️ O valor mínimo para gerar link é R$ 1,00.")
            return None

        valor_em_centavos = int(round(valor_total * 100))
        id_curto = str(pedido_id).split('-')[0].upper()

        email_final = str(cliente_email).strip() if cliente_email and "@" in str(cliente_email) else "docecestabrasilia@gmail.com"
        nome_limpo = str(cliente_nome or "").strip() or "Cliente DoceCesta"
        telefone = _formatar_telefone(cliente_tel)

        customer = {"name": nome_limpo[:100], "email": email_final}
        if telefone:
            customer["phone_number"] = telefone

        base = {
            "order_nsu": str(pedido_id),
            "items": [
                {
                    "quantity": 1,
                    "price": valor_em_centavos,
                    "description": f"Pedido #{id_curto} - Doce Cesta"
                }
            ],
        }
        base["handle"] = handle
        if redirect_url:
            base["redirect_url"] = redirect_url

        webhook_novo = {"webhook": {"url": webhook_url, "events": ["paid"]}}
        webhook_legado = {"webhook_url": webhook_url}

        # Variações, da mais completa para a mais simples.
        # webhook_url (formato oficial da API) vem SEMPRE primeiro; "sem webhook" é o último recurso.
        tentativas = [
            ({**base, **webhook_legado, "customer": customer}, True),
            ({**base, **webhook_legado}, True),
            ({**base, **webhook_legado, **webhook_novo, "customer": customer}, True),
            ({**base, "customer": customer}, False),
            ({**base}, False),
        ]

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        }
        if api_key:
            headers["X-Api-Key"] = str(api_key)

        ultimo_erro = ""
        for payload, com_webhook in tentativas:
            try:
                response = requests.post(URL_API, json=payload, headers=headers, timeout=15)
            except requests.RequestException as e:
                ultimo_erro = f"Falha de conexão: {e}"
                continue

            if response.status_code in (200, 201):
                try:
                    dados = response.json()
                except ValueError:
                    ultimo_erro = f"Resposta inválida da InfinitePay: {response.text[:300]}"
                    continue
                link_longo = _extrair_url(dados)
                if link_longo:
                    if not com_webhook:
                        st.warning("⚠️ Link gerado SEM aviso automático de pagamento. Use o botão '🔄 Verificar pagamento' ou marque como Pago manualmente.")
                    return link_longo
                ultimo_erro = f"Resposta sem link de checkout: {str(dados)[:300]}"
                continue

            ultimo_erro = f"Código {response.status_code}: {response.text[:300]}"
            # Erros de autenticação/permissão não se resolvem mudando o payload
            if response.status_code in (401, 403):
                break

        st.error(f"Erro da InfinitePay ({ultimo_erro})")
        return None

    except Exception as e:
        st.error(f"Falha ao gerar o link de pagamento: {e}")
        return None


def verificar_pagamento_infinitepay(pedido_id: str, transaction_nsu: str = "", slug: str = ""):
    """
    Consulta direto na InfinitePay (payment_check) se o pedido já foi pago.
    Retorna dict: {"pago": bool, "transaction_nsu": str, "erro": str}
    """
    handle = _secret("INFINITEPAY_HANDLE", "vanessa-hagen")
    corpo = {"handle": handle, "order_nsu": str(pedido_id)}
    if transaction_nsu:
        corpo["transaction_nsu"] = transaction_nsu
    if slug:
        corpo["slug"] = slug
    try:
        r = requests.post(
            "https://api.checkout.infinitepay.io/payment_check",
            json=corpo,
            headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
    except requests.RequestException as e:
        return {"pago": False, "transaction_nsu": "", "erro": f"Falha de conexão: {e}"}
    if r.status_code != 200:
        return {"pago": False, "transaction_nsu": "", "erro": f"HTTP {r.status_code}: {r.text[:200]}"}
    try:
        dados = r.json()
    except ValueError:
        return {"pago": False, "transaction_nsu": "", "erro": "Resposta inválida da InfinitePay"}
    d = dados.get("data", dados) if isinstance(dados, dict) else {}
    pago = d.get("paid") in (True, "true") or float(d.get("paid_amount") or 0) > 0
    return {"pago": bool(pago), "transaction_nsu": str(d.get("transaction_nsu") or transaction_nsu or ""), "erro": ""}
