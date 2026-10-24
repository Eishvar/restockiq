# How good is the RestockAI forecast? A plain-language audit

Written 24 Oct 2026. **All numbers come from simulated restaurants and our own synthetic demo data. No real restaurant's sales were used, because none exist for this project. Treat the results as "the method is sound and we know where it is weak", not as a promise of accuracy in a real kitchen.**

The forecasting maths contains no AI. It is ordinary statistics (weekday pattern, recent level, holidays, dish mix). The only AI in the product is the Help chat.

## What we did

We built a second, independent "messy restaurant" simulator, on purpose different from the one that made our demo data, so a good score cannot just mean "the model matches the way we made the data". It includes holidays, surprise events, one-off big days, growth, closed days, missing days, sold-out dishes and menu changes.

We then pretended to be the app on many past days: use only what was known on that day, plan the next 7 days, and compare with what really sold. We did the same with six standard methods (last week's numbers, a 4-week average, same-weekday average, Holt-Winters, a ridge regression and a gradient-boosting model), so we can say whether our own method is worth having.

## Result 1: the forecast beats the standard methods

Error on daily sales totals (lower is better; 7-day plans over the last 52 weeks; 8 types of restaurant, 2 simulated restaurants each):

| | RestockAI | Holt-Winters | Ridge | Gradient boosting | Same weekday, 4 wks | Last week | 4-week average |
|---|---|---|---|---|---|---|---|
| Typical restaurant | **15.7%** | 16.7% | 16.7% | 16.8% | 18.8% | 23.3% | 21.6% |
| Our own demo data | **13.9%** | 17.8% | 16.2% | 19.7% | 24.2% | 20.6% | 26.8% |

- Across all 8 types, RestockAI's error was 12% to 22%. It was the lowest, or within about 0.1 points of the lowest, in every type.
- Even a perfect model cannot get below the randomness of real days. In the simulation that floor is about 8 to 9% for a typical restaurant (up to 13.5% for a small cafe).
- Accuracy is nearly the same for tomorrow and for 7 days ahead (for example 16.3% vs 16.4%).
- Holiday and event days are harder: about 25% error against about 14% on normal days.

## Result 2: the safety buffer is mostly honest

The buffer adds extra stock so that you run short only rarely. "90% buffer" should be enough on about 90% of days. We checked this on days the buffer had never seen:

| Promised | 80% | 90% | 95% |
|---|---|---|---|
| Delivered, 2 years of history | 79.3% | 88.3% | 92.7% |
| Delivered, first year of data (our demo data) | about 76% | about 81% | about 85% |

- With a long history the buffer is slightly short of its promise (1 to 2 points), but close, and the same for every horizon.
- In the first year it falls further behind (up to 9 points at the 90% level). The reason is that the demo year contains changes that the buffer had not yet seen. We tried a "small-sample" correction. It added about 1.7 points of coverage but made small buffers much bigger (chicken breast from 29% to 41% with about 30 past cases, meaning more waste). **We rejected it and left the buffer as it was.**
- Plans made 3 days apart overlap, so their errors move together (correlation +0.65 for 7-day plans). In practice, a bad week tends to be short on several plans at once, not one.

## Result 3: how much history the app needs

| History available | Error | Plain 4-week average |
|---|---|---|
| 14 days | 21.4% | 22.4% |
| 28 days | 18.8% | 22.0% |
| 56 days | 17.3% | 22.0% |
| 90 days (about 3 months) | 16.9% | 22.0% |
| 180 days | 16.7% | 22.0% |
| 1 year | 16.5% | 22.0% |
| 1.5 years | 16.4% | 22.0% |

So the app already beats a plain average after about 4 weeks, and gains little after about 3 months. That is why the Help guide says about 3 months of history is best. A trick to improve the first two weeks would gain only about 1 point, so we did not add it.

## What we changed because of the audit

Two real weaknesses showed up and are now fixed (with tests):

1. **A day the shop is always closed.** Before, a weekday with no sales ever (for example every Monday) gave an empty (not-a-number) forecast. In the closed-Monday simulation, **all 360 test forecasts failed** with the old code and none fail now. A normal-day zero is now treated as "closed", left out of the level and weekday maths, and the day forecasts 0. Holiday closures are still learned from the calendar.
2. **A dish that has stopped selling.** A dish with no sales for 28 days, although it normally sells at least 5 in that time, now gets a share of 0 instead of lingering in the plan. Averaged over the 10 simulated restaurant types, this lowered the 3-day ingredient-need error from 18.6% to 18.3% (0.3 points). It matters most when the menu keeps changing: 18.5% to 17.7% (0.8 points) for the "menu churn" restaurant.

On our original demo data the forecasts did not change at all, so the demo plans are the same as before.

## What we tried and did NOT change

Small tuning ideas, each tested alone on top of the fixed engine (30 simulated restaurants, 10 types):

| Idea | Daily-total error change | Ingredient-need (3-day) change |
|---|---|---|
| "Recent level" over 21 days instead of 14 | -0.19 points | -0.14 points |
| "Recent level" over 28 days | -0.26 points | -0.20 points |
| Same, 21 days, ignoring extreme days | -0.30 points | -0.23 points |
| Dish mix: weight recent sales fully | 0.00 points | -0.23 points |
| Split the holiday effect into before / on / after | -0.25 points | -0.09 points |

These helped the simulated restaurants by only 0.1 to 0.3 points. The holiday split was the one outlier: it helped a restaurant that closes on holidays by 1.2 points. On our own demo data the same ideas made the daily-total error slightly worse (for example 13.76% to 14.01% for the holiday split). A gain this small in one place, and a loss in another, is not worth changing the demo before a deadline. They are listed as possible later improvements.

## Awkward data we checked

Random closure days, 5% of days missing, 5 to 180 days of history, one huge catering day (8 times normal, it barely moves the plan), no calendar at all, a 3-week hole in the data, and a brand-new holiday label (the app then falls back to the recent level instead of guessing). All behaved sensibly. These checks are in `edge_cases.py`; they print results and there is no saved output file.

## Known gaps (not fixed)

These are honest limits, and the main risks for a real deployment:

1. **Supplier delivery days and lead times are stored and editable but not used by the buying maths.** The plan can say "buy Tuesday" for a supplier who only delivers Monday and Thursday. This is the biggest gap. Fixing it would change the demo plans, so it is the first thing to fix after the demo. The owner reviews every order before it goes out, but the app does not warn about a wrong delivery day yet.
2. **Sold-out days hide real demand.** If a dish sells out at 2 pm, sales show a number below true demand and the forecast learns it. The sales files carry no "ran out" flag, so the app cannot know.
3. **Ingredient waste and yield are not modelled.** The ingredient list has a waste percentage, but it is not used yet.
4. **Buffers are re-measured only** at setup, when the calendar or risk setting changes, when 7 or more new days of sales are imported, and when the owner presses Recompute.
5. **One holiday effect** covers the day before, the day of and the day after, for all holidays.
6. **A new holiday label** has no effect until it has happened once.

## Hardest risk, and the fallback

The hardest risk is that real sales behave in ways our simulations do not (for example a long stretch of sold-out days, or a promotion nobody told the app about). The fallback is built in: every purchase line shows its safety buffer, the owner approves or edits each order before it is sent, the app never pays or sends money, and every decision is written to the activity log. When there are fewer than 12 past cases the app uses a default 15% buffer instead of a measured one.

## Reproduce it

Everything is in `research/forecast_audit/`. See [README.md](README.md) there. Please read the results as simulated, and re-check them on a real restaurant's data (with the owner's permission, under PDPA) before relying on any figure.
