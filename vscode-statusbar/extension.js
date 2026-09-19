// Extensão local: consumo de cota na barra de status + seletor de modelo.
//
// Barra:   ⚡ groq 1% · 21:00
//          (provedor ativo, % da cota diária, hora em que ela reseta)
//
// Clique:  menu para trocar de perfil ou fixar um modelo verificado pelo
//          catálogo automático — como o seletor de modelo do Claude Code.

const vscode = require("vscode");

let item, timer;

function cfg() {
  const c = vscode.workspace.getConfiguration("saci");
  return {
    url: (c.get("serverUrl") || "http://127.0.0.1:8000").replace(/\/+$/, ""),
    refresh: Math.max(5, c.get("refreshSeconds") || 15),
  };
}

async function api(path, options) {
  const res = await fetch(`${cfg().url}${path}`, { signal: AbortSignal.timeout(5000), ...options });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

const postJson = (path, body) => api(path, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

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
    const live = u.providers.filter(x => x.active && !x.exhausted);
    const active = live[0] || u.providers.find(x => x.active);
    if (!active) throw new Error("sem provedor");

    const pct = active.rpd_limit ? 100 * active.calls_today / active.rpd_limit : 0;
    const when = active.daily_reset_at || human(active.daily_reset_in);
    const pinned = p.pin ? "$(pin) " : "";

    item.text = `${pinned}$(zap) ${active.provider} ${pct.toFixed(0)}%` + (when ? ` · ${when}` : "");
    item.backgroundColor =
      pct >= 90 ? new vscode.ThemeColor("statusBarItem.errorBackground")
      : pct >= 70 ? new vscode.ThemeColor("statusBarItem.warningBackground")
      : undefined;

    const calls = u.providers.reduce((a, x) => a + x.calls_today, 0);
    const toks = u.providers.reduce((a, x) => a + x.tokens_today, 0);
    const lines = u.providers.filter(x => x.active).map(x => {
      const q = x.rpd_limit ? `${x.calls_today}/${x.rpd_limit}` : `${x.calls_today} chamadas`;
      const r = x.daily_reset_at ? ` · reseta às ${x.daily_reset_at}` : "";
      const flag = (x.exhausted ? " ⛔" : "") + (x.cost === "credits" ? " 💳" : "");
      return `- \`${x.provider}\` ${q}${r}${flag}`;
    });

    const md = new vscode.MarkdownString(
      `**Saci** — perfil \`${p.profile || "auto"}\`\n\n` +
      (p.pin ? `📌 fixado: \`${p.pin.provider}/${p.pin.model}\`\n\n` : "") +
      lines.join("\n") +
      `\n\nHoje: ${calls} chamadas · ${toks.toLocaleString("pt-BR")} tokens` +
      `\n\n_Clique para trocar de perfil ou modelo._`
    );
    md.isTrusted = true;
    item.tooltip = md;
  } catch {
    item.text = "$(zap) Saci: offline";
    item.tooltip = `Servidor nao responde em ${cfg().url}.\nRode: saci-on`;
    item.backgroundColor = undefined;
  }
}

// O seletor — perfis primeiro, depois todo modelo que o catálogo julgou OK.
async function pickMenu() {
  let p;
  try {
    p = await api("/prefs");
  } catch {
    const go = await vscode.window.showErrorMessage("Saci nao responde.", "Abrir painel");
    if (go) openDashboard();
    return;
  }

  const items = [];
  items.push({ label: "Perfis", kind: vscode.QuickPickItemKind.Separator });
  items.push({
    label: `${!p.profile ? "$(check) " : ""}auto`,
    description: "usa o perfil que a requisicao pedir",
    action: () => postJson("/prefs", { profile: "" }),
  });
  for (const prof of p.profiles) {
    const first = prof.steps[0];
    items.push({
      label: `${p.profile === prof.profile ? "$(check) " : ""}${prof.profile}`,
      description: first ? `${first.label} · ${first.model || "melhor verificado"}` : "",
      action: () => postJson("/prefs", { profile: prof.profile }),
    });
  }

  items.push({ label: "Fixar um modelo verificado", kind: vscode.QuickPickItemKind.Separator });
  if (p.pin) {
    items.push({
      label: "$(close) soltar modelo fixado",
      description: `${p.pin.provider}/${p.pin.model}`,
      action: () => postJson("/prefs", { clear_pin: true }),
    });
  }
  for (const [prov, models] of Object.entries(p.verified || {})) {
    const credit = (p.cost || {})[prov] === "credits" ? " 💳 gasta crédito" : "";
    for (const m of models) {
      const isPin = p.pin && p.pin.provider === prov && p.pin.model === m.model;
      const bits = [];
      if (m.latency_ms) bits.push(`${(m.latency_ms / 1000).toFixed(1)}s`);
      if (m.context) bits.push(`${Math.round(m.context / 1000)}k ctx`);
      items.push({
        label: `${isPin ? "$(pin) " : ""}${prov} · ${m.model}`,
        description: bits.join(" · ") + credit,
        action: () => postJson("/prefs", { pin_provider: prov, pin_model: m.model }),
      });
    }
  }

  items.push({ label: "", kind: vscode.QuickPickItemKind.Separator });
  items.push({ label: "$(sync) verificar catálogo agora", action: () => postJson("/catalog/refresh", {}) });
  items.push({ label: "$(graph) abrir painel completo", action: openDashboard });

  const choice = await vscode.window.showQuickPick(items, {
    title: "Saci",
    placeHolder: "Escolha o perfil ou fixe um modelo",
    matchOnDescription: true,
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
  item.command = "saci.pick";
  item.text = "$(zap) Saci: …";
  item.show();

  context.subscriptions.push(
    item,
    vscode.commands.registerCommand("saci.pick", pickMenu),
    vscode.commands.registerCommand("saci.openDashboard", openDashboard),
    vscode.workspace.onDidChangeConfiguration(e => { if (e.affectsConfiguration("saci")) start(); })
  );
  start();
}

function start() {
  if (timer) clearInterval(timer);
  refresh();
  timer = setInterval(refresh, cfg().refresh * 1000);
}

function deactivate() { if (timer) clearInterval(timer); }

module.exports = { activate, deactivate };
