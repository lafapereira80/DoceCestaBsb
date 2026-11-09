import { neon } from "@neondatabase/serverless";

export interface Env {
  DATABASE_URL: string;
  INFINITEPAY_HANDLE: string;
  TELEGRAM_TOKEN?: string;
  TELEGRAM_CHAT_ID?: string;
  TEST_BYPASS_TOKEN?: string;
}

interface WebhookBody {
  invoice_slug?: string;
  slug?: string;
  amount?: number;
  paid_amount?: number;
  transaction_nsu?: string;
  order_nsu?: string;
  order_id?: string;
}

async function confirmarPagamento(env: Env, orderNsu: string, transactionNsu: string, slug: string): Promise<boolean> {
  try {
    const resp = await fetch(
      "https://api.checkout.infinitepay.io/payment_check",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          handle: env.INFINITEPAY_HANDLE,
          order_nsu: orderNsu,
          transaction_nsu: transactionNsu,
          slug: slug,
        }),
      }
    );

    if (!resp.ok) {
      console.error(`Erro InfinitePay payment_check Status: ${resp.status}`);
      return false;
    }
    const data: any = await resp.json();
    return Boolean(data?.paid);
  } catch (err) {
    console.error("Erro ao chamar API de confirmação InfinitePay:", err);
    return false;
  }
}

async function notificarTelegram(env: Env, texto: string) {
  if (!env.TELEGRAM_TOKEN || !env.TELEGRAM_CHAT_ID) {
    console.warn("TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID não definidos nas envs do Worker.");
    return;
  }
  try {
    const res = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: env.TELEGRAM_CHAT_ID,
        text: texto,
        parse_mode: "HTML",
      }),
    });
    if (!res.ok) {
      console.error("Erro ao enviar mensagem Telegram:", await res.text());
    }
  } catch (err) {
    console.error("Erro na requisição ao Telegram:", err);
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    let body: WebhookBody;
    try {
      body = await request.json();
    } catch {
      return new Response("JSON inválido", { status: 400 });
    }

    // Normalização dos campos recebidos
    const orderNsu = String(body.order_nsu || body.order_id || "").trim();
    const slug = String(body.invoice_slug || body.slug || "").trim();
    const transactionNsu = String(body.transaction_nsu || "").trim();

    if (!orderNsu || !slug) {
      console.error("Payload do webhook ausente order_nsu ou slug:", body);
      return new Response("order_nsu ou slug ausente", { status: 400 });
    }

    const tokenRecebido = request.headers.get("X-Test-Bypass");
    const ehTeste = Boolean(env.TEST_BYPASS_TOKEN) && tokenRecebido === env.TEST_BYPASS_TOKEN;

    if (!ehTeste) {
      const pago = await confirmarPagamento(env, orderNsu, transactionNsu, slug);
      if (!pago) {
        return new Response("Pagamento não confirmado na InfinitePay", { status: 400 });
      }
    }

    if (!env.DATABASE_URL) {
      console.error("DATABASE_URL não configurada no Cloudflare Worker!");
      return new Response("Erro de configuração do servidor", { status: 500 });
    }

    const sql = neon(env.DATABASE_URL);
    let linhas: any[];
    try {
      linhas = await sql`
        UPDATE pedidos
        SET status = 'Pago',
            data_pagamento = now(),
            infinitepay_transaction_id = ${transactionNsu}
        WHERE id::text = ${orderNsu}
          AND status <> 'Pago'
        RETURNING id, cliente_nome, valor_total
      `;
    } catch (err) {
      console.error("Erro ao atualizar pedido no Neon:", err);
      return new Response("Erro interno ao gravar no banco", { status: 500 });
    }

    if (linhas.length > 0) {
      const pedido = linhas[0];
      const prefixo = ehTeste ? "🧪 [TESTE] " : "💰 ";
      await notificarTelegram(
        env,
        `${prefixo}<b>Pagamento confirmado!</b>\nPedido: ${pedido.id}\nCliente: ${pedido.cliente_nome}\nValor: R$ ${pedido.valor_total}`
      );
    } else {
      console.log(`Nenhum pedido atualizado para id=${orderNsu} (não encontrado ou já estava Pago).`);
    }

    return new Response(
      JSON.stringify({ ok: true, teste: ehTeste, pedidos_atualizados: linhas.length }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  },
};
