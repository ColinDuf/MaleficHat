import discord
from discord import app_commands
import logging

from fonction_bdd import (
    get_guild,
    insert_guild,
    get_leaderboard_by_guild,
    insert_leaderboard,
    get_player_by_username,
    insert_leaderboard_member,
    delete_leaderboard_member,
    delete_leaderboard,
    get_leaderboard_data, username_autocomplete
)

# ─── /leaderboard ───────────────────────────────────────────────────────────────
@app_commands.command(
    name="leaderboard",
    description="Créer un nouveau salon pour le leaderboard de cette guilde"
)
@app_commands.describe(
    channel_name="Nom du salon à créer pour le leaderboard"
)
async def leaderboard_cmd(
        interaction: discord.Interaction,
        channel_name: str
):
    guild = interaction.guild
    if guild is None:
        return await interaction.response.send_message(
            "Impossible de récupérer le serveur.",
            ephemeral=True
        )

    # 1) Création du salon
    new_channel = await guild.create_text_channel(name=channel_name)
    guild_id = guild.id

    # 2) Enregistrement du salon comme channel de leaderboard
    insert_guild(guild_id, new_channel.id, 0)

    lb_id = get_leaderboard_by_guild(guild_id)
    if lb_id is None:
        lb_id = insert_leaderboard(guild_id)

    await update_leaderboard_message(new_channel.id, interaction.client, guild_id)

    await interaction.response.send_message(
        f"✅ Leaderboard créé dans {new_channel.mention}.",
        ephemeral=True
    )
    return None


@app_commands.command(
    name="addleaderboard",
    description="Ajouter un joueur déjà enregistré au leaderboard"
)
@app_commands.describe(
    username="Pseudo du joueur (format: USERNAME#TAG)"
)
@app_commands.autocomplete(username=username_autocomplete)
async def add_leaderboard_cmd(
        interaction: discord.Interaction,
        username: str
):
    guild_id = interaction.guild.id
    username = username.upper()

    # Vérifie que le joueur est enregistr�
    player = get_player_by_username(username, guild_id)
    if not player:
        return await interaction.response.send_message(
            f"❌ Le joueur {username} n'est pas enregistré ici.",
            ephemeral=True
        )
    puuid = player[0]

    # Récupère l'ID du leaderboard (ligne dédiée)
    lb_id = get_leaderboard_by_guild(guild_id)
    if lb_id is None:
        return await interaction.response.send_message(
            "❌ Aucune configuration de leaderboard trouvée. Lancez d'abord `/leaderboard`.",
            ephemeral=True
        )

    # Insertion en BDD
    insert_leaderboard_member(lb_id, puuid)
    logging.info(f"[BDD] Added {puuid} to leaderboard #{lb_id}")

    channel_id = get_guild(guild_id)[1]
    await update_leaderboard_message(channel_id, interaction.client, guild_id)

    await interaction.response.send_message(
        f"✅ Joueur **{username}** ajouté au leaderboard.",
        ephemeral=True
    )

# ─── /removeleaderboard ─────────────────────────────────────────────────────────
@app_commands.command(
    name="removeleaderboard",
    description="Retirer un joueur du leaderboard"
)
@app_commands.describe(
    username="Pseudo du joueur (format: USERNAME#TAG)"
)

@app_commands.autocomplete(username=username_autocomplete)
async def remove_leaderboard_cmd(
        interaction: discord.Interaction,
        username: str
):
    guild_id = interaction.guild.id
    username = username.upper()

    # Vérifie que le joueur est enregistré
    player = get_player_by_username(username, guild_id)
    if not player:
        return await interaction.response.send_message(
            f"❌ Le joueur {username} n'est pas enregistré ici.",
            ephemeral=True
        )
    puuid = player[0]

    lb_id = get_leaderboard_by_guild(guild_id)
    if lb_id is None:
        return await interaction.response.send_message(
            "❌ Aucune configuration de leaderboard trouvée.",
            ephemeral=True
        )

    delete_leaderboard_member(lb_id, puuid)
    logging.info(f"[BDD] Removed {puuid} from leaderboard #{lb_id}")

    channel_id = get_guild(guild_id)[1]
    await update_leaderboard_message(channel_id, interaction.client, guild_id)

    await interaction.response.send_message(
        f"✅ Joueur **{username}** retiré du leaderboard.",
        ephemeral=True
    )

# ─── Fonction de mise à jour d’embed ────────────────────────────────────────────
async def update_leaderboard_message(channel_id: int, bot: discord.Client, guild_id: int):
    """
    Met à jour ou envoie un message texte monospace contenant
    le classement trié des joueurs du leaderboard.
    """
    # 1) Récupère le leaderboard_id et les données
    lb_id = get_leaderboard_by_guild(guild_id)
    if lb_id is None:
        return
    rows = get_leaderboard_data(lb_id, guild_id)
    # rows = List[ (username, tier, rank, current_lp, lp24h, lp7d) ]

    # 1.5) Tri du classement : catégorie → division → LP courant
    rank_order = [
        'IRON', 'BRONZE', 'SILVER', 'GOLD',
        'PLATINUM', 'EMERALD', 'DIAMOND', 'MASTER',
        'GRANDMASTER', 'CHALLENGER'
    ]
    tier_order = ['IV', 'III', 'II', 'I']  # I = meilleur

    def rank_idx(val: str | None) -> int:
        return rank_order.index(val) if val in rank_order else -1

    def tier_idx(val: str | None) -> int:
        return tier_order.index(val) if val in tier_order else -1

    rows.sort(key=lambda x: (
        -rank_idx(x[2]),    # meilleur rang en premier, "Unranked" en dernier
        -tier_idx(x[1]),    # meilleure division en premier
        -(x[3] if x[3] is not None else float('-inf'))
    ))

    # 2) Prépare header et séparateur
    header    = "Username                      | Rank              | LP (24h) | LP (7d)"
    separator = "-" * len(header)

    # 3) Calcule la largeur de chaque colonne à partir du header
    parts  = header.split("|")
    user_w = len(parts[0])
    rank_w = len(parts[1])
    lp24_w = len(parts[2])
    lp7_w  = len(parts[3])

    # 4) Construit les lignes du tableau
    lines = [header, separator]
    for username, tier, rank_val, current_lp, lp24h, lp7d in rows:
        # Affiche "GOLD I 30 LP" par exemple
        rank_display = f"{rank_val} {tier} {current_lp} LP" if rank_val and tier else "Unranked"
        user_col = username.ljust(user_w)
        rank_col = rank_display.ljust(rank_w)
        lp24_col = str(lp24h).rjust(lp24_w)
        lp7_col  = str(lp7d).rjust(lp7_w)
        lines.append(f"{user_col}|{rank_col}|{lp24_col}|{lp7_col}")

    # 5) Assemble le bloc de code Markdown
    table = "```" + "\n".join(lines) + "```"

    # 6) Recherche un ancien message à éditer
    guild_obj = bot.get_guild(guild_id)
    if guild_obj is None:
        logging.error(
            f"[update_leaderboard_message] Guild with id {guild_id} not found"
        )
        return

    channel = guild_obj.get_channel(channel_id)
    if channel is None:
        logging.error(
            f"[update_leaderboard_message] Channel with id {channel_id} not found"
        )
        delete_leaderboard(guild_id)
        logging.info(
            f"[update_leaderboard_message] Dropped leaderboard for guild {guild_id}" \
            f" because channel {channel_id} is missing"
        )
        return

    async for msg in channel.history(limit=50):
        if (
                msg.author == guild_obj.me
                and msg.content.startswith("```")
                and header in msg.content
        ):
            await msg.edit(content=table)
            return

    # 7) Sinon, envoie un nouveau message
    try:
        await channel.send(table)
    except discord.DiscordException as e:
        logging.error(f"[update_leaderboard_message] Failed to send leaderboard: {e}")


def setup_tree(tree_obj: app_commands.CommandTree):
    tree_obj.add_command(leaderboard_cmd)
    tree_obj.add_command(add_leaderboard_cmd)
    tree_obj.add_command(remove_leaderboard_cmd)
