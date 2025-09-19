<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\Guild;
use App\Models\Player;
use Illuminate\Http\Request;
use Illuminate\Support\Arr;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Validator;

class AdminDashboardController extends Controller
{
    /**
     * Display the admin dashboard listing players with filters and stats.
     */
    public function index(Request $request)
    {
        $filters = Validator::make($request->query(), [
            'search'   => ['nullable', 'string', 'max:80'],
            'region'   => ['nullable', 'string', 'max:10'],
            'tier'     => ['nullable', 'string', 'max:20'],
            'status'   => ['nullable', 'in:in_game,in_queue,offline'],
            'guild_id' => ['nullable', 'integer'],
            'sort'     => ['nullable', 'in:recent,name,lp,tier'],
            'direction'=> ['nullable', 'in:asc,desc'],
        ])->validate();

        $playersQuery = Player::query()
            ->with(['guilds' => function ($query) {
                $query->select('guild.guild_id', 'leaderboard_channel_id');
            }]);

        if (!empty($filters['search'])) {
            $term = '%' . $filters['search'] . '%';
            $playersQuery->where(function ($query) use ($term) {
                $query->where('username', 'like', $term)
                    ->orWhere('puuid', 'like', $term)
                    ->orWhere('region', 'like', $term);
            });
        }

        if (!empty($filters['region'])) {
            $playersQuery->where('region', $filters['region']);
        }

        if (!empty($filters['tier'])) {
            $playersQuery->where('tier', $filters['tier']);
        }

        if (!empty($filters['status'])) {
            $playersQuery->where('current_game_status', $filters['status']);
        }

        if (!empty($filters['guild_id'])) {
            $playersQuery->whereHas('guilds', function ($query) use ($filters) {
                $query->where('guild.guild_id', $filters['guild_id']);
            });
        }

        $direction = Arr::get($filters, 'direction', 'desc');
        switch (Arr::get($filters, 'sort')) {
            case 'name':
                $playersQuery->orderBy('username', $direction);
                break;
            case 'lp':
                $playersQuery->orderBy('lp', $direction);
                break;
            case 'tier':
                $playersQuery->orderBy('tier', $direction);
                break;
            default:
                $playersQuery->orderBy('updated_at', $direction);
        }

        $players = $playersQuery->paginate(25)->withQueryString();

        $stats = Cache::remember('admin.dashboard.stats', now()->addSeconds(15), function () {
            return [
                'total_players'   => Player::count(),
                'players_in_game' => Player::where('current_game_status', 'in_game')->count(),
                'players_in_queue'=> Player::where('current_game_status', 'in_queue')->count(),
                'updated_at'      => Carbon::now(),
            ];
        });

        $regions = Player::query()
            ->select('region')
            ->distinct()
            ->orderBy('region')
            ->pluck('region')
            ->filter(fn ($region) => !empty($region))
            ->values();

        $tiers = Player::query()
            ->select('tier')
            ->distinct()
            ->orderBy('tier')
            ->pluck('tier')
            ->filter(fn ($tier) => !empty($tier))
            ->values();

        $guilds = Guild::query()
            ->orderBy('guild_id')
            ->get(['guild_id', 'leaderboard_channel_id']);

        return view('admin.dashboard', [
            'players' => $players,
            'stats'   => $stats,
            'filters' => $filters,
            'regions' => $regions,
            'tiers'   => $tiers,
            'guilds'  => $guilds,
        ]);
    }
}
