from flask import Flask, render_template_string, jsonify, request
import subprocess
import threading
import json
import os
from datetime import datetime

app = Flask(__name__)

bot_running = False
logs = []

def ajouter_log(message):
    timestamp = datetime.now().strftime('%H:%M:%S')
    logs.append(f"[{timestamp}] {message}")
    if len(logs) > 100:
        logs.pop(0)

def charger_stats():
    if not os.path.exists("stats.json"):
        return {"envoyes": 0, "vus": 0, "reponses": 0}
    with open("stats.json", "r") as f:
        return json.load(f)

def charger_contacts():
    if not os.path.exists("contacts.txt"):
        return []
    with open("contacts.txt", "r") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def charger_invites():
    if not os.path.exists("deja_invites.json"):
        return []
    with open("deja_invites.json", "r") as f:
        return json.load(f)

HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Bot Dashboard</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --bg: #0a0a0f; --surface: #111118; --surface2: #1a1a24;
            --border: #2a2a3a; --accent: #7c6af7; --accent2: #5b52c4;
            --green: #22c55e; --red: #ef4444; --yellow: #f59e0b;
            --text: #e2e8f0; --text2: #94a3b8; --text3: #64748b;
        }
        body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; min-height: 100vh; padding: 24px; }
        .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 32px; padding-bottom: 24px; border-bottom: 1px solid var(--border); }
        .header-left { display: flex; align-items: center; gap: 12px; }
        .logo { width: 40px; height: 40px; background: linear-gradient(135deg, var(--accent), var(--accent2)); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; }
        .title { font-size: 20px; font-weight: 600; }
        .subtitle { font-size: 13px; color: var(--text3); margin-top: 2px; }
        .status-badge { display: flex; align-items: center; gap: 8px; padding: 8px 16px; border-radius: 100px; font-size: 13px; font-weight: 500; border: 1px solid var(--border); background: var(--surface); }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--text3); }
        .status-dot.active { background: var(--green); box-shadow: 0 0 8px var(--green); animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
        .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
        .card-label { font-size: 12px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; }
        .card-value { font-size: 32px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
        .card-value.green { color: var(--green); }
        .card-value.accent { color: var(--accent); }
        .card-value.yellow { color: var(--yellow); }
        .card-sub { font-size: 12px; color: var(--text3); margin-top: 4px; }
        .progress-bar { width: 100%; height: 4px; background: var(--border); border-radius: 2px; margin-top: 12px; overflow: hidden; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, var(--accent), var(--green)); border-radius: 2px; transition: width 0.5s ease; }
        .bottom-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }
        .log-container { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
        .log-header { padding: 16px 20px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
        .log-header-title { font-size: 14px; font-weight: 500; }
        .log-body { padding: 16px; height: 280px; overflow-y: auto; font-family: 'JetBrains Mono', monospace; font-size: 12px; line-height: 1.8; }
        .log-body::-webkit-scrollbar { width: 4px; }
        .log-body::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
        .log-line { color: var(--text2); }
        .log-line.success { color: var(--green); }
        .log-line.error { color: var(--red); }
        .log-line.warning { color: var(--yellow); }
        .log-line.info { color: var(--accent); }
        .invites-body { padding: 12px; height: 280px; overflow-y: auto; }
        .invite-item { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 8px; margin-bottom: 4px; font-size: 13px; }
        .invite-item:hover { background: var(--surface2); }
        .invite-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green); flex-shrink: 0; }
        .controls { display: flex; gap: 12px; }
        .btn { padding: 12px 28px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; border: none; transition: all 0.2s; font-family: 'Inter', sans-serif; }
        .btn-start { background: linear-gradient(135deg, var(--accent), var(--accent2)); color: white; }
        .btn-start:hover { opacity: 0.85; transform: translateY(-1px); }
        .btn-stop { background: var(--surface2); color: var(--red); border: 1px solid var(--red); }
        .btn-stop:hover { background: var(--red); color: white; }
        .btn-refresh { background: var(--surface2); color: var(--text2); border: 1px solid var(--border); }
        .btn-refresh:hover { border-color: var(--accent); color: var(--accent); }
        .empty { color: var(--text3); font-size: 13px; text-align: center; padding: 40px; }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-left">
            <div class="logo">🤖</div>
            <div>
                <div class="title">Telegram Bot</div>
                <div class="subtitle">Dashboard de contrôle</div>
            </div>
        </div>
        <div class="status-badge">
            <div class="status-dot" id="statusDot"></div>
            <span id="statusText">Arrêté</span>
        </div>
    </div>
    <div class="grid">
        <div class="card">
            <div class="card-label">Messages envoyés</div>
            <div class="card-value green" id="envoyes">0</div>
            <div class="card-sub">aujourd'hui</div>
        </div>
        <div class="card">
            <div class="card-label">Messages vus</div>
            <div class="card-value accent" id="vus">0</div>
            <div class="card-sub">au total</div>
        </div>
        <div class="card">
            <div class="card-label">Réponses reçues</div>
            <div class="card-value yellow" id="reponses">0</div>
            <div class="card-sub">au total</div>
        </div>
    </div>
    <div class="grid">
        <div class="card">
            <div class="card-label">Progression</div>
            <div class="card-value accent" id="progression">0%</div>
            <div class="card-sub" id="progressionSub">0 / 0 contacts invités</div>
            <div class="progress-bar">
                <div class="progress-fill" id="progressBar" style="width: 0%"></div>
            </div>
        </div>
        <div class="card">
            <div class="card-label">Contacts restants</div>
            <div class="card-value" id="restants">0</div>
            <div class="card-sub">à inviter</div>
        </div>
        <div class="card">
            <div class="card-label">Total contacts</div>
            <div class="card-value" id="total">0</div>
            <div class="card-sub">dans la base</div>
        </div>
    </div>
    <div class="bottom-grid">
        <div class="log-container">
            <div class="log-header">
                <div class="log-header-title">📋 Logs en direct</div>
            </div>
            <div class="log-body" id="logBody">
                <div class="empty">Aucun log pour l'instant</div>
            </div>
        </div>
        <div class="log-container">
            <div class="log-header">
                <div class="log-header-title">✅ Derniers invités</div>
            </div>
            <div class="invites-body" id="invitesBody">
                <div class="empty">Aucun invité pour l'instant</div>
            </div>
        </div>
    </div>
    <div class="controls">
        <button class="btn btn-start" onclick="startBot()">▶ Démarrer</button>
        <button class="btn btn-stop" onclick="stopBot()">■ Arrêter</button>
        <button class="btn btn-refresh" onclick="refresh()">↻ Actualiser</button>
    </div>
    <script>
        function refresh() {
            fetch('/api/stats').then(r => r.json()).then(data => {
                document.getElementById('envoyes').textContent = data.stats.envoyes || 0;
                document.getElementById('vus').textContent = data.stats.vus || 0;
                document.getElementById('reponses').textContent = data.stats.reponses || 0;
                const total = data.total;
                const invites = data.invites;
                const restants = total - invites;
                const pct = total > 0 ? Math.round((invites / total) * 100) : 0;
                document.getElementById('total').textContent = total;
                document.getElementById('restants').textContent = restants;
                document.getElementById('progression').textContent = pct + '%';
                document.getElementById('progressionSub').textContent = invites + ' / ' + total + ' contacts invités';
                document.getElementById('progressBar').style.width = pct + '%';
                const dot = document.getElementById('statusDot');
                const statusText = document.getElementById('statusText');
                if (data.running) { dot.classList.add('active'); statusText.textContent = 'En cours'; }
                else { dot.classList.remove('active'); statusText.textContent = 'Arrêté'; }
                const logBody = document.getElementById('logBody');
                if (data.logs.length > 0) {
                    logBody.innerHTML = data.logs.map(l => {
                        let cls = 'log-line';
                        if (l.includes('✅')) cls += ' success';
                        else if (l.includes('❌') || l.includes('🚨')) cls += ' error';
                        else if (l.includes('⚠️')) cls += ' warning';
                        else if (l.includes('🔍') || l.includes('📨')) cls += ' info';
                        return '<div class="' + cls + '">' + l + '</div>';
                    }).join('');
                    logBody.scrollTop = logBody.scrollHeight;
                }
                const invitesBody = document.getElementById('invitesBody');
                if (data.derniers_invites.length > 0) {
                    invitesBody.innerHTML = data.derniers_invites.slice(-20).reverse().map(u =>
                        '<div class="invite-item"><div class="invite-dot"></div>' + u + '</div>'
                    ).join('');
                }
            });
        }
        function startBot() {
            fetch('/api/start', {method: 'POST'}).then(r => r.json()).then(d => { refresh(); });
        }
        function stopBot() {
            fetch('/api/stop', {method: 'POST'}).then(r => r.json()).then(d => { refresh(); });
        }
        setInterval(refresh, 5000);
        refresh();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/stats')
def stats():
    contacts = charger_contacts()
    invites = charger_invites()
    stats_data = charger_stats()
    return jsonify({
        "stats": stats_data,
        "total": len(contacts),
        "invites": len(invites),
        "running": bot_running,
        "logs": logs[-50:],
        "derniers_invites": invites[-20:]
    })

@app.route('/api/start', methods=['POST'])
def start_bot():
    global bot_running
    if bot_running:
        return jsonify({"message": "Bot déjà en cours"})
    bot_running = True
    ajouter_log("🚀 Bot démarré")
    def run():
        global bot_running
        process = subprocess.Popen(["python", "telegram_inviter.py"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            ajouter_log(line.strip())
        bot_running = False
        ajouter_log("✅ Bot terminé")
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"message": "Bot démarré !"})

@app.route('/api/stop', methods=['POST'])
def stop_bot():
    global bot_running
    bot_running = False
    ajouter_log("⛔ Bot arrêté manuellement")
    return jsonify({"message": "Bot arrêté"})

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
