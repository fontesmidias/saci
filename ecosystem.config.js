// Configuração do PM2 para o servidor do Saci.
//
//   pm2 start ecosystem.config.js   (ou: saci-on)
//   pm2 stop saci             (ou: saci-off)
//   pm2 logs saci             (ou: saci-logs)
//
// O PM2 mantém o processo vivo em segundo plano: você fecha o terminal
// e o servidor continua rodando. Ele também reinicia sozinho se cair.

const path = require("path");

module.exports = {
  apps: [
    {
      name: "saci",
      script: path.join(__dirname, "server.py"),
      interpreter: path.join(__dirname, ".venv", "Scripts", "python.exe"),
      cwd: __dirname,

      // Sem cluster: é um processo Python, não Node.
      instances: 1,
      exec_mode: "fork",

      // Reinicia se o processo morrer, com limite para não entrar em loop
      // infinito caso haja erro de configuração.
      autorestart: true,
      max_restarts: 10,
      min_uptime: "10s",
      restart_delay: 2000,

      // Reinicia se passar de 300MB (proteção contra vazamento).
      max_memory_restart: "300M",

      env: {
        // Garante acentuação correta nos logs em Windows.
        PYTHONIOENCODING: "utf-8",
        PYTHONUNBUFFERED: "1",
      },

      // Logs em ./logs (ignorado pelo git).
      out_file: path.join(__dirname, "logs", "saci-out.log"),
      error_file: path.join(__dirname, "logs", "saci-err.log"),
      merge_logs: true,
      time: true,
    },
  ],
};
