@extends('layouts.admin')

@section('content')
    <style>
        h1 {
            font-size: clamp(1.8rem, 5vw, 2.5rem);
            margin: 0 0 0.5rem;
        }

        p.lead {
            margin: 0 0 2rem;
            color: rgba(226, 232, 240, 0.8);
            max-width: 720px;
        }

        .stat-card h2 {
            margin: 0;
            font-size: clamp(1.6rem, 4vw, 2.4rem);
            font-weight: 700;
        }

        .stat-card span.label {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.75rem;
            font-weight: 600;
            color: rgba(226, 232, 240, 0.7);
        }

        .filters-form {
            margin-top: 2rem;
            display: grid;
            gap: 1.2rem;
        }

        .filters-form .grid {
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        }

        .filters-form label {
            font-size: 0.85rem;
            font-weight: 600;
            display: block;
            margin-bottom: 0.35rem;
            color: rgba(226, 232, 240, 0.75);
        }

        .filters-form input,
        .filters-form select {
            width: 100%;
            padding: 0.55rem 0.75rem;
            border-radius: 10px;
            border: 1px solid rgba(148, 163, 184, 0.25);
            background: rgba(15, 23, 42, 0.35);
            color: #f8fafc;
            font-size: 0.95rem;
            transition: border-color 0.15s ease, background-color 0.15s ease;
        }

        .filters-form input:focus,
        .filters-form select:focus {
            outline: none;
            border-color: rgba(99, 102, 241, 0.6);
            background: rgba(99, 102, 241, 0.12);
        }

        .filters-form .actions {
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            justify-content: flex-end;
        }

        .filters-form button {
            border-radius: 10px;
            border: 1px solid transparent;
            padding: 0.6rem 1.4rem;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.15s ease, box-shadow 0.2s ease;
        }

        .filters-form button[type="submit"] {
            background: linear-gradient(135deg, #6366f1, #8b5cf6);
            color: white;
            box-shadow: 0 12px 30px rgba(99, 102, 241, 0.35);
        }

        .filters-form button[type="submit"]:hover {
            transform: translateY(-1px);
        }

        .filters-form a.reset {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.6rem 1.1rem;
            border-radius: 10px;
            text-decoration: none;
            font-weight: 600;
            background: rgba(15, 23, 42, 0.55);
            border: 1px solid rgba(148, 163, 184, 0.25);
            color: rgba(226, 232, 240, 0.85);
        }

        .sort-link {
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
            color: inherit;
            text-decoration: none;
            font-weight: 600;
            letter-spacing: 0.05em;
        }

        .sort-link .sort-indicator {
            font-size: 0.75rem;
            opacity: 0.6;
        }

        .sort-link.is-active {
            color: rgba(248, 250, 252, 0.95);
        }

        .sort-link.is-active .sort-indicator {
            opacity: 0.9;
        }

        .sort-link:not(.is-active):hover .sort-indicator {
            opacity: 0.8;
        }

        .player-info strong {
            display: block;
        }

        .puuid-toggle {
            margin-top: 0.4rem;
            padding: 0.35rem 0.75rem;
            border-radius: 8px;
            border: 1px solid rgba(99, 102, 241, 0.45);
            background: rgba(99, 102, 241, 0.12);
            color: rgba(191, 219, 254, 0.95);
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.04em;
            cursor: pointer;
            transition: background-color 0.15s ease, border-color 0.15s ease;
        }

        .puuid-toggle:hover {
            background: rgba(99, 102, 241, 0.22);
            border-color: rgba(99, 102, 241, 0.65);
        }

        .player-puuid {
            display: block;
            margin-top: 0.35rem;
            color: rgba(148, 163, 184, 0.8);
            word-break: break-all;
        }

        .player-puuid[hidden] {
            display: none !important;
        }

        .table-wrapper {
            margin-top: 2.5rem;
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            min-width: 720px;
        }

        thead {
            background: rgba(15, 23, 42, 0.75);
        }

        th {
            text-align: left;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 600;
            padding: 0.9rem 1rem;
            color: rgba(148, 163, 184, 0.95);
            border-bottom: 1px solid rgba(148, 163, 184, 0.3);
        }

        td {
            padding: 1rem;
            border-bottom: 1px solid rgba(148, 163, 184, 0.12);
            font-size: 0.95rem;
            color: rgba(241, 245, 249, 0.92);
        }

        tr:hover td {
            background: rgba(45, 55, 72, 0.2);
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.25rem 0.6rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        .status-badge[data-status="in_game"] {
            background: rgba(74, 222, 128, 0.12);
            color: rgb(74, 222, 128);
        }

        .status-badge[data-status="offline"] {
            background: rgba(148, 163, 184, 0.14);
            color: rgba(203, 213, 225, 0.95);
        }

        .guild-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.25rem 0.6rem;
            border-radius: 999px;
            background: rgba(99, 102, 241, 0.16);
            color: rgba(191, 219, 254, 0.95);
            font-size: 0.75rem;
            font-weight: 600;
            margin-right: 0.4rem;
            margin-bottom: 0.4rem;
        }

        .empty-state {
            text-align: center;
            padding: 3rem 1rem;
            color: rgba(148, 163, 184, 0.85);
        }

        .pagination {
            margin-top: 2rem;
            display: flex;
            justify-content: flex-end;
            gap: 0.5rem;
            flex-wrap: wrap;
        }

        .pagination * {
            color: #f8fafc;
        }
    </style>

    <header>
        <h1>Admin Dashboard</h1>
        <p class="lead">View the players tracked by MaleficHat, monitor live activity, and apply precise filters to quickly locate a person or group.</p>
    </header>

    <section class="grid stats">
        <article class="card stat-card">
            <span class="label">Total Players</span>
            <h2>{{ number_format($stats['total_players']) }}</h2>
        </article>
        <article class="card stat-card">
            <span class="label">In Game</span>
            <h2>{{ number_format($stats['players_in_game']) }}</h2>
        </article>
        <article class="card stat-card">
            <span class="label">Last Update</span>
            <h2>{{ $stats['updated_at']->diffForHumans() }}</h2>
        </article>
    </section>

    <form method="GET" action="{{ route('admin.dashboard') }}" class="card filters-form">
        <input type="hidden" name="sort" value="{{ $filters['sort'] ?? 'recent' }}">
        <input type="hidden" name="direction" value="{{ $filters['direction'] ?? 'desc' }}">
        <div class="grid">
            <div>
                <label for="search">Search</label>
                <input type="text" id="search" name="search" placeholder="Player, PUUID, region..." value="{{ $filters['search'] ?? '' }}">
            </div>
            <div>
                <label for="region">Region</label>
                <select id="region" name="region">
                    <option value="">All</option>
                    @foreach ($regions as $region)
                        <option value="{{ $region }}" @selected(($filters['region'] ?? '') === $region)>{{ strtoupper($region) }}</option>
                    @endforeach
                </select>
            </div>
            <div>
                <label for="tier">Rank (solo)</label>
                <select id="tier" name="tier">
                    <option value="">All</option>
                    @foreach ($tiers as $tier)
                        <option value="{{ $tier['value'] }}" @selected(($filters['tier'] ?? '') === $tier['value'])>{{ $tier['label'] }}</option>
                    @endforeach
                </select>
            </div>
            <div>
                <label for="status">Status</label>
                <select id="status" name="status">
                    <option value="">All</option>
                    <option value="in_game" @selected(($filters['status'] ?? '') === 'in_game')>In Game</option>
                    <option value="offline" @selected(($filters['status'] ?? '') === 'offline')>Offline</option>
                </select>
            </div>
            <div>
                <label for="guild_id">Discord Server</label>
                <select id="guild_id" name="guild_id">
                    <option value="">All</option>
                    @foreach ($guilds as $guild)
                        @php
                            $guildLabel = $guild->name ?: ('#' . $guild->guild_id);
                        @endphp
                        <option value="{{ $guild->guild_id }}" @selected(($filters['guild_id'] ?? null) == $guild->guild_id)>
                            {{ $guildLabel }}
                        </option>
                    @endforeach
                </select>
            </div>
        </div>
        <div class="actions">
            <a href="{{ route('admin.dashboard') }}" class="reset">Reset</a>
        </div>
    </form>

    <div class="table-wrapper card">
        @php
            $currentSort = $filters['sort'] ?? 'recent';
            $currentDirection = $filters['direction'] ?? 'desc';

            $sortMeta = function (string $field, string $defaultDirection = 'asc') use ($currentSort, $currentDirection) {
                $isActive = $currentSort === $field;
                $nextDirection = $isActive
                    ? ($currentDirection === 'asc' ? 'desc' : 'asc')
                    : $defaultDirection;

                $url = request()->fullUrlWithQuery([
                    'sort' => $field,
                    'direction' => $nextDirection,
                    'page' => null,
                ]);

                return [
                    'url' => $url,
                    'isActive' => $isActive,
                    'direction' => $isActive ? $currentDirection : null,
                ];
            };

            $playerSort = $sortMeta('name', 'asc');
            $statusSort = $sortMeta('status', 'asc');
            $rankSort = $sortMeta('rank', 'desc');
            $lpSort = $sortMeta('lp', 'desc');
            $regionSort = $sortMeta('region', 'asc');
            $guildSort = $sortMeta('guilds', 'desc');
            $recentSort = $sortMeta('recent', 'desc');
            $statusUpdatedSort = $sortMeta('status_updated', 'desc');
        @endphp

        <table>
            <thead>
                <tr>
                    <th>
                        <a href="{{ $playerSort['url'] }}" class="sort-link{{ $playerSort['isActive'] ? ' is-active' : '' }}">
                            Player
                            <span class="sort-indicator">
                                @if ($playerSort['isActive'])
                                    {{ $playerSort['direction'] === 'asc' ? '↑' : '↓' }}
                                @else
                                    ↕
                                @endif
                            </span>
                        </a>
                    </th>
                    <th>
                        <a href="{{ $statusSort['url'] }}" class="sort-link{{ $statusSort['isActive'] ? ' is-active' : '' }}">
                            Status
                            <span class="sort-indicator">
                                @if ($statusSort['isActive'])
                                    {{ $statusSort['direction'] === 'asc' ? '↑' : '↓' }}
                                @else
                                    ↕
                                @endif
                            </span>
                        </a>
                    </th>
                    <th>
                        <a href="{{ $rankSort['url'] }}" class="sort-link{{ $rankSort['isActive'] ? ' is-active' : '' }}">
                            Rank
                            <span class="sort-indicator">
                                @if ($rankSort['isActive'])
                                    {{ $rankSort['direction'] === 'asc' ? '↑' : '↓' }}
                                @else
                                    ↕
                                @endif
                            </span>
                        </a>
                    </th>
                    <th>
                        <a href="{{ $lpSort['url'] }}" class="sort-link{{ $lpSort['isActive'] ? ' is-active' : '' }}">
                            LP
                            <span class="sort-indicator">
                                @if ($lpSort['isActive'])
                                    {{ $lpSort['direction'] === 'asc' ? '↑' : '↓' }}
                                @else
                                    ↕
                                @endif
                            </span>
                        </a>
                    </th>
                    <th>
                        <a href="{{ $regionSort['url'] }}" class="sort-link{{ $regionSort['isActive'] ? ' is-active' : '' }}">
                            Region
                            <span class="sort-indicator">
                                @if ($regionSort['isActive'])
                                    {{ $regionSort['direction'] === 'asc' ? '↑' : '↓' }}
                                @else
                                    ↕
                                @endif
                            </span>
                        </a>
                    </th>
                    <th>
                        <a href="{{ $guildSort['url'] }}" class="sort-link{{ $guildSort['isActive'] ? ' is-active' : '' }}">
                            Tracked Guilds
                            <span class="sort-indicator">
                                @if ($guildSort['isActive'])
                                    {{ $guildSort['direction'] === 'asc' ? '↑' : '↓' }}
                                @else
                                    ↕
                                @endif
                            </span>
                        </a>
                    </th>
                    <th>
                        <a href="{{ $recentSort['url'] }}" class="sort-link{{ $recentSort['isActive'] ? ' is-active' : '' }}">
                            Profile Updated
                            <span class="sort-indicator">
                                @if ($recentSort['isActive'])
                                    {{ $recentSort['direction'] === 'asc' ? '↑' : '↓' }}
                                @else
                                    ↕
                                @endif
                            </span>
                        </a>
                    </th>
                    <th>
                        <a href="{{ $statusUpdatedSort['url'] }}" class="sort-link{{ $statusUpdatedSort['isActive'] ? ' is-active' : '' }}">
                            Status Updated
                            <span class="sort-indicator">
                                @if ($statusUpdatedSort['isActive'])
                                    {{ $statusUpdatedSort['direction'] === 'asc' ? '↑' : '↓' }}
                                @else
                                    ↕
                                @endif
                            </span>
                        </a>
                    </th>
                </tr>
            </thead>
            <tbody>
                @forelse ($players as $player)
                    <tr>
                        <td class="player-info">
                            <strong>{{ $player->username }}</strong>
                            @php
                                $puuidElementId = 'puuid-' . $loop->iteration;
                            @endphp
                            <button type="button" class="puuid-toggle" data-target="{{ $puuidElementId }}">Show PUUID</button>
                            <small id="{{ $puuidElementId }}" class="player-puuid" hidden>{{ $player->puuid }}</small>
                        </td>
                        <td>
                            <span class="status-badge" data-status="{{ $player->current_game_status ?? 'offline' }}">
                                {{ match ($player->current_game_status) {
                                    'in_game' => 'In Game',
                                    default   => 'Offline',
                                } }}
                            </span>
                        </td>
                        <td>{{ $player->rank }} {{ strtoupper($player->tier ?? '') }}</td>
                        <td>{{ number_format($player->lp ?? 0) }}</td>
                        <td>{{ strtoupper($player->region ?? 'n/a') }}</td>
                        <td>
                            @forelse ($player->guilds as $guild)
                                @php
                                    $guildLabel = $guild->name ?: ('#' . $guild->guild_id);
                                @endphp
                                <span class="guild-pill" title="#{{ $guild->guild_id }}">{{ $guildLabel }}</span>
                            @empty
                                <span style="color: rgba(148, 163, 184, 0.8);">Not linked</span>
                            @endforelse
                        </td>
                        <td>{{ optional($player->updated_at)->diffForHumans() ?? '—' }}</td>
                        <td>{{ optional($player->current_game_updated_at)->diffForHumans() ?? '—' }}</td>
                    </tr>
                @empty
                    <tr>
                        <td colspan="8">
                            <div class="empty-state">
                                No players match the selected filters. Adjust your search or reset the filters.
                            </div>
                        </td>
                    </tr>
                @endforelse
            </tbody>
        </table>

        <div class="pagination">
            {{ $players->links() }}
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function () {
            document.addEventListener('click', function (event) {
                const toggle = event.target.closest('.puuid-toggle');
                if (!toggle) {
                    return;
                }

                const targetId = toggle.getAttribute('data-target');
                const target = document.getElementById(targetId);
                if (!target) {
                    return;
                }

                const isHidden = target.hasAttribute('hidden');
                if (isHidden) {
                    target.removeAttribute('hidden');
                    toggle.textContent = 'Hide PUUID';
                } else {
                    target.setAttribute('hidden', 'hidden');
                    toggle.textContent = 'Show PUUID';
                }
            });

            const filtersForm = document.querySelector('.filters-form');
            if (!filtersForm) {
                return;
            }

            const submitForm = () => {
                if (typeof filtersForm.requestSubmit === 'function') {
                    filtersForm.requestSubmit();
                } else {
                    filtersForm.submit();
                }
            };

            const debounce = (fn, delay = 500) => {
                let timeoutId;
                return (...args) => {
                    clearTimeout(timeoutId);
                    timeoutId = setTimeout(() => fn(...args), delay);
                };
            };

            const submitWithDebounce = debounce(submitForm, 500);

            filtersForm.querySelectorAll('select').forEach((select) => {
                select.addEventListener('change', submitForm);
            });

            const searchInput = filtersForm.querySelector('input[name="search"]');
            if (searchInput) {
                searchInput.addEventListener('input', submitWithDebounce);
            }

            const autoRefreshIntervalMs = 60000;
            setInterval(submitForm, autoRefreshIntervalMs);
        });
    </script>
@endsection
