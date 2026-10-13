# Atrium return analyzer: design

Agreed 13 Oct 2026. Builds on the What-if Studio engine (Plan 3), fund orders (Plan 3) and the order ticket with the Pre-trade Guardian (Plan 4).

## Why

Someone landing on Atrium wants one answer before anything else: "if I put this much into this, for this long, what could it become?" The What-if Studio answers that, but only for signed-in investors, only for house funds, and as a comparison tool rather than a simple question. Nothing turns an answer into an investment.

## Who it is for

Anyone on the front door, signed in or not, and investors who want to act on what they saw.

**Success:** a visitor picks a type, an investment, an amount and a duration, and within a few seconds sees how the money could grow, what the unit price has done (for a fund), and what the numbers rest on. An investor can turn that into a fund order or a share order in one step; a visitor can turn it into an application an advisor picks up with the analysis attached.

## Decisions

1. **Inputs, in order.**
   1. Type: **unit trust** (an Atrium house fund) or **shares** (one of the 30 stocks or 17 ETFs Atrium quotes).
   2. Investment: the fund, or the stock or ETF.
   3. One-time amount: **required** for every type. For a unit trust it must meet the fund's minimum.
   4. Monthly amount: **unit trusts only**, optional, at least $50 when given (the monthly-plan minimum). Shares have no monthly amount; the field is not shown and the API refuses one.
   5. Duration: 1 to 40 years.
2. **Simulation for every type.** The What-if engine runs for both:
   - unit trusts on the fund's monthly history since June 2007, net of the fund fee;
   - shares on that stock's or ETF's own monthly history from `market_monthly.csv`, with no fund fee.

   The output is the same for both: the fan of outcomes by year (10th, 25th, median, 75th, 90th percentile), money paid in, the chance of ending below it, and the final range.
3. **Guarding against hindsight for shares.** The 30 stocks are today's largest companies, so their histories flatter them. For shares:
   - the S&P 500 (SPY) is simulated on the same drawn months and drawn as a comparison line;
   - the history window and the worst 12 months are shown beside the result;
   - a share needs at least 10 years of monthly history to be analysed (every current one has);
   - the disclosure names the selection effect.
4. **Unit price chart for unit trusts.** A line chart of the fund's unit price with ranges 1Y, 2Y and "Since 2007":
   - published daily unit prices where they exist;
   - before the fund's launch, the monthly backtest chained to the first published price, drawn dashed and labelled "backtest".

   It shows the start-to-end change and the largest fall in the range shown.
5. **Public, on the front door.** A section "See what your money could become" sits above "Choose a person". No sign-in is needed.
   - Each analysis is saved (inputs, summary figures, device and hashed IP, the person if signed in), so it can be rate-limited and later linked to what it led to.
   - Rate limit: 30 analyses an hour per device or network, and 600 an hour in all.
6. **The AI explanation** (Gemini Flash, figures checked) is offered only to signed-in people. Visitors get the figures and charts, which need no AI. This keeps anonymous use free of AI cost.
7. **Disclosure.** Under every result, in plain words, following FINRA Rule 2214 for investment analysis tools:
   - how it works: simulated paths stitched from 12-month blocks of real monthly returns, the window used, the fee;
   - its limits: past returns, no taxes, prices only;
   - that results vary with the inputs and as new months are added;
   - for shares, that the list was chosen today, so its history flatters it;
   - that the results are hypothetical, not actual investment results and not a guarantee.
8. **Turning an analysis into an investment.**

   | Who | Unit trust | Shares |
   |---|---|---|
   | Signed-in investor | Fund orders opens with the fund and one-time amount filled in and, if a monthly amount was given, the monthly plan filled in too. The usual preview, minimum and risk-band acknowledgement apply. | The stock's page opens with the order ticket set to buy the whole number of shares the amount buys at the live price, with the leftover cash shown. The Pre-trade Guardian applies as always. |
   | Visitor (or staff) | "Talk to an advisor about this plan" opens the prospect form with the amount, monthly amount and years filled in. The lead carries the analysis, and the advisor sees it on the lead page. | Same |

   The fund order, monthly plan, share order and lead each record the analysis they came from.

## Out of scope

- Monthly purchases of shares.
- Mixes of several funds or shares in one analysis (the What-if Studio keeps doing that for investors).
- Changes to the Guardian, the fund-order checks or the prospect form's scoring.

## Testing

- **API unit tests:**
  - the input rules (one-time amount required, monthly only for unit trusts, the fund minimum, 10 years of share history);
  - share simulation and the SPY comparison on the same draws;
  - rate limits;
  - the unit price history join at launch;
  - analysis links on leads, fund orders, monthly plans and share orders, including an analysis for a different fund or symbol being refused.
- **Web unit tests (Vitest):** input rules, whole shares from an amount, and the link parameters built and read back.
- **Gates:** `uv run pytest`; `pnpm tsc --noEmit`, `pnpm lint` and `pnpm vitest run`.
- **Visual check:** the front door at 1280 and 390 px, with no horizontal page scroll at 390.
- **After deploy:** one analysis of each type on the live site, signed out and signed in, and one conversion of each kind.
