const toMrkdwn = (s = "") => s.replace(/\*\*(.+?)\*\*/g, "*$1*");

const SOURCE_GLYPH = {
  slack_thread: ":thread:",
  google_drive: ":page_facing_up:",
  github: ":octocat:",
  notion: ":notebook:",
};

function buildCitedAnswer({ answer_markdown, confidence = "medium", sources = [] }) {
  const out = [{ type: "section", text: { type: "mrkdwn", text: toMrkdwn(answer_markdown) } }];
  if (sources.length === 0) {
    out.push({ type: "context", elements: [{ type: "mrkdwn", text: ":warning:  No confident source found, so I won't guess." }] });
    return out;
  }
  out.push({ type: "divider" });
  out.push({ type: "context", elements: [{ type: "mrkdwn", text: `*Sources · ${sources.length}*    confidence: ${confidence}` }] });
  for (const s of sources) {
    const glyph = SOURCE_GLYPH[s.type] || ":link:";
    const section = { type: "section", text: { type: "mrkdwn", text: `${glyph}  *${s.title}*\n_${s.snippet}_` } };
    if (s.url) section.accessory = { type: "button", text: { type: "plain_text", text: "View" }, url: s.url, action_id: "view_source" };
    out.push(section);
    out.push({ type: "context", elements: [{ type: "mrkdwn", text: `${s.type} · ${s.date || ""}` }] });
  }
  return out;
}

function buildDecisionCard(d) {
  return [
    { type: "header", text: { type: "plain_text", text: "Decision captured", emoji: true } },
    { type: "section", text: { type: "mrkdwn", text: `*${d.summary}*` } },
    ...(d.body ? [{ type: "section", text: { type: "mrkdwn", text: d.body } }] : []),
    { type: "context", elements: [{ type: "mrkdwn", text: `decided by ${d.decidedBy} · ${d.channel} · ${d.date}` }] },
    { type: "actions", block_id: `decision_${d.id}`, elements: [
      { type: "button", text: { type: "plain_text", text: "View thread" }, url: d.threadUrl, action_id: "view_thread" },
      { type: "button", text: { type: "plain_text", text: "Confirm" }, style: "primary", action_id: "confirm_decision", value: d.id },
      { type: "button", text: { type: "plain_text", text: "Dispute" }, style: "danger", action_id: "dispute_decision", value: d.id },
    ]},
  ];
}

function buildAppHome({ decisions = [], channels = [], firstRun = false }) {
  const out = [
    { type: "header", text: { type: "plain_text", text: "Synapse", emoji: true } },
    { type: "section", text: { type: "mrkdwn", text: "Your workspace's memory. Ask a question and get the answer with its sources." },
      accessory: { type: "button", text: { type: "plain_text", text: "Ask Synapse" }, style: "primary", action_id: "open_ask_modal" } },
    { type: "divider" },
  ];
  if (firstRun) {
    out.push(
      { type: "header", text: { type: "plain_text", text: "Get set up", emoji: true } },
      { type: "section", text: { type: "mrkdwn", text: "1.  Add Synapse to a channel\n2.  Connect Drive, Notion, or GitHub\n3.  Ask your first question" } },
    );
    return out;
  }
  out.push({ type: "header", text: { type: "plain_text", text: "Recent decisions", emoji: true } });
  if (decisions.length === 0) {
    out.push({ type: "context", elements: [{ type: "mrkdwn", text: "Nothing captured yet. Decisions show up here on their own." }] });
  } else {
    for (const d of decisions.slice(0, 5)) {
      out.push({ type: "section", text: { type: "mrkdwn", text: `*${d.summary}*` } });
      out.push({ type: "context", elements: [{ type: "mrkdwn", text: `${d.decidedBy} · ${d.channel} · ${d.date}` }] });
    }
  }
  out.push({ type: "divider" }, { type: "header", text: { type: "plain_text", text: "Indexing", emoji: true } });
  for (const c of channels) {
    out.push({ type: "context", elements: [{ type: "mrkdwn", text: `*${c.name}*  last indexed ${c.lastIndexed}` }] });
  }
  return out;
}

function buildAskModal() {
  return {
    type: "modal",
    callback_id: "ask_modal_submit",
    title: { type: "plain_text", text: "Ask Synapse" },
    submit: { type: "plain_text", text: "Ask" },
    close: { type: "plain_text", text: "Cancel" },
    blocks: [
      { type: "input", block_id: "question_block",
        label: { type: "plain_text", text: "What do you want to know?" },
        element: { type: "plain_text_input", action_id: "question_input",
          placeholder: { type: "plain_text", text: "Why did we move off Postgres for the events table?" } } },
    ],
  };
}

module.exports = { buildCitedAnswer, buildDecisionCard, buildAppHome, buildAskModal };