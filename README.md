# 📊 Daily Institutional Intelligence Dashboard

**Real-time Market Intelligence, Portfolio Impact Analysis & Automated Investment Insights**

---

## 🎯 Overview

This is a **fully automated institutional-grade investment intelligence dashboard** for Tejas Jadhav's personal portfolio. It provides daily market analysis, expert commentary, FII/DII flows, geopolitical risk tracking, and personalized portfolio impact assessments.

**Live Dashboard:** https://tejasgjadhav.github.io/daily-dashboard

---

## ✨ Key Features

### 1. **GIFT Nifty LIVE Pre-Market Indicator**
- Captures live GIFT Nifty (NSE IX) data at 8:30 AM IST
- Shows gap vs Nifty 50 previous close
- Indicates expected opening direction (Gap-Up/Gap-Down)
- Real-time market sentiment indicator

### 2. **FII/DII Capital Flow Intelligence**
- **Equity Segment:** FII and DII buy/sell flows from previous trading day
- **FNO Segment:** Futures & Options positioning and flows
- Net sentiment analysis (Bullish/Bearish indicators)
- Impact assessment on portfolio holdings
- Identifies institutional support/resistance levels

### 3. **Trump Indicator - Geopolitical Risk Tracker**
- Latest Trump administration developments (last 24 hours)
- US-India trade and tariff policy tracking
- Court rulings and policy changes affecting markets
- Truth Social post market impact analysis
- Sentiment assessment: BULLISH/NEUTRAL/BEARISH for Indian markets
- Affected sectors identified (Tech, Defence, Manufacturing, Pharma)

### 4. **Market News Aggregation**
- Curated headlines from multiple sources:
  - Moneycontrol
  - CNBC-TV18
  - Bloomberg India
  - Economic Times
- Categorized by sector and market relevance

### 5. **Expert Commentary**
- Daily expert views from institutional analysts
- Anil Sanghvi (Emkay Global) - Defence & Capex expert
- Key insights on market catalysts and opportunities
- Sector-specific recommendations

### 6. **Personalized Portfolio Impact Analysis**
Maps daily news and market events to specific holdings:
- **Equity Holdings:** BEL, Data Patterns, HDFC Bank, HDFC AMC
- **Mutual Funds:** 20 direct-plan schemes (Axis, ICICI, Mirae Asset, Motilal Oswal, SBI, etc.)
- **Retirement:** NPS account
- **Portfolio Value:** ₹32.39 Lakhs across 4 demat accounts

For each holding, the dashboard assesses:
- Direct impact from today's news
- Sector impact (if applicable)
- Risk/Opportunity level: CRITICAL | HIGH | MEDIUM | LOW
- Action timeframe: IMMEDIATE | NEAR-TERM | EOD | WEEKLY

### 7. **Decision Framework**
Time-based action recommendations:
- **IMMEDIATE (Next 1-2 hours):** Critical market open actions
- **NEAR-TERM (Today):** Intraday management and monitoring
- **EOD (By Market Close):** Position closing and rebalancing
- **WEEKLY:** Portfolio rebalancing and strategic adjustments

### 8. **Key Market Metrics**
All metrics verified with official sources:
- Nifty 50 (NSE)
- SENSEX (BSE)
- Nifty Bank (NSE)
- India VIX (NSE)
- USD/INR (RBI Reference Rate)
- GIFT Nifty (NSE IX)

Every number includes: **[VALUE] ✅ VERIFIED from [SOURCE]**

---

## 🤖 Automation System

### How It Works

The dashboard is **fully automated** using Claude scheduled tasks + GitHub Actions:

```
8:30 AM IST Daily Trigger
        ↓
Claude Scheduled Task Runs
        ↓
Fetch LIVE Market Data (NSE/RBI)
        ↓
Gather FII/DII Intelligence
        ↓
Search Trump Latest Developments
        ↓
Aggregate News (Moneycontrol, CNBC, Bloomberg, ET)
        ↓
Extract Expert Commentary
        ↓
Map to Portfolio Holdings
        ↓
Update index.html
        ↓
Git Commit + Push
        ↓
GitHub Pages Auto-Deploy
        ↓
Website Updates Live (2-5 seconds)
        ↓
Email Confirmation Sent
```

### Daily Automation Steps

**STEP 1: Fetch Real-Time Market Data (8:30 AM IST)**
- GIFT Nifty LIVE from NSE IX
- Nifty 50, SENSEX, Nifty Bank from NSE
- India VIX from NSE
- USD/INR from RBI

**STEP 2: Gather FII/DII Intelligence**
- Equity segment flows (previous day)
- FNO segment flows (previous day)
- Calculate net positioning and sentiment

**STEP 3: Trump Geopolitical Indicator**
- Search latest Trump statements (24-hour window)
- US-India relations and trade developments
- Court rulings affecting tariffs/policy
- Truth Social market impact assessment

**STEP 4: Market News Aggregation**
- Search Moneycontrol for latest market news
- Search CNBC-TV18 for expert analysis
- Search Bloomberg India for global context
- Search Economic Times for policy updates

**STEP 5: Extract Expert Commentary**
- Anil Sanghvi views on defence sector
- Other institutional analyst perspectives
- Key insights and catalysts

**STEP 6: Portfolio Impact Analysis**
- Map news items to specific holdings
- Assess impact level and timeframe
- Generate decision recommendations

**STEP 7: Update Dashboard**
- Replace outdated data with fresh metrics
- Update portfolio impact section
- Refresh action framework
- Add timestamp showing update time

**STEP 8: Commit & Deploy**
- Git add index.html
- Git commit with timestamp message
- Git push to GitHub (authenticated)
- GitHub Pages automatically deploys

**STEP 9: Send Confirmation Email**
- Email to tejasipsjadhav@gmail.com
- Summary of today's key metrics
- Portfolio impact highlights
- Link to live dashboard

---

## 🛟 Fallback: when the Claude API has a bad day

`scripts/update_dashboard.py` calls the Claude API first. If that call
errors out (rate limit, outage, auth failure) after retries, or comes back
malformed (no HTML block, missing sections, suspiciously short), the script
does **not** just give up and leave the dashboard stale — it automatically
retries the exact same prompt against free, web-grounded open models served
through [Puter.com](https://puter.com)'s OpenAI-compatible API (no
Perplexity/OpenAI key required, just a one-time free Puter token):

```
Claude API (primary)
        ↓ fails / bad response
perplexity/sonar-pro          (Puter, free)
        ↓ fails / bad response
perplexity/sonar-reasoning-pro (Puter, free)
        ↓ fails / bad response
perplexity/sonar              (Puter, free)
        ↓ all failed
exit 5 — dashboard left untouched, logs explain why
```

Perplexity's Sonar models were chosen for the fallback because they do
real-time web search natively (same need as Claude's `web_search` tool) —
so the fallback still produces genuinely fresh market commentary, FII/DII
flows, news, and portfolio impact analysis instead of a hallucinated
placeholder.

Configuration (all via env vars / GitHub Actions secrets):

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | one of these two | — | primary Claude provider |
| `PUTER_TOKEN` | one of these two | — | enables the free fallback chain |
| `FALLBACK_MODELS` | no | `perplexity/sonar-pro,perplexity/sonar-reasoning-pro,perplexity/sonar` | fallback order |
| `FALLBACK_MAX_TOKENS` | no | `8000` | output budget per fallback call |

If `ANTHROPIC_API_KEY` is missing entirely, the script skips straight to
the fallback chain — useful if the Anthropic key is ever revoked or hits a
billing issue but the dashboard still needs to update.

---

## 📁 File Structure

```
daily-dashboard/
├── index.html              # Main dashboard (auto-updated daily)
├── README.md              # This file
└── .github/
    └── workflows/
        └── deploy.yml     # GitHub Actions deployment workflow
```

### index.html
- Single-page HTML application
- Dark-mode professional styling (gradient backgrounds)
- Responsive grid layouts
- Real-time clock updates
- All data verified with sources

### .github/workflows/deploy.yml
- Scheduled trigger: Daily at 3:00 AM UTC (8:30 AM IST)
- Automatically deploys any committed changes
- Uses GitHub Pages for hosting

---

## 🔗 Data Sources

All data is **VERIFIED** from official sources:

| Metric | Source | Update Frequency |
|--------|--------|------------------|
| GIFT Nifty | NSE IX | Daily 8:30 AM IST |
| Nifty 50 | NSE | Daily market close |
| SENSEX | BSE | Daily market close |
| Nifty Bank | NSE | Daily market close |
| India VIX | NSE | Daily market close |
| USD/INR | RBI Reference Rate | Daily |
| FII/DII Flows | NSE/BSE | Previous day close |
| Trump Developments | Official statements, court filings | Last 24 hours |
| Market News | Moneycontrol, CNBC, Bloomberg, ET | Real-time |

---

## 📊 Portfolio Overview

**Total Portfolio Value:** ₹32,39,104

### Equity Holdings (Direct)
- **Bharat Electronics (BEL):** 317 shares | ₹127,006 (3.92%)
- **Data Patterns:** 35 shares | ₹106,236 (3.28%)
- **HDFC Bank:** 80 shares | ₹58,524 (1.81%)
- **HDFC AMC:** Holdings tracked

### Mutual Funds
- **20 Direct-Plan Schemes** across 4 demat accounts
  - Axis Funds
  - ICICI Funds
  - Mirae Asset
  - Motilal Oswal
  - SBI Funds
  - Others

### Retirement
- **NPS Account** (National Pension Scheme)

---

## 📈 Daily Dashboard Sections

### 1. GIFT Nifty Indicator
Pre-market signal at top of dashboard with:
- Live GIFT Nifty level
- Change % and gap vs previous close
- Expected opening direction
- Range for the day
- Time of capture (8:30 AM IST)

### 2. Summary Box
High-level overview of today's critical events, portfolio impact, and key recommendations

### 3. Top Priority Events
Timestamped listing of major events affecting the portfolio today:
- RBI announcements
- Corporate earnings
- Economic data releases
- Market opens/closes
- Policy decisions

### 4. FII/DII Intelligence
Table showing:
- Equity segment flows (previous day)
- FNO segment flows (previous day)
- Net sentiment (Bullish/Bearish)
- Impact on specific holdings
- Key insights on institutional positioning

### 5. Trump Indicator
Geopolitical risk tracker showing:
- Latest Trump administration developments
- US-India relations status
- Trade and tariff impacts
- Risk assessment
- Portfolio implications

### 6. Expert Market Views
Daily expert commentary with:
- Analyst name and affiliation
- Key quotes and insights
- Sector-specific recommendations
- Price targets (if applicable)

### 7. Your Portfolio Impact
Grid layout showing impact on each major holding:
- Holdings affected today
- Impact type (positive/negative/neutral)
- Recommended action (Buy/Hold/Reduce)
- Risk level assessment

### 8. Action Framework
Time-based decision recommendations:
- **IMMEDIATE:** Market open actions
- **NEAR-TERM:** Today's intraday moves
- **EOD:** End-of-day closing decisions
- **WEEKLY:** Strategic rebalancing

### 9. Key Metrics
Dashboard of live market indicators:
- All major indices (Nifty, Bank, Sensex)
- Volatility (VIX)
- Currency (USD/INR)
- Market structure analysis

### 10. Recent News
Curated news headlines from:
- Moneycontrol
- CNBC-TV18
- Bloomberg
- Economic Times

---

## 🎨 Design & UI

- **Color Scheme:** Dark mode (professional/institutional look)
- **Gradient Backgrounds:** Blue (#1F3864 → #2C5AA0) and accent colors
- **Impact Badges:** Color-coded (Red=CRITICAL, Yellow=HIGH, Green=POSITIVE)
- **Responsive Design:** Works on desktop, tablet, mobile
- **Live Clock:** Real-time IST clock updates at bottom
- **Status Indicator:** Pulsing green dot showing live update status

---

## ⚙️ Setup & Deployment

### Prerequisites
- GitHub account with repository access
- `ANTHROPIC_API_KEY` repo secret (primary generator) — and/or
- `PUTER_TOKEN` repo secret (enables the free fallback chain — see
  "Fallback" section above; get one free at https://puter.com)
- GitHub Pages enabled on repository

### GitHub Pages Setup
1. Repository: `tejasgjadhav/daily-dashboard`
2. Branch: `main`
3. Source: Root folder
4. URL: `https://tejasgjadhav.github.io/daily-dashboard`

### Daily Automation
- Scheduled task runs at 8:30 AM IST
- Fetches verified data from NSE, RBI, news sources
- Updates `index.html` with fresh data
- Commits and pushes to GitHub
- GitHub Pages auto-deploys within 2-5 seconds
- Email confirmation sent to inbox

---

## 📊 Data Accuracy & Validation

**All metrics are VERIFIED:**
- ✅ Market data from official NSE/BSE/RBI sources
- ✅ FII/DII flows from NSE official reports
- ✅ Trump information from official statements and court records
- ✅ News aggregated from established financial media
- ✅ Expert commentary from verified institutional analysts
- ✅ Timestamps showing when data was captured and source

**No placeholder values.** Every number in the dashboard is validated and sourced.

---

## 🔐 Security & Privacy

- Dashboard is public read-only (no authentication required)
- Personal portfolio data anonymized where necessary
- No sensitive banking information stored
- GitHub authentication via Personal Access Token (PAT)
- All communications over HTTPS

---

## 📧 Email Notifications

Daily confirmation email includes:
- Subject: ✅ Daily Dashboard Updated - [DATE]
- GIFT Nifty LIVE data
- FII/DII flow summary
- Trump indicator update
- Key portfolio holdings impact
- Link to live dashboard
- Time of update (IST)

---

## 🎯 Use Cases

### For Daily Trading
- Check GIFT Nifty at 8:30 AM to assess market direction
- Review FII/DII flows to understand institutional sentiment
- Read expert views for intraday catalysts
- Monitor portfolio impact section for position management

### For Weekly Portfolio Reviews
- Assess portfolio impact from week's developments
- Review Trump geopolitical changes
- Identify rebalancing opportunities
- Check expert recommendations for adjustments

### For Long-Term Strategic Planning
- Track Trump administration policy shifts
- Monitor defence sector (BEL, Data Patterns) opportunities
- Assess FII outflow trends vs DII accumulation
- Plan capital allocation adjustments

---

## 🚀 Automation Features

✅ **Fully Automated:** No manual updates needed  
✅ **Daily at 8:30 AM IST:** Consistent timing, every day  
✅ **LIVE Data:** Captured at exact time, not cached  
✅ **Verified Sources:** Every metric linked to official source  
✅ **Personalized:** Mapped to your specific holdings  
✅ **Deployed Automatically:** GitHub Pages updates instantly  
✅ **Email Confirmed:** Inbox notification every day  
✅ **Always Accurate:** Real data, no placeholders  

---

## 📞 Support & Updates

For questions, issues, or feature requests:
- Check the live dashboard: https://tejasgjadhav.github.io/daily-dashboard
- Review this README for automation details
- Email confirmation shows last update time and status

---

## 📅 Version History

**v1.0 - May 10, 2026**
- Initial launch with GIFT Nifty, FII/DII, Trump Indicator
- Full automation setup
- Daily 8:30 AM IST scheduled task
- GitHub Pages deployment
- Email notifications

---

## 💡 Key Insights

### Your Portfolio Positioning
- **Heavy Defence Exposure:** BEL (3.92%) + Data Patterns (3.28%) = 7.2% in defence theme
- **Banking Stability:** HDFC Bank (1.81%) provides dividend yield and stability
- **Mutual Fund Diversification:** 20 schemes across multiple asset classes
- **NPS Retirement:** Long-term tax-advantaged growth

### Market Dynamics
- FIIs pulling $21B in 2026 (headwind)
- DIIs accumulating quality names (support)
- Defence sector benefits from Trump administration preference
- Tech sector at risk from US tariff policy uncertainty

### Institutional Strategy
- Counter-trend accumulation in defence on FII selling
- Position against global market divergence (Nifty -8% vs global +30-150%)
- Benefit from India's manufacturing shift opportunities
- Hedge geopolitical uncertainty with quality holdings

---

## 🎓 Educational Value

This dashboard demonstrates:
- Institutional investment analysis frameworks
- Daily market intelligence gathering
- Portfolio-specific impact mapping
- Geopolitical risk assessment
- Automated data pipeline design
- GitHub Pages deployment patterns

---

**Dashboard Status:** ✅ LIVE | ✅ AUTOMATED | ✅ VERIFIED DATA

Last Updated: May 10, 2026 8:30 AM IST
