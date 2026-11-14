// 每日精選發到 Threads：Telegram 說明圖下面的按鈕可以排到最佳時段或馬上發，發完再把留言區連結貼成第一則回覆。
// 也會記錄每篇貼文的成效，用你自己的數據算出最佳發文時段，每週一早上在 Telegram 送週報。
// 有新留言時送到 Telegram，附上 AI 草擬的回覆，你按「用這個回」或直接回覆那則訊息才會送出。
//
// /auth            用 Threads 帳號授權（只有 app 的 Threads 測試人員能授權），完成後順便設定 Telegram webhook
// /auth/callback   授權完成的轉址
// /telegram        Telegram webhook，處理按鈕，以及你回覆留言通知的文字
// 排程每 15 分鐘跑一次：發排好的文、發文 1 小時後回報成績、檢查新留言、每小時更新成效、每天更新 token、每週一送週報

import * as OpenCC from "opencc-js/cn2t";
import topicsConfig from "../topics.json";

const TOPICS = topicsConfig.topics;

const GRAPH = "https://graph.threads.com";
// 回覆要 threads_manage_replies，讀留言要 threads_read_replies，讀成效要 threads_manage_insights
const SCOPES = "threads_basic,threads_content_publish,threads_manage_replies,threads_read_replies,threads_manage_insights";
const POLL_INTERVAL_MS = 3000;
const POLL_ATTEMPTS = 15;

const HOUR = 3600 * 1000;
const DAY = 24 * HOUR;
const TAIPEI_OFFSET = 8 * HOUR;
const METRICS = ["views", "likes", "replies", "reposts", "quotes", "shares"];
// 自己的貼文累積到這麼多篇有成效資料，才改用自己的數據挑時段
const MIN_POSTS_FOR_BEST_TIME = 10;
const HISTORY_LIMIT = 100;
// 免費方案每次執行最多 50 個對外請求，成效分批更新
const INSIGHTS_PER_RUN = 20;
// 發文後多久內的留言要通知，每次最多送幾則（其餘下次再送）
const COMMENT_WATCH = 48 * HOUR;
const COMMENTS_PER_RUN = 5;
const HIDDEN_STATUSES = ["HIDDEN", "COVERED", "BLOCKED", "RESTRICTED"];
const toTraditional = OpenCC.Converter({ from: "cn", to: "twp" });
// 還沒有自己的數據時，台北時間的時段偏好順序（台灣 Threads 平日晚上互動最高，中午次之）
const DEFAULT_HOURS = [21, 20, 22, 19, 18, 12, 17, 16, 13, 15, 14, 11, 10, 23, 9];

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/auth") return startAuth(url, env);
    if (url.pathname === "/auth/callback") return finishAuth(url, env).catch((e) => page(`授權失敗：${e.message}`, 500));
    if (url.pathname === "/telegram" && request.method === "POST") return onTelegram(request, env);
    return new Response("not found", { status: 404 });
  },

  async scheduled(event, env) {
    const t = taipei(event.scheduledTime);
    const published = await run("scheduled posts", () => runSchedule(env, event.scheduledTime));
    if (!published) await run("comments", () => checkComments(env, event.scheduledTime));
    // 發文那次已經用掉不少請求，成效留到下次
    if (!published && t.minute >= 30 && t.minute < 45) await run("insights", () => updateInsights(env, event.scheduledTime));
    if (t.hour === 11 && t.minute < 15) await run("token", () => refreshToken(env));
    if (t.weekday === 1 && t.hour === 8 && t.minute < 15) await run("weekly", () => weeklyReport(env, event.scheduledTime));
  },
};

async function run(name, job) {
  try {
    return await job();
  } catch (e) {
    console.log(`${name} failed: ${e.message}`);
  }
}

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
    allowed_updates: ["callback_query", "message"],
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
  const auth = await getJSON(env, "auth", null);
  if (!auth) throw new Error("還沒授權 Threads，請先打開 Worker 的 /auth");
  return auth;
}

async function refreshToken(env) {
  const auth = await getJSON(env, "auth", null);
  // token 至少要 24 小時才能更新
  if (!auth || Date.now() - auth.refreshedAt < 23 * HOUR) return;
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

// ---------- Telegram 按鈕 ----------
//
// later:<日期>    排到最佳時段          post:<日期>     馬上發
// topics:<日期>   列出頻道              topic:<日期>:<第幾個或 n=不加>  選頻道
// cancel:<日期>   取消排程              back:<日期>     回到主按鈕
// 舊訊息的 post:<日期>:<第幾個或 n> 是「選了頻道就馬上發」

async function onTelegram(request, env) {
  const secret = await env.KV.get("webhook_secret");
  if (!secret || request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== secret) {
    return new Response("forbidden", { status: 403 });
  }
  const update = await request.json();
  const query = update.callback_query;
  const chatId = query ? query.message?.chat?.id : update.message?.chat?.id;
  if (String(chatId) !== String(env.TELEGRAM_CHAT_ID)) return new Response("ok");
  try {
    if (update.message?.reply_to_message && update.message.text) {
      await replyWithOwnText(env, update.message);
    } else if (query?.data?.startsWith("c:")) {
      await handleCommentButton(env, query, query.data.slice(2));
    } else if (query?.data) {
      const [action, day, arg] = query.data.split(":");
      if (day) await handleButton(env, query, action, day, arg);
    }
  } catch (e) {
    // 回 200，免得 Telegram 一直重送同一個按鈕
    await notify(env, `❌ 按鈕處理失敗：${e.message}`).catch(() => {});
  }
  return new Response("ok");
}

async function handleButton(env, query, action, day, arg) {
  const msg = { chatId: query.message.chat.id, messageId: query.message.message_id };
  if (action === "topics") {
    await answer(env, query);
    return setKeyboard(env, msg, topicKeyboard(day));
  }
  if (action === "back") {
    await answer(env, query);
    return setKeyboard(env, msg, await mainKeyboard(env, day));
  }
  if (action === "topic") {
    const topic = topicFrom(arg);
    if (topic === undefined) return answer(env, query, "這個頻道已經不在清單裡了，請重新選");
    await env.KV.put(`topic:${day}`, topic, { expirationTtl: 14 * 24 * 3600 });
    await answer(env, query, topic ? `頻道改成 ${topic}` : "這篇不加頻道");
    return setKeyboard(env, msg, await mainKeyboard(env, day));
  }
  if (action === "cancel") {
    await updateSchedule(env, (s) => delete s[day]);
    await answer(env, query, "已取消排程");
    return setKeyboard(env, msg, await mainKeyboard(env, day));
  }
  if (action === "later") return schedulePost(env, query, msg, day);
  if (action === "post") {
    const topic = arg === undefined ? await chosenTopic(env, day) : topicFrom(arg);
    if (topic === undefined) return answer(env, query, "這個頻道已經不在清單裡了，請重新選");
    return postNow(env, query, msg, day, topic);
  }
}

function topicFrom(arg) {
  return arg === "n" ? "" : TOPICS[Number(arg)];
}

async function chosenTopic(env, day) {
  const topic = await env.KV.get(`topic:${day}`);
  return topic ?? (TOPICS[0] || "");
}

// 說明圖下面的按鈕。沒排程、預設頻道時要跟 trending/notify.py 的 _publish_button 一致
async function mainKeyboard(env, day) {
  const topic = await chosenTopic(env, day);
  const scheduled = (await getJSON(env, "schedule", {}))[day];
  const first = scheduled
    ? [{ text: `⏰ ${slotLabel(env, scheduled.at)}・取消`, callback_data: `cancel:${day}` }]
    : [{ text: "⏰ 排到最佳時段", callback_data: `later:${day}` }];
  const rows = [[...first, { text: "🚀 現在發", callback_data: `post:${day}` }]];
  if (TOPICS.length) rows.push([{ text: `🏷 頻道：${topic || "不加"}`, callback_data: `topics:${day}` }]);
  return { inline_keyboard: rows };
}

function topicKeyboard(day) {
  return {
    inline_keyboard: [
      ...TOPICS.map((t, i) => [{ text: t, callback_data: `topic:${day}:${i}` }]),
      [{ text: "不加頻道", callback_data: `topic:${day}:n` }],
      [{ text: "↩️ 返回", callback_data: `back:${day}` }],
    ],
  };
}

function postedKeyboard(done) {
  const where = done.topic ? `（${done.topic}）` : "";
  return { inline_keyboard: [[{ text: `✅ 已發到 Threads${where}`, url: done.permalink }]] };
}

async function setKeyboard(env, msg, markup) {
  try {
    await telegram(env, "editMessageReplyMarkup", {
      chat_id: msg.chatId,
      message_id: msg.messageId,
      reply_markup: markup,
    });
  } catch (e) {
    // 連按兩次時按鈕沒有變，Telegram 會回錯誤，不用理它
    if (!e.message.includes("message is not modified")) throw e;
  }
}

async function schedulePost(env, query, msg, day) {
  const text = query.message.caption ?? query.message.text ?? "";
  if (!text.trim()) return answer(env, query, "這則訊息沒有貼文內容");
  const posted = await alreadyPosted(env, day);
  if (posted) {
    await answer(env, query, "這篇已經發過了");
    return setKeyboard(env, msg, postedKeyboard(posted));
  }
  const { at, basis } = await nextSlot(env, Date.now());
  await updateSchedule(env, (s) => { s[day] = { at, text, ...msg }; });
  await answer(env, query, `已排在 ${slotLabel(env, at)} 發。${basis}`);
  await setKeyboard(env, msg, await mainKeyboard(env, day));
}

async function postNow(env, query, msg, day, topic) {
  // 防止連按或 Telegram 重送時發兩次
  if (await env.KV.get(`lock:${day}`)) return answer(env, query, "正在發文或已經發過了");
  await env.KV.put(`lock:${day}`, "1", { expirationTtl: 600 });
  await answer(env, query, "發文中，大約半分鐘…");
  await updateSchedule(env, (s) => delete s[day]);
  try {
    const done = await publish(env, day, query.message.caption ?? query.message.text ?? "", topic);
    await afterPublish(env, msg, done);
  } catch (e) {
    await env.KV.delete(`lock:${day}`);
    await notify(env, `❌ 發到 Threads 失敗：${e.message}\n修好之後可以再按一次按鈕。`);
  }
}

// ---------- 排程 ----------

async function updateSchedule(env, change) {
  const schedule = await getJSON(env, "schedule", {});
  const before = JSON.stringify(schedule);
  change(schedule);
  if (JSON.stringify(schedule) !== before) await env.KV.put("schedule", JSON.stringify(schedule));
}

async function runSchedule(env, now) {
  let published = false;
  const schedule = await getJSON(env, "schedule", {});
  const due = Object.entries(schedule).filter(([, job]) => job.at <= now);
  if (due.length) {
    // 先從排程拿掉，失敗也不會每 15 分鐘重試一次
    await updateSchedule(env, (s) => due.forEach(([day]) => delete s[day]));
    for (const [day, job] of due) {
      const msg = { chatId: job.chatId, messageId: job.messageId };
      if (await env.KV.get(`lock:${day}`)) continue;
      await env.KV.put(`lock:${day}`, "1", { expirationTtl: 600 });
      try {
        await afterPublish(env, msg, await publish(env, day, job.text, await chosenTopic(env, day)));
        published = true;
      } catch (e) {
        await env.KV.delete(`lock:${day}`);
        await setKeyboard(env, msg, await mainKeyboard(env, day)).catch(() => {});
        await notify(env, `❌ 排程發文失敗：${e.message}\n修好之後按那則的「🚀 現在發」或重新排程。`);
      }
    }
  }
  await runFollowups(env, now).catch((e) => console.log(`followups failed: ${e.message}`));
  return published;
}

// 發完之後：按鈕換成貼文連結、提醒去回留言、排 1 小時後的成績回報、記進成效紀錄
async function afterPublish(env, msg, done) {
  await setKeyboard(env, msg, postedKeyboard(done));
  if (!done.fresh) return;
  await notify(env, [
    `✅ 已發到 Threads${done.topic ? `（${done.topic}）` : ""}`,
    done.permalink,
    "",
    "💬 接下來 30 分鐘記得回每一則留言，發文初期有沒有人討論最影響觸及。1 小時後我會回報成績。",
  ].join("\n"));
  const followups = await getJSON(env, "followups", []);
  followups.push({ postId: done.postId, permalink: done.permalink, at: Date.now() + HOUR });
  await env.KV.put("followups", JSON.stringify(followups));
  const history = await getJSON(env, "history", { posts: [] });
  if (!history.posts.some((p) => p.id === done.postId)) {
    history.posts.push({ id: done.postId, at: Date.now(), permalink: done.permalink, hook: done.hook, topic: done.topic });
    await env.KV.put("history", JSON.stringify(history));
  }
}

async function runFollowups(env, now) {
  const followups = await getJSON(env, "followups", []);
  const due = followups.filter((f) => f.at <= now);
  if (!due.length) return;
  await env.KV.put("followups", JSON.stringify(followups.filter((f) => f.at > now)));
  const auth = await loadAuth(env);
  for (const f of due) {
    const m = await fetchMetrics(auth, f.postId).catch(() => null);
    if (!m) continue;
    await notify(env, `⏱ 發文 1 小時：👀 ${m.views} 觀看・💬 ${m.replies} 留言・❤️ ${m.likes} 讚・🔁 ${m.reposts + m.quotes} 轉發\n${f.permalink}`);
  }
}

// 下一個最佳時段（台北時間整點）：照排名一個個試，跳過已經過了的、發文後 1 小時你那邊不方便回留言的
async function nextSlot(env, now) {
  const { hours, basis } = await rankedHours(env);
  for (let days = 0; days <= 1; days++) {
    for (const hour of hours) {
      const at = Date.parse(`${taipei(now + days * DAY).date}T${pad(hour)}:00:00+08:00`);
      if (at >= now + 10 * 60 * 1000 && awake(env, at)) {
        const shifted = hour !== hours[0] ? `；${hours[0]} 點你那邊太晚或已經過了，改排 ${hour} 點` : "";
        return { at, basis: basis + shifted };
      }
    }
  }
  return { at: now + 10 * 60 * 1000, basis: "找不到你方便的時段，10 分鐘後發" };
}

// 時段排名：自己的貼文夠多就照觀看中位數，不夠就用 DEFAULT_HOURS
async function rankedHours(env) {
  const posts = (await getJSON(env, "history", { posts: [] })).posts.filter((p) => p.metrics);
  const fallback = [...DEFAULT_HOURS, ...Array.from({ length: 24 }, (_, h) => h).filter((h) => !DEFAULT_HOURS.includes(h))];
  if (posts.length < MIN_POSTS_FOR_BEST_TIME) {
    return { hours: fallback, basis: `台灣 Threads 平日晚上互動最高；累積 ${MIN_POSTS_FOR_BEST_TIME} 篇成效後改用你自己的數據（目前 ${posts.length} 篇）` };
  }
  const ranked = hourStats(posts).filter((b) => b.count >= 2).sort((a, b) => b.median - a.median);
  if (!ranked.length) return { hours: fallback, basis: "各時段的篇數還太少，先用預設時段" };
  const hours = [...ranked.map((b) => b.hour), ...fallback.filter((h) => !ranked.some((b) => b.hour === h))];
  return { hours, basis: `依你最近 ${posts.length} 篇，${ranked[0].hour} 點發的觀看中位數最高（${ranked[0].median}）` };
}

// 你那邊（OWNER_TZ）在 OWNER_HOURS 之內，而且發文後 1 小時都還在，才方便回留言
function awake(env, at) {
  const [from, to] = (env.OWNER_HOURS || "0-24").split("-").map(Number);
  const hour = ownerTime(env, at).hour;
  return hour >= from && hour + 1 <= to;
}

function ownerTime(env, ms) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: env.OWNER_TZ || "Asia/Taipei", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(new Date(ms));
  const get = (type) => Number(parts.find((p) => p.type === type).value);
  return { hour: get("hour"), minute: get("minute") };
}

function hourStats(posts) {
  const buckets = {};
  for (const p of posts) (buckets[taipei(p.at).hour] ||= []).push(p.metrics.views);
  return Object.entries(buckets).map(([hour, views]) => ({
    hour: Number(hour),
    count: views.length,
    median: median(views),
  }));
}

// ---------- 發文 ----------

async function publish(env, day, text, topic) {
  if (!text.trim()) throw new Error("這則訊息沒有貼文內容");
  const res = await fetch(`${env.PICKS_URL}${day}.json`);
  if (!res.ok) throw new Error(`找不到 ${day} 的精選資料（HTTP ${res.status}）`);
  const pick = await res.json();
  const auth = await loadAuth(env);
  // 發文和回覆分開記錄：回覆失敗時再按一次只補回覆，不會重複發文；貼文被刪掉了就重新發
  let done = await getJSON(env, `post:${day}`, {});
  if (done.postId && !(await postExists(auth, done.postId))) done = {};
  let fresh = false;

  if (!done.postId) {
    const post = { media_type: pick.image ? "IMAGE" : "TEXT", text };
    if (pick.image) post.image_url = `${env.PAGES_URL}${pick.image}`;
    if (topic) post.topic_tag = topic;
    done.postId = await createAndPublish(auth, post);
    done.topic = topic;
    done.permalink = (await call("GET", `/v1.0/${done.postId}`, {
      fields: "permalink",
      access_token: auth.token,
    })).permalink;
    await env.KV.put(`post:${day}`, JSON.stringify(done));
    fresh = true;
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
  return { ...done, fresh, hook: firstLine(text) };
}

async function alreadyPosted(env, day) {
  const done = await getJSON(env, `post:${day}`, {});
  if (!done.postId) return null;
  return (await postExists(await loadAuth(env), done.postId)) ? done : null;
}

// 貼文還在嗎？被刪掉會回 4xx；token 失效或 Threads 出問題時丟錯誤，免得誤判成刪掉而重複發文
async function postExists(auth, id) {
  const res = await fetch(`${GRAPH}/v1.0/${id}?${new URLSearchParams({ fields: "id", access_token: auth.token })}`);
  const data = await res.json().catch(() => ({}));
  if (res.ok && !data.error) return true;
  if (res.status >= 400 && res.status < 500 && data.error?.code !== 190) return false;
  throw new Error(data.error?.message || `HTTP ${res.status}`);
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

// ---------- 留言 ----------
//
// 留言通知的按鈕：c:ok 用 AI 的草稿回、c:redo 換一個、c:skip 不回、c:undo 取消「不回」。
// 直接回覆那則通知，就用你打的文字回。每則通知對應的留言存在 KV 的 cm:<訊息 id>（7 天）。

async function checkComments(env, now) {
  const auth = await getJSON(env, "auth", null);
  if (!auth) return;
  const watched = (await getJSON(env, "history", { posts: [] })).posts.filter((p) => now - p.at < COMMENT_WATCH);
  const seen = await getJSON(env, "comments_seen", {});
  const before = JSON.stringify(seen);
  for (const id of Object.keys(seen)) if (!watched.some((p) => p.id === id)) delete seen[id];
  let sent = 0;

  for (const post of watched) {
    if (sent >= COMMENTS_PER_RUN) break;
    let data;
    try {
      ({ data = [] } = await call("GET", `/v1.0/${post.id}/conversation`, {
        fields: "id,text,username,permalink,is_reply_owned_by_me,replied_to,hide_status",
        reverse: "false",
        access_token: auth.token,
      }));
    } catch (e) {
      if (/permission/i.test(e.message)) break; // 還沒開 threads_read_replies，等重新授權
      continue;
    }
    const known = new Set(seen[post.id] || []);
    let postText;
    for (const c of data) {
      if (known.has(c.id)) continue;
      if (c.is_reply_owned_by_me || HIDDEN_STATUSES.includes(c.hide_status) || !c.text) {
        known.add(c.id);
        continue;
      }
      if (sent >= COMMENTS_PER_RUN) break;
      postText ??= (await call("GET", `/v1.0/${post.id}`, { fields: "text", access_token: auth.token })).text || post.hook || "";
      const parentId = c.replied_to?.id;
      const parent = parentId && parentId !== post.id ? data.find((d) => d.id === parentId) : null;
      await sendComment(env, {
        commentId: c.id,
        permalink: c.permalink,
        username: c.username,
        text: c.text,
        parent: parent ? { username: parent.username, text: parent.text } : null,
        postText,
        hook: post.hook || firstLine(postText),
      });
      known.add(c.id);
      sent++;
    }
    seen[post.id] = [...known];
  }
  if (JSON.stringify(seen) !== before) await env.KV.put("comments_seen", JSON.stringify(seen));
}

async function sendComment(env, comment) {
  comment.draft = await draftReply(env, comment);
  const msg = await telegram(env, "sendMessage", {
    chat_id: env.TELEGRAM_CHAT_ID,
    text: commentMessage(comment),
    parse_mode: "HTML",
    disable_web_page_preview: true,
    reply_markup: commentKeyboard(comment),
  });
  await saveComment(env, msg.message_id, comment);
}

function saveComment(env, messageId, comment) {
  return env.KV.put(`cm:${messageId}`, JSON.stringify(comment), { expirationTtl: 7 * 24 * 3600 });
}

function commentMessage(c) {
  const lines = [`💬 <b>@${escape(c.username)}</b> 在「${escape(c.hook)}」留言：`];
  if (c.parent) lines.push(`<i>（回覆 @${escape(c.parent.username)}：${escape(c.parent.text.slice(0, 80))}）</i>`);
  lines.push(`<blockquote>${escape(c.text)}</blockquote>`, "");
  if (c.draft === "SKIP") lines.push("🤖 AI 覺得這則不用回（像廣告或沒有內容）。");
  else if (c.draft) lines.push("✍️ 建議回覆：", `<pre>${escape(c.draft)}</pre>`);
  else lines.push("🤖 AI 這次沒寫出來，可以按「🔄 換一個」再試。");
  lines.push("", "想自己寫：直接回覆這則訊息，我會用你的文字回。");
  return lines.join("\n");
}

function commentKeyboard(c) {
  const row = [];
  if (c.draft && c.draft !== "SKIP") row.push({ text: "✅ 用這個回", callback_data: "c:ok" });
  row.push({ text: c.draft === "SKIP" ? "✍️ 還是寫一個" : "🔄 換一個", callback_data: "c:redo" });
  row.push({ text: "🙈 不回", callback_data: "c:skip" });
  return { inline_keyboard: [row] };
}

async function handleCommentButton(env, query, action) {
  const msg = { chatId: query.message.chat.id, messageId: query.message.message_id };
  const c = await getJSON(env, `cm:${msg.messageId}`, null);
  if (!c) return answer(env, query, "找不到這則留言的資料（超過 7 天了）");
  if (c.replied) return answer(env, query, "這則已經回過了");

  if (action === "ok") {
    if (!c.draft || c.draft === "SKIP") return answer(env, query, "沒有可以用的草稿");
    await answer(env, query, "回覆中…");
    return sendReply(env, msg, c, c.draft);
  }
  if (action === "redo") {
    await answer(env, query, "重寫中…");
    c.avoid = [...(c.avoid || []), c.draft].filter((d) => d && d !== "SKIP").slice(-3);
    c.draft = await draftReply(env, { ...c, forceReply: true });
    c.skipped = false;
    await saveComment(env, msg.messageId, c);
    return telegram(env, "editMessageText", {
      chat_id: msg.chatId,
      message_id: msg.messageId,
      text: commentMessage(c),
      parse_mode: "HTML",
      disable_web_page_preview: true,
      reply_markup: commentKeyboard(c),
    });
  }
  if (action === "skip") {
    c.skipped = true;
    await saveComment(env, msg.messageId, c);
    await answer(env, query, "這則不回了");
    return setKeyboard(env, msg, { inline_keyboard: [[{ text: "🙈 不回（按這裡改回）", callback_data: "c:undo" }]] });
  }
  if (action === "undo") {
    c.skipped = false;
    await saveComment(env, msg.messageId, c);
    await answer(env, query);
    return setKeyboard(env, msg, commentKeyboard(c));
  }
}

async function replyWithOwnText(env, message) {
  const original = message.reply_to_message.message_id;
  const c = await getJSON(env, `cm:${original}`, null);
  if (!c) return; // 回覆的不是留言通知，不理它
  const ack = (text) => telegram(env, "sendMessage", { chat_id: env.TELEGRAM_CHAT_ID, text, reply_to_message_id: message.message_id });
  if (c.replied) return ack("這則留言已經回過了");
  const text = message.text.trim();
  if (text.length > 500) return ack("太長了，Threads 一則最多 500 字");
  await sendReply(env, { chatId: message.chat.id, messageId: original }, c, text);
  await ack(`✅ 已用你的文字回覆 @${c.username}`);
}

async function sendReply(env, msg, c, text) {
  const lock = `cmlock:${c.commentId}`;
  if (await env.KV.get(lock)) return;
  await env.KV.put(lock, "1", { expirationTtl: 300 });
  try {
    await createAndPublish(await loadAuth(env), { media_type: "TEXT", text, reply_to_id: c.commentId });
  } catch (e) {
    await env.KV.delete(lock);
    return notify(env, `❌ 回覆 @${c.username} 失敗：${e.message}`);
  }
  c.replied = true;
  await saveComment(env, msg.messageId, c);
  await setKeyboard(env, msg, { inline_keyboard: [[{ text: "✅ 已回覆", url: c.permalink }]] });
}

async function draftReply(env, c) {
  if (!env.AI) return null;
  const system = [
    "你經營一個 Threads 帳號，每天分享 GitHub 上值得一試的開源專案。現在要回覆你貼文底下的一則留言。",
    env.VOICE_PROMPT ? `以下是你寫貼文時的口吻說明，回覆時沿用同樣的語氣和用語就好，結構和字數規則不用管：\n${env.VOICE_PROMPT}` : "",
    "回覆規則：",
    "- 用留言的語言回；中文一律用台灣繁體中文和台灣用語",
    "- 1～3 句，像朋友聊天，直接回應對方說的內容；可以補一個具體的資訊，或反問一句讓對話接下去",
    "- 不要用「感謝留言」「謝謝分享」這類客套開頭",
    "- 不確定的事不要編，不知道就老實說",
    "- 不放網址（連結已經在第一則留言），不加主題標籤",
    c.forceReply ? "" : "- 留言是廣告、詐騙、沒有內容或惡意攻擊時，只輸出 SKIP",
    "- 只輸出回覆本身，不要加引號或說明",
  ].filter(Boolean).join("\n");
  const user = [
    `你的貼文：\n${c.postText}`,
    c.parent ? `對方是在回 @${c.parent.username} 的這則留言：\n${c.parent.text}` : "",
    `@${c.username} 的留言：\n${c.text}`,
    c.avoid?.length ? `換個說法，不要跟這些太像：\n${c.avoid.join("\n")}` : "",
  ].filter(Boolean).join("\n\n");
  try {
    const result = await env.AI.run(env.AI_MODEL, {
      messages: [{ role: "system", content: system }, { role: "user", content: user }],
      max_tokens: 300,
      temperature: 0.8,
      // 關閉思考模式，免得思考吃掉 max_tokens
      chat_template_kwargs: { enable_thinking: false },
    });
    const raw = typeof result?.response === "string" ? result.response : result?.choices?.[0]?.message?.content || "";
    const text = raw.replace(/<think>[\s\S]*?<\/think>/g, "").trim().replace(/^["「『]|["」』]$/g, "").trim();
    if (!text) return null;
    if (/^SKIP\b/i.test(text)) return "SKIP";
    // 模型偶爾會混進簡體字，統一轉成繁體與台灣用語
    return toTraditional(text).slice(0, 500);
  } catch (e) {
    console.log(`draft failed: ${e.message}`);
    return null;
  }
}

// ---------- 成效 ----------

async function fetchMetrics(auth, id) {
  const { data } = await call("GET", `/v1.0/${id}/insights`, {
    metric: METRICS.join(","),
    access_token: auth.token,
  });
  const metrics = Object.fromEntries(METRICS.map((m) => [m, 0]));
  for (const item of data || []) metrics[item.name] = item.values?.[0]?.value ?? item.total_value?.value ?? 0;
  return metrics;
}

// 每小時跑一次：每 6 小時同步一次帳號的貼文清單（手動發的也算），再分批更新各篇成效，每天記一次追蹤者數
async function updateInsights(env, now) {
  const auth = await getJSON(env, "auth", null);
  if (!auth) return;
  const history = await getJSON(env, "history", { posts: [] });
  const byId = new Map(history.posts.map((p) => [p.id, p]));

  if (!history.syncedAt || now - history.syncedAt > 6 * HOUR) {
    const { data = [] } = await call("GET", "/v1.0/me/threads", {
      fields: "id,timestamp,permalink,text,media_type",
      limit: "50",
      access_token: auth.token,
    });
    const listed = data.filter((t) => t.media_type !== "REPOST_FACADE");
    for (const t of listed) {
      if (!byId.has(t.id)) byId.set(t.id, { id: t.id, at: Date.parse(t.timestamp), permalink: t.permalink, hook: firstLine(t.text || "") });
    }
    // 清單涵蓋的時間範圍內卻不在清單上，就是被刪掉了
    const oldest = Math.min(...listed.map((t) => Date.parse(t.timestamp)));
    const ids = new Set(listed.map((t) => t.id));
    for (const [id, p] of byId) if (listed.length && p.at >= oldest && !ids.has(id)) byId.delete(id);
    history.syncedAt = now;
  }

  const stale = (p) => {
    if (!p.checkedAt) return true;
    return now - p.at < 7 * DAY ? now - p.checkedAt > 6 * HOUR : now - p.checkedAt > 7 * DAY;
  };
  const queue = [...byId.values()].filter(stale).sort((a, b) => (a.checkedAt || 0) - (b.checkedAt || 0));
  for (const p of queue.slice(0, INSIGHTS_PER_RUN)) {
    try {
      p.metrics = await fetchMetrics(auth, p.id);
      p.checkedAt = now;
    } catch (e) {
      if (/permission/i.test(e.message)) break; // 還沒開 threads_manage_insights，等重新授權
      if (/not exist|does not exist|Unsupported get/i.test(e.message)) byId.delete(p.id);
    }
  }

  const today = taipei(now).date;
  history.followers ||= [];
  if (history.followers.at(-1)?.date !== today) {
    const count = await fetchFollowers(auth).catch(() => null);
    if (count !== null) history.followers = [...history.followers, { date: today, count }].slice(-90);
  }

  history.posts = [...byId.values()].sort((a, b) => a.at - b.at).slice(-HISTORY_LIMIT);
  await env.KV.put("history", JSON.stringify(history));
}

async function fetchFollowers(auth) {
  const { data } = await call("GET", "/v1.0/me/threads_insights", {
    metric: "followers_count",
    access_token: auth.token,
  });
  const item = (data || []).find((d) => d.name === "followers_count");
  return item?.total_value?.value ?? item?.values?.at(-1)?.value ?? null;
}

async function weeklyReport(env, now) {
  const history = await getJSON(env, "history", { posts: [] });
  const withMetrics = history.posts.filter((p) => p.metrics);
  const origin = await env.KV.get("origin");
  if (!withMetrics.length) {
    return notify(env, `📊 Threads 週報：還沒有成效資料。\n要先在 Meta app 的權限加上 threads_manage_insights，再重新授權：${origin ? `${origin}/auth` : "Worker 的 /auth"}`);
  }
  const week = withMetrics.filter((p) => p.at >= now - 7 * DAY);
  const sum = (list, key) => list.reduce((n, p) => n + (p.metrics[key] || 0), 0);
  const lines = [`📊 <b>Threads 週報</b>（${shortDate(now - 7 * DAY)}～${shortDate(now - DAY)}）`];

  const followers = history.followers || [];
  if (followers.length) {
    const latest = followers.at(-1).count;
    const weekAgo = followers.find((f) => f.date >= taipei(now - 7 * DAY).date)?.count;
    lines.push(`👥 追蹤者 ${latest}${weekAgo !== undefined ? `（這週 ${signed(latest - weekAgo)}）` : ""}`);
  }
  if (week.length) {
    lines.push(`📝 這週 ${week.length} 篇・👀 ${sum(week, "views")} 觀看・💬 ${sum(week, "replies")} 留言・❤️ ${sum(week, "likes")} 讚`);
    const top = [...week].sort((a, b) => b.metrics.views - a.metrics.views)[0];
    lines.push("", `🏆 這週最好：<a href="${escape(top.permalink)}">${escape(top.hook || "（沒有文字）")}</a>`);
    lines.push(`　👀 ${top.metrics.views}・💬 ${top.metrics.replies}・❤️ ${top.metrics.likes}`);
  } else {
    lines.push("📝 這週沒有發文");
  }

  // 各時段、各頻道表現（最近 30 天），用來決定下週怎麼發
  const month = withMetrics.filter((p) => p.at >= now - 30 * DAY);
  const hours = hourStats(month).sort((a, b) => a.hour - b.hour);
  if (hours.length) {
    lines.push("", "⏰ 最近 30 天各時段（台北）的觀看中位數：");
    for (const h of hours) {
      const local = ownerTime(env, Date.parse(`${taipei(now).date}T${pad(h.hour)}:00:00+08:00`)).hour;
      lines.push(`　${pad(h.hour)} 點（${escape(ownerLabel(env))} ${pad(local)} 點）：${h.median}（${h.count} 篇）`);
    }
  }
  const topics = {};
  for (const p of month) if (p.topic !== undefined) (topics[p.topic || "不加頻道"] ||= []).push(p.metrics.views);
  if (Object.keys(topics).length > 1) {
    lines.push("", "🏷 各頻道的觀看中位數：");
    for (const [t, v] of Object.entries(topics)) lines.push(`　${escape(t)}：${median(v)}（${v.length} 篇）`);
  }
  const { at, basis } = await nextSlot(env, now);
  lines.push("", `👉 現在按「⏰ 排到最佳時段」會排在 ${escape(slotLabel(env, at, now))}：${escape(basis)}`);
  await telegram(env, "sendMessage", {
    chat_id: env.TELEGRAM_CHAT_ID,
    text: lines.join("\n"),
    parse_mode: "HTML",
    disable_web_page_preview: true,
  });
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

function answer(env, query, text = "") {
  return telegram(env, "answerCallbackQuery", { callback_query_id: query.id, text: text.slice(0, 200) });
}

function notify(env, text) {
  return telegram(env, "sendMessage", { chat_id: env.TELEGRAM_CHAT_ID, text, disable_web_page_preview: true });
}

async function getJSON(env, key, fallback) {
  const value = await env.KV.get(key);
  return value ? JSON.parse(value) : fallback;
}

function taipei(ms) {
  const d = new Date(Number(ms) + TAIPEI_OFFSET);
  return { date: d.toISOString().slice(0, 10), hour: d.getUTCHours(), minute: d.getUTCMinutes(), weekday: d.getUTCDay() };
}

// 「今天 19:00（雪梨 22:00）」：日期用台北時間算，括號裡是你那邊的時間
function slotLabel(env, at, now = Date.now()) {
  const a = taipei(at);
  const time = `${pad(a.hour)}:${pad(a.minute)}`;
  const day = a.date === taipei(now).date ? "今天" : a.date === taipei(now + DAY).date ? "明天" : shortDate(at);
  const local = ownerTime(env, at);
  const localTime = `${pad(local.hour)}:${pad(local.minute)}`;
  return localTime === time ? `${day} ${time}` : `${day} ${time}（${ownerLabel(env)} ${localTime}）`;
}

function ownerLabel(env) {
  return env.OWNER_LABEL || env.OWNER_TZ || "當地";
}

function shortDate(ms) {
  const [, m, d] = taipei(ms).date.split("-");
  return `${Number(m)}/${Number(d)}`;
}

function pad(n) {
  return String(n).padStart(2, "0");
}

function signed(n) {
  return n > 0 ? `+${n}` : String(n);
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : Math.round((sorted[mid - 1] + sorted[mid]) / 2);
}

function firstLine(text) {
  return (text.split("\n").find((line) => line.trim()) || "").trim().slice(0, 60);
}

function escape(text) {
  return String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}

function page(message, status = 200) {
  return new Response(`<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<body style="font:18px/1.6 system-ui;padding:24px">${escape(message)}</body>`, {
    status,
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}
