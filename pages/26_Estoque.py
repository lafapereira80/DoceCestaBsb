import pandas as pd
import streamlit as st
from datetime import date, timedelta

from services.cesta_service import listar_cestas
from services.estoque_service import (
    UNIDADES, garantir_schema, sincronizar_catalogo, listar_itens, listar_movimentos, criar_insumo,
    atualizar_item, movimentar, lancar_lote, ajustar_contagem, composicao_cesta, insumos_cesta,
)
from utils.menu import configurar_pagina, menu_lateral
from utils.permissao import administrador_operador
from utils.ui import page_header, kpi_grid, secao, alerta, empty_state, brl

st.set_page_config(page_title="Controle de Estoque", page_icon="📦", layout="wide")
configurar_pagina()
menu_lateral()
administrador_operador()

page_header("Controle de estoque", "Produtos e insumos, entradas, baixas e inventário com histórico completo.", "📦",
            ["Operação", "Estoque"], "ok")

try:
    garantir_schema()
    if not st.session_state.get("_estoque_sync"):
        sincronizar_catalogo()
        st.session_state["_estoque_sync"] = True
    itens = listar_itens()
except Exception as erro:
    st.error(f"Não foi possível carregar o estoque: {erro}")
    st.stop()

ativos = [i for i in itens if i["ativo"]]
rot = {i["id"]: f"{i['nome']} ({i['unidade']})" for i in ativos}
inv = {v: k for k, v in rot.items()}
por_id = {i["id"]: i for i in itens}


def _status(i):
    est, mini = float(i["estoque_atual"]), float(i["estoque_minimo"])
    if est <= 0:
        return "🔴 Zerado"
    if mini > 0 and est <= mini:
        return "🟠 Baixo"
    return "🟢 OK"


def _ok(msg):
    st.toast(msg)
    st.rerun()


# =====================================================
# KPIs
# =====================================================
df = pd.DataFrame(ativos) if ativos else pd.DataFrame(columns=["nome"])
if ativos:
    for c in ["estoque_atual", "estoque_minimo", "custo_unitario", "custo_efetivo", "perda_pct"]:
        df[c] = df[c].astype(float)
    df["Status"] = [_status(i) for i in ativos]
    df["Valor em estoque"] = df["estoque_atual"] * df["custo_unitario"]
kpi_grid([
    {"icone": "📦", "rotulo": "Itens ativos", "valor": len(ativos), "tom": "brand"},
    {"icone": "💰", "rotulo": "Valor em estoque", "valor": float(df["Valor em estoque"].sum()) if ativos else 0.0,
     "prefixo": "R$ ", "casas": 2, "tom": "ok"},
    {"icone": "🟠", "rotulo": "Estoque baixo", "valor": int((df["Status"] == "🟠 Baixo").sum()) if ativos else 0, "tom": "warn"},
    {"icone": "🔴", "rotulo": "Zerados", "valor": int((df["Status"] == "🔴 Zerado").sum()) if ativos else 0, "tom": "danger"},
])

t_est, t_ent, t_prod, t_inv, t_itens, t_mov = st.tabs(
    ["📦 Estoque", "➕ Entrada de compra", "🏭 Baixa por cesta", "📝 Inventário", "🧾 Itens e custos", "🕘 Movimentações"])


# =====================================================
# DIÁLOGO DE MOVIMENTAÇÃO RÁPIDA
# =====================================================
@st.dialog("Movimentar estoque")
def _dialogo(item):
    st.markdown(f"**{item['nome']}** · saldo atual: **{float(item['estoque_atual']):g} {item['unidade']}**")
    tipo = st.radio("Tipo", ["entrada", "saida", "perda"], horizontal=True,
                    format_func={"entrada": "➕ Entrada", "saida": "➖ Saída", "perda": "🗑️ Perda"}.get)
    qtd = st.number_input(f"Quantidade ({item['unidade']})", min_value=0.0, step=1.0, format="%.3f")
    total = None
    if tipo == "entrada":
        total = st.number_input("Valor total pago (R$) — opcional", min_value=0.0, step=1.0, format="%.2f",
                                help="Atualiza o custo do item pela média ponderada.")
    motivo = st.text_input("Motivo / observação", placeholder="Ex.: compra Atacadão, quebra no transporte…")
    if st.button("Confirmar", type="primary", width="stretch", disabled=qtd <= 0):
        try:
            movimentar(item["id"], tipo, qtd, (total / qtd) if (total and qtd) else None, motivo or None)
            _ok("Movimentação registrada.")
        except Exception as e:
            st.error(str(e))


# =====================================================
# ABA ESTOQUE
# =====================================================
with t_est:
    if not ativos:
        empty_state("Nenhum item no estoque", "Cadastre produtos ou crie insumos na aba «Itens e custos».", "📦")
    else:
        f1, f2, f3 = st.columns([2, 1.2, 1.6])
        busca = f1.text_input("Buscar", placeholder="Buscar item…", label_visibility="collapsed")
        tipo_f = f2.segmented_control("Tipo", ["Todos", "produto", "insumo"], default="Todos",
                                      format_func=lambda x: {"Todos": "Todos", "produto": "Produtos", "insumo": "Insumos"}[x],
                                      label_visibility="collapsed")
        st_f = f3.pills("Status", ["Todos", "🔴 Zerado", "🟠 Baixo", "🟢 OK"], default="Todos", label_visibility="collapsed")
        v = df.copy()
        if busca:
            v = v[v["nome"].str.contains(busca, case=False, na=False)]
        if tipo_f and tipo_f != "Todos":
            v = v[v["tipo"] == tipo_f]
        if st_f and st_f != "Todos":
            v = v[v["Status"] == st_f]
        v = v.reset_index(drop=True)
        maximo = max(float(df["estoque_atual"].max()), 1.0)
        cfg = {
            "nome": st.column_config.TextColumn("Item", width="large"),
            "tipo": st.column_config.TextColumn("Tipo", width="small"),
            "unidade": st.column_config.TextColumn("Un.", width="small"),
            "estoque_atual": st.column_config.ProgressColumn("Estoque", format="%.1f", min_value=0, max_value=maximo),
            "estoque_minimo": st.column_config.NumberColumn("Mínimo", format="%.1f"),
            "custo_unitario": st.column_config.NumberColumn("Custo unit.", format="R$ %.2f"),
            "Valor em estoque": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
            "fornecedor": st.column_config.TextColumn("Fornecedor"),
        }
        cols = ["nome", "Status", "tipo", "estoque_atual", "unidade", "estoque_minimo", "custo_unitario", "Valor em estoque", "fornecedor"]
        sel = None
        try:
            ev = st.dataframe(v[cols], column_config=cfg, hide_index=True, width="stretch", height=min(520, 78 + 36 * len(v)),
                              on_select="rerun", selection_mode="single-row", key="est_tabela")
            if ev.selection.rows:
                sel = v.iloc[ev.selection.rows[0]]
        except TypeError:
            st.dataframe(v[cols], column_config=cfg, hide_index=True, width="stretch")
        if sel is not None:
            if st.button(f"➕➖ Movimentar «{sel['nome']}»", type="primary"):
                _dialogo(por_id[sel["id"]])
        else:
            st.caption("Selecione uma linha para registrar entrada, saída ou perda.")

        baixos = df[(df["estoque_minimo"] > 0) & (df["estoque_atual"] <= df["estoque_minimo"])].copy()
        with st.expander(f"🛒 Lista de compras sugerida ({len(baixos)})", expanded=False):
            if baixos.empty:
                st.success("Nada abaixo do estoque mínimo.")
            else:
                baixos["Comprar"] = (baixos["estoque_minimo"] * 2 - baixos["estoque_atual"]).clip(lower=0)
                baixos["Estimativa"] = baixos["Comprar"] * baixos["custo_unitario"]
                lista = baixos[["nome", "unidade", "estoque_atual", "estoque_minimo", "Comprar", "Estimativa", "fornecedor"]]
                st.dataframe(lista, hide_index=True, width="stretch", column_config={
                    "nome": "Item", "unidade": "Un.", "estoque_atual": st.column_config.NumberColumn("Atual", format="%.1f"),
                    "estoque_minimo": st.column_config.NumberColumn("Mínimo", format="%.1f"),
                    "Comprar": st.column_config.NumberColumn("Comprar", format="%.1f"),
                    "Estimativa": st.column_config.NumberColumn("Estimativa", format="R$ %.2f"), "fornecedor": "Fornecedor"})
                st.caption(f"Reposição até 2× o mínimo · estimativa total: **{brl(baixos['Estimativa'].sum())}**")
                texto = "*Lista de compras*\n" + "\n".join(f"• {r.nome}: {r.Comprar:g} {r.unidade}" for r in baixos.itertuples())
                st.code(texto, language=None)
                st.download_button("⬇️ Baixar CSV", lista.to_csv(index=False).encode("utf-8-sig"), "lista_compras.csv", "text/csv")

# =====================================================
# ENTRADA DE COMPRA EM LOTE
# =====================================================
with t_ent:
    secao("Entrada de compra", "Lance várias linhas de uma vez. O custo do item é atualizado pela média ponderada.", "➕")
    if not ativos:
        empty_state("Sem itens", "Cadastre itens primeiro.", "📦")
    else:
        v_ent = st.session_state.get("ver_entrada", 0)
        modelo = pd.DataFrame([{"Item": None, "Quantidade": 0.0, "Valor total (R$)": 0.0}])
        ed = st.data_editor(modelo, num_rows="dynamic", hide_index=True, width="stretch", key=f"ed_entrada_{v_ent}",
                            column_config={
                                "Item": st.column_config.SelectboxColumn("Item", options=sorted(inv), required=True),
                                "Quantidade": st.column_config.NumberColumn("Quantidade", min_value=0.0, step=1.0, format="%.3f"),
                                "Valor total (R$)": st.column_config.NumberColumn("Valor total (R$)", min_value=0.0, step=1.0, format="R$ %.2f"),
                            })
        ref = st.text_input("Referência (nota / fornecedor)", placeholder="Ex.: NF 1234 — Atacadão")
        validas = ed[(ed["Item"].notna()) & (ed["Quantidade"] > 0)]
        if not validas.empty:
            st.caption(f"{len(validas)} linha(s) · total da compra: **{brl(validas['Valor total (R$)'].sum())}**")
        if st.button("✅ Registrar entradas", type="primary", disabled=validas.empty):
            try:
                n = lancar_lote([{
                    "item_id": inv[r["Item"]], "tipo": "entrada", "quantidade": float(r["Quantidade"]),
                    "custo_unitario": (float(r["Valor total (R$)"]) / float(r["Quantidade"])) if r["Valor total (R$)"] > 0 else None,
                    "motivo": "Compra", "referencia": ref or None} for _, r in validas.iterrows()])
                st.session_state["ver_entrada"] = v_ent + 1
                _ok(f"{n} entrada(s) registrada(s).")
            except Exception as e:
                st.error(str(e))

# =====================================================
# BAIXA POR CESTA PRODUZIDA
# =====================================================
with t_prod:
    secao("Baixa por cesta produzida", "Desconta do estoque os itens e a embalagem das cestas montadas.", "🏭")
    cestas = listar_cestas()
    if not cestas:
        empty_state("Sem cestas", "Cadastre cestas primeiro.", "🧺")
    else:
        c1, c2, c3 = st.columns([2, 1, 2])
        cesta = c1.selectbox("Cesta", cestas, format_func=lambda c: c["nome"], key="bx_cesta")
        qtd_c = c2.number_input("Qtd. de cestas", 1, 500, 1, key="bx_qtd")
        ref_b = c3.text_input("Referência", placeholder="Pedido / lote", key="bx_ref")
        grupos, ins = composicao_cesta(cesta["id"]), insumos_cesta(cesta["id"])
        consumo, erros = {}, []

        def _add(item_id, q):
            if item_id:
                consumo[item_id] = consumo.get(item_id, 0.0) + q

        for gi, g in enumerate(grupos):
            vagas = max(1, g["max"]) * qtd_c
            if len(g["itens"]) <= max(1, g["max"]):
                for i in g["itens"]:
                    _add(i["item_id"], i["quantidade"] * qtd_c)
            else:
                st.markdown(f"**{g['categoria']}** — distribua **{vagas}** unidade(s) entre as opções")
                base = pd.DataFrame([{"Item": i["nome"], "Usado": 0.0, "Estoque": i["estoque"]} for i in g["itens"]])
                e = st.data_editor(base, hide_index=True, width="stretch", disabled=["Item", "Estoque"],
                                   key=f"bx_{cesta['id']}_{gi}_{qtd_c}",
                                   column_config={"Usado": st.column_config.NumberColumn("Usado", min_value=0.0, step=1.0, format="%.1f"),
                                                  "Estoque": st.column_config.NumberColumn(format="%.1f")})
                soma = float(e["Usado"].sum())
                if abs(soma - vagas) > 1e-9:
                    erros.append(f"{g['categoria']}: informado {soma:g} de {vagas:g}")
                for i, (_, r) in zip(g["itens"], e.iterrows()):
                    _add(i["item_id"], float(r["Usado"]))
        for l in ins:
            _add(l["item_id"], float(l["quantidade"]) * qtd_c)

        linhas_res = [{"Item": rot.get(k, por_id.get(k, {}).get("nome", "?")), "Baixar": q,
                       "Saldo": float(por_id[k]["estoque_atual"]),
                       "Situação": "✅" if float(por_id[k]["estoque_atual"]) >= q else "⚠️ Insuficiente"}
                      for k, q in consumo.items() if k in por_id and q > 0]
        if linhas_res:
            res = pd.DataFrame(linhas_res)
            st.dataframe(res, hide_index=True, width="stretch", column_config={
                "Baixar": st.column_config.NumberColumn(format="%.1f"), "Saldo": st.column_config.NumberColumn(format="%.1f")})
            falta = res[res["Situação"] != "✅"]
            if not falta.empty:
                alerta("Estoque insuficiente para: <b>" + ", ".join(falta["Item"]) + "</b>.", "danger")
        for er in erros:
            st.warning(er)
        if st.button("✅ Confirmar baixa", type="primary", disabled=(not linhas_res or bool(erros))):
            try:
                n = lancar_lote([{"item_id": k, "tipo": "saida", "quantidade": q,
                                  "motivo": f"Produção: {qtd_c}× {cesta['nome']}", "referencia": ref_b or None}
                                 for k, q in consumo.items() if q > 0])
                _ok(f"Baixa registrada ({n} itens).")
            except Exception as e:
                st.error(str(e))

# =====================================================
# INVENTÁRIO (CONTAGEM FÍSICA)
# =====================================================
with t_inv:
    secao("Inventário", "Informe a contagem física; só as diferenças viram ajuste.", "📝")
    if ativos:
        v_inv = st.session_state.get("ver_inv", 0)
        base = pd.DataFrame([{"id": i["id"], "Item": i["nome"], "Un.": i["unidade"],
                              "Sistema": float(i["estoque_atual"]), "Contagem": float(i["estoque_atual"])} for i in ativos])
        e = st.data_editor(base, hide_index=True, width="stretch", disabled=["Item", "Un.", "Sistema"], key=f"ed_inv_{v_inv}",
                           column_order=["Item", "Un.", "Sistema", "Contagem"],
                           column_config={"Sistema": st.column_config.NumberColumn(format="%.1f"),
                                          "Contagem": st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%.1f", required=True)})
        dif = e[(e["Contagem"] - e["Sistema"]).abs() > 1e-9]
        if not dif.empty:
            st.dataframe(dif.assign(Diferença=dif["Contagem"] - dif["Sistema"])[["Item", "Sistema", "Contagem", "Diferença"]],
                         hide_index=True, width="stretch", column_config={"Diferença": st.column_config.NumberColumn(format="%+.1f")})
        if st.button(f"✅ Aplicar {len(dif)} ajuste(s)", type="primary", disabled=dif.empty):
            n = ajustar_contagem({r["id"]: r["Contagem"] for _, r in dif.iterrows()})
            st.session_state["ver_inv"] = v_inv + 1
            _ok(f"{n} ajuste(s) aplicado(s).")

# =====================================================
# ITENS E CUSTOS
# =====================================================
with t_itens:
    secao("Itens e custos", "Edite custo, perda, mínimo e fornecedor. Produtos do catálogo são sincronizados automaticamente.", "🧾")
    if st.button("🔄 Sincronizar com catálogo"):
        _ok(f"{sincronizar_catalogo()} produto(s) novo(s) importado(s).")
    if itens:
        base = pd.DataFrame([{
            "id": i["id"], "Ativo": bool(i["ativo"]), "Item": i["nome"], "Tipo": i["tipo"], "Un.": i["unidade"],
            "Custo unit.": float(i["custo_unitario"]), "Perda %": float(i["perda_pct"]),
            "Custo efetivo": float(i["custo_efetivo"]), "Mínimo": float(i["estoque_minimo"]),
            "Fornecedor": i.get("fornecedor") or ""} for i in itens])
        e = st.data_editor(base, hide_index=True, width="stretch", key="ed_itens", num_rows="fixed",
                           disabled=["id", "Item", "Tipo", "Custo efetivo"],
                           column_order=["Ativo", "Item", "Tipo", "Un.", "Custo unit.", "Perda %", "Custo efetivo", "Mínimo", "Fornecedor"],
                           column_config={
                               "Ativo": st.column_config.CheckboxColumn("Ativo"),
                               "Un.": st.column_config.SelectboxColumn("Un.", options=UNIDADES, required=True),
                               "Custo unit.": st.column_config.NumberColumn(min_value=0.0, step=0.01, format="R$ %.2f"),
                               "Perda %": st.column_config.NumberColumn(min_value=0.0, max_value=99.0, step=0.5, format="%.1f%%"),
                               "Custo efetivo": st.column_config.NumberColumn(format="R$ %.2f"),
                               "Mínimo": st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%.1f")})
        if st.button("💾 Salvar alterações", type="primary"):
            n = 0
            for a, b in zip(base.to_dict("records"), e.to_dict("records")):
                campos = {}
                for col, k in [("Ativo", "ativo"), ("Un.", "unidade"), ("Custo unit.", "custo_unitario"),
                               ("Perda %", "perda_pct"), ("Mínimo", "estoque_minimo")]:
                    if a[col] != b[col]:
                        campos[k] = b[col]
                if (a["Fornecedor"] or "") != (b["Fornecedor"] or ""):
                    campos["fornecedor"] = b["Fornecedor"] or None
                if campos:
                    atualizar_item(a["id"], campos)
                    n += 1
            _ok(f"{n} item(ns) atualizado(s).")

    with st.expander("➕ Novo insumo (caixa, laço, cartão, fita…)"):
        with st.form("novo_insumo", clear_on_submit=True):
            a, b, c = st.columns([2, 1, 1])
            nome = a.text_input("Nome *")
            un = b.selectbox("Unidade", UNIDADES)
            custo = c.number_input("Custo unit. (R$)", 0.0, step=0.1, format="%.2f")
            d, f, g = st.columns(3)
            mini = d.number_input("Estoque mínimo", 0.0, step=1.0)
            perda = f.number_input("Perda %", 0.0, 99.0, step=0.5)
            forn = g.text_input("Fornecedor")
            if st.form_submit_button("Criar insumo", type="primary"):
                if not nome.strip():
                    st.error("Informe o nome.")
                else:
                    try:
                        criar_insumo(nome, un, custo, mini, forn, perda)
                        _ok("Insumo criado.")
                    except Exception as ex:
                        st.error(str(ex))

# =====================================================
# MOVIMENTAÇÕES
# =====================================================
with t_mov:
    secao("Histórico de movimentações", "", "🕘")
    movs = listar_movimentos(2000)
    if not movs:
        empty_state("Sem movimentações", "As entradas, baixas, perdas e ajustes aparecem aqui.", "🕘")
    else:
        dm = pd.DataFrame(movs)
        dm["Quando"] = pd.to_datetime(dm["criado_em"], utc=True).dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None)
        dm["Item"] = dm["item_id"].map(lambda x: por_id.get(x, {}).get("nome", "?"))
        dm["Tipo"] = dm["tipo"].map({"entrada": "➕ Entrada", "saida": "➖ Saída", "perda": "🗑️ Perda", "ajuste": "📝 Ajuste"})
        f1, f2, f3 = st.columns([1.2, 1.5, 1.5])
        periodo = f1.date_input("Período", (date.today() - timedelta(days=30), date.today()), format="DD/MM/YYYY")
        tipos = f2.multiselect("Tipo", sorted(dm["Tipo"].dropna().unique()), placeholder="Todos os tipos")
        itf = f3.multiselect("Item", sorted(dm["Item"].unique()), placeholder="Todos os itens")
        if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
            dm = dm[(dm["Quando"].dt.date >= periodo[0]) & (dm["Quando"].dt.date <= periodo[1])]
        if tipos:
            dm = dm[dm["Tipo"].isin(tipos)]
        if itf:
            dm = dm[dm["Item"].isin(itf)]
        out = dm[["Quando", "Item", "Tipo", "quantidade", "saldo_apos", "custo_unitario", "motivo", "referencia", "usuario"]]
        st.dataframe(out, hide_index=True, width="stretch", column_config={
            "Quando": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
            "quantidade": st.column_config.NumberColumn("Qtd", format="%.1f"),
            "saldo_apos": st.column_config.NumberColumn("Saldo após", format="%.1f"),
            "custo_unitario": st.column_config.NumberColumn("Custo unit.", format="R$ %.2f"),
            "motivo": "Motivo", "referencia": "Referência", "usuario": "Usuário"})
        st.download_button("⬇️ Baixar CSV", out.to_csv(index=False).encode("utf-8-sig"), "movimentacoes_estoque.csv", "text/csv")
