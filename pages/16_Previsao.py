import streamlit as st
import pandas as pd
import html
from datetime import datetime, date
import json
import time

from config.db import supabase
from utils.menu import configurar_pagina, menu_lateral
from utils.ui import page_header
from utils.permissao import administrador_operador
from services.cesta_service import buscar_cesta
from services.pedido_adicional_service import listar_adicionais_pedido

# =====================================================
# CONFIGURAÇÃO DA PÁGINA
# =====================================================
st.set_page_config(page_title="Painel de Produção", page_icon="🏭", layout="wide")
configurar_pagina()
menu_lateral()
administrador_operador()

st.markdown(
"""
<style>
.block-container { padding-top: 1.5rem !important; padding-bottom: 3rem !important; max-width: 1200px; }
h1 { font-size: 28px !important; font-weight: 800 !important; color: #4a2e1b !important; margin-bottom: 2px !important; letter-spacing: -0.5px; }
h3, h4 { color: #5a3b28 !important; font-weight: 800 !important; margin-top: 15px !important; margin-bottom: 10px !important; }
p, label { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important; font-size: 13px !important; }

.resumo-bar { background: linear-gradient(145deg, #ffffff 0%, #fdfcfb 100%); border: 1px solid #e8ddd3; border-radius: 16px; padding: 20px 24px; margin-bottom: 24px; }
.resumo-header { font-size: 13px; font-weight: 800; color: #775a46; text-transform: uppercase; margin-bottom: 12px; }
.pills-container { display: flex; flex-wrap: wrap; gap: 10px; }
.cesta-pill { background: #faf7f3; border: 1px solid #e8ddd3; padding: 6px 14px; border-radius: 20px; font-size: 14px; font-weight: 800; color: #5a3b28; display: flex; align-items: center; gap: 8px; }
.cesta-pill-qtd { background: #b06000; color: #ffffff; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 800; }

.pedido-card { background: #ffffff; border: 1px solid #e8ddd3; border-radius: 14px; padding: 18px 20px; margin-bottom: 12px; transition: all 0.2s ease; }
.pedido-card:hover { border-color: #d2bfae; transform: translateY(-2px); }
.card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; border-bottom: 1px solid #f3ece6; padding-bottom: 6px; }
.pedido-id { font-size: 13px; font-weight: 800; color: #9d7d65; text-transform: uppercase; }

.badge-status-pendente { background: #fef7e0; color: #b06000; padding: 4px 10px; border-radius: 8px; font-size: 11px; font-weight: 800; border: 1px solid #fce8b2; }
.badge-status-andamento { background: #fdf7e3; color: #b06000; padding: 4px 10px; border-radius: 8px; font-size: 11px; font-weight: 800; border: 1px solid #fce8b2; }
.badge-status-pronta { background: #e6f4ea; color: #137333; padding: 4px 10px; border-radius: 8px; font-size: 11px; font-weight: 800; border: 1px solid #ceead6; }

.cliente-titulo { font-size: 17px; font-weight: 800; color: #2c1e14; margin-bottom: 2px; }
.cesta-subtitulo { font-size: 15px; font-weight: 800; color: #b06000; margin-bottom: 10px; }
.info-linha-card { font-size: 13px; color: #555; margin-bottom: 4px; display: flex; align-items: center; gap: 6px; font-weight: 500; }

.progresso-container { background: #f3ece6; border-radius: 8px; height: 8px; width: 100%; margin: 14px 0 6px 0; overflow: hidden; }
.progresso-barra { background: linear-gradient(90deg, #b06000, #137333); height: 100%; border-radius: 8px; transition: width 0.4s ease; }

div[data-testid="stVerticalBlockBorderWrapper"] { background: #ffffff; border: 1px solid #e8ddd3 !important; border-radius: 14px !important; padding: 20px 24px !important; }
.montagem-header { background: #faf7f3; border: 1px solid #e8ddd3; border-radius: 12px; padding: 16px; margin-bottom: 16px; border-left: 4px solid #b06000; }
.secao-titulo { font-size: 14px; font-weight: 800; color: #775a46; text-transform: uppercase; margin-top: 15px; margin-bottom: 10px; border-bottom: 1px dashed #dfcdbb; padding-bottom: 4px; }

div[data-testid="stCheckbox"] { background: #faf7f3; border: 1px solid #e8ddd3; padding: 8px 12px; border-radius: 10px; margin-bottom: 6px; }
div[data-testid="stButton"] > button { font-size: 14px !important; font-weight: 800 !important; border-radius: 10px !important; min-height: 40px !important; }

/* =========================================
   RESPONSIVIDADE — TABLET (≤ 1024px)
========================================== */
@media (max-width: 1024px) {
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
}

/* =========================================
   RESPONSIVIDADE — CELULAR (≤ 768px)
========================================== */
@media (max-width: 768px) {
    .block-container { padding-top: 1rem !important; padding-left: .8rem !important; padding-right: .8rem !important; }
    h1 { font-size: 22px !important; }
    .pedido-card { padding: 14px 16px; }
    .cliente-titulo { font-size: 15px; }
    .cesta-subtitulo { font-size: 13.5px; }
    .cesta-pill { font-size: 12px; padding: 5px 10px; }
    div[data-testid="stVerticalBlockBorderWrapper"] { padding: 14px 16px !important; }
}
</style>
""", unsafe_allow_html=True)

page_header("Painel de produção", "O que montar, o que comprar e o que já está pronto.", "🏭", ["Operação", "Produção"], "warn")
st.caption("Acompanhe o volume diário e valide os itens via checklist.")

if "pedido_em_montagem" not in st.session_state: st.session_state.pedido_em_montagem = None

def buscar_pedidos_producao():
    # A fábrica só vê os pedidos com Status "Pago".
    res_producao = supabase.table("pedidos").select("*").eq("status", "Pago").execute()
    lista_total = res_producao.data or []
    # Uma vez que um entregador foi atribuído em 08_Entregas.py, o pedido já saiu das
    # mãos da produção (mesmo continuando com status "Pago") e não deve mais aparecer
    # aqui — só volta a ficar visível na fila de logística/entrega.
    lista_total = [p for p in lista_total if not p.get("entregador_login")]
    unicos = {p["id"]: p for p in lista_total}.values()
    return sorted(list(unicos), key=lambda x: x.get('data_entrega') or '9999-99-99')

pedidos = buscar_pedidos_producao()

if not pedidos:
    st.success("🎉 Excelente trabalho! A fila de produção está limpa.")
    st.stop()

resumo = {}
hoje = date.today()

for p in pedidos:
    dt_str = p.get("data_entrega")
    if not dt_str:
        chave_ordem = "9999-99-99"
        label_dia = "SEM DATA DEFINIDA"
    else:
        try:
            dt_obj = datetime.strptime(str(dt_str)[:10], "%Y-%m-%d").date()
            dias_diff = (dt_obj - hoje).days
            if dias_diff < 0: label_dia = f"⚠️ ATRASADO ({dt_obj.strftime('%d/%m')})"
            elif dias_diff == 0: label_dia = f"HOJE ({dt_obj.strftime('%d/%m')})"
            elif dias_diff == 1: label_dia = f"AMANHÃ ({dt_obj.strftime('%d/%m')})"
            elif dias_diff == 2: label_dia = f"DEPOIS ({dt_obj.strftime('%d/%m')})"
            else: label_dia = f"{dias_diff} DIAS ({dt_obj.strftime('%d/%m')})"
            chave_ordem = dt_obj.strftime("%Y-%m-%d")
        except:
            chave_ordem = "9999-99-99"
            label_dia = "SEM DATA DEFINIDA"
            
    if chave_ordem not in resumo: resumo[chave_ordem] = {"label": label_dia, "cestas_agrupadas": {}, "pedidos_lista": [], "total": 0}
    nome_cesta = p.get("cesta_nome") or "Cesta Não Informada"
    resumo[chave_ordem]["cestas_agrupadas"][nome_cesta] = resumo[chave_ordem]["cestas_agrupadas"].get(nome_cesta, 0) + 1
    resumo[chave_ordem]["pedidos_lista"].append(p)
    resumo[chave_ordem]["total"] += 1
    
dados_previsao = dict(sorted(resumo.items()))

# =====================================================
# GAVETA DE MONTAGEM
# =====================================================
if st.session_state.pedido_em_montagem:
    p_ativo = next((p for p in pedidos if p["id"] == st.session_state.pedido_em_montagem), None)
    
    if p_ativo:
        with st.container(border=True):
            col_tit, col_fechar = st.columns([4, 1])
            with col_tit: st.markdown(f"### 🛠️ Montagem da Cesta (Pedido #{str(p_ativo['id']).split('-')[0].upper()})")
            with col_fechar:
                if st.button("❌ Fechar Painel", use_container_width=True):
                    st.session_state.pedido_em_montagem = None
                    st.rerun()
            
            nome_cli_exibicao = html.escape((p_ativo.get('cliente_nome') or '').replace("[B2B]", "").strip())

            st.markdown(f"""
                <div class="montagem-header">
                    <div style="font-size: 18px; font-weight: 800; color: #2c1e14;">👤 {nome_cli_exibicao}</div>
                    <div style="font-size: 15px; font-weight: 800; color: #b06000;">🎁 {html.escape(str(p_ativo.get('cesta_nome') or '-'))}</div>
                    <div style="font-size: 13px; color: #444; margin-top: 4px;">📍 <strong>Endereço:</strong> {html.escape(str(p_ativo.get('endereco') or 'N/I'))}</div>
                </div>
                """, unsafe_allow_html=True)
            
            if str(p_ativo.get('anotacoes_internas') or '').replace('[FRETE_DEFINIDO]', '').strip(): st.warning(f"✨ **Atenções Internas:** {str(p_ativo.get('anotacoes_internas')).replace('[FRETE_DEFINIDO]', '').strip()}")
            
            st.markdown("#### 📋 Checklist")
            
            checklist_salvo = p_ativo.get("checklist") or {}
            if isinstance(checklist_salvo, str):
                try: checklist_salvo = json.loads(checklist_salvo)
                except: checklist_salvo = {}

            itens_consulta_salvos = p_ativo.get("itens_consulta") or {}
            if isinstance(itens_consulta_salvos, str):
                try: itens_consulta_salvos = json.loads(itens_consulta_salvos)
                except: itens_consulta_salvos = {}

            chaves_itens_pedido = []
            
            cesta_obj = buscar_cesta(p_ativo.get("cesta_id")) if p_ativo.get("cesta_id") else {}
            descricao_cesta = cesta_obj.get("descricao", "") if cesta_obj else ""
            if descricao_cesta:
                bloco_inclusos = descricao_cesta
                if "Inclusos:" in descricao_cesta: bloco_inclusos = descricao_cesta.split("Inclusos:")[1]
                elif "inclusos:" in descricao_cesta.lower(): bloco_inclusos = descricao_cesta.lower().split("inclusos:")[1]
                bloco_inclusos = bloco_inclusos.split("\n\n")[0]
                for item in [i.strip() for i in bloco_inclusos.split(";") if i.strip()]: chaves_itens_pedido.append(f"📦 {item}")
            
            produtos = p_ativo.get("produtos", "")
            if produtos:
                for prod_limpo in [p.replace('•', '').strip() for p in produtos.split("\n") if p.replace('•', '').strip()]: chaves_itens_pedido.append(f"✔️ {prod_limpo}")
            
            adicionais_bd = []
            try:
                lista_bruta = listar_adicionais_pedido(p_ativo['id'])
                nomes_vistos = set()
                for ad in lista_bruta:
                    nome_ad = ad.get("nome_produto")
                    if nome_ad and nome_ad not in nomes_vistos:
                        adicionais_bd.append(ad)
                        nomes_vistos.add(nome_ad)
            except: pass

            for ad in adicionais_bd:
                nome_ad = ad.get("nome_produto", "")
                if nome_ad:
                    chave_ad = f"➕ {nome_ad}"
                    if chave_ad not in chaves_itens_pedido: chaves_itens_pedido.append(chave_ad)

            for k, v in itens_consulta_salvos.items():
                if "Valor Manual de" not in k and not k.startswith("Valor de "):
                    chave_extra = f"🔹 {k}"
                    if chave_extra not in chaves_itens_pedido: chaves_itens_pedido.append(chave_extra)
            
            if p_ativo.get("mensagem", ""): chaves_itens_pedido.append("✅ Cartão impresso e posicionado")

            col_m1, col_m2 = st.columns(2)
            if col_m1.button("✅ Marcar Todos", use_container_width=True):
                for k in chaves_itens_pedido: st.session_state[f"chk_item_{p_ativo['id']}_{k}"] = True
                st.rerun()
            if col_m2.button("❌ Desmarcar Todos", use_container_width=True):
                for k in chaves_itens_pedido: st.session_state[f"chk_item_{p_ativo['id']}_{k}"] = False
                st.rerun()

            novo_checklist = {}
            itens_desc = []
            if descricao_cesta:
                bloco_inclusos = descricao_cesta
                if "Inclusos:" in descricao_cesta: bloco_inclusos = descricao_cesta.split("Inclusos:")[1]
                elif "inclusos:" in descricao_cesta.lower(): bloco_inclusos = descricao_cesta.lower().split("inclusos:")[1]
                bloco_inclusos = bloco_inclusos.split("\n\n")[0]
                itens_desc = [i.strip() for i in bloco_inclusos.split(";") if i.strip()]

            if itens_desc:
                st.markdown("<div class='secao-titulo'>📦 Itens Padrão</div>", unsafe_allow_html=True)
                cols_padrao = st.columns(2)
                for idx, item in enumerate(itens_desc):
                    chave_chk = f"📦 {item}"
                    val_padrao = (checklist_salvo.get(chave_chk, False) or bool(p_ativo.get("cesta_montada")))
                    session_key = f"chk_item_{p_ativo['id']}_{chave_chk}"
                    if session_key in st.session_state: val_padrao = st.session_state[session_key]
                    with cols_padrao[idx % 2]: novo_checklist[chave_chk] = st.checkbox(chave_chk, value=val_padrao, key=session_key)
            
            if produtos:
                st.markdown("<div class='secao-titulo'>🍓 Produtos / Lote</div>", unsafe_allow_html=True)
                prods_lista = [p.replace('•', '').strip() for p in produtos.split("\n") if p.replace('•', '').strip()]
                cols_pers = st.columns(2)
                for idx, prod_limpo in enumerate(prods_lista):
                    chave_chk = f"✔️ {prod_limpo}"
                    val_padrao = (checklist_salvo.get(chave_chk, False) or bool(p_ativo.get("cesta_montada")))
                    session_key = f"chk_item_{p_ativo['id']}_{chave_chk}"
                    if session_key in st.session_state: val_padrao = st.session_state[session_key]
                    with cols_pers[idx % 2]: novo_checklist[chave_chk] = st.checkbox(chave_chk, value=val_padrao, key=session_key)

            if adicionais_bd or itens_consulta_salvos:
                st.markdown("<div class='secao-titulo'>🎀 Adicionais e Extras</div>", unsafe_allow_html=True)
                cols_add = st.columns(2)
                contador_add = 0
                for ad in adicionais_bd:
                    nome_ad = ad.get('nome_produto', '')
                    if nome_ad:
                        chave_chk = f"➕ {nome_ad}"
                        val_padrao = (checklist_salvo.get(chave_chk, False) or bool(p_ativo.get("cesta_montada")))
                        session_key = f"chk_item_{p_ativo['id']}_{chave_chk}"
                        if session_key in st.session_state: val_padrao = st.session_state[session_key]
                        with cols_add[contador_add % 2]: novo_checklist[chave_chk] = st.checkbox(chave_chk, value=val_padrao, key=session_key)
                        contador_add += 1

                for k, v in itens_consulta_salvos.items():
                    if "Valor Manual de" not in k and not k.startswith("Valor de "):
                        chave_chk = f"🔹 {k}"
                        val_padrao = (checklist_salvo.get(chave_chk, False) or bool(p_ativo.get("cesta_montada")))
                        session_key = f"chk_item_{p_ativo['id']}_{chave_chk}"
                        if session_key in st.session_state: val_padrao = st.session_state[session_key]
                        with cols_add[contador_add % 2]: novo_checklist[chave_chk] = st.checkbox(chave_chk, value=val_padrao, key=session_key)
                        contador_add += 1
            
            mensagem = p_ativo.get("mensagem", "")
            if mensagem:
                st.markdown("<div class='secao-titulo'>💌 Mensagem do Cartão</div>", unsafe_allow_html=True)
                chave_chk = "✅ Cartão impresso e posicionado"
                val_padrao = (checklist_salvo.get(chave_chk, False) or bool(p_ativo.get("cesta_montada")))
                session_key = f"chk_item_{p_ativo['id']}_{chave_chk}"
                if session_key in st.session_state: val_padrao = st.session_state[session_key]
                novo_checklist[chave_chk] = st.checkbox(chave_chk, value=val_padrao, key=session_key)
                
            st.write("")
            st.divider()
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("💾 Salvar Checklist (Progresso)", use_container_width=True):
                    # APENAS ATUALIZA O PROGRESSO, NÃO TOCA NO STATUS GERAL.
                    tudo_pronto = len(novo_checklist) > 0 and all(novo_checklist.values())
                    try:
                        supabase.table("pedidos").update({
                            "checklist": novo_checklist,
                            "cesta_montada": tudo_pronto
                        }).eq("id", p_ativo['id']).execute()
                        st.toast("✅ Progresso salvo no sistema!")
                        time.sleep(0.5)
                        st.rerun(scope="app")
                    except Exception as e: st.error(f"❌ Erro ao salvar: {e}")
            with col_b2:
                if st.button("🚚 Finalizar e Despachar para Rota", type="primary", use_container_width=True):
                    try:
                        supabase.table("pedidos").update({
                            "checklist": novo_checklist,
                            "cesta_montada": True,
                            # O status PERMANECE "Pago" de propósito: a etapa de entrega é controlada
                            # pela flag 'cesta_montada' + atribuição de entregador (08_Entregas.py), não
                            # por uma troca de status. Isso mantém o pedido visível em 02_Pedidos.py
                            # dentro do filtro "Pago" até a entrega ser efetivamente concluída.
                        }).eq("id", p_ativo['id']).execute()
                        st.success("✅ Cesta pronta e liberada para a Rota de Entrega!")
                        st.session_state.pedido_em_montagem = None
                        time.sleep(1.5)
                        st.rerun(scope="app")
                    except Exception as e: st.error(f"❌ Erro ao despachar: {e}")
        st.divider()

# =====================================================
# INTERFACE PRINCIPAL
# =====================================================
if dados_previsao:
    nomes_abas = [info["label"] for data, info in dados_previsao.items()]
    abas = st.tabs(nomes_abas)
    
    for i, (data, info) in enumerate(dados_previsao.items()):
        with abas[i]:
            html_pills = "".join([f"<div class='cesta-pill'>📦 {html.escape(str(cesta))} <span class='cesta-pill-qtd'>{qtd}</span></div>" for cesta, qtd in info["cestas_agrupadas"].items()])
            st.markdown(f"<div class='resumo-bar'><div class='resumo-header'>📊 Resumo (Total: {info['total']})</div><div class='pills-container'>{html_pills}</div></div>", unsafe_allow_html=True)
            
            pedidos_lista = info["pedidos_lista"]
            col_esq, col_dir = st.columns(2)
            
            for idx, p in enumerate(pedidos_lista):
                pid = str(p["id"]).split('-')[0].upper()
                
                chk_atual = p.get("checklist") or {}
                if isinstance(chk_atual, str):
                    try: chk_atual = json.loads(chk_atual)
                    except: chk_atual = {}
                
                total_itens = len(chk_atual) if chk_atual else 1
                itens_marcados = sum(1 for v in chk_atual.values() if v)
                porcentagem = int((itens_marcados / total_itens) * 100) if total_itens > 0 else 0
                
                # Visual do Progresso no Kanban
                if p.get("cesta_montada", False) or porcentagem == 100:
                    status_badge = '<span class="badge-status-pronta">✅ PRONTA</span>'
                elif itens_marcados > 0:
                    status_badge = '<span class="badge-status-andamento">⚙️ EM MONTAGEM</span>'
                else:
                    status_badge = '<span class="badge-status-pendente">⏳ PENDENTE</span>'
                
                endereco_completo = p.get('endereco') or 'Endereço não informado'
                bairro = endereco_completo.split(',')[-1].split('(')[0].strip() if ',' in endereco_completo else endereco_completo
                nome_cliente_card = (p.get('cliente_nome') or '-').replace("[B2B]", "").strip()
                
                card_html = f"""
                <div class="pedido-card">
                    <div class="card-top"><span class="pedido-id">Pedido #{pid}</span>{status_badge}</div>
                    <div class="cliente-titulo">{html.escape(nome_cliente_card)}</div>
                    <div class="cesta-subtitulo">🎁 {html.escape(str(p.get('cesta_nome') or '-'))}</div>
                    <div class="info-linha-card">📍 <strong>Localização:</strong> {html.escape(bairro)}</div>
                    <div class="progresso-container"><div class="progresso-barra" style="width: {porcentagem}%;"></div></div>
                    <div style="font-size: 11px; color: #775a46; text-align: right; font-weight: 800;">Verificação: {itens_marcados}/{total_itens} ({porcentagem}%)</div>
                </div>
                """
                col_alvo = col_esq if idx % 2 == 0 else col_dir
                with col_alvo:
                    st.markdown(card_html.replace('\n', ''), unsafe_allow_html=True)
                    if st.button("🔍 Abrir Gaveta de Montagem", key=f"abrir_montagem_{p['id']}", use_container_width=True):
                        st.session_state.pedido_em_montagem = p['id']
                        st.rerun()

st.write("")
st.divider()
st.caption("🏭 Controle Oficial de Produção - Doce Cesta Brasília")
