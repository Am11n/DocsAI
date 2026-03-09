import { HealthCard } from "../lib/health-card";

export default function HomePage() {
  return (
    <main style={{ maxWidth: 900, margin: "40px auto", fontFamily: "sans-serif" }}>
      <h1>DocsAI MVP</h1>
      <p>Upload/search/chat UI comes in next phases.</p>
      <HealthCard />
    </main>
  );
}
