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

        .status-badge[data-status="in_queue"] {
            background: rgba(250, 204, 21, 0.12);
            color: rgb(250, 204, 21);
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
        <h1>Panel administrateur</h1>
        <p class="lead">Visualisez les joueurs suivis par MaleficHat, surveillez l'activité en direct et appliquez des filtres précis pour retrouver rapidement une personne ou un groupe.</p>
    </header>

    <section class="grid stats">
        <article class="card stat-card">
            <span class="label">Total joueurs</span>
            <h2>{{ number_format($stats['total_players']) }}</h2>
        </article>
        <article class="card stat-card">
            <span class="label">En game</span>
            <h2>{{ number_format($stats['players_in_game']) }}</h2>
        </article>
        <article class="card stat-card">
            <span class="label">En file</span>
            <h2>{{ number_format($stats['players_in_queue']) }}</h2>
        </article>
        <article class="card stat-card">
            <span class="label">Mise à jour</span>
            <h2>{{ $stats['updated_at']->diffForHumans() }}</h2>
        </article>
    </section>

    <form method="GET" action="{{ route('admin.dashboard') }}" class="card filters-form">
        <div class="grid">
            <div>
                <label for="search">Recherche</label>
                <input type="text" id="search" name="search" placeholder="Pseudo, PUUID, région…" value="{{ $filters['search'] ?? '' }}">
            </div>
            <div>
                <label for="region">Région</label>
                <select id="region" name="region">
                    <option value="">Toutes</option>
                    @foreach ($regions as $region)
                        <option value="{{ $region }}" @selected(($filters['region'] ?? '') === $region)>{{ strtoupper($region) }}</option>
                    @endforeach
                </select>
            </div>
            <div>
                <label for="tier">Rang (solo)</label>
                <select id="tier" name="tier">
                    <option value="">Tous</option>
                    @foreach ($tiers as $tier)
                        <option value="{{ $tier }}" @selected(($filters['tier'] ?? '') === $tier)>{{ ucfirst(strtolower($tier)) }}</option>
                    @endforeach
                </select>
            </div>
            <div>
                <label for="status">Statut</label>
                <select id="status" name="status">
                    <option value="">Tous</option>
                    <option value="in_game" @selected(($filters['status'] ?? '') === 'in_game')>En game</option>
                    <option value="in_queue" @selected(($filters['status'] ?? '') === 'in_queue')>En file</option>
                    <option value="offline" @selected(($filters['status'] ?? '') === 'offline')>Hors ligne</option>
                </select>
            </div>
            <div>
                <label for="guild_id">Serveur Discord</label>
                <select id="guild_id" name="guild_id">
                    <option value="">Tous</option>
                    @foreach ($guilds as $guild)
                        <option value="{{ $guild->guild_id }}" @selected(($filters['guild_id'] ?? null) == $guild->guild_id)>
                            #{{ $guild->guild_id }}
                        </option>
                    @endforeach
                </select>
            </div>
            <div>
                <label for="sort">Tri</label>
                <select id="sort" name="sort">
                    <option value="recent" @selected(($filters['sort'] ?? 'recent') === 'recent')>Dernière mise à jour</option>
                    <option value="name" @selected(($filters['sort'] ?? '') === 'name')>Pseudo</option>
                    <option value="lp" @selected(($filters['sort'] ?? '') === 'lp')>LP</option>
                    <option value="tier" @selected(($filters['sort'] ?? '') === 'tier')>Tier</option>
                </select>
            </div>
            <div>
                <label for="direction">Ordre</label>
                <select id="direction" name="direction">
                    <option value="desc" @selected(($filters['direction'] ?? 'desc') === 'desc')>Décroissant</option>
                    <option value="asc" @selected(($filters['direction'] ?? 'desc') === 'asc')>Croissant</option>
                </select>
            </div>
        </div>
        <div class="actions">
            <a href="{{ route('admin.dashboard') }}" class="reset">Réinitialiser</a>
            <button type="submit">Appliquer</button>
        </div>
    </form>

    <div class="table-wrapper card">
        <table>
            <thead>
                <tr>
                    <th>Joueur</th>
                    <th>Région</th>
                    <th>Rang</th>
                    <th>LP</th>
                    <th>Statut</th>
                    <th>Guildes suivies</th>
                    <th>Maj globale</th>
                    <th>Maj statut</th>
                </tr>
            </thead>
            <tbody>
                @forelse ($players as $player)
                    <tr>
                        <td>
                            <strong>{{ $player->username }}</strong><br>
                            <small style="color: rgba(148, 163, 184, 0.8);">{{ $player->puuid }}</small>
                        </td>
                        <td>{{ strtoupper($player->region ?? 'n/a') }}</td>
                        <td>{{ ucfirst(strtolower($player->tier ?? '')) }} {{ $player->rank }}</td>
                        <td>{{ number_format($player->lp ?? 0) }}</td>
                        <td>
                            <span class="status-badge" data-status="{{ $player->current_game_status ?? 'offline' }}">
                                {{ match ($player->current_game_status) {
                                    'in_game'  => 'En game',
                                    'in_queue' => 'En file',
                                    default    => 'Hors ligne',
                                } }}
                            </span>
                        </td>
                        <td>
                            @forelse ($player->guilds as $guild)
                                <span class="guild-pill">#{{ $guild->guild_id }}</span>
                            @empty
                                <span style="color: rgba(148, 163, 184, 0.8);">Non liée</span>
                            @endforelse
                        </td>
                        <td>{{ optional($player->updated_at)->diffForHumans() ?? '—' }}</td>
                        <td>{{ optional($player->current_game_updated_at)->diffForHumans() ?? '—' }}</td>
                    </tr>
                @empty
                    <tr>
                        <td colspan="8">
                            <div class="empty-state">
                                Aucun joueur ne correspond aux filtres sélectionnés. Modifiez votre recherche ou réinitialisez les filtres.
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
@endsection
