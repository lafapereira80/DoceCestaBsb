from config.db import supabase



# =====================================================
# CARREGAR CONFIGURAÇÃO DA CESTA
# =====================================================

def carregar_configuracao_cesta(cesta_id):


    resposta = (

        supabase

        .table("cesta_produtos")

        .select(
            """
            *,
            produtos (
                id,
                nome,
                preco,
                ativo,
                categoria_id
            )
            """
        )

        .eq(
            "cesta_id",
            cesta_id
        )

        .order(
            "ordem"
        )

        .execute()

    )



    if not resposta.data:

        return []



    categorias = {}



    for item in resposta.data:


        produto = item.get(
            "produtos"
        )



        if not produto:

            continue



        categoria_nome = item.get(
            "categoria"
        )



        if not categoria_nome:


            categoria_resp = (

                supabase

                .table("categorias")

                .select("nome")

                .eq(
                    "id",
                    produto["categoria_id"]
                )

                .single()

                .execute()

            )


            if categoria_resp.data:

                categoria_nome = categoria_resp.data["nome"]


            else:

                categoria_nome = "Sem Categoria"




        if categoria_nome not in categorias:


            categorias[categoria_nome] = {


                "categoria": categoria_nome,


                "min_escolhas": item.get(
                    "min_escolhas",
                    1
                ),


                "max_escolhas": item.get(
                    "max_escolhas",
                    1
                ),


                "produtos": []

            }




        categorias[categoria_nome]["produtos"].append(
            produto
        )



    return list(
        categorias.values()
    )




# =====================================================
# SALVAR CONFIGURAÇÃO DA CESTA
# =====================================================

def salvar_configuracao_cesta(
    cesta_id,
    configuracoes
):


    (
        supabase

        .table("cesta_produtos")

        .delete()

        .eq(
            "cesta_id",
            cesta_id
        )

        .execute()
    )



    registros = []



    ordem = 0



    for grupo in configuracoes:



        for produto_id in grupo["produtos"]:



            registros.append({


                "cesta_id": cesta_id,


                "produto_id": produto_id,


                "categoria": grupo["categoria"],


                "min_escolhas": grupo["min_escolhas"],


                "max_escolhas": grupo["max_escolhas"],


                "quantidade": grupo["max_escolhas"],


                "ordem": ordem


            })


            ordem += 1




    if registros:


        (

            supabase

            .table("cesta_produtos")

            .insert(registros)

            .execute()

        )
