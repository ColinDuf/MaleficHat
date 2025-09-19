<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Player extends Model
{
    protected $table = 'player';

    protected $primaryKey = 'puuid';

    public $incrementing = false;

    protected $keyType = 'string';

    public const CREATED_AT = 'created_at';

    public const UPDATED_AT = 'updated_at';

    protected $guarded = [];

    protected $casts = [
        'lp'                     => 'integer',
        'lp_24h'                 => 'integer',
        'lp_7d'                  => 'integer',
        'created_at'             => 'datetime',
        'updated_at'             => 'datetime',
        'current_game_updated_at'=> 'datetime',
    ];

    /**
     * Guilds the player belongs to.
     */
    public function guilds(): BelongsToMany
    {
        return $this->belongsToMany(Guild::class, 'player_guild', 'player_puuid', 'guild_id')
            ->withPivot(['channel_id', 'last_match_id']);
    }

    /**
     * Raw player-guild pivot entries for advanced filtering.
     */
    public function playerGuildEntries(): HasMany
    {
        return $this->hasMany(PlayerGuild::class, 'player_puuid', 'puuid');
    }
}
