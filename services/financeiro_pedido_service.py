from config.db import supabase



# =====================================================
# BUSCAR VALOR DA CESTA
# =====================================================

def buscar_valor_cesta(cesta_id):


    if not cesta_id:

        return 0



    resposta = (

        supabase

        .table("cestas")

        .select(

            "preco"

        )

        .eq(

            "id",

            cesta_id

        )

        .single()

        .execute()

    )



    if not resposta.data:


        return 0



    return float(

        resposta.data.get(

            "preco",

            0

        )

        or 0

    )





# =====================================================
# BUSCAR PRODUTOS ADICIONAIS
#
# Retorna adicionais cadastrados
# com preço definido
# =====================================================

def buscar_adicionais_com_preco():


    resposta = (

        supabase

        .table("produtos")

        .select(

            """

            *,

            categorias(

                nome

            )

            """

        )

        .eq(

            "ativo",

            True

        )

        .execute()

    )



    produtos = []



    for produto in resposta.data or []:



        categoria = produto.get(

            "categorias"

        )



        if categoria:



            nome_categoria = categoria.get(

                "nome",

                ""

            ).lower().strip()



            if nome_categoria == "adicionais":



                if produto.get(

                    "preco"

                ) is not None:



                    produtos.append({

                        "nome":

                            produto["nome"],


                        "preco":

                            float(

                                produto["preco"]

                            )

                    })



    return produtos





# =====================================================
# CALCULA VALOR DOS ADICIONAIS DO PEDIDO
# =====================================================

def calcular_adicionais_pedido(

    adicionais_texto

):


    if not adicionais_texto:


        return 0



    adicionais_cadastrados = buscar_adicionais_com_preco()



    total = 0



    nomes_pedido = [


        item.strip()


        for item in adicionais_texto.split(",")


    ]



    for item in nomes_pedido:



        for adicional in adicionais_cadastrados:



            if item.lower() == adicional["nome"].lower():



                total += adicional["preco"]



    return total





# =====================================================
# IDENTIFICA ITENS SOB CONSULTA
# =====================================================

def listar_itens_consulta(

    itens

):


    if not itens:


        return []



    resultado = []



    for item in itens:


        resultado.append({

            "nome":

                item.get(

                    "nome",

                    ""

                ),


            "valor":

                float(

                    item.get(

                        "valor",

                        0

                    )

                    or 0

                )

        })



    return resultado





# =====================================================
# SOMA ITENS SOB CONSULTA
# =====================================================

def calcular_itens_consulta(

    itens

):


    total = 0



    for item in itens or []:


        total += float(

            item.get(

                "valor",

                0

            )

            or 0

        )



    return total





# =====================================================
# CALCULO FINAL DO PEDIDO
# =====================================================

def calcular_total_pedido(

    valor_cesta,

    valor_adicionais,

    valor_consulta,

    frete,

    desconto

):


    total = (

        valor_cesta

        +

        valor_adicionais

        +

        valor_consulta

        +

        frete

        -

        desconto

    )



    if total < 0:


        total = 0



    return round(

        total,

        2

    )
