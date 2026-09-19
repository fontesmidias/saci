// Extensão local: consumo de cota na barra de status + seletor de perfil.
//
// Barra:   ⚡ groq 1% · 4h39m
//          (provedor ativo, % da cota diária, quando reseta)
//
// Clique:  menu para trocar de perfil ou fixar um modelo — como o
//          seletor de modelo do Claude Code.

const vscode = require("vscode");

let item, timer;

function cfg() {
  const c = vscode.workspace.getConfiguration("llmRouter");
  return {
    url: (c.get("serverUrl") || "http://127.0.0.1:8000").replace(/\/+$/, ""),
    refresh: Math.max(5, c.get("refreshSeconds") || 15),
  };
}

async function api(path, options) {
  const res = await fetch(`${cfg().url}${path}`, {
    signal: AbortSignal.timeout(5000),
    ...options,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function human(secs) {
  if (secs == null) return null;
  if (secs <= 1) return "agora";
  const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60);
  if (h >= 24) return `${Math.floor(h / 24)}d${h % 24}h`;
  if (h) return `${h}h${String(m).padStart(2, "0")}m`;
  if (m) return `${m}m`;
  return `${Math.round(secs)}s`;
}

async function refresh() {
  try {
    const [u, p] = await Promise.all([api("/usage"), api("/prefs")]);

    // O provedor "ativo" é o primeiro da cascata com cota sobrando.
    const live = u.providers.filter(x => !x.exhausted);
    const active = live[0] || u.providers[0];
    if (!active) throw new Error("sem dados");

    const pct = active.rpd_limit
      ? 100 * active.calls_today / active.rpd_limit
      : 0;
    const reset = human(active.daily_reset_in);
    const pinned = p.pin ? "$(pin) " : "";

    item.text = `${pinned}$(zap) ${active.provider} ${pct.toFixed(0)}%` +
                (reset ? ` · ${reset}` : "");

    item.backgroundColor =
      pct >= 90 ? new vscode.ThemeColor("statusBarItem.errorBackground")
      : pct >= 70 ? new vscode.ThemeColor("statusBarItem.warningBackground")
      : undefined;

    const calls = u.providers.reduce((a, x) => a + x.calls_today, 0);
    const toks = u.providers.reduce((a, x) => a + x.tokens_today, 0);
    const lines = u.providers
      .filter(x => x.rpd_limit)
      .map(x => {
        const q = `${x.calls_today}/${x.rpd_limit}`;
        const r = human(x.daily_reset_in);
        const flag = x.exhausted ? " ⛔" : "";
        return `- \`${x.provider}\` ${q} · reseta em ${r}${flag}`;
      });

    const md = new vscode.MarkdownString(
      `**LLM Router** — perfil \`${p.profile || "auto"}\`\n\n` +
      (p.pin ? `📌 fixado: \`${p.pin.provider}/${p.pin.model}\`\n\n` : "") +
      lines.join("\n") +
      `\n\nHoje: ${calls} chamadas · ${toks.toLocaleString("pt-BR")} tokens` +
      `\n\n_Clique para trocar de perfil ou modelo._`
    );
    md.isTrusted = true;
    item.tooltip = md;
  } catch {
    item.text = "$(zap) LLM: offline";
    item.tooltip = `Servidor nao responde em ${cfg().url}.\nRode: llm-on`;
    item.backgroundColor = undefined;
  }
}

// Menu de troca — o equivalente ao seletor de modelo do Claude Code.
async function pickMenu() {
  let u, p;
  try {
    [u, p] = await Promise.all([api("/usage"), api("/prefs")]);
  } catch {
    const go = await vscode.window.showErrorMessage(
      "Servidor do LLM Router nao responde.", "Abrir painel"
    );
    if (go) openDashboard();
    return;
  }

  const items = [];

  items.push({ label: "Perfis", kind: vscode.QuickPickItemKind.Separator });
  items.push({
    label: `${!p.profile ? "$(check) " : ""}auto`,
    description: "usa o perfil que a requisicao pedir",
    action: () => api("/prefs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "" }),
    }),
  });
  for (const prof of p.profiles) {
    const first = prof.steps[0];
    items.push({
      label: `${p.profile === prof.profile ? "$(check) " : ""}${prof.profile}`,
      description: first ? `${first.label} · ${first.model}` : "",
      action: () => api("/prefs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: prof.profile }),
      }),
    });
  }

  // Fixar um modelo específico, ignorando a ordem da cascata.
  items.push({ label: "Fixar um modelo", kind: vscode.QuickPickItemKind.Separator });
  if (p.pin) {
    items.push({
      label: "$(close) soltar modelo fixado",
      description: `${p.pin.provider}/${p.pin.model}`,
      action: () => api("/prefs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ clear_pin: true }),
      }),
    });
  }
  for (const prov of u.providers) {
    for (const m of prov.models) {
      const isPin = p.pin && p.pin.provider === prov.provider && p.pin.model === m.model;
      const bits = [];
      if (m.exhausted) bits.push("sem cota");
      if (m.avg_latency) bits.push(`${m.avg_latency}s`);
      items.push({
        label: `${isPin ? "$(pin) " : ""}${prov.provider} · ${m.model}`,
        description: bits.join(" · "),
        action: () => api("/prefs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pin_provider: prov.provider, pin_model: m.model }),
        }),
      });
    }
  }

  items.push({ label: "", kind: vscode.QuickPickItemKind.Separator });
  items.push({ label: "$(graph) abrir painel completo", action: openDashboard });

  const choice = await vscode.window.showQuickPick(items, {
    title: "LLM Router",
    placeHolder: "Escolha o perfil ou fixe um modelo",
  });
  if (choice?.action) {
    await choice.action();
    await refresh();
  }
}

async function openDashboard() {
  await vscode.commands.executeCommand("simpleBrowser.show", `${cfg().url}/dashboard`);
}

function activate(context) {
  item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  item.command = "llmRouter.pick";
  item.text = "$(zap) LLM: …";
  item.show();

  context.subscriptions.push(
    item,
    vscode.commands.registerCommand("llmRouter.pick", pickMenu),
    vscode.commands.registerCommand("llmRouter.openDashboard", openDashboard),
    vscode.workspace.onDidChangeConfiguration(e => {
      if (e.affectsConfiguration("llmRouter")) start();
    })
  );

  start();
}

function start() {
  if (timer) clearInterval(timer);
  refresh();
  timer = setInterval(refresh, cfg().refresh * 1000);
}

function deactivate() {
  if (timer) clearInterval(timer);
}

module.exports = { activate, deactivate };
