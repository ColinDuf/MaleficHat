import discord


def build_recap_embed(rows, period: str) -> discord.Embed:
    """Build an embed summarizing LP changes for ``rows``.

    rows schema: (username, tier, rank, lp, lp_24h, lp_7d)
    - Always display both 24h and 7d gains.
    - Include current rank (e.g., "GOLD I — 57 LP").
    - Sort by 24h for daily, by 7d for weekly.
    """
    idx_sort = 4 if period == "daily" else 5
    title = "Daily" if period == "daily" else "Weekly"

    # Sort players by the selected period change, descending
    sorted_rows = sorted(rows, key=lambda r: (r[idx_sort] or 0), reverse=True)

    embed = discord.Embed(title=f"{title} recap")

    for i, row in enumerate(sorted_rows, start=1):
        username, tier, rank_cat, current_lp, lp_24h, lp_7d = row

        # Current rank line
        if rank_cat and tier:
            rank_line = f"{rank_cat} {tier} — {current_lp} LP"
        else:
            rank_line = "Unranked"

        # Normalize LP deltas
        lp24 = lp_24h or 0
        lp7 = lp_7d or 0
        s24 = "+" if lp24 >= 0 else ""
        s7 = "+" if lp7 >= 0 else ""

        value = (
            f"Rank: {rank_line}\n"
            f"LP 24h: {s24}{lp24} | LP 7d: {s7}{lp7}"
        )

        embed.add_field(
            name=f"{i}. {username}",
            value=value,
            inline=False,
        )

    return embed
