require("dotenv").config();
const { App } = require("@slack/bolt");
const blocks = require("./blocks");
const { mockAnswer, mockHomeData } = require("./mock");

const ANSWER_ENDPOINT = process.env.ANSWER_ENDPOINT || null;

const app = new App({
  token: process.env.SLACK_BOT_TOKEN,
  appToken: process.env.SLACK_APP_TOKEN,
  socketMode: true,
});

async function getAnswer(question) {
  if (!ANSWER_ENDPOINT) return mockAnswer(question);
  try {
    const res = await fetch(ANSWER_ENDPOINT, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!res.ok) throw new Error("backend");
    const data = await res.json();
    if (!data.sources) data.sources = [];
    return data;
  } catch {
    return mockAnswer(question);
  }
}

async function answerInto(client, channel, thread_ts, question) {
  const placeholder = await client.chat.postMessage({ channel, thread_ts, text: "Synapse is thinking…" });
  const answer = await getAnswer(question);
  await client.chat.update({ channel, ts: placeholder.ts, text: answer.answer_markdown, blocks: blocks.buildCitedAnswer(answer) });
}

app.event("app_mention", async ({ event, client }) => {
  const question = event.text.replace(/<@[^>]+>/g, "").trim();
  await answerInto(client, event.channel, event.thread_ts || event.ts, question);
});

app.event("message", async ({ event, client }) => {
  if (event.channel_type !== "im" || event.bot_id || event.subtype) return;
  await answerInto(client, event.channel, undefined, event.text.trim());
});

app.command("/ask", async ({ ack, body, client }) => {
  await ack();
  await client.views.open({ trigger_id: body.trigger_id, view: blocks.buildAskModal() });
});

app.action("open_ask_modal", async ({ ack, body, client }) => {
  await ack();
  await client.views.open({ trigger_id: body.trigger_id, view: blocks.buildAskModal() });
});

app.view("ask_modal_submit", async ({ ack, view, body, client }) => {
  await ack();
  const question = view.state.values.question_block.question_input.value;
  const dm = await client.conversations.open({ users: body.user.id });
  await answerInto(client, dm.channel.id, undefined, question);
});

app.action("view_source", async ({ ack }) => { await ack(); });
app.action("view_thread", async ({ ack }) => { await ack(); });

async function resolveDecision({ ack, body, client }, label) {
  await ack();
  const kept = body.message.blocks.filter((b) => b.type !== "actions");
  await client.chat.update({ channel: body.channel.id, ts: body.message.ts, text: label,
    blocks: [...kept, { type: "context", elements: [{ type: "mrkdwn", text: `${label} by <@${body.user.id}>` }] }] });
}
app.action("confirm_decision", (args) => resolveDecision(args, ":white_check_mark: Confirmed"));
app.action("dispute_decision", (args) => resolveDecision(args, ":no_entry: Disputed"));

app.event("app_home_opened", async ({ event, client }) => {
  await client.views.publish({ user_id: event.user, view: { type: "home", blocks: blocks.buildAppHome(mockHomeData()) } });
});

(async () => {
  await app.start();
  console.log("Synapse is running");
})();