import html
import streamlit as st
import pandas as pd
import re
import time
import uuid
import requests
import math
import urllib.parse
import json
from datetime import datetime, date, timezone, timedelta

from config.db import supabase
from services.cesta_service import listar_cestas, buscar_cesta
from services.configuracao_cesta_service import carregar_configuracao_cesta
from services.produto_service import listar_produtos_por_categoria_id
from services.foto_service import listar_fotos, deletar_foto, salvar_fotos
from services.pedido_adicional_service import listar_adicionais_pedido
from utils.menu import configurar_pagina, menu_lateral
from utils.permissao import administrador_operador
from services.email_service import enviar_email_cobranca, enviar_email_recibo

try:
    from services.infinitepay_service import gerar_link_checkout_infinitepay
except ImportError:
    gerar_link_checkout_infinitepay = None


def esc(valor, padrao='-'):
    """Escapa texto vindo do banco antes de inserir em blocos HTML (evita XSS/quebra de layout)."""
    texto = str(valor) if valor not in (None, '') else padrao
    return html.escape(texto)


# =====================================================
# FUNÇÕES DE FORMATAÇÃO LOCAL (substituem utils.formatacao)
# =====================================================
def formatar_moeda(valor):
    try:
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "0,00"

def tratar_preco(valor):
    """
    Converte string monetária brasileira ou float para float.
    Aceita formatos:
      - "1.234,56" (milhar com ponto e decimal com vírgula)
      - "1234,56"
      - "1234.56" (decimal com ponto)
      - "1234" (inteiro)
    """
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip().replace('R$', '').replace(' ', '')
    if not s:
        return 0.0

    # Se contém ambos '.' e ',', assume que '.' é milhar e ',' decimal
    if '.' in s and ',' in s:
        s = s.replace('.', '')   # remove milhar
        s = s.replace(',', '.')   # decimal
    # Se contém apenas ',' -> decimal
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except:
        return 0.0


def formatar_data_br(data_str):
    try:
        dt = datetime.strptime(str(data_str)[:10], "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except:
        return str(data_str) if data_str else ""

def gerar_link_wpp(telefone, mensagem):
    numero = re.sub(r'\D', '', str(telefone or ''))
    if not numero:
        return "#"
    return f"https://wa.me/{numero}?text={urllib.parse.quote(mensagem)}"

def gerar_resumo_whatsapp(cliente, destinatario, data, periodo, local, itens_str, subtotal, desconto, frete, total, pagamento, link_pagamento=None):
    msg = f"*RESUMO DO PEDIDO*\n\n"
    msg += f"👤 *Cliente:* {cliente}\n"
    msg += f"💝 *Para:* {destinatario}\n"
    msg += f"📅 *Entrega:* {data} ({periodo})\n"
    msg += f"📍 *Endereço:* {local}\n\n"
    msg += f"{itens_str}\n\n"
    msg += f"Subtotal: R$ {formatar_moeda(subtotal)}\n"
    if desconto:
        msg += f"Desconto: - R$ {formatar_moeda(desconto)}\n"
    msg += f"Frete: R$ {formatar_moeda(frete)}\n"
    msg += f"*TOTAL: R$ {formatar_moeda(total)}*\n"
    msg += f"Pagamento: {pagamento}\n"
    if link_pagamento:
        msg += f"\n🔗 {link_pagamento}"
    return msg


# =====================================================
# FUNÇÕES DE CÁLCULO INTELIGENTE DE FRETE (BLINDADAS)
# =====================================================
@st.cache_data(ttl=60, show_spinner=False)
def obter_configuracoes_loja():
    try:
        res = supabase.table("configuracoes_loja").select("*").eq("id", 1).execute()
        if res.data: return res.data[0]
    except: pass
    return {"cep_origem": "71680377", "valor_km": 1.0, "taxa_fixa": 3.0}

@st.cache_data(ttl=86400, show_spinner=False)
def obter_coordenadas_viacep_nominatim(cep_limpo):
    """Descobre as coordenadas exatas transformando CEP em Endereço via Correios primeiro"""
    try:
        res_viacep = requests.get(f"https://viacep.com.br/ws/{cep_limpo}/json/", timeout=4).json()
        if "erro" in res_viacep: return None, None
        
        logradouro = res_viacep.get("logradouro", "")
        bairro = res_viacep.get("bairro", "")
        localidade = res_viacep.get("localidade", "")
        uf = res_viacep.get("uf", "")
        
        headers = {"User-Agent": "DoceCestaAdminApp/2.0"}
        
        # Tentativa 1: Precisão total (Rua)
        if logradouro:
            q = urllib.parse.quote(f"{logradouro}, {localidade}, {uf}, Brazil")
            res = requests.get(f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1", headers=headers, timeout=4).json()
            if res: return float(res[0]["lon"]), float(res[0]["lat"])
        
        # Tentativa 2: Média (Bairro)
        if bairro:
            q = urllib.parse.quote(f"{bairro}, {localidade}, {uf}, Brazil")
            res = requests.get(f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1", headers=headers, timeout=4).json()
            if res: return float(res[0]["lon"]), float(res[0]["lat"])
            
        # Tentativa 3: Ampla (Cidade)
        q = urllib.parse.quote(f"{localidade}, {uf}, Brazil")
        res = requests.get(f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1", headers=headers, timeout=4).json()
        if res: return float(res[0]["lon"]), float(res[0]["lat"])

    except Exception:
        pass
    return None, None

@st.cache_data(ttl=86400, show_spinner=False)
def calcular_frete_por_cep(cep_destino_limpo):
    try:
        config_loja = obter_configuracoes_loja()
        cep_origem = config_loja.get("cep_origem", "71680377")
        valor_km = float(config_loja.get("valor_km", 1.0))
        taxa_fixa = float(config_loja.get("taxa_fixa", 3.0))

        if not cep_destino_limpo or len(cep_destino_limpo) != 8: return 0.0

        lon_o, lat_o = obter_coordenadas_viacep_nominatim(cep_origem)
        lon_d, lat_d = obter_coordenadas_viacep_nominatim(cep_destino_limpo)

        if not lon_o or not lon_d: return 0.0

        distancia_km = 0.0
        
        # Tenta OSRM (Rota de Carro Real pelas ruas)
        try:
            url_rota = f"http://router.project-osrm.org/route/v1/driving/{lon_o},{lat_o};{lon_d},{lat_d}?overview=false"
            res_rota = requests.get(url_rota, timeout=4).json()
            if res_rota.get("code") == "Ok":
                distancia_km = res_rota["routes"][0]["distance"] / 1000.0
        except Exception:
            pass
        
        # Salva-Vidas: Se a rota de carro falhar, calcula linha reta e adiciona 30% de margem
        if distancia_km == 0.0:
            R = 6371.0 # Raio da Terra
            dLat = math.radians(lat_d - lat_o)
            dLon = math.radians(lon_d - lon_o)
            a = math.sin(dLat/2)**2 + math.cos(math.radians(lat_o))*math.cos(math.radians(lat_d))*math.sin(dLon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            distancia_km = (R * c) * 1.3 
            
        return round(taxa_fixa + (distancia_km * valor_km), 2)
    except Exception:
        return 0.0


# =====================================================
# CONFIGURAÇÃO DA PÁGINA E CSS
# =====================================================
st.set_page_config(page_title="Detalhes do Pedido", page_icon="🔍", layout="wide")
configurar_pagina()
menu_lateral()
administrador_operador()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');

:root {
    --ink: #4a2e1b;
    --ink-strong: #2c1e14;
    --muted: #8c7362;
    --border: #e8ddd3;
    --brand: #c5721f;
    --ok: #137333;
    --ok-bg: #e6f4ea;
    --info: #1a73e8;
    --info-bg: #e8f0fe;
    --warn: #b06000;
    --warn-bg: #fef7e0;
    --purple: #6a1b9a;
    --purple-bg: #f3e8fd;
}

html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; color: var(--ink) !important; font-size: 14px !important; }
.block-container { padding-top: 1.5rem !important; padding-bottom: 4rem !important; max-width: 1200px !important; }

.order-header {
    background: linear-gradient(135deg, #ffffff 0%, #fdfbf8 100%);
    padding: 16px 20px; border-radius: 14px; border: 1px solid var(--border);
    box-shadow: 0 4px 14px rgba(90, 59, 40, 0.04); margin-bottom: 20px;
    display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;
}
.order-text { font-size: 14px; font-weight: 800; color: var(--ink); margin: 0; display: flex; align-items: center; gap: 8px; }

.order-type-badge {
    padding: 4px 9px; border-radius: 20px; font-size: 10.5px; font-weight: 800; border: 1px solid transparent;
    text-transform: uppercase; letter-spacing: .02em;
}
.order-type-badge.corp { background: var(--ok-bg); color: var(--ok); border-color: #ceead6; }
.order-type-badge.vitrine { background: var(--info-bg); color: var(--info); border-color: #d2e3fc; }
.order-type-badge:not(.corp):not(.vitrine) { background: var(--warn-bg); color: var(--warn); border-color: #fce8b2; }

.status-text { font-size: 14px; font-weight: 800; color: var(--brand); text-align: right; text-transform: uppercase; display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }

.info-card { background: #ffffff; border: 1px solid var(--border); border-radius: 14px; padding: 20px; box-shadow: 0 4px 14px rgba(90, 59, 40, 0.03); margin-bottom: 16px; height: 100%; transition: box-shadow .2s ease; }
.info-card:hover { box-shadow: 0 8px 22px rgba(90, 59, 40, 0.07); }
.card-title { font-size: 14px; font-weight: 800; color: var(--brand); margin-bottom: 12px; display: flex; align-items: center; gap: 6px; border-bottom: 1px dashed var(--border); padding-bottom: 6px; text-transform: uppercase; }

.data-label { font-size: 11.5px; color: var(--muted); font-weight: 700; text-transform: uppercase; margin-bottom: 2px; letter-spacing: .02em; }
.data-value { font-size: 14px; color: var(--ink-strong); font-weight: 600; margin-bottom: 12px; }
.item-pill { background: #faf7f3; border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; margin-bottom: 6px; font-size: 13.5px; font-weight: 600; color: var(--ink); }
.item-pill.discount { background: var(--warn-bg); border-color: #fce8b2; color: var(--warn); }

.resumo-financeiro { background: #fdfbf8; border: 1px solid var(--border); border-radius: 12px; padding: 16px; display: flex; justify-content: space-between; align-items: center; margin-top: 15px; margin-bottom: 15px; flex-wrap: wrap; gap: 10px; }
.resumo-item { text-align: center; }
.resumo-label { font-size: 11.5px; font-weight: 700; color: #775a46; text-transform: uppercase; letter-spacing: .02em; }
.resumo-valor { font-size: 15px; font-weight: 800; color: var(--ink); margin-top: 4px; }
.resumo-destaque { font-size: 16px; font-weight: 800; color: var(--ok); margin-top: 4px; }

.section-step { font-size: 14px; font-weight: 800; margin-bottom: 8px; margin-top: 15px; display: flex; align-items: center; gap: 8px; }
.step-num { width: 22px; height: 22px; border-radius: 50%; background: var(--brand); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 800; flex-shrink: 0; }

div[data-testid="stButton"] button { border-radius: 10px !important; font-weight: 800 !important; font-size: 13px !important; transition: all 0.2s ease !important; }
div[data-testid="stButton"] button:hover { transform: translateY(-1px); }
div[data-testid="stButton"] button[kind="primary"] { background: linear-gradient(135deg, #137333 0%, #0d4e22) !important; color: white !important; border: none !important; }
div[data-testid="stButton"] button[kind="primary"]:hover { box-shadow: 0 6px 16px rgba(19, 115, 51, .25); }
.btn-wpp > a { background: #25d366 !important; color: white !important; font-weight: 800 !important; font-size: 13px !important; border-radius: 10px !important; padding: 12px !important; display: flex; justify-content: center; align-items: center; text-decoration: none !important; transition: all .2s ease; }
.btn-wpp > a:hover { box-shadow: 0 6px 16px rgba(37, 211, 102, .3); transform: translateY(-1px); }
div[data-testid="stVerticalBlockBorderWrapper"] { background: #ffffff !important; border-radius: 14px !important; border: 1px solid var(--border) !important; padding: 18px !important; margin-bottom: 15px !important; }

/* =========================================
   RESPONSIVIDADE
========================================== */
@media (max-width: 1024px) {
    .info-card { padding: 16px; }
    .resumo-financeiro { justify-content: flex-start; gap: 18px; }
}

@media (max-width: 640px) {
    .block-container { padding-left: .8rem !important; padding-right: .8rem !important; padding-top: 1rem !important; }
    .order-header { padding: 12px 14px; flex-direction: column; align-items: flex-start; }
    .order-text { font-size: 13px; flex-wrap: wrap; }
    .status-text { text-align: left; justify-content: flex-start; width: 100%; }
    .info-card { padding: 14px; }
    .card-title { font-size: 12.5px; }
    .data-label { font-size: 10.5px; }
    .data-value { font-size: 13px; margin-bottom: 10px; }
    .item-pill { font-size: 12.5px; padding: 7px 10px; }
    .resumo-financeiro { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; padding: 14px; text-align: left; }
    .resumo-item { text-align: left; }
    .resumo-valor { font-size: 13.5px; }
    .resumo-destaque { font-size: 15px; }
    div[data-testid="stVerticalBlockBorderWrapper"] { padding: 14px !important; }
}
</style>
""", unsafe_allow_html=True)


def salvar_nota_interna(pid, key):
    nova_nota = st.session_state[key]
    try:
        supabase.table("pedidos").update({"anotacoes_internas": nova_nota}).eq("id", pid).execute()
        st.toast("✅ Anotação interna salva com sucesso!")
    except Exception as e:
        st.toast(f"❌ Erro ao salvar anotação: {e}", icon="⚠️")


pedido_id = st.session_state.get('pedido_detalhe_id')
if not pedido_id:
    st.warning("Nenhum pedido selecionado.")
    if st.button("⬅️ Voltar aos Pedidos"): st.switch_page("pages/02_Pedidos.py")
    st.stop()

def obter_detalhe(p_id):
    res = supabase.table("pedidos").select("*").eq("id", p_id).execute()
    return res.data[0] if res.data else None

pedido = obter_detalhe(pedido_id)
if not pedido: st.stop()

cliente_id = pedido.get('cliente_id')
email_cliente = pedido.get('cliente_email') or ""
if not email_cliente and cliente_id:
    try:
        res_cliente = supabase.table("clientes").select("email").eq("id", cliente_id).execute()
        if res_cliente.data and res_cliente.data[0].get("email"):
            email_cliente = res_cliente.data[0]["email"]
    except: pass

cliente_nome_banco = pedido.get('cliente_nome') or ''
is_b2b = "[B2B]" in cliente_nome_banco
is_vitrine = "[VITRINE]" in cliente_nome_banco
cliente_limpo = cliente_nome_banco.replace("[B2B]", "").replace("[VITRINE]", "").strip()
tipo_classe = "corp" if is_b2b else ("vitrine" if is_vitrine else "")
tipo_texto = "🏢 CORPORATIVO" if is_b2b else ("🌐 VITRINE" if is_vitrine else "🛍️ VAREJO")
id_curto = str(pedido['id']).split('-')[0].upper()

@st.cache_data(ttl=300, show_spinner=False)
def obter_cestas():
    try: return sorted([c for c in listar_cestas() if c.get("ativa", True)], key=lambda x: x.get("nome", ""))
    except: return []

@st.cache_data(ttl=300, show_spinner=False)
def obter_adicionais():
    try:
        cat_add = next((c for c in supabase.table("categorias").select("*").execute().data if c.get("nome", "").strip().lower() == "adicionais"), None)
        if cat_add: return sorted([p for p in listar_produtos_por_categoria_id(cat_add["id"]) if p.get("ativo", True)], key=lambda x: x.get("nome", ""))
        return []
    except: return []

@st.cache_data(ttl=300, show_spinner=False)
def carregar_config_cesta_cached(cesta_id):
    # Não engole a exceção: se engolir, o Streamlit CACHEIA o resultado
    # vazio por 300s e a cesta fica "sem itens" pra qualquer pedido que
    # use essa mesma cesta, escondendo o erro real. Deixa subir pra quem
    # chamou decidir o que mostrar.
    return carregar_configuracao_cesta(cesta_id)


def extrair_desconto(adicionais_str):
    vd = 0.0
    if not adicionais_str:
        return vd
    for linha in adicionais_str.split('\n'):
        if "desconto" in linha.lower():
            m = re.search(r'R\$\s*([\d.,]+)', linha)
            if m:
                try:
                    vd += tratar_preco(m.group(1))
                except:
                    pass
    return vd


vd_db = extrair_desconto(pedido.get('adicionais') or '')

total_db = tratar_preco(pedido.get('valor_total', 0))
frete_db = tratar_preco(pedido.get('valor_frete', 0))
subtotal_db = total_db + vd_db - frete_db
desc_perc_inicial = float(round((vd_db / subtotal_db) * 100, 2)) if subtotal_db > 0 else 0.0

endereco_str = str(pedido.get('endereco') or '')
cep_cliente = ""

match_cep = re.search(r'(?i)CEP:?\s*([\d\.-]+)', endereco_str)
if match_cep:
    cep_cliente = re.sub(r'\D', '', match_cep.group(1))
else:
    match_fallback = re.search(r'\b(\d{5}-?\d{3})\b', endereco_str)
    if match_fallback:
        cep_cliente = re.sub(r'\D', '', match_fallback.group(1))

sugestao_frete = 0.0
if cep_cliente and len(cep_cliente) == 8:
    sugestao_frete = calcular_frete_por_cep(cep_cliente)

valor_padrao_frete = frete_db if frete_db > 0 else sugestao_frete

if "modo_edicao" not in st.session_state: st.session_state.modo_edicao = False

def _preco_txt(txt):
    return tratar_preco(txt)

_PADRAO_ITEM = re.compile(r'^(\d+)x\s+(.+?)\s*\(R\$\s*([\d\.,]+)\)\s*$')

def montar_carrinho_edicao(pedido, subtotal_base):
    itens = []
    produtos_txt = pedido.get("produtos") or ""
    for bloco in [b.strip() for b in produtos_txt.split("\n\n") if b.strip()]:
        linhas = bloco.split("\n")
        m = _PADRAO_ITEM.match(linhas[0].strip())
        if m:
            qtd, nome, preco = m.groups()
            itens.append({
                "id": str(uuid.uuid4()), "tipo": "Cesta", "cesta_id": pedido.get("cesta_id"),
                "nome": nome.strip(), "preco_unitario": _preco_txt(preco), "quantidade": int(qtd),
                "descricao": "\n".join(linhas[1:]).strip()
            })
        else:
            itens.append({
                "id": str(uuid.uuid4()), "tipo": "Cesta", "cesta_id": pedido.get("cesta_id"),
                "nome": linhas[0].strip(), "preco_unitario": 0.0, "quantidade": 1,
                "descricao": "\n".join(linhas[1:]).strip()
            })

    try: extras_bd = listar_adicionais_pedido(pedido["id"]) or []
    except: extras_bd = []

    for ad in extras_bd:
        nome_ad = ad.get("nome_produto") or "Extra"
        itens.append({
            "id": str(uuid.uuid4()), "tipo": "Extra", "cesta_id": None,
            "produto_id": ad.get("produto_id"),
            "nome": nome_ad,
            "preco_unitario": tratar_preco(ad.get("valor_unitario") or 0), "quantidade": int(ad.get("quantidade") or 1), "descricao": ""
        })

    if not any(i["tipo"] == "Cesta" for i in itens):
        soma_extras = sum(i["preco_unitario"] * i["quantidade"] for i in itens if i["tipo"] == "Extra")
        preco_cesta_isolado = max(subtotal_base - soma_extras, 0.0)
        itens.insert(0, {
            "id": str(uuid.uuid4()), "tipo": "Cesta", "cesta_id": pedido.get("cesta_id"),
            "nome": pedido.get("cesta_nome") or "Cesta", "preco_unitario": preco_cesta_isolado,
            "quantidade": 1, "descricao": produtos_txt
        })
    return itens

if "foto_confirmar_exclusao" not in st.session_state: st.session_state["foto_confirmar_exclusao"] = None
if "mostrar_upload_polaroid" not in st.session_state: st.session_state["mostrar_upload_polaroid"] = False
if "edit_cart" not in st.session_state or st.session_state.get("edit_pedido_id") != pedido_id:
    st.session_state["edit_cart"] = montar_carrinho_edicao(pedido, subtotal_db)
    st.session_state["edit_pedido_id"] = pedido_id

STATUS_PERMITIDOS = ["Recebido", "Pago", "Em Montagem", "Pronto", "Enviado", "Em Rota de Entrega", "Entregue", "Desistência"]

# =====================================================
# CABEÇALHO COM A NOVA MÁQUINA DE ESTADOS VISUAIS
# =====================================================
c_head, c_btn = st.columns([4, 1], vertical_alignment="center")
with c_head:
    tx_id_topo = pedido.get("infinitepay_transaction_id")
    badge_infinite = '<span style="background: #111; color: #00ffaa; padding: 4px 8px; border-radius: 4px; font-size: 10px; font-weight: 800; margin-right: 6px; border: 1px solid #333;">♾️ INFINITEPAY</span>' if tx_id_topo else ''

    status_db = pedido.get('status') or 'Recebido'
    entregador = pedido.get('entregador_login')
    is_montada = pedido.get('cesta_montada', False)
    
    tickets_visuais = []

    if status_db == 'Em Montagem':
        tickets_visuais.append('<span style="background: #fdf7e3; color: #b06000; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 700; border: 1px solid #fce8b2; margin-right: 6px;">⚙️ MONTAGEM INICIADA</span>')
    elif status_db == 'Pronto' or is_montada:
        tickets_visuais.append('<span style="background: #e6f4ea; color: #137333; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 700; border: 1px solid #ceead6; margin-right: 6px;">✅ CESTA MONTADA</span>')

    if status_db == 'Entregue':
        tickets_visuais.append('<span style="background: #f3e8fd; color: #6a1b9a; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 700; border: 1px solid #e9d2fd; margin-right: 6px;">🎉 PEDIDO ENTREGUE</span>')
    elif status_db in ['Enviado', 'Em Rota de Entrega'] or (entregador and status_db not in ['Entregue', 'Desistência']):
        tickets_visuais.append('<span style="background: #e8f0fe; color: #1a73e8; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 700; border: 1px solid #d2e3fc; margin-right: 6px;">🛵 PARA ENTREGA (ROTA)</span>')

    tickets_str = "".join(tickets_visuais)

    st.markdown(f"""
    <div class="order-header">
        <div class="order-text">Pedido #{id_curto} <span class="order-type-badge {tipo_classe}">{tipo_texto}</span></div>
        <div class="status-text">{badge_infinite} {tickets_str}</div>
    </div>
    """, unsafe_allow_html=True)
with c_btn:
    if st.button("⬅️ Voltar ao Mural", use_container_width=True):
        st.session_state.modo_edicao = False
        st.switch_page("pages/02_Pedidos.py")

# =====================================================
# MODO DE VISUALIZAÇÃO E AJUSTES RÁPIDOS
# =====================================================
if not st.session_state.modo_edicao:
    col1, col2 = st.columns(2)
    with col1:
        html_info1 = f"""<div class="info-card">
            <div class="card-title">👤 Informações do Pedido</div>
            <div class="data-label">Cliente / Empresa</div><div class="data-value">{esc(cliente_limpo)} ({esc(pedido.get('cliente_telefone'))})</div>
            <div class="data-label">CPF / CNPJ</div><div class="data-value">{esc(pedido.get('cliente_cpf'))}</div>
            <div class="data-label">E-mail Cadastrado</div><div class="data-value">{esc(email_cliente, 'Não informado')}</div>
            <div class="data-label" style="margin-top:10px;">Recebedor (Destinatário)</div><div class="data-value">{esc(pedido.get('destinatario_nome'))} (Tel: {esc(pedido.get('destinatario_telefone') or 'Não informado')})</div>
            <div class="data-label">Ocasião / Motivo</div><div class="data-value">{esc(pedido.get('motivo_homenagem'))}</div>
            <div class="data-label" style="margin-top:10px;">Data e Período</div><div class="data-value">{esc(formatar_data_br(pedido.get('data_entrega')))} - {esc(pedido.get('periodo_entrega'))}</div>
            <div class="data-label">Endereço de Entrega</div><div class="data-value">{esc(pedido.get('endereco'))}</div>"""
        if (pedido.get('pedido_especial') or '').strip():
            html_info1 += f"""<div class="data-label" style="margin-top:15px; color:#5b21b6;">✨ Pedido Especial</div>
            <div style="background:#ede9fe; padding:10px; border-radius:8px; font-size:13px; color:#5b21b6; border-left:3px solid #5b21b6;">{esc(pedido.get('pedido_especial'))}</div>"""
        st.markdown(html_info1 + "</div>", unsafe_allow_html=True)

    with col2:
        html_info2 = """<div class="info-card"><div class="card-title">🎁 Detalhamento</div>"""
        try: cesta_info = buscar_cesta(pedido.get('cesta_id')) if pedido.get('cesta_id') else None
        except Exception: cesta_info = None

        nome_cesta_exibir = cesta_info.get('nome') if cesta_info else (pedido.get('cesta_nome') or '')
        if nome_cesta_exibir:
            html_info2 += f"<div class='data-label'>Cesta Comprada</div><div class='data-value'>🧺 {esc(nome_cesta_exibir)}</div>"
        if cesta_info and cesta_info.get('descricao'):
            html_info2 += f"<div style='background:#faf7f3; padding:8px 10px; border-radius:8px; font-size:12.5px; color:#5a3b28; margin-bottom:10px; border-left:3px solid #e8ddd3;'>{esc(cesta_info.get('descricao'))}</div>"

        produtos_brutos = pedido.get('produtos') or ''
        if produtos_brutos:
            for linha in produtos_brutos.split("\n"):
                if linha.strip(): 
                    if "x " in linha or ":" in linha:
                        html_info2 += f"<div class='item-pill'>📦 {esc(linha.strip())}</div>"
                    else:
                        html_info2 += f"<div class='item-pill' style='background: #fff; border-color: transparent; padding: 4px 12px; margin-bottom: 0;'>🔹 {esc(linha.strip())}</div>"

        itens_personalizados = None
        itens_consulta_str = pedido.get('itens_consulta')
        if itens_consulta_str:
            try:
                # O Supabase pode retornar jsonb já como dicionário
                if isinstance(itens_consulta_str, dict):
                    itens_personalizados = itens_consulta_str
                else:
                    itens_personalizados = json.loads(itens_consulta_str)
            except:
                itens_personalizados = None

        categorias_da_cesta = []
        erro_config_cesta = None
        if pedido.get('cesta_id'):
            try:
                categorias_da_cesta = carregar_config_cesta_cached(pedido.get('cesta_id')) or []
            except Exception as e:
                categorias_da_cesta = []
                erro_config_cesta = str(e)

        categorias_ja_exibidas = set()

        def _norm(txt):
            return (txt or "").strip().lower()

        mapa_itens_normalizado = {}
        if itens_personalizados:
            for k, v in itens_personalizados.items():
                mapa_itens_normalizado[_norm(k)] = v

        if categorias_da_cesta:
            for grupo in categorias_da_cesta:
                cat = grupo.get("categoria", "Categoria")
                categorias_ja_exibidas.add(_norm(cat))
                escolha = mapa_itens_normalizado.get(_norm(cat))
                
                nomes = ""
                if escolha:
                    if isinstance(escolha, list):
                        # Caso seja uma lista de dicionários ou lista de strings
                        nomes = ", ".join([p.get("nome", "") if isinstance(p, dict) else str(p) for p in escolha])
                    elif isinstance(escolha, dict):
                        nomes = escolha.get("nome", "")
                    else:
                        nomes = str(escolha)

                html_info2 += f"<div class='data-label' style='margin-top:10px;'>📦 {esc(cat)}</div>"
                if nomes:
                    html_info2 += f"<div class='item-pill'>🔹 {esc(nomes)}</div>"
                elif itens_personalizados:
                    html_info2 += "<div class='item-pill' style='opacity:.6;'>🔹 Não registrado neste pedido</div>"
                else:
                    html_info2 += "<div class='item-pill' style='opacity:.6; background:#fef2f2; border-color:#fecaca; color:#991b1b;'>🔹 Este pedido não tem nenhuma personalização salva</div>"

        if itens_personalizados:
            for categoria, produtos in itens_personalizados.items():
                if _norm(categoria) in categorias_ja_exibidas or not produtos:
                    continue
                nomes = ""
                if isinstance(produtos, list):
                    nomes = ", ".join([p.get("nome", "") if isinstance(p, dict) else str(p) for p in produtos])
                elif isinstance(produtos, dict):
                    nomes = produtos.get("nome", "")
                else:
                    nomes = str(produtos)
                    
                if nomes:
                    html_info2 += f"<div class='data-label' style='margin-top:10px;'>📦 {esc(categoria)}</div>"
                    html_info2 += f"<div class='item-pill'>🔹 {esc(nomes)}</div>"

        if erro_config_cesta:
            html_info2 += f"<div class='item-pill' style='background:#fef2f2; border-color:#fecaca; color:#991b1b;'>⚠️ Não foi possível carregar a configuração desta cesta ({esc(erro_config_cesta)}). Os itens abaixo podem estar incompletos.</div>"

        if not categorias_da_cesta and not itens_personalizados:
            for campo, rotulo, icone in [("pao", "Pães", "🍞"), ("espalhavel", "Espalháveis", "🧈"), ("bebida", "Bebidas", "🥤")]:
                valor_campo = pedido.get(campo)
                if valor_campo and valor_campo.strip():
                    html_info2 += f"<div class='data-label' style='margin-top:10px;'>{icone} {rotulo} escolhidos</div>"
                    html_info2 += f"<div class='item-pill'>🔹 {esc(valor_campo)}</div>"

        try: extras_valor = listar_adicionais_pedido(pedido["id"]) or []
        except Exception: extras_valor = []

        for extra in extras_valor:
            nome_extra = extra.get('nome_produto') or 'Extra'
            valor_unit = extra.get('valor_unitario')
            if valor_unit is None:
                valor_txt = "💬 Sob consulta"
            else:
                try: valor_txt = f"R$ {float(valor_unit):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                except: valor_txt = "💬 Sob consulta"
            html_info2 += f"<div class='item-pill'>✨ {esc(nome_extra)} — <b>{valor_txt}</b></div>"

        if vd_db > 0:
            html_info2 += f"<div class='item-pill discount'>🔻 Desconto: - R$ {formatar_moeda(vd_db)}</div>"

        codigo_cupom_detalhe = pedido.get("cupom_codigo")
        if codigo_cupom_detalhe:
            desconto_cupom_detalhe = tratar_preco(pedido.get("desconto_cupom", 0))
            nome_campanha = ""
            try:
                res_cupom_info = supabase.table("cupons").select("descricao").eq("codigo", codigo_cupom_detalhe).single().execute()
                nome_campanha = (res_cupom_info.data or {}).get("descricao") or ""
            except Exception:
                pass
            texto_campanha = f" — {esc(nome_campanha)}" if nome_campanha else ""
            html_info2 += f"<div class='data-label' style='margin-top:10px;'>🎟️ Cupom Utilizado</div>"
            html_info2 += f"<div class='item-pill' style='background:#f0fdf4; border-color:#bbf7d0; color:#166534;'>🎟️ {esc(codigo_cupom_detalhe)}{texto_campanha} (- R$ {formatar_moeda(desconto_cupom_detalhe)})</div>"

        mensagem_cartao_pedido = (pedido.get('mensagem') or '').strip()
        html_info2 += "<div class='data-label' style='margin-top: 15px;'>💌 Cartão de Presente</div>"
        if mensagem_cartao_pedido:
            html_info2 += f"""<div style='background:#fdfbf8; padding:10px; border-radius:8px; font-style:italic; font-size:13px; color:#4a2e1b; border-left:3px solid #c5721f;'>"{esc(mensagem_cartao_pedido)}"</div>"""
        else:
            html_info2 += """<div style='background:#f8fafc; padding:10px; border-radius:8px; font-size:13px; color:#94a3b8; border-left:3px solid #cbd5e1;'>O cliente não digitou nenhuma mensagem no cartão.</div>"""
        st.markdown(html_info2 + "</div>", unsafe_allow_html=True)

    fotos_pedido = listar_fotos(pedido_id)
    if not fotos_pedido and "FOTOS PENDENTES" in str(pedido.get('pedido_especial') or "").upper():
        st.warning("📷 **FOTOS PENDENTES (Polaroid):** o cliente escolheu **enviar as fotos depois pelo WhatsApp**. "
                   "Entre em contato com ele para pedir as fotos antes de montar a cesta.")
    if fotos_pedido:
        with st.container(border=True):
            st.markdown("<div class='card-title'>📷 Fotos Polaroid</div>", unsafe_allow_html=True)
            cols_fotos = st.columns(4)
            for i, foto in enumerate(fotos_pedido):
                with cols_fotos[i % 4]:
                    if foto.get("url"): st.image(foto["url"], use_container_width=True)
            st.caption("Para enviar ou excluir fotos, use '✏️ Editar Carrinho / Dados Completos'.")

    with st.container(border=True):
        st.markdown("<div style='font-size: 13px; font-weight: 800; color: #b06000; margin-bottom: 4px;'>⚠️ Anotações Internas</div>", unsafe_allow_html=True)
        st.text_area("Anotações Internas", value=pedido.get('anotacoes_internas') or '', height=80, key=f"nota_{pedido_id}", on_change=salvar_nota_interna, args=(pedido_id, f"nota_{pedido_id}"), label_visibility="collapsed")

    st.markdown("<div class='section-step'><span class='step-num'>⚡</span><span style='color:#137333;'>Resumo de Valores</span></div>", unsafe_allow_html=True)
    with st.container(border=True):
        # Substitui os valores fixos do banco pelos cálculos se o frete no banco estiver zerado
        novo_vd = vd_db
        novo_frete = valor_padrao_frete
        novo_total = subtotal_db - novo_vd + novo_frete

        st.markdown(f"**Status Atual:** {esc(status_db)}")

        codigo_cupom_pedido = pedido.get("cupom_codigo")
        desconto_cupom_pedido = tratar_preco(pedido.get("desconto_cupom", 0))

        linha_html_desconto = f'<div class="resumo-item"><div class="resumo-label">Desconto</div><div class="resumo-valor" style="color:#c5221f;">- R$ {formatar_moeda(novo_vd)}</div></div>' if novo_vd > 0 else ''
        linha_html_cupom = ''
        if codigo_cupom_pedido:
            linha_html_cupom = f'<div class="resumo-item"><div class="resumo-label">🎟️ Cupom aplicado</div><div class="resumo-valor" style="color:#16A34A;">{esc(codigo_cupom_pedido)}{f" (- R$ {formatar_moeda(desconto_cupom_pedido)})" if desconto_cupom_pedido > 0 else ""}</div></div>'
        html_resumo = f"""<div class="resumo-financeiro">
        <div class="resumo-item"><div class="resumo-label">Subtotal</div><div class="resumo-valor">R$ {formatar_moeda(subtotal_db)}</div></div>{linha_html_desconto}{linha_html_cupom}
        <div class="resumo-item"><div class="resumo-label">Frete</div><div class="resumo-valor">R$ {formatar_moeda(novo_frete)}</div></div>
        <div class="resumo-item"><div class="resumo-label">Pagamento</div><div class="resumo-valor">{esc(pedido.get('pagamento') or 'Pix')}</div></div>
        <div class="resumo-item"><div class="resumo-label">TOTAL FINAL</div><div class="resumo-destaque">R$ {formatar_moeda(novo_total)}</div></div></div>"""
        st.markdown(html_resumo.replace('\n', ''), unsafe_allow_html=True)
        st.caption("Para alterar frete, desconto ou forma de pagamento, use '✏️ Editar Carrinho / Dados Completos' abaixo.")

        if True:
            st.write("")
            link_pagamento_atual = pedido.get('infinitepay_url')

            def _gerar_e_salvar_link():
                if not gerar_link_checkout_infinitepay:
                    st.error("Serviço da InfinitePay indisponível.")
                    return
                with st.spinner("Gerando link de pagamento..."):
                    link_gerado = gerar_link_checkout_infinitepay(pedido_id=pedido_id, valor_total=novo_total, cliente_nome=cliente_limpo, cliente_tel=pedido.get('cliente_telefone') or '', cliente_email=email_cliente, cliente_endereco=pedido.get('endereco') or '')
                    if link_gerado:
                        supabase.table("pedidos").update({"infinitepay_url": link_gerado}).eq("id", pedido_id).execute()
                        st.success("✅ Link gerado!")
                        st.rerun()

            if link_pagamento_atual:
                st.success("🔗 **Link de Pagamento (InfinitePay):**")
                st.code(str(link_pagamento_atual), language=None)
                st.link_button("Abrir link de pagamento", str(link_pagamento_atual), use_container_width=True)
                if st.button("🔄 Gerar novo link de pagamento", key="regerar_link_pagamento", use_container_width=True):
                    _gerar_e_salvar_link()
            else:
                if st.button("💳 Gerar Link de Pagamento", use_container_width=True):
                    _gerar_e_salvar_link()

            tx_id = pedido.get("infinitepay_transaction_id")
            if tx_id:
                data_pagamento = pedido.get("data_pagamento")
                try:
                    dt_pg = datetime.fromisoformat(str(data_pagamento).replace("Z", "+00:00"))
                    if dt_pg.tzinfo is None:
                        dt_pg = dt_pg.replace(tzinfo=timezone.utc)
                    dt_pg_br = dt_pg.astimezone(timezone(timedelta(hours=-3)))
                    data_f = dt_pg_br.strftime("%d/%m/%Y às %H:%M:%S")
                except: data_f = str(data_pagamento)
                st.markdown(f"""
                <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:10px; padding:16px; margin:15px 0; display:flex; justify-content:space-between; flex-wrap:wrap; gap:10px;">
                    <div><div class="data-label" style="color:#166534;">💳 Pagamento</div><div class="data-value" style="color:#15803d; font-size:15px;">♾️ InfinitePay ({esc(tx_id)})</div></div>
                    <div><div class="data-label" style="color:#166534;">Horário da Aprovação</div><div class="data-value" style="color:#15803d; font-size:15px;">⏰ {esc(data_f)}</div></div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("<div class='section-step' style='color:#1E293B;'>📲 Notificar Cliente</div>", unsafe_allow_html=True)
            fone_cliente = re.sub(r'\D', '', pedido.get('cliente_telefone') or '')
            linhas_wpp = "\n".join([f"📦 {p.strip()}" for p in (pedido.get('produtos') or '').split('\n') if p.strip()]) or f"📦 {pedido.get('cesta_nome') or 'Itens do Pedido'}"
            
            for extra in extras_valor:
                linhas_wpp += f"\n🎀 {extra.get('nome_produto')} — R$ {formatar_moeda(extra.get('valor_unitario') or 0)}"

            if itens_personalizados:
                for cat, prods in itens_personalizados.items():
                    if prods:
                        nomes = ""
                        if isinstance(prods, list):
                            nomes = ", ".join([p.get("nome", "") if isinstance(p, dict) else str(p) for p in prods])
                        elif isinstance(prods, dict):
                            nomes = prods.get("nome", "")
                        else:
                            nomes = str(prods)
                        if nomes:
                            linhas_wpp += f"\n📦 {cat}: {nomes}"

            texto_resumo = gerar_resumo_whatsapp(
                cliente=cliente_limpo, destinatario=pedido.get('destinatario_nome') or 'O mesmo',
                data=formatar_data_br(pedido.get('data_entrega')), periodo=pedido.get('periodo_entrega') or 'A combinar',
                local=pedido.get('endereco') or 'Não informado', itens_str=linhas_wpp,
                subtotal=subtotal_db, desconto=vd_db, frete=novo_frete, total=novo_total,
                pagamento=pedido.get('pagamento') or 'Pix', link_pagamento=link_pagamento_atual
            )

            with st.container(border=True):
                c_wpp, c_mail = st.columns(2)
                with c_wpp:
                    link_wpp = gerar_link_wpp(fone_cliente, texto_resumo)
                    if fone_cliente: st.markdown(f'<div class="btn-wpp"><a href="{link_wpp}" target="_blank">💬 Enviar Resumo (WhatsApp)</a></div>', unsafe_allow_html=True)
                    else: st.warning("Sem telefone cadastrado.")
                with c_mail:
                    e_col1, e_col2 = st.columns([2, 1])
                    with e_col1: email_input = st.text_input("E-mail", value=email_cliente, placeholder="cliente@email.com", label_visibility="collapsed", key=f"email_dest_{pedido_id}")
                    with e_col2:
                        if st.button("✉️ Disparar E-mail", use_container_width=True):
                            if email_input:
                                resumo_texto_email = linhas_wpp
                                sucesso, msg_retorno = enviar_email_cobranca(
                                    email_input,
                                    cliente_limpo,
                                    id_curto,
                                    resumo_texto_email,
                                    link_pagamento_atual
                                )
                                if sucesso:
                                    st.success(msg_retorno)
                                    if email_input.strip() != email_cliente:
                                        try:
                                            supabase.table("pedidos").update({"cliente_email": email_input.strip()}).eq("id", pedido_id).execute()
                                            if cliente_id:
                                                supabase.table("clientes").update({"email": email_input.strip()}).eq("id", cliente_id).execute()
                                        except Exception as e:
                                            st.toast(f"⚠️ E-mail enviado, mas não foi possível atualizar no cadastro: {e}")
                                else:
                                    st.error(f"Erro ao enviar e-mail: {msg_retorno}")
                            else:
                                st.warning("⚠️ Digite um e-mail.")

            # ===== SEÇÃO DE RECIBO =====
            if status_db in ['Pago', 'Enviado', 'Em Rota de Entrega', 'Entregue'] and email_cliente:
                with st.container(border=True):
                    st.markdown("<div class='card-title'>🧾 Recibo de Pagamento</div>", unsafe_allow_html=True)

                    if tx_id_topo:
                        if st.button("📧 Enviar Recibo por E-mail", use_container_width=True):
                            itens_detalhados = []
                            cesta_nome = pedido.get('cesta_nome') or 'Cesta'
                            extras_bd = listar_adicionais_pedido(pedido_id) or []
                            total_extras = sum(tratar_preco(extra.get('valor_unitario')) for extra in extras_bd)
                            frete_valor = novo_frete
                            valor_cesta = max(novo_total - total_extras - frete_valor, 0)
                            itens_detalhados.append({"nome": cesta_nome, "valor": valor_cesta})
                            for extra in extras_bd:
                                itens_detalhados.append({
                                    "nome": extra.get('nome_produto') or 'Extra',
                                    "valor": tratar_preco(extra.get('valor_unitario') or 0)
                                })
                            if frete_valor > 0:
                                itens_detalhados.append({"nome": "Frete", "valor": frete_valor})
                            if not itens_detalhados:
                                itens_detalhados.append({"nome": "Total do Pedido", "valor": novo_total})

                            resumo_recibo = {
                                "cesta_nome": cesta_nome,
                                "destinatario_nome": pedido.get('destinatario_nome', ''),
                                "data_entrega": pedido.get('data_entrega', ''),
                                "periodo_entrega": pedido.get('periodo_entrega', ''),
                                "endereco": pedido.get('endereco', ''),
                                "valor_total": f"R$ {novo_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                            }

                            data_pg_str = formatar_data_br(pedido.get('data_pagamento')) if pedido.get('data_pagamento') else 'Data não informada'
                            dados_pagamento = {
                                "transaction_id": tx_id_topo,
                                "data_pagamento": data_pg_str,
                                "forma_pagamento": 'InfinitePay',
                                "valor_pago": resumo_recibo["valor_total"],
                                "status": 'Aprovado'
                            }

                            sucesso, msg = enviar_email_recibo(
                                email_cliente,
                                cliente_limpo,
                                id_curto,
                                resumo_recibo,
                                dados_pagamento,
                                itens_detalhados
                            )
                            if sucesso:
                                st.success(msg)
                            else:
                                st.error(msg)
                    else:
                        st.write("Envie o recibo detalhado com todos os itens e valores para o e-mail do cliente.")
                        
                        if "data_pg" not in st.session_state or st.session_state.get("pedido_id_pg") != pedido_id:
                            data_pg_raw = pedido.get('data_pagamento')
                            if data_pg_raw:
                                try:
                                    dt_pg = datetime.fromisoformat(str(data_pg_raw).replace('Z', '+00:00'))
                                    dt_pg = dt_pg.astimezone(timezone(timedelta(hours=-3)))
                                    dt_pg = dt_pg.replace(tzinfo=None)
                                except:
                                    dt_pg = datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)
                            else:
                                dt_pg = datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)
                            st.session_state["data_pg"] = dt_pg
                            st.session_state["pedido_id_pg"] = pedido_id

                        col_data_pg, col_hora_pg = st.columns(2)
                        with col_data_pg:
                            data_pg = st.date_input("Data do pagamento", value=st.session_state["data_pg"].date(), format="DD/MM/YYYY", key="input_data_pg")
                        with col_hora_pg:
                            hora_pg = st.time_input("Hora do pagamento", value=st.session_state["data_pg"].time(), key="input_hora_pg")

                        if st.button("📧 Enviar Recibo por E-mail", use_container_width=True):
                            itens_detalhados = []
                            cesta_nome = pedido.get('cesta_nome') or 'Cesta'
                            extras_bd = listar_adicionais_pedido(pedido_id) or []
                            total_extras = sum(tratar_preco(extra.get('valor_unitario')) for extra in extras_bd)
                            frete_valor = novo_frete
                            valor_cesta = max(novo_total - total_extras - frete_valor, 0)
                            itens_detalhados.append({"nome": cesta_nome, "valor": valor_cesta})
                            for extra in extras_bd:
                                itens_detalhados.append({
                                    "nome": extra.get('nome_produto') or 'Extra',
                                    "valor": tratar_preco(extra.get('valor_unitario') or 0)
                                })
                            if frete_valor > 0:
                                itens_detalhados.append({"nome": "Frete", "valor": frete_valor})
                            if not itens_detalhados:
                                itens_detalhados.append({"nome": "Total do Pedido", "valor": novo_total})

                            data_pg_formatada = datetime.combine(data_pg, hora_pg)
                            data_pg_str = data_pg_formatada.strftime("%d/%m/%Y %H:%M")

                            resumo_recibo = {
                                "cesta_nome": cesta_nome,
                                "destinatario_nome": pedido.get('destinatario_nome', ''),
                                "data_entrega": pedido.get('data_entrega', ''),
                                "periodo_entrega": pedido.get('periodo_entrega', ''),
                                "endereco": pedido.get('endereco', ''),
                                "valor_total": f"R$ {novo_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                            }
                            dados_pagamento = {
                                "transaction_id": "Pagamento manual",
                                "data_pagamento": data_pg_str,
                                "forma_pagamento": 'Manual',
                                "valor_pago": resumo_recibo["valor_total"],
                                "status": 'Confirmado'
                            }

                            try:
                                supabase.table("pedidos").update({"data_pagamento": data_pg_formatada.isoformat()}).eq("id", pedido_id).execute()
                                st.session_state["data_pg"] = data_pg_formatada
                            except Exception as e:
                                st.warning(f"Recibo enviado, mas não foi possível atualizar a data do pagamento: {e}")

                            sucesso, msg = enviar_email_recibo(
                                email_cliente,
                                cliente_limpo,
                                id_curto,
                                resumo_recibo,
                                dados_pagamento,
                                itens_detalhados
                            )
                            if sucesso:
                                st.success(msg)
                            else:
                                st.error(msg)

            st.write("")
            if st.button("✏️ Editar Carrinho / Dados Completos", use_container_width=True):
                st.session_state.modo_edicao = True
                st.rerun()

# =====================================================
# MODO EDIÇÃO (EDIÇÃO PROFUNDA - CARRINHO E COMPRADOR)
# =====================================================
else:
    st.info("✏️ **Modo de Edição Profunda Ativado.** Altere os dados abaixo e clique em Salvar.")
    with st.container(border=True):
        st.markdown("<div class='card-title'>👤 1. DADOS DO COMPRADOR</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: e_nome = st.text_input("Nome Comprador", value=pedido.get('cliente_nome') or '')
        with c2: e_tel = st.text_input("WhatsApp", value=pedido.get('cliente_telefone') or '')
        c3, c4 = st.columns(2)
        with c3: e_cpf = st.text_input("CPF / CNPJ", value=pedido.get('cliente_cpf') or '')
        with c4: e_email = st.text_input("E-mail", value=email_cliente)

    with st.container(border=True):
        st.markdown("<div class='card-title'>💌 2. DESTINATÁRIO, ENTREGA E CARTÃO</div>", unsafe_allow_html=True)
        c4, c5, c6 = st.columns(3)
        with c4: e_dest = st.text_input("Nome Destinatário", value=pedido.get('destinatario_nome') or '')
        with c5: e_dtel = st.text_input("Tel Destinatário", value=pedido.get('destinatario_telefone') or '')
        with c6: e_motivo = st.text_input("Motivo/Ocasião", value=pedido.get('motivo_homenagem') or '')
        e_end = st.text_area("Endereço Completo", value=pedido.get('endereco') or '', height=70)
        try: dt_obj = datetime.strptime(str(pedido.get('data_entrega'))[:10], "%Y-%m-%d").date()
        except: dt_obj = date.today()
        c7, c8 = st.columns(2)
        with c7: e_data = st.date_input("Data de Entrega", value=dt_obj, format="DD/MM/YYYY")
        with c8: e_per = st.text_input("Período/Horário", value=pedido.get('periodo_entrega') or '')
        c9, c10 = st.columns(2)
        with c9: 
            e_msg = st.text_area("Mensagem do Cartão", value=pedido.get('mensagem') or '', height=70)
            e_pedido_especial = st.text_area("Pedido Especial", value=pedido.get('pedido_especial') or '', height=70)
        with c10: 
            e_anotacoes = st.text_area("Anotações Internas", value=pedido.get('anotacoes_internas') or '', height=185)

    # =====================================================
    # PRODUTOS E EXTRAS (FECHAMENTO)
    # =====================================================
    with st.container(border=True):
        st.markdown("<div class='card-title'>🎁 PRODUTOS E EXTRAS (FECHAMENTO)</div>", unsafe_allow_html=True)
        col_add1, col_add2, col_add3 = st.columns(3)
        cestas_disponiveis, adicionais_disponiveis = obter_cestas(), obter_adicionais()
        with col_add1:
            cesta_sel = st.selectbox("Nova Cesta", [None] + cestas_disponiveis, format_func=lambda x: x["nome"] if x else "Selecione...")
            if st.button("➕ Inserir Cesta", use_container_width=True) and cesta_sel:
                st.session_state["edit_cart"].append({"id": str(uuid.uuid4()), "tipo": "Cesta", "cesta_id": cesta_sel["id"], "nome": cesta_sel["nome"], "preco_unitario": tratar_preco(cesta_sel.get("preco")), "quantidade": 1, "descricao": ""})
                st.rerun()
        with col_add2:
            adc_sel = st.selectbox("Extra do Catálogo", [None] + adicionais_disponiveis, format_func=lambda x: x["nome"] if x else "Selecione...")

            eh_polaroid = adc_sel and "polaroid" in str(adc_sel.get("nome", "")).lower()
            fotos_polaroid_edicao = None
            if eh_polaroid:
                fotos_polaroid_edicao = st.file_uploader(
                    "📷 Fotos para o Polaroid (envia direto pro bucket)",
                    type=["jpg", "jpeg", "png", "webp", "heic"],
                    accept_multiple_files=True, key="upload_polaroid_edicao_pedido"
                )

            if st.button("➕ Inserir Extra", use_container_width=True) and adc_sel:
                novo_item = {
                    "id": str(uuid.uuid4()), "tipo": "Extra", "cesta_id": None,
                    "produto_id": adc_sel["id"],
                    "nome": adc_sel["nome"], "preco_unitario": tratar_preco(adc_sel.get("preco")),
                    "quantidade": 1, "descricao": ""
                }
                st.session_state["edit_cart"].append(novo_item)
                if eh_polaroid and fotos_polaroid_edicao:
                    with st.spinner("📦 Enviando fotos para o bucket..."):
                        ok_fotos, msg_fotos = salvar_fotos(pedido_id, fotos_polaroid_edicao[:2])
                    if ok_fotos:
                        st.toast(f"📷 {len(fotos_polaroid_edicao[:2])} foto(s) enviada(s) ao bucket!")
                    else:
                        st.error(f"Extra adicionado, mas houve falha ao enviar as fotos: {msg_fotos}")
                st.rerun()
        with col_add3:
            txt_man = st.text_input("Extra Manual", placeholder="Ex: Vinho Personalizado")
            if st.button("➕ Inserir Manual", use_container_width=True) and txt_man.strip():
                st.session_state["edit_cart"].append({"id": str(uuid.uuid4()), "tipo": "Extra", "cesta_id": None, "produto_id": None, "nome": txt_man.strip(), "preco_unitario": 0.0, "quantidade": 1, "descricao": ""})
                st.rerun()

        total_bruto = 0
        if st.session_state["edit_cart"]:
            st.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)
            for i, item in enumerate(st.session_state["edit_cart"]):
                c1, c2, c3, c4, c5 = st.columns([3.5, 1.5, 1.5, 1.5, 0.5])
                with c1: st.markdown(f"**{esc(item['nome'])}**")
                with c2: n_preco = st.number_input("V", value=float(item["preco_unitario"]), key=f"e_p_{item['id']}", label_visibility="collapsed")
                with c3: n_qtd = st.number_input("Q", value=int(item["quantidade"]), min_value=1, key=f"e_q_{item['id']}", label_visibility="collapsed")
                with c4:
                    st.session_state["edit_cart"][i]["preco_unitario"] = n_preco
                    st.session_state["edit_cart"][i]["quantidade"] = n_qtd
                    sub_linha = n_preco * n_qtd
                    total_bruto += sub_linha
                    st.markdown(f"**R$ {formatar_moeda(sub_linha)}**")
                with c5:
                    if st.button("🗑️", key=f"e_d_{item['id']}"):
                        st.session_state["edit_cart"].pop(i)
                        st.rerun()

    # =====================================================
    # PERSONALIZAÇÃO DA CESTA (CORRIGIDO PARA CARREGAR OS DADOS SALVOS)
    # =====================================================
    with st.container(border=True):
        st.markdown("<div class='card-title'>🍓 PERSONALIZAÇÃO DA CESTA (ESCOLHAS DO CLIENTE)</div>", unsafe_allow_html=True)

        cesta_atual_id = None
        for item in st.session_state["edit_cart"]:
            if item["tipo"] == "Cesta":
                cesta_atual_id = item.get("cesta_id")
                break

        if cesta_atual_id:
            configuracao = carregar_config_cesta_cached(cesta_atual_id)
        else:
            configuracao = []

        if configuracao:
            # Recupera as escolhas salvas corretamente do banco (suporta itens_consulta ou colunas legadas pao/espalhavel/bebida)
            itens_atuais = {}
            itens_consulta_str = pedido.get('itens_consulta')
            if itens_consulta_str:
                try:
                    if isinstance(itens_consulta_str, dict):
                        itens_atuais = itens_consulta_str
                    else:
                        itens_atuais = json.loads(itens_consulta_str)
                except:
                    itens_atuais = {}
            
            # Se itens_consulta estiver vazio, tenta montar o dicionário a partir das colunas legadas do pedido
            if not itens_atuais:
                for grupo in configuracao:
                    cat = grupo.get("categoria", "Categoria")
                    cat_lower = cat.lower()
                    val_legado = ""
                    if "pão" in cat_lower or "pao" in cat_lower:
                        val_legado = pedido.get('pao') or ""
                    elif "espalhav" in cat_lower or "espalháv" in cat_lower:
                        val_legado = pedido.get('espalhavel') or ""
                    elif "bebida" in cat_lower:
                        val_legado = pedido.get('bebida') or ""
                    
                    if val_legado:
                        # Separa por vírgula caso tenha múltiplos itens salvos em string simples
                        nomes_legados = [n.strip() for n in val_legado.split(",") if n.strip()]
                        itens_atuais[cat] = [{"nome": n} for n in nomes_legados]

            selecoes_edit = {}
            categorias_configuracao_atual = set()

            for grupo in configuracao:
                cat = grupo.get("categoria", "Categoria")
                prods = grupo.get("produtos", [])
                maximo = grupo.get("max_escolhas", 1)
                categorias_configuracao_atual.add(cat)

                if not prods:
                    # Categoria existe na configuração atual da cesta, mas sem
                    # nenhum produto ativo pra oferecer (ex: todos foram
                    # desativados depois da compra). Preserva a escolha
                    # histórica sem tornar editável, pra não apagar o dado.
                    if itens_atuais.get(cat):
                        selecoes_edit[cat] = itens_atuais[cat]
                        nomes_hist = ", ".join([p.get("nome", "") for p in itens_atuais[cat]])
                        st.markdown(f"**{cat}**")
                        st.caption(f"🔒 {nomes_hist} — produto não está mais disponível para edição, mas foi preservado do pedido original.")
                    continue

                prods_atuais = itens_atuais.get(cat, [])
                # Coleta tanto IDs salvos (se houver) quanto os nomes salvos para fazer o match cruzado
                ids_selecionados = [p.get("id") for p in prods_atuais if isinstance(p, dict) and p.get("id")]
                nomes_selecionados = [str(p.get("nome", "")).strip().lower() for p in prods_atuais if isinstance(p, dict) and p.get("nome")]
                
                # Suporte para itens_consulta salvo como lista de strings (versões antigas)
                if prods_atuais and isinstance(prods_atuais[0], str):
                   nomes_selecionados = [str(p).strip().lower() for p in prods_atuais]

                st.markdown(f"**{cat}**")
                
                opcoes = {p["id"]: p["nome"] for p in prods}
                
                if maximo == 1:
                    default_id = None
                    # Tenta encontrar primeiro por ID correspondente
                    for pid in opcoes.keys():
                        if pid in ids_selecionados:
                            default_id = pid
                            break
                    # Se não achou por ID, tenta encontrar pelo nome correspondente
                    if not default_id and nomes_selecionados:
                        for pid, pnome in opcoes.items():
                            if pnome.strip().lower() in nomes_selecionados:
                                default_id = pid
                                break
                    # Se ainda não achou, pega o primeiro da lista
                    if not default_id and prods:
                        default_id = prods[0]["id"]

                    idx_escolha = 0
                    if default_id and default_id in list(opcoes.keys()):
                        idx_escolha = list(opcoes.keys()).index(default_id)

                    escolha_id = st.radio(
                        f"Escolha 1 opção para {cat}",
                        options=list(opcoes.keys()),
                        format_func=lambda x: opcoes[x],
                        index=idx_escolha,
                        key=f"edit_radio_{cesta_atual_id}_{cat}"
                    )
                    selecoes_edit[cat] = [{"id": escolha_id, "nome": opcoes[escolha_id]}]
                else:
                    default_ids = []
                    for pid, pnome in opcoes.items():
                        if pid in ids_selecionados or pnome.strip().lower() in nomes_selecionados:
                            default_ids.append(pid)

                    escolhas_ids = st.multiselect(
                        f"Escolha até {maximo} opções para {cat}",
                        options=list(opcoes.keys()),
                        format_func=lambda x: opcoes[x],
                        default=default_ids,
                        max_selections=maximo,
                        key=f"edit_multi_{cesta_atual_id}_{cat}"
                    )
                    selecoes_edit[cat] = [{"id": pid, "nome": opcoes[pid]} for pid in escolhas_ids]

            # Preserva categorias que existiam no pedido original mas que não
            # existem mais na configuração atual da cesta (categoria renomeada
            # ou removida do cadastro) — sem isso, salvar o pedido apagava
            # silenciosamente esses itens do histórico do cliente.
            for cat_hist, produtos_hist in itens_atuais.items():
                if cat_hist not in categorias_configuracao_atual and produtos_hist:
                    selecoes_edit[cat_hist] = produtos_hist
                    if isinstance(produtos_hist, list):
                        nomes_hist = ", ".join([p.get("nome", "") if isinstance(p, dict) else str(p) for p in produtos_hist])
                    elif isinstance(produtos_hist, dict):
                        nomes_hist = produtos_hist.get("nome", "")
                    else:
                        nomes_hist = str(produtos_hist)
                    st.markdown(f"**{cat_hist}** ⚠️ *(categoria alterada/removida do cadastro atual)*")
                    st.caption(f"🔒 {nomes_hist} — preservado do pedido original, não editável aqui.")

            st.session_state["edit_personalizacoes"] = selecoes_edit
        else:
            st.info("Esta cesta não possui itens personalizáveis configurados.")
            st.session_state["edit_personalizacoes"] = {}

    # =====================================================
    # FOTOS POLAROID
    # =====================================================
    with st.container(border=True):
        st.markdown("<div class='card-title'>📷 FOTOS POLAROID</div>", unsafe_allow_html=True)
        fotos_pedido_edicao = listar_fotos(pedido_id)
        if fotos_pedido_edicao:
            cols_fotos_ed = st.columns(4)
            for i, foto in enumerate(fotos_pedido_edicao):
                with cols_fotos_ed[i % 4]:
                    if foto.get("url"):
                        st.image(foto["url"], use_container_width=True)

                    if st.session_state.get("foto_confirmar_exclusao") == foto["id"]:
                        st.caption("⚠️ Excluir do bucket?")
                        cfc1, cfc2 = st.columns(2)
                        with cfc1:
                            if st.button("✅", key=f"conf_del_foto_ed_{foto['id']}", use_container_width=True, help="Confirmar exclusão"):
                                sucesso, msg = deletar_foto(foto["id"], foto.get("arquivo"))
                                if sucesso:
                                    st.session_state["foto_confirmar_exclusao"] = None
                                    st.toast("🗑️ Foto excluída do bucket.")
                                    st.rerun()
                                else:
                                    st.error(msg)
                        with cfc2:
                            if st.button("❌", key=f"canc_del_foto_ed_{foto['id']}", use_container_width=True, help="Cancelar"):
                                st.session_state["foto_confirmar_exclusao"] = None
                                st.rerun()
                    else:
                        if st.button("🗑️ Excluir Foto", key=f"del_foto_ed_{foto['id']}", use_container_width=True):
                            st.session_state["foto_confirmar_exclusao"] = foto["id"]
                            st.rerun()
        else:
            st.caption("Nenhuma foto enviada para este pedido ainda.")

        st.write("")
        novas_fotos_edicao = st.file_uploader(
            "Enviar novas fotos para o bucket (pedido_fotos)",
            type=["jpg", "jpeg", "png", "webp", "heic"],
            accept_multiple_files=True, key=f"upload_fotos_edicao_{pedido_id}"
        )
        if st.button("📤 Enviar Fotos ao Bucket", use_container_width=True, disabled=not novas_fotos_edicao):
            with st.spinner("Enviando fotos..."):
                ok_fotos, msg_fotos = salvar_fotos(pedido_id, novas_fotos_edicao)
            if ok_fotos:
                st.toast(f"📷 {len(novas_fotos_edicao)} foto(s) enviada(s) com sucesso!")
                st.rerun()
            else:
                st.error(f"Falha ao enviar as fotos: {msg_fotos}")

    # =====================================================
    # PARTE FINANCEIRA
    # =====================================================
    with st.container(border=True):
        st.markdown("<div class='card-title'>💰 FECHAMENTO FINANCEIRO</div>", unsafe_allow_html=True)
        c_f1, c_f2, c_f3 = st.columns(3)
        with c_f1: e_frete = st.number_input("Frete / Taxa (R$)", min_value=0.0, step=5.0, value=float(valor_padrao_frete))
        with c_f2: e_desc = st.number_input("Desconto (%)", min_value=0.0, max_value=100.0, step=1.0, value=desc_perc_inicial)
        with c_f3: e_pag = st.selectbox("Pagamento Edit", ["Pix", "Cartão de Crédito", "Faturamento", "Transferência"], index=["Pix", "Cartão de Crédito", "Faturamento", "Transferência"].index(pedido.get('pagamento') or 'Pix') if pedido.get('pagamento') in ["Pix", "Cartão de Crédito", "Faturamento", "Transferência"] else 0)

        st.markdown(f"**Status Atual:** {esc(pedido.get('status') or 'Recebido')}")

        valor_desconto = total_bruto * (e_desc / 100)
        total_liquido = total_bruto - valor_desconto + e_frete
        st.markdown(f"<div class='resumo-financeiro'><div class='resumo-item'>TOTAL FINAL</div><div class='resumo-destaque'>R$ {formatar_moeda(total_liquido)}</div></div>", unsafe_allow_html=True)

    # =====================================================
    # BOTÕES DE SALVAR E CANCELAR
    # =====================================================
    st.write("")
    c_save1, c_save2 = st.columns(2)
    with c_save1:
        if st.button("💾 SALVAR ALTERAÇÕES COMPLETAS", type="primary", use_container_width=True):
            if not st.session_state["edit_cart"]: st.error("Carrinho vazio."); st.stop()
            
            lista_cestas = [it for it in st.session_state["edit_cart"] if it["tipo"] == "Cesta"]
            lista_extras = [it for it in st.session_state["edit_cart"] if it["tipo"] == "Extra"]
            
            str_prod = [f"{it['quantidade']}x {it['nome']} (R$ {formatar_moeda(it['preco_unitario'])})" for it in lista_cestas]
            str_ext = [f"{it['quantidade']}x {it['nome']} (R$ {formatar_moeda(it['preco_unitario'])})" for it in lista_extras]
            
            n_cesta = lista_cestas[0]["nome"] if lista_cestas else "Pedido Editado"
            id_cesta = lista_cestas[0]["cesta_id"] if lista_cestas else None
            
            msg_add = ""
            if valor_desconto > 0:
                msg_add += f"Desconto: - R$ {formatar_moeda(valor_desconto)}\n"
            if str_ext:
                msg_add += "\nEXTRAS E ADICIONAIS:\n" + "\n".join(str_ext)

            selecoes_personalizacao = st.session_state.get("edit_personalizacoes", {})
            
            pao_novo = ""
            espalhavel_novo = ""
            bebida_novo = ""
            for cat, lista in selecoes_personalizacao.items():
                nomes = ", ".join([p["nome"] for p in lista])
                cat_norm = cat.lower()
                if "pão" in cat_norm or "pao" in cat_norm:
                    pao_novo = nomes
                elif "espalhav" in cat_norm or "espalháv" in cat_norm:
                    espalhavel_novo = nomes
                elif "bebida" in cat_norm:
                    bebida_novo = nomes

            itens_consulta_novo = json.dumps(selecoes_personalizacao, ensure_ascii=False)

            dados_update = {
                "cliente_nome": e_nome.strip() + (" [B2B]" if is_b2b else (" [VITRINE]" if is_vitrine else "")),
                "cliente_email": e_email.strip(),
                "cliente_telefone": e_tel, "cliente_cpf": e_cpf, "destinatario_nome": e_dest.strip(),
                "destinatario_telefone": e_dtel, "motivo_homenagem": e_motivo, "endereco": e_end,
                "data_entrega": e_data.strftime("%Y-%m-%d"), "periodo_entrega": e_per, "mensagem": e_msg,
                "anotacoes_internas": e_anotacoes.strip(), "pedido_especial": e_pedido_especial.strip(),
                "cesta_nome": n_cesta, "cesta_id": id_cesta, "produtos": "\n\n".join(str_prod),
                "adicionais": msg_add.strip(), "pagamento": e_pag,
                "valor_frete": e_frete, "valor_total": total_liquido,
                "pao": pao_novo,
                "espalhavel": espalhavel_novo,
                "bebida": bebida_novo,
                "itens_consulta": itens_consulta_novo
            }

            valor_mudou = round(total_liquido, 2) != round(total_db, 2)
            # Nunca apaga o link/transação de pagamento de um pedido que JÁ
            # está marcado como Pago — mudar frete/desconto/itens depois do
            # pagamento confirmado não pode desfazer o registro do pagamento.
            if valor_mudou and pedido.get("infinitepay_url") and status_db != "Pago":
                dados_update["infinitepay_url"] = None
                dados_update["infinitepay_transaction_id"] = None

            try:
                supabase.table("pedidos").update(dados_update).eq("id", pedido_id).execute()
                
                supabase.table("pedido_adicionais").delete().eq("pedido_id", pedido_id).execute()
                for extra in lista_extras:
                    supabase.table("pedido_adicionais").insert({
                        "pedido_id": pedido_id,
                        "produto_id": extra.get("produto_id"),
                        "nome_produto": extra["nome"],
                        "quantidade": extra["quantidade"],
                        "valor_unitario": extra["preco_unitario"]
                    }).execute()
                
                if cliente_id and e_email.strip() != email_cliente:
                    try:
                        supabase.table("clientes").update({"email": e_email.strip()}).eq("id", cliente_id).execute()
                    except Exception as e:
                        st.toast(f"⚠️ Pedido salvo, mas não foi possível atualizar o perfil do cliente: {e}")
                st.success("✅ Atualizado!")
                if valor_mudou:
                    st.warning("⚠️ O valor do pedido mudou — o link de pagamento anterior foi invalidado. Gere um novo link na tela de detalhes antes de cobrar o cliente.")
                    time.sleep(2)
                st.session_state.modo_edicao = False
                st.rerun()
            except Exception as e: st.error(f"Erro: {e}")
    with c_save2:
        if st.button("❌ Cancelar", use_container_width=True): st.session_state.modo_edicao = False; st.rerun()
