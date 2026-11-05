from config.db import supabase



# =====================================================
# LISTAR PRODUTOS DA CESTA
# =====================================================

def listar_produtos_da_cesta(cesta_id):

    resposta = (

        supabase

        .table("cesta_produtos")

        .select("*")

        .eq(
            "cesta_id",
            cesta_id
        )

        .execute()

    )

    return resposta.data or []




# =====================================================
# SALVAR PRODUTOS DA CESTA
# (USADO NA PÁGINA 12)
# =====================================================

def salvar_produtos_da_cesta(
    cesta_id,
    produtos_selecionados
):


    # remove vínculos atuais

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



    ordem = 0



    for produto_id in produtos_selecionados:


        (

            supabase

            .table("cesta_produtos")

            .insert({

                "cesta_id":

                    cesta_id,


                "produto_id":

                    produto_id,


                "quantidade":

                    1,


                "min_escolhas":

                    1,


                "max_escolhas":

                    1,


                "ordem":

                    ordem

            })

            .execute()

        )


        ordem += 1





# =====================================================
# CARREGAR CONFIGURAÇÃO COMPLETA DA CESTA
# (USADO NO APP.PY)
# =====================================================

def carregar_configuracao_cesta(cesta_id):


    resposta = (

        supabase

        .table("cesta_produtos")

        .select("*")

        .eq(
            "cesta_id",
            cesta_id
        )

        .execute()

    )


    if not resposta.data:

        return []



    categorias = {}



    for item in resposta.data:



        produto_resp = (

            supabase

            .table("produtos")

            .select("*")

            .eq(
                "id",
                item["produto_id"]
            )

            .single()

            .execute()

        )


        produto = produto_resp.data



        if not produto:

            continue



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



        categoria_nome = (

            categoria_resp.data["nome"]

            if categoria_resp.data

            else "Sem Categoria"

        )



        if categoria_nome not in categorias:


            categorias[categoria_nome] = {


                "categoria":

                    categoria_nome,


                "min_escolhas":

                    item.get(
                        "min_escolhas",
                        1
                    ),


                "max_escolhas":

                    item.get(
                        "max_escolhas",
                        1
                    ),


                "produtos":

                    []

            }



        categorias[categoria_nome]["produtos"].append(

            produto

        )



    return list(
        categorias.values()
    )





# =====================================================
# SALVAR CONFIGURAÇÃO COMPLETA DA CESTA
# (USADO NA PÁGINA 14)
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



    ordem = 0



    for categoria in configuracoes:



        for produto_id in categoria["produtos"]:



            (

                supabase

                .table("cesta_produtos")

                .insert({


                    "cesta_id":

                        cesta_id,


                    "produto_id":

                        produto_id,


                    "categoria":

                        categoria["categoria"],


                    "quantidade":

                        1,


                    "min_escolhas":

                        categoria.get(
                            "min_escolhas",
                            1
                        ),


                    "max_escolhas":

                        categoria.get(
                            "max_escolhas",
                            1
                        ),


                    "ordem":

                        ordem


                })

                .execute()

            )


            ordem += 1





# =====================================================
# EXCLUIR CONFIGURAÇÃO DA CESTA
# =====================================================

def excluir_configuracao_cesta(
    cesta_id
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
