// Extensão local: mostra o consumo de cota na barra de status do VSCode.
//
// Consulta GET /status do servidor do LLM Router e exibe algo como:
//     $(zap) groq 12% · 1m26s
//
// Clicar abre o painel completo numa aba lateral.

const vscode = require("vscode");

let item;
let timer;

function cfg() {
  const c = vscode.workspace.getConfiguration("llmRouter");
  return {
    url: (c.get("serverUrl") || "http://127.0.0.1:8000").replace(/\/+$/, ""),
    refresh: Math.max(5, c.get("refreshSeconds") || 15),
  };
}

function humanize(secs) {
  if (secs == null) return null;
  if (secs <= 0.5) return "pronto";
  if (secs < 60) return `${Math.round(secs)}s`;
  const m = Math.floor(secs / 60);
  const s = Math.round(secs % 60);
  if (m < 60) return `${m}m${String(s).padStart(2, "0")}s`;
  return `${Math.floor(m / 60)}h${String(m % 60).padStart(2, "0")}m`;
}

async function refresh() {
  const { url } = cfg();
  try {
    // AbortSignal evita a barra travar se o servidor não responder.
    const res = await fetch(`${url}/status`, { signal: AbortSignal.timeout(4000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const d = await res.json();

    if (!d.active) {
      item.text = "$(zap) LLM: sem cota";
      item.tooltip = "Todos os provedores estao sem cota no momento.";
      item.backgroundColor = new vscode.ThemeColor("statusBarItem.errorBackground");
      return;
    }

    const pct = d.used_pct ?? 0;
    const reset = humanize(d.reset_in);
    item.text = `$(zap) ${d.active} ${pct.toFixed(0)}%` + (reset ? ` · ${reset}` : "");

    // Amarelo acima de 70%, vermelho acima de 90%.
    item.backgroundColor =
      pct >= 90 ? new vscode.ThemeColor("statusBarItem.errorBackground")
      : pct >= 70 ? new vscode.ThemeColor("statusBarItem.warningBackground")
      : undefined;

    const out = d.exhausted?.length ? `\nSem cota: ${d.exhausted.join(", ")}` : "";
    item.tooltip = new vscode.MarkdownString(
      `**LLM Router**\n\n` +
      `Provedor ativo: \`${d.active}\` (${pct.toFixed(1)}% da cota usada)\n\n` +
      `Hoje: ${d.calls_today} chamadas · ${d.tokens_today.toLocaleString("pt-BR")} tokens` +
      out +
      `\n\n_Clique para abrir o painel._`
    );
  } catch (e) {
    item.text = "$(zap) LLM: offline";
    item.tooltip = `Servidor nao responde em ${url}.\nRode: llm-on`;
    item.backgroundColor = undefined;
  }
}

function activate(context) {
  item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  item.command = "llmRouter.openDashboard";
  item.text = "$(zap) LLM: …";
  item.show();

  context.subscriptions.push(
    item,
    vscode.commands.registerCommand("llmRouter.openDashboard", async () => {
      const { url } = cfg();
      await vscode.commands.executeCommand(
        "simpleBrowser.show",
        `${url}/dashboard`
      );
    }),
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
