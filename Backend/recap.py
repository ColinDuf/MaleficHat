import discord


def build_recap_embed(rows, period: str) -> discord.Embed:
    """Build an embed summarizing LP changes for ``rows``."""
    index = 4 if period == "daily" else 5
    title = "Daily" if period == "daily" else "Weekly"
    sorted_rows = sorted(rows, key=lambda r: r[index], reverse=True)
    embed = discord.Embed(title=f"{title} recap")
    for i, row in enumerate(sorted_rows):
        change = row[index]
        sign = "+" if change >= 0 else ""
        embed.add_field(
            name=f"{i+1}. {row[0]}",
            value=f"{sign}{change} LP",
            inline=False,
        )
    return embed