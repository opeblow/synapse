// Server-side proxy. The Anthropic key stays here, never in the browser.
// Returns the same JSON contract the frontend already renders.
exports.handler = async (event) => {
  if (event.httpMethod !== "POST") {
    return json(405, { error: "Method not allowed" });
  }

  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) return json(500, { error: "Server is missing ANTHROPIC_API_KEY" });

  let question = "";
  try {
    question = (JSON.parse(event.body || "{}").question || "").trim();
  } catch {
    return json(400, { error: "Bad request body" });
  }
  if (!question) return json(400, { error: "No question provided" });

  const prompt = `You are Synapse, an institutional-memory agent inside a mid-size software company's Slack workspace (product + engineering). A teammate asks the question below. Answer as if you retrieved it from Slack history and connected tools (Google Docs, GitHub, Notion). Invent specific, plausible sources.

Respond with ONLY a JSON object, no fences, with keys:
- "answer_markdown": 2-4 plain sentences, **bold** the key fact.
- "confidence": "high" | "medium" | "low".
- "sources": 1-3 objects with "type" ("slack_thread"|"google_drive"|"github"|"notion"), "title", "snippet" (<14 words), "date".

Question: ${question}`;

  try {
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: "claude-sonnet-4-6",
        max_tokens: 1000,
        messages: [{ role: "user", content: prompt }],
      }),
    });

    if (!res.ok) {
      const detail = (await res.text()).slice(0, 200);
      return json(502, { error: "Upstream error", detail });
    }

    const data = await res.json();
    const text = (data.content || [])
      .filter((b) => b.type === "text")
      .map((b) => b.text)
      .join("")
      .trim();
    const clean = text.replace(/```json/gi, "").replace(/```/g, "").trim();

    let parsed;
    try {
      parsed = JSON.parse(clean);
    } catch {
      parsed = JSON.parse(clean.slice(clean.indexOf("{"), clean.lastIndexOf("}") + 1));
    }
    if (!parsed.sources) parsed.sources = [];

    return json(200, parsed);
  } catch {
    return json(502, { error: "Request failed" });
  }
};

function json(statusCode, obj) {
  return {
    statusCode,
    headers: { "content-type": "application/json" },
    body: JSON.stringify(obj),
  };
}