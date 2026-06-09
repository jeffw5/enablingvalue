/**
 * Cloudflare Worker — Ask Jeffrey API Proxy
 * With Pinecone RAG retrieval for grounded responses
 *
 * Secrets required (set via wrangler secret put):
 *   ANTHROPIC_API_KEY
 *   PINECONE_API_KEY
 *   PINECONE_HOST  (e.g. https://enabling-value-xxx.svc.aped-4627-b74a.pinecone.io)
 */

const SYSTEM_PROMPT = `You are an AI assistant representing Jeffrey Wallk, Managing Partner of The Value Enablement Group, LLC. You respond on his behalf to visitors of enablingvalue.com.

Jeffrey is an Enterprise Architect and Semantic Governance pioneer based in Deerfield, Illinois with 17+ years of experience across healthcare, pharma, telecom, and aerospace. He built the Knowledge Engineering discipline at Verizon governing 30,000+ data assets using GraphDB, OWL, RDF, SPARQL, SHACL, and SKOS.

CORE FRAMEWORKS:
- AI Circuit Breaker Architecture: Five-layer morphism-grounded AI assurance with MTBH metric, Composition Theorem, GUM uncertainty quantification, and STPA/STAMP integration. Co-authored with Paul Wach (University of Arizona) for INCOSE SE4AI.
- RDSG v2.0: Requirements-Driven Semantic Gateway with full STPA/STAMP integration, UCA coverage, irreversibility enforcement, and temporal SWRL rules.
- Holonic Semantic Architecture: Four-level holarchic structure integrating all frameworks into a unified whole-part architecture.
- Unified Semantic Knowledge Layer: Built from scratch at Verizon governing 30,000+ data assets.
- Morphism-Grounded AI Assurance: DARPA DSO research targeting Thrust 4, category-theoretic foundation.
- S.E.P.A.: Systemic Exploitation Prevention Act grounded in Doughnut Economics and STPA/STAMP.
- Agent-Based Ecosystem Design: Federated knowledge architecture using domain-specific ontologies, SLMs, and microservices for intelligent agent governance.
- Enterprise Architecture as Complex Adaptive Systems: N-dimensional cartography for knowledge engineering and causality discovery.
- Digital Twin Architecture: Control Theory + Theory of Constraints applied to discrete twins for education and enterprise systems.

APPLIED WORK: Baxter FABRIC, Gulfstream Smart Manufacturing, AbbVie ARCH/KEP, Hollister Digital Factory, Yaskawa America, Verizon USKL, Prolong Pharmaceuticals, Mylan N.V.

VALUES: Planet > People > Profit. Every decision serves planetary health first, then human dignity, then economic sustainability.

COMMUNITY: One Good Thing initiative. Vision Awake Africa for Development (VAAFD) — Carolyn A. Miller Schools at Buduburam Refugee Settlement, Ghana.

When relevant knowledge context is provided below, use it to give specific, grounded answers drawn from Jeffrey's actual work and documents. Reference the source material naturally.

Respond in first person as Jeffrey. Be precise, intellectually rigorous, and grounded in real work. Maximum 3-5 paragraphs unless technical depth genuinely requires more.`;

const MODE_ADDENDUMS = {
  explorer: "The visitor is exploring frameworks and work. Be a knowledgeable guide — illuminate the thinking behind the work.",
  challenge: "The visitor has an organizational challenge. Be consultative — diagnose before prescribing.",
  engage: "The visitor wants to work together. Be warm, direct, and professional.",
  recruiter: "The visitor is interested in background and career. Be honest and compelling."
};

// ── CORS ──
function corsHeaders(request) {
  const origin = request.headers.get("Origin") || "*";
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
  };
}

// ── PINECONE QUERY ──
async function queryPinecone(question, env) {
  if (!env.PINECONE_API_KEY || !env.PINECONE_HOST) return [];

  try {
    // Step 1 — Embed the question
    const embedRes = await fetch("https://api.pinecone.io/embed", {
      method: "POST",
      headers: {
        "Api-Key": env.PINECONE_API_KEY,
        "Content-Type": "application/json",
        "X-Pinecone-API-Version": "2024-07"
      },
      body: JSON.stringify({
        inputs: [{ text: question }],
        model: "llama-text-embed-v2",
        parameters: { input_type: "query", truncate: "END" }
      })
    });

    if (!embedRes.ok) return [];

    const embedData = await embedRes.json();
    const vector = embedData?.data?.[0]?.values;
    if (!vector) return [];

    // Step 2 — Query Pinecone for top 5 similar chunks
    const queryRes = await fetch(`${env.PINECONE_HOST}/query`, {
      method: "POST",
      headers: {
        "Api-Key": env.PINECONE_API_KEY,
        "Content-Type": "application/json",
        "X-Pinecone-API-Version": "2024-07"
      },
      body: JSON.stringify({
        vector: vector,
        topK: 5,
        includeMetadata: true
      })
    });

    if (!queryRes.ok) return [];

    const queryData = await queryRes.json();
    return queryData?.matches || [];

  } catch (err) {
    console.log("Pinecone error:", err.message);
    return [];
  }
}

// ── BUILD CONTEXT FROM PINECONE RESULTS ──
function buildContext(matches) {
  if (!matches || matches.length === 0) return "";

  const chunks = matches
    .filter(m => m.score > 0.4)  // only include relevant matches
    .map(m => {
      const filename = m.metadata?.filename || "unknown";
      const domain   = m.metadata?.domain || "";
      const text     = m.metadata?.text || "";
      return `[Source: ${filename} | Domain: ${domain}]\n${text}`;
    });

  if (chunks.length === 0) return "";

  return "\n\n## Relevant Knowledge from Jeffrey's Documents\n\n" + chunks.join("\n\n---\n\n");
}

// ── MAIN HANDLER ──
export default {
  async fetch(request, env) {

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(request) });
    }

    const url = new URL(request.url);
    if (request.method !== "POST" || url.pathname !== "/chat") {
      return new Response(JSON.stringify({ error: "Not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json", ...corsHeaders(request) }
      });
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return new Response(JSON.stringify({ error: "Invalid JSON" }), {
        status: 400,
        headers: { "Content-Type": "application/json", ...corsHeaders(request) }
      });
    }

    const messages = (body.messages || [])
      .filter(m => m.role === "user" || m.role === "assistant")
      .map(m => ({ role: m.role, content: String(m.content).slice(0, 4000) }))
      .slice(-20);

    const mode = body.mode || "explorer";

    // Get the latest user message for RAG query
    const lastUserMsg = messages.filter(m => m.role === "user").pop()?.content || "";

    // Query Pinecone for relevant context
    const matches = await queryPinecone(lastUserMsg, env);
    const context = buildContext(matches);

    // Build enriched system prompt
    const modeAddendum = MODE_ADDENDUMS[mode] || MODE_ADDENDUMS.explorer;
    const system = SYSTEM_PROMPT + context + "\n\nMode: " + modeAddendum;

    // Call Anthropic
    let anthropicRes;
    try {
      anthropicRes = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': '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',
          'anthropic-version': '2023-06-01'
        },
        body: JSON.stringify({
          model: "claude-sonnet-4-6",
          max_tokens: 1024,
          system: system,
          messages: messages
        })
      });
    } catch (err) {
      return new Response(JSON.stringify({ error: "Failed to reach Anthropic" }), {
        status: 502,
        headers: { "Content-Type": "application/json", ...corsHeaders(request) }
      });
    }

    if (!anthropicRes.ok) {
      const errText = await anthropicRes.text();
      console.log("Anthropic error:", anthropicRes.status, errText);
      return new Response(JSON.stringify({ error: "AI service temporarily unavailable. Please try again shortly." }), {
        status: 502,
        headers: { "Content-Type": "application/json", ...corsHeaders(request) }
      });
    }

    const data = await anthropicRes.json();
    const reply = data.content?.[0]?.text || "Something went wrong. Please try again.";

    return new Response(JSON.stringify({
      reply: reply,
      sources: matches.filter(m => m.score > 0.4).map(m => m.metadata?.filename).filter(Boolean)
    }), {
      status: 200,
      headers: { "Content-Type": "application/json", ...corsHeaders(request) }
    });
  }
};