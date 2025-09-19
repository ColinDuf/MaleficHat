<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Guild extends Model
{
    protected $table = 'guild';

    protected $primaryKey = 'guild_id';

    public $incrementing = false;

    public $timestamps = false;

    protected $guarded = [];

    public function players(): BelongsToMany
    {
        return $this->belongsToMany(Player::class, 'player_guild', 'guild_id', 'player_puuid')
            ->withPivot(['channel_id', 'last_match_id']);
    }

    public function playerGuildEntries(): HasMany
    {
        return $this->hasMany(PlayerGuild::class, 'guild_id', 'guild_id');
    }
}
