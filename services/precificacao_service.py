"""Precificação: custo da cesta, preço sugerido por margem líquida, arredondamento e histórico."""
import math


from config.db import supabase
from services.estoque_service import garantir_schema, composicao_cesta, insumos_cesta, _usuario

PADRAO = {
    "mao_de_obra": 0.0, "outros_custos": 0.0, "frete_absorvido": 0.0,
    "margem_alvo_pct": 35.0, "taxa_pagamento_pct": 3.5, "imposto_pct": 0.0,
    "modo_custo": "pior", "arredondamento": "90",
}
MODOS = {"pior": "Pior caso (escolhas mais caras)", "media": "Média das opções", "melhor": "Melhor caso (mais baratas)"}
ARREDONDAMENTOS = {"nenhum": "Sem arredondar", "inteiro": "Próximo inteiro", "90": "Terminar em ,90", "5": "Múltiplo de R$ 5"}


def parametros(cesta_id):
    garantir_schema()
    r = supabase.table("precificacao_cestas").select("*").eq("cesta_id", str(cesta_id)).execute().data
    base = dict(PADRAO)
    if r:
        base.update({k: (float(v) if isinstance(v, (int, float)) else v) for k, v in r[0].items() if k in PADRAO})
    return base


def salvar_parametros(cesta_id, p):
    from services.estoque_service import _tx
    with _tx() as c:
        c.execute("""INSERT INTO precificacao_cestas
            (cesta_id,mao_de_obra,outros_custos,frete_absorvido,margem_alvo_pct,taxa_pagamento_pct,imposto_pct,modo_custo,arredondamento,atualizado_em)
            VALUES (%(cesta_id)s,%(mao_de_obra)s,%(outros_custos)s,%(frete_absorvido)s,%(margem_alvo_pct)s,%(taxa_pagamento_pct)s,%(imposto_pct)s,%(modo_custo)s,%(arredondamento)s,now())
            ON CONFLICT (cesta_id) DO UPDATE SET
              mao_de_obra=EXCLUDED.mao_de_obra, outros_custos=EXCLUDED.outros_custos, frete_absorvido=EXCLUDED.frete_absorvido,
              margem_alvo_pct=EXCLUDED.margem_alvo_pct, taxa_pagamento_pct=EXCLUDED.taxa_pagamento_pct, imposto_pct=EXCLUDED.imposto_pct,
              modo_custo=EXCLUDED.modo_custo, arredondamento=EXCLUDED.arredondamento, atualizado_em=now()""",
                  {**{k: p[k] for k in PADRAO}, "cesta_id": str(cesta_id)})


# ---------------------------------------------------------------- cálculo
def custo_grupo(grupo, modo):
    """Custo de um grupo de escolha. Se há mais opções que vagas (max), o cliente escolhe → aplica o modo."""
    itens = sorted(grupo["itens"], key=lambda i: i["custo"] * i["quantidade"])
    custos = [i["custo"] * i["quantidade"] for i in itens]
    vagas = max(1, grupo["max"])
    if len(itens) <= vagas:                      # tudo entra na cesta
        return sum(custos), "Fixo"
    if modo == "melhor":
        return sum(custos[:vagas]), "Escolha"
    if modo == "media":
        return vagas * (sum(custos) / len(custos)), "Escolha"
    return sum(custos[-vagas:]), "Escolha"


def arredondar(preco, regra):
    if preco <= 0 or regra == "nenhum":
        return round(preco, 2)
    if regra == "inteiro":
        return float(math.ceil(preco))
    if regra == "5":
        return float(math.ceil(preco / 5) * 5)
    base = math.floor(preco) + 0.90
    return round(base if base >= preco else base + 1, 2)


def preco_para_margem(custo, margem_pct, taxa_pct, imposto_pct):
    """Preço = custo / (1 − taxas − margem). Margem calculada sobre o preço de venda."""
    denom = 1 - (taxa_pct + imposto_pct + margem_pct) / 100
    return custo / denom if denom > 0 else float("inf")


def resultado(preco, custo, taxa_pct, imposto_pct):
    taxas = preco * (taxa_pct + imposto_pct) / 100
    lucro = preco - taxas - custo
    return {"taxas": taxas, "lucro": lucro,
            "margem_pct": (lucro / preco * 100) if preco else 0.0,
            "markup": (preco / custo) if custo else 0.0}


def calcular(cesta_id, params=None, grupos=None, insumos=None):
    p = params or parametros(cesta_id)
    grupos = composicao_cesta(cesta_id) if grupos is None else grupos
    insumos = insumos_cesta(cesta_id) if insumos is None else insumos
    linhas, c_itens = [], 0.0
    for g in grupos:
        c, tipo = custo_grupo(g, p["modo_custo"])
        c_itens += c
        linhas.append({"grupo": g["categoria"], "tipo": tipo, "vagas": g["max"], "opcoes": len(g["itens"]), "custo": c})
    c_insumos = sum(float(i["item"]["custo_efetivo"]) * float(i["quantidade"]) for i in insumos)
    custo = c_itens + c_insumos + p["mao_de_obra"] + p["outros_custos"] + p["frete_absorvido"]
    bruto = preco_para_margem(custo, p["margem_alvo_pct"], p["taxa_pagamento_pct"], p["imposto_pct"])
    sugerido = arredondar(bruto, p["arredondamento"]) if math.isfinite(bruto) else 0.0
    sem_custo = [i["nome"] for g in grupos for i in g["itens"] if i["custo"] <= 0]
    return {"params": p, "linhas": linhas, "custo_itens": c_itens, "custo_insumos": c_insumos, "custo_total": custo,
            "preco_bruto": bruto, "preco_sugerido": sugerido, "sem_custo": sem_custo, "grupos": grupos, "insumos": insumos}


def aplicar_preco(cesta, novo_preco, custo, margem_pct):
    garantir_schema()
    anterior = cesta.get("preco")
    supabase.table("cestas").update({"preco": float(novo_preco)}).eq("id", cesta["id"]).execute()
    supabase.table("precificacao_historico").insert({
        "cesta_id": str(cesta["id"]), "cesta_nome": cesta.get("nome"), "preco_anterior": anterior,
        "preco_novo": float(novo_preco), "custo_total": round(custo, 2), "margem_pct": round(margem_pct, 2),
        "usuario": _usuario(),
    }).execute()


def historico(cesta_id=None, limite=300):
    garantir_schema()
    q = supabase.table("precificacao_historico").select("*").order("criado_em", desc=True).limit(limite)
    if cesta_id:
        q = q.eq("cesta_id", str(cesta_id))
    return q.execute().data or []
