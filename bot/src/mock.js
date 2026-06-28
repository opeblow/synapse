function mockAnswer() {
  return {
    answer_markdown: "The events table moved to **ClickHouse in April** for write throughput. Postgres was choking on ingestion spikes at peak traffic, and the migration was signed off in the Apr 2 eng sync.",
    confidence: "high",
    sources: [
      { type: "slack_thread", title: "Eng sync · Apr 2", snippet: "decided to migrate to ClickHouse for write throughput", url: "https://app.slack.com/archives/C0123/p169", date: "Apr 2, 2026" },
      { type: "google_drive", title: "Events pipeline RFC", snippet: "proposed ClickHouse for append-heavy ingestion", url: "https://docs.google.com/document/d/abc", date: "Mar 28, 2026" },
    ],
  };
}
function mockHomeData() {
  return {
    decisions: [
      { summary: "Migrate events table to ClickHouse", decidedBy: "@dayo", channel: "#engineering", date: "Apr 2, 2026" },
      { summary: "Ship pricing redesign behind a flag", decidedBy: "@lara", channel: "#product", date: "Mar 30, 2026" },
    ],
    channels: [
      { name: "#engineering", lastIndexed: "4 minutes ago" },
      { name: "#product", lastIndexed: "12 minutes ago" },
    ],
  };
}
module.exports = { mockAnswer, mockHomeData };