import { getLiveHealth, getReadyHealth } from "./api";

export async function HealthCard() {
  try {
    const [live, ready] = await Promise.all([getLiveHealth(), getReadyHealth()]);

    return (
      <section style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
        <h2 style={{ marginTop: 0 }}>API Health</h2>
        <p>Live: {live.status}</p>
        <p>Ready: {ready.status}</p>
      </section>
    );
  } catch {
    return (
      <section style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
        <h2 style={{ marginTop: 0 }}>API Health</h2>
        <p>API is unavailable right now. UI is still usable.</p>
      </section>
    );
  }
}
