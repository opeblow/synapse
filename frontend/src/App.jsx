import { useState, useEffect, useRef } from "react";


const ANSWER_ENDPOINT = "/api/answer";

const STARTERS = [
  "Why did we move off Postgres for the events table?",
  "What did we decide about the pricing page redesign?",
  "Who owns the on-call rotation now?",
];

const SOURCE_META = {
  slack_thread: { label: "Slack thread", glyph: "#" },
  google_drive: { label: "Google Doc", glyph: "Doc" },
  notion: { label: "Notion", glyph: "N" },
  github: { label: "GitHub", glyph: "GH" },
};

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function renderMrkdwn(s) {
  return escapeHtml(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}


function mockAnswer(q) {
  return {
    answer_markdown:
      "From the workspace, **the team settled this in an earlier thread** and the reasoning lives in a linked doc. Here is the short version, with the sources it came from below.",
    confidence: "medium",
    sources: [
      { type: "slack_thread", title: "Eng sync — Apr 2", snippet: "decided to migrate for write throughput", date: "Apr 2, 2026" },
      { type: "google_drive", title: "Events pipeline RFC", snippet: "proposed for append-heavy ingestion", date: "Mar 28, 2026" },
    ],
  };
}

export default function App() {
  const [question, setQuestion] = useState("");
  const [status, setStatus] = useState("idle"); // idle | loading | done | error
  const [result, setResult] = useState(null);
  const heroRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const l = document.createElement("link");
    l.rel = "stylesheet";
    l.href =
      "https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap";
    document.head.appendChild(l);
    return () => l.remove();
  }, []);

  function focusAsk() {
    heroRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    setTimeout(() => inputRef.current?.focus(), 400);
  }

  async function askSynapse(q) {
    const query = (q ?? question).trim();
    if (!query) return;
    setQuestion(query);
    setStatus("loading");
    setResult(null);

    const prompt = `You are Synapse, an institutional-memory agent inside a mid-size software company's Slack workspace (product + engineering). A teammate asks the question below. Answer as if you retrieved it from Slack history and connected tools (Google Docs, GitHub, Notion). Invent specific, plausible sources.

Respond with ONLY a JSON object, no fences, with keys:
- "answer_markdown": 2-4 plain sentences, **bold** the key fact.
- "confidence": "high" | "medium" | "low".
- "sources": 1-3 objects with "type" ("slack_thread"|"google_drive"|"github"|"notion"), "title", "snippet" (<14 words), "date".

Question: ${query}`;

    try {
      let parsed;
      if (ANSWER_ENDPOINT) {
        const res = await fetch(ANSWER_ENDPOINT, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: query }),
        });
        if (!res.ok) throw new Error("backend");
        parsed = await res.json();
      } else {
        const res = await fetch("https://api.anthropic.com/v1/messages", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model: "claude-sonnet-4-6",
            max_tokens: 1000,
            messages: [{ role: "user", content: prompt }],
          }),
        });
        if (!res.ok) throw new Error("api");
        const data = await res.json();
        const text = (data.content || []).filter((b) => b.type === "text").map((b) => b.text).join("").trim();
        const clean = text.replace(/```json/gi, "").replace(/```/g, "").trim();
        try {
          parsed = JSON.parse(clean);
        } catch {
          parsed = JSON.parse(clean.slice(clean.indexOf("{"), clean.lastIndexOf("}") + 1));
        }
      }
      if (!parsed.sources) parsed.sources = [];
      setResult(parsed);
      setStatus("done");
    } catch {
      setResult(mockAnswer(query));
      setStatus("done");
    }
  }

  const Mark = () => (
    <svg className="mark" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="6" cy="6" r="2.4" stroke="var(--cite)" strokeWidth="1.6" />
      <circle cx="18" cy="7" r="2.4" stroke="var(--violet)" strokeWidth="1.6" />
      <circle cx="12" cy="18" r="2.4" stroke="var(--cite)" strokeWidth="1.6" />
      <path d="M7.6 7.4 10.6 16M16.4 8.6 13 16M8 6.6h8" stroke="var(--line-2)" strokeWidth="1.4" />
    </svg>
  );

  const Answer = ({ data }) => (
    <div className="answer-card">
      <div className="ac-head">
        <Mark /> Synapse
        <span className="mono ac-conf">confidence: {data.confidence || "medium"}</span>
      </div>
      <p className="a-body" dangerouslySetInnerHTML={{ __html: renderMrkdwn(data.answer_markdown || "") }} />
      {data.sources?.length > 0 && (
        <>
          <div className="src-label">Sources · {data.sources.length}</div>
          {data.sources.map((s, i) => {
            const m = SOURCE_META[s.type] || { glyph: "•" };
            return (
              <div className="src" key={i}>
                <span className="src-glyph">{m.glyph}</span>
                <span>
                  <div className="src-title">{s.title}</div>
                  {s.snippet && <div className="src-snip">“{s.snippet}”</div>}
                  <div className="src-meta">{s.type}{s.date ? " · " + s.date : ""}</div>
                </span>
              </div>
            );
          })}
        </>
      )}
    </div>
  );

  return (
    <div className="syn">
      <style>{CSS}</style>

      {/* breathing ambient aura */}
      <div className="aura" aria-hidden="true">
        <span className="a1" /><span className="a2" /><span className="a3" />
      </div>

      <nav className="nav">
        <div className="brand"><Mark />Synapse</div>
        <div className="nav-links">
          <a href="#index">Capabilities</a>
          <a href="#how">How it works</a>
          <a href="#hero" onClick={(e) => { e.preventDefault(); focusAsk(); }}>Try it</a>
        </div>
        <button className="btn btn-primary" onClick={focusAsk}>
          Add to Slack <span className="arr">→</span>
        </button>
      </nav>

      {/* HERO = live ask, promoted to the centerpiece */}
      <header className="hero" id="hero" ref={heroRef}>
        <div className="wrap">
          <div className="eyebrow mono">Institutional memory · for Slack</div>
          <h1>
            Ask your workspace<br />
            what it <span className="hl"><span>already knows.</span></span>
          </h1>
          <p className="sub">
            Synapse reads your Slack history, decisions, and connected docs, then answers with a
            link straight to the source. Type a question and watch it cite its receipts.
          </p>

          <div className="askbox">
            <div className="chips">
              {STARTERS.map((s) => (
                <button key={s} className="chip" onClick={() => askSynapse(s)}>{s}</button>
              ))}
            </div>
            <div className="input-row">
              <input
                ref={inputRef}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") askSynapse(); }}
                placeholder="Ask anything your team has discussed…"
                aria-label="Ask Synapse"
              />
              <button className="btn btn-primary ask-btn" onClick={() => askSynapse()} disabled={status === "loading"}>
                {status === "loading" ? "Searching…" : <>Ask <span className="arr">→</span></>}
              </button>
            </div>
            {status === "loading" && (
              <div className="thinking"><span className="dot" /> Searching the workspace and connected docs…</div>
            )}
            {status === "done" && result && <Answer data={result} />}
            <div className="demo-note">Answers are generated live and illustrative. In production, Synapse cites real threads and docs.</div>
          </div>
        </div>
      </header>

      {/* MANIFESTO */}
      <section className="manifesto">
        <div className="wrap">
          <p>
            Slack remembers <em>everything</em><span className="and"> and surfaces </span><em>nothing.</em>{" "}
            The decision made in a thread three months ago is still in there. Synapse is how you get it back.
          </p>
        </div>
      </section>

      {/* CAPABILITIES as an archive index, not a card grid */}
      <section className="index" id="index">
        <div className="wrap">
          <div className="kicker mono">// what it does</div>
          {[
            { n: "MEM.01", t: "Ask anything", d: "Mention Synapse or DM it a question. It searches Slack and connected tools, then answers with a link back to where the answer came from." },
            { n: "MEM.02", t: "Decision capture", d: "When a thread reaches a conclusion, Synapse files a Decision Card to #decisions on its own. Who decided what, why, and the source thread." },
            { n: "MEM.03", t: "Catch me up", d: "Back from leave or new to a channel? Ask for a short, cited briefing of what changed. Onboard in minutes, not a day of scrollback." },
          ].map((e) => (
            <a className="entry" href="#hero" key={e.n} onClick={(ev) => { ev.preventDefault(); focusAsk(); }}>
              <span className="entry-n mono">{e.n}</span>
              <span className="entry-body">
                <span className="entry-t">{e.t}</span>
                <span className="entry-d">{e.d}</span>
              </span>
              <span className="entry-arr">↗</span>
            </a>
          ))}
        </div>
      </section>

      {/* DECISION CARD SHOWCASE */}
      <section className="deck-sec">
        <div className="wrap deck">
          <div>
            <div className="kicker mono">// nobody had to write a recap</div>
            <h2>Decisions, captured the moment they happen.</h2>
            <p className="sub low">
              Synapse watches the channels you add it to. When a thread lands on a conclusion it
              files a structured card, so the decision is findable forever and a human can confirm
              or dispute it with one tap.
            </p>
          </div>
          <div className="slackcard">
            <div className="sc-top">
              <div className="sc-avatar" />
              <div className="sc-name">Synapse <span>APP</span></div>
              <div className="sc-badge">Decision</div>
            </div>
            <h4 className="sc-title">Migrate events table to ClickHouse</h4>
            <p className="sc-body">Approved after the ingestion-spike incident. Postgres stays for transactional data; events move to ClickHouse for write throughput.</p>
            <div className="sc-meta mono"><span>decided by @dayo</span><span>#engineering</span><span>Apr 2, 2026</span></div>
            <div className="sc-actions">
              <button className="sc-btn amber">View thread →</button>
              <button className="sc-btn">Confirm</button>
              <button className="sc-btn">Dispute</button>
            </div>
          </div>
        </div>
      </section>

      {/* HOW (real sequence, numbered) */}
      <section className="how" id="how">
        <div className="wrap">
          <div className="kicker mono">// how it works</div>
          <h2>Connect once. Ask forever.</h2>
          <div className="steps">
            {[
              { n: "01", t: "Connect", d: "Add Synapse to a channel and link Drive, Notion, or GitHub through MCP." },
              { n: "02", t: "Index", d: "It builds a private, searchable memory of your threads, decisions, and docs." },
              { n: "03", t: "Ask", d: "Every answer links to its source. No good match? It says so instead of guessing." },
            ].map((s) => (
              <div className="step" key={s.n}>
                <div className="step-n mono">{s.n}</div>
                <h4>{s.t}</h4>
                <p>{s.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* TECH */}
      <section className="tech">
        <div className="wrap">
          <div className="kicker mono">// built on the slack agent platform</div>
          <p className="tech-line">
            All three of the platform's agent technologies, each where it earns its place:
            {" "}<b>Slack AI</b> for native summaries, <b>MCP servers</b> for Drive and GitHub, and the
            {" "}<b>Real-Time Search API</b> for what happened five minutes ago.
          </p>
          <div className="pills">
            <span className="pill"><b>Slack AI</b> native summaries</span>
            <span className="pill"><b>MCP</b> Drive · GitHub · Notion</span>
            <span className="pill"><b>Real-Time Search</b> live context</span>
          </div>
        </div>
      </section>

      <footer>
        <div className="wrap foot">
          <h2 className="serif">Stop losing what your team already figured out.</h2>
          <button className="btn btn-primary big" onClick={focusAsk}>Add Synapse to Slack <span className="arr">→</span></button>
        </div>
        <div className="wrap legal">
          <div className="brand small"><Mark />Synapse</div>
          <div className="mono">Slack Agent Builder Challenge · Track: New Slack Agent</div>
        </div>
      </footer>
    </div>
  );
}

const CSS = `
.syn{
  --ink:#14101c; --ink-2:#1c1626; --ink-3:#251d33;
  --line:rgba(243,237,225,.09); --line-2:rgba(243,237,225,.16);
  --paper:#f3ede1; --muted:#a99fb8; --muted-2:#7e7590;
  --cite:#f0a73e; --cite-soft:rgba(240,167,62,.16); --cite-line:rgba(240,167,62,.42);
  --violet:#b095e0;
  position:relative; min-height:100vh; background:var(--ink); color:var(--paper);
  font-family:Inter,system-ui,sans-serif; line-height:1.55; -webkit-font-smoothing:antialiased; overflow-x:hidden;
}
.syn *{box-sizing:border-box}
.syn ::selection{background:var(--cite);color:#1a1206}
.syn .wrap{max-width:1040px;margin:0 auto;padding:0 24px;position:relative;z-index:1}
.syn .mono{font-family:"JetBrains Mono",ui-monospace,monospace}
.syn .serif{font-family:Fraunces,Georgia,serif}

/* breathing ambient aura */
.syn .aura{position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden}
.syn .aura span{position:absolute;border-radius:50%;filter:blur(90px);will-change:transform}
.syn .a1{width:48vw;height:48vw;left:-10vw;top:-8vw;background:radial-gradient(circle,rgba(176,149,224,.45),transparent 64%);animation:drift1 24s ease-in-out infinite alternate}
.syn .a2{width:42vw;height:42vw;right:-8vw;top:22vh;background:radial-gradient(circle,rgba(240,167,62,.30),transparent 64%);animation:drift2 29s ease-in-out infinite alternate}
.syn .a3{width:52vw;height:52vw;left:18vw;bottom:-24vh;background:radial-gradient(circle,rgba(120,90,180,.40),transparent 64%);animation:drift3 33s ease-in-out infinite alternate}
@keyframes drift1{to{transform:translate(6vw,5vh) scale(1.16)}}
@keyframes drift2{to{transform:translate(-5vw,-4vh) scale(1.12)}}
@keyframes drift3{to{transform:translate(4vw,-6vh) scale(1.18)}}

/* nav */
.syn .nav{position:sticky;top:16px;z-index:50;max-width:1040px;margin:16px auto 0;display:flex;align-items:center;justify-content:space-between;gap:16px;padding:11px 12px 11px 18px;border:1px solid var(--line);border-radius:999px;background:rgba(28,22,38,.6);backdrop-filter:blur(14px)}
.syn .brand{display:flex;align-items:center;gap:9px;font-family:Fraunces,serif;font-weight:600;font-size:20px}
.syn .brand.small{font-size:16px}
.syn .mark{width:25px;height:25px;flex:0 0 auto}
.syn .nav-links{display:flex;gap:24px;font-size:14px;color:var(--muted)}
.syn .nav-links a{color:inherit;text-decoration:none;position:relative;transition:color .2s}
.syn .nav-links a:hover{color:var(--paper)}
.syn .nav-links a::after{content:"";position:absolute;left:0;bottom:-5px;height:1.5px;width:100%;background:var(--cite);transform:scaleX(0);transform-origin:left;transition:transform .26s cubic-bezier(.2,.7,.2,1)}
.syn .nav-links a:hover::after{transform:scaleX(1)}
@media(max-width:720px){.syn .nav-links{display:none}}

/* buttons */
.syn .btn{font-family:Inter,sans-serif;font-size:14px;font-weight:600;display:inline-flex;align-items:center;gap:7px;cursor:pointer;border-radius:999px;padding:10px 18px;border:1px solid transparent;text-decoration:none;transition:transform .18s cubic-bezier(.2,.7,.2,1),box-shadow .18s,background .18s,border-color .18s}
.syn .btn .arr{transition:transform .18s cubic-bezier(.2,.7,.2,1)}
.syn .btn:hover .arr{transform:translateX(4px)}
.syn .btn:active{transform:scale(.96)}
.syn .btn-primary{background:var(--cite);color:#1a1206}
.syn .btn-primary:hover{transform:translateY(-2px);box-shadow:0 12px 30px -10px rgba(240,167,62,.55)}
.syn .btn-primary:active{transform:translateY(0) scale(.96)}
.syn .btn.big{padding:14px 26px;font-size:15px}
.syn :focus-visible{outline:2px solid var(--cite);outline-offset:3px;border-radius:8px}

/* hero */
.syn .hero{padding:78px 0 40px}
.syn .eyebrow{font-size:12px;letter-spacing:.18em;color:var(--cite);text-transform:uppercase;margin-bottom:22px}
.syn h1{font-family:Fraunces,serif;font-weight:500;letter-spacing:-.02em;font-size:clamp(40px,7.4vw,78px);line-height:1.03;margin:0 0 22px}
.syn .hl{position:relative;white-space:nowrap}
.syn .hl>span{position:relative;z-index:1}
.syn .hl::after{content:"";position:absolute;left:-.05em;right:-.05em;bottom:.08em;height:.4em;z-index:0;background:var(--cite);border-radius:3px;transform:scaleX(0);transform-origin:left;animation:swipe .7s cubic-bezier(.2,.7,.2,1) .5s forwards}
@keyframes swipe{to{transform:scaleX(1)}}
.syn .sub{font-size:clamp(16px,1.9vw,19px);color:var(--muted);max-width:54ch;margin:0 0 30px}
.syn .sub.low{margin-top:18px}

/* ask box */
.syn .askbox{border:1px solid var(--line-2);background:rgba(28,22,38,.72);backdrop-filter:blur(8px);border-radius:18px;padding:18px;max-width:620px;box-shadow:0 40px 80px -40px rgba(0,0,0,.8)}
.syn .chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.syn .chip{font-size:12.5px;color:var(--muted);border:1px solid var(--line);background:var(--ink-3);border-radius:999px;padding:7px 13px;cursor:pointer;transition:transform .16s,color .16s,border-color .16s,background .16s}
.syn .chip:hover{color:var(--paper);border-color:var(--cite-line);transform:translateY(-1px)}
.syn .chip:active{transform:scale(.97)}
.syn .input-row{display:flex;gap:10px}
.syn .input-row input{flex:1;background:var(--ink);border:1px solid var(--line-2);border-radius:12px;color:var(--paper);font-family:Inter,sans-serif;font-size:15px;padding:13px 15px;outline:none;transition:border-color .18s,box-shadow .18s}
.syn .input-row input::placeholder{color:var(--muted-2)}
.syn .input-row input:focus{border-color:var(--cite-line);box-shadow:0 0 0 3px var(--cite-soft)}
.syn .ask-btn{white-space:nowrap}
.syn .thinking{display:flex;align-items:center;gap:10px;color:var(--muted);font-size:14px;padding:14px 2px}
.syn .dot{width:7px;height:7px;border-radius:50%;background:var(--cite);animation:pulse 1s infinite ease-in-out}
@keyframes pulse{0%,100%{opacity:.3;transform:scale(.8)}50%{opacity:1;transform:scale(1)}}
.syn .demo-note{font-size:11.5px;color:var(--muted-2);font-family:"JetBrains Mono",monospace;margin-top:11px}

/* answer card */
.syn .answer-card{border:1px solid var(--line);background:linear-gradient(180deg,var(--ink-2),var(--ink));border-radius:16px;padding:18px;margin-top:16px;animation:rise .5s cubic-bezier(.2,.7,.2,1)}
@keyframes rise{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
.syn .ac-head{display:flex;align-items:center;gap:9px;font-size:13px;color:var(--muted);margin-bottom:12px}
.syn .ac-conf{margin-left:auto;font-size:11px;color:var(--muted-2)}
.syn .a-body{font-size:15px;color:#ded5e6;margin:0 0 16px}
.syn .a-body strong{color:var(--paper)}
.syn .src-label{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted-2);margin-bottom:8px}
.syn .src{display:flex;gap:11px;align-items:flex-start;padding:11px 12px;border:1px solid var(--cite-line);border-radius:12px;background:var(--cite-soft);margin-bottom:8px;transition:background .18s,transform .18s,box-shadow .18s}
.syn .src:hover{background:rgba(240,167,62,.24);transform:translateX(3px);box-shadow:-4px 0 0 var(--cite)}
.syn .src-glyph{flex:0 0 auto;width:30px;height:30px;border-radius:8px;display:grid;place-items:center;background:rgba(240,167,62,.22);color:var(--cite);font-family:"JetBrains Mono",monospace;font-size:11px}
.syn .src-title{font-size:13.5px;font-weight:600;color:var(--paper)}
.syn .src-snip{font-size:12.5px;color:var(--muted)}
.syn .src-meta{font-size:11px;color:var(--muted-2);font-family:"JetBrains Mono",monospace;margin-top:2px}

/* manifesto */
.syn .manifesto{padding:90px 0}
.syn .manifesto p{font-family:Fraunces,serif;font-weight:400;font-size:clamp(26px,4vw,42px);line-height:1.3;letter-spacing:-.01em;max-width:24ch;color:var(--muted)}
.syn .manifesto em{font-style:italic;color:var(--paper)}
.syn .manifesto .and{color:var(--muted-2)}

/* section labels */
.syn .kicker{font-size:12px;letter-spacing:.06em;color:var(--cite);margin-bottom:14px}
.syn h2{font-family:Fraunces,serif;font-weight:500;letter-spacing:-.015em;font-size:clamp(28px,4.4vw,44px);margin:0}

/* capabilities as archive index */
.syn .index{padding:40px 0 90px}
.syn .entry{display:flex;align-items:flex-start;gap:22px;padding:26px 8px;border-top:1px solid var(--line-2);text-decoration:none;color:inherit;transition:padding .25s cubic-bezier(.2,.7,.2,1),background .25s;border-radius:8px}
.syn .entry:last-child{border-bottom:1px solid var(--line-2)}
.syn .entry:hover{padding-left:20px;background:linear-gradient(90deg,var(--cite-soft),transparent 60%)}
.syn .entry-n{flex:0 0 auto;font-size:13px;color:var(--cite);padding-top:6px;width:64px}
.syn .entry-body{display:flex;flex-direction:column;gap:6px}
.syn .entry-t{font-family:Fraunces,serif;font-size:clamp(22px,3vw,30px);font-weight:500;transition:transform .25s cubic-bezier(.2,.7,.2,1)}
.syn .entry:hover .entry-t{transform:translateX(4px)}
.syn .entry-d{color:var(--muted);font-size:14.5px;max-width:62ch}
.syn .entry-arr{margin-left:auto;color:var(--muted-2);font-size:20px;transition:transform .25s,color .25s}
.syn .entry:hover .entry-arr{color:var(--cite);transform:translate(4px,-4px)}

/* decision showcase */
.syn .deck-sec{padding:30px 0 90px}
.syn .deck{display:grid;grid-template-columns:1fr 1fr;gap:44px;align-items:center}
@media(max-width:820px){.syn .deck{grid-template-columns:1fr;gap:28px}}
.syn .slackcard{border:1px solid var(--line-2);background:var(--ink-2);border-radius:14px;padding:16px;transition:transform .25s,box-shadow .25s}
.syn .slackcard:hover{transform:translateY(-4px);box-shadow:0 24px 50px -24px rgba(0,0,0,.8)}
.syn .sc-top{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.syn .sc-avatar{width:34px;height:34px;border-radius:8px;background:linear-gradient(135deg,var(--violet),var(--cite))}
.syn .sc-name{font-weight:600;font-size:14px}
.syn .sc-name span{color:var(--muted-2);font-weight:400;font-family:"JetBrains Mono",monospace;font-size:11px;margin-left:6px}
.syn .sc-badge{margin-left:auto;font-family:"JetBrains Mono",monospace;font-size:11px;color:var(--cite);border:1px solid var(--cite-line);border-radius:6px;padding:2px 7px}
.syn .sc-title{font-family:Fraunces,serif;font-weight:500;font-size:19px;margin:0 0 6px}
.syn .sc-body{font-size:14px;color:#ded5e6;margin:0 0 12px}
.syn .sc-meta{display:flex;gap:14px;flex-wrap:wrap;font-size:11.5px;color:var(--muted-2);margin-bottom:14px}
.syn .sc-actions{display:flex;gap:8px}
.syn .sc-btn{font-size:13px;border-radius:8px;padding:7px 12px;border:1px solid var(--line-2);background:var(--ink-3);color:var(--paper);cursor:pointer;transition:transform .16s,background .16s}
.syn .sc-btn:hover{transform:translateY(-1px)}
.syn .sc-btn:active{transform:scale(.96)}
.syn .sc-btn.amber{background:var(--cite);color:#1a1206;border-color:var(--cite)}

/* how */
.syn .how{padding:30px 0 90px}
.syn .how h2{margin-top:0}
.syn .steps{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:34px}
@media(max-width:820px){.syn .steps{grid-template-columns:1fr}}
.syn .step{border-top:1px solid var(--line-2);padding-top:16px;transition:border-color .25s}
.syn .step:hover{border-color:var(--cite)}
.syn .step-n{color:var(--cite);font-size:13px}
.syn .step h4{font-family:Fraunces,serif;font-weight:500;font-size:20px;margin:8px 0 6px}
.syn .step p{color:var(--muted);font-size:14px;margin:0}

/* tech */
.syn .tech{padding:48px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.syn .tech-line{color:var(--muted);max-width:64ch;font-size:15.5px;margin:0}
.syn .tech-line b{color:var(--paper);font-weight:600}
.syn .pills{display:flex;gap:10px;flex-wrap:wrap;margin-top:20px}
.syn .pill{font-family:"JetBrains Mono",monospace;font-size:12.5px;color:var(--paper);border:1px solid var(--line-2);border-radius:999px;padding:8px 14px;transition:border-color .2s,transform .2s}
.syn .pill:hover{border-color:var(--cite-line);transform:translateY(-2px)}
.syn .pill b{color:var(--cite)}

/* footer */
.syn .foot{padding:90px 0 60px;text-align:center}
.syn .foot h2{max-width:18ch;margin:0 auto 26px}
.syn .legal{border-top:1px solid var(--line);padding:22px 0;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;color:var(--muted-2);font-size:12.5px}

@media(prefers-reduced-motion:reduce){
  .syn .aura span,.syn .hl::after,.syn .dot,.syn .answer-card{animation:none!important}
  .syn .hl::after{transform:scaleX(1)}
  .syn *{transition:none!important}
}
`;