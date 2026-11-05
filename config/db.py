"""
Substituto do config/supabase.py — fala com o Neon (Postgres puro) via psycopg2,
mas mantém a MESMA sintaxe encadeada do supabase-py (.table().select().eq()...)
para não ser necessário reescrever os pontos de chamada no projeto.

v3.3 — Ajustes de Segurança e Resiliência (Cold Start):
- DATABASE_URL é consumida estritamente via st.secrets ou variável de ambiente.
- O método .execute() agora implementa um loop de retries progressivos. Se o 
  Neon estiver "dormindo", ele aguarda e tenta novamente até 3 vezes antes de falhar,
  evitando que a aplicação quebre na segunda tentativa imediata.
"""

import re
import time
import os
import uuid
from datetime import date, datetime, time as datetime_time
from decimal import Decimal

import streamlit as st
import psycopg2
import psycopg2.extras
from psycopg2.extras import Json
from psycopg2.pool import SimpleConnectionPool

_pool = None


def _dsn_limpa():
    # Busca a URL estritamente dos secrets ou variáveis de ambiente
    try:
        dsn = st.secrets["connections"]["postgresql"]["DATABASE_URL"]
    except Exception:
        dsn = os.getenv("DATABASE_URL")
        
    if not dsn:
        raise ValueError("DATABASE_URL não encontrada. Verifique o arquivo .streamlit/secrets.toml ou as variáveis de ambiente.")

    # channel_binding confunde o psycopg2 em algumas versões — remove com segurança
    dsn = re.sub(r"([&?])channel_binding=[^&]*(&|$)", r"\1", dsn)
    dsn = dsn.replace("&&", "&").rstrip("?&")
    return dsn


def _get_pool():
    global _pool
    if _pool is not None:
        return _pool

    dsn = _dsn_limpa()
    max_tentativas = 3
    ultimo_erro = None
    for tentativa in range(max_tentativas):
        try:
            _pool = SimpleConnectionPool(
                minconn=2,
                maxconn=10,
                dsn=dsn,
                connect_timeout=5,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=3,
            )
            return _pool
        except psycopg2.OperationalError as e:
            ultimo_erro = e
            if tentativa < max_tentativas - 1:
                time.sleep(1.5)  # dá tempo do Neon sair do cold start
    raise ultimo_erro


# =====================================================================
# Relações conhecidas para o "embed" estilo PostgREST
# =====================================================================
_FK_OVERRIDES = {
    # "tabela_embutida": "coluna_fk_na_tabela_principal",
}


def _fk_column_for(embed_table):
    if embed_table in _FK_OVERRIDES:
        return _FK_OVERRIDES[embed_table]
    singular = embed_table[:-1] if embed_table.endswith("s") else embed_table
    return f"{singular}_id"


_EMBED_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*(.*)\s*\)$", re.S)


def _parse_select(columns_str):
    text = columns_str.strip()
    tokens = []
    depth = 0
    current = ""
    for ch in text:
        if ch == "(":
            depth += 1
            current += ch
        elif ch == ")":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            tokens.append(current)
            current = ""
        else:
            current += ch
    if current.strip():
        tokens.append(current)

    simples = []
    embeds = []
    for tok in tokens:
        tok_stripped = tok.strip()
        if not tok_stripped:
            continue
        m = _EMBED_RE.match(tok_stripped)
        if m:
            embed_table = m.group(1).strip()
            inner = [c.strip() for c in m.group(2).split(",") if c.strip()]
            embeds.append((embed_table, inner or ["*"]))
        else:
            simples.append(" ".join(tok_stripped.split()))

    if not simples:
        simples = ["*"]
    return simples, embeds


# =====================================================================
# Normalização de valores lidos do banco
# =====================================================================

def _normalize_value(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime): 
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, datetime_time):
        return v.isoformat()
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, dict):
        return {k: _normalize_value(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_normalize_value(x) for x in v]
    return v


def _normalize_row(row):
    return {k: _normalize_value(v) for k, v in row.items()}


def _adapt_payload(payload):
    adaptado = {}
    for k, v in payload.items():
        if isinstance(v, (dict, list)):
            adaptado[k] = Json(v)
        else:
            adaptado[k] = v
    return adaptado


class _Result:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class _Query:
    def __init__(self, table_name):
        self._table = table_name
        self._op = None
        self._columns_raw = "*"
        self._payload = None
        self._filters = []       
        self._order_by = []      
        self._limit_n = None
        self._want_single = False
        self._negate_next = False

    # ---------------- filtros ----------------

    def _push(self, sql_fragment, *params):
        if self._negate_next:
            sql_fragment = f"NOT ({sql_fragment})"
            self._negate_next = False
        self._filters.append((sql_fragment, params))
        return self

    @property
    def not_(self):
        self._negate_next = True
        return self

    def eq(self, col, val):
        return self._push(f'"{col}" = %s', val)

    def neq(self, col, val):
        return self._push(f'"{col}" <> %s', val)

    def gt(self, col, val):
        return self._push(f'"{col}" > %s', val)

    def gte(self, col, val):
        return self._push(f'"{col}" >= %s', val)

    def lt(self, col, val):
        return self._push(f'"{col}" < %s', val)

    def lte(self, col, val):
        return self._push(f'"{col}" <= %s', val)

    def is_(self, col, val):
        if val is None:
            return self._push(f'"{col}" IS NULL')
        return self._push(f'"{col}" IS {"TRUE" if val else "FALSE"}')

    def ilike(self, col, pattern):
        return self._push(f'"{col}" ILIKE %s', pattern)

    def like(self, col, pattern):
        return self._push(f'"{col}" LIKE %s', pattern)

    def in_(self, col, values):
        values = list(values)
        if not values:
            return self._push("FALSE")
        placeholders = ", ".join(["%s"] * len(values))
        return self._push(f'"{col}" IN ({placeholders})', *values)

    def or_(self, expr):
        op_map = {"eq": "=", "neq": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
        parts, params = [], []
        for cond in expr.split(","):
            col, op, val = cond.split(".", 2)
            parts.append(f'"{col}" {op_map.get(op, "=")} %s')
            params.append(val)
        sql = "(" + " OR ".join(parts) + ")"
        return self._push(sql, *params)

    # ---------------- forma da query ----------------

    def select(self, *columns):
        self._op = "select"
        self._columns_raw = ", ".join(columns) if columns else "*"
        return self

    def insert(self, payload):
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def delete(self):
        self._op = "delete"
        return self

    def order(self, col, desc=False):
        self._order_by.append(f'"{col}" {"DESC" if desc else "ASC"}')
        return self

    def limit(self, n):
        self._limit_n = int(n)
        return self

    def single(self):
        self._want_single = True
        return self

    # ---------------- montagem do WHERE ----------------

    def _where_clause(self, base_params=None):
        params = list(base_params) if base_params else []
        if not self._filters:
            return "", params
        clauses = []
        for frag, fparams in self._filters:
            clauses.append(frag)
            params.extend(fparams)
        return " WHERE " + " AND ".join(clauses), params

    # ---------------- embeds (joins estilo PostgREST) ----------------

    def _carregar_embeds(self, cur, linhas, embeds):
        for embed_table, embed_cols in embeds:
            fk_col = _fk_column_for(embed_table)

            fk_valores = sorted({r[fk_col] for r in linhas if r.get(fk_col) is not None})
            if not fk_valores:
                for r in linhas:
                    r[embed_table] = None
                continue

            quer_tudo = "*" in embed_cols
            cols_para_buscar = ["id"] if quer_tudo else list(dict.fromkeys(["id"] + embed_cols))
            cols_sql = "*" if quer_tudo else ", ".join(cols_para_buscar)

            placeholders = ", ".join(["%s"] * len(fk_valores))
            cur.execute(
                f'SELECT {cols_sql} FROM "{embed_table}" WHERE "id" IN ({placeholders})',
                fk_valores,
            )
            registros = [_normalize_row(dict(r)) for r in cur.fetchall()]
            mapa = {reg["id"]: reg for reg in registros}

            for r in linhas:
                fk_val = r.get(fk_col)
                if fk_val is None or fk_val not in mapa:
                    r[embed_table] = None
                    continue
                encontrado = mapa[fk_val]
                if quer_tudo:
                    r[embed_table] = encontrado
                else:
                    r[embed_table] = {k: v for k, v in encontrado.items() if k in embed_cols}

    # ---------------- execução ----------------

    def _run(self, conn):
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

                if self._op == "select":
                    simples, embeds = _parse_select(self._columns_raw)
                    sql = f'SELECT {", ".join(simples)} FROM "{self._table}"'
                    where_sql, params = self._where_clause()
                    sql += where_sql
                    if self._order_by:
                        sql += " ORDER BY " + ", ".join(self._order_by)
                    if self._limit_n:
                        sql += f" LIMIT {self._limit_n}"
                    cur.execute(sql, params)
                    rows = [_normalize_row(dict(r)) for r in cur.fetchall()]

                    if embeds:
                        self._carregar_embeds(cur, rows, embeds)

                    if self._want_single:
                        return _Result(rows[0] if rows else None)
                    return _Result(rows)

                if self._op == "insert":
                    registros = self._payload if isinstance(self._payload, list) else [self._payload]
                    resultado = []
                    for registro in registros:
                        registro_adaptado = _adapt_payload(registro)
                        cols = list(registro_adaptado.keys())
                        vals = [registro_adaptado[c] for c in cols]
                        col_sql = ", ".join(f'"{c}"' for c in cols)
                        ph = ", ".join(["%s"] * len(cols))
                        sql = f'INSERT INTO "{self._table}" ({col_sql}) VALUES ({ph}) RETURNING *'
                        cur.execute(sql, vals)
                        resultado.append(_normalize_row(dict(cur.fetchone())))
                    return _Result(resultado)

                if self._op == "update":
                    payload_adaptado = _adapt_payload(self._payload)
                    cols = list(payload_adaptado.keys())
                    vals = [payload_adaptado[c] for c in cols]
                    set_sql = ", ".join(f'"{c}" = %s' for c in cols)
                    sql = f'UPDATE "{self._table}" SET {set_sql}'
                    where_sql, params = self._where_clause(base_params=vals)
                    sql += where_sql + " RETURNING *"
                    cur.execute(sql, params)
                    rows = [_normalize_row(dict(r)) for r in cur.fetchall()]
                    return _Result(rows)

                if self._op == "delete":
                    sql = f'DELETE FROM "{self._table}"'
                    where_sql, params = self._where_clause()
                    sql += where_sql + " RETURNING *"
                    cur.execute(sql, params)
                    rows = [_normalize_row(dict(r)) for r in cur.fetchall()]
                    return _Result(rows)

                raise ValueError(
                    "Nenhuma operação (select/insert/update/delete) foi chamada antes de .execute()"
                )

    def execute(self):
        pool = _get_pool()
        max_retries = 3
        ultimo_erro = None

        for attempt in range(max_retries):
            conn = pool.getconn()
            try:
                # Tenta executar a query
                resultado = self._run(conn)
                # Se der certo, devolve a conexão pro pool saudável
                pool.putconn(conn)
                return resultado

            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                # Conexão caiu ou banco está em cold start
                ultimo_erro = e
                try:
                    pool.putconn(conn, close=True) # Descarta a conexão problemática
                except Exception:
                    pass
                
                if attempt < max_retries - 1:
                    # Pausa de tempo progressiva para deixar o banco acordar
                    time.sleep(1.5 * (attempt + 1))
            
            except Exception as e:
                # Erros de sintaxe ou violação de restrição não devem ser repetidos
                conn.rollback()
                try:
                    pool.putconn(conn)
                except Exception:
                    pass
                raise e

        # Se esgotar as tentativas, lança o último erro de conexão
        raise ultimo_erro


class _Client:
    def table(self, name):
        return _Query(name)


# Mesmo nome de variável usado em todo o projeto — só troca o import.
supabase = _Client()
