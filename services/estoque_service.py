"""Estoque: itens, movimentações atômicas (transação + lock de linha) e sincronização com o catálogo."""
from contextlib import contextmanager
from pathlib import Path

import psycopg2.extras
import streamlit as st

from config.db import supabase, _get_pool

_SQL = Path(__file__).resolve().parent.parent / "migrations" / "001_estoque_precificacao.sql"

TIPOS_MOV = {"entrada": 1, "saida": -1, "perda": -1}  # ajuste é calculado (contagem física)
UNIDADES = ["un", "kg", "g", "l", "ml", "cx", "pct"]


@st.cache_resource(show_spinner=False)
def garantir_schema():
    """Cria as tabelas na primeira execução (idempotente)."""
    if not _SQL.exists():          # tabelas já criadas manualmente no banco (ex.: Neon)
        return True
    with _tx() as cur:
        cur.execute(_SQL.read_text(encoding="utf-8"))
    return True


@contextmanager
def _tx():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                yield cur
        pool.putconn(conn)
    except Exception:
        try:
            conn.rollback()
        finally:
            pool.putconn(conn)
        raise


def _usuario():
    u = st.session_state.get("usuario") or {}
    return u.get("login") or "sistema"


# ---------------------------------------------------------------- leitura
def listar_itens(somente_ativos=False):
    garantir_schema()
    q = supabase.table("estoque_itens").select("*").order("nome")
    if somente_ativos:
        q = q.eq("ativo", True)
    return q.execute().data or []


def listar_movimentos(limite=1000):
    garantir_schema()
    return (supabase.table("estoque_movimentos").select("*")
            .order("criado_em", desc=True).limit(limite).execute().data or [])


# ---------------------------------------------------------------- cadastro
def sincronizar_catalogo():
    """Espelha produtos do catálogo em estoque_itens (só cria os que faltam). Retorna qtd criada."""
    garantir_schema()
    existentes = {r["produto_id"] for r in supabase.table("estoque_itens").select("produto_id").execute().data if r.get("produto_id")}
    novos = [p for p in (supabase.table("produtos").select("id,nome,ativo").execute().data or [])
             if str(p["id"]) not in existentes]
    for p in novos:
        supabase.table("estoque_itens").insert({
            "produto_id": str(p["id"]), "nome": p["nome"], "tipo": "produto",
            "ativo": bool(p.get("ativo", True)),
        }).execute()
    return len(novos)


def criar_insumo(nome, unidade="un", custo=0.0, minimo=0.0, fornecedor=None, perda_pct=0.0):
    garantir_schema()
    return supabase.table("estoque_itens").insert({
        "nome": nome.strip(), "tipo": "insumo", "unidade": unidade, "custo_unitario": custo,
        "estoque_minimo": minimo, "fornecedor": fornecedor or None, "perda_pct": perda_pct,
    }).execute().data


def atualizar_item(item_id, campos: dict):
    permitidos = {"nome", "unidade", "custo_unitario", "perda_pct", "estoque_minimo", "fornecedor", "ativo", "tipo"}
    campos = {k: v for k, v in campos.items() if k in permitidos}
    if not campos:
        return
    cols = ", ".join(f'"{k}" = %s' for k in campos)
    with _tx() as cur:
        cur.execute(f"UPDATE estoque_itens SET {cols}, atualizado_em = now() WHERE id = %s",
                    list(campos.values()) + [str(item_id)])


# ---------------------------------------------------------------- movimentação
def movimentar(item_id, tipo, quantidade, custo_unitario=None, motivo=None, referencia=None,
               permitir_negativo=False, cur=None):
    """Entrada/saída/perda atômicas. Entrada com custo atualiza o custo pela média ponderada."""
    if tipo not in TIPOS_MOV:
        raise ValueError("Tipo inválido.")
    quantidade = float(quantidade)
    if quantidade <= 0:
        raise ValueError("A quantidade deve ser maior que zero.")

    def _exec(c):
        c.execute("SELECT nome, estoque_atual, custo_unitario FROM estoque_itens WHERE id = %s FOR UPDATE", (str(item_id),))
        item = c.fetchone()
        if not item:
            raise ValueError("Item não encontrado.")
        saldo = float(item["estoque_atual"])
        novo = saldo + TIPOS_MOV[tipo] * quantidade
        if novo < 0 and not permitir_negativo:
            raise ValueError(f"Estoque insuficiente de «{item['nome']}»: saldo {saldo:g}, solicitado {quantidade:g}.")
        novo_custo = float(item["custo_unitario"])
        if tipo == "entrada" and custo_unitario is not None and float(custo_unitario) >= 0:
            base = max(saldo, 0.0)
            total = base + quantidade
            novo_custo = (base * novo_custo + quantidade * float(custo_unitario)) / total if total else float(custo_unitario)
        c.execute("UPDATE estoque_itens SET estoque_atual=%s, custo_unitario=%s, atualizado_em=now() WHERE id=%s",
                  (novo, round(novo_custo, 4), str(item_id)))
        c.execute("""INSERT INTO estoque_movimentos (item_id,tipo,quantidade,saldo_apos,custo_unitario,motivo,referencia,usuario)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                  (str(item_id), tipo, quantidade, novo, custo_unitario, motivo, referencia, _usuario()))
        return novo

    if cur is not None:
        return _exec(cur)
    with _tx() as c:
        return _exec(c)


def lancar_lote(movimentos):
    """movimentos: lista de dicts (item_id,tipo,quantidade,custo_unitario?,motivo?,referencia?). Tudo ou nada."""
    with _tx() as c:
        for m in movimentos:
            movimentar(m["item_id"], m["tipo"], m["quantidade"], m.get("custo_unitario"),
                       m.get("motivo"), m.get("referencia"), cur=c)
    return len(movimentos)


def ajustar_contagem(contagens, motivo="Inventário"):
    """contagens: {item_id: quantidade_contada}. Gera movimento 'ajuste' só onde há diferença."""
    n = 0
    with _tx() as c:
        for item_id, contado in contagens.items():
            c.execute("SELECT estoque_atual FROM estoque_itens WHERE id=%s FOR UPDATE", (str(item_id),))
            r = c.fetchone()
            if not r:
                continue
            saldo = float(r["estoque_atual"])
            contado = float(contado)
            if abs(contado - saldo) < 1e-9:
                continue
            c.execute("UPDATE estoque_itens SET estoque_atual=%s, atualizado_em=now() WHERE id=%s", (contado, str(item_id)))
            c.execute("""INSERT INTO estoque_movimentos (item_id,tipo,quantidade,saldo_apos,motivo,usuario)
                         VALUES (%s,'ajuste',%s,%s,%s,%s)""",
                      (str(item_id), abs(contado - saldo), contado,
                       f"{motivo} ({'+' if contado > saldo else '-'}{abs(contado - saldo):g})", _usuario()))
            n += 1
    return n


# ---------------------------------------------------------------- composição das cestas
def composicao_cesta(cesta_id):
    """Grupos de escolha da cesta: [{categoria, min, max, itens:[{produto_id,item_id,nome,custo,estoque}]}]."""
    garantir_schema()
    vinc = supabase.table("cesta_produtos").select("*").eq("cesta_id", cesta_id).execute().data or []
    if not vinc:
        return []
    ids = [v["produto_id"] for v in vinc]
    prods = {str(p["id"]): p for p in (supabase.table("produtos").select("id,nome,categoria_id").in_("id", ids).execute().data or [])}
    cats = {str(c["id"]): c["nome"] for c in (supabase.table("categorias").select("id,nome").execute().data or [])}
    itens = {r["produto_id"]: r for r in (supabase.table("estoque_itens").select("*").execute().data or []) if r.get("produto_id")}
    grupos = {}
    for v in vinc:
        p = prods.get(str(v["produto_id"]))
        if not p:
            continue
        g = grupos.setdefault(str(p["categoria_id"]), {
            "categoria": cats.get(str(p["categoria_id"]), "Sem categoria"),
            "min": int(v.get("min_escolhas") or 1), "max": int(v.get("max_escolhas") or 1), "itens": []})
        est = itens.get(str(p["id"]))
        g["itens"].append({
            "produto_id": str(p["id"]), "item_id": est["id"] if est else None, "nome": p["nome"],
            "quantidade": float(v.get("quantidade") or 1),
            "custo": float(est["custo_efetivo"]) if est else 0.0,
            "custo_unitario": float(est["custo_unitario"]) if est else 0.0,
            "perda_pct": float(est["perda_pct"]) if est else 0.0,
            "estoque": float(est["estoque_atual"]) if est else 0.0,
        })
    return list(grupos.values())


def insumos_cesta(cesta_id):
    garantir_schema()
    linhas = supabase.table("cesta_insumos").select("*").eq("cesta_id", str(cesta_id)).execute().data or []
    itens = {r["id"]: r for r in supabase.table("estoque_itens").select("*").execute().data or []}
    return [{**l, "item": itens.get(l["item_id"])} for l in linhas if itens.get(l["item_id"])]


def salvar_insumos_cesta(cesta_id, linhas):
    """linhas: [(item_id, quantidade)] — substitui a lista atual."""
    with _tx() as c:
        c.execute("DELETE FROM cesta_insumos WHERE cesta_id=%s", (str(cesta_id),))
        agg = {}
        for item_id, q in linhas:
            if item_id and q and float(q) > 0:
                agg[str(item_id)] = agg.get(str(item_id), 0) + float(q)
        for item_id, q in agg.items():
            c.execute("INSERT INTO cesta_insumos (cesta_id,item_id,quantidade) VALUES (%s,%s,%s)", (str(cesta_id), item_id, q))
