import asyncio
import json
import random
import os
from datetime import datetime, timedelta
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
            "date_lecture": None,
            "lu": False,
            "repondu": False,
            "messages_recus": [],
            "nb_relances": 0,
            "derniere_relance": None,
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
    if jours < 7:
        return 0
    elif jours < 14:
        return config.get("limite_semaine_1", 3)
    elif jours < 21:
        return config.get("limite_semaine_2", 10)
    else:
        return config.get("limite_semaine_3", 20)

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
async def verifier_crm(client, session):
    """Vérifie les messages lus et les réponses pour chaque personne invitée."""
    crm = charger_crm()
    stats = charger_stats()
    nouvelles_reponses = 0

    print(f"  🔍 Vérification CRM...")

    for username, data in crm.items():
        if data.get("repondu"):
            continue
        try:
            entity = await client.get_entity(username)
            messages = await client.get_messages(entity, limit=10)

            for msg in messages:
                # Message envoyé par nous → vérifier s'il est lu
                if msg.out and not data.get("lu"):
                    if msg.is_private and hasattr(msg, 'read_outbox_max_id') and msg.read_outbox_max_id:
                        update_crm(username, {"lu": True, "date_lecture": datetime.now().isoformat(), "statut": "vu"})
                        stats["vus"] += 1
                        print(f"  👁️ Message lu par {username}")

                # Message reçu de leur part → réponse détectée
                if not msg.out and not data.get("repondu"):
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
        except Exception as e:
            pass

    sauvegarder_stats(stats)
    if nouvelles_reponses > 0:
        print(f"  🎉 {nouvelles_reponses} nouvelles réponses !")
    return nouvelles_reponses

# ─── RELANCES INTELLIGENTES ───
async def envoyer_relances(client, session, config):
    """Envoie des relances aux personnes qui n'ont pas répondu après 7 jours."""
    crm = charger_crm()
    maintenant = datetime.now()
    relances_envoyees = 0

    messages_relance_pas_vu = config.get("messages_relance_pas_vu", [
        "Hé ! Tu as vu mon message ? 👀",
        "Yo, t'as loupé ça 👉 {canal}",
        "Au cas où t'aurais pas vu → {canal}"
    ])

    messages_relance_vu = config.get("messages_relance_vu", [
        "Tu as eu le temps de regarder ? {canal}",
        "Toujours intéressé ? → {canal}",
        "Hésite pas à rejoindre si t'as pas encore eu le temps ! {canal}"
    ])

    canal = config.get("canal_lien", "")

    for username, data in crm.items():
        if data.get("repondu") or data.get("nb_relances", 0) >= 2:
            continue

        date_invitation = datetime.fromisoformat(data.get("date_invitation", maintenant.isoformat()))
        jours_passes = (maintenant - date_invitation).days

        derniere_relance = data.get("derniere_relance")
        if derniere_relance:
            jours_depuis_relance = (maintenant - datetime.fromisoformat(derniere_relance)).days
            if jours_depuis_relance < 7:
                continue

        if jours_passes >= 7:
            try:
                lu = data.get("lu", False)
                if lu:
                    msg = random.choice(messages_relance_vu).replace("{canal}", canal)
                else:
                    msg = random.choice(messages_relance_pas_vu).replace("{canal}", canal)

                await client.send_message(username, msg)
                update_crm(username, {
                    "nb_relances": data.get("nb_relances", 0) + 1,
                    "derniere_relance": maintenant.isoformat(),
                    "statut": "relance"
                })
                relances_envoyees += 1
                print(f"  🔄 Relance {'(vu)' if lu else '(pas vu)'} → {username}")
                await asyncio.sleep(random.randint(60, 180))

            except Exception as e:
                print(f"  ❌ Relance {username} : {e}")

    if relances_envoyees > 0:
        print(f"  ✅ {relances_envoyees} relances envoyées")

# ─── WARMUP ───
async def phase_warmup(account, config, jours):
    session = account["session"]
    client = TelegramClient(session, int(account["api_id"]), account["api_hash"])

    try:
        await client.start()
    except Exception as e:
        print(f"  🚨 [{session}] Impossible de se connecter : {e}")
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
    nb_messages = random.randint(2, 4)
    msgs_choisis = random.sample(messages_maitre, min(nb_messages, len(messages_maitre)))
    for msg in msgs_choisis:
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
            print(f"  ❌ Erreur envoi maître : {e}")

    # 3. Messages aux amis
    amis = config.get("amis", [])
    messages_amis = config.get("messages_amis", ["Ça va ?"])
    if amis:
        amis_du_jour = random.sample(amis, min(2, len(amis)))
        for ami in amis_du_jour:
            try:
                await client.send_message(ami, random.choice(messages_amis))
                update_score(session, "ok")
                print(f"  💬 [AMI] → {ami}")
                await asyncio.sleep(random.randint(120, 300))
            except Exception as e:
                print(f"  ❌ {ami} : {e}")

    # 4. Message dans groupe d'amis
    groupes_amis = config.get("groupes_amis", [])
    messages_groupes = config.get("messages_groupes", [])
    if groupes_amis and messages_groupes:
        try:
            groupe = random.choice(groupes_amis)
            entity = await client.get_entity(groupe)
            await client.send_message(entity, random.choice(messages_groupes))
            print(f"  💬 [GROUPE] → {groupe}")
            await asyncio.sleep(random.randint(60, 180))
        except Exception as e:
            print(f"  ❌ groupe amis : {e}")

    # 5. Réactions
    for groupe in config.get("groupes", [])[:2]:
        try:
            entity = await client.get_entity(groupe)
            messages = await client.get_messages(entity, limit=10)
            if messages:
                msg = random.choice(messages)
                await client.send_reaction(entity, msg.id, random.choice(["👍", "❤️", "🔥", "😂"]))
                print(f"  ❤️ Réaction dans {groupe}")
                await asyncio.sleep(random.randint(10, 30))
        except Exception as e:
            print(f"  ❌ réaction : {e}")

    # 6. DM progressifs
    limite = limite_du_jour(jours, config)
    if limite > 0:
        score = get_score(session)
        if score["dernier_statut"] in ["restreint", "banni"]:
            print(f"  🚫 [{session}] Score trop bas — DM suspendus")
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
                update_crm(username, {
                    "compte_utilisé": session,
                    "statut": "invite"
                })
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

        # Vérification CRM + relances
        await verifier_crm(client, session)
        await envoyer_relances(client, session, config)

    else:
        print(f"  ⏳ Jour {jours} — DM commencent au jour 7")

    # 7. Passage en phase envoi
    duree = config.get("duree_warmup", 21)
    if jours >= duree:
        print(f"\n🎉 [{session}] Warm up terminé !")
        update_statut_compte(session, {"phase": "envoi"})
        try:
            await client.send_message(USERNAME_MAITRE, f"✅ {session} a terminé son warm up !")
        except:
            pass

    score = get_score(session)
    emoji = "🟢" if score["dernier_statut"] == "sain" else "🟡" if score["dernier_statut"] == "attention" else "🔴" if score["dernier_statut"] == "restreint" else "⚫"
    print(f"  {emoji} Score {session} : {score['score']}/100 — {score['dernier_statut'].upper()}")

    await client.disconnect()

# ─── MAIN ───
async def main():
    config = charger_config()
    if not config:
        print("❌ Fichier config.json introuvable !")
        return

    print("=" * 50)
    print(f"🤖 Démarrage — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 50)

    # Traiter la file d'attente des réponses
    queue_file = "reply_queue.json"
    if os.path.exists(queue_file):
        with open(queue_file, "r") as f:
            queue = json.load(f)

        if queue:
            print(f"\n📬 {len(queue)} réponse(s) en attente à envoyer")
            # Utiliser le premier compte disponible
            for account in config.get("comptes", []):
                if account.get("api_id") and account.get("api_hash"):
                    client = TelegramClient(account["session"], int(account["api_id"]), account["api_hash"])
                    try:
                        await client.start()
                        for item in queue:
                            try:
                                await client.send_message(item["username"], item["message"])
                                print(f"  ✅ Réponse envoyée à {item['username']}")
                                await asyncio.sleep(5)
                            except Exception as e:
                                print(f"  ❌ Erreur réponse {item['username']} : {e}")
                        await client.disconnect()
                        # Vider la file
                        with open(queue_file, "w") as f:
                            json.dump([], f)
                    except Exception as e:
                        print(f"  ❌ Impossible d'envoyer les réponses : {e}")
                    break

    for account in config.get("comptes", []):
        if not account.get("api_id") or not account.get("api_hash"):
            continue

        session = account["session"]
        jours = jours_depuis_debut(session)
        print(f"\n📱 {session} — Jour {jours}")
        await phase_warmup(account, config, jours)
        await asyncio.sleep(5)

    crm = charger_crm()
    reponses = sum(1 for v in crm.values() if v.get("repondu"))
    relances = sum(1 for v in crm.values() if v.get("nb_relances", 0) > 0)

    print("\n" + "=" * 50)
    print(f"📬 Invités : {len(charger_invites())} / {len(charger_contacts())}")
    print(f"💬 Réponses reçues : {reponses}")
    print(f"🔄 Relances envoyées : {relances}")
    print("✅ Session terminée")
    print("=" * 50)

asyncio.run(main())
