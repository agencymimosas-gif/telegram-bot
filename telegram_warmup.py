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

def charger_config():
    if not os.path.exists(FICHIER_CONFIG):
        return {}
    with open(FICHIER_CONFIG, "r") as f:
        return json.load(f)

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
        return 0  # Pas de DM les 7 premiers jours
    elif jours < 14:
        return config.get("limite_semaine_1", 3)   # Semaine 2 → 3/jour
    elif jours < 21:
        return config.get("limite_semaine_2", 10)  # Semaine 3 → 10/jour
    else:
        return config.get("limite_semaine_3", 20)  # Semaine 4+ → 20/jour

# ─── COMPTE MAÎTRE ───
async def compte_maitre_envoie(config):
    maitre = config.get("compte_maitre", {})
    if not maitre.get("api_id") or not maitre.get("api_hash"):
        print("⚠️ Compte maître non configuré — skipped")
        return

    client = TelegramClient(maitre.get("session", "compte_maitre"), int(maitre["api_id"]), maitre["api_hash"])
    await client.start()
    print(f"\n👑 COMPTE MAÎTRE — Envoi vers les comptes")

    messages_maitre = config.get("messages_maitre", ["Ça va ?", "T'es là ?", "Quoi de neuf ?"])

    for compte in config.get("comptes", []):
        if not compte.get("tel"):
            continue
        nb = random.randint(3, 4)
        msgs = random.sample(messages_maitre, min(nb, len(messages_maitre)))
        for msg in msgs:
            try:
                await client.send_message(compte["tel"], msg)
                print(f"  💬 → {compte['session']} : '{msg}'")
                await asyncio.sleep(random.randint(30, 90))
            except Exception as e:
                print(f"  ❌ {compte['session']} : {e}")
        await asyncio.sleep(random.randint(60, 120))

    await client.disconnect()

# ─── SCRAPING MEMBRES ───
async def scraper_membres(client, config):
    membres = set()
    admins = set()
    groupes = config.get("groupes", [])

    for groupe in groupes:
        try:
            entity = await client.get_entity(groupe)

            # Récupère les admins pour les exclure
            admins_result = await client(
                __import__('telethon.tl.functions.channels', fromlist=['GetParticipantsRequest']).GetParticipantsRequest(
                    entity, ChannelParticipantsAdmins(), offset=0, limit=200, hash=0
                )
            )
            for user in admins_result.users:
                if user.username:
                    admins.add(f"@{user.username}")
                admins.add(str(user.id))

            # Récupère membres actifs via messages
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

# ─── WARM UP ───
async def phase_warmup(account, config, jours):
    session = account["session"]
    client = TelegramClient(session, int(account["api_id"]), account["api_hash"])
    await client.start()

    print(f"\n🔥 [{session}] WARM UP — Jour {jours}")

    # Rejoindre les groupes
    for groupe in config.get("groupes", []):
        try:
            await client(JoinChannelRequest(groupe))
            print(f"  ✅ Rejoint {groupe}")
            await asyncio.sleep(random.randint(5, 15))
        except Exception as e:
            print(f"  ℹ️ {groupe} : {e}")

    # Messages aux amis
    amis = config.get("amis", [])
    messages_amis = config.get("messages_amis", ["Ça va ?"])
    if amis:
        amis_du_jour = random.sample(amis, min(2, len(amis)))
        for ami in amis_du_jour:
            try:
                await client.send_message(ami, random.choice(messages_amis))
                print(f"  💬 [AMI] → {ami}")
                await asyncio.sleep(random.randint(120, 300))
            except Exception as e:
                print(f"  ❌ {ami} : {e}")

    # Message dans groupe d'amis
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

    # Réactions dans les groupes
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

    # DM progressifs selon les jours
    limite = limite_du_jour(jours, config)
    if limite > 0:
        print(f"  📨 Jour {jours} — envoi de {limite} DM autorisés")

        # Scrape les membres si pas encore fait
        membres = await scraper_membres(client, config)
        sauvegarder_contacts(membres)

        contacts = charger_contacts()
        invites = charger_invites()
        restants = [c for c in contacts if c not in invites]
        random.shuffle(restants)
        a_envoyer = restants[:limite]

        messages_invitation = config.get("messages_invitation", ["Salut ! Rejoins mon canal : {canal}"])
        canal = config.get("canal_lien", "")
        stats = charger_stats()

        for username in a_envoyer:
            try:
                msg = random.choice(messages_invitation).replace("{canal}", canal)
                await client.send_message(username, msg)
                sauvegarder_invite(username)
                stats["envoyes"] += 1
                sauvegarder_stats(stats)
                print(f"  ✅ Invité : {username}")
                await asyncio.sleep(random.randint(180, 600))
            except FloodWaitError as e:
                print(f"  ⚠️ FloodWait {e.seconds}s")
                await asyncio.sleep(e.seconds)
            except UserPrivacyRestrictedError:
                sauvegarder_invite(username)
                print(f"  🔒 DM désactivés : {username}")
            except Exception as e:
                print(f"  ❌ {username} : {e}")
                if "PeerFlood" in str(e):
                    print(f"  🚨 {session} restreint !")
                    break
    else:
        print(f"  ⏳ Jour {jours} — pas encore de DM (commence jour 7)")

    await client.disconnect()

# ─── MAIN ───
async def main():
    config = charger_config()
    if not config:
        print("❌ Fichier config.json introuvable — configure d'abord le dashboard !")
        return

    print("=" * 50)
    print(f"🤖 Démarrage — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 50)

    # Compte maître envoie aux comptes
    await compte_maitre_envoie(config)

    # Chaque compte fait son warm up progressif
    for account in config.get("comptes", []):
        if not account.get("api_id") or not account.get("api_hash"):
            print(f"⚠️ {account.get('session')} non configuré — skipped")
            continue

        session = account["session"]
        jours = jours_depuis_debut(session)

        print(f"\n📱 {session} — Jour {jours}")
        await phase_warmup(account, config, jours)
        await asyncio.sleep(5)

    statut = charger_statut()
    print("\n" + "=" * 50)
    print(f"📬 Invités : {len(charger_invites())} / {len(charger_contacts())}")
    print("✅ Session terminée")
    print("=" * 50)

asyncio.run(main())