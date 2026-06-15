from flask import Flask, render_template_string, jsonify, request
import subprocess
import threading
import json
import os
from datetime import datetime

app = Flask(__name__)

bot_running = False
logs = []

FICHIER_CONFIG   = "config.json"
FICHIER_STATUT   = "warmup_statut.json"
FICHIER_STATS    = "stats.json"
FICHIER_CONTACTS = "contacts.txt"
FICHIER_INVITES  = "deja_invites.json"

DEFAULT_CONFIG = {
    "comptes": [
        {"nom": f"Compte {i+1}", "session": f"compte{i+1}", "tel": "", "api_id": "", "api_hash": ""}
        for i in range(20)
    ],
    "compte_maitre": {"api_id": "", "api_hash": "", "tel": "", "session": "compte_maitre"},
    "groupes": [],
    "amis": [],
    "messages_invitation": ["Salut ! 👋\n\nJe voulais t'inviter sur mon canal.\n\nRejoins-nous : {canal}"],
    "messages_amis": ["Ça va ?", "T'es là ?", "Tu fais quoi ce soir ?"],
    "messages_groupes": ["Mets ton message ici"],
    "messages_maitre": ["Ça va ?", "T'es dispo ?", "Quoi de neuf ?", "On se voit quand ?", "Tu fais quoi ce soir ?"],
    "messages_relance_pas_vu": [
        "Hé ! Tu as vu mon message ? 👀",
        "Yo, t'as loupé ça 👉 {canal}",
        "Au cas où t'aurais pas vu → {canal}",
        "Je voulais juste m'assurer que t'avais vu ça → {canal}"
    ],
    "messages_relance_vu": [
        "Tu as eu le temps de regarder ? {canal}",
        "Toujours intéressé ? → {canal}",
        "Hésite pas à rejoindre si t'as pas encore eu le temps ! {canal}",
        "C'est gratuit, ça vaut le coup d'œil → {canal}"
    ],
    "canal_lien": "https://t.me/TON_CANAL",
    "mon_username": "@tonusername",
    "duree_warmup": 21,
    "limite_semaine_1": 3,
    "limite_semaine_2": 10,
    "limite_semaine_3": 20,
}

def charger_config():
    if not os.path.exists(FICHIER_CONFIG):
        sauvegarder_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    with open(FICHIER_CONFIG, "r") as f:
        return json.load(f)

def sauvegarder_config(config):
    with open(FICHIER_CONFIG, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def charger_statut():
    if not os.path.exists(FICHIER_STATUT):
        return {}
    with open(FICHIER_STATUT, "r") as f:
        return json.load(f)

def charger_stats():
    if not os.path.exists(FICHIER_STATS):
        return {"envoyes": 0, "vus": 0, "reponses": 0}
    with open(FICHIER_STATS, "r") as f:
        return json.load(f)

def charger_contacts():
    if not os.path.exists(FICHIER_CONTACTS):
        return []
    with open(FICHIER_CONTACTS, "r") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def charger_invites():
    if not os.path.exists(FICHIER_INVITES):
        return []
    with open(FICHIER_INVITES, "r") as f:
        return json.load(f)

def ajouter_log(message):
    timestamp = datetime.now().strftime('%H:%M:%S')
    logs.append(f"[{timestamp}] {message}")
    if len(logs) > 100:
        logs.pop(0)

def statut_compte(session):
    statut = charger_statut()
    if session in statut:
        return statut[session].get("phase", "warmup")
    return "warmup"

def jours_warmup(session):
    statut = charger_statut()
    if session in statut:
        debut = datetime.fromisoformat(statut[session].get("debut_warmup", datetime.now().isoformat()))
        return (datetime.now() - debut).days
    return 0

def charger_scores():
    if not os.path.exists("scores.json"):
        return {}
    with open("scores.json", "r") as f:
        return json.load(f)

def score_compte(session):
    scores = charger_scores()
    if session in scores:
        return scores[session]
    return {"score": 100, "dernier_statut": "sain", "messages_ok": 0, "flood_wait": 0, "peer_flood": 0}

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
            --bg: #0a0a0f; --surface: #111118; --surface2: #1a1a24; --surface3: #222230;
            --border: #2a2a3a; --accent: #7c6af7; --accent2: #5b52c4;
            --green: #22c55e; --red: #ef4444; --yellow: #f59e0b;
            --text: #e2e8f0; --text2: #94a3b8; --text3: #64748b;
        }
        body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; min-height: 100vh; }
        .sidebar { position: fixed; left: 0; top: 0; bottom: 0; width: 220px; background: var(--surface); border-right: 1px solid var(--border); padding: 24px 16px; display: flex; flex-direction: column; gap: 4px; z-index: 100; }
        .sidebar-logo { display: flex; align-items: center; gap: 10px; padding: 8px; margin-bottom: 24px; }
        .logo-icon { width: 36px; height: 36px; background: linear-gradient(135deg, var(--accent), var(--accent2)); border-radius: 9px; display: flex; align-items: center; justify-content: center; font-size: 18px; }
        .logo-text { font-size: 15px; font-weight: 700; }
        .logo-sub { font-size: 11px; color: var(--text3); }
        .nav-item { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: 8px; cursor: pointer; font-size: 14px; color: var(--text2); transition: all 0.15s; border: none; background: none; width: 100%; text-align: left; }
        .nav-item:hover { background: var(--surface2); color: var(--text); }
        .nav-item.active { background: rgba(124,106,247,0.15); color: var(--accent); font-weight: 600; }
        .nav-icon { font-size: 16px; width: 20px; text-align: center; }
        .sidebar-bottom { margin-top: auto; }
        .status-pill { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-radius: 8px; background: var(--surface2); font-size: 13px; }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--text3); flex-shrink: 0; }
        .status-dot.active { background: var(--green); box-shadow: 0 0 8px var(--green); animation: pulse 2s infinite; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
        .main { margin-left: 220px; padding: 28px; min-height: 100vh; }
        .page { display: none; }
        .page.active { display: block; }
        .page-title { font-size: 22px; font-weight: 700; margin-bottom: 6px; }
        .page-sub { font-size: 14px; color: var(--text3); margin-bottom: 28px; }
        .grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
        .grid2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 24px; }
        .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
        .card-label { font-size: 12px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; }
        .card-value { font-size: 32px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
        .card-value.green { color: var(--green); }
        .card-value.accent { color: var(--accent); }
        .card-value.yellow { color: var(--yellow); }
        .card-sub { font-size: 12px; color: var(--text3); margin-top: 4px; }
        .progress-bar { width: 100%; height: 4px; background: var(--border); border-radius: 2px; margin-top: 12px; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, var(--accent), var(--green)); border-radius: 2px; transition: width 0.5s; }
        .section-title { font-size: 13px; font-weight: 600; color: var(--text3); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 14px; margin-top: 8px; }

        /* COMPTES GRID 20 */
        .comptes-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 28px; }
        .compte-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px; text-align: center; }
        .compte-card.configured { border-color: rgba(124,106,247,0.3); }
        .compte-avatar { width: 38px; height: 38px; border-radius: 50%; background: linear-gradient(135deg, var(--accent), var(--accent2)); display: flex; align-items: center; justify-content: center; font-size: 16px; margin: 0 auto 8px; }
        .compte-avatar.inactive { background: var(--surface2); }
        .compte-nom { font-size: 12px; font-weight: 600; margin-bottom: 4px; }
        .compte-phase { font-size: 10px; padding: 2px 7px; border-radius: 100px; display: inline-block; margin-bottom: 5px; }
        .compte-phase.warmup { background: rgba(245,158,11,0.15); color: var(--yellow); }
        .compte-phase.envoi { background: rgba(34,197,94,0.15); color: var(--green); }
        .compte-phase.inactive { background: rgba(100,116,139,0.15); color: var(--text3); }
        .compte-jours { font-size: 10px; color: var(--text3); margin-bottom: 8px; }
        .btn-tg { display: block; padding: 6px 10px; background: linear-gradient(135deg, #229ED9, #1a7dab); color: white; border-radius: 6px; font-size: 11px; font-weight: 600; text-decoration: none; }
        .btn-tg:hover { opacity: 0.8; }
        .btn-tg.disabled { background: var(--surface2); color: var(--text3); pointer-events: none; }

        /* STATS BAR */
        .stats-bar { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; padding: 16px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; }
        .stat-item { text-align: center; }
        .stat-value { font-size: 24px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
        .stat-label { font-size: 11px; color: var(--text3); margin-top: 2px; }

        /* LOGS */
        .log-container { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
        .log-header { padding: 14px 18px; border-bottom: 1px solid var(--border); font-size: 13px; font-weight: 500; }
        .log-body { padding: 14px; height: 240px; overflow-y: auto; font-family: 'JetBrains Mono', monospace; font-size: 11px; line-height: 1.8; }
        .log-body::-webkit-scrollbar { width: 3px; }
        .log-body::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
        .log-line { color: var(--text2); }
        .log-line.success { color: var(--green); }
        .log-line.error { color: var(--red); }
        .log-line.warning { color: var(--yellow); }
        .log-line.info { color: var(--accent); }
        .invites-body { padding: 12px; height: 240px; overflow-y: auto; }
        .invite-item { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 6px; margin-bottom: 3px; font-size: 12px; }
        .invite-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--green); flex-shrink: 0; }

        /* CONTROLS */
        .controls { display: flex; gap: 12px; margin-top: 20px; }
        .btn { padding: 11px 24px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; border: none; transition: all 0.2s; font-family: 'Inter', sans-serif; }
        .btn-start { background: linear-gradient(135deg, var(--accent), var(--accent2)); color: white; }
        .btn-start:hover { opacity: 0.85; }
        .btn-stop { background: var(--surface2); color: var(--red); border: 1px solid var(--red); }
        .btn-stop:hover { background: var(--red); color: white; }
        .btn-secondary { background: var(--surface2); color: var(--text2); border: 1px solid var(--border); }
        .btn-danger { background: var(--surface2); color: var(--red); border: 1px solid var(--border); font-size: 12px; padding: 6px 12px; border-radius: 6px; cursor: pointer; }
        .btn-danger:hover { background: var(--red); color: white; }
        .btn-add { background: rgba(124,106,247,0.1); color: var(--accent); border: 1px dashed var(--accent); width: 100%; padding: 10px; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600; margin-top: 8px; }
        .btn-add:hover { background: rgba(124,106,247,0.2); }
        .btn-save-main { background: linear-gradient(135deg, var(--accent), var(--accent2)); color: white; padding: 11px 28px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; border: none; margin-top: 16px; }

        /* FORMS */
        .form-group { display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px; }
        .form-label { font-size: 12px; color: var(--text3); font-weight: 500; }
        .form-input { background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; color: var(--text); font-size: 13px; font-family: 'Inter', sans-serif; width: 100%; }
        .form-input:focus { outline: none; border-color: var(--accent); }
        .form-textarea { background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; color: var(--text); font-size: 13px; font-family: 'Inter', sans-serif; width: 100%; resize: vertical; min-height: 70px; }
        .form-textarea:focus { outline: none; border-color: var(--accent); }
        .form-grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
        .form-grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; }
        .form-grid4 { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 12px; }

        /* COMPTE EDIT */
        .compte-edit-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 12px; }
        .compte-edit-header { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
        .compte-edit-num { width: 28px; height: 28px; border-radius: 50%; background: linear-gradient(135deg, var(--accent), var(--accent2)); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; flex-shrink: 0; }
        .compte-edit-nom { font-size: 13px; font-weight: 600; }
        .compte-edit-phase { font-size: 11px; color: var(--text3); margin-left: auto; }

        /* LIST */
        .list-item { display: flex; align-items: center; gap: 10px; background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; }
        .list-item-input { flex: 1; background: transparent; border: none; color: var(--accent); font-size: 13px; font-family: 'JetBrains Mono', monospace; }
        .list-item-input:focus { outline: none; }

        /* MSG */
        .msg-card { background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; padding: 12px; margin-bottom: 8px; display: flex; gap: 10px; align-items: flex-start; }
        .msg-index { font-size: 11px; color: var(--text3); font-family: 'JetBrains Mono', monospace; padding-top: 2px; width: 20px; flex-shrink: 0; }

        /* TOAST */
        .toast { position: fixed; bottom: 24px; right: 24px; padding: 12px 20px; border-radius: 8px; font-size: 13px; font-weight: 600; display: none; z-index: 999; }
        .toast.success { background: var(--green); color: white; }
        .toast.error { background: var(--red); color: white; }

        .divider { border: none; border-top: 1px solid var(--border); margin: 24px 0; }
        .tag { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 100px; font-size: 11px; }
        .tag.maitre { background: rgba(124,106,247,0.15); color: var(--accent); margin-left: 8px; }
        .crm-item { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 12px; }
        .crm-item.repondu { border-color: var(--green); }
        .crm-item.relance { border-color: var(--yellow); }
        .crm-header { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
        .crm-username { font-size: 14px; font-weight: 600; color: var(--accent); font-family: 'JetBrains Mono', monospace; flex: 1; }
        .crm-statut { font-size: 11px; padding: 3px 8px; border-radius: 100px; }
        .crm-statut.invite { background: rgba(100,116,139,0.15); color: var(--text3); }
        .crm-statut.vu { background: rgba(59,130,246,0.15); color: var(--blue); }
        .crm-statut.repondu { background: rgba(34,197,94,0.15); color: var(--green); }
        .crm-statut.relance { background: rgba(245,158,11,0.15); color: var(--yellow); }
        .crm-date { font-size: 11px; color: var(--text3); }
        .crm-message { background: var(--surface2); border-radius: 8px; padding: 10px 14px; font-size: 13px; color: var(--text2); margin-bottom: 10px; border-left: 3px solid var(--green); }
        .crm-reply { display: flex; gap: 8px; margin-top: 10px; }
        .crm-reply-input { flex: 1; background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; color: var(--text); font-size: 13px; font-family: 'Inter', sans-serif; }
        .crm-reply-input:focus { outline: none; border-color: var(--accent); }
        .crm-reply-btn { padding: 8px 16px; background: linear-gradient(135deg, var(--accent), var(--accent2)); color: white; border: none; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; }
        .crm-filters { display: flex; gap: 8px; margin-bottom: 20px; }
        .crm-filter { padding: 6px 14px; border-radius: 100px; font-size: 12px; font-weight: 600; cursor: pointer; border: 1px solid var(--border); background: var(--surface2); color: var(--text2); }
        .crm-filter.active { background: rgba(124,106,247,0.15); border-color: var(--accent); color: var(--accent); }
        .crm-empty { text-align: center; padding: 60px; color: var(--text3); font-size: 14px; }

        /* PAGINATION COMPTES */
        .comptes-pages { display: flex; gap: 8px; margin-bottom: 16px; }
        .page-btn { padding: 6px 14px; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; border: 1px solid var(--border); background: var(--surface2); color: var(--text2); }
        .page-btn.active { background: rgba(124,106,247,0.15); border-color: var(--accent); color: var(--accent); }
    </style>
</head>
<body>

<div class="sidebar">
    <div class="sidebar-logo">
        <div class="logo-icon">🤖</div>
        <div>
            <div class="logo-text">TG Bot</div>
            <div class="logo-sub">20 comptes</div>
        </div>
    </div>
    <button class="nav-item active" onclick="showPage('dashboard', this)"><span class="nav-icon">📊</span> Dashboard</button>
    <button class="nav-item" onclick="showPage('crm', this)"><span class="nav-icon">💬</span> CRM <span id="crm-badge" style="background:var(--red);color:white;font-size:10px;padding:2px 6px;border-radius:100px;margin-left:4px;display:none;">0</span></button>
    <button class="nav-item" onclick="showPage('comptes', this)"><span class="nav-icon">👤</span> Comptes</button>
    <button class="nav-item" onclick="showPage('groupes', this)"><span class="nav-icon">👥</span> Groupes</button>
    <button class="nav-item" onclick="showPage('amis', this)"><span class="nav-icon">🤝</span> Amis warmup</button>
    <button class="nav-item" onclick="showPage('messages', this)"><span class="nav-icon">✉️</span> Messages</button>
    <button class="nav-item" onclick="showPage('parametres', this)"><span class="nav-icon">⚙️</span> Paramètres</button>
    <div class="sidebar-bottom">
        <div class="status-pill">
            <div class="status-dot" id="statusDot"></div>
            <span id="statusText" style="font-size:13px;">Arrêté</span>
        </div>
    </div>
</div>

<div class="main">

    <!-- DASHBOARD -->
    <div class="page active" id="page-dashboard">
        <div class="page-title">Dashboard</div>
        <div class="page-sub">Vue d'ensemble — 20 comptes actifs</div>

        <div class="stats-bar">
            <div class="stat-item">
                <div class="stat-value green" id="envoyes">0</div>
                <div class="stat-label">Messages envoyés</div>
            </div>
            <div class="stat-item">
                <div class="stat-value accent" id="progression">0%</div>
                <div class="stat-label" id="progressionSub">0 / 0 invités</div>
            </div>
            <div class="stat-item">
                <div class="stat-value yellow" id="restants">0</div>
                <div class="stat-label">Contacts restants</div>
            </div>
            <div class="stat-item">
                <div class="stat-value" id="comptes-actifs">0</div>
                <div class="stat-label">Comptes configurés</div>
            </div>
        </div>

        <div class="section-title">Mes 20 comptes</div>
        <div class="comptes-grid" id="comptesGrid"></div>

        <div class="grid2">
            <div class="log-container">
                <div class="log-header">📋 Logs en direct</div>
                <div class="log-body" id="logBody"><div class="empty">Aucun log</div></div>
            </div>
            <div class="log-container">
                <div class="log-header">✅ Derniers invités</div>
                <div class="invites-body" id="invitesBody"><div class="empty">Aucun invité</div></div>
            </div>
        </div>

        <div class="controls">
            <button class="btn btn-start" onclick="startBot()">▶ Démarrer le bot</button>
            <button class="btn btn-stop" onclick="stopBot()">■ Arrêter</button>
            <button class="btn btn-secondary" onclick="refresh()">↻ Actualiser</button>
        </div>
    </div>

    <!-- CRM -->
    <div class="page" id="page-crm">
        <div class="page-title">CRM — Conversations</div>
        <div class="page-sub">Toutes les réponses reçues — réponds directement depuis ici</div>

        <div class="crm-filters">
            <button class="crm-filter active" onclick="filtrerCRM('tous', this)">Tous</button>
            <button class="crm-filter" onclick="filtrerCRM('repondu', this)">💬 Réponses</button>
            <button class="crm-filter" onclick="filtrerCRM('vu', this)">👁️ Vus</button>
            <button class="crm-filter" onclick="filtrerCRM('invite', this)">📨 Invités</button>
            <button class="crm-filter" onclick="filtrerCRM('relance', this)">🔄 Relancés</button>
        </div>

        <div id="crm-list"><div class="crm-empty">Aucune conversation pour l'instant<br><br>Lance le bot pour commencer à inviter des personnes !</div></div>
    </div>

    <!-- COMPTES -->
    <div class="page" id="page-comptes">
        <div class="page-title">Comptes Telegram</div>
        <div class="page-sub">Configure tes 20 comptes et le compte maître</div>

        <div class="section-title">👑 Compte Maître <span class="tag maitre">Envoie aux 20 comptes</span></div>
        <div class="card" style="margin-bottom:24px;">
            <div class="form-grid3">
                <div class="form-group">
                    <div class="form-label">API ID</div>
                    <input class="form-input" id="maitre_api_id" placeholder="1234567" />
                </div>
                <div class="form-group">
                    <div class="form-label">API Hash</div>
                    <input class="form-input" id="maitre_api_hash" placeholder="abc123..." />
                </div>
                <div class="form-group">
                    <div class="form-label">Numéro de téléphone</div>
                    <input class="form-input" id="maitre_tel" placeholder="+33600000000" />
                </div>
            </div>
        </div>

        <div class="section-title">Mes 20 comptes</div>
        <div class="comptes-pages" id="comptes-pages"></div>
        <div id="comptes-edit-list"></div>

        <button class="btn-save-main" onclick="sauvegarderComptes()">💾 Sauvegarder tous les comptes</button>
    </div>

    <!-- GROUPES -->
    <div class="page" id="page-groupes">
        <div class="page-title">Groupes Telegram</div>
        <div class="page-sub">Les groupes dont tu es membre — le bot récupère les membres actifs</div>
        <div id="groupes-list"></div>
        <button class="btn-add" onclick="ajouterGroupe()">+ Ajouter un groupe</button>
        <div class="controls">
            <button class="btn-save-main" onclick="sauvegarderGroupes()">💾 Sauvegarder</button>
        </div>
    </div>

    <!-- AMIS -->
    <div class="page" id="page-amis">
        <div class="page-title">Amis Warmup</div>
        <div class="page-sub">Les @ de tes amis à qui le bot envoie des messages pendant le warm up</div>
        <div id="amis-list"></div>
        <button class="btn-add" onclick="ajouterAmi()">+ Ajouter un ami</button>
        <div class="controls">
            <button class="btn-save-main" onclick="sauvegarderAmis()">💾 Sauvegarder</button>
        </div>
    </div>

    <!-- MESSAGES -->
    <div class="page" id="page-messages">
        <div class="page-title">Messages</div>
        <div class="page-sub">Tous tes scripts de messages — le bot pioche aléatoirement</div>

        <div class="section-title">📨 Messages d'invitation</div>
        <div style="font-size:12px;color:var(--text3);margin-bottom:12px;">Utilise {canal} pour insérer le lien automatiquement</div>
        <div id="msgs-invitation"></div>
        <button class="btn-add" onclick="ajouterMessage('invitation')">+ Ajouter</button>

        <hr class="divider">
        <div class="section-title">🤝 Messages aux amis (Warm up)</div>
        <div id="msgs-amis"></div>
        <button class="btn-add" onclick="ajouterMessage('amis')">+ Ajouter</button>

        <hr class="divider">
        <div class="section-title">👥 Messages dans les groupes (Warm up)</div>
        <div id="msgs-groupes"></div>
        <button class="btn-add" onclick="ajouterMessage('groupes')">+ Ajouter</button>

        <hr class="divider">
        <div class="section-title">👑 Messages du compte maître</div>
        <div id="msgs-maitre"></div>
        <button class="btn-add" onclick="ajouterMessage('maitre')">+ Ajouter</button>

        <hr class="divider">
        <div class="section-title">🔄 Relance — Message pas vu (après 7 jours)</div>
        <div style="font-size:12px;color:var(--text3);margin-bottom:12px;">Envoyé si la personne n'a pas ouvert ton message après 7 jours. Utilise {canal} pour le lien.</div>
        <div id="msgs-relance-pas-vu"></div>
        <button class="btn-add" onclick="ajouterMessage('relance_pas_vu')">+ Ajouter</button>

        <hr class="divider">
        <div class="section-title">👁️ Relance — Message vu sans réponse (après 7 jours)</div>
        <div style="font-size:12px;color:var(--text3);margin-bottom:12px;">Envoyé si la personne a lu ton message mais n'a pas répondu après 7 jours. Utilise {canal} pour le lien.</div>
        <div id="msgs-relance-vu"></div>
        <button class="btn-add" onclick="ajouterMessage('relance_vu')">+ Ajouter</button>

        <div class="controls">
            <button class="btn-save-main" onclick="sauvegarderMessages()">💾 Sauvegarder</button>
        </div>
    </div>

    <!-- PARAMETRES -->
    <div class="page" id="page-parametres">
        <div class="page-title">Paramètres</div>
        <div class="page-sub">Configuration générale du bot</div>

        <div class="card" style="margin-bottom:16px;">
            <div class="section-title" style="margin-top:0;">📢 Canal & Notifications</div>
            <div class="form-grid2">
                <div class="form-group">
                    <div class="form-label">Lien de ton canal</div>
                    <input class="form-input" id="param_canal" placeholder="https://t.me/toncanal" />
                </div>
                <div class="form-group">
                    <div class="form-label">Ton username (notifications)</div>
                    <input class="form-input" id="param_username" placeholder="@tonusername" />
                </div>
            </div>
        </div>

        <div class="card" style="margin-bottom:16px;">
            <div class="section-title" style="margin-top:0;">🔥 Warm Up</div>
            <div class="form-grid2">
                <div class="form-group">
                    <div class="form-label">Durée totale (jours)</div>
                    <input class="form-input" id="param_duree" type="number" placeholder="21" />
                </div>
            </div>
        </div>

        <div class="card" style="margin-bottom:24px;">
            <div class="section-title" style="margin-top:0;">📨 Limites d'envoi progressives</div>
            <div class="form-grid3">
                <div class="form-group">
                    <div class="form-label">Semaine 2 (DM/jour)</div>
                    <input class="form-input" id="param_s1" type="number" placeholder="3" />
                </div>
                <div class="form-group">
                    <div class="form-label">Semaine 3 (DM/jour)</div>
                    <input class="form-input" id="param_s2" type="number" placeholder="10" />
                </div>
                <div class="form-group">
                    <div class="form-label">Semaine 4+ (DM/jour)</div>
                    <input class="form-input" id="param_s3" type="number" placeholder="20" />
                </div>
            </div>
        </div>

        <button class="btn-save-main" onclick="sauvegarderParametres()">💾 Sauvegarder</button>
    </div>

</div>

<div class="toast" id="toast"></div>

<script>
let config = {};
let currentComptePage = 0;
const COMPTES_PAR_PAGE = 5;

function showPage(name, btn) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById('page-' + name).classList.add('active');
    if (btn) btn.classList.add('active');
    if (name === 'crm') renderCRM('tous');

function filtrerCRM(filtre, btn) {
    document.querySelectorAll('.crm-filter').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    renderCRM(filtre);
}

function renderCRM(filtre) {
    fetch('/api/crm').then(r => r.json()).then(data => {
        const list = document.getElementById('crm-list');
        let items = Object.values(data);

        if (filtre !== 'tous') {
            items = items.filter(c => c.statut === filtre);
        }

        // Trier : répondus en premier
        items.sort((a, b) => {
            if (a.repondu && !b.repondu) return -1;
            if (!a.repondu && b.repondu) return 1;
            return new Date(b.date_invitation) - new Date(a.date_invitation);
        });

        if (items.length === 0) {
            list.innerHTML = '<div class="crm-empty">Aucune conversation dans cette catégorie</div>';
            return;
        }

        list.innerHTML = items.map(c => {
            const statutLabel = {
                'invite': '📨 Invité',
                'vu': '👁️ Vu',
                'repondu': '💬 A répondu',
                'relance': '🔄 Relancé'
            }[c.statut] || c.statut;

            const date = new Date(c.date_invitation).toLocaleDateString('fr-FR');
            const msgs = (c.messages_recus || []).map(m =>
                `<div class="crm-message">💬 ${m.texte}</div>`
            ).join('');

            const replyBox = c.repondu ? `
                <div class="crm-reply">
                    <input class="crm-reply-input" id="reply-${c.username}" placeholder="Répondre à ${c.username}..." />
                    <button class="crm-reply-btn" onclick="envoyerReponse('${c.username}')">Envoyer</button>
                </div>` : '';

            return `<div class="crm-item ${c.statut}">
                <div class="crm-header">
                    <div class="crm-username">${c.username}</div>
                    <span class="crm-statut ${c.statut}">${statutLabel}</span>
                    <div class="crm-date">${date}</div>
                    ${c.nb_relances > 0 ? `<span style="font-size:11px;color:var(--yellow);">🔄 ${c.nb_relances} relance(s)</span>` : ''}
                </div>
                ${msgs}
                ${replyBox}
            </div>`;
        }).join('');
    });
}

function envoyerReponse(username) {
    const input = document.getElementById('reply-' + username);
    const message = input.value.trim();
    if (!message) return;

    fetch('/api/repondre', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username, message})
    }).then(r => r.json()).then(d => {
        showToast(d.message || '✅ Message envoyé !');
        input.value = '';
        renderCRM('tous');
    });
}

function showPage(name, btn) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById('page-' + name).classList.add('active');
    if (btn) btn.classList.add('active');

    fetch('/api/stats').then(r => r.json()).then(data => {
        config = data.config || {};
        if (name === 'comptes') renderComptes();
        if (name === 'crm') renderCRM('tous');
        if (name === 'groupes') renderGroupes();
        if (name === 'amis') renderAmis();
        if (name === 'messages') renderMessages();
        if (name === 'parametres') renderParametres();
    });
}

function showToast(msg, type='success') {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className = 'toast ' + type;
    t.style.display = 'block';
    setTimeout(() => t.style.display = 'none', 3000);
}

// ─── COMPTES ───
function renderComptes() {
    document.getElementById('maitre_api_id').value = config.compte_maitre?.api_id || '';
    document.getElementById('maitre_api_hash').value = config.compte_maitre?.api_hash || '';
    document.getElementById('maitre_tel').value = config.compte_maitre?.tel || '';

    const comptes = config.comptes || [];
    const nbPages = Math.ceil(comptes.length / COMPTES_PAR_PAGE);

    // Pages buttons
    const pagesDiv = document.getElementById('comptes-pages');
    pagesDiv.innerHTML = Array.from({length: nbPages}, (_, i) =>
        `<button class="page-btn ${i === currentComptePage ? 'active' : ''}" onclick="goComptePage(${i})">
            Comptes ${i*5+1}-${Math.min((i+1)*5, comptes.length)}
        </button>`
    ).join('');

    // Liste des comptes de la page courante
    const start = currentComptePage * COMPTES_PAR_PAGE;
    const pageComptes = comptes.slice(start, start + COMPTES_PAR_PAGE);

    const list = document.getElementById('comptes-edit-list');
    list.innerHTML = pageComptes.map((c, pi) => {
        const i = start + pi;
        return `
        <div class="compte-edit-card">
            <div class="compte-edit-header">
                <div class="compte-edit-num">${i+1}</div>
                <div class="compte-edit-nom">${c.nom}</div>
                <div class="compte-edit-phase">${c.api_id ? '✅ Configuré' : '⚪ Non configuré'}</div>
            </div>
            <div class="form-grid4">
                <div class="form-group">
                    <div class="form-label">Numéro</div>
                    <input class="form-input" id="c${i}_tel" value="${c.tel || ''}" placeholder="+336..." />
                </div>
                <div class="form-group">
                    <div class="form-label">API ID</div>
                    <input class="form-input" id="c${i}_api_id" value="${c.api_id || ''}" placeholder="1234567" />
                </div>
                <div class="form-group" style="grid-column: span 2;">
                    <div class="form-label">API Hash</div>
                    <input class="form-input" id="c${i}_api_hash" value="${c.api_hash || ''}" placeholder="abc123def456..." />
                </div>
            </div>
        </div>`;
    }).join('');
}

function goComptePage(page) {
    currentComptePage = page;
    renderComptes();
}

function sauvegarderComptes() {
    config.compte_maitre = {
        api_id: document.getElementById('maitre_api_id').value,
        api_hash: document.getElementById('maitre_api_hash').value,
        tel: document.getElementById('maitre_tel').value,
        session: 'compte_maitre'
    };
    const comptes = config.comptes || [];
    comptes.forEach((c, i) => {
        const telEl = document.getElementById(`c${i}_tel`);
        const idEl = document.getElementById(`c${i}_api_id`);
        const hashEl = document.getElementById(`c${i}_api_hash`);
        if (telEl) comptes[i].tel = telEl.value;
        if (idEl) comptes[i].api_id = idEl.value;
        if (hashEl) comptes[i].api_hash = hashEl.value;
    });
    config.comptes = comptes;
    saveConfig();
}

// ─── GROUPES ───
function renderGroupes() {
    document.getElementById('groupes-list').innerHTML = (config.groupes || []).map((g, i) => `
        <div class="list-item">
            <span style="color:var(--text3);font-size:12px;width:20px;">${i+1}</span>
            <input class="list-item-input" id="g${i}" value="${g}" placeholder="@nomdugroupe" />
            <button class="btn-danger" onclick="supprimerGroupe(${i})">✕</button>
        </div>`).join('');
}
function ajouterGroupe() { config.groupes = config.groupes || []; config.groupes.push('@nouveau_groupe'); renderGroupes(); }
function supprimerGroupe(i) { config.groupes.splice(i, 1); renderGroupes(); }
function sauvegarderGroupes() {
    config.groupes = (config.groupes || []).map((_, i) => document.getElementById(`g${i}`).value).filter(v => v.trim());
    saveConfig();
}

// ─── AMIS ───
function renderAmis() {
    document.getElementById('amis-list').innerHTML = (config.amis || []).map((a, i) => `
        <div class="list-item">
            <span style="color:var(--text3);font-size:12px;width:20px;">${i+1}</span>
            <input class="list-item-input" id="a${i}" value="${a}" placeholder="@username" />
            <button class="btn-danger" onclick="supprimerAmi(${i})">✕</button>
        </div>`).join('');
}
function ajouterAmi() { config.amis = config.amis || []; config.amis.push('@nouvel_ami'); renderAmis(); }
function supprimerAmi(i) { config.amis.splice(i, 1); renderAmis(); }
function sauvegarderAmis() {
    config.amis = (config.amis || []).map((_, i) => document.getElementById(`a${i}`).value).filter(v => v.trim());
    saveConfig();
}

// ─── MESSAGES ───
function renderMsgSection(listId, key) {
    document.getElementById(listId).innerHTML = (config[key] || []).map((m, i) => `
        <div class="msg-card">
            <span class="msg-index">${i+1}</span>
            <textarea class="form-textarea" id="m_${key}_${i}">${m}</textarea>
            <button class="btn-danger" onclick="supprimerMessage('${key}', ${i})" style="flex-shrink:0;">✕</button>
        </div>`).join('');
}
function renderMessages() {
    renderMsgSection('msgs-invitation', 'messages_invitation');
    renderMsgSection('msgs-amis', 'messages_amis');
    renderMsgSection('msgs-groupes', 'messages_groupes');
    renderMsgSection('msgs-maitre', 'messages_maitre');
    renderMsgSection('msgs-relance-pas-vu', 'messages_relance_pas_vu');
    renderMsgSection('msgs-relance-vu', 'messages_relance_vu');
}
function ajouterMessage(key) {
    const k = 'messages_' + key;
    config[k] = config[k] || [];
    config[k].push('Nouveau message...');
    renderMessages();
}
    config['messages_' + key].splice(i, 1);
    renderMessages();
}
function sauvegarderMessages() {
    ['invitation', 'amis', 'groupes', 'maitre', 'relance_pas_vu', 'relance_vu'].forEach(key => {
        const k = 'messages_' + key;
        config[k] = (config[k] || []).map((_, i) => {
            const el = document.getElementById(`m_${k}_${i}`);
            return el ? el.value : '';
        }).filter(v => v.trim());
    });
    saveConfig();
}

// ─── PARAMETRES ───
function renderParametres() {
    document.getElementById('param_canal').value = config.canal_lien || '';
    document.getElementById('param_username').value = config.mon_username || '';
    document.getElementById('param_duree').value = config.duree_warmup || 21;
    document.getElementById('param_s1').value = config.limite_semaine_1 || 3;
    document.getElementById('param_s2').value = config.limite_semaine_2 || 10;
    document.getElementById('param_s3').value = config.limite_semaine_3 || 20;
}
function sauvegarderParametres() {
    config.canal_lien = document.getElementById('param_canal').value;
    config.mon_username = document.getElementById('param_username').value;
    config.duree_warmup = parseInt(document.getElementById('param_duree').value) || 21;
    config.limite_semaine_1 = parseInt(document.getElementById('param_s1').value) || 3;
    config.limite_semaine_2 = parseInt(document.getElementById('param_s2').value) || 10;
    config.limite_semaine_3 = parseInt(document.getElementById('param_s3').value) || 20;
    saveConfig();
}

// ─── SAVE ───
function saveConfig() {
    fetch('/api/config', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(config)
    }).then(r => r.json()).then(() => showToast('✅ Sauvegardé !'));
}

// ─── REFRESH ───
function refresh() {
    fetch('/api/stats').then(r => r.json()).then(data => {
        config = data.config || {};

        document.getElementById('envoyes').textContent = data.stats.envoyes || 0;
        const total = data.total, invites = data.invites;
        const pct = total > 0 ? Math.round((invites / total) * 100) : 0;
        document.getElementById('restants').textContent = total - invites;
        document.getElementById('progression').textContent = pct + '%';
        document.getElementById('progressionSub').textContent = invites + ' / ' + total + ' invités';

        const actifs = (data.comptes || []).filter(c => c.configured).length;
        document.getElementById('comptes-actifs').textContent = actifs + '/20';

        // Badge CRM
        fetch('/api/crm').then(r => r.json()).then(crm => {
            const reponses = Object.values(crm).filter(c => c.repondu).length;
            const badge = document.getElementById('crm-badge');
            if (reponses > 0) {
                badge.textContent = reponses;
                badge.style.display = 'inline';
            } else {
                badge.style.display = 'none';
            }
        });
        if (data.running) { dot.classList.add('active'); document.getElementById('statusText').textContent = 'En cours'; }
        else { dot.classList.remove('active'); document.getElementById('statusText').textContent = 'Arrêté'; }

        const logBody = document.getElementById('logBody');
        if (data.logs.length > 0) {
            logBody.innerHTML = data.logs.map(l => {
                let cls = 'log-line';
                if (l.includes('✅')) cls += ' success';
                else if (l.includes('❌') || l.includes('🚨')) cls += ' error';
                else if (l.includes('⚠️')) cls += ' warning';
                else if (l.includes('🔥') || l.includes('👑') || l.includes('📨') || l.includes('🤖')) cls += ' info';
                return '<div class="' + cls + '">' + l + '</div>';
            }).join('');
            logBody.scrollTop = logBody.scrollHeight;
        }

        const invitesBody = document.getElementById('invitesBody');
        if (data.derniers_invites && data.derniers_invites.length > 0) {
            invitesBody.innerHTML = data.derniers_invites.slice(-20).reverse().map(u =>
                '<div class="invite-item"><div class="invite-dot"></div>' + u + '</div>'
            ).join('');
        }

        // Grid des 20 comptes
        const comptesGrid = document.getElementById('comptesGrid');
        if (data.comptes) {
            comptesGrid.innerHTML = data.comptes.map(c => {
                const telLink = c.tel ? 'https://t.me/' + c.tel.replace('+', '') : '#';
                const phaseLabel = !c.configured ? 'Non configuré' : c.phase === 'envoi' ? '📨 Envoi' : '🔥 Warm up';
                const phaseClass = !c.configured ? 'inactive' : c.phase;
                const joursLabel = !c.configured ? '' : c.phase === 'warmup' ? 'Jour ' + c.jours + '/21' : 'Actif';

                // Score
                let scoreEmoji = '🟢';
                let scoreCouleur = 'var(--green)';
                if (c.score) {
                    if (c.score.dernier_statut === 'attention') { scoreEmoji = '🟡'; scoreCouleur = 'var(--yellow)'; }
                    else if (c.score.dernier_statut === 'restreint') { scoreEmoji = '🔴'; scoreCouleur = 'var(--red)'; }
                    else if (c.score.dernier_statut === 'banni') { scoreEmoji = '⚫'; scoreCouleur = 'var(--text3)'; }
                }
                const scoreVal = c.score ? c.score.score : 100;
                const scoreTxt = c.configured ? `<div style="font-size:11px;color:${scoreCouleur};margin-bottom:6px;">${scoreEmoji} Trust ${scoreVal}/100</div>` : '';

                return '<div class="compte-card' + (c.configured ? ' configured' : '') + '">' +
                    '<div class="compte-avatar' + (!c.configured ? ' inactive' : '') + '">👤</div>' +
                    '<div class="compte-nom">' + c.nom + '</div>' +
                    '<span class="compte-phase ' + phaseClass + '">' + phaseLabel + '</span>' +
                    (joursLabel ? '<div class="compte-jours">' + joursLabel + '</div>' : '') +
                    scoreTxt +
                    '<a class="btn-tg' + (!c.configured ? ' disabled' : '') + '" href="' + telLink + '" target="_blank">' +
                    (c.configured ? '✈️ Ouvrir' : '⚙️ Config') + '</a>' +
                    '</div>';
            }).join('');
        }
    });
}

function startBot() {
    fetch('/api/start', {method:'POST'}).then(r=>r.json()).then(()=>{ showToast('🚀 Bot démarré !'); refresh(); });
}
function stopBot() {
    fetch('/api/stop', {method:'POST'}).then(r=>r.json()).then(()=>{ showToast('⛔ Bot arrêté'); refresh(); });
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
    config = charger_config()
    contacts = charger_contacts()
    invites = charger_invites()
    stats_data = charger_stats()
    comptes_data = [{
        "nom": c["nom"],
        "tel": c.get("tel", ""),
        "phase": statut_compte(c["session"]),
        "jours": jours_warmup(c["session"]),
        "configured": bool(c.get("api_id") and c.get("api_hash")),
        "score": score_compte(c["session"])
    } for c in config.get("comptes", [])]
    return jsonify({
        "stats": stats_data,
        "total": len(contacts),
        "invites": len(invites),
        "running": bot_running,
        "logs": logs[-50:],
        "derniers_invites": invites[-20:],
        "comptes": comptes_data,
        "config": config
    })

@app.route('/api/crm')
def get_crm():
    if not os.path.exists("crm.json"):
        return jsonify({})
    with open("crm.json", "r") as f:
        return jsonify(json.load(f))

@app.route('/api/repondre', methods=['POST'])
def repondre():
    data = request.get_json()
    username = data.get("username")
    message = data.get("message")

    if not username or not message:
        return jsonify({"message": "❌ Données manquantes"})

    # On met la réponse en file d'attente dans un fichier
    queue_file = "reply_queue.json"
    queue = []
    if os.path.exists(queue_file):
        with open(queue_file, "r") as f:
            queue = json.load(f)

    queue.append({
        "username": username,
        "message": message,
        "date": datetime.now().isoformat()
    })

    with open(queue_file, "w") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)

    return jsonify({"message": f"✅ Message en file d'attente pour {username}"})

@app.route('/api/config', methods=['POST'])
def save_config():
    data = request.get_json()
    sauvegarder_config(data)
    return jsonify({"message": "Config sauvegardée"})

@app.route('/api/start', methods=['POST'])
def start_bot():
    global bot_running
    if bot_running:
        return jsonify({"message": "Bot déjà en cours"})
    bot_running = True
    ajouter_log("🚀 Bot démarré")
    def run():
        global bot_running
        process = subprocess.Popen(["python", "telegram_warmup.py"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
