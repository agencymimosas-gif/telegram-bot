import asyncio
import json
import random
import os
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import ChannelParticipantsAdmins

FICHIER_CONFIG   = "config.json"
FICHIER_STATUT   = "warmup_statut.json"
FICHIER_CONTACTS = "contacts.txt"
FICHIER_INVITES  = "deja_invites.json"
FICHIER_STATS    = "stats.json"
FICHIER_SCORES   = "scores.json"
FICHIER_CRM      = "crm.json"

USERNAME_MAITRE = "@mimosqsa"

# ─── CONFIG ───
def charger_config():
    if not os.path.exists(FICHIER_CONFIG):
        return {}
    with open(FICHIER_CONFIG, "r") as f:
        return json.load(f)

# ─── CRM ───
def charger_crm():
    if not os.path.exists(FICHIER_CRM):
        return {}
    with open(FICHIER_CRM, "r") as f:
        return json.load(f)

def sauvegarder_crm(crm):
    with open(FICHIER_CRM, "w") as f:
        json.dump(crm, f, indent=2, ensure_ascii=False)

def update_crm(username, data):
    crm = charger_crm()
    if username not in crm:
        crm[username] = {
            "username": username,
            "statut": "invite",
            "date_invitation": datetime.now().isoformat(),
            "lu": False,
            "repondu": False,
            "messages_recus": [],
            "compte_utilisé": None,
        }
    crm[username].update(data)
    sauvegarder_crm(crm)

# ─── SCORES ───
def charger_scores():
    if not os.path.exists(FICHIER_SCORES):
        return {}
    with open(FICHIER_SCORES, "r") as f:
        return json.load(f)

def sauvegarder_scores(scores):
    with open(FICHIER_SCORES, "w") as f:
        json.dump(scores, f, indent=2)

def get_score(session):
    scores = charger_scores()
    if session not in scores:
        scores[session] = {
            "score": 100,
            "flood_wait": 0,
            "peer_flood": 0,
            "messages_ok": 0,
            "dernier_statut": "sain",
            "derniere_activite": datetime.now().isoformat()
        }
        sauvegarder_scores(scores)
    return scores[session]

def update_score(session, event):
    scores = charger_scores()
    if session not in scores:
        scores[session] = {
            "score": 100,
            "flood_wait": 0,
            "peer_flood": 0,
            "messages_ok": 0,
            "dernier_statut": "sain",
            "derniere_activite": datetime.now().isoformat()
        }
    s = scores[session]
    s["derniere_activite"] = datetime.now().isoformat()
    if event == "ok":
        s["messages_ok"] += 1
        s["score"] = min(100, s["score"] + 2)
    elif event == "flood_wait":
        s["flood_wait"] += 1
        s["score"] = max(0, s["score"] - 10)
    elif event == "peer_flood":
        s["peer_flood"] += 1
        s["score"] = max(0, s["score"] - 30)
    elif event == "ban":
        s["score"] = 0
    if s["score"] >= 70:
        s["dernier_statut"] = "sain"
    elif s["score"] >= 40:
        s["dernier_statut"] = "attention"
    elif s["score"] >= 10:
        s["dernier_statut"] = "restreint"
    else:
        s["dernier_statut"] = "banni"
    scores[session] = s
    sauvegarder_scores(scores)
    return s

# ─── STATUT ───
def charger_statut():
    if not os.path.exists(FICHIER_STATUT):
        return {}
    with open(FICHIER_STATUT, "r") as f:
        return json.load(f)

def sauvegarder_statut(statut):
    with open(FICHIER_STATUT, "w") as f:
        json.dump(statut, f, indent=2)

def get_statut_compte(session):
    statut = charger_statut()
    if session not in statut:
        statut[session] = {
            "phase": "warmup",
            "debut_warmup": datetime.now().isoformat(),
        }
        sauvegarder_statut(statut)
    return statut[session]

def update_statut_compte(session, data):
    statut = charger_statut()
    if session not in statut:
        statut[session] = {}
    statut[session].update(data)
    sauvegarder_statut(statut)

def jours_depuis_debut(session):
    s = get_statut_compte(session)
    debut = datetime.fromisoformat(s["debut_warmup"])
    return (datetime.now() - debut).days

# ─── CONTACTS ───
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

def sauvegarder_invite(username):
    invites = charger_invites()
    if username not in invites:
        invites.append(username)
    with open(FICHIER_INVITES, "w") as f:
        json.dump(invites, f)

def sauvegarder_contacts(membres):
    existants = set()
    if os.path.exists(FICHIER_CONTACTS):
        with open(FICHIER_CONTACTS, "r") as f:
            existants = set(line.strip() for line in f.readlines() if line.strip())
    nouveaux = membres - existants
    with open(FICHIER_CONTACTS, "a") as f:
        for m in nouveaux:
            f.write(m + "\n")
    print(f"  📋 {len(nouveaux)} nouveaux contacts ajoutés")

def charger_stats():
    if not os.path.exists(FICHIER_STATS):
        return {"envoyes": 0, "vus": 0, "reponses": 0}
    with open(FICHIER_STATS, "r") as f:
        return json.load(f)

def sauvegarder_stats(stats):
    with open(FICHIER_STATS, "w") as f:
        json.dump(stats, f)

def limite_du_jour(jours, config):
    if jours < 3:
        return 0
    elif jours < 7:
        return config.get("limite_semaine_1", 3)
    elif jours < 14:
        return config.get("limite_semaine_2", 5)
    elif jours < 21:
        return config.get("limite_semaine_3", 10)
    else:
        return config.get("limite_semaine_4", 15)

# ─── SCRAPING ───
async def scraper_membres(client, config):
    membres = set()
    admins = set()
    for groupe in config.get("groupes", []):
        try:
            entity = await client.get_entity(groupe)
            from telethon.tl.functions.channels import GetParticipantsRequest
            admins_result = await client(GetParticipantsRequest(
                entity, ChannelParticipantsAdmins(), offset=0, limit=200, hash=0
            ))
            for user in admins_result.users:
                if user.username:
                    admins.add(f"@{user.username}")
                admins.add(str(user.id))
            async for message in client.iter_messages(entity, limit=1000):
                if message.sender and hasattr(message.sender, 'username'):
                    if message.sender.username and not message.sender.bot:
                        username = f"@{message.sender.username}"
                        if username not in admins and str(message.sender.id) not in admins:
                            membres.add(username)
            print(f"  ✅ {groupe} — {len(membres)} membres actifs")
        except Exception as e:
            print(f"  ❌ {groupe} : {e}")
    return membres

# ─── VÉRIFICATION CRM ───
async def verifier_crm(client):
    crm = charger_crm()
    stats = charger_stats()
    nouvelles_reponses = 0
    print(f"  🔍 Vérification des réponses...")

    for username, data in crm.items():
        if data.get("repondu"):
            continue
        try:
            entity = await client.get_entity(username)
            messages = await client.get_messages(entity, limit=10)
            for msg in messages:
                if not msg.out:
                    texte = msg.text or ""
                    messages_recus = data.get("messages_recus", [])
                    if texte and texte not in [m.get("texte") for m in messages_recus]:
                        messages_recus.append({
                            "texte": texte,
                            "date": datetime.now().isoformat()
                        })
                        update_crm(username, {
                            "repondu": True,
                            "statut": "repondu",
                            "messages_recus": messages_recus
                        })
                        stats["reponses"] += 1
                        nouvelles_reponses += 1
                        print(f"  💬 Réponse de {username} : '{texte[:50]}'")
            await asyncio.sleep(1)
        except Exception:
            pass

    sauvegarder_stats(stats)
    if nouvelles_reponses > 0:
        print(f"  🎉 {nouvelles_reponses} nouvelles réponses !")

# ─── WARMUP ───
async def phase_warmup(account, config, jours):
    session = account["session"]
    client = TelegramClient(session, int(account["api_id"]), account["api_hash"])

    try:
        await client.start()
    except Exception as e:
        print(f"  🚨 [{session}] Connexion impossible : {e}")
        update_score(session, "ban")
        return

    print(f"\n🔥 [{session}] WARM UP — Jour {jours}")

    # 1. Rejoindre les groupes
    for groupe in config.get("groupes", []):
        try:
            await client(JoinChannelRequest(groupe))
            print(f"  ✅ Rejoint {groupe}")
            await asyncio.sleep(random.randint(5, 15))
        except Exception as e:
            print(f"  ℹ️ {groupe} : {e}")

    # 2. Messages au compte maître
    messages_maitre = config.get("messages_maitre", ["Ça va ?", "T'es là ?"])
    nb = random.randint(2, 4)
    msgs = random.sample(messages_maitre, min(nb, len(messages_maitre)))
    for msg in msgs:
        try:
            await client.send_message(USERNAME_MAITRE, msg)
            update_score(session, "ok")
            print(f"  💬 → {USERNAME_MAITRE} : '{msg}'")
            await asyncio.sleep(random.randint(1800, 7200))
        except FloodWaitError as e:
            update_score(session, "flood_wait")
            print(f"  ⚠️ FloodWait {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"  ❌ {e}")

    # 3. DM progressifs (jour 3+)
    limite = limite_du_jour(jours, config)
    if limite > 0:
        score = get_score(session)
        if score["dernier_statut"] in ["restreint", "banni"]:
            print(f"  🚫 Score trop bas — DM suspendus")
            await client.disconnect()
            return

        print(f"  📨 Jour {jours} — {limite} DM autorisés")

        membres = await scraper_membres(client, config)
        sauvegarder_contacts(membres)

        contacts = charger_contacts()
        invites = charger_invites()
        restants = [c for c in contacts if c not in invites]
        random.shuffle(restants)
        a_envoyer = restants[:limite]

        messages_invitation = config.get("messages_invitation", ["Salut ! {canal}"])
        canal = config.get("canal_lien", "")
        stats = charger_stats()

        for username in a_envoyer:
            try:
                msg = random.choice(messages_invitation).replace("{canal}", canal)
                await client.send_message(username, msg)
                sauvegarder_invite(username)
                stats["envoyes"] += 1
                sauvegarder_stats(stats)
                update_score(session, "ok")
                update_crm(username, {"compte_utilisé": session, "statut": "invite"})
                print(f"  ✅ Invité : {username}")
                await asyncio.sleep(random.randint(180, 600))
            except FloodWaitError as e:
                update_score(session, "flood_wait")
                print(f"  ⚠️ FloodWait {e.seconds}s")
                await asyncio.sleep(e.seconds)
            except UserPrivacyRestrictedError:
                sauvegarder_invite(username)
                print(f"  🔒 DM désactivés : {username}")
            except Exception as e:
                print(f"  ❌ {username} : {e}")
                if "PeerFlood" in str(e):
                    update_score(session, "peer_flood")
                    print(f"  🚨 {session} restreint !")
                    break

        # Vérification des réponses
        await verifier_crm(client)

    else:
        print(f"  ⏳ Jour {jours} — DM commencent au jour 3")

    # Passage en phase envoi
    if jours >= config.get("duree_warmup", 21):
        print(f"\n🎉 [{session}] Warm up terminé !")
        update_statut_compte(session, {"phase": "envoi"})
        try:
            await client.send_message(USERNAME_MAITRE, f"✅ {session} a terminé son warm up !")
        except:
            pass

    score = get_score(session)
    emoji = "🟢" if score["dernier_statut"] == "sain" else "🟡" if score["dernier_statut"] == "attention" else "🔴" if score["dernier_statut"] == "restreint" else "⚫"
    print(f"  {emoji} Score {session} : {score['score']}/100")

    await client.disconnect()

# ─── MAIN ───
async def main():
    config = charger_config()
    if not config:
        print("❌ config.json introuvable !")
        return

    print("=" * 50)
    print(f"🤖 Démarrage — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 50)

    # File d'attente des réponses depuis le dashboard
    queue_file = "reply_queue.json"
    if os.path.exists(queue_file):
        with open(queue_file, "r") as f:
            queue = json.load(f)
        if queue:
            print(f"\n📬 {len(queue)} réponse(s) en attente")
            for account in config.get("comptes", []):
                if account.get("api_id") and account.get("api_hash"):
                    client = TelegramClient(account["session"], int(account["api_id"]), account["api_hash"])
                    try:
                        await client.start()
                        for item in queue:
                            try:
                                await client.send_message(item["username"], item["message"])
                                print(f"  ✅ Réponse → {item['username']}")
                                await asyncio.sleep(5)
                            except Exception as e:
                                print(f"  ❌ {e}")
                        await client.disconnect()
                        with open(queue_file, "w") as f:
                            json.dump([], f)
                    except Exception as e:
                        print(f"  ❌ {e}")
                    break

    # Warm up de chaque compte
    for account in config.get("comptes", []):
        if not account.get("api_id") or not account.get("api_hash"):
            continue
        session = account["session"]
        jours = jours_depuis_debut(session)
        print(f"\n📱 {session} — Jour {jours}")
        await phase_warmup(account, config, jours)
        await asyncio.sleep(5)

    crm = charger_crm()
    print("\n" + "=" * 50)
    print(f"📬 Invités : {len(charger_invites())} / {len(charger_contacts())}")
    print(f"💬 Réponses : {sum(1 for v in crm.values() if v.get('repondu'))}")
    print("✅ Terminé")
    print("=" * 50)

asyncio.run(main())
