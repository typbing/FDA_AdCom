const paths = {
  backtest: "data/runs/mini_backtest_v3.json",
  labels: "data/outcome_labels.csv",
  trades: "data/paper_trades.csv",
};

const $ = (id) => document.getElementById(id);

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (char === '"' && quoted && next === '"') {
      cell += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") {
        index += 1;
      }
      row.push(cell);
      if (row.some((value) => value.length > 0)) {
        rows.push(row);
      }
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }

  if (cell.length || row.length) {
    row.push(cell);
    rows.push(row);
  }

  const headers = rows.shift() || [];
  return rows.map((values) =>
    Object.fromEntries(headers.map((header, index) => [header, values[index] || ""])),
  );
}

function bucketClass(value) {
  const lower = String(value || "").toLowerCase();
  if (lower.includes("positive") || lower.includes("approved") || lower === "true") {
    return "positive";
  }
  if (lower.includes("negative") || lower.includes("crl") || lower === "false") {
    return "negative";
  }
  return "mixed";
}

function text(value, fallback = "--") {
  return value === null || value === undefined || value === "" ? fallback : value;
}

function renderMetrics(backtest, labels) {
  const fullyLabeled = labels.filter((row) =>
    ["drug", "indication", "adcom_vote", "adcom_outcome", "fda_final_decision", "fda_decision_date", "outcome_source"].every(
      (field) => row[field] && !String(row[field]).includes("TODO"),
    ),
  ).length;
  const todo = labels.filter((row) => Object.values(row).join(" ").includes("TODO_SOURCE_NEEDED")).length;

  $("metric-accuracy").textContent =
    typeof backtest.accuracy === "number" ? `${Math.round(backtest.accuracy * 1000) / 10}%` : "--";
  $("metric-actionable").textContent = text(backtest.actionable_count);
  $("metric-correct").textContent = text(backtest.correct_count);
  $("metric-labeled").textContent = fullyLabeled;
  $("metric-todo").textContent = todo;
}

function renderCases(rows) {
  $("case-count").textContent = `${rows.length} cases`;
  $("case-table").innerHTML = rows
    .map(
      (row) => `<tr>
        <td class="doc-title">${text(row.title)}</td>
        <td>${text(row.ticker)}</td>
        <td><span class="pill ${bucketClass(row.signal)}">${text(row.signal)}</span></td>
        <td>${text(row.probability)}</td>
        <td>${text(row.confidence)}</td>
        <td><span class="pill ${bucketClass(row.target_outcome)}">${text(row.target_outcome)}</span></td>
        <td><span class="pill ${bucketClass(row.correct)}">${row.correct === null ? "review" : text(row.correct)}</span></td>
      </tr>`,
    )
    .join("");

  const misses = rows.filter((row) => row.correct === false);
  $("miss-count").textContent = `${misses.length} misses`;
  $("miss-list").innerHTML =
    misses
      .map(
        (row) => `<div class="item">
          <strong>${text(row.ticker, "No ticker")} · ${text(row.signal)} vs ${text(row.target_outcome)}</strong>
          <span>${text(row.title)}</span>
        </div>`,
      )
      .join("") || `<div class="item"><strong>No misses</strong><span>Current sample has no false calls.</span></div>`;
}

function renderGaps(labels) {
  const gaps = labels
    .filter((row) => Object.values(row).join(" ").includes("TODO_SOURCE_NEEDED"))
    .slice(0, 10);
  $("gap-count").textContent = `${gaps.length} shown`;
  $("gap-list").innerHTML =
    gaps
      .map(
        (row) => `<div class="item">
          <strong>${text(row.document_id)} · ${text(row.ticker, "No ticker")}</strong>
          <span>${text(row.drug, "Drug pending")} · ${text(row.indication, "Indication pending")}</span>
        </div>`,
      )
      .join("") || `<div class="item"><strong>No TODO labels</strong><span>All labels are currently populated.</span></div>`;
}

function renderTrades(trades) {
  $("trade-count").textContent = `${trades.length} rows`;
  $("trade-table").innerHTML =
    trades
      .map(
        (row) => `<tr>
          <td class="doc-title">${text(row.trade_id)}</td>
          <td>${text(row.ticker)}</td>
          <td><span class="pill ${bucketClass(row.signal)}">${text(row.signal)}</span></td>
          <td>${text(row.probability)}</td>
          <td>${text(row.confidence)}</td>
          <td>${text(row.actual_outcome)}</td>
          <td>${text(row.notes)}</td>
        </tr>`,
      )
      .join("") || `<tr><td colspan="7">No paper trade rows yet.</td></tr>`;
}

async function loadDashboard() {
  try {
    const [backtestResponse, labelsResponse, tradesResponse] = await Promise.all([
      fetch(paths.backtest),
      fetch(paths.labels),
      fetch(paths.trades),
    ]);

    if (!backtestResponse.ok || !labelsResponse.ok || !tradesResponse.ok) {
      throw new Error("One or more data files could not be loaded.");
    }

    const backtest = await backtestResponse.json();
    const labels = parseCsv(await labelsResponse.text());
    const trades = parseCsv(await tradesResponse.text());

    renderMetrics(backtest, labels);
    renderCases(backtest.rows || []);
    renderGaps(labels);
    renderTrades(trades);
    $("data-status").textContent = "Data loaded";
  } catch (error) {
    $("data-status").textContent = "Data unavailable";
    console.error(error);
  }
}

loadDashboard();
