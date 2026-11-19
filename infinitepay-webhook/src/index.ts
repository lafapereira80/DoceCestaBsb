import { neon } from "@neondatabase/serverless";

export interface Env {
  DATABASE_URL?: string;
  INFINITEPAY_HANDLE?: string;
  TELEGRAM_TOKEN?: string;
  TELEGRAM_CHAT_ID?: string;
  TEST_BYPASS_TOKEN?: string;
}

const HANDLE_PADRAO = "vanessa-hagen";

const EVENTOS_IGNORADOS = new Set([
  "created", "canceled", "cancelled", "refunded", "payment_failed", "failed", "expired",
]);

// Status em que o pedido já foi pago (ou já avançou na operação): nunca voltam para "Pago"
const STATUS_JA_PAGOS = new Set([
  "Pago", "Em Montagem", "Pronto", "Enviado", "Em Rota de Entrega", "Entregue",
]);

type Pedido = {
  id: string;
  status: string | null;
  cliente_nome: string | null;
  valor_total: number | string | null;
  infinitepay_transaction_id: string | null;
};

function texto(v: unknown): string {
  return v === undefined || v === null ? "" : String(v).trim();
}

function escaparHtml(v: unknown): string {
  return texto(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

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

function json(obj: unknown, status = 200): Response {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/* ------------------------------ Banco de dados ------------------------------ */

const temBanco = (env: Env) => Boolean(env.DATABASE_URL);

async function buscarPedido(env: Env, id: string): Promise<Pedido | null> {
  const sql = neon(env.DATABASE_URL!);
  const linhas = (await sql`
    SELECT id, status, cliente_nome, valor_total, infinitepay_transaction_id
    FROM pedidos WHERE id::text = ${id} LIMIT 1
  `) as Pedido[];
  return linhas[0] ?? null;
}

async function marcarComoPago(env: Env, id: string, transactionNsu: string): Promise<void> {
  const sql = neon(env.DATABASE_URL!);
  await sql`
    UPDATE pedidos
    SET status = 'Pago',
        data_pagamento = now(),
        infinitepay_transaction_id = ${transactionNsu || null}
    WHERE id::text = ${id}
  `;
}

async function gravarSoTransacao(env: Env, id: string, transactionNsu: string): Promise<void> {
  const sql = neon(env.DATABASE_URL!);
  await sql`UPDATE pedidos SET infinitepay_transaction_id = ${transactionNsu} WHERE id::text = ${id}`;
}

async function buscarLinkPorCodigo(env: Env, codigo: string): Promise<{ infinitepay_url: string; status: string | null } | null> {
  const sql = neon(env.DATABASE_URL!);
  const linhas: any[] = await sql`
    SELECT infinitepay_url, status
    FROM pedidos
    WHERE id::text LIKE ${codigo + "-%"} AND infinitepay_url IS NOT NULL
    LIMIT 1
  `;
  return linhas[0] ?? null;
}

/* --------------------------------- InfinitePay -------------------------------- */

type ResultadoCheck = "pago" | "nao_pago" | "indisponivel";

async function confirmarPagamento(env: Env, orderNsu: string, transactionNsu: string, slug: string): Promise<ResultadoCheck> {
  try {
    const corpo: Record<string, string> = {
      handle: texto(env.INFINITEPAY_HANDLE) || HANDLE_PADRAO,
      order_nsu: orderNsu,
    };
    if (transactionNsu) corpo.transaction_nsu = transactionNsu;
    if (slug) corpo.slug = slug;

    const resp = await fetch("https://api.checkout.infinitepay.io/payment_check", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(corpo),
    });

    if (!resp.ok) {
      console.error(`payment_check HTTP ${resp.status}: ${await resp.text()} | enviado: ${JSON.stringify(corpo)}`);
      return "indisponivel";
    }
    const data: any = await resp.json();
    console.log("payment_check resposta:", JSON.stringify(data));
    const d = data?.data ?? data;
    const pago = d?.paid === true || d?.paid === "true" || Number(d?.paid_amount ?? 0) > 0;
    return pago ? "pago" : "nao_pago";
  } catch (err) {
    console.error("Erro ao chamar payment_check:", err);
    return "indisponivel";
  }
}

async function notificarTelegram(env: Env, msg: string) {
  if (!env.TELEGRAM_TOKEN || !env.TELEGRAM_CHAT_ID) return;
  try {
    const res = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: env.TELEGRAM_CHAT_ID, text: msg, parse_mode: "HTML" }),
    });
    if (!res.ok) console.error("Erro Telegram:", await res.text());
  } catch (err) {
    console.error("Erro na requisição ao Telegram:", err);
  }
}

/* ------------------------------------ Páginas ---------------------------------- */

function paginaHtml(titulo: string, mensagem: string, status: number): Response {
  const html = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${titulo}</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#fff9f2;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#3b2417}
main{max-width:420px;margin:24px;padding:32px 26px;border-radius:24px;background:#fff;box-shadow:0 12px 40px rgba(60,35,18,.12);text-align:center}
h1{font-size:22px;margin:0 0 10px}p{margin:0;color:#7a6657;line-height:1.5}</style></head>
<body><main><h1>${titulo}</h1><p>${mensagem}</p></main></body></html>`;
  return new Response(html, {
    status,
    headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store", "X-Robots-Tag": "noindex" },
  });
}

async function redirecionarLinkCurto(env: Env, codigo: string): Promise<Response> {
  if (!/^[0-9a-f]{8}$/.test(codigo)) {
    return paginaHtml("Link inválido", "Confira o endereço recebido ou peça um novo link à Doce Cesta pelo WhatsApp.", 404);
  }
  if (!temBanco(env)) {
    return paginaHtml("Serviço indisponível", "Tente novamente em instantes.", 500);
  }
  try {
    const linha = await buscarLinkPorCodigo(env, codigo);
    if (!linha) {
      return paginaHtml("Link não encontrado", "Este link expirou ou foi substituído. Peça um novo link à Doce Cesta pelo WhatsApp.", 404);
    }
    if (linha.status && STATUS_JA_PAGOS.has(linha.status)) {
      return paginaHtml("Pagamento já confirmado ✅", "Recebemos o pagamento deste pedido. Obrigado pela confiança!", 200);
    }
    if (!/^https:\/\//.test(String(linha.infinitepay_url))) {
      return paginaHtml("Link indisponível", "Peça um novo link à Doce Cesta pelo WhatsApp.", 404);
    }
    return new Response(null, {
      status: 302,
      headers: { Location: String(linha.infinitepay_url), "Cache-Control": "no-store", "X-Robots-Tag": "noindex" },
    });
  } catch (err) {
    console.error("Erro ao resolver link curto:", err);
    return paginaHtml("Serviço indisponível", "Tente novamente em instantes.", 500);
  }
}

/* ------------------------------------ Worker ----------------------------------- */

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    if (request.method === "GET" || request.method === "HEAD") {
      const url = new URL(request.url);
      const m = url.pathname.match(/^\/(?:p\/)?([0-9a-fA-F]{8})\/?$/);
      if (m) return redirecionarLinkCurto(env, m[1].toLowerCase());
      if (url.pathname === "/" || url.pathname === "/health") {
        return new Response("ok", { status: 200, headers: { "Content-Type": "text/plain" } });
      }
      return paginaHtml("Página não encontrada", "Confira o endereço digitado.", 404);
    }
    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    let bruto: any;
    try {
      bruto = await request.json();
    } catch {
      return new Response("JSON inválido", { status: 400 });
    }
    console.log("Webhook recebido:", JSON.stringify(bruto));

    const body = achatarPayload(bruto);

    const evento = texto(bruto?.event ?? bruto?.event_type ?? bruto?.type).toLowerCase();
    if (evento && EVENTOS_IGNORADOS.has(evento)) {
      return json({ ok: true, ignorado: evento });
    }

    const orderNsu = texto(body.order_nsu || body.order_id);
    const slug = texto(body.invoice_slug || body.slug);
    const transactionNsu = texto(body.transaction_nsu);

    if (!orderNsu) {
      console.error("Payload do webhook sem order_nsu:", JSON.stringify(bruto));
      return new Response("order_nsu ausente", { status: 400 });
    }

    if (!temBanco(env)) {
      console.error("DATABASE_URL não configurada no Worker.");
      return new Response("Erro de configuração do servidor", { status: 500 });
    }

    const tokenRecebido = request.headers.get("X-Test-Bypass");
    const ehTeste = Boolean(env.TEST_BYPASS_TOKEN) && tokenRecebido === env.TEST_BYPASS_TOKEN;

    let pedido: Pedido | null;
    try {
      pedido = await buscarPedido(env, orderNsu);
    } catch (err) {
      console.error("Erro ao consultar pedido:", err);
      return new Response("Erro interno ao consultar o banco", { status: 500 });
    }
    if (!pedido) {
      console.error(`Pedido não encontrado para order_nsu=${orderNsu}. Confira se o Worker aponta para o mesmo banco do app.`);
      return json({ ok: true, pedidos_atualizados: 0, motivo: "pedido_nao_encontrado" });
    }

    if (!ehTeste) {
      const check = await confirmarPagamento(env, orderNsu, transactionNsu, slug);
      if (check === "nao_pago") {
        return new Response("Pagamento não confirmado na InfinitePay", { status: 400 });
      }
      if (check === "indisponivel") {
        // API de verificação fora do ar / recusou o formato: só aceita se o webhook trouxer
        // os dados completos e o valor pago cobrir o total do pedido (order_nsu é um UUID não adivinhável).
        const pagoCentavos = Number(body.paid_amount ?? body.amount ?? 0);
        const esperado = Math.round(Number(pedido.valor_total ?? 0) * 100);
        const confiavel = Boolean(transactionNsu && slug) && pagoCentavos > 0 && pagoCentavos >= esperado;
        if (!confiavel) {
          console.error("Verificação indisponível e payload insuficiente; pagamento NÃO registrado.");
          return new Response("Não foi possível confirmar o pagamento", { status: 503 });
        }
        console.warn("payment_check indisponível; pagamento aceito pelo payload do webhook.");
      }
    }

    let atualizados = 0;
    try {
      if (!pedido.status || !STATUS_JA_PAGOS.has(pedido.status)) {
        await marcarComoPago(env, orderNsu, transactionNsu);
        atualizados = 1;
      } else if (!pedido.infinitepay_transaction_id && transactionNsu) {
        await gravarSoTransacao(env, orderNsu, transactionNsu);
      }
    } catch (err) {
      console.error("Erro ao atualizar pedido:", err);
      return new Response("Erro interno ao gravar no banco", { status: 500 });
    }

    if (atualizados > 0) {
      const prefixo = ehTeste ? "🧪 [TESTE] " : "💰 ";
      ctx.waitUntil(
        notificarTelegram(
          env,
          `${prefixo}<b>Pagamento confirmado!</b>\nPedido: ${escaparHtml(pedido.id)}\nCliente: ${escaparHtml(pedido.cliente_nome)}\nValor: R$ ${escaparHtml(pedido.valor_total)}`
        )
      );
    }

    return json({ ok: true, teste: ehTeste, pedidos_atualizados: atualizados });
  },
};
