import { neon } from "@neondatabase/serverless";

export interface Env {
  DATABASE_URL: string;
  INFINITEPAY_HANDLE: string;
  INFINITEPAY_API_KEY?: string;
  TELEGRAM_TOKEN?: string;
  TELEGRAM_CHAT_ID?: string;
  TEST_BYPASS_TOKEN?: string;
}

const EVENTOS_IGNORADOS = new Set([
  "created",
  "canceled",
  "cancelled",
  "refunded",
  "payment_failed",
  "failed",
  "expired",
]);

function texto(v: unknown): string {
  return v === undefined || v === null ? "" : String(v).trim();
}

function escaparHtml(v: unknown): string {
  return texto(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/**
 * Aceita o payload tanto no formato plano (order_nsu, invoice_slug, ...)
 * quanto aninhado em data / payload / invoice / order.
 */
function achatarPayload(body: any): Record<string, any> {
  if (!body || typeof body !== "object") return {};
  let resultado: Record<string, any> = { ...body };
  for (const chave of ["data", "payload", "invoice", "order", "transaction"]) {
    const interno = body[chave];
    if (interno && typeof interno === "object" && !Array.isArray(interno)) {
      resultado = { ...interno, ...resultado };
    }
  }
  return resultado;
}

async function confirmarPagamento(
  env: Env,
  orderNsu: string,
  transactionNsu: string,
  slug: string
): Promise<boolean> {
  try {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };
    if (env.INFINITEPAY_API_KEY) headers["X-Api-Key"] = env.INFINITEPAY_API_KEY;

    const corpo: Record<string, string> = { order_nsu: orderNsu };
    if (env.INFINITEPAY_HANDLE) corpo.handle = env.INFINITEPAY_HANDLE;
    if (transactionNsu) corpo.transaction_nsu = transactionNsu;
    if (slug) corpo.slug = slug;

    const resp = await fetch("https://api.checkout.infinitepay.io/payment_check", {
      method: "POST",
      headers,
      body: JSON.stringify(corpo),
    });

    if (!resp.ok) {
      console.error(`Erro InfinitePay payment_check Status: ${resp.status} Corpo: ${await resp.text()}`);
      return false;
    }
    const data: any = await resp.json();
    return Boolean(data?.paid ?? data?.data?.paid);
  } catch (err) {
    console.error("Erro ao chamar API de confirmação InfinitePay:", err);
    return false;
  }
}

async function notificarTelegram(env: Env, msg: string) {
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
        text: msg,
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

    let bruto: any;
    try {
      bruto = await request.json();
    } catch {
      return new Response("JSON inválido", { status: 400 });
    }

    const body = achatarPayload(bruto);

    // Eventos que não são de pagamento aprovado: confirma recebimento e ignora
    const evento = texto(bruto?.event ?? bruto?.event_type ?? bruto?.type ?? body.event ?? body.status).toLowerCase();
    if (evento && EVENTOS_IGNORADOS.has(evento)) {
      console.log(`Evento "${evento}" ignorado.`);
      return new Response(JSON.stringify({ ok: true, ignorado: evento }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    const orderNsu = texto(body.order_nsu || body.order_id);
    const slug = texto(body.invoice_slug || body.slug);
    const transactionNsu = texto(body.transaction_nsu);

    if (!orderNsu) {
      console.error("Payload do webhook sem order_nsu:", JSON.stringify(bruto));
      return new Response("order_nsu ausente", { status: 400 });
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
            infinitepay_transaction_id = ${transactionNsu || null}
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
        `${prefixo}<b>Pagamento confirmado!</b>\nPedido: ${escaparHtml(pedido.id)}\nCliente: ${escaparHtml(pedido.cliente_nome)}\nValor: R$ ${escaparHtml(pedido.valor_total)}`
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
