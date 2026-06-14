import asyncio
import json
import random
import os
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError, PeerFloodError
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch

# ─────────────────────────────────────────
# CONFIGURATION — à remplir avec tes infos
# ─────────────────────────────────────────

ACCOUNTS = [
    {"api_id": 0000001, "api_hash": "HASH_COMPTE_1", "session": "compte1"},
    {"api_id": 0000002, "api_hash": "HASH_COMPTE_2", "session": "compte2"},
    {"api_id": 0000003, "api_hash": "HASH_COMPTE_3", "session": "compte3"},
    {"api_id": 0000004, "api_hash": "HASH_COMPTE_4", "session": "compte4"},
    {"api_id": 0000005, "api_hash": "HASH_COMPTE_5", "session": "compte5"},
]

# Groupes dont tu es membre (username ou lien)
GROUPES = [
    "@nom_groupe_1",
    "@nom_groupe_2",
    "https://t.me/nom_groupe_3",
]

CANAL_LIEN = "https://t.me/TON_CANAL"

MESSAGE = f"""Salut ! 👋

Je voulais t'inviter sur mon canal Telegram, j'y partage des trucs intéressants.

Rejoins-nous ici : {CANAL_LIEN}"""

# Limite d'envois par compte par jour
LIMITE_PAR_COMPTE = 5

# Délai entre chaque message (secondes)
DELAI_MIN = 60    # 1 minute
DELAI_MAX = 300   # 5 minutes

# Fichiers de données
FICHIER_CONTACTS     = "contacts.txt"
FICHIER_DEJA_INVITES = "deja_invites.json"

# ─────────────────────────────────────────
# SCRAPING DES MEMBRES DES GROUPES
# ─────────────────────────────────────────

async def scraper_membres(account):
    """Récupère tous les usernames des membres de tes groupes."""
    client = TelegramClient(account["session"], account["api_id"], account["api_hash"])
    await client.start()

    tous_les_membres = set()

    for groupe in GROUPES:
        try:
            print(f"  📥 Scraping du groupe {groupe}...")
            entity = await client.get_entity(groupe)
            offset = 0
            limit  = 100

            while True:
                participants = await client(GetParticipantsRequest(
                    entity,
                    ChannelParticipantsSearch(""),
                    offset=offset,
                    limit=limit,
                    hash=0
                ))
                if not participants.users:
                    break
                for user in participants.users:
                    if user.username and not user.bot:
                        tous_les_membres.add(f"@{user.username}")
                offset += len(participants.users)
                await asyncio.sleep(1)  # Pause pour ne pas flood

            print(f"  ✅ {groupe} — {len(tous_les_membres)} membres récupérés au total")

        except Exception as e:
            print(f"  ❌ Erreur sur {groupe} : {e}")

    await client.disconnect()
    return tous_les_membres

def sauvegarder_contacts(membres):
    """Ajoute les nouveaux membres dans contacts.txt sans doublon."""
    existants = set()
    if os.path.exists(FICHIER_CONTACTS):
        with open(FICHIER_CONTACTS, "r") as f:
            existants = set(line.strip() for line in f.readlines() if line.strip())

    nouveaux = membres - existants
    with open(FICHIER_CONTACTS, "a") as f:
        for m in nouveaux:
            f.write(m + "\n")

    print(f"\n📋 {len(nouveaux)} nouveaux contacts ajoutés ({len(existants) + len(nouveaux)} total)")

# ─────────────────────────────────────────
# LOGIQUE D'ENVOI
# ─────────────────────────────────────────

def charger_contacts():
    if not os.path.exists(FICHIER_CONTACTS):
        return []
    with open(FICHIER_CONTACTS, "r") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def charger_deja_invites():
    if not os.path.exists(FICHIER_DEJA_INVITES):
        return []
    with open(FICHIER_DEJA_INVITES, "r") as f:
        return json.load(f)

def sauvegarder_invite(username):
    deja = charger_deja_invites()
    if username not in deja:
        deja.append(username)
    with open(FICHIER_DEJA_INVITES, "w") as f:
        json.dump(deja, f)

def contacts_restants():
    tous = charger_contacts()
    deja = charger_deja_invites()
    restants = [c for c in tous if c not in deja]
    random.shuffle(restants)
    return restants

async def envoyer_avec_compte(account, contacts_a_envoyer):
    client = TelegramClient(account["session"], account["api_id"], account["api_hash"])
    await client.start()

    print(f"\n✅ Compte '{account['session']}' connecté — {len(contacts_a_envoyer)} messages à envoyer")

    for username in contacts_a_envoyer:
        try:
            await client.send_message(username, MESSAGE)
            sauvegarder_invite(username)
            print(f"  📨 Envoyé à {username} — {datetime.now().strftime('%H:%M:%S')}")

            delai = random.randint(DELAI_MIN, DELAI_MAX)
            print(f"  ⏳ Attente {delai}s...")
            await asyncio.sleep(delai)

        except FloodWaitError as e:
            print(f"  ⚠️  FloodWait — attente {e.seconds}s")
            await asyncio.sleep(e.seconds)

        except UserPrivacyRestrictedError:
            print(f"  🔒 {username} a désactivé les DM — ignoré")
            sauvegarder_invite(username)

        except PeerFloodError:
            print(f"  🚨 Trop de messages avec '{account['session']}' — arrêt de ce compte")
            break

        except Exception as e:
            print(f"  ❌ Erreur avec {username} : {e}")

    await client.disconnect()

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

async def main():
    # Étape 1 — Scraper les membres des groupes (avec le 1er compte)
    print("🔍 Récupération des membres de tes groupes...")
    membres = await scraper_membres(ACCOUNTS[0])
    sauvegarder_contacts(membres)

    # Étape 2 — Envoyer les invitations
    restants = contacts_restants()

    if not restants:
        print("\n✅ Tout le monde a déjà été invité !")
        return

    print(f"\n📨 {len(restants)} contacts à inviter aujourd'hui")

    # Répartir entre les 5 comptes
    idx = 0
    for account in ACCOUNTS:
        tranche = restants[idx:idx + LIMITE_PAR_COMPTE]
        if tranche:
            await envoyer_avec_compte(account, tranche)
        idx += LIMITE_PAR_COMPTE
        if idx >= len(restants):
            break

    print(f"\n🎉 Session terminée !")
    print(f"📊 Total invités : {len(charger_deja_invites())} / {len(charger_contacts())}")

if __name__ == "__main__":
    asyncio.run(main())
