HOW RESTOCKAI WORKS (plain-language notes for the help chat)

This file is read by the Help chat for questions that are not on the ready-made list. Write it in everyday words.
When a screen or a rule changes, change the matching section here. No code, no secrets, no business data.

== THE BIG PICTURE ==
RestockAI works out what a kitchen should buy for the next 1 to 7 days. It learns from your own sales history, turns
the expected dishes into ingredients, adds a safety margin, subtracts the stock you already have, rounds up to
whole supplier packs and prices the result. It makes one list per supplier. People stay in control: a manager
prepares the order and the owner places it. The app never pays or sends anything by itself. It is statistics and
arithmetic, not AI. The AI is only this help chat.

== HOW THE FORECAST WORKS (step by step) ==
The forecast predicts how many dishes you will sell on each future day, using only your own past sales.
1. Daily total. Add up all dishes sold each day. Days with no sales count as zero.
2. Weekday pattern. Fridays may be busier than Mondays. The app measures how much busier or quieter each weekday
   usually is, using normal days only (not holidays or events).
3. Calendar level. The calendar marks periods such as semester, break or school holidays. The app learns the
   usual number of dishes for each kind of period from your history. Near the edge of a period it blends the
   levels of the days around it, because customers drift in and out gradually.
4. Holidays and events. Public holidays (and the day before and after) and local events changed your sales in the
   past. The app measures how much, compared with the days around them. If it has seen few examples it trusts that
   measurement less and moves it toward "no change".
5. Recent strength. The app checks how busy the last 2 weeks were compared with the usual level. This is how it
   notices growth or decline by itself, so nobody has to type in a growth percentage.
6. Put together: expected dishes for a day = usual level for that period x recent strength x weekday pattern x
   holiday or event effect.
7. Splitting into dishes. The day's total is shared between dishes by how popular each one has been, mostly the last
   28 days and partly all history. A brand-new dish (launched in the last 60 days) uses only the recent weeks.
   Each menu category's own weekday pattern is also used, for example breakfast dishes can sell more on weekdays.
If there is little history (under about 8 weeks) the app uses a simpler method, a 4-week average with the weekday
pattern, and says so. It needs about 3 months of sales to reach most of its accuracy.
Closed days: a weekday the shop is always closed on is forecast as zero, and an ordinary day with no sales at all
is treated as a closure, not as "demand was zero", so it does not pull the forecast down. Closing on a public
holiday is still learned, as part of the holiday effect. A dish that has sold nothing for four weeks, although it
normally would have, is treated as gone from the menu and gets no forecast.
Accuracy: Plan purchases shows how far off the forecast was when replayed on your past sales. On the demo data it
is off by about 13% on a typical day, against about 21% for "same weekday last week" and 28% for a plain 4-week
average. Single dishes are harder to predict than the daily total, which is why the plan works with ingredients,
where the errors partly cancel out.

== FROM DISHES TO INGREDIENTS ==
Each dish has a recipe. The amount of an ingredient needed on a day is the sum, over all dishes, of dishes expected
x the amount of that ingredient in one serving. A dish with no recipe cannot be turned into ingredients and is
flagged for a person to fix. Recipes are kept on the Recipes page: Edit a dish to choose its ingredients and the
amount in one serving (grams, millilitres or pieces), or press + Add a dish for a new one (use the name the till
prints). First-time setup has a Recipes step that cannot be skipped: every
dish must have a recipe before setup can finish, and an example recipe is filled in for each dish. A recipe change is
used the next time a plan is generated, and the safety buffers are measured again afterwards.

== THE SAFETY BUFFER (extra on top of the forecast) ==
A forecast is never exact, so a little extra is added. The extra is not one fixed percentage, because it depends on
how unpredictable each ingredient is and for how many days you buy.
- The app replays your history many times (about 80 starting points over the last 34 weeks) and asks for each
  ingredient: if I had planned then, how far off would I have been?
- It then picks the extra that would have been enough in most past cases. How sure it tries to be depends on the
  shelf life and on the owner's risk setting in Settings: lean, balanced or never run out.
  Short-life items (under 7 days) use lower certainty, because leftovers spoil. Long-life items (30 days or more)
  use higher certainty, because leftovers keep and running out costs more. Balanced uses about 80%, 90% and 95%
  for short, medium and long life.
- The buffer is capped between 0% and 60%. With fewer than 12 past examples (a new restaurant or a new ingredient)
  it uses a default of 15% and marks it as "default until we learn your pattern".
- Buying for fewer days needs a larger percentage, because errors average out over longer periods.
Every purchase line shows its buffer percentage.

== STOCK, EXPIRY AND SHELF LIFE ==
- Every purchase is a batch with its own bought date, shelf life and price, so the same item bought on different
  days expires on different days. Expiry = bought date + shelf life.
- Expired stock is never counted as stock. It appears in red with a Remove expired button.
- The plan goes day by day. Each day it first drops expired batches and uses the oldest stock first. When stock
  would run short on a day, it buys on that day enough for the days that purchase can still cover before it
  expires. So fast-spoiling items are bought in several trips, and long-life items may need nothing for a week.
- Leftovers (from the buffer and from whole packs) carry forward while still fresh, so later trips buy less.

== PACKS, PRICES AND ORDERS ==
- The amount to buy = target (forecast plus buffer) minus usable stock, rounded UP to whole supplier packs, then
  multiplied by the pack price. Each line has a "Why?" explaining its numbers in words.
- One list per supplier with a subtotal, and a grand total. A supplier below its minimum order is flagged.
- An item that no recipe uses is flagged so a person can check it.
- Order steps: manager edits quantities and presses Finish and submit. The owner presses Review and place order,
  sends the message by WhatsApp or phone, then presses I have placed the order. The owner can also Reject with a
  reason. When the delivery arrives the manager presses Mark received and stock updates. Everything is saved in
  Activity.

== THE CALENDAR ==
Managers and the owner can add periods (such as school holidays or Ramadan), public holidays and local events. The
forecast learns from how each kind of period changed past sales, so one that repeats helps more each time. A brand
new kind of period with no history cannot change the forecast yet, but it is recorded and starts to help once it has
happened before. Malaysian public holidays are added when you choose Malaysia in setup.

== SALES HISTORY ==
Forecasts use the sales history already stored in the app. The demo includes synthetic sales for its sample
menu. There is no sales-system connection or sales upload feature. The app's "today" is the day after its latest sales.

== WHO CAN DO WHAT ==
Owner: everything, including setup, placing and rejecting orders, removing suppliers and places, and Settings.
Manager: plan purchases, edit and submit orders, mark received, update stock, add or rename suppliers and places,
edit recipes and add dishes, calendar, Activity. Staff: view stock and update quantities only.

== LIMITS OF THIS HELP CHAT ==
It explains how the app works. It cannot see your stock, sales, plans or orders, cannot change anything, and cannot
give financial or legal advice. It is not a license to promise results.
