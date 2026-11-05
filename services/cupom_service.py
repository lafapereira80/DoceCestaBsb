import random
import string
from datetime import date, datetime, time as dtime

from config.db import supabase


def gerar_codigo(prefixo="DOCE"):
    """Gera um código curto e fácil de digitar, ex: DOCE-7K3F9Q."""
    sufixo = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefixo}-{sufixo}"


def criar_cupom(codigo, tipo, valor, valido_de, valido_ate, limite_usos,
                 limite_por_cliente=1, valor_minimo_pedido=0, descricao="",
                 origem="manual", criado_por="",
                 valido_de_hora=None, valido_ate_hora=None, cesta_ids=None):
    """
    tipo: 'percentual' (valor = % ex 10), 'fixo' (valor em R$), 'cortesia_total' (valor ignorado, zera o pedido).
    cesta_ids: lista de IDs de cesta em que o cupom pode ser usado. None/[] = vale para todas.
    """
    codigo = codigo.strip().upper()
    payload = {
        "codigo": codigo,
        "tipo": tipo,
        "valor": float(valor or 0),
        "descricao": descricao.strip(),
        "valido_de": str(valido_de),
        "valido_ate": str(valido_ate),
        "valido_de_hora": str(valido_de_hora or dtime(0, 0, 0)),
        "valido_ate_hora": str(valido_ate_hora or dtime(23, 59, 59)),
        "limite_usos": int(limite_usos),
        "limite_por_cliente": int(limite_por_cliente),
        "valor_minimo_pedido": float(valor_minimo_pedido or 0),
        "cesta_ids": list(cesta_ids) if cesta_ids else None,
        "ativo": True,
        "origem": origem,
        "criado_por": criado_por,
    }
    try:
        res = supabase.table("cupons").insert(payload).execute()
        return True, res.data[0] if res.data else None
    except Exception as e:
        return False, str(e)


def listar_cupons():
    try:
        res = supabase.table("cupons").select("*").order("created_at", desc=True).execute()
        return res.data or []
    except Exception:
        return []


def alternar_ativo(cupom_id, novo_status):
    try:
        supabase.table("cupons").update({"ativo": bool(novo_status)}).eq("id", cupom_id).execute()
        return True, ""
    except Exception as e:
        return False, str(e)


def excluir_cupom(cupom_id):
    try:
        supabase.table("cupons").delete().eq("id", cupom_id).execute()
        return True, ""
    except Exception as e:
        return False, str(e)


def contar_usos(cupom_id):
    try:
        res = supabase.table("cupom_usos").select("id").eq("cupom_id", cupom_id).execute()
        return len(res.data or [])
    except Exception:
        return 0


def _parse_hora(valor, padrao):
    """Converte 'HH:MM:SS' (string vinda do banco) em datetime.time; usa padrão se vazio/inválido."""
    if not valor:
        return padrao
    try:
        partes = [int(p) for p in str(valor).split(":")]
        while len(partes) < 3:
            partes.append(0)
        return dtime(*partes[:3])
    except Exception:
        return padrao


def validar_cupom(codigo, valor_pedido, cliente_identificador, cesta_id=None):
    """
    Verifica se o cupom pode ser usado agora, por esse cliente, nesse valor de
    pedido e (se o cupom for restrito) nessa cesta específica.
    Retorna (ok: bool, mensagem: str, cupom: dict|None, valor_desconto: float).
    """
    codigo = (codigo or "").strip().upper()
    if not codigo:
        return False, "Digite um código de cupom.", None, 0.0

    try:
        res = supabase.table("cupons").select("*").eq("codigo", codigo).single().execute()
        cupom = res.data
    except Exception:
        cupom = None

    if not cupom:
        return False, "Cupom não encontrado.", None, 0.0

    if not cupom.get("ativo", False):
        return False, "Este cupom não está mais ativo.", None, 0.0

    agora = datetime.now()
    hora_inicio = _parse_hora(cupom.get("valido_de_hora"), dtime(0, 0, 0))
    hora_fim = _parse_hora(cupom.get("valido_ate_hora"), dtime(23, 59, 59))

    try:
        inicio_dt = datetime.combine(datetime.strptime(str(cupom["valido_de"])[:10], "%Y-%m-%d").date(), hora_inicio)
        fim_dt = datetime.combine(datetime.strptime(str(cupom["valido_ate"])[:10], "%Y-%m-%d").date(), hora_fim)
    except Exception:
        inicio_dt, fim_dt = None, None

    if inicio_dt and agora < inicio_dt:
        return False, f"Este cupom só é válido a partir de {inicio_dt.strftime('%d/%m/%Y às %H:%M')}.", None, 0.0
    if fim_dt and agora > fim_dt:
        return False, "Este cupom expirou.", None, 0.0

    cesta_ids = cupom.get("cesta_ids")
    if cesta_ids:
        if cesta_id is None or cesta_id not in cesta_ids:
            return False, "Este cupom não é válido para a cesta escolhida.", None, 0.0

    if float(valor_pedido or 0) < float(cupom.get("valor_minimo_pedido") or 0):
        minimo = cupom.get("valor_minimo_pedido")
        return False, f"Pedido mínimo de R$ {minimo:.2f} para usar este cupom.", None, 0.0

    total_usos = contar_usos(cupom["id"])
    if total_usos >= int(cupom.get("limite_usos") or 1):
        return False, "Este cupom já atingiu o limite de usos.", None, 0.0

    if cliente_identificador:
        try:
            res_uso = (
                supabase.table("cupom_usos")
                .select("id")
                .eq("cupom_id", cupom["id"])
                .eq("cliente_identificador", cliente_identificador)
                .execute()
            )
            usos_deste_cliente = len(res_uso.data or [])
        except Exception:
            usos_deste_cliente = 0
        if usos_deste_cliente >= int(cupom.get("limite_por_cliente") or 1):
            return False, "Você já utilizou este cupom antes.", None, 0.0

    tipo = cupom.get("tipo")
    if tipo == "percentual":
        desconto = float(valor_pedido) * (float(cupom.get("valor") or 0) / 100.0)
    elif tipo == "fixo":
        desconto = float(cupom.get("valor") or 0)
    elif tipo == "cortesia_total":
        desconto = float(valor_pedido)
    else:
        desconto = 0.0

    desconto = min(desconto, float(valor_pedido))
    return True, "Cupom aplicado! 🎉", cupom, round(desconto, 2)


def registrar_uso(cupom_id, pedido_id, cliente_identificador, valor_desconto_aplicado):
    try:
        supabase.table("cupom_usos").insert({
            "cupom_id": cupom_id,
            "pedido_id": pedido_id,
            "cliente_identificador": cliente_identificador,
            "valor_desconto_aplicado": float(valor_desconto_aplicado or 0),
        }).execute()
        return True, ""
    except Exception as e:
        return False, str(e)


def listar_clientes_para_envio():
    """
    Lista clientes únicos (nome, telefone, email) pra usar no envio de cupons de
    cortesia. Monta a partir de 'pedidos' — é ali que cliente_email fica
    confiavelmente preenchido (a view vw_resumo_clientes nem sempre traz esse
    campo, o que fazia o e-mail aparecer vazio na tela de envio).
    """
    try:
        res = supabase.table("pedidos").select(
            "cliente_nome, cliente_telefone, cliente_email, cliente_cpf"
        ).order("created_at", desc=True).execute()
    except Exception:
        return []

    vistos = {}
    for p in res.data or []:
        chave = (p.get("cliente_telefone") or p.get("cliente_cpf") or p.get("cliente_email") or "").strip()
        if not chave:
            continue
        if chave not in vistos:
            vistos[chave] = {
                "nome": p.get("cliente_nome", "Cliente"),
                "telefone": p.get("cliente_telefone") or "",
                "email": p.get("cliente_email") or "",
                "total_pedidos": 0,
            }
        else:
            # Se um pedido mais recente tiver e-mail preenchido e o registro atual não tiver, completa.
            if not vistos[chave]["email"] and p.get("cliente_email"):
                vistos[chave]["email"] = p.get("cliente_email")
        vistos[chave]["total_pedidos"] += 1

    return list(vistos.values())
