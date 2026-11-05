import streamlit as st
import base64
import html
import math
import mimetypes
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

from config.db import supabase

# ==========================================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================================
st.set_page_config(
    page_title="Doce Cesta Brasília | Vitrine Oficial",
    page_icon="🎁",
    layout="wide",
    initial_sidebar_state="collapsed"
)

ASSETS_DIR = Path("assets").resolve()


def _url_imagem_segura(url):
    """Só aceita http(s) ou data-URI de imagem — bloqueia esquemas perigosos (ex: javascript:)."""
    url = str(url or "").strip()
    if url.startswith(("http://", "https://", "data:image/")):
        return url
    return ""


def _linhas_estimadas(texto, chars_por_linha=40):
    """Estima quantas linhas o texto ocupará no card (para igualar alturas na mesma linha)."""
    texto = str(texto or "")
    if not texto.strip():
        return 1
    return sum(max(1, math.ceil(len(par) / chars_por_linha)) for par in texto.split("\n"))


def promocao_ativa(cesta):
    """Retorna True se a cesta está com uma promoção configurada e dentro do período vigente."""
    if not cesta.get("em_promocao"):
        return False
    if cesta.get("preco_promocional") is None:
        return False
    try:
        agora = datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)
        inicio = datetime.fromisoformat(str(cesta.get("promocao_inicio"))) if cesta.get("promocao_inicio") else None
        fim = datetime.fromisoformat(str(cesta.get("promocao_fim"))) if cesta.get("promocao_fim") else None
        if inicio and agora < inicio:
            return False
        if fim and agora > fim:
            return False
        return True
    except Exception:
        return False


# ==========================================================
# CACHING DINÂMICO (VITRINE SEMPRE ATUALIZADA)
# ==========================================================
@st.cache_data(ttl=300, show_spinner=False)  
def obter_vitrine_oficial():
    """
    Busca as seções ativas destinadas ao público PF (ou AMBOS)
    e filtra as cestas vinculadas a essas seções.
    Tenta até 3 vezes (com pequena espera) antes de desistir.
    """
    ultimo_erro = None
    for tentativa in range(3):
        try:
            try:
                res_secoes = supabase.table("vitrine_secoes").select("*").eq("ativa", True).in_("publico", ["PF", "AMBOS"]).order("ordem").execute()
            except Exception:
                res_secoes = supabase.table("vitrine_secoes").select("*").eq("ativa", True).order("ordem").execute()

            secoes = res_secoes.data or []

            res_cestas = supabase.table("cestas").select("*").eq("ativa", True).order("ordem").execute()
            cestas = res_cestas.data or []

            if not secoes:
                secoes = [{"nome": "Cestas de Café", "ordem": 1}]

            secoes_set = {s.get("nome") for s in secoes if s.get("nome")}
            cestas_filtradas = [c for c in cestas if (c.get("secao_vitrine") or "Cestas de Café") in secoes_set]

            return secoes, cestas_filtradas
        except Exception as e:
            ultimo_erro = e
            if tentativa < 2:
                time.sleep(1)
    print(f"Erro ao carregar vitrine após 3 tentativas: {ultimo_erro}")
    raise ultimo_erro

@st.cache_data(ttl=300, show_spinner=False) 
def obter_adicionais_vitrine():
    """
    Busca os produtos cadastrados na categoria de Adicionais.
    """
    ultimo_erro = None
    for tentativa in range(3):
        try:
            categorias = supabase.table("categorias").select("*").execute().data or []
            cat_add = next((c for c in categorias if c.get("nome", "").strip().lower() == "adicionais"), None)

            if cat_add:
                res_prods = supabase.table("produtos").select("*").eq("categoria_id", cat_add["id"]).eq("ativo", True).execute()
                return res_prods.data or []
            return []
        except Exception as e:
            ultimo_erro = e
            if tentativa < 2:
                time.sleep(1)
    print(f"Erro ao carregar adicionais após 3 tentativas: {ultimo_erro}")
    raise ultimo_erro

@st.cache_data(ttl=300, show_spinner=False) 
def obter_configuracoes_loja():
    try:
        res = supabase.table("configuracoes_loja").select("*").eq("id", 1).execute()
        if res.data: return res.data[0]
    except Exception: pass
    return {"corporativo_ativo": True}

@st.cache_data(ttl=300, show_spinner=False) 
def obter_regioes_ativas():
    """
    Busca as regiões/bairros liberados para entrega na tabela configuracoes_loja.
    """
    try:
        res = supabase.table("configuracoes_loja").select("bairros_permitidos").eq("id", 1).execute()
        if res.data and res.data[0].get("bairros_permitidos"):
            bairros = res.data[0]["bairros_permitidos"]
            if isinstance(bairros, list) and len(bairros) > 0:
                bairros.sort() # Ordena alfabeticamente
                return ", ".join(bairros)
    except Exception as e:
        print(f"Erro ao carregar regiões ativas: {e}")
        
    return "Asa Norte, Asa Sul, Cruzeiro Novo, Cruzeiro Velho, Guará I, Guará II, Lago Norte, Lago Sul, Noroeste, Sudoeste / Octogonal"

# Função auxiliar para garantir que o Lightbox leia qualquer tipo de imagem
@st.cache_data(show_spinner=False)
def image_to_base64(img_path):
    """
    Converte uma imagem local em data-URI base64.
    """
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

from utils.ui import tema_loja, esc  # noqa: E402

tema_loja()

if "cesta_selecionada_home" not in st.session_state:
    st.session_state["cesta_selecionada_home"] = None

WHATS = "https://wa.me/5561999759079?text=Olá!%20Gostaria%20de%20tirar%20dúvidas%20sobre%20as%20cestas."


@st.cache_data(show_spinner=False)
def carregar_logo_base64():
    caminho = Path("assets/logo.png")
    if not caminho.exists():
        return ""
    with open(caminho, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()


logo_b64 = carregar_logo_base64()
logo_nav = f'<img src="data:image/png;base64,{logo_b64}" alt="">' if logo_b64 else ""

# ==========================================================
# BARRA DE NAVEGAÇÃO + HERO
# ==========================================================
st.markdown(
    f"""<div class="lj-nav">
      <a class="lj-nav-logo" href="#topo">{logo_nav}Doce Cesta Brasília</a>
      <div class="lj-nav-links">
        <a class="l" href="#como-pedir">Como pedir</a><a class="l" href="#catalogo">Catálogo</a><a class="l" href="#contato">Contato</a>
        <a class="cta" href="#catalogo">Ver cestas</a>
      </div></div>
    <div id="topo"></div>
    <section class="lj-hero">
      <div class="lj-blob a"></div><div class="lj-blob b"></div>
      <div>
        <div class="lj-tag">🌿 Cestas grazing · Brasília, DF</div>
        <h1>Cestas para criar <em>memórias inesquecíveis</em>.</h1>
        <p class="lead">Montadas à mão no estilo grazing, com cartão personalizável. Escolha uma cesta, monte do seu jeito e a gente entrega o carinho na porta de quem você ama.</p>
        <div class="ctas"><a class="lj-btn pri" href="#catalogo">🎁 Escolher minha cesta</a><a class="lj-btn ghost" href="{WHATS}" target="_blank" rel="noopener">💬 Falar no WhatsApp</a></div>
      </div>
      <div class="lj-scene" aria-hidden="true">
        <div class="lj-steam"><i></i><i></i><i></i></div>
        <div class="lj-plate">🧺</div>
        <div class="lj-chip c1">🍓</div><div class="lj-chip c2">☕</div><div class="lj-chip c3">🥐</div><div class="lj-chip c4">💌</div>
      </div>
    </section>
    <div class="lj-perks">
      <div class="lj-perk"><i>⏳</i><div><b>24h de antecedência</b><span>72h se tiver mini bolo</span></div></div>
      <div class="lj-perk"><i>💌</i><div><b>Cartão personalizável</b><span>Em todas as cestas</span></div></div>
      <div class="lj-perk"><i>🛵</i><div><b>Entrega ou retirada</b><span>Combinamos com você</span></div></div>
      <div class="lj-perk"><i>💳</i><div><b>Pix ou cartão</b><span>Link de crédito disponível</span></div></div>
    </div>""".replace("\n", ""),
    unsafe_allow_html=True,
)

# ==========================================================
# COMO PEDIR
# ==========================================================
regioes_atendidas = obter_regioes_ativas()
chips_regioes = "".join(f"<span>{esc(r.strip())}</span>" for r in str(regioes_atendidas).split(",") if r.strip())

st.markdown(
    f"""<div id="como-pedir" style="scroll-margin-top:90px"></div>
    <h2 class="lj-h2">Como fazer o pedido</h2><p class="lj-sub">Quatro passos simples, do catálogo à entrega.</p>
    <div class="lj-steps">
      <div class="lj-step"><b>Escolha a cesta</b><p>Veja o catálogo abaixo e clique em <b>“Quero montar esta cesta”</b>.</p></div>
      <div class="lj-step"><b>Personalize</b><p>Adicione extras e escreva o cartão para o homenageado.</p></div>
      <div class="lj-step"><b>Agende a entrega</b><p>Peça com no mínimo <b>24h</b> de antecedência (<b>72h</b> com mini bolo).</p></div>
      <div class="lj-step"><b>Pague e pronto</b><p>PIX ou link de cartão de crédito (com pequena taxa do aplicativo).</p></div>
    </div>
    <div class="lj-info">
      <div class="lj-box"><h4>📍 Regiões atendidas</h4><div class="lj-regions">{chips_regioes}</div>
        <p class="lj-note">Para demais regiões, entre em contato para verificar a disponibilidade.</p></div>
      <div class="lj-box"><h4>🕒 Atendimento e entrega</h4>
        <p><b>Segunda a sexta:</b> 7h às 19h<br><b>Sábado:</b> 8h às 12h</p>
        <p>Entregamos pessoalmente ou, dependendo da distância, via <b>Uber Flash / 99</b>. Também é possível retirar em mãos.</p></div>
    </div>
    <div id="catalogo" class="lj-cat-head"><div><h2 class="lj-h2">Catálogo</h2>
      <p class="lj-sub" style="margin:0">Escolha a cesta perfeita, confira os itens e personalize do seu jeito.</p></div></div>""".replace("\n", ""),
    unsafe_allow_html=True,
)

# ==========================================================
# CARREGAMENTO DOS DADOS DINÂMICOS
# ==========================================================
with st.spinner("Preparando a vitrine..."):
    try:
        secoes, cestas = obter_vitrine_oficial()
    except Exception as e:
        print(f"Vitrine indisponível após retries: {e}")
        secoes, cestas = [{"nome": "Catálogo", "ordem": 1}], []

    try:
        produtos_adicionais = obter_adicionais_vitrine()
    except Exception as e:
        print(f"Adicionais indisponíveis após retries: {e}")
        produtos_adicionais = []

if not cestas:
    st.info("O catálogo está sendo atualizado. Nenhuma cesta disponível no momento.")
else:
    # ==========================================================
    # CATÁLOGO DE CESTAS DINÂMICO (COM ABAS)
    # ==========================================================
    nomes_secoes = [sec["nome"] for sec in secoes]
    cestas_em_promocao = [c for c in cestas if promocao_ativa(c)]

    if cestas_em_promocao:
        nomes_secoes = ["🔥 Promoção"] + nomes_secoes

    if len(nomes_secoes) > 1:
        abas = st.tabs(nomes_secoes)
    else:
        abas = [st.container()]

    for i, aba in enumerate(abas):
        secao_atual = nomes_secoes[i]
        
        with aba:
            st.write("") # Respiro visual
            
            # Filtra cestas desta aba específica
            if secao_atual == "🔥 Promoção":
                cestas_da_aba = cestas_em_promocao
            else:
                cestas_da_aba = [c for c in cestas if c.get("secao_vitrine", "Cestas de Café") == secao_atual]
            
            if not cestas_da_aba:
                st.write(f"*(Nenhuma opção disponível no momento em {html.escape(str(secao_atual))})*")
                continue

            # ==========================================================
            # APRESENTAÇÃO EM LINHAS DE 3 COLUNAS COM ALTURA IGUAL
            # ==========================================================
            for sub_idx in range(0, len(cestas_da_aba), 3):
                grupo_cestas = cestas_da_aba[sub_idx:sub_idx + 3]
                colunas_vitrine = st.columns(3, gap="medium")

                # --- Métricas da linha: todos os cards assumem o tamanho do maior ---
                max_linhas_desc = max(_linhas_estimadas(c.get("descricao")) for c in grupo_cestas)
                desc_min_h = max_linhas_desc * 18 + 24
                max_chars_nome = max(len(str(c.get("nome") or "")) for c in grupo_cestas)
                titulo_min_h = 34 if max_chars_nome <= 20 else 62
                linha_tem_promo = any(promocao_ativa(c) for c in grupo_cestas)
                preco_min_h = 112 if linha_tem_promo else 40
                linha_tem_extras = any(
                    isinstance(c.get("fotos_adicionais"), list) and len([f for f in c.get("fotos_adicionais") if f and str(f).strip()]) > 0
                    for c in grupo_cestas
                )

                for idx, cesta in enumerate(grupo_cestas):
                    with colunas_vitrine[idx]:
                        with st.container(border=True):
                            cesta_nome_seguro = html.escape(str(cesta.get("nome") or "Cesta"))

                            # --- PARTE 1: NOME DA CESTA ---
                            st.markdown(f'<div class="card-cesta-titulo" style="--min-h:{titulo_min_h}px;">{cesta_nome_seguro}</div>', unsafe_allow_html=True)

                            # --- PARTE 2: IMAGEM PRINCIPAL & GALERIA ---
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

                            fotos_extras = cesta.get("fotos_adicionais", [])
                            fotos_extras_validas = [str(f).strip() for f in fotos_extras if f and str(f).strip()] if isinstance(fotos_extras, list) else []
                            if fotos_extras_validas:
                                st.markdown("<div class='extras-label'>📸 Outros ângulos</div>", unsafe_allow_html=True)
                                cols_extras = st.columns(min(len(fotos_extras_validas), 3))
                                for f_idx, f_url in enumerate(fotos_extras_validas[:3]):
                                    with cols_extras[f_idx]:
                                        st.image(f_url, use_container_width=True)
                            elif linha_tem_extras:
                                st.markdown('<div class="extras-spacer" style="--min-h:100px;"></div>', unsafe_allow_html=True)

                            # --- PARTE 3: DESCRIÇÃO ---
                            descricao_txt = html.escape(str(cesta.get("descricao") or "")).replace("\n", "<br>")
                            st.markdown(f'<div class="card-cesta-desc" style="--min-h:{desc_min_h}px;">{descricao_txt}</div>', unsafe_allow_html=True)

                            # --- PARTE 4: PREÇO ---
                            if promocao_ativa(cesta):
                                try:
                                    de_f = float(cesta.get("preco", 0))
                                    por_f = float(cesta.get("preco_promocional"))
                                    de_fmt = f"R$ {de_f:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                                    por_fmt = f"R$ {por_f:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                                    preco_html = (
                                        '<div class="promo-badge">🔥 Promoção por tempo limitado</div>'
                                        f'<div class="promo-de">De {de_fmt}</div>'
                                        f'<div class="promo-por">Por {por_fmt}</div>'
                                    )
                                except Exception:
                                    preco_html = '<div class="card-cesta-preco">Preço sob consulta</div>'
                            else:
                                try:
                                    valor = float(cesta.get("preco", 0))
                                    valor_fmt = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                                    preco_html = f'<div class="card-cesta-preco">{valor_fmt}</div>'
                                except Exception:
                                    preco_html = '<div class="card-cesta-preco">Preço sob consulta</div>'
                            st.markdown(
                                f'<div class="preco-container" style="--min-h:{preco_min_h}px;">{preco_html}</div>',
                                unsafe_allow_html=True
                            )

                            # --- PARTE 5: BOTÃO ---
                            if st.button("Quero montar esta cesta", icon="🛒", key=f"cesta_btn_{cesta['id']}_{i}", use_container_width=True):
                                st.session_state["cesta_selecionada_home"] = cesta["id"]
                                st.switch_page("pages/01_Inicio.py")

# ==========================================================
# ADICIONAIS (carrossel)
# ==========================================================
if produtos_adicionais:
    cards_html = ""
    for prod in produtos_adicionais:
        nome_p = str(prod.get("nome") or "")
        nome_p_seguro = html.escape(nome_p)
        preco_p = prod.get("preco")
        imagem_p = prod.get("imagem")

        if preco_p is not None and str(preco_p).strip() != "":
            try:
                val_f = float(preco_p)
                texto_preco = f'R$ {val_f:,.2f}'.replace(",", "X").replace(".", ",").replace("X", ".")
                span_preco = f'<span class="adicional-preco-fixo">{texto_preco}</span>'
            except Exception:
                span_preco = '<span class="adicional-preco-consulta">Consulta</span>'
        else:
            span_preco = '<span class="adicional-preco-consulta">Consulta</span>'

        img_src = _url_imagem_segura(image_to_base64(imagem_p)) if imagem_p and str(imagem_p).strip() else ""
        if img_src:
            img_src_seguro = html.escape(img_src, quote=True)
            img_html = f'<label style="cursor: zoom-in; display: block;"><input type="checkbox" class="lightbox-toggle"><img src="{img_src_seguro}" class="adicional-img-small" alt="{nome_p_seguro}" loading="lazy"><div class="lightbox-modal"><img src="{img_src_seguro}" alt="{nome_p_seguro}"></div></label>'
        else:
            icone = "📷" if "polaroid" in nome_p.lower() else "🎀"
            img_html = f'<div class="adicional-img-placeholder">{icone}</div>'

        cards_html += f'<div class="adicional-item-box">{img_html}<div class="adicional-nome">{nome_p_seguro}</div><div>{span_preco}</div></div>'

    st.markdown(
        f"""<div class="lj-add">
            <h2 class="lj-h2" style="font-size:26px">🎀 Incremente seu presente</h2>
            <p class="lj-sub">Escolha os adicionais na próxima tela, durante a montagem. Deslize para ver todos e toque na foto para ampliar.</p>
            <div class="lj-add-track">{cards_html}</div></div>""".replace("\n", ""),
        unsafe_allow_html=True,
    )

# ==========================================================
# CONTATO, CORPORATIVO E RODAPÉ
# ==========================================================
st.markdown(
    f"""<div id="contato" class="footer-container">
        <div class="footer-title">Fale conosco</div>
        <div class="footer-text">Ficou com dúvida sobre entregas e prazos, ou quer uma encomenda corporativa?<br>Nossa equipe está pronta para te atender.</div>
        <div class="social-btn-box">
            <a href="{WHATS}" target="_blank" rel="noopener" class="btn-whatsapp">💬 (61) 99975-9079</a>
            <a href="https://instagram.com/docecestabrasilia" target="_blank" rel="noopener" class="btn-instagram">📸 @docecestabrasilia</a>
        </div></div>
    <a class="lj-fab" href="{WHATS}" target="_blank" rel="noopener" aria-label="Falar no WhatsApp">💬</a>""".replace("\n", ""),
    unsafe_allow_html=True,
)

config_loja_app = obter_configuracoes_loja()
if bool(config_loja_app.get("corporativo_ativo", True)):
    st.markdown(
        """<div class="faixa-corporativa">
            <div><h3>🏢 Sua empresa também merece uma cesta especial</h3>
            <p>Brindes de fim de ano, eventos e boas-vindas — com identidade da sua marca e entrega em escala.</p></div>
            <a class="faixa-corporativa-btn" href="/Corporativo_Publico" target="_self">Conhecer soluções corporativas</a></div>""".replace("\n", ""),
        unsafe_allow_html=True,
    )

st.write("")
col_rodape1, col_rodape2 = st.columns(2)
with col_rodape1:
    st.page_link("pages/99_Admin.py", label="Acesso Restrito Administrativo", icon="🔒")
with col_rodape2:
    st.page_link("pages/21_politica_privacidade.py", label="Política de Privacidade", icon="📄")
