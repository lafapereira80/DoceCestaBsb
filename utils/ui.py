"""
Design system do Doce Cesta Brasília (v2).

Tudo que é visual e compartilhado vive aqui:
  - tema_loja() / tema_admin()  -> injeta CSS + JS (animações, paleta de comandos, dock mobile)
  - page_header(), kpi_grid(), badge(), empty_state(), alerta()  -> componentes HTML reutilizáveis
  - A camada de compatibilidade de containers (st.container(border=True)) que funciona em
    qualquer versão do Streamlit (o seletor antigo `stVerticalBlockBorderWrapper` deixou de existir).
"""
import html
import itertools
from pathlib import Path

import streamlit as st

_ASSETS = Path(__file__).resolve().parent.parent / "assets"


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
def esc(valor, padrao=""):
    texto = str(valor) if valor not in (None, "") else padrao
    return html.escape(texto)


def brl(valor):
    try:
        return f"R$ {float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


@st.cache_data(show_spinner=False)
def _ler_asset(nome):
    caminho = _ASSETS / nome
    try:
        return caminho.read_text(encoding="utf-8").replace("@S", "html body .stApp")
    except Exception:
        return ""


# ----------------------------------------------------------------------------
# Compatibilidade: st.container(border=True) em QUALQUER versão do Streamlit
# As versões novas não geram mais `stVerticalBlockBorderWrapper`; sem um seletor estável
# o card perderia o estilo. Solução: todo container com borda ganha uma `key` automática
# (classe .st-key-dccard-N) e o CSS estiliza essa classe.
# ----------------------------------------------------------------------------
def _instalar_compat_container():
    if getattr(st, "_dc_container_patched", False):
        return
    try:
        from streamlit.delta_generator import DeltaGenerator
        original = DeltaGenerator.container
    except Exception:
        return

    contador = itertools.count(1)

    def container_compat(self, *args, **kwargs):
        if kwargs.get("border") and "key" not in kwargs:
            kwargs["key"] = f"dccard-{next(contador)}"
            kwargs["border"] = False
            try:
                return original(self, *args, **kwargs)
            except TypeError:  # Streamlit antigo sem `key`
                kwargs.pop("key", None)
                kwargs["border"] = True
        return original(self, *args, **kwargs)

    DeltaGenerator.container = container_compat
    st.container = lambda *a, **k: container_compat(st._main, *a, **k)
    st._dc_container_patched = True


def _executar_js(codigo):
    """Executa JS na página principal. O código vai em base64 porque o sanitizador do st.html
    descarta scripts com certos caracteres (<, &, aspas). Fallback: components.html."""
    import base64
    b64 = base64.b64encode(codigo.encode("utf-8")).decode("ascii")
    carregador = f'(0,eval)(decodeURIComponent(escape(atob("{b64}"))))'
    try:
        st.html(f"<script>{carregador}</script>", unsafe_allow_javascript=True)
    except TypeError:
        import streamlit.components.v1 as components
        components.html(
            f"<script>(function(){{var window=parent.window;var document=parent.document;{codigo}}})();</script>",
            height=0,
        )


def _injetar(tema, extra_css=""):
    _instalar_compat_container()
    base = _ler_asset("ds_base.css")
    especifico = _ler_asset(f"ds_{tema}.css")
    st.markdown(f"<style>{base}\n{especifico}\n{extra_css}</style>", unsafe_allow_html=True)
    _executar_js(_ler_asset("motion.js") + f"\nwindow.__dcBoot && window.__dcBoot('{tema}');")


def tema_loja():
    """Vitrine, checkout e páginas públicas."""
    _injetar("loja")


def tema_admin():
    """Todas as páginas do painel (chamado por utils.menu.configurar_pagina)."""
    _injetar("admin")


# ----------------------------------------------------------------------------
# Componentes
# ----------------------------------------------------------------------------
def page_header(titulo, subtitulo="", icone="✨", trilha=None, tom="brand"):
    """Cabeçalho padrão de página do painel: ícone, trilha de navegação, título, subtítulo."""
    crumbs = ""
    if trilha:
        partes = [f'<span>{esc(t)}</span>' for t in trilha]
        crumbs = '<div class="dc-crumbs">' + '<i></i>'.join(partes) + "</div>"
    sub = f'<p class="dc-ph-sub">{esc(subtitulo)}</p>' if subtitulo else ""
    st.markdown(
        f"""<div class="dc-ph dc-tone-{esc(tom)}">
            <div class="dc-ph-ico">{icone}</div>
            <div class="dc-ph-txt">{crumbs}<h1 class="dc-ph-title">{esc(titulo)}</h1>{sub}</div>
        </div>""".replace("\n", ""),
        unsafe_allow_html=True,
    )


def kpi_grid(itens, colunas=None):
    """itens: lista de dicts {icone, rotulo, valor, tom, prefixo, sufixo, dica, casas}
    Se `valor` for numérico, anima contagem (count-up)."""
    cards = []
    for i, it in enumerate(itens):
        valor = it.get("valor", 0)
        tom = it.get("tom", "brand")
        pref, suf = it.get("prefixo", ""), it.get("sufixo", "")
        casas = it.get("casas", 0)
        if isinstance(valor, (int, float)):
            miolo = (f'<span class="dc-kpi-val" data-count="{valor}" data-dec="{casas}" '
                     f'data-pre="{esc(pref)}" data-suf="{esc(suf)}">{esc(pref)}{valor:,.{casas}f}{esc(suf)}</span>'
                     ).replace(",", "X").replace(".", ",").replace("X", ".")
            # corrige separadores só no texto estático (o count-up usa pt-BR no JS)
        else:
            miolo = f'<span class="dc-kpi-val">{esc(valor)}</span>'
        dica = f'<div class="dc-kpi-hint">{esc(it.get("dica"))}</div>' if it.get("dica") else ""
        cards.append(
            f'<div class="dc-kpi dc-tone-{esc(tom)}" style="--i:{i}">'
            f'<div class="dc-kpi-ico">{it.get("icone", "•")}</div>'
            f'<div class="dc-kpi-body"><div class="dc-kpi-lab">{esc(it.get("rotulo"))}</div>{miolo}{dica}</div>'
            f'</div>'
        )
    estilo = f' style="grid-template-columns:repeat({int(colunas)},minmax(0,1fr))"' if colunas else ""
    st.markdown(f'<div class="dc-kpis"{estilo}>{"".join(cards)}</div>', unsafe_allow_html=True)


def badge(texto, tom="neutral", ponto=False):
    dot = '<i class="dc-dot"></i>' if ponto else ""
    return f'<span class="dc-badge dc-tone-{esc(tom)}">{dot}{esc(texto)}</span>'


def secao(titulo, descricao="", icone=""):
    desc = f'<span class="dc-sec-desc">{esc(descricao)}</span>' if descricao else ""
    ico = f'<b>{icone}</b>' if icone else ""
    st.markdown(f'<div class="dc-sec">{ico}<h3>{esc(titulo)}</h3>{desc}</div>', unsafe_allow_html=True)


def empty_state(titulo, descricao="", icone="🍰"):
    st.markdown(
        f'<div class="dc-empty"><div class="dc-empty-ico">{icone}</div>'
        f'<h4>{esc(titulo)}</h4><p>{esc(descricao)}</p></div>',
        unsafe_allow_html=True,
    )


def alerta(texto_html, tom="warn", icone="⚠️"):
    """texto_html deve vir já escapado pelo chamador."""
    st.markdown(
        f'<div class="dc-alert dc-tone-{esc(tom)}"><span class="dc-alert-ico">{icone}</span>'
        f'<div>{texto_html}</div></div>',
        unsafe_allow_html=True,
    )
