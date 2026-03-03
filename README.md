# PolyTrace — Polymarket Insider & Oracle Tracker

Track "Smart Money" wallets on Polymarket and correlate prediction market probabilities against live spot markets to find actionable trading alpha.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Data Ingestion Layer                        │
│  Gamma Poller │ CLOB Poller │ Data API │ Spot Poller │ Chain RPC│
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
                    ┌──────────────┐
                    │  PostgreSQL   │  (TimescaleDB)
                    └──────┬───────┘
                           ▼
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   Heuristics Engine  Oracle Engine   DAC Algorithm
   (Sniper/Spec/OHW)  (Lead-Lag)    (Decay Adjusted)
          └────────────────┼────────────────┘
                           ▼
                  ┌────────────────┐
                  │  FastAPI REST   │  + APScheduler
                  └────────┬───────┘
                           ▼
                  ┌────────────────┐
                  │  Next.js 15     │  Dashboard
                  └────────────────┘
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- (Optional) Polygon RPC URL from Alchemy/QuickNode for on-chain data

### 1. Configure environment
```bash
cp .env.example .env
# Edit .env with your POLYGON_RPC_URL (optional) and any overrides
```

### 2. Start everything
```bash
docker compose up -d
```

This starts:
- **PostgreSQL** (TimescaleDB) on port 5432
- **Backend** (FastAPI) on port 8000
- **Frontend** (Next.js) on port 3000

### 3. Open the dashboard
Navigate to [http://localhost:3000](http://localhost:3000).

## Local Development (without Docker)

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/smart-money/alerts` | Smart Money alerts (filter by type, hours) |
| GET | `/api/smart-money/feed` | Live alert feed |
| GET | `/api/smart-money/stats` | 24h aggregate stats |
| GET | `/api/wallet/{address}/profile` | Wallet PnL, positions, classification |
| GET | `/api/wallet/{address}/trades` | Paginated trade history |
| GET | `/api/wallet/leaderboard` | Top wallets by PnL/win rate |
| GET | `/api/oracle/signals` | Oracle divergence signals |
| GET | `/api/oracle/divergence/{condition_id}` | Price overlay data for charting |
| GET | `/api/oracle/stats` | Oracle aggregate stats |

## Heuristics Engine

Three wallet archetypes are detected:

- **Sniper** — Heavy USDC volume into a market within 4 hours of resolution
- **Niche Specialist** — Win rate > 80% across 10+ trades in a specific category
- **One-Hit Wonder** — Freshly funded wallet (<7 days old), single large bet (>$10k)

Sybil detection flags wallets that consistently trade the same markets at the same times.

## Oracle Engine (Decay Adjusted Confidence)

The DAC algorithm adjusts raw probability changes for time-to-resolution:

```
DAC(t) = |ΔP| × volume_surge × σ(TTR; k=0.15, mid=6h)
```

A sigmoid centered at 6 hours means signals far from resolution receive full weight (real alpha), while signals near resolution are discounted (mechanical decay).

## External APIs Used

- **Polymarket Gamma API** — `gamma-api.polymarket.com` (markets, events, tags)
- **Polymarket Data API** — `data-api.polymarket.com` (trades, holders, positions)
- **Polymarket CLOB API** — `clob.polymarket.com` (price history, order book)
- **Polygon RPC** — Conditional Tokens contract events (TransferSingle/Batch)
- **Binance** — BTC/ETH/SOL spot klines
- **Yahoo Finance** — SPY, Gold, Oil via yfinance

## License

MIT
