import streamlit as st
import base64
import html
import re
import unicodedata
import json
from pathlib import Path
from datetime import date, datetime, timezone, timedelta
import requests
from urllib.parse import quote

from services.pedido_service import salvar_pedido
from services.cesta_service import listar_cestas
from services.configuracao_cesta_service import carregar_configuracao_cesta
from services.produto_service import listar_produtos_por_categoria_id
from services.pedido_adicional_service import salvar_adicionais_pedido
from services.telegram_service import enviar_notificacao_telegram
from services.foto_service import salvar_fotos
from services.cupom_service import validar_cupom, registrar_uso
from utils.email_service import enviar_email_confirmacao
from config.db import supabase

OPCAO_OUTRO_BAIRRO = "__OUTRO_BAIRRO__"

PAGAMENTO_PIX = "Pix (Aprovação Imediata)"
PAGAMENTO_CARTAO = "Cartão de Crédito"

st.set_page_config(page_title="Finalizar Pedido | Doce Cesta Brasília", page_icon="🎁", layout="centered", initial_sidebar_state="collapsed")
from utils.ui import tema_loja  # noqa: E402
tema_loja()

def obter_hora_brasilia():
    return datetime.now(timezone(timedelta(hours=-3)))

def esc(valor, padrao=''):
    texto = str(valor) if valor not in (None, '') else padrao
    return html.escape(texto)

def normalizar_texto(texto):
    if not texto: return ""
    texto = str(texto).lower()
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    return texto.strip()

def bairro_esta_permitido(bairro_informado, lista_permitidos):
    if not bairro_informado or not lista_permitidos:
        return False
    b_norm = normalizar_texto(bairro_informado)
    for bp in lista_permitidos:
        bp_norm = normalizar_texto(bp)
        if not bp_norm: continue
        if bp_norm in b_norm or b_norm in bp_norm:
            return True
    return False

def _aliases_bairro(nome):
    sem_par = re.sub(r"\(.*?\)", "", str(nome)).split(" - ")[0]
    aliases = {normalizar_texto(nome), normalizar_texto(sem_par)}
    for parte in sem_par.split("/"):
        aliases.add(normalizar_texto(parte))
    return {a for a in aliases if a}

def encontrar_bairro_na_lista(bairro_informado, opcoes):
    """Mapeia o bairro vindo do ViaCEP para uma das opções liberadas. Retorna '' se não encontrar."""
    b_norm = normalizar_texto(bairro_informado)
    if not b_norm: return ""
    melhor, melhor_tam = "", 0
    for op in opcoes:
        for alias in _aliases_bairro(op):
            if b_norm == alias: return op
            if re.search(rf"\b{re.escape(alias)}\b", b_norm) and len(alias) > melhor_tam:
                melhor, melhor_tam = op, len(alias)
    return melhor

def fmt_brl(valor):
    return f"R$ {float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def promocao_ativa(cesta):
    if not cesta or not cesta.get("em_promocao") or cesta.get("preco_promocional") is None:
        return False
    try:
        agora = obter_hora_brasilia()
        inicio_str = cesta.get("promocao_inicio")
        fim_str = cesta.get("promocao_fim")
        
        if inicio_str:
            inicio = datetime.fromisoformat(str(inicio_str).replace('Z', '+00:00'))
            if inicio.tzinfo is None:
                inicio = inicio.replace(tzinfo=timezone(timedelta(hours=-3)))
            if agora < inicio: 
                return False
                
        if fim_str:
            fim = datetime.fromisoformat(str(fim_str).replace('Z', '+00:00'))
            if fim.tzinfo is None:
                fim = fim.replace(tzinfo=timezone(timedelta(hours=-3)))
            if agora > fim: 
                return False
                
        return True
    except Exception: 
        return False

def preco_efetivo_cesta(cesta):
    if not cesta: return 0.0
    if promocao_ativa(cesta):
        try: return float(cesta.get("preco_promocional") or 0)
        except Exception: pass
    try: return float(cesta.get("preco", 0) or 0)
    except Exception: return 0.0

def montar_url_imagem(caminho, tipo):
    if not caminho:
        return None
    caminho = str(caminho).strip()
    if not caminho:
        return None
    if caminho.startswith("http://") or caminho.startswith("https://"):
        return caminho
    try:
        base_url = st.secrets.get("r2_urls", {}).get(tipo, "")
    except Exception:
        base_url = ""
    if not base_url:
        return None
    return f"{base_url.rstrip('/')}/{caminho.lstrip('/')}"

@st.cache_data(ttl=600, show_spinner=False)
def obter_categorias_cacheadas():
    try: 
        res = supabase.table("categorias").select("*").execute()
        return res.data or []
    except Exception: 
        return []

@st.cache_data(ttl=600, show_spinner=False)
def obter_secoes_e_cestas_ativas():
    try:
        res_secoes = supabase.table("vitrine_secoes").select("nome", "ativa", "publico").eq("ativa", True).in_("publico", ["PF", "AMBOS"]).order("ordem").execute()
        secoes_ativas = [s["nome"] for s in (res_secoes.data or [])]
    except Exception:
        try:
            res_secoes = supabase.table("vitrine_secoes").select("nome", "ativa").eq("ativa", True).order("ordem").execute()
            secoes_ativas = [s["nome"] for s in (res_secoes.data or [])]
        except Exception:
            secoes_ativas = []

    if not secoes_ativas:
        secoes_ativas = ["Cestas de Café"]

    try:
        cestas_todas = listar_cestas()
        secoes_set = {str(sec).strip().lower() for sec in secoes_ativas}
        cestas_ativas = [c for c in cestas_todas if c.get("ativa", True) and str(c.get("secao_vitrine") or "Cestas de Café").strip().lower() in secoes_set]
        return secoes_ativas, sorted(cestas_ativas, key=lambda x: x.get("ordem", 999))
    except Exception:
        return ["Cestas de Café"], []

@st.cache_data(ttl=600, show_spinner=False)
def obter_configuracao_cesta_cacheada(cesta_id):
    return carregar_configuracao_cesta(cesta_id)

@st.cache_data(ttl=600, show_spinner=False)
def obter_produtos_por_categoria_cacheados(categoria_id):
    try: return listar_produtos_por_categoria_id(categoria_id)
    except Exception: return []

@st.cache_data(ttl=300, show_spinner=False)
def obter_configuracoes_loja():
    try:
        res = supabase.table("configuracoes_loja").select("*").eq("id", 1).execute()
        if res.data: return res.data[0]
    except Exception: pass
    return {
        "dias_antecedencia": 1, 
        "bloquear_apos_corte": True, 
        "hora_corte": "18:00:00", 
        "whatsapp_loja": "5561999759079", 
        "email_loja": "",
        "bairros_cadastrados": [],
        "bairros_permitidos": []
    }

@st.cache_data(show_spinner=False)
def carregar_logo_base64():
    logo_path = Path("assets/logo.png")
    if logo_path.exists():
        with open(logo_path, "rb") as img_file:
            encoded_logo = base64.b64encode(img_file.read()).decode()
            return f'<img src="data:image/png;base64,{encoded_logo}" class="header-logo" alt="Logo">'
    return "🎁"

@st.cache_data(ttl=86400, show_spinner=False)
def _consultar_cep_online(cep_limpo):
    """Só retorna dados válidos. Em falha levanta exceção, para o st.cache_data NÃO guardar o erro por 24h."""
    try:
        res = requests.get(f"https://viacep.com.br/ws/{cep_limpo}/json/", timeout=5)
        if res.status_code == 200:
            dados = res.json()
            if isinstance(dados, dict) and "erro" not in dados: return dados
    except Exception: pass
    # Alternativa caso o ViaCEP esteja fora do ar ou lento
    res = requests.get(f"https://brasilapi.com.br/api/cep/v2/{cep_limpo}", timeout=5)
    if res.status_code == 200:
        d = res.json()
        return {"logradouro": d.get("street", "") or "", "bairro": d.get("neighborhood", "") or "",
                "localidade": d.get("city", "") or "", "uf": d.get("state", "") or ""}
    raise ValueError("CEP não encontrado")

def buscar_cep_cacheado(cep_limpo):
    try: return _consultar_cep_online(cep_limpo)
    except Exception: return None

def validar_cpf(cpf: str) -> bool:
    cpf = re.sub(r'\D', '', cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11: return False
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    if (soma * 10 % 11) % 10 != int(cpf[9]): return False
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    if (soma * 10 % 11) % 10 != int(cpf[10]): return False
    return True

def get_cesta_by_id(cesta_id):
    if not cesta_id: return None
    _, cestas_ativas = obter_secoes_e_cestas_ativas()
    for c in cestas_ativas:
        if c["id"] == cesta_id:
            return c
    return None

st.markdown(
"""
<style>
@S .block-container { max-width: 820px !important; padding-top: 1.2rem !important; padding-bottom: 5rem !important; }
@S header[data-testid="stHeader"] { display: none !important; }
@S [data-testid="stProgress"] { display: none !important; }

/* topo da marca */
.header-banner { position: relative; overflow: hidden; display: flex; align-items: center; gap: 18px; padding: 20px 26px; margin-bottom: 20px; border-radius: 28px; color: #fff; isolation: isolate;
    background: radial-gradient(260px 160px at 100% 0%, rgba(232,162,78,.55), transparent 70%), linear-gradient(135deg, #3B2417, #1E130D); box-shadow: var(--sh-2); animation: dc-rise .7s var(--ease) both; }
.header-logo { width: 64px; height: 64px; border-radius: 50%; object-fit: cover; background: #fff; padding: 3px; flex: 0 0 auto; }
@S .header-title { font-family: var(--f-script) !important; font-size: 38px !important; font-weight: 700 !important; color: #FFD9A0 !important; margin: 0 !important; line-height: 1.05 !important; }
@S .header-subtitle { font-size: 13.5px !important; color: #E6D2BE !important; font-weight: 600 !important; margin: 4px 0 0 !important; }

/* título de cada seção */
.sec-h { display: flex; align-items: center; gap: 12px; margin: 0 0 14px; scroll-margin-top: 110px; }
.sec-h b { width: 38px; height: 38px; border-radius: 13px; display: grid; place-items: center; flex: 0 0 auto; font: 800 17px var(--f-display); color: #fff; background: linear-gradient(135deg, var(--caramelo-2), var(--caramelo-dk)); box-shadow: 0 6px 14px rgba(197,114,31,.3); transition: background .4s; }
.sec-h b.ok { background: linear-gradient(135deg, #34D27B, var(--ok)); box-shadow: 0 6px 14px rgba(19,115,51,.3); }
@S .sec-h .step-title { font-family: var(--f-display) !important; font-size: clamp(20px, 3.2vw, 26px) !important; font-weight: 800 !important; letter-spacing: -.035em !important; margin: 0 !important; color: var(--ink) !important; flex: 1; }
.sec-tag { font: 700 11px var(--f-body); padding: 4px 10px; border-radius: 999px; background: var(--brand-bg); color: var(--caramelo-dk); border: 1px solid var(--brand-ln); white-space: nowrap; }
.sec-tag.ok { background: var(--ok-bg); color: var(--ok); border-color: var(--ok-ln); }
.sec-tag.opc { background: #F1ECE6; color: var(--muted); border-color: var(--line); }
@S [class*="st-key-dccard-"] { margin-bottom: 14px; }

.destaque-cesta-nome-local { font-family: var(--f-script) !important; font-size: 38px !important; font-weight: 700 !important; color: var(--caramelo-dk) !important; line-height: 1.1 !important; margin-bottom: 2px; }

/* opções (checkbox) como cartões */
@S div[data-testid="stCheckbox"] { background: var(--surface-2); border: 1.5px solid var(--line); padding: 12px 16px; border-radius: 16px; margin-bottom: 8px; transition: all .25s var(--ease); }
@S div[data-testid="stCheckbox"]:hover { border-color: var(--caramelo); transform: translateX(3px); background: #fff; }
@S div[data-testid="stCheckbox"]:has(input:checked) { border-color: var(--caramelo); background: var(--brand-bg); }
@S div[data-testid="stCheckbox"] p, @S div[data-testid="stCheckbox"] label { color: var(--ink-2) !important; }

/* botões grandes */
@S div[data-testid="stButton"] button[kind="primary"], @S div[data-testid="stButton"] button[data-testid="stBaseButton-primary"] { min-height: 58px !important; font-size: 16px !important; margin-top: 10px; border-radius: 18px !important; }
@S div[data-testid="stButton"] button[kind="secondary"], @S div[data-testid="stButton"] button[data-testid="stBaseButton-secondary"] { min-height: 52px !important; margin-top: 10px; }

/* recibo */
.receipt-box { position: relative; background: #fff; border: 1.5px dashed var(--line-2); border-radius: 20px; padding: 24px; margin-top: 10px; box-shadow: var(--sh-1); }
.receipt-box::before, .receipt-box::after { content: ""; position: absolute; top: 50%; width: 18px; height: 18px; border-radius: 50%; background: #FFFCF8; border: 1.5px dashed var(--line-2); }
.receipt-box::before { left: -10px; } .receipt-box::after { right: -10px; }
.receipt-line { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 12px; font-size: 14px; color: var(--ink-2); }
.receipt-total { display: flex; justify-content: space-between; font: 800 18px var(--f-display); color: var(--pistache); margin-top: 15px; padding-top: 15px; border-top: 2px dashed var(--line-2); }

.sucesso-container { background: linear-gradient(145deg, #F0F9F3, #E4F4E9); border: 1.5px solid var(--ok-ln); border-radius: 30px; padding: 40px 28px; text-align: center; margin-top: 20px; box-shadow: var(--sh-2); animation: dc-pop .8s var(--spring) both; }
.sucesso-icone { font-size: 64px; margin-bottom: 6px; display: inline-block; animation: dc-bob 2.4s ease-in-out infinite; }
@S .sucesso-titulo { font: 800 clamp(26px, 4vw, 34px) var(--f-display); color: var(--ok); margin-bottom: 12px; letter-spacing: -.04em; }
@media (max-width: 640px) { .header-banner { padding: 16px; gap: 12px; } @S .header-title { font-size: 30px !important; } .header-logo { width: 52px; height: 52px; } }
</style>
""".replace("@S", "html body .stApp"), unsafe_allow_html=True)

def renderizar_secao(numero, titulo, ok=False, opcional=False):
    selo = '<span class="sec-tag opc">Opcional</span>' if opcional else ('<span class="sec-tag ok">Completo ✓</span>' if ok else '<span class="sec-tag">Obrigatório</span>')
    st.markdown(
        f'<div id="sec-{int(numero)}" class="sec-h"><b class="{"ok" if ok else ""}">{"✓" if ok else int(numero)}</b><h3 class="step-title">{titulo}</h3>{selo}</div>',
        unsafe_allow_html=True,
    )

LISTA_DDI_COMPLETA = [
    "🇧🇷 +55 (Brasil)", "🇺🇸 +1 (Estados Unidos)", "🇵🇹 +351 (Portugal)", "🇪🇸 +34 (Espanha)", 
    "🇦🇷 +54 (Argentina)", "🇨🇦 +1 (Canadá)", "🇫🇷 +33 (França)", "🇮🇹 +39 (Itália)", "🇬🇧 +44 (Reino Unido)"
]

# INICIALIZAÇÃO DE ESTADOS PARA O WIZARD
if "passo_atual" not in st.session_state: st.session_state["passo_atual"] = 1
if "pedido_enviado_com_sucesso" not in st.session_state: st.session_state["pedido_enviado_com_sucesso"] = False
if "pedido_processando" not in st.session_state: st.session_state["pedido_processando"] = False
if "ultimo_cep_buscado" not in st.session_state: st.session_state["ultimo_cep_buscado"] = ""

# Variáveis Persistentes
if "s_nome" not in st.session_state: st.session_state["s_nome"] = ""
if "s_email" not in st.session_state: st.session_state["s_email"] = ""
if "s_ddi_idx" not in st.session_state: st.session_state["s_ddi_idx"] = 0
if "s_tel" not in st.session_state: st.session_state["s_tel"] = ""
if "s_cpf" not in st.session_state: st.session_state["s_cpf"] = ""

if "s_dest_nome" not in st.session_state: st.session_state["s_dest_nome"] = ""
if "s_dest_tel" not in st.session_state: st.session_state["s_dest_tel"] = ""
if "s_motivo" not in st.session_state: st.session_state["s_motivo"] = ""
if "s_mensagem" not in st.session_state: st.session_state["s_mensagem"] = ""

if "s_cep" not in st.session_state: st.session_state["s_cep"] = ""
if "s_cidade" not in st.session_state: st.session_state["s_cidade"] = ""
if "s_bairro" not in st.session_state: st.session_state["s_bairro"] = ""
if "s_rua" not in st.session_state: st.session_state["s_rua"] = ""
if "s_numero" not in st.session_state: st.session_state["s_numero"] = ""
if "s_complemento" not in st.session_state: st.session_state["s_complemento"] = ""
if "s_data_entrega" not in st.session_state: st.session_state["s_data_entrega"] = None
if "s_periodo" not in st.session_state: st.session_state["s_periodo"] = "Manhã"
if "s_obs" not in st.session_state: st.session_state["s_obs"] = ""

if "s_secao" not in st.session_state: st.session_state["s_secao"] = None
if "s_cesta_id" not in st.session_state: st.session_state["s_cesta_id"] = None
if "s_selecoes_cliente" not in st.session_state: st.session_state["s_selecoes_cliente"] = {}

if "s_adicionais" not in st.session_state: st.session_state["s_adicionais"] = []
if "s_consentimento_fotos" not in st.session_state: st.session_state["s_consentimento_fotos"] = False
if "s_fotos_polaroid" not in st.session_state: st.session_state["s_fotos_polaroid"] = []

if "s_pagamento" not in st.session_state: st.session_state["s_pagamento"] = "Pix (Aprovação Imediata)"
if "s_consentimento_lgpd" not in st.session_state: st.session_state["s_consentimento_lgpd"] = False

secoes_disponiveis, cestas_ativas = obter_secoes_e_cestas_ativas()

# Processamento de cesta vinda da home
if st.session_state.get("cesta_selecionada_home"):
    cesta_veio_da_home = st.session_state.get("cesta_selecionada_home")
    for c in cestas_ativas:
        if c["id"] == cesta_veio_da_home:
            st.session_state["s_secao"] = c.get("secao_vitrine") or "Cestas de Café"
            st.session_state["s_cesta_id"] = cesta_veio_da_home
            break
    st.session_state["cesta_selecionada_home"] = None

# TELA DE SUCESSO
if st.session_state["pedido_enviado_com_sucesso"]:
    st.balloons()
    dados = st.session_state.get("resumo_pedido_sucesso", {})
    st.markdown(f'<div class="header-banner">{carregar_logo_base64()}<div class="header-text"><h1 class="header-title">Doce Cesta Brasília</h1></div></div>', unsafe_allow_html=True)
    linha_pagamento_ticket = f'<div class="receipt-line"><span>💳 <b>Pagamento:</b></span> <span style="text-align: right;">{esc(dados.get("pagamento_resumo"), "-")}</span></div>'
    st.markdown(f"""
<div class="sucesso-container">
<div class="sucesso-icone">🎉</div>
<div class="sucesso-titulo">Pedido Confirmado!</div>
<div style="font-size: 16px; color: #4a2e1b; line-height: 1.6; margin-bottom: 25px;">
Que alegria, <b>{esc(dados.get('cliente_nome'))}</b>! Seu pedido foi reservado com muito carinho pela nossa equipe. <br><br>
⏳ <b>Próximo Passo:</b> Nossa equipe entrará em contato via WhatsApp em instantes para enviar o link/chave de pagamento.<br>
📧 <i>Enviamos também um resumo para o seu e-mail.</i>
</div>
<div class="receipt-box" style="margin-top: 0; background-image: none; background: #ffffff;">
<div style="font-size: 16px; font-weight: 800; color: #5a3b28; margin-bottom: 15px; border-bottom: 1px solid #e8ddd3; padding-bottom: 10px;">📋 Seu Ticket de Encomenda</div>
<div class="receipt-line"><span>💝 <b>Para:</b></span> <span>{esc(dados.get('destinatario_nome'), '-')}</span></div>
<div class="receipt-line"><span>🎁 <b>Presente:</b></span> <span style="text-align: right;">{esc(dados.get('cesta_nome'))}</span></div>
<div class="receipt-line"><span>🎀 <b>Extras:</b></span> <span style="text-align: right;">{esc(dados.get('adicionais_str')) if dados.get('adicionais_str') else 'Nenhum'}</span></div>
<div class="receipt-line"><span>📅 <b>Data:</b></span> <span>{esc(dados.get('data_entrega'))} ({esc(dados.get('periodo_entrega'))})</span></div>
{linha_pagamento_ticket}
<div class="receipt-total"><span>TOTAL ESTIMADO (Sem frete)</span> <span>{esc(dados.get('valor_total'))}</span></div>
</div>
</div>
""", unsafe_allow_html=True)
    st.write("")
    if st.button("🎁 Fazer Novo Pedido", use_container_width=True, type="primary"):
        for key in list(st.session_state.keys()):
            if key.startswith("s_") or key.startswith("input_") or key in ["pedido_enviado_com_sucesso", "passo_atual", "ultimo_cep_buscado", "cep_nao_encontrado", "bairro_informado_cep"]:
                del st.session_state[key]
        st.rerun()
    st.stop()

# CABEÇALHO PADRÃO
st.markdown(f'<div class="header-banner">{carregar_logo_base64()}<div class="header-text"><h1 class="header-title">Doce Cesta Brasília</h1><p class="header-subtitle">Preencha tudo nesta página e finalize seu pedido 💝</p></div></div>', unsafe_allow_html=True)

# ------------------------------------------
# Progresso do formulário (lê o estado atual dos campos)
# ------------------------------------------
def _ss(chave, padrao=""):
    valor = st.session_state.get(chave, padrao)
    return valor if valor is not None else padrao

def _calcular_secoes_ok():
    comprador = (bool(str(_ss("input_nome", st.session_state["s_nome"])).strip())
                 and "@" in str(_ss("input_email", st.session_state["s_email"]))
                 and bool(re.sub(r"\D", "", str(_ss("input_tel", st.session_state["s_tel"]))))
                 and validar_cpf(str(_ss("input_cpf", st.session_state["s_cpf"]))))
    destinatario = bool(str(_ss("input_dest_nome", st.session_state["s_dest_nome"])).strip())
    endereco = all(str(_ss(k, st.session_state[s])).strip() for k, s in
                   [("input_cidade", "s_cidade"), ("input_bairro", "s_bairro"), ("input_rua", "s_rua"), ("input_numero", "s_numero")])
    cesta_widget = st.session_state.get("input_cesta_widget")
    presente = bool((isinstance(cesta_widget, dict) and cesta_widget.get("id")) or (cesta_widget is None and st.session_state.get("s_cesta_id")))
    extras = True
    pagamento = bool(_ss("input_consent_lgpd", st.session_state["s_consentimento_lgpd"]))
    return [comprador, destinatario, endereco, presente, extras, pagamento]

SECOES_OK = _calcular_secoes_ok()
# ==========================================
# 1. COMPRADOR
# ==========================================
with st.container(border=True):
    renderizar_secao(1, "Quem está presenteando?", SECOES_OK[0], False)
    st.caption("Precisamos dos seus dados para confirmar o pagamento e te enviar o recibo.")
    col_n, col_e = st.columns(2)
    with col_n: st.text_input("Seu Nome Completo *", value=st.session_state["s_nome"], placeholder="Ex: Maria Clara", key="input_nome", autocomplete="name")
    with col_e: st.text_input("Seu E-mail *", value=st.session_state["s_email"], placeholder="Ex: email@dominio.com", key="input_email", autocomplete="email")
    col_ddi, col_tel, col_cpf = st.columns([1.5, 2.5, 2.5])
    with col_ddi: st.selectbox("DDI *", LISTA_DDI_COMPLETA, index=st.session_state["s_ddi_idx"], key="input_ddi")
    with col_tel: st.text_input("Seu WhatsApp *", value=st.session_state["s_tel"], placeholder="(61) 99999-9999", key="input_tel", autocomplete="tel-national")
    with col_cpf: st.text_input("Seu CPF *", value=st.session_state["s_cpf"], placeholder="Apenas números", max_chars=14, key="input_cpf")

# ==========================================
# 2. DESTINATÁRIO
# ==========================================
with st.container(border=True):
    renderizar_secao(2, "Para quem é o presente?", SECOES_OK[1], False)
    col_d1, col_d2 = st.columns(2)
    with col_d1: st.text_input("Nome de quem vai receber *", value=st.session_state["s_dest_nome"], placeholder="Ex: Ana Clara", key="input_dest_nome")
    with col_d2: st.text_input("WhatsApp do destinatário", value=st.session_state["s_dest_tel"], placeholder="(Opcional)", key="input_dest_tel")
    st.text_input("Qual a Ocasião? (Opcional)", value=st.session_state["s_motivo"], placeholder="Ex: Aniversário, Dia das Mães...", key="input_motivo")
    st.text_area("💌 Cartão de Presente", value=st.session_state["s_mensagem"], height=100, placeholder="Escreva aqui a mensagem...", key="input_mensagem")

# ==========================================
# 3. LOCAL E AGENDAMENTO
# ==========================================
with st.container(border=True):
    renderizar_secao(3, "Local e agendamento", SECOES_OK[2], False)
    
    # Bairros liberados (cadastrados e liberados em 20_Configuracoes_Loja.py, salvos no banco)
    config_loja = obter_configuracoes_loja()
    bairros_cadastrados = config_loja.get("bairros_cadastrados")
    if not isinstance(bairros_cadastrados, list): bairros_cadastrados = []
    bairros_permitidos = config_loja.get("bairros_permitidos")
    if not isinstance(bairros_permitidos, list): bairros_permitidos = bairros_cadastrados
    bairros_permitidos = [b for b in bairros_permitidos if isinstance(b, str) and b.strip() and (not bairros_cadastrados or b in bairros_cadastrados)]
    opcoes_bairro = sorted(set(bairros_permitidos), key=normalizar_texto)
    opcoes_select = [""] + opcoes_bairro + [OPCAO_OUTRO_BAIRRO]

    # Lógica do CEP
    cep_input = st.text_input("CEP da Entrega", value=st.session_state["s_cep"], max_chars=8, placeholder="Somente números", key="input_cep")
    cep_limpo = re.sub(r'\D', '', cep_input)
    if len(cep_limpo) == 8 and st.session_state["ultimo_cep_buscado"] != cep_limpo:
        dados_cep = buscar_cep_cacheado(cep_limpo)
        st.session_state["ultimo_cep_buscado"] = cep_limpo
        if dados_cep:
            bairro_cep = dados_cep.get("bairro", "") or ""
            uf_cep = str(dados_cep.get("uf", "")).upper()
            rua_cep = dados_cep.get("logradouro", "") or ""
            cidade_cep = f"{dados_cep.get('localidade', '')} - {dados_cep.get('uf', '')}"
            st.session_state["s_rua"] = rua_cep
            st.session_state["s_cidade"] = cidade_cep
            st.session_state["bairro_informado_cep"] = bairro_cep
            if uf_cep == "DF" and bairro_cep.strip():
                bairro_lista = encontrar_bairro_na_lista(bairro_cep, opcoes_bairro)
                st.session_state["s_bairro"] = bairro_lista if bairro_lista else OPCAO_OUTRO_BAIRRO
            else:
                st.session_state["s_bairro"] = ""
            # Preenche os campos diretamente (antes de eles serem desenhados)
            st.session_state["input_rua"] = rua_cep
            st.session_state["input_cidade"] = cidade_cep
            st.session_state["input_bairro"] = st.session_state["s_bairro"]
            st.session_state["cep_nao_encontrado"] = ""
        else:
            st.session_state["cep_nao_encontrado"] = cep_limpo
    if len(cep_limpo) == 8 and st.session_state.get("cep_nao_encontrado") == cep_limpo:
        st.caption("⚠️ Não conseguimos localizar este CEP automaticamente. Confira o número ou preencha o endereço manualmente.")

    # Valores iniciais dos campos (ao voltar de outro passo, recupera o que já estava salvo)
    if "input_cidade" not in st.session_state: st.session_state["input_cidade"] = st.session_state["s_cidade"]
    if "input_rua" not in st.session_state: st.session_state["input_rua"] = st.session_state["s_rua"]

    # Garante que o valor atual do bairro é uma opção válida da lista
    if st.session_state.get("input_bairro") not in opcoes_select:
        st.session_state["input_bairro"] = st.session_state["s_bairro"] if st.session_state["s_bairro"] in opcoes_select else ""

    col_cid, col_bairro = st.columns([1.5, 1])
    with col_cid: st.text_input("Cidade - UF *", placeholder="Ex: Brasília - DF", key="input_cidade")
    with col_bairro:
        st.selectbox(
            "Bairro *",
            options=opcoes_select,
            format_func=lambda x: "Selecione o bairro..." if x == "" else ("Meu bairro não está na lista" if x == OPCAO_OUTRO_BAIRRO else x),
            key="input_bairro"
        )
    col_rua, col_num = st.columns([2.5, 1])
    with col_rua: st.text_input("Rua / Logradouro *", placeholder="Ex: SQS 101 Bloco A", key="input_rua")
    with col_num: st.text_input("Nº *", value=st.session_state["s_numero"], placeholder="Ex: 202", key="input_numero")
    st.text_input("Complemento (opcional)", value=st.session_state["s_complemento"], placeholder="Apto, bloco, ponto de referência...", key="input_complemento")
    
    st.markdown("<hr style='border: none; border-top: 1px dashed #dfcdbb; margin: 15px 0;'>", unsafe_allow_html=True)

    cidade_digitada = st.session_state.get("input_cidade", "")
    bairro_digitado = st.session_state.get("input_bairro", "")
    uf_entrega = cidade_digitada.split("-")[-1].strip() if "-" in cidade_digitada else "DF"
    
    bloquear_envio = False
    eh_df = (uf_entrega.upper() == "DF" or "DF" in cidade_digitada.upper() or "BRASILIA" in normalizar_texto(cidade_digitada) or "DISTRITO FEDERAL" in normalizar_texto(cidade_digitada))

    if (len(cep_limpo) == 8 or cidade_digitada.strip()) and not eh_df:
        bloquear_envio = True
        st.markdown("""
        <div style="background: #ffffff; border: 2px solid #DC2626; border-radius: 16px; padding: 25px; margin-top: 15px; box-shadow: 0 8px 24px rgba(220, 38, 38, 0.12); text-align: center; margin-bottom: 15px;">
            <div style="font-size: 40px; margin-bottom: 10px;">🚫</div>
            <h3 style="color: #DC2626; font-weight: 800; font-size: 20px; margin: 0 0 10px 0;">Entrega Indisponível Fora do DF</h3>
            <p style="color: #5a3b28; font-size: 15px; line-height: 1.6; margin-bottom: 0;">No momento, realizamos entregas exclusivamente no <b>Distrito Federal (Brasília e Regiões Administrativas)</b>.</p>
        </div>""", unsafe_allow_html=True)
    elif eh_df and bairro_digitado.strip():
        if bairro_digitado == OPCAO_OUTRO_BAIRRO or not bairro_esta_permitido(bairro_digitado, bairros_permitidos):
            bloquear_envio = True
            if bairro_digitado == OPCAO_OUTRO_BAIRRO:
                bairro_digitado = st.session_state.get("bairro_informado_cep", "") or "informado"
            st.markdown(f"""
            <div style="background: #ffffff; border: 2px solid #c5721f; border-radius: 16px; padding: 25px; margin-top: 15px; box-shadow: 0 8px 24px rgba(197, 114, 31, 0.12); text-align: center; margin-bottom: 15px;">
                <div style="font-size: 40px; margin-bottom: 10px;">📍</div>
                <h3 style="color: #c5721f; font-weight: 800; font-size: 22px; margin: 0 0 10px 0;">Bairro sob Consulta para Entrega</h3>
                <p style="color: #5a3b28; font-size: 15px; line-height: 1.6; margin-bottom: 0;">O bairro <b>{esc(bairro_digitado)}</b> ainda não possui entrega automática direta no site.<br>Entre em contato via WhatsApp para verificarmos a disponibilidade e o valor do frete para o seu endereço!</p>
            </div>""", unsafe_allow_html=True)

    # Lógica de Data - Step 3 (Leva em conta apenas a loja por enquanto)
    agora_bsb_oficial = obter_hora_brasilia()
    hoje_bsb_oficial = agora_bsb_oficial.date()
    dias_ant_loja = int(config_loja.get("dias_antecedencia", 1))
    data_minima_liberada = hoje_bsb_oficial + timedelta(days=dias_ant_loja)

    dt_default = st.session_state.get("s_data_entrega")
    if not dt_default or dt_default < data_minima_liberada:
        dt_default = data_minima_liberada

    col_ent1, col_ent2 = st.columns(2)
    with col_ent1: dt_ent = st.date_input("📅 Data da Entrega", min_value=data_minima_liberada, value=dt_default, format="DD/MM/YYYY", key="input_data_entrega")
    
    idx_periodo = ["Manhã", "Tarde", "Noite"].index(st.session_state["s_periodo"]) if st.session_state["s_periodo"] in ["Manhã", "Tarde", "Noite"] else 0
    with col_ent2: st.selectbox("🕒 Período Desejado", ["Manhã", "Tarde", "Noite"], index=idx_periodo, key="input_periodo")
    st.text_input("✨ Observações (Opcional)", value=st.session_state["s_obs"], key="input_obs")

    bloqueio_ativo = config_loja.get("bloquear_apos_corte", True)
    hora_corte_str = config_loja.get("hora_corte", "18:00:00")
    try: h_corte, m_corte, s_corte = map(int, hora_corte_str.split(':'))
    except: h_corte, m_corte = 18, 0

    if dt_ent == data_minima_liberada and bloqueio_ativo:
        if agora_bsb_oficial.time() >= datetime.strptime(hora_corte_str, "%H:%M:%S").time():
            bloquear_envio = True
            hora_formatada = f"{h_corte}h" if m_corte == 0 else f"{h_corte}h{m_corte:02d}"
            st.markdown(f"""
            <div style="background: #ffffff; border: 2px solid #c5721f; border-radius: 16px; padding: 25px; margin-top: 15px; box-shadow: 0 8px 24px rgba(197, 114, 31, 0.12); text-align: center; margin-bottom: 15px;">
                <div style="font-size: 40px; margin-bottom: 10px;">⏰</div>
                <h3 style="color: #c5721f; font-weight: 800; font-size: 22px; margin: 0 0 10px 0;">Ops! Prazo Excedido</h3>
                <p style="color: #5a3b28; font-size: 15px; line-height: 1.6; margin-bottom: 0;">As encomendas para a data selecionada encerraram às <b>{hora_formatada}</b>.<br>Confirme a disponibilidade pelo WhatsApp enviando seu pedido ou altere a data.</p>
            </div>""", unsafe_allow_html=True)

# ==========================================
# 4. A ESCOLHA DO PRESENTE
# ==========================================
nova_selecao = {}
bloquear_avanco_cesta = False

with st.container(border=True):
    renderizar_secao(4, "A escolha do presente", SECOES_OK[3], False)
    
    idx_secao = 0
    if st.session_state["s_secao"] in secoes_disponiveis:
        idx_secao = secoes_disponiveis.index(st.session_state["s_secao"])
    elif "Cestas de Café" in secoes_disponiveis:
        idx_secao = secoes_disponiveis.index("Cestas de Café")
        
    def resetar_cesta(): st.session_state["s_cesta_id"] = None
    
    if len(secoes_disponiveis) > 1:
        col_cat, col_mod = st.columns(2)
        with col_cat: secao_selecionada = st.selectbox("💌 1. O que deseja enviar?", secoes_disponiveis, index=idx_secao, key="input_secao", on_change=resetar_cesta)
    else:
        secao_selecionada = secoes_disponiveis[0]

    cestas_da_secao = [c for c in cestas_ativas if (c.get("secao_vitrine") or "Cestas de Café").strip().lower() == secao_selecionada.strip().lower()]
    opcoes_cestas = [{"id": None, "nome": "Clique para selecionar o modelo..."}] + cestas_da_secao
    
    idx_cesta = 0
    for i, c in enumerate(opcoes_cestas):
        if c["id"] == st.session_state["s_cesta_id"]: idx_cesta = i; break
        
    if len(secoes_disponiveis) > 1:
        with col_mod: cesta_selecionada = st.selectbox("💝 2. Escolha o modelo", opcoes_cestas, format_func=lambda c: c["nome"], index=idx_cesta, key="input_cesta_widget")
    else:
        cesta_selecionada = st.selectbox("💝 Escolha o modelo do presente", opcoes_cestas, format_func=lambda c: c["nome"], index=idx_cesta, key="input_cesta_widget")

    cesta_obj = get_cesta_by_id(cesta_selecionada["id"]) if cesta_selecionada and cesta_selecionada.get("id") else None

    if cesta_obj:
        # Validação cruzada de data
        config_loja = obter_configuracoes_loja()
        dias_ant_loja = int(config_loja.get("dias_antecedencia", 1))
        dias_ant_cesta = int(cesta_obj.get("dias_producao") or 0)
        if dias_ant_cesta > dias_ant_loja:
            data_min_cesta = obter_hora_brasilia().date() + timedelta(days=dias_ant_cesta)
            if dt_ent and dt_ent < data_min_cesta:
                st.error(f"⚠️ Atenção! A cesta selecionada ({cesta_obj['nome']}) exige {dias_ant_cesta} dia(s) de produção. A data de entrega escolhida na seção 3 ({dt_ent.strftime('%d/%m/%Y')}) não atende ao prazo. Por favor, ajuste a data em “Local e agendamento”.")
                bloquear_avanco_cesta = True

        st.markdown("<hr style='border: none; border-top: 1px dashed #dfcdbb; margin: 20px 0;'>", unsafe_allow_html=True)
        col_img, col_txt = st.columns([1.2, 1.8], gap="large")
        with col_img:
            url_img = montar_url_imagem(cesta_obj.get("imagem"), "cestas")
            if url_img: st.image(url_img, use_container_width=True)
            valor_base = preco_efetivo_cesta(cesta_obj)
            valor_txt = f"R$ {valor_base:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            st.markdown(f'<div style="margin-top: 15px; background: #ffffff; border: 2px solid #e8ddd3; border-radius: 16px; padding: 15px 10px; text-align: center;"><div style="font-size: 11px; font-weight: 800; color: #a65d14; text-transform: uppercase;">Valor</div><div style="font-size: 28px; color: #137333; font-weight: 800; line-height: 1;">{valor_txt}</div></div>', unsafe_allow_html=True)
        with col_txt:
            sec_txt = esc(cesta_obj.get("secao_vitrine") or "Cestas de Café")
            st.markdown(f'<div class="destaque-cesta-nome-local">{esc(cesta_obj.get("nome"))}</div><div style="color: #8c7362; font-size:13px; font-weight: 600; margin-bottom: 20px; text-transform: uppercase;">Coleção: {sec_txt}</div>', unsafe_allow_html=True)
            if cesta_obj.get("descricao"):
                desc_segura = esc(cesta_obj.get("descricao")).replace("\n", "<br>")
                st.markdown(f'<div style="background: #ffffff; padding: 20px; border-radius: 16px; font-size: 14px; color: #4a2e1b; line-height: 1.6; border: 1px solid #f5eee6;"><div style="color: #c5721f; font-weight: 800; text-transform: uppercase; margin-bottom: 12px;">✨ O que compõe esta cesta?</div><div style="text-align: justify;">{desc_segura}</div></div>', unsafe_allow_html=True)
        
        # Personalizações
        try: configuracao = obter_configuracao_cesta_cacheada(cesta_obj["id"])
        except Exception: configuracao = []
        
        if configuracao and any(grp.get("produtos") for grp in configuracao):
            st.markdown("<hr style='border: none; border-top: 1px dashed #dfcdbb; margin: 20px 0;'>", unsafe_allow_html=True)
            st.markdown('<div style="font-size: 16px; font-weight: 800; color: #5a3b28; margin-bottom: 15px;">🍓 Personalize os Itens da Cesta</div>', unsafe_allow_html=True)
            
            selecoes_anteriores = st.session_state.get("s_selecoes_cliente", {})
            for idx_grupo, grupo in enumerate(configuracao):
                cat = grupo.get("categoria") or "Categoria"
                prods = [p for p in (grupo.get("produtos") or []) if p and p.get("id") is not None]
                try: maximo = int(grupo.get("max_escolhas") or 1)
                except (TypeError, ValueError): maximo = 1
                if maximo < 1: maximo = 1
                if not prods: continue
                st.markdown(f"<div style='font-size: 14px; font-weight: 700; color: #775a46; margin-bottom: 6px; margin-top: 10px;'>📦 {esc(cat)}</div>", unsafe_allow_html=True)
                
                itens_default = selecoes_anteriores.get(cat, [])
                if maximo == 1:
                    idx_prod = 0
                    if itens_default:
                        for i, p in enumerate(prods):
                            if any(p["id"] == d.get("id") for d in itens_default): idx_prod = i; break
                    escolhido = st.radio("Escolha 1 opção", prods, index=idx_prod, format_func=lambda p: p["nome"], key=f"rad_{cesta_obj['id']}_{idx_grupo}_{cat}", label_visibility="collapsed")
                    if escolhido: nova_selecao.setdefault(cat, []).append(escolhido)
                else:
                    def_items = [p for p in prods if any(d.get("id") == p["id"] for d in itens_default)]
                    escolhidos = st.multiselect(f"Escolha até {maximo} opções", prods, default=def_items, format_func=lambda p: p["nome"], max_selections=maximo, key=f"mul_{cesta_obj['id']}_{idx_grupo}_{cat}")
                    nova_selecao.setdefault(cat, []).extend(escolhidos)

# ==========================================
# 5. MIMOS EXTRAS
# ==========================================
novos_adicionais = []
polaroid = False
fotos_upload = []
fotos_depois = False
with st.container(border=True):
    renderizar_secao(5, "Mimos extras", SECOES_OK[4], True)
    categorias = obter_categorias_cacheadas()
    cat_adicionais = next((c for c in categorias if c.get("nome", "").strip().lower() == "adicionais"), None)
    
    if cat_adicionais:
        produtos_adicionais = obter_produtos_por_categoria_cacheados(cat_adicionais["id"])
        if produtos_adicionais:
            colunas = st.columns(2)
            for indice, prod in enumerate(produtos_adicionais):
                preco_add = prod.get("preco")
                txt_val_add = f"+ R$ {float(preco_add):,.2f}".replace(",", "X").replace(".", ",").replace("X",".") if preco_add is not None else "Sob Consulta"
                
                foi_selecionado = any(a["produto_id"] == prod["id"] for a in st.session_state["s_adicionais"])
                
                with colunas[indice % 2]:
                    chk = st.checkbox(f"✨ {prod['nome']} **{txt_val_add}**", value=foi_selecionado, key=f"add_{prod['id']}")
                    if chk:
                        novos_adicionais.append({"produto_id": prod["id"], "nome": prod["nome"], "preco": float(preco_add) if preco_add is not None else None, "categoria": "Adicionais"})
                        if "polaroid" in prod["nome"].lower().strip() or "foto" in prod["nome"].lower().strip():
                            polaroid = True

    if polaroid:
        st.markdown("<hr style='border: none; border-top: 1px dashed #dfcdbb; margin: 15px 0;'>", unsafe_allow_html=True)
        st.markdown('<div style="font-size: 18px; font-weight: 800; color: #d1476a; margin-bottom: 5px;">📷 Envie suas Fotos (Polaroid)</div>', unsafe_allow_html=True)
        consentimento_fotos = st.checkbox(
            "Autorizo o uso das imagens enviadas exclusivamente para a personalização do produto.",
            value=st.session_state["s_consentimento_fotos"],
            key="input_consent_fotos"
        )
        st.caption("Envie até 2 fotos. Aguarde o carregamento terminar (✓) antes de finalizar o pedido.")
        fotos_upload = st.file_uploader(
            "Toque para anexar do seu celular/PC (até 2 fotos)",
            type=["jpg", "jpeg", "png", "webp", "heic"],
            accept_multiple_files=True,
            key="input_fotos_polaroid",
            disabled=not consentimento_fotos
        )
        if fotos_upload:
            st.success(f"📎 {len(fotos_upload)} foto(s) anexada(s).")
        fotos_depois = st.checkbox("Prefiro enviar as fotos depois, pelo WhatsApp.", key="input_fotos_depois")

# ==========================================
# 6. PAGAMENTO E RESUMO
# ==========================================
with st.container(border=True):
    renderizar_secao(6, "Pagamento e resumo", SECOES_OK[5], False)
    
    idx_pag = 1 if str(st.session_state["s_pagamento"]).startswith("Cartão") else 0
    pagamento_escolhido = st.radio("Como você prefere pagar?", [PAGAMENTO_PIX, PAGAMENTO_CARTAO], index=idx_pag, horizontal=True, key="input_pagamento")
    slot_parcelas = st.container()
    
    cesta_obj = get_cesta_by_id(cesta_selecionada["id"]) if cesta_selecionada and cesta_selecionada.get("id") else None
    valor_base = preco_efetivo_cesta(cesta_obj) if cesta_obj else 0
    valor_adicionais = sum([float(item.get("preco") or 0) for item in novos_adicionais if item.get("preco") is not None])
    total_estimado = valor_base + valor_adicionais

    with st.expander("🎟️ Tenho um cupom de desconto"):
        codigo_cupom_digitado = st.text_input("Código do cupom", key="input_codigo_cupom", placeholder="ex: DOCE-7K3F9Q")
        if st.button("Aplicar cupom"):
            identificador_cliente = re.sub(r"\D", "", st.session_state["s_cpf"] or st.session_state["s_tel"])
            ok_cupom, msg_cupom, cupom_valido, desconto_calculado = validar_cupom(
                codigo_cupom_digitado, total_estimado, identificador_cliente, cesta_obj.get("id") if cesta_obj else None
            )
            if ok_cupom:
                st.session_state["cupom_aplicado"] = cupom_valido
                st.session_state["cupom_desconto_valor"] = desconto_calculado
                st.success(msg_cupom)
            else:
                st.session_state["cupom_aplicado"] = None
                st.session_state["cupom_desconto_valor"] = 0.0
                st.error(msg_cupom)

    cupom_aplicado = st.session_state.get("cupom_aplicado")
    desconto_cupom = float(st.session_state.get("cupom_desconto_valor") or 0.0)
    if cupom_aplicado and desconto_cupom > total_estimado: desconto_cupom = total_estimado
    total_com_desconto = max(total_estimado - desconto_cupom, 0.0)
    codigo_cupom_aplicado_txt = cupom_aplicado["codigo"] if cupom_aplicado else ""

    valor_base_fmt = f"R$ {valor_base:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    valor_adc_fmt = f"R$ {valor_adicionais:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    total_fmt = f"R$ {total_com_desconto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    desconto_fmt = f"R$ {desconto_cupom:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    # ---- Cartão de crédito: exibe somente as taxas (salvas em 20_Configuracoes_Loja.py) ----
    usa_cartao = pagamento_escolhido == PAGAMENTO_CARTAO
    with slot_parcelas:
        if usa_cartao:
            st.caption("💳 Na opção de cartão de crédito há um acréscimo no valor referente à taxa da máquina.")
        else:
            st.caption("💚 No Pix não há nenhum acréscimo.")

    pagamento_detalhe = f"{PAGAMENTO_CARTAO} (com taxa da máquina)" if usa_cartao else pagamento_escolhido
    pagamento_resumo = f"{PAGAMENTO_CARTAO} (com taxa da máquina)" if usa_cartao else "Pix"
    aviso_cartao_html = (
        '<div style="font-size:12px;color:#8a6d4b;margin-top:10px;text-align:center;line-height:1.5;">'
        '💳 Na opção de cartão de crédito há um acréscimo no valor referente à taxa da máquina. O valor acima é o valor à vista.</div>'
    ) if usa_cartao else ""

    linha_extras_html = f'<div class="receipt-line"><span>🎀 Mimos Extras</span> <strong>{valor_adc_fmt}</strong></div>' if valor_adicionais > 0 else ""
    linha_desconto_html = f'<div class="receipt-line" style="color:#16A34A;"><span>🎟️ Cupom {esc(codigo_cupom_aplicado_txt)}</span> <strong>- {desconto_fmt}</strong></div>' if cupom_aplicado and desconto_cupom > 0 else ""
    linha_cesta_nome = esc(cesta_obj['nome']) if cesta_obj else "Cesta não selecionada"

    st.markdown(f"""
    <div class="receipt-box">
    <div style="font-size: 16px; font-weight: 800; color: #5a3b28; margin-bottom: 15px; text-align: center;">RESUMO DO PEDIDO</div>
    <div class="receipt-line"><span>🎁 <b>{linha_cesta_nome}</b></span> <strong>{valor_base_fmt}</strong></div>
    {linha_extras_html}
    {linha_desconto_html}
    <div class="receipt-line"><span>🚚 Taxa de Entrega</span> <strong>A calcular (via WhatsApp)</strong></div>
    <div class="receipt-total"><span>SUBTOTAL ESTIMADO:</span> <span>{total_fmt}</span></div>
    {aviso_cartao_html}
    </div>
    """, unsafe_allow_html=True)

    with st.expander("🔒 Privacidade e Proteção de Dados (LGPD)", expanded=False):
        st.markdown("""
        A **Doce Cesta Brasília** valoriza a sua privacidade e cumpre a Lei Geral de Proteção de Dados (Lei nº 13.709/2018).
        Ao prosseguir, você declara estar ciente do tratamento de seus dados conforme nossa Política de Privacidade.
        """)
    consentimento_lgpd = st.checkbox("Li e aceito a Política de Privacidade.", value=st.session_state["s_consentimento_lgpd"], key="input_consent_lgpd")

# ==========================================
# FINALIZAR (valida tudo de uma vez)
# ==========================================
st.write("")
_pendencias = []
if bloquear_envio:
    _pendencias.append("Confira o endereço/data de entrega (seção 3): há uma restrição indicada acima.")
if bloquear_avanco_cesta:
    _pendencias.append("A data de entrega não atende ao prazo de produção da cesta escolhida.")
if _pendencias:
    for _p in _pendencias:
        st.warning("⚠️ " + _p)

if st.button("🎁 FINALIZAR PEDIDO AGORA", use_container_width=True, type="primary",
             disabled=(st.session_state.get("pedido_processando", False) or bloquear_envio or bloquear_avanco_cesta)):
    erros = []
    if not st.session_state.input_nome.strip(): erros.append("Informe seu Nome Completo (seção 1).")
    if not st.session_state.input_email.strip() or "@" not in st.session_state.input_email: erros.append("E-mail inválido (seção 1).")
    if not st.session_state.input_tel.strip() or not re.sub(r"\D", "", st.session_state.input_tel): erros.append("WhatsApp inválido (seção 1).")
    if not validar_cpf(st.session_state.input_cpf): erros.append("CPF inválido (seção 1).")
    if not st.session_state.input_dest_nome.strip(): erros.append("Informe o nome de quem vai receber (seção 2).")
    if not (st.session_state.input_cidade.strip() and st.session_state.input_bairro.strip() and st.session_state.input_rua.strip() and st.session_state.input_numero.strip()):
        erros.append("Preencha todos os campos obrigatórios de endereço (seção 3).")
    if not cesta_selecionada or not cesta_selecionada.get("id"): erros.append("Escolha um modelo de cesta (seção 4).")
    if polaroid and not st.session_state.get("input_consent_fotos"): erros.append("É necessário autorizar o uso das fotos (seção 5).")
    if polaroid and st.session_state.get("input_consent_fotos") and not fotos_upload and not fotos_depois:
        erros.append("Anexe as fotos do Polaroid ou marque \"Prefiro enviar as fotos depois, pelo WhatsApp\" (seção 5).")
    if polaroid and fotos_upload and len(fotos_upload) > 2: erros.append("Envie no máximo 2 fotos (seção 5).")
    if st.session_state.get("pedido_processando"): st.stop()
    if not st.session_state.input_consent_lgpd: erros.append("É necessário aceitar a Política de Privacidade (seção 6).")
    if erros:
        for e in erros: st.error("❌ " + e)
        st.stop()

    # Consolida os campos nos estados definitivos (mesmos usados na gravação do pedido)
    st.session_state["s_nome"] = st.session_state.input_nome
    st.session_state["s_email"] = st.session_state.input_email
    try: st.session_state["s_ddi_idx"] = LISTA_DDI_COMPLETA.index(st.session_state.input_ddi)
    except Exception: st.session_state["s_ddi_idx"] = 0
    st.session_state["s_tel"] = st.session_state.input_tel
    st.session_state["s_cpf"] = st.session_state.input_cpf
    st.session_state["s_dest_nome"] = st.session_state.input_dest_nome
    st.session_state["s_dest_tel"] = st.session_state.input_dest_tel
    st.session_state["s_motivo"] = st.session_state.input_motivo
    st.session_state["s_mensagem"] = st.session_state.input_mensagem
    st.session_state["s_cep"] = st.session_state.input_cep
    st.session_state["s_cidade"] = st.session_state.input_cidade
    st.session_state["s_bairro"] = st.session_state.input_bairro
    st.session_state["s_rua"] = st.session_state.input_rua
    st.session_state["s_numero"] = st.session_state.input_numero
    st.session_state["s_complemento"] = st.session_state.input_complemento
    st.session_state["s_data_entrega"] = st.session_state.input_data_entrega
    st.session_state["s_periodo"] = st.session_state.input_periodo
    st.session_state["s_obs"] = st.session_state.input_obs
    st.session_state["s_secao"] = secao_selecionada
    st.session_state["s_cesta_id"] = cesta_selecionada["id"]
    st.session_state["s_selecoes_cliente"] = nova_selecao
    st.session_state["s_adicionais"] = novos_adicionais
    if polaroid:
        st.session_state["s_consentimento_fotos"] = st.session_state.get("input_consent_fotos", False)
        st.session_state["s_fotos_polaroid"] = list(fotos_upload or [])
    else:
        st.session_state["s_consentimento_fotos"] = False
        st.session_state["s_fotos_polaroid"] = []
    st.session_state["s_pagamento"] = st.session_state.input_pagamento
    st.session_state["s_consentimento_lgpd"] = st.session_state.input_consent_lgpd

    # PREPARAÇÃO DOS DADOS PARA SALVAR
    ddi_completo = LISTA_DDI_COMPLETA[st.session_state["s_ddi_idx"]]
    ddi = re.search(r'\+(\d+)', ddi_completo).group(1) if re.search(r'\+(\d+)', ddi_completo) else "55"
    cpf_limpo = re.sub(r'\D', '', st.session_state["s_cpf"])
    tel_digitos = re.sub(r"\D", "", st.session_state["s_tel"])
    if ddi == "55" and tel_digitos.startswith("55") and len(tel_digitos) > 11: tel_digitos = tel_digitos[2:]
    telefone_oficial = f"{ddi}{tel_digitos}"

    rua = st.session_state["s_rua"]
    num = st.session_state["s_numero"]
    complemento = st.session_state["s_complemento"].strip()
    bairro = st.session_state["s_bairro"]
    cidade = st.session_state["s_cidade"]
    cep = st.session_state["s_cep"]
    endereco_completo = f"{rua}, {num}" + (f" - {complemento}" if complemento else "") + f" - {bairro}, {cidade} (CEP: {cep})"

    valor_base_fmt_db = f"{valor_base:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    produtos_formatados_para_banco = f"1x {cesta_obj['nome']} (R$ {valor_base_fmt_db})"

    adicionais_lista = [f"{i['nome']}" for i in st.session_state["s_adicionais"]]

    pao_selecionado = ""
    espalhavel_selecionado = ""
    bebida_selecionada = ""

    for cat_nome, itens_escolhidos in st.session_state["s_selecoes_cliente"].items():
        if not itens_escolhidos: continue
        nomes_itens = ", ".join([item["nome"] for item in itens_escolhidos])
        cat_norm = normalizar_texto(cat_nome)
        if "pao" in cat_norm or "paes" in cat_norm: pao_selecionado = nomes_itens
        elif "espalhavel" in cat_norm or "espalhaveis" in cat_norm: espalhavel_selecionado = nomes_itens
        elif "bebida" in cat_norm: bebida_selecionada = nomes_itens

    tem_polaroid = any("polaroid" in str(a.get("nome")).lower() or "foto" in str(a.get("nome")).lower() for a in st.session_state["s_adicionais"])

    dt_ent_val = st.session_state.get("s_data_entrega")

    dados_pedido = {
        "cliente_nome": st.session_state["s_nome"].strip(),
        "cliente_email": st.session_state["s_email"].strip(),
        "cliente_cpf": cpf_limpo,
        "cliente_telefone": telefone_oficial,
        "destinatario_nome": st.session_state["s_dest_nome"].strip(),
        "destinatario_telefone": re.sub(r'\D', '', st.session_state["s_dest_tel"]),
        "motivo_homenagem": st.session_state["s_motivo"].strip(),
        "cesta_id": cesta_obj["id"],
        "cesta_nome": cesta_obj["nome"],
        "produtos": produtos_formatados_para_banco,
        "adicionais": ", ".join(adicionais_lista) if adicionais_lista else "Nenhum",
        "pao": pao_selecionado,
        "espalhavel": espalhavel_selecionado,
        "bebida": bebida_selecionada,
        "itens_consulta": json.dumps(st.session_state["s_selecoes_cliente"], ensure_ascii=False),
        "pagamento": pagamento_detalhe,
        "mensagem": st.session_state["s_mensagem"].strip(),
        "pedido_especial": st.session_state["s_obs"].strip(),
        "endereco": endereco_completo,
        "data_entrega": dt_ent_val.strftime("%Y-%m-%d") if dt_ent_val else str(obter_hora_brasilia().date()),
        "periodo_entrega": st.session_state["s_periodo"],
        "status": "Recebido",
        "valor_frete": 0,
        "valor_total": total_com_desconto,
        "cupom_codigo": codigo_cupom_aplicado_txt or None,
        "desconto_cupom": desconto_cupom,
        "consentimento_lgpd": st.session_state["s_consentimento_lgpd"],
        "consentimento_fotos": st.session_state["s_consentimento_fotos"] if tem_polaroid else False,
        "created_at": obter_hora_brasilia().isoformat()
    }

    with st.spinner("Reservando seu presente e finalizando pedido..."):
        st.session_state["pedido_processando"] = True
        try: 
            sucesso, pedido_id = salvar_pedido(dados_pedido)
        except Exception: 
            st.session_state["pedido_processando"] = False
            st.error("❌ Erro ao salvar pedido.")
            st.stop()
    
        if sucesso:
            if cupom_aplicado and desconto_cupom > 0:
                identificador_uso = re.sub(r"\D", "", cpf_limpo or telefone_oficial or "")
                try: registrar_uso(cupom_aplicado["id"], pedido_id, identificador_uso, desconto_cupom)
                except Exception: pass
            alertas_pedido = []
            if st.session_state["s_adicionais"]:
                try: salvar_adicionais_pedido(pedido_id, st.session_state["s_adicionais"])
                except Exception as e_add: alertas_pedido.append(f"Extras não gravados na tabela de adicionais ({e_add}). Conferir campo 'adicionais' do pedido.")
            n_fotos_enviadas = 0
            if tem_polaroid and st.session_state["s_consentimento_fotos"]:
                fotos_para_salvar = st.session_state["s_fotos_polaroid"][:2]
                if fotos_para_salvar:
                    try:
                        ok_fotos, msg_fotos = salvar_fotos(pedido_id, fotos_para_salvar)
                    except Exception as e_foto:
                        ok_fotos, msg_fotos = False, str(e_foto)
                    if ok_fotos: n_fotos_enviadas = len(fotos_para_salvar)
                    else: alertas_pedido.append(f"FALHA NO ENVIO DAS FOTOS: {msg_fotos}")
                else:
                    alertas_pedido.append("Cliente vai enviar as fotos pelo WhatsApp.")
            nota_extra = []
            if tem_polaroid:
                nota_extra.append(f"📷 Fotos recebidas: {n_fotos_enviadas}")
            if alertas_pedido:
                nota_extra.extend(f"⚠️ {a}" for a in alertas_pedido)
                try: enviar_notificacao_telegram("⚠️ <b>ATENÇÃO NO PEDIDO</b> <code>" + str(pedido_id) + "</code>\n" + "\n".join(esc(a) for a in alertas_pedido))
                except Exception: pass
            if nota_extra:
                try:
                    obs_atual = dados_pedido.get("pedido_especial") or ""
                    supabase.table("pedidos").update({"pedido_especial": (obs_atual + "\n" if obs_atual else "") + " | ".join(nota_extra)}).eq("id", pedido_id).execute()
                except Exception: pass
        
            linha_cupom_telegram = f"\n🎟️ <b>Cupom:</b> {codigo_cupom_aplicado_txt} (-{fmt_brl(desconto_cupom)})" if cupom_aplicado else ""
            msg_telegram_pedido = (
                f"🚨 <b>NOVO PEDIDO RECEBIDO!</b> 🚨\n\n"
                f"📦 <b>ID:</b> <code>{pedido_id}</code>\n"
                f"👤 <b>Cliente:</b> {esc(dados_pedido['cliente_nome'])}\n"
                f"🎁 <b>Presente:</b> {esc(cesta_obj['nome'])}\n"
                f"💰 <b>Estimativa (sem frete):</b> {total_fmt}\n"
                f"💳 <b>Pagamento:</b> {esc(pagamento_detalhe)}"
                f"{linha_cupom_telegram}"
            )
            try: enviar_notificacao_telegram(msg_telegram_pedido)
            except Exception: pass 
        
            with st.spinner("📧 Enviando recibo para o seu e-mail..."):
                itens_personalizados_txt = ""
                for categoria, produtos in st.session_state["s_selecoes_cliente"].items():
                    if produtos:
                        nomes = ", ".join([p["nome"] for p in produtos])
                        itens_personalizados_txt += f"{categoria}: {nomes}\n"
                if not itens_personalizados_txt:
                    itens_personalizados_txt = "Nenhum item personalizado selecionado."
                itens_personalizados_lista = [
                    {"categoria": categoria, "itens": [p["nome"] for p in produtos]}
                    for categoria, produtos in st.session_state["s_selecoes_cliente"].items() if produtos
                ]

                resumo_email = {
                    "cesta_nome": cesta_obj['nome'],
                    "destinatario_nome": dados_pedido["destinatario_nome"],
                    "data_entrega": dt_ent_val.strftime("%d/%m/%Y") if dt_ent_val else "",
                    "periodo_entrega": dados_pedido["periodo_entrega"],
                    "adicionais_str": ", ".join(adicionais_lista) if adicionais_lista else "Nenhum",
                    "itens_personalizados_str": itens_personalizados_txt,
                    "itens_personalizados": itens_personalizados_lista,
                    "tem_polaroid": bool(tem_polaroid),
                    "valor_total": total_fmt
                }
                try: enviar_email_confirmacao(dados_pedido["cliente_email"], dados_pedido["cliente_nome"], str(pedido_id).split('-')[0].upper(), resumo_email)
                except Exception: pass

            st.session_state["resumo_pedido_sucesso"] = {
                "cliente_nome": dados_pedido["cliente_nome"], "destinatario_nome": dados_pedido["destinatario_nome"], "cesta_nome": f"{cesta_obj['nome']}",
                "adicionais_str": ", ".join(adicionais_lista), "data_entrega": dt_ent_val.strftime("%d/%m/%Y") if dt_ent_val else "",
                "periodo_entrega": dados_pedido["periodo_entrega"], "endereco": endereco_completo, "valor_total": total_fmt,
                "pagamento_resumo": pagamento_resumo
            }
            st.session_state["pedido_enviado_com_sucesso"] = True
            st.session_state["pedido_processando"] = False
            st.rerun()
        else:
            st.session_state["pedido_processando"] = False
            st.error("❌ Ocorreu um problema ao registrar o pedido.")


st.divider()
st.markdown('<div style="text-align:center; font-size:12px; color:#888; font-weight: 500;">Doce Cesta Brasília © 2026<br>Transação 100% Segura 🔒</div>', unsafe_allow_html=True)
st.page_link("app.py", label="⬅️ Voltar para a Loja", icon="🛍️")
