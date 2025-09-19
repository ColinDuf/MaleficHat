# Tableau de bord Laravel

Ce dossier contient le code nécessaire pour ajouter un panel administrateur Laravel à MaleficHat. Il s'appuie sur la base SQLite déjà utilisée par le bot Python afin d'afficher :

- la liste des joueurs enregistrés ;
- le compteur total de joueurs ;
- le compteur de joueurs actuellement « en game » ;
- des filtres (recherche, région, rang, statut, guilde) et un tri.

## 1. Pré-requis

- PHP 8.2+
- Composer
- Node.js (optionnel, uniquement si vous souhaitez compiler des assets via Vite)

## 2. Installer un squelette Laravel

```bash
cd /chemin/vers/MaleficHat
composer create-project laravel/laravel admin-panel
```

Ensuite, copiez les fichiers de ce dossier `laravel-admin` vers le nouveau projet :

```bash
rsync -av laravel-admin/ admin-panel/
```

> ⚠️ Le dossier `admin-panel` est un projet Laravel standard : ne remplacez pas les dossiers `vendor/` ou `bootstrap/` créés par Composer.

## 3. Brancher la base SQLite existante

Dans `admin-panel/.env`, configurez la connexion :

```ini
DB_CONNECTION=sqlite
DB_DATABASE=/chemin/absolu/vers/MaleficHat/Backend/database.db
```

Vérifiez que l'application web a les droits en lecture/écriture sur ce fichier.

## 4. Charger la nouvelle route admin

Dans `app/Providers/RouteServiceProvider.php`, ajoutez le chargement du fichier `routes/admin.php` :

```php
public function boot(): void
{
    parent::boot();

    Route::middleware('web')
        ->group(base_path('routes/admin.php'));
}
```

Le groupe de routes défini applique le middleware `auth`. Tant que l'authentification n'est pas configurée, vous pouvez retirer `auth` de `routes/admin.php` pour valider l'interface localement.

## 5. Mettre à jour le schéma `player`

Le script Python `Backend/create_db.py` a été enrichi pour ajouter automatiquement les colonnes :

- `current_game_status` (`offline` par défaut) ;
- `current_game_updated_at` (horodatage de la dernière mise à jour de statut).

Exécutez-le une fois pour garantir la présence de ces colonnes sur la base existante :

```bash
python Backend/create_db.py
```

Côté Laravel, une migration idempotente (`database/migrations/2024_03_05_000000_add_current_game_status_to_player_table.php`) est également fournie. Lancez-la si vous préférez gérer le schéma via Laravel :

```bash
cd admin-panel
php artisan migrate --path=database/migrations/2024_03_05_000000_add_current_game_status_to_player_table.php
```

## 6. Maintenir l'état « en game »

Un nouveau helper Python met à jour le statut d'un joueur dans la table `player` :

```python
from Backend.fonction_bdd import update_player_status
update_player_status(puuid, "in_game")
```

Statuts disponibles : `in_game`, `offline`. Le champ `current_game_updated_at` est rempli avec l'heure courante si aucun horodatage n'est fourni.

Mettez à jour ce statut lorsque vous détectez l'entrée / la sortie de partie (par exemple via vos tâches de scraping Riot). Le tableau de bord comptera automatiquement les joueurs `in_game`.

## 7. Lancer le panel

```bash
cd admin-panel
php artisan serve
```

Ouvrez `http://127.0.0.1:8000/admin` et connectez-vous. Vous verrez :

- les statistiques en tête de page (total, en game) ;
- un formulaire de filtre ;
- un tableau paginé (25 joueurs / page) avec guildes, statut, LP, timestamp des mises à jour.

Le cache des statistiques se rafraîchit toutes les 15 secondes.

## 8. Personnalisation

- Ajoutez vos propres middlewares d'authentification/autorisation.
- Adaptez les couleurs et la charte via `resources/views/layouts/admin.blade.php`.
- Intégrez Vite/Tailwind si vous souhaitez une UI plus poussée.

Bon build !
