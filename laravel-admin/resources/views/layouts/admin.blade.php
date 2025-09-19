<!DOCTYPE html>
<html lang="fr">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Panel admin - MaleficHat</title>
        <link rel="preconnect" href="https://fonts.bunny.net">
        <link href="https://fonts.bunny.net/css?family=inter:400,500,600,700" rel="stylesheet" />
        <style>
            :root {
                color-scheme: light dark;
                font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                --bg: #0f172a;
                --bg-card: rgba(15, 23, 42, 0.8);
                --bg-card-light: rgba(255, 255, 255, 0.9);
                --border: rgba(148, 163, 184, 0.3);
                --text: #0f172a;
                --text-light: #f8fafc;
                --accent: #6366f1;
            }

            body {
                margin: 0;
                min-height: 100vh;
                background: linear-gradient(135deg, #020617, #0b1120 45%, #1e1b4b);
                color: var(--text-light);
                display: flex;
                flex-direction: column;
            }

            main {
                width: 100%;
                max-width: 1200px;
                margin: 2rem auto 3rem;
                padding: 0 1.5rem;
                box-sizing: border-box;
            }

            .card {
                background: rgba(15, 23, 42, 0.85);
                border: 1px solid rgba(148, 163, 184, 0.25);
                border-radius: 18px;
                padding: 1.5rem;
                backdrop-filter: blur(16px);
                box-shadow: 0 24px 60px rgba(15, 23, 42, 0.35);
            }

            .card.light {
                background: rgba(255, 255, 255, 0.92);
                color: #0f172a;
            }

            .grid {
                display: grid;
                gap: 1.25rem;
            }

            @media (min-width: 1024px) {
                .grid.stats {
                    grid-template-columns: repeat(4, minmax(0, 1fr));
                }
            }

            a {
                color: inherit;
            }
        </style>
        @stack('head')
    </head>
    <body>
        <main>
            @yield('content')
        </main>
        @stack('scripts')
    </body>
</html>
