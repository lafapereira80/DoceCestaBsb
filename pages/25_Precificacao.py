import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path

from services.cesta_service import listar_cestas
from services.estoque_service import (
    garantir_schema, sincronizar_catalogo, listar_itens, atualizar_item, salvar_insumos_cesta,
)
from services.precificacao_service import (
    MODOS, ARREDONDAMENTOS, calcular, salvar_parametros, preco_para_margem,
    arredondar, resultado, aplicar_preco, historico,
)
from utils.menu import configurar_pagina, menu_lateral
from utils.permissao import administrador
from utils.ui import page_header, kpi_grid, secao, alerta, empty_state, brl, esc

st.set_page_config(page_title="Precificação de Cestas", page_icon="💲", layout="wide")
configurar_pagina()
menu_lateral()
administrador()

page_header("Precificação de cestas", "Custo real, margem líquida e preço sugerido por cesta.", "💲",
            ["Catálogo", "Precificação"], "ok")

try:
    garantir_schema()
    if not st.session_state.get("_estoque_sync"):
        sincronizar_catalogo()
        st.session_state["_estoque_sync"] = True
except Exception as erro:
    st.error(f"Não foi possível preparar as tabelas de estoque/custos: {erro}")
    st.stop()


# =====================================================
# VISÃO GERAL (cacheada — recalcula ao salvar)
# =====================================================
@st.cache_data(ttl=120, show_spinner="Calculando custos das cestas…")
def _visao():
    linhas = []
    for c in listar_cestas():
        r = calcular(c["id"])
        p = r["params"]
        preco = c.get("preco")
        custo = r["custo_total"]
        res = resultado(float(preco), custo, p["taxa_pagamento_pct"], p["imposto_pct"]) if preco else None
        if preco is None:
            status = "💬 Sob consulta"
        elif custo <= 0:
            status = "⚪ Sem custo"
        elif res["margem_pct"] < 0:
            status = "🔴 Prejuízo"
        elif res["margem_pct"] < p["margem_alvo_pct"]:
            status = "🟡 Abaixo da meta"
        else:
            status = "🟢 Na meta"
        linhas.append({
            "id": c["id"], "Cesta": c["nome"], "Ativa": bool(c.get("ativa", True)),
            "Preço atual": float(preco) if preco is not None else None,
            "Custo": round(custo, 2), "Preço sugerido": r["preco_sugerido"],
            "Margem líquida": round(res["margem_pct"], 1) if res else None,
            "Meta": p["margem_alvo_pct"], "Lucro": round(res["lucro"], 2) if res else None,
            "Ajuste": round(r["preco_sugerido"] - float(preco), 2) if preco is not None else None,
            "Status": status, "sem_custo": r["sem_custo"],
        })
    return linhas


def _recarregar():
    _visao.clear()
    st.rerun()


try:
    visao = _visao()
except Exception as erro:
    st.error(f"Erro ao carregar cestas: {erro}")
    st.stop()

aba_geral, aba_hist, aba_guia = st.tabs(["📊 Visão geral", "🕘 Histórico de preços", "📘 Guia"])

# =====================================================
# ABA 1 — VISÃO GERAL + DETALHE
# =====================================================
with aba_geral:
    if not visao:
        empty_state("Nenhuma cesta cadastrada", "Cadastre cestas em Cestas e kits para precificar.", "🧺")
        st.stop()

    df = pd.DataFrame(visao)
    com_preco = df[df["Margem líquida"].notna()]
    sem_custo_total = sorted({n for v in visao for n in v["sem_custo"]})
    kpi_grid([
        {"icone": "🧺", "rotulo": "Cestas", "valor": len(df), "tom": "brand"},
        {"icone": "📈", "rotulo": "Margem líquida média",
         "valor": float(com_preco["Margem líquida"].mean()) if len(com_preco) else 0.0,
         "casas": 1, "sufixo": "%", "tom": "ok"},
        {"icone": "🟡", "rotulo": "Abaixo da meta",
         "valor": int(df["Status"].isin(["🟡 Abaixo da meta", "🔴 Prejuízo"]).sum()), "tom": "warn"},
        {"icone": "❓", "rotulo": "Itens sem custo", "valor": len(sem_custo_total), "tom": "danger",
         "dica": "Preencha em «Composição»"},
    ])

    secao("Todas as cestas", "Clique na caixa à esquerda de uma linha para detalhar.", "📋")
    f1, f2 = st.columns([2, 1])
    busca = f1.text_input("Buscar cesta", placeholder="Digite o nome…", label_visibility="collapsed")
    filtro = f2.pills("Status", ["Todas", "🟢 Na meta", "🟡 Abaixo da meta", "🔴 Prejuízo", "⚪ Sem custo"],
                      default="Todas", label_visibility="collapsed")
    dff = df.copy()
    if busca:
        dff = dff[dff["Cesta"].str.contains(busca, case=False, na=False)]
    if filtro and filtro != "Todas":
        dff = dff[dff["Status"] == filtro]
    dff = dff.reset_index(drop=True)

    cfg = {
        "Preço atual": st.column_config.NumberColumn("Preço atual", format="R$ %.2f"),
        "Custo": st.column_config.NumberColumn("Custo", format="R$ %.2f"),
        "Preço sugerido": st.column_config.NumberColumn("Sugerido", format="R$ %.2f"),
        "Margem líquida": st.column_config.ProgressColumn("Margem líquida", format="%.1f%%", min_value=0, max_value=60),
        "Meta": st.column_config.NumberColumn("Meta", format="%.0f%%"),
        "Lucro": st.column_config.NumberColumn("Lucro/cesta", format="R$ %.2f"),
        "Ajuste": st.column_config.NumberColumn("Ajuste p/ meta", format="%+.2f"),
        "Ativa": st.column_config.CheckboxColumn("Ativa"),
        "Status": st.column_config.TextColumn("Status"),
    }
    cols = ["Cesta", "Ativa", "Status", "Preço atual", "Custo", "Lucro", "Margem líquida", "Meta", "Preço sugerido", "Ajuste"]
    selecionada = None
    try:
        ev = st.dataframe(dff[cols], column_config=cfg, hide_index=True, width="stretch", height=min(420, 78 + 36 * len(dff)),
                          on_select="rerun", selection_mode="single-row", key="prec_tabela")
        if ev.selection.rows:
            selecionada = dff.iloc[ev.selection.rows[0]]["id"]
    except TypeError:
        st.dataframe(dff[cols], column_config=cfg, hide_index=True, width="stretch")
    if dff.empty:
        st.info("Nenhuma cesta com esse filtro.")
        st.stop()
    if selecionada is None:
        nomes = {r["id"]: r["Cesta"] for _, r in dff.iterrows()}
        selecionada = st.selectbox("Cesta para detalhar", list(nomes), format_func=nomes.get, key="prec_sel_fallback")

    # -------------------------------------------------
    # DETALHE DA CESTA
    # -------------------------------------------------
    cesta = next(c for c in listar_cestas() if c["id"] == selecionada)
    cid = str(cesta["id"])
    base = calcular(cesta["id"])
    grupos, insumos = base["grupos"], base["insumos"]
    p0 = base["params"]

    st.divider()
    secao(f"{cesta['nome']}", "Ajuste os parâmetros: o preço sugerido recalcula na hora.", "🧮")

    col_p, col_r = st.columns([1, 1.5], gap="large")
    with col_p:
        with st.container(border=True):
            st.markdown("**Parâmetros**")
            a, b = st.columns(2)
            mo = a.number_input("Mão de obra (R$)", 0.0, step=1.0, value=p0["mao_de_obra"], format="%.2f", key=f"mo_{cid}")
            ou = b.number_input("Outros custos (R$)", 0.0, step=1.0, value=p0["outros_custos"], format="%.2f", key=f"ou_{cid}")
            fr = a.number_input("Frete absorvido (R$)", 0.0, step=1.0, value=p0["frete_absorvido"], format="%.2f", key=f"fr_{cid}")
            mg = b.number_input("Margem líquida alvo (%)", 0.0, 90.0, step=1.0, value=p0["margem_alvo_pct"], format="%.1f", key=f"mg_{cid}")
            tx = a.number_input("Taxa de pagamento (%)", 0.0, 30.0, step=0.1, value=p0["taxa_pagamento_pct"], format="%.2f", key=f"tx_{cid}")
            im = b.number_input("Impostos (%)", 0.0, 40.0, step=0.5, value=p0["imposto_pct"], format="%.2f", key=f"im_{cid}")
            modo = st.selectbox("Custo das opções de escolha", list(MODOS), index=list(MODOS).index(p0["modo_custo"]),
                                format_func=MODOS.get, key=f"md_{cid}",
                                help="Quando o cliente escolhe itens entre várias opções, qual custo considerar.")
            arr = st.selectbox("Arredondamento", list(ARREDONDAMENTOS), index=list(ARREDONDAMENTOS).index(p0["arredondamento"]),
                               format_func=ARREDONDAMENTOS.get, key=f"ar_{cid}")
            live = {"mao_de_obra": mo, "outros_custos": ou, "frete_absorvido": fr, "margem_alvo_pct": mg,
                    "taxa_pagamento_pct": tx, "imposto_pct": im, "modo_custo": modo, "arredondamento": arr}
            if st.button("💾 Salvar parâmetros", key=f"sp_{cid}", width="stretch"):
                salvar_parametros(cid, live)
                st.toast("Parâmetros salvos.")
                _recarregar()

    calc = calcular(cesta["id"], params=live, grupos=grupos, insumos=insumos)
    custo, sugerido = calc["custo_total"], calc["preco_sugerido"]
    preco_atual = float(cesta["preco"]) if cesta.get("preco") is not None else None
    res_sug = resultado(sugerido, custo, tx, im)
    res_atual = resultado(preco_atual, custo, tx, im) if preco_atual else None

    with col_r:
        m1, m2, m3 = st.columns(3)
        m1.metric("Custo total", brl(custo))
        m2.metric("Preço sugerido", brl(sugerido), f"margem {res_sug['margem_pct']:.1f}%")
        m3.metric("Preço atual", brl(preco_atual) if preco_atual else "Sob consulta",
                  f"margem {res_atual['margem_pct']:.1f}%" if res_atual else None,
                  delta_color="normal" if (res_atual and res_atual["margem_pct"] >= mg) else "inverse")
        if calc["sem_custo"]:
            alerta(f"<b>{len(calc['sem_custo'])} item(ns) sem custo</b> — o custo da cesta está subestimado: "
                   f"{esc(', '.join(calc['sem_custo'][:6]))}{'…' if len(calc['sem_custo']) > 6 else ''}.", "warn")
        taxas = sugerido * (tx + im) / 100
        fig = go.Figure(go.Waterfall(
            orientation="v", x=["Itens", "Embalagem/insumos", "Mão de obra", "Outros + frete", "Taxas e impostos", "Lucro", "Preço"],
            measure=["relative"] * 6 + ["total"],
            y=[calc["custo_itens"], calc["custo_insumos"], mo, ou + fr, taxas, max(res_sug["lucro"], 0), 0],
            text=[brl(v) for v in [calc["custo_itens"], calc["custo_insumos"], mo, ou + fr, taxas, max(res_sug["lucro"], 0), sugerido]],
            textposition="outside", connector={"line": {"color": "#d2bfae"}},
            increasing={"marker": {"color": "#8c6245"}}, totals={"marker": {"color": "#2e7d32"}},
        ))
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), showlegend=False,
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", yaxis=dict(visible=False))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

        st.markdown("**Aplicar preço**")
        pa, pb = st.columns([2, 1])
        preco_final = pa.number_input("Novo preço (R$)", 0.0, step=0.5, format="%.2f", value=float(sugerido),
                                      key=f"pf_{cid}_{sugerido:.2f}", label_visibility="collapsed")
        r_final = resultado(preco_final, custo, tx, im)
        pb.markdown(f"<div style='padding-top:8px'>margem <b>{r_final['margem_pct']:.1f}%</b> · lucro <b>{brl(r_final['lucro'])}</b></div>",
                    unsafe_allow_html=True)
        if st.button("✅ Aplicar na vitrine", type="primary", key=f"ap_{cid}", disabled=preco_final <= 0, width="stretch"):
            aplicar_preco(cesta, preco_final, custo, r_final["margem_pct"])
            st.toast(f"Preço de «{cesta['nome']}» atualizado para {brl(preco_final)}.")
            _recarregar()
        promo = cesta.get("preco_promocional")
        if cesta.get("em_promocao") and promo:
            rp = resultado(float(promo), custo, tx, im)
            alerta(f"Preço promocional {brl(promo)}: margem <b>{rp['margem_pct']:.1f}%</b> (lucro {brl(rp['lucro'])}).",
                   "danger" if rp["margem_pct"] < 0 else "warn", "🏷️")

    t_comp, t_ins, t_sim = st.tabs(["🍓 Composição e custos", "📦 Embalagem e insumos", "🎚️ Simulador de margem"])

    # ---------------- composição editável
    with t_comp:
        linhas = []
        for g in grupos:
            tipo = "Fixo" if len(g["itens"]) <= max(1, g["max"]) else f"Escolha ({g['max']} de {len(g['itens'])})"
            for i in g["itens"]:
                linhas.append({"item_id": i["item_id"], "Grupo": g["categoria"], "Tipo": tipo, "Item": i["nome"],
                               "Custo unit.": i["custo_unitario"], "Perda %": i["perda_pct"],
                               "Custo efetivo": i["custo"], "Estoque": i["estoque"]})
        if not linhas:
            empty_state("Cesta sem produtos configurados", "Configure os itens em Cestas e kits → Configurar.", "🧺")
        else:
            orig = pd.DataFrame(linhas)
            editado = st.data_editor(
                orig, hide_index=True, width="stretch", key=f"ed_comp_{cid}", num_rows="fixed",
                disabled=["Grupo", "Tipo", "Item", "Custo efetivo", "Estoque"], column_order=["Grupo", "Tipo", "Item", "Custo unit.", "Perda %", "Custo efetivo", "Estoque"],
                column_config={
                    "Custo unit.": st.column_config.NumberColumn("Custo unit. (R$)", min_value=0.0, step=0.01, format="R$ %.2f", required=True),
                    "Perda %": st.column_config.NumberColumn("Perda %", min_value=0.0, max_value=99.0, step=0.5, format="%.1f%%"),
                    "Custo efetivo": st.column_config.NumberColumn("Custo efetivo", format="R$ %.2f", help="Custo ÷ (1 − perda)"),
                    "Estoque": st.column_config.NumberColumn("Estoque", format="%.1f"),
                })
            if st.button("💾 Salvar custos dos itens", key=f"sv_comp_{cid}"):
                n = 0
                for i in range(len(orig)):
                    a, b = orig.iloc[i], editado.iloc[i]
                    if a["item_id"] and (abs(a["Custo unit."] - b["Custo unit."]) > 1e-9 or abs(a["Perda %"] - b["Perda %"]) > 1e-9):
                        atualizar_item(a["item_id"], {"custo_unitario": float(b["Custo unit."]), "perda_pct": float(b["Perda %"])})
                        n += 1
                st.toast(f"{n} item(ns) atualizado(s).")
                _recarregar()
            st.caption("O custo do item é compartilhado: alterar aqui reflete em todas as cestas que o usam e no Estoque.")

    # ---------------- insumos/embalagem
    with t_ins:
        todos = [i for i in listar_itens(True)]
        insumos_disp = [i for i in todos if i["tipo"] == "insumo"]
        if not insumos_disp:
            empty_state("Nenhum insumo cadastrado", "Cadastre caixa, laço, cartão etc. em Estoque → Itens.", "📦")
        else:
            rotulo = {i["id"]: f"{i['nome']} ({i['unidade']})" for i in insumos_disp}
            inv = {v: k for k, v in rotulo.items()}
            atual = pd.DataFrame([{"Item": rotulo[l["item_id"]], "Quantidade": float(l["quantidade"])}
                                  for l in insumos if l["item_id"] in rotulo] or [], columns=["Item", "Quantidade"])
            ed = st.data_editor(
                atual, num_rows="dynamic", hide_index=True, width="stretch", key=f"ed_ins_{cid}",
                column_config={
                    "Item": st.column_config.SelectboxColumn("Item", options=list(inv), required=True),
                    "Quantidade": st.column_config.NumberColumn("Qtd por cesta", min_value=0.0, step=1.0, default=1.0, format="%.2f"),
                })
            if st.button("💾 Salvar embalagem", key=f"sv_ins_{cid}"):
                salvar_insumos_cesta(cid, [(inv.get(r["Item"]), r["Quantidade"]) for _, r in ed.iterrows() if r["Item"]])
                st.toast("Embalagem salva.")
                _recarregar()
            st.caption(f"Custo atual de embalagem/insumos: **{brl(calc['custo_insumos'])}** por cesta.")

    # ---------------- simulador
    with t_sim:
        alvo_lista = sorted({10, 15, 20, 25, 30, 35, 40, 45, 50, int(mg)})
        sim = []
        for m in alvo_lista:
            bruto = preco_para_margem(custo, m, tx, im)
            pr = arredondar(bruto, arr) if bruto != float("inf") else 0.0
            r = resultado(pr, custo, tx, im)
            sim.append({"Margem alvo": float(m), "Preço": pr, "Lucro": r["lucro"], "Margem real": r["margem_pct"],
                        "Markup": r["markup"], "vs atual": (pr - preco_atual) if preco_atual else None})
        st.dataframe(pd.DataFrame(sim), hide_index=True, width="stretch", column_config={
            "Margem alvo": st.column_config.NumberColumn(format="%.0f%%"),
            "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
            "Lucro": st.column_config.NumberColumn("Lucro/cesta", format="R$ %.2f"),
            "Margem real": st.column_config.ProgressColumn("Margem real", format="%.1f%%", min_value=0, max_value=60),
            "Markup": st.column_config.NumberColumn(format="%.2fx"),
            "vs atual": st.column_config.NumberColumn("vs preço atual", format="%+.2f"),
        })
        if custo > 0 and tx + im < 100:
            pe = custo / (1 - (tx + im) / 100)
            st.caption(f"Preço de equilíbrio (lucro zero): **{brl(pe)}** — abaixo disso a cesta dá prejuízo.")

# =====================================================
# ABA 2 — HISTÓRICO
# =====================================================
with aba_hist:
    try:
        hist = historico()
    except Exception as erro:
        hist, _ = [], st.error(f"Erro: {erro}")
    if not hist:
        empty_state("Sem alterações de preço registradas", "Quando você aplicar um preço aqui, o histórico aparece nesta tabela.", "🕘")
    else:
        dh = pd.DataFrame(hist)
        dh["criado_em"] = pd.to_datetime(dh["criado_em"], utc=True).dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None)
        dh = dh.rename(columns={"criado_em": "Quando", "cesta_nome": "Cesta", "preco_anterior": "Antes", "preco_novo": "Depois",
                                "custo_total": "Custo", "margem_pct": "Margem", "usuario": "Usuário"})
        st.dataframe(dh[["Quando", "Cesta", "Antes", "Depois", "Custo", "Margem", "Usuário"]], hide_index=True, width="stretch", column_config={
            "Quando": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
            "Antes": st.column_config.NumberColumn(format="R$ %.2f"), "Depois": st.column_config.NumberColumn(format="R$ %.2f"),
            "Custo": st.column_config.NumberColumn(format="R$ %.2f"), "Margem": st.column_config.NumberColumn(format="%.1f%%")})
        st.download_button("⬇️ Baixar CSV", dh.to_csv(index=False).encode("utf-8-sig"), "historico_precos.csv", "text/csv")

# =====================================================
# ABA 3 — GUIA
# =====================================================
with aba_guia:
    guia = Path(__file__).resolve().parent.parent / "docs" / "guia_precificacao.md"
    st.markdown(guia.read_text(encoding="utf-8") if guia.exists() else "Guia não encontrado.")
