<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::table('player', function (Blueprint $table) {
            if (!Schema::hasColumn('player', 'current_game_status')) {
                $table->string('current_game_status', 20)->default('offline');
            }

            if (!Schema::hasColumn('player', 'current_game_updated_at')) {
                $table->timestamp('current_game_updated_at')->nullable();
            }
        });
    }

    public function down(): void
    {
        Schema::table('player', function (Blueprint $table) {
            if (Schema::hasColumn('player', 'current_game_status')) {
                $table->dropColumn('current_game_status');
            }
            if (Schema::hasColumn('player', 'current_game_updated_at')) {
                $table->dropColumn('current_game_updated_at');
            }
        });
    }
};
