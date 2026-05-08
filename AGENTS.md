# Repository Guidelines

## Project Structure & Module Organization

`fund-baby/` is the Next.js reference implementation. Application code lives in `fund-baby/app/`: `page.jsx` is the main client UI, `layout.jsx` defines app metadata/layout, `globals.css` contains global styles, and `icon.svg` is the app icon. Reusable UI lives in `fund-baby/app/components/`, data helpers in `fund-baby/app/api/fund.js`, Supabase setup in `fund-baby/app/lib/supabase.js`, and images in `fund-baby/app/assets/`. New Python CLI scripts belong in `fund_radar/`; do not add them under `fund-baby/`. Deployment files include `fund-baby/.github/workflows/`, `Dockerfile`, `docker-compose.yml`, `vercel.json`, `next.config.js`, and `supabase.sql`.

## Environment Setup

Use the conda virtual environment named `fund` for project work:

```bash
conda activate fund
```

Install JavaScript dependencies inside `fund-baby/` with `npm install`. Run Python tools from the repository root, for example `python fund_radar/query_fund_estimate.py 110022`. Keep local secrets in `fund-baby/.env.local`, copied from `fund-baby/env.example`.

## Build, Test, and Development Commands

Run app commands from `fund-baby/`:

```bash
npm install
npm run dev
npm run build
npm run start
docker build -t fund-baby .
docker compose up -d --build
```

`npm run dev` starts Next.js at `http://localhost:3000`. `npm run build` creates the production build; GitHub Pages expects static output in `out/`. Docker commands validate the CI deployment path.

Run the fund radar CLI from the repository root:

```bash
conda run -n fund python fund_radar/query_fund_estimate.py 110022 易方达消费
```

## Coding Style & Naming Conventions

Use JavaScript and JSX with ES modules. Follow the existing style: two-space indentation, semicolons, single quotes where practical, and PascalCase for React components such as `FundTrendChart`. Use camelCase for functions, variables, and hooks. Prefer CSS variables from `app/globals.css` for theme-aware styling.

## Testing Guidelines

No dedicated app test framework is configured. Before app changes, run `npm run build`. For UI changes, manually check: add a 6-digit fund code, refresh data, switch tabs, open settings, and verify mobile layout. For Python tools, add focused `unittest` coverage and run it with `conda run -n fund python -m unittest ...`.

## Commit & Pull Request Guidelines

Recent history uses short, direct commit messages in Chinese or English, for example `新用户设置默认基金`, `优化估值涨跌幅/实际涨跌幅的逻辑`, and `Update README.md`. Keep commits focused. Pull requests should describe the change, list verification, mention environment or schema updates, and include screenshots for visible UI changes.

## Security & Configuration Tips

Do not commit secrets. Public client variables must use the `NEXT_PUBLIC_` prefix and currently include Supabase URL, Supabase anon key, and Web3Forms access key. Keep database changes mirrored in `fund-baby/supabase.sql`.
