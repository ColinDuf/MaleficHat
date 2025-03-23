import discord
from discord import app_commands
import logging

from fonction_bdd import (
    get_guild,
    get_leaderboard_data,
    insert_guild,
    get_player_by_username, insert_leaderboard_member,
    # update_registration is utilisé dans d'autres parties, mais pour le leaderboard, on utilise notre nouvelle table
)
# On importera localement les fonctions d'insertion/suppression dans leaderboard_members pour éviter les cycles.
# Importez l'objet global "tree" et "client" depuis bot.py, si nécessaire


@app_commands.command(name="leaderboard", description="Créer un leaderboard dans un nouveau channel")
@app_commands.describe(channel_name="Le nom du nouveau channel pour le leaderboard")
async def leaderboard(interaction: discord.Interaction, channel_name: str):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("Impossible de récupérer le serveur.", ephemeral=True)
        return

    # Créer le nouveau channel pour le leaderboard
    new_channel = await guild.create_text_channel(name=channel_name)
    guild_id = str(guild.id)

    # Insérer le channel dans la BDD (la table 'guilds' stocke ici l'ID du channel du leaderboard)
    insert_guild(guild_id, str(new_channel.id))
    # Met à jour l'embed du leaderboard en passant le nouveau channel comme leaderboard_id
    await update_leaderboard_embed(new_channel.id, interaction.client, guild_id)

    await interaction.response.send_message(f"Leaderboard créé dans {new_channel.mention}.", ephemeral=True)

@app_commands.command(name="addleaderboard", description="Ajouter un joueur au leaderboard")
@app_commands.describe(username="Le nom du joueur (format: USERNAME#TAG)")
async def addleaderboard(interaction: discord.Interaction, username: str):
    guild_id = str(interaction.guild.id)
    username = username.upper()
    player = get_player_by_username(username)
    if not player:
        await interaction.response.send_message(f"Le joueur {username} n'est pas enregistré.", ephemeral=True)
        return
    puuid = player[1]

    # Pour ajouter un joueur au leaderboard, on insère une ligne dans la table 'leaderboard_members'
    # Récupérer l'ID du leaderboard à partir de la table 'guilds'
    guild_data = get_guild(guild_id)
    if not guild_data:
        await interaction.response.send_message("Aucun leaderboard configuré dans ce serveur.", ephemeral=True)
        return
    leaderboard_id = guild_data[1]  # l'ID du channel du leaderboard
    insert_leaderboard_member(guild_id, leaderboard_id, puuid)
    await interaction.response.send_message(f"Le joueur {username} a été ajouté au leaderboard.", ephemeral=True)
    await update_leaderboard_embed(leaderboard_id, interaction.client, guild_id)

@app_commands.command(name="removeleaderboard", description="Supprimer un joueur du leaderboard")
@app_commands.describe(username="Le nom du joueur (format: USERNAME#TAG)")
async def removeleaderboard(interaction: discord.Interaction, username: str):
    guild_id = str(interaction.guild.id)
    username = username.upper()
    player = get_player_by_username(username)
    if not player:
        await interaction.response.send_message(f"Le joueur {username} n'est pas enregistré.", ephemeral=True)
        return
    puuid = player[1]
    from fonction_bdd import delete_leaderboard_member  # Import local pour éviter un cycle
    guild_data = get_guild(guild_id)
    if not guild_data:
        await interaction.response.send_message("Aucun leaderboard configuré dans ce serveur.", ephemeral=True)
        return
    leaderboard_id = guild_data[1]
    delete_leaderboard_member(guild_id, leaderboard_id, puuid)
    await interaction.response.send_message(f"Le joueur {username} a été retiré du leaderboard.", ephemeral=True)
    await update_leaderboard_embed(leaderboard_id, interaction.client, guild_id)

async def update_leaderboard_embed(leaderboard_id, bot, guild_id):
    """
    Met à jour l'embed du leaderboard selon la nouvelle table 'leaderboard'.
    """
    guild_obj = bot.get_guild(int(guild_id))
    channel = discord.utils.get(guild_obj.text_channels, id=int(leaderboard_id))
    if not channel:
        logging.warning(f"Leaderboard channel {leaderboard_id} not found")
        return
    # Récupère uniquement les membres du leaderboard depuis la nouvelle table
    rows = get_leaderboard_data(leaderboard_id, guild_id)
    embed = discord.Embed(
        title="Leaderboard",
        description="Classement des joueurs",
        color=discord.Color.blue()
    )
    for row in rows:
        # On suppose que get_leaderboard_data retourne (username, tier, rank, lp_24h, lp_7d)
        username, tier, rank_val, lp_24h, lp_7d = row
        embed.add_field(
            name=username,
            value=f"Rank: {tier} {rank_val}\nLP (24h): {lp_24h}\nLP (7j): {lp_7d}",
            inline=False
        )
    async for message in channel.history(limit=50):
        if message.author == guild_obj.me and message.embeds and "Leaderboard" in message.embeds[0].title:
            await message.edit(embed=embed)
            return
    await channel.send(embed=embed)

# Optionnel : Une fonction de setup pour ajouter les commandes dans l'arbre global
def setup_tree(tree_obj: app_commands.CommandTree):
    tree_obj.add_command(leaderboard)
    tree_obj.add_command(addleaderboard)
    tree_obj.add_command(removeleaderboard)

