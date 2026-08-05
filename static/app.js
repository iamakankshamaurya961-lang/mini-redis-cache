document.addEventListener("DOMContentLoaded", () => {
    // Poll stats every 1 second
    fetchStats();
    setInterval(fetchStats, 1000);

    // Event Listeners for Forms & Buttons
    document.getElementById("set-form").addEventListener("submit", handleSet);
    document.getElementById("btn-get").addEventListener("click", handleGet);
    document.getElementById("btn-delete").addEventListener("click", handleDelete);
    document.getElementById("btn-benchmark").addEventListener("click", handleBenchmark);
});

// Fetch telemetry stats and render queue
async function fetchStats() {
    try {
        const response = await fetch("/api/stats");
        if (!response.ok) return;
        const data = await response.json();

        // 1. Update Metrics
        document.getElementById("metric-capacity").innerText = `${data.current_size} / ${data.capacity}`;
        const capPct = (data.current_size / data.capacity) * 100;
        document.getElementById("capacity-progress").style.width = `${capPct}%`;

        document.getElementById("metric-hitrate").innerText = `${data.hit_rate_pct}%`;
        document.getElementById("hit-miss-count").innerText = `Hits: ${data.hits} | Misses: ${data.misses}`;
        document.getElementById("metric-reads").innerText = data.total_reads;
        document.getElementById("metric-writes").innerText = data.total_writes;

        // 2. Render Live LRU Queue Cards
        renderQueue(data.items);
    } catch (err) {
        console.error("Error fetching stats:", err);
    }
}

// Render dynamic item cards (Head/MRU -> Tail/LRU)
function renderQueue(items) {
    const container = document.getElementById("queue-container");
    if (!items || items.length === 0) {
        container.innerHTML = `<div class="empty-state">Cache is currently empty. Use the playground below to set keys!</div>`;
        return;
    }

    container.innerHTML = "";
    items.forEach((item, index) => {
        const card = document.createElement("div");
        card.className = "queue-card";

        let tagHtml = "";
        if (index === 0) {
            card.classList.add("mru");
            tagHtml = `<span class="queue-tag mru-tag">MRU (Head)</span>`;
        } else if (index === items.length - 1 && items.length > 1) {
            card.classList.add("lru");
            tagHtml = `<span class="queue-tag lru-tag">LRU (Tail)</span>`;
        }

        let ttlHtml = "";
        if (item.expires_in_sec !== null) {
            ttlHtml = `<div class="card-ttl">⏱️ Expired in: ${item.expires_in_sec}s</div>`;
        }

        card.innerHTML = `
            ${tagHtml}
            <div class="card-key">${escapeHtml(item.key)}</div>
            <div class="card-val">${escapeHtml(String(item.value))}</div>
            ${ttlHtml}
        `;
        container.appendChild(card);
    });
}

// Handle SET key form
async function handleSet(e) {
    e.preventDefault();
    const key = document.getElementById("set-key").value.trim();
    const value = document.getElementById("set-val").value.trim();
    const ttl = document.getElementById("set-ttl").value.trim();

    if (!key || !value) return;

    const payload = { key, value };
    if (ttl) payload.ttl_seconds = parseFloat(ttl);

    try {
        const res = await fetch("/api/set", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        
        // Clear form
        document.getElementById("set-key").value = "";
        document.getElementById("set-val").value = "";
        document.getElementById("set-ttl").value = "";

        fetchStats();
    } catch (err) {
        console.error("SET failed:", err);
    }
}

// Handle GET key button
async function handleGet() {
    const key = document.getElementById("query-key").value.trim();
    if (!key) return;

    const resultBox = document.getElementById("query-result");
    try {
        const res = await fetch(`/api/get?key=${encodeURIComponent(key)}`);
        const data = await res.json();

        resultBox.classList.remove("hidden", "success", "error");
        if (data.found) {
            resultBox.classList.add("success");
            resultBox.innerHTML = `✅ <strong>HIT!</strong> Key: <code>${escapeHtml(key)}</code> | Value: <code>${escapeHtml(String(data.value))}</code>`;
        } else {
            resultBox.classList.add("error");
            resultBox.innerHTML = `❌ <strong>MISS!</strong> Key: <code>${escapeHtml(key)}</code> not found or expired.`;
        }
        fetchStats();
    } catch (err) {
        console.error("GET failed:", err);
    }
}

// Handle DELETE key button
async function handleDelete() {
    const key = document.getElementById("query-key").value.trim();
    if (!key) return;

    const resultBox = document.getElementById("query-result");
    try {
        const res = await fetch(`/api/delete?key=${encodeURIComponent(key)}`, { method: "DELETE" });
        const data = await res.json();

        resultBox.classList.remove("hidden", "success", "error");
        if (data.success) {
            resultBox.classList.add("success");
            resultBox.innerHTML = `🗑️ Key <code>${escapeHtml(key)}</code> successfully deleted.`;
            document.getElementById("query-key").value = "";
        } else {
            resultBox.classList.add("error");
            resultBox.innerHTML = `❌ Key <code>${escapeHtml(key)}</code> was not in cache.`;
        }
        fetchStats();
    } catch (err) {
        console.error("DELETE failed:", err);
    }
}

// Handle 1,000 Ops Benchmark Button
async function handleBenchmark() {
    const btn = document.getElementById("btn-benchmark");
    const resultsContainer = document.getElementById("benchmark-results");
    
    btn.disabled = true;
    btn.innerText = "⏳ Running 1,000 Operations...";

    try {
        const res = await fetch("/api/benchmark", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ operations: 1000 })
        });
        const data = await res.json();

        resultsContainer.classList.remove("hidden");
        document.getElementById("bench-ops").innerText = data.total_operations.toLocaleString();
        document.getElementById("bench-throughput").innerText = `${data.throughput_ops_per_sec.toLocaleString()} ops/sec`;
        document.getElementById("bench-latency").innerText = `${data.average_latency_ms} ms`;

        fetchStats();
    } catch (err) {
        console.error("Benchmark failed:", err);
    } finally {
        btn.disabled = false;
        btn.innerText = "⚡ Run 1,000 Ops Benchmark";
    }
}

function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
