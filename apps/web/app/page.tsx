"use client";

import { FormEvent, useMemo, useState } from "react";

import { HealthCard } from "../lib/health-card";
import {
  getMetadata,
  listDocuments,
  patchMetadata,
  ragChat,
  semanticSearch,
  uploadConfirm,
  uploadInit,
  uploadToSignedUrl,
} from "../lib/api";

export default function HomePage() {
  const [token, setToken] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string>("");
  const [loading, setLoading] = useState(false);

  const [documents, setDocuments] = useState<
    Array<{ id: string; file_name: string; status: string; last_error: string | null }>
  >([]);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Array<{ chunk_id: string; score: number; snippet: string }>>([]);
  const [chatQuestion, setChatQuestion] = useState("");
  const [chatAnswer, setChatAnswer] = useState("");
  const [chatSources, setChatSources] = useState<Array<{ chunk_id: string; score: number }>>([]);

  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [metadataRaw, setMetadataRaw] = useState("");

  const hasToken = useMemo(() => token.trim().length > 10, [token]);

  async function onUpload(e: FormEvent) {
    e.preventDefault();
    if (!file || !hasToken) return;
    setLoading(true);
    setMessage("");
    try {
      const init = await uploadInit(token, {
        file_name: file.name,
        mime_type: file.type || "application/pdf",
        file_size: file.size,
      });
      await uploadToSignedUrl(init.upload_url, file);
      const confirm = await uploadConfirm(token, init.document_id);
      setMessage(`Upload queued. Document: ${confirm.document_id}, status: ${confirm.status}`);
      setSelectedDocumentId(confirm.document_id);
      setFile(null);
    } catch (err) {
      setMessage(String(err));
    } finally {
      setLoading(false);
    }
  }

  async function refreshDocuments() {
    if (!hasToken) return;
    setLoading(true);
    try {
      const response = await listDocuments(token);
      setDocuments(response.documents);
      setMessage(`Loaded ${response.documents.length} documents`);
    } catch (err) {
      setMessage(String(err));
    } finally {
      setLoading(false);
    }
  }

  async function runSearch() {
    if (!hasToken || !query.trim()) return;
    setLoading(true);
    try {
      const response = await semanticSearch(token, query, 5);
      setSearchResults(response.results.map((r) => ({ chunk_id: r.chunk_id, score: r.score, snippet: r.snippet })));
      setMessage(`Found ${response.results.length} search results`);
    } catch (err) {
      setMessage(String(err));
    } finally {
      setLoading(false);
    }
  }

  async function runChat() {
    if (!hasToken || !chatQuestion.trim()) return;
    setLoading(true);
    try {
      const response = await ragChat(
        token,
        chatQuestion,
        5,
        selectedDocumentId ? [selectedDocumentId] : undefined,
      );
      setChatAnswer(response.answer);
      setChatSources(response.sources.map((s) => ({ chunk_id: s.chunk_id, score: s.score })));
      setMessage(`Chat completed with ${response.sources.length} sources`);
    } catch (err) {
      setMessage(String(err));
    } finally {
      setLoading(false);
    }
  }

  async function loadMetadata() {
    if (!hasToken || !selectedDocumentId) return;
    setLoading(true);
    try {
      const metadata = await getMetadata(token, selectedDocumentId);
      setMetadataRaw(JSON.stringify(metadata, null, 2));
      setMessage("Metadata loaded");
    } catch (err) {
      setMessage(String(err));
    } finally {
      setLoading(false);
    }
  }

  async function saveMetadata() {
    if (!hasToken || !selectedDocumentId || !metadataRaw.trim()) return;
    setLoading(true);
    try {
      const parsed = JSON.parse(metadataRaw) as {
        dato?: string | null;
        parter?: string[] | null;
        belop?: number | null;
        valuta?: string | null;
        nokkelvilkar?: string[] | null;
        review_status?: string;
      };
      const updated = await patchMetadata(token, selectedDocumentId, parsed);
      setMetadataRaw(JSON.stringify(updated, null, 2));
      setMessage("Metadata updated");
    } catch (err) {
      setMessage(String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 980, margin: "40px auto", fontFamily: "sans-serif", display: "grid", gap: 18 }}>
      <h1>DocsAI MVP</h1>
      <HealthCard />

      <section style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
        <h2>Auth token</h2>
        <input
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="Paste Supabase JWT token"
          style={{ width: "100%", padding: 8 }}
        />
      </section>

      <section style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
        <h2>Upload</h2>
        <form onSubmit={onUpload}>
          <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <button style={{ marginLeft: 12 }} disabled={loading || !hasToken || !file} type="submit">
            Upload and queue
          </button>
        </form>
      </section>

      <section style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
        <h2>Document status</h2>
        <button onClick={refreshDocuments} disabled={loading || !hasToken}>
          Refresh
        </button>
        <ul>
          {documents.map((doc) => (
            <li key={doc.id}>
              <button onClick={() => setSelectedDocumentId(doc.id)}>{doc.file_name}</button> - {doc.status}{" "}
              {doc.last_error ? `(error: ${doc.last_error})` : ""}
            </li>
          ))}
        </ul>
      </section>

      <section style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
        <h2>Semantic search</h2>
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ask a search query" />
        <button style={{ marginLeft: 8 }} onClick={runSearch} disabled={loading || !hasToken || !query.trim()}>
          Search
        </button>
        <ul>
          {searchResults.map((result) => (
            <li key={result.chunk_id}>
              <code>{result.chunk_id}</code> ({result.score.toFixed(3)}) - {result.snippet}
            </li>
          ))}
        </ul>
      </section>

      <section style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
        <h2>RAG chat</h2>
        <input
          value={chatQuestion}
          onChange={(e) => setChatQuestion(e.target.value)}
          placeholder="Ask a grounded question"
          style={{ width: "70%" }}
        />
        <button style={{ marginLeft: 8 }} onClick={runChat} disabled={loading || !hasToken || !chatQuestion.trim()}>
          Chat
        </button>
        <p>{chatAnswer}</p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {chatSources.map((source) => (
            <span
              key={source.chunk_id}
              style={{ border: "1px solid #ccc", borderRadius: 12, padding: "4px 8px", fontSize: 12 }}
            >
              {source.chunk_id.slice(0, 8)} ({source.score.toFixed(3)})
            </span>
          ))}
        </div>
      </section>

      <section style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
        <h2>Metadata editor</h2>
        <p>Selected document: {selectedDocumentId || "none"}</p>
        <button onClick={loadMetadata} disabled={loading || !hasToken || !selectedDocumentId}>
          Load metadata
        </button>
        <button onClick={saveMetadata} disabled={loading || !hasToken || !selectedDocumentId || !metadataRaw.trim()}>
          Save metadata
        </button>
        <textarea
          value={metadataRaw}
          onChange={(e) => setMetadataRaw(e.target.value)}
          rows={12}
          style={{ width: "100%", marginTop: 8, fontFamily: "monospace" }}
        />
      </section>

      <p>{loading ? "Working..." : message}</p>
    </main>
  );
}
