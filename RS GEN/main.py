import discord
from discord import app_commands
import sqlite3
import random
import string

TOKEN = "dQw4w9WgXcQ:djEwX8+s6NK0Sg0u7CSIFl1U9x67h3rOlqtKNgkYkz3AonYttJ1OGPUL4iH0me+MB/xvTmy0mCP6ekUb2fbSFSQsfV3sxGmwZ7yUkE9Jz+8gUJJv4paz8MyShznyUPwr3ZNvEnUyrg=="  # Remplacez par votre vrai token Discord
intents = discord.Intents.default()
intents.members = True  # Activer l'intention pour gérer les rôles des membres
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Connexion à la base de données SQLite
db = sqlite3.connect("database.db")
cursor = db.cursor()

# Création des tables si elles n'existent pas
cursor.execute("""
CREATE TABLE IF NOT EXISTS keys (
    key TEXT PRIMARY KEY,
    duration INTEGER,
    used_by TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    password TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS nitro_codes (
    code TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS admins (
    user_id TEXT PRIMARY KEY
)
""")
db.commit()

user_timers = {}

def is_admin(user_id):
    cursor.execute("SELECT * FROM admins WHERE user_id = ?", (str(user_id),))
    return cursor.fetchone() is not None

@client.event
async def on_ready():
    await tree.sync()
    print(f"Connecté en tant que {client.user}")

def create_embed(title, description, color=discord.Color.blue()):
    return discord.Embed(title=title, description=description, color=color)

@tree.command(name="addstock", description="Ajoute du stock de comptes (Admin uniquement)")
async def addstock(interaction: discord.Interaction, service: str, fichier: discord.Attachment):
    if is_admin(interaction.user.id):
        services = ["RS", "NB"]

        if service not in services:
            embed = create_embed("Erreur", f"Service non valide. Choisissez parmi : {', '.join(services)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        file_path = f"./{fichier.filename}"
        await fichier.save(file_path)

        if service == "RS":
            with open(file_path, "r") as file:
                for line in file:
                    line = line.strip()
                    if not line:  # Ignorer les lignes vides
                        continue

                    # Vérification du format [Mail| email : Psswrt : | password | link :]
                    if line.startswith("[Mail|") and line.endswith("| link :]"):
                        try:
                            # Extraire les parties de la ligne
                            parts = line[6:-8].split(" : ")  # Retirer [Mail| et | link :]
                            if len(parts) == 3:
                                email = parts[0].strip()
                                password = parts[1].strip()
                                link = parts[2].strip()

                                # Insertion dans la base de données
                                cursor.execute("INSERT INTO accounts (username, password) VALUES (?, ?)", (email, password))
                            else:
                                print(f"Ligne mal formattée (ignorée) : {line}")
                        except Exception as e:
                            print(f"Erreur lors du traitement de la ligne : {line}, erreur : {str(e)}")
                    else:
                        print(f"Ligne mal formattée (ignorée) : {line}")

        elif service == "NB":
            with open(file_path, "r") as file:
                for line in file:
                    code = line.strip() 
                    cursor.execute("INSERT INTO nitro_codes (code) VALUES (?)", (code,))

        db.commit()
        await interaction.response.send_message(embed=create_embed("Succès", f"Stock de {service} a été ajouté."), ephemeral=True)
    else:
        embed = create_embed("Erreur", "Seul les administrateurs peuvent utiliser cette commande.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="service", description="Affiche les services disponibles et leur stock")
async def service(interaction: discord.Interaction):
    # Récupérer le stock des comptes Rockstar
    cursor.execute("SELECT COUNT(*) FROM accounts")
    rs_stock = cursor.fetchone()[0]

    # Récupérer le stock des codes Nitro
    cursor.execute("SELECT COUNT(*) FROM nitro_codes")
    nb_stock = cursor.fetchone()[0]

    # Créer l'embed avec les informations
    embed = create_embed("Services et Stock", "")
    embed.add_field(name="Rockstar Accounts", value=f"Stock: {rs_stock}", inline=False)
    embed.add_field(name="Nitro Codes", value=f"Stock: {nb_stock}", inline=False)

    await interaction.response.send_message(embed=embed)

@tree.command(name="licence", description="Affiche votre propre clé")
async def licence(interaction: discord.Interaction):
    cursor.execute("SELECT key FROM keys WHERE used_by = ?", (str(interaction.user.id),))
    result = cursor.fetchone()

    if result:
        embed = create_embed("Votre Clé", f"**Clé:** {result[0]}")
    else:
        embed = create_embed("Erreur", "Vous n'avez pas de clé activée.")

    await interaction.response.send_message(embed=embed)

@tree.command(name="gen", description="Génère un compte ou un code")
async def gen(interaction: discord.Interaction, service: str):
    services = ["RS", "NB"]

    if service not in services:
        embed = create_embed("Erreur", f"Service non valide. Choisissez parmi : {', '.join(services)}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    user_id = str(interaction.user.id)
    last_gen_time = user_timers.get(user_id, 0)
    current_time = discord.utils.utcnow().timestamp()

    if current_time - last_gen_time < 1500:  # 25 minutes
        wait_time = 1500 - (current_time - last_gen_time)
        embed = create_embed("Attendez", f"Vous devez attendre encore {int(wait_time / 60)} minutes avant de générer à nouveau.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    user_timers[user_id] = current_time
    embed = create_embed("Génération de Compte", "")

    # Vérification de la clé
    cursor.execute("SELECT key FROM keys WHERE used_by = ?", (user_id,))
    if not cursor.fetchone():  # Si l'utilisateur n'a pas de clé activée
        embed.description = "Vous devez d'abord activer une clé avec /redeem."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if service == "RS":
        cursor.execute("SELECT id, username, password FROM accounts ORDER BY RANDOM() LIMIT 1")
        account = cursor.fetchone()

        if account:
            account_id = account[0]
            pm_embed = create_embed("Votre Compte Rockstar", 
                                    description=f"**Utilisateur :** {account[1]}\n**Mot de passe :** {account[2]}")
            pm_embed.set_footer(text="Merci d'avoir utilisé le Bot Gen!")

            try:
                await interaction.user.send(embed=pm_embed)
                embed.description = "Votre compte Rockstar a été envoyé en message privé !"
                cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
                db.commit()
            except discord.Forbidden:
                embed.description = "Je ne peux pas vous envoyer de message privé. Veuillez vérifier vos paramètres de confidentialité."

        else:
            embed.description = "Aucun compte disponible."

    elif service == "NB":
        cursor.execute("SELECT code FROM nitro_codes ORDER BY RANDOM() LIMIT 1")
        code = cursor.fetchone()

        if code:
            pm_embed = create_embed("Votre Code Nitro Boost", 
                                    description=f"**Code :** {code[0]}")
            pm_embed.set_footer(text="Merci d'avoir utilisé le Bot Gen!")

            try:
                await interaction.user.send(embed=pm_embed)
                embed.description = "Votre code Nitro Boost a été envoyé en message privé !"
                cursor.execute("DELETE FROM nitro_codes WHERE code = ?", (code[0],))
                db.commit()
            except discord.Forbidden:
                embed.description = "Je ne peux pas vous envoyer de message privé. Veuillez vérifier vos paramètres de confidentialité."
        else:
            embed.description = "Aucun code Nitro Boost disponible."

    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="redeem", description="Lie une clé à votre compte")
async def redeem(interaction: discord.Interaction, key: str):
    cursor.execute("SELECT * FROM keys WHERE key = ? AND used_by IS NULL", (key,))
    result = cursor.fetchone()

    if result:
        cursor.execute("UPDATE keys SET used_by = ? WHERE key = ?", (str(interaction.user.id), key))
        db.commit()
        await interaction.response.send_message(embed=create_embed("Clé activée", "Votre clé a été activée avec succès."), ephemeral=True)
    else:
        await interaction.response.send_message(embed=create_embed("Erreur", "Clé invalide ou déjà utilisée."), ephemeral=True)

@tree.command(name="create", description="Crée de nouvelles clés (Admin uniquement)")
async def create(interaction: discord.Interaction, duration: int, num_keys: int):
    if is_admin(interaction.user.id):
        new_keys = [generate_key(duration) for _ in range(num_keys)]
        for key in new_keys:
            cursor.execute("INSERT INTO keys (key, duration) VALUES (?, ?)", (key, duration))

        db.commit()

        keys_list = "\n".join(new_keys)
        embed = create_embed("Clés créées", f"{num_keys} nouvelles clés ont été générées :\n{keys_list}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = create_embed("Erreur", "Seul les administrateurs peuvent utiliser cette commande.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="addadmin", description="Ajoute un administrateur")
async def addadmin(interaction: discord.Interaction, user: discord.User, password: str):
    if password == "xyzw2600":
        if not is_admin(user.id):
            cursor.execute("INSERT OR REPLACE INTO admins (user_id) VALUES (?)", (user.id,))
            db.commit()
            await interaction.response.send_message(embed=create_embed("Succès", f"{user.name} a été ajouté en tant qu'administrateur."), ephemeral=True)
        else:
            await interaction.response.send_message(embed=create_embed("Erreur", f"{user.name} est déjà un administrateur."), ephemeral=True)
    else:
        await interaction.response.send_message(embed=create_embed("Erreur", "Mot de passe incorrect. Utilisez 'xyzw2600'."), ephemeral=True)

@tree.command(name="delete", description="Supprime une clé (Admin uniquement)")
async def delete(interaction: discord.Interaction, key: str):
    if is_admin(interaction.user.id):
        cursor.execute("DELETE FROM keys WHERE key = ?", (key,))
        db.commit()
        await interaction.response.send_message(embed=create_embed("Succès", "La clé a été supprimée."), ephemeral=True)
    else:
        embed = create_embed("Erreur", "Seul les administrateurs peuvent utiliser cette commande.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="getinfo", description="Affiche les infos d'un utilisateur (Admin uniquement)")
async def getinfo(interaction: discord.Interaction, user: discord.User):
    if is_admin(interaction.user.id):
        cursor.execute("SELECT * FROM keys WHERE used_by = ?", (str(user.id),))
        keys = cursor.fetchall()
        if keys:
            keys_list = "\n".join([key[0] for key in keys])
            embed = create_embed("Infos de l'utilisateur", f"Clés utilisées par {user.name} :\n{keys_list}")
        else:
            embed = create_embed("Infos de l'utilisateur", f"Aucune clé utilisée par {user.name}.")

        await interaction.response.send_message(embed=embed)
    else:
        embed = create_embed("Erreur", "Seul les administrateurs peuvent utiliser cette commande.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="listadmin", description="Affiche la liste des administrateurs")
async def listadmin(interaction: discord.Interaction):
    if is_admin(interaction.user.id):
        cursor.execute("SELECT user_id FROM admins")
        admins = cursor.fetchall()
        if admins:
            admin_list = "\n".join([str(admin[0]) for admin in admins])
            embed = create_embed("Liste des Administrateurs", f"Les administrateurs sont :\n{admin_list}")
        else:
            embed = create_embed("Liste des Administrateurs", "Aucun administrateur trouvé.")

        await interaction.response.send_message(embed=embed)
    else:
        embed = create_embed("Erreur", "Seul les administrateurs peuvent utiliser cette commande.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="help", description="Affiche l'aide pour chaque commande")
async def help_command(interaction: discord.Interaction):
    help_text = """
**Commandes disponibles :**

/gen [service] : Génère un compte ou un code.
- Pour un compte Rockstar : /gen RS
- Pour un code Nitro Boost : /gen NB

/redeem <clé> : Lie une clé à votre compte.

/create <durée> <nombre> : Crée de nouvelles clés (Admin uniquement).

/addstock <service> <fichier> : Ajoute du stock de comptes ou de codes (Admin uniquement).

/delete <clé> : Supprime une clé (Admin uniquement).

/getinfo <utilisateur> : Affiche les infos d'un utilisateur (Admin uniquement).

/listadmin : Affiche la liste des administrateurs (Admin uniquement).

/help : Affiche cette aide.

/addadmin <utilisateur> <mot de passe> : Ajoute un administrateur (Avec mot de passe).

/removetimer <user_id> : Retire le timer de génération pour un utilisateur (Admin uniquement).

/licence : Affiche votre propre clé.
"""
    embed = create_embed("Aide", help_text)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="removetimer", description="Retire le timer de génération d'un utilisateur (Admin uniquement)")
async def removetimer(interaction: discord.Interaction, user_id: str):
    if is_admin(interaction.user.id):
        if int(user_id) == interaction.user.id:
            await interaction.response.send_message(embed=create_embed("Erreur", "Vous ne pouvez pas retirer votre propre timer."), ephemeral=True)
            return

        if user_id in user_timers:
            del user_timers[user_id]
            await interaction.response.send_message(embed=create_embed("Succès", f"Le timer de génération de l'utilisateur {user_id} a été retiré."), ephemeral=True)
        else:
            await interaction.response.send_message(embed=create_embed("Erreur", f"Aucun timer trouvé pour l'utilisateur {user_id}."), ephemeral=True)
    else:
        embed = create_embed("Erreur", "Seul les administrateurs peuvent utiliser cette commande.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

def generate_key(duration):
    prefix = ""
    if duration <= 2:
        prefix = "DAY-"
    elif duration <= 30:
        prefix = "MONTHS-"
    elif duration >= 365:
        prefix = "LIFETIME-"

    letters = ''.join(random.choices(string.ascii_uppercase, k=4))
    numbers = ''.join(random.choices(string.digits, k=4))
    extra = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

    return f"{prefix}{letters}-{numbers}-{extra}"

client.run("MTMzMDI5NzIxNzM4MjA5MjkxMQ.GvEY7l.1JfFkKe8f2JVeGFrQLxWrLfR9B7FrXxWjHTmJk")