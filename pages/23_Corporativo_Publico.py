import base64
import html
import mimetypes
import re
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from config.db import supabase
from services.configuracao_cesta_service import carregar_configuracao_cesta
from services.email_service import enviar_email_lead_corporativo
from services.telegram_service import enviar_notificacao_telegram
from utils.ui import tema_loja

st.set_page_config(
    page_title="Doce Cesta Corporativo | Presentes em Escala",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed",
)
tema_loja()

ASSETS_DIR = Path("assets").resolve()

def esc(v, padrao=""):
    return html.escape(str(v)) if v not in (None, "") else padrao

def _url_imagem_segura(url):
    """Só aceita http(s) ou data-URI de imagem — bloqueia esquemas perigosos."""
    url = str(url or "").strip()
    if url.startswith(("http://", "https://", "data:image/")):
        return url
    return ""

@st.cache_data(show_spinner=False)
def image_to_base64(img_path):
    """Converte uma imagem local em data-URI base64 para o Lightbox."""
    img_path = str(img_path).strip()
    if not img_path:
        return ""
    if img_path.startswith("http") or img_path.startswith("data:image"):
        return img_path
    try:
        caminho_resolvido = (ASSETS_DIR / img_path).resolve()
        caminho_resolvido.relative_to(ASSETS_DIR)
        with open(caminho_resolvido, "rb") as f:
            data = f.read()
            b64 = base64.b64encode(data).decode()
            mime = mimetypes.guess_type(str(caminho_resolvido))[0] or "image/jpeg"
            return f"data:{mime};base64,{b64}"
    except Exception:
        return ""

@st.cache_data(ttl=300, show_spinner=False)
def obter_catalogo_completo():
    """Busca as seções ativas destinadas ao público PJ (ou AMBOS)
    e as cestas vinculadas a essas seções.
    """
    secoes = []
    try:
        res_secoes = (
            supabase.table("vitrine_secoes")
            .select("*")
            .eq("ativa", True)
            .in_("publico", ["PJ", "AMBOS"])
            .order("ordem")
            .execute()
        )
        secoes = [s["nome"] for s in (res_secoes.data or [])]
    except Exception:
        try:
            res_secoes = (
                supabase.table("vitrine_secoes")
                .select("*")
                .eq("ativa", True)
                .order("ordem")
                .execute()
            )
            secoes = [s["nome"] for s in (res_secoes.data or [])]
        except Exception:
            secoes = []

    try:
        res_cestas = (
            supabase.table("cestas")
            .select("*")
            .eq("ativa", True)
            .order("ordem")
            .execute()
        )
        cestas = res_cestas.data or []
    except Exception:
        cestas = []

    secoes_set = set(secoes)
    cestas = [
        c for c in cestas if (c.get("secao_vitrine") or "Cestas de Café") in secoes_set
    ]

    return secoes, cestas

@st.cache_data(ttl=300, show_spinner=False)
def obter_itens_cesta_cached(cesta_id):
    try:
        return carregar_configuracao_cesta(cesta_id) or []
    except Exception:
        return []

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Dancing+Script:wght@600;700&family=Montserrat:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; }
[data-testid="stSidebar"] { display: none !important; }

/* CSS Hero Corporativo */
.corp-hero {
    position: relative; overflow: hidden; isolation: isolate;
    background: radial-gradient(420px 260px at 90% 0%, rgba(232,162,78,.5), transparent 65%), radial-gradient(320px 220px at 0% 110%, rgba(19,115,51,.4), transparent 65%), linear-gradient(135deg, #3B2417 0%, #1E130D 100%);
    border-radius: 32px; padding: clamp(36px, 6vw, 64px) 28px; text-align: center; color: #fff; margin-bottom: 26px; box-shadow: var(--sh-3);
    animation: dc-rise .8s var(--ease) both;
}
.corp-hero h1 { font-size: clamp(28px, 4.4vw, 46px); font-weight: 800; margin: 0 0 10px 0; letter-spacing: -.04em; line-height: 1.05; }
.corp-hero p { color: #EBD9C6; font-size: 16px; margin: 0 auto; max-width: 640px; }

.beneficio-item { display:flex; gap:10px; align-items:flex-start; margin-bottom:14px; }
.beneficio-icone { font-size:22px; }
.beneficio-texto b { color:#0F172A; }
.beneficio-texto span { color:#64748B; font-size:13.5px; }

/* =========================================
   CARDS DE CESTA (ALINHAMENTO E ALTURA IGUAL)
========================================= */
div[data-testid="stHorizontalBlock"] { display: flex !important; align-items: stretch !important; }
div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
    display: flex !important; flex-direction: column !important; flex: 1 1 0px !important; min-width: 0 !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #ffffff; border: 1px solid #e8ddd3 !important; border-radius: 20px !important;
    padding: 16px !important; margin-bottom: 20px !important; box-shadow: 0 4px 15px rgba(90, 59, 40, 0.03);
    position: relative; top: 0; transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
    flex: 1 !important; display: flex !important; flex-direction: column !important; height: 100% !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: #cbab92 !important; box-shadow: 0 12px 30px rgba(90, 59, 40, 0.08); top: -4px;
}
div[data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlock"] {
    flex: 1 !important; display: flex !important; flex-direction: column !important; justify-content: flex-start !important; 
    height: 100% !important; gap: 0 !important;
}

/* Títulos, Descrições e Abas */
div[data-testid="stTabs"] button {
    font-family: 'Montserrat', sans-serif !important; font-weight: 700 !important; font-size: 16px !important; 
    color: #8c7362 !important; padding-bottom: 10px !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] { color: #c5721f !important; border-bottom-color: #c5721f !important; }

.card-cesta-titulo {
    font-family: 'Dancing Script', cursive !important; font-size: 30px !important; font-weight: 700 !important;
    color: #c5721f !important; margin-top: 0px !important; margin-bottom: 10px !important;
    line-height: 1.15 !important; text-align: center !important; height: 40px !important;
    display: flex !important; align-items: center !important; justify-content: center !important;
}
.card-cesta-desc {
    font-size: 13px !important; color: #4d3e35 !important; line-height: 1.45 !important; text-align: justify !important;
    margin-top: 10px !important; margin-bottom: 4px !important; background: #faf7f3; padding: 12px;
    border-radius: 12px; border: 1px solid #f0e6dc; height: auto !important; min-height: 100px; overflow: visible !important;
}

/* =========================================
   LIGHTBOX CSS
========================================= */
.lightbox-wrapper { text-align: center; margin-bottom: 4px; width: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center; }
.lightbox-toggle { display: none !important; }
.lightbox-image {
    max-width: 100%; 
    width: auto !important; 
    height: auto !important; 
    max-height: 280px; 
    border-radius: 14px; 
    cursor: zoom-in;
    transition: transform 0.3s ease, box-shadow 0.3s ease; 
    box-shadow: 0 4px 15px rgba(90, 59, 40, 0.1);
    background-color: transparent; 
    border: 1px solid #e8ddd3;
    margin: 0 auto; 
}
.lightbox-image:hover { transform: scale(1.03); box-shadow: 0 8px 20px rgba(90, 59, 40, 0.15); }
.imagem-legenda { text-align: center; font-size: 10.5px; color: #888; margin-top: 6px; margin-bottom: 2px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
.lightbox-modal {
    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background-color: rgba(0, 0, 0, 0.85); z-index: 999999;
    display: flex; align-items: center; justify-content: center; opacity: 0; visibility: hidden; transition: opacity 0.3s ease; cursor: zoom-out;
}
.lightbox-modal img { max-width: 90vw; max-height: 90vh; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.6); }
.lightbox-toggle:checked ~ .lightbox-modal { opacity: 1; visibility: visible; }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="corp-hero">
    <h1>🏢 Presentes corporativos que fortalecem relações</h1>
    <p>Cestas personalizadas para clientes, equipe e parceiros — com identidade da sua marca e entrega em escala.</p>
</div>
""",
    unsafe_allow_html=True,
)

# 1. CENÁRIO DE USO (APENAS INFORMATIVO)
st.markdown("<h3 style='margin-bottom: 2px;'>🎯 Qual é a sua ocasião?</h3>", unsafe_allow_html=True)
st.markdown("<p style='color: #64748B; font-size: 14px; margin-bottom: 18px;'>Conheça as principais finalidades dos presentes para adaptarmos a proposta às suas necessidades:</p>", unsafe_allow_html=True)

CENARIOS = {
    "brindes_fim_de_ano": {
        "icone": "🎄",
        "titulo": "Brindes de Fim de Ano",
        "texto": "Encante clientes e parceiros com uma lembrança memorável para fechar o ano.",
    },
    "eventos_corporativos": {
        "icone": "🎉",
        "titulo": "Eventos & Convenções",
        "texto": "Kits de boas-vindas, brindes para palestras e mimos para eventos internos.",
    },
    "onboarding_rh": {
        "icone": "👋",
        "titulo": "Onboarding & RH",
        "texto": "Boas-vindas calorosas para novos colaboradores e datas comemorativas da equipe.",
    },
    "parcerias": {
        "icone": "🤝",
        "titulo": "Ações com Parceiros",
        "texto": "Presentes estratégicos para fortalecer o relacionamento com parceiros-chave.",
    },
    "outro": {
        "icone": "✍️",
        "titulo": "Projeto Sob Medida",
        "texto": "Conta pra gente a sua ideia — montamos um kit exclusivo para a sua demanda.",
    },
}

cols_cenario = st.columns(len(CENARIOS), gap="small")
for col, (chave, info) in zip(cols_cenario, CENARIOS.items()):
    with col:
        st.markdown(
            f"""
            <div style="
                border: 1px solid #e2e8f0;
                background-color: #ffffff;
                border-radius: 16px;
                padding: 16px 12px;
                text-align: center;
                min-height: 170px;
                display: flex;
                flex-direction: column;
                justify-content: flex-start;
                box-shadow: 0 2px 8px rgba(0,0,0,0.03);
                margin-bottom: 8px;
            ">
                <div>
                    <div style="font-size: 30px; margin-bottom: 6px;">{info['icone']}</div>
                    <div style="font-weight: 700; font-size: 13.5px; color: #1e293b; margin-bottom: 6px; line-height: 1.2;">{info['titulo']}</div>
                    <div style="font-size: 11.5px; color: #64748B; line-height: 1.35;">{info['texto']}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.divider()

# 2. CATÁLOGO CORPORATIVO
secoes_disponiveis, cestas_ativas = obter_catalogo_completo()

if cestas_ativas:
    st.markdown("### Nosso catálogo corporativo")
    st.caption("Toque na foto para ampliar. Nossas cestas são altamente personalizáveis para atender sua demanda.")

    if len(secoes_disponiveis) > 1:
        abas = st.tabs(secoes_disponiveis)
    else:
        abas = [st.container()]

    for i, aba in enumerate(abas):
        secao_atual = secoes_disponiveis[i] if len(secoes_disponiveis) > 1 else secoes_disponiveis[0]
        
        with aba:
            st.write("")
            cestas_da_secao = [
                c for c in cestas_ativas
                if (c.get("secao_vitrine") or "Cestas de Café").strip().lower() == secao_atual.strip().lower()
            ]
            
            if not cestas_da_secao:
                st.caption("Nenhuma cesta nesta seção no momento.")
                continue

            # Apresentação em colunas
            for sub_idx in range(0, len(cestas_da_secao), 3):
                grupo_cestas = cestas_da_secao[sub_idx:sub_idx + 3]
                colunas_vitrine = st.columns(3, gap="medium")
                
                for idx, cesta in enumerate(grupo_cestas):
                    with colunas_vitrine[idx]:
                        with st.container(border=True):
                            cesta_nome_seguro = html.escape(str(cesta.get("nome") or "Cesta"))

                            # --- NOME DA CESTA ---
                            st.markdown(f'<div class="card-cesta-titulo">{cesta_nome_seguro}</div>', unsafe_allow_html=True)

                            # --- IMAGEM PRINCIPAL & LIGHTBOX ---
                            imagem_url = cesta.get("imagem")
                            if imagem_url and str(imagem_url).strip():
                                img_src = _url_imagem_segura(image_to_base64(imagem_url))
                                if img_src:
                                    img_src_seguro = html.escape(img_src, quote=True)
                                    st.markdown(
                                        f"""
                                        <div class="lightbox-wrapper">
                                            <label style="cursor: zoom-in; width: 100%; display: flex; flex-direction: column; align-items: center;">
                                                <input type="checkbox" class="lightbox-toggle">
                                                <img src="{img_src_seguro}" class="lightbox-image" alt="Foto de {cesta_nome_seguro}" title="Clique para ampliar a foto da cesta" loading="lazy" decoding="async">
                                                <div class="lightbox-modal">
                                                    <img src="{img_src_seguro}" alt="Foto ampliada de {cesta_nome_seguro}">
                                                </div>
                                            </label>
                                            <div class="imagem-legenda">👆 Toque na foto para ampliar</div>
                                        </div>
                                        """,
                                        unsafe_allow_html=True
                                    )

                            # --- FOTOS ADICIONAIS ---
                            fotos_extras = cesta.get("fotos_adicionais", [])
                            if isinstance(fotos_extras, list) and len(fotos_extras) > 0:
                                st.markdown("<div style='font-size: 11px; font-weight: 800; color: #775a46; margin-bottom: 6px; text-transform: uppercase;'>📸 Outros ângulos:</div>", unsafe_allow_html=True)
                                cols_extras = st.columns(min(len(fotos_extras), 3))
                                for f_idx, f_url in enumerate(fotos_extras[:3]):
                                    if f_url and str(f_url).strip():
                                        with cols_extras[f_idx]:
                                            st.image(str(f_url).strip(), use_container_width=True)

                            # --- DESCRIÇÃO ---
                            descricao_txt = html.escape(str(cesta.get("descricao") or "")).replace("\n", "<br>")
                            
                            if not descricao_txt.strip():
                                itens_html = ""
                                for grupo in obter_itens_cesta_cached(cesta.get("id")):
                                    cat = esc(grupo.get("categoria", "Categoria"))
                                    prods = grupo.get("produtos", [])
                                    if prods:
                                        nomes_prods = esc(", ".join(p.get("nome", "") for p in prods))
                                        itens_html += f"<b>{cat}:</b> {nomes_prods}<br>"
                                if itens_html:
                                    descricao_txt = itens_html
                                else:
                                    descricao_txt = "Composição sob consulta — nossa equipe te ajuda a montar e adaptar."

                            st.markdown(f'<div class="card-cesta-desc">{descricao_txt}</div>', unsafe_allow_html=True)

    st.divider()

# 3. VANTAGENS
st.markdown("### O que você ganha pedindo com a gente")
col_b1, col_b2 = st.columns(2)
with col_b1:
    st.markdown(
        """
    <div class="beneficio-item"><div class="beneficio-icone">🎨</div><div class="beneficio-texto"><b>Identidade da sua marca</b><br><span>Cartão, embalagem e mensagem personalizados com o nome da empresa.</span></div></div>
    <div class="beneficio-item"><div class="beneficio-icone">📦</div><div class="beneficio-texto"><b>Logística centralizada</b><br><span>Você envia uma lista, a gente entrega em múltiplos endereços na mesma janela.</span></div></div>
    """,
        unsafe_allow_html=True,
    )
with col_b2:
    st.markdown(
        """
    <div class="beneficio-item"><div class="beneficio-icone">🧾</div><div class="beneficio-texto"><b>Nota fiscal e faturamento</b><br><span>Emissão de NF e condições de pagamento facilitadas para pessoa jurídica.</span></div></div>
    <div class="beneficio-item"><div class="beneficio-icone">💰</div><div class="beneficio-texto"><b>Condições especiais por volume</b><br><span>Propostas personalizadas com descontos progressivos conforme a quantidade de cestas.</span></div></div>
    """,
        unsafe_allow_html=True,
    )

st.divider()

# 4. FORMULÁRIO DE CONTATO
st.markdown("### Solicitar orçamento")

if st.session_state.get("lead_corporativo_enviado"):
    st.success(
        "🎉 Recebemos sua solicitação! Nossa equipe vai te procurar em até 1 dia útil."
    )
    st.balloons()
    if st.button("Enviar outra solicitação"):
        st.session_state["lead_corporativo_enviado"] = False
        st.rerun()
else:
    with st.form("form_lead_corporativo"):
        col1, col2 = st.columns(2)
        with col1:
            empresa_nome = st.text_input("Nome da empresa *")
            cnpj = st.text_input("CNPJ (opcional)")
            contato_nome = st.text_input("Seu nome *")
        with col2:
            contato_email = st.text_input("E-mail *")
            contato_telefone = st.text_input("Telefone / WhatsApp *")
            data_desejada = st.date_input(
                "Data desejada para entrega",
                value=date.today() + timedelta(days=14),
                format="DD/MM/YYYY",
            )
        
        # Ocasião e Preferências agora estão no formulário
        ocasiao_selecionada = st.selectbox(
            "Qual é a sua ocasião?",
            [info["titulo"] for info in CENARIOS.values()]
        )
        
        cesta_preferida = "Sem preferência / quero sugestão"
        if cestas_ativas:
            cesta_preferida = st.selectbox(
                "Cesta de interesse (opcional)",
                ["Sem preferência / quero sugestão"]
                + [c.get("nome") for c in cestas_ativas],
            )

        quantidade_estimada = st.number_input(
            "Quantidade estimada de cestas", min_value=1, value=10, step=1
        )
        observacoes = st.text_area(
            "Conte mais sobre o que você precisa (opcional)",
            placeholder=(
                "Ex: queremos o logo da empresa no cartão, entrega em 3 endereços diferentes..."
            ),
        )

        enviar = st.form_submit_button(
            "🚀 Solicitar Orçamento", type="primary", use_container_width=True
        )

        if enviar:
            erros = []
            if not empresa_nome.strip():
                erros.append("Informe o nome da empresa.")
            if not contato_nome.strip():
                erros.append("Informe seu nome.")
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", contato_email.strip()):
                erros.append("Informe um e-mail válido.")
            if len(re.sub(r"\D", "", contato_telefone)) < 10:
                erros.append("Informe um telefone válido (com DDD).")

            if erros:
                for e in erros:
                    st.error(e)
            else:
                cesta_base_id = None
                if cesta_preferida != "Sem preferência / quero sugestão":
                    encontrada = next(
                        (c for c in cestas_ativas if c.get("nome") == cesta_preferida),
                        None,
                    )
                    cesta_base_id = encontrada["id"] if encontrada else None

                payload_completo = {
                    "empresa_nome": empresa_nome.strip(),
                    "cnpj": re.sub(r"\D", "", cnpj) or None,
                    "contato_nome": contato_nome.strip(),
                    "contato_email": contato_email.strip(),
                    "contato_telefone": re.sub(r"\D", "", contato_telefone),
                    "caso_de_uso": ocasiao_selecionada,  # Atualizado para receber do form
                    "quantidade_estimada": str(quantidade_estimada),
                    "data_desejada": str(data_desejada),
                    "observacoes": observacoes.strip(),
                    "cesta_base_id": cesta_base_id,
                    "status": "novo",
                }

                payload_minimo = {
                    k: v
                    for k, v in payload_completo.items()
                    if k in {
                        "empresa_nome", "cnpj", "contato_nome", "contato_email",
                        "contato_telefone", "caso_de_uso", "quantidade_estimada",
                        "data_desejada", "observacoes", "status",
                    }
                }

                salvou = False
                erro_final = None
                for payload_tentativa in (payload_completo, payload_minimo):
                    try:
                        supabase.table("leads_corporativos").insert(
                            payload_tentativa
                        ).execute()
                        salvou = True
                        break
                    except Exception as e:
                        erro_final = e
                        continue

                if salvou:
                    msg_telegram = (
                        "🏢 <b>NOVO LEAD CORPORATIVO!</b>\n\n"
                        f"🏭 <b>Empresa:</b> {esc(empresa_nome.strip())}\n"
                        f"🆔 <b>CNPJ:</b> {esc(cnpj.strip() if cnpj else 'Não informado')}\n"
                        f"👤 <b>Contato:</b> {esc(contato_nome.strip())}"
                        f" ({esc(contato_telefone.strip())})\n"
                        f"📧 <b>E-mail:</b> {esc(contato_email.strip())}\n"
                        f"🎯 <b>Ocasião:</b> {esc(ocasiao_selecionada)}\n"
                        f"📦 <b>Quantidade:</b> {quantidade_estimada}\n"
                        f"🧺 <b>Cesta de interesse:</b> {esc(cesta_preferida)}\n"
                        f"📅 <b>Data desejada:</b> {data_desejada.strftime('%d/%m/%Y')}\n"
                        f"📝 <b>Observações:</b> {esc(observacoes.strip() if observacoes else 'Nenhuma')}"
                    )
                    try:
                        enviar_notificacao_telegram(msg_telegram)
                    except Exception:
                        pass

                    try:
                        enviar_email_lead_corporativo(
                            contato_email.strip(),
                            contato_nome.strip(),
                            empresa_nome.strip(),
                        )
                    except Exception:
                        pass

                    st.session_state["lead_corporativo_enviado"] = True
                    st.rerun()
                else:
                    st.error(
                        "Não foi possível enviar sua solicitação agora. Tente novamente "
                        f"em alguns minutos. ({erro_final})"
                    )

st.divider()
st.page_link("app.py", label="⬅️ Voltar para a Loja", icon="🛍️")
