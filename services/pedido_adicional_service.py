from config.db import supabase


# ==========================================================
# SALVAR ADICIONAIS DO PEDIDO
# ==========================================================

def salvar_adicionais_pedido(
    pedido_id,
    adicionais
):

    if not adicionais:
        return True


    registros = []


    for item in adicionais:

        registros.append(

            {

                "pedido_id":
                    pedido_id,

                "produto_id":
                    item["produto_id"],

                "nome_produto":
                    item["nome"],

                "quantidade":
                    1,

                "valor_unitario":
                    item["preco"]

            }

        )


    resposta = (

        supabase

        .table("pedido_adicionais")

        .insert(registros)

        .execute()

    )


    return resposta.data



# ==========================================================
# LISTAR ADICIONAIS DO PEDIDO
# ==========================================================

def listar_adicionais_pedido(
    pedido_id
):

    resposta = (

        supabase

        .table("pedido_adicionais")

        .select("*")

        .eq(
            "pedido_id",
            pedido_id
        )

        .execute()

    )


    return resposta.data



# ==========================================================
# CALCULAR TOTAL DOS ADICIONAIS
# ==========================================================

def calcular_total_adicionais(
    pedido_id
):

    adicionais = listar_adicionais_pedido(
        pedido_id
    )


    total = 0


    for item in adicionais:

        valor = item.get(
            "valor_unitario",
            0
        )


        if valor:

            total += float(valor)


    return total
# ==========================================================
# ATUALIZAR VALOR DO ADICIONAL
# ==========================================================

def atualizar_valor_adicional(
    adicional_id,
    novo_valor
):

    resposta = (

        supabase

        .table("pedido_adicionais")

        .update(

            {
                "valor_unitario": novo_valor
            }

        )

        .eq(
            "id",
            adicional_id
        )

        .execute()

    )


    if resposta.data:

        return True, "Valor atualizado com sucesso."


    return False, "Não foi possível atualizar o valor."
