// 每日精選發到 Threads：Telegram 說明圖下面按「發到 Threads」，這裡收到後發文，再把留言區連結貼成第一則回覆。
//
// /auth            用 Threads 帳號授權（只有 app 的 Threads 測試人員能授權），完成後順便設定 Telegram webhook
// /auth/callback   授權完成的轉址
// /telegram        Telegram webhook，處理按鈕
// 排程每天更新一次 Threads token（長期 token 60 天到期，更新後重新計算）

const GRAPH = "https://graph.threads.com";
const SCOPES = "threads_basic,threads_content_publish";
const POLL_INTERVAL_MS = 3000;
const POLL_ATTEMPTS = 15;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/auth") return startAuth(url, env);
    if (url.pathname === "/auth/callback") return finishAuth(url, env).catch((e) => page(`授權失敗：${e.message}`, 500));
    if (url.pathname === "/telegram" && request.method === "POST") return onTelegram(request, env);
    return new Response("not found", { status: 404 });
  },

  async scheduled(_event, env) {
    await refreshToken(env);
  },
};

// ---------- 授權 ----------

async function startAuth(url, env) {
  const state = crypto.randomUUID();
  await env.KV.put(`state:${state}`, "1", { expirationTtl: 600 });
  const params = new URLSearchParams({
    client_id: env.THREADS_APP_ID,
    redirect_uri: `${url.origin}/auth/callback`,
    scope: SCOPES,
    response_type: "code",
    state,
  });
  return Response.redirect(`https://threads.com/oauth/authorize?${params}`, 302);
}

async function finishAuth(url, env) {
  const state = url.searchParams.get("state");
  if (!state || !(await env.KV.get(`state:${state}`))) return page("授權逾時或連結無效，請重新打開 /auth", 400);
  await env.KV.delete(`state:${state}`);
  const code = (url.searchParams.get("code") || "").replace(/#_$/, "");
  if (!code) return page(`沒有拿到授權：${url.searchParams.get("error_description") || "未知原因"}`, 400);

  const short = await call("POST", "/oauth/access_token", {
    client_id: env.THREADS_APP_ID,
    client_secret: env.THREADS_APP_SECRET,
    grant_type: "authorization_code",
    redirect_uri: `${url.origin}/auth/callback`,
    code,
  });
  const long = await call("GET", "/access_token", {
    grant_type: "th_exchange_token",
    client_secret: env.THREADS_APP_SECRET,
    access_token: short.access_token,
  });
  await saveAuth(env, { token: long.access_token, expiresIn: long.expires_in });
  await env.KV.put("origin", url.origin);

  // webhook 的密語只有這裡和 Telegram 知道，用來確認請求真的來自 Telegram
  const secret = crypto.randomUUID().replaceAll("-", "");
  await env.KV.put("webhook_secret", secret);
  await telegram(env, "setWebhook", {
    url: `${url.origin}/telegram`,
    secret_token: secret,
    allowed_updates: ["callback_query"],
  });
  return page("完成了：Threads 已授權，Telegram 的「發到 Threads」按鈕可以用了。");
}

async function saveAuth(env, { token, expiresIn }) {
  await env.KV.put("auth", JSON.stringify({
    token,
    refreshedAt: Date.now(),
    expiresAt: Date.now() + (expiresIn || 0) * 1000,
  }));
}

async function loadAuth(env) {
  const auth = JSON.parse((await env.KV.get("auth")) || "null");
  if (!auth) throw new Error("還沒授權 Threads，請先打開 Worker 的 /auth");
  return auth;
}

async function refreshToken(env) {
  const auth = JSON.parse((await env.KV.get("auth")) || "null");
  // token 至少要 24 小時才能更新
  if (!auth || Date.now() - auth.refreshedAt < 23 * 3600 * 1000) return;
  try {
    const data = await call("GET", "/refresh_access_token", {
      grant_type: "th_refresh_token",
      access_token: auth.token,
    });
    await saveAuth(env, { token: data.access_token, expiresIn: data.expires_in });
  } catch (e) {
    const origin = await env.KV.get("origin");
    await notify(env, `⚠️ Threads token 更新失敗：${e.message}\n請重新授權：${origin ? `${origin}/auth` : "打開 Worker 的 /auth"}`);
  }
}

// ---------- 發文 ----------

async function onTelegram(request, env) {
  const secret = await env.KV.get("webhook_secret");
  if (!secret || request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== secret) {
    return new Response("forbidden", { status: 403 });
  }
  const query = (await request.json()).callback_query;
  if (!query?.data?.startsWith("post:") || String(query.message?.chat?.id) !== String(env.TELEGRAM_CHAT_ID)) {
    return new Response("ok");
  }
  const day = query.data.slice("post:".length);

  // 防止連按或 Telegram 重送時發兩次
  if (await env.KV.get(`lock:${day}`)) {
    await answer(env, query, "正在發文或已經發過了");
    return new Response("ok");
  }
  await env.KV.put(`lock:${day}`, "1", { expirationTtl: 600 });
  await answer(env, query, "發文中，大約半分鐘…");

  try {
    const permalink = await publish(env, day, query.message.caption ?? query.message.text ?? "");
    await telegram(env, "editMessageReplyMarkup", {
      chat_id: query.message.chat.id,
      message_id: query.message.message_id,
      reply_markup: { inline_keyboard: [[{ text: "✅ 已發到 Threads", url: permalink }]] },
    });
  } catch (e) {
    await env.KV.delete(`lock:${day}`);
    await notify(env, `❌ 發到 Threads 失敗：${e.message}\n修好之後可以再按一次按鈕。`);
  }
  return new Response("ok");
}

async function publish(env, day, text) {
  if (!text.trim()) throw new Error("這則訊息沒有貼文內容");
  const res = await fetch(`${env.PICKS_URL}${day}.json`);
  if (!res.ok) throw new Error(`找不到 ${day} 的精選資料（HTTP ${res.status}）`);
  const pick = await res.json();
  const auth = await loadAuth(env);
  // 發文和回覆分開記錄：回覆失敗時再按一次只補回覆，不會重複發文
  const done = JSON.parse((await env.KV.get(`post:${day}`)) || "{}");

  if (!done.postId) {
    const post = { media_type: pick.image ? "IMAGE" : "TEXT", text };
    if (pick.image) post.image_url = `${env.PAGES_URL}${pick.image}`;
    if (env.THREADS_TOPIC) post.topic_tag = env.THREADS_TOPIC;
    done.postId = await createAndPublish(auth, post);
    done.permalink = (await call("GET", `/v1.0/${done.postId}`, {
      fields: "permalink",
      access_token: auth.token,
    })).permalink;
    await env.KV.put(`post:${day}`, JSON.stringify(done));
  }
  if (!done.replied) {
    await createAndPublish(auth, {
      media_type: "TEXT",
      text: `🔗 留言區連結：${pick.repo.url}`,
      reply_to_id: done.postId,
    });
    done.replied = true;
    await env.KV.put(`post:${day}`, JSON.stringify(done));
  }
  return done.permalink;
}

async function createAndPublish(auth, params) {
  const { id } = await call("POST", "/v1.0/me/threads", { ...params, access_token: auth.token });
  // Threads 要先處理完圖片才能發佈，處理狀態變成 FINISHED 再發
  for (let i = 0; i < POLL_ATTEMPTS; i++) {
    const { status, error_message } = await call("GET", `/v1.0/${id}`, {
      fields: "status,error_message",
      access_token: auth.token,
    });
    if (status === "FINISHED") {
      const published = await call("POST", "/v1.0/me/threads_publish", {
        creation_id: id,
        access_token: auth.token,
      });
      return published.id;
    }
    if (status === "ERROR" || status === "EXPIRED") throw new Error(`Threads 處理失敗：${error_message || status}`);
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
  throw new Error("Threads 處理太久，沒有發出去");
}

// ---------- 共用 ----------

async function call(method, path, params) {
  const body = new URLSearchParams(params);
  const res = method === "GET"
    ? await fetch(`${GRAPH}${path}?${body}`)
    : await fetch(`${GRAPH}${path}`, { method, body });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.error) {
    throw new Error(data.error?.error_user_msg || data.error?.message || data.error_message || `HTTP ${res.status}`);
  }
  return data;
}

async function telegram(env, method, body) {
  const res = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!data.ok) throw new Error(`Telegram ${method}: ${data.description}`);
  return data.result;
}

function answer(env, query, text) {
  return telegram(env, "answerCallbackQuery", { callback_query_id: query.id, text });
}

function notify(env, text) {
  return telegram(env, "sendMessage", { chat_id: env.TELEGRAM_CHAT_ID, text, disable_web_page_preview: true });
}

function page(message, status = 200) {
  const escaped = message.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  return new Response(`<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<body style="font:18px/1.6 system-ui;padding:24px">${escaped}</body>`, {
    status,
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}
