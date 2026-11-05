import streamlit as st
import time

from services.cesta_service import listar_cestas
from services.produto_service import listar_produtos, listar_categorias
from services.cesta_produto_service import listar_produtos_da_cesta
from services.configuracao_cesta_service import salvar_configuracao_cesta
from utils.menu import configurar_pagina, menu_lateral
from utils.permissao import administrador_operador

st.set_page_config(page_title="Configurar Cesta", page_icon="⚙️", layout="wide")
configurar_pagina()
menu_lateral()
administrador_operador()

# =====================================================
# CSS PARA AJUSTAR A APARÊNCIA DOS CARDS NATIVOS
# =====================================================
st.markdown("""
<style>
.resumo-card { 
    background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; 
    padding: 15px; margin-bottom: 10px; height: 100%; 
}
.resumo-cat { font-size: 14px; font-weight: 800; color: #1e293b; margin-bottom: 8px; }
.resumo-info { font-size: 13px; color: #475569; }
</style>
""", unsafe_allow_html=True)

# --- (CARREGAMENTO DOS DADOS MANTIDO IGUAL) ---
try:
    cestas = listar_cestas()
    produtos = listar_produtos()
    categorias = listar_categorias()
except Exception as erro:
    st.error(f"Erro ao carregar dados: {erro}")
    st.stop()

cesta_alvo_id = st.session_state.get("config_cesta_id", None)
cesta = st.selectbox("🎁 Selecione a Cesta:", cestas, format_func=lambda x: x["nome"])
if not cesta: st.stop()
cesta_id = cesta["id"]

# --- (LÓGICA DE CATEGORIAS E PRODUTOS MANTIDA IGUAL) ---
categorias_dict = {cat["id"]: cat for cat in categorias}
produtos_configuraveis = [p for p in produtos if categorias_dict.get(p["categoria_id"], {}).get("nome", "").strip().lower() != "adicionais" and p.get("ativo", True)]
produtos_configurados = listar_produtos_da_cesta(cesta_id)
produtos_marcados = [item["produto_id"] for item in produtos_configurados]

produtos_por_categoria = {}
for prod in produtos_configuraveis:
    cat_id = prod["categoria_id"]
    if cat_id not in produtos_por_categoria: produtos_por_categoria[cat_id] = {"nome": categorias_dict[cat_id]["nome"], "produtos": []}
    produtos_por_categoria[cat_id]["produtos"].append(prod)

configuracoes = []
ordem = 1
for cat_id, dados in produtos_por_categoria.items():
    with st.container(border=True):
        st.subheader(f"📁 {dados['nome']}")
        c1, c2 = st.columns(2)
        minimo = c1.number_input("Mínimo", 0, 50, 1, key=f"min_{cat_id}")
        maximo = c2.number_input("Máximo", 1, 50, 1, key=f"max_{cat_id}")
        
        selecionados = []
        cols = st.columns(3)
        for i, prod in enumerate(dados["produtos"]):
            if cols[i%3].checkbox(prod["nome"], value=prod["id"] in produtos_marcados, key=f"p_{prod['id']}"):
                selecionados.append(prod["id"])
        
        if selecionados:
            configuracoes.append({"categoria_id": cat_id, "categoria": dados["nome"], "produtos": selecionados, "min_escolhas": minimo, "max_escolhas": maximo, "ordem": ordem})
            ordem += 1

# =====================================================
# RESUMO DA CONFIGURAÇÃO (CORRIGIDO COM COLUNAS NATIVAS)
# =====================================================
st.subheader("📋 Resumo da Estrutura")
if configuracoes:
    # Agrupamos em blocos de 3 para não quebrar
    for i in range(0, len(configuracoes), 3):
        row = st.columns(3)
        for j in range(3):
            if i + j < len(configuracoes):
                item = configuracoes[i + j]
                with row[j]:
                    st.markdown(f"""
                    <div class="resumo-card">
                        <div class="resumo-cat">📦 {item['categoria']}</div>
                        <div class="resumo-info">Produtos: <strong>{len(item['produtos'])}</strong></div>
                        <div class="resumo-info">Regra: <strong>{item['min_escolhas']} a {item['max_escolhas']} itens</strong></div>
                    </div>
                    """, unsafe_allow_html=True)
else:
    st.info("Nenhuma categoria configurada.")

# =====================================================
# BOTÕES DE AÇÃO
# =====================================================
st.divider()
col1, col2 = st.columns([1, 1])
if col1.button("💾 Salvar Configurações", type="primary", use_container_width=True):
    salvar_configuracao_cesta(cesta_id, configuracoes)
    st.cache_data.clear()
    st.toast("✅ Salvo!")
    time.sleep(1)
    st.switch_page("pages/04_Cestas.py")
if col2.button("⬅ Voltar", use_container_width=True):
    st.switch_page("pages/04_Cestas.py")
