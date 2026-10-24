"""The help centre's ready-made answers.

Every entry here is answered instantly with NO call to the AI (no cost). They are also the knowledge the AI
helper is given for questions that are not on the list, so there is one source of truth: if a screen changes,
fix the answer here.
"""

FAQ: list[dict[str, str]] = [
    {
        "id": "plan",
        "topic": "Planning",
        "question": "How do I plan what to buy?",
        "answer": (
            "Open Plan purchases, choose how many days to buy for (1 to 7, starting tomorrow) and press Generate plan. "
            "In a few seconds you get a list for each supplier with what to buy, how much and when, plus a short "
            "'Why?' for every line. Managers and the owner can generate plans."
        ),
    },
    {
        "id": "order-flow",
        "topic": "Orders",
        "question": "What happens after I generate a plan?",
        "answer": (
            "Each supplier gets its own order, shown on Plan purchases under Supplier orders. 1) The manager checks or "
            "edits the quantities and presses Finish & submit. 2) The owner presses Review & place order, sends the "
            "message by WhatsApp or phone, then presses I have placed the order. The order moves to Approved. The "
            "owner can also Reject an order and say why. 3) When the delivery arrives, the manager presses Mark "
            "received and your stock updates. Every step is saved in Activity."
        ),
    },
    {
        "id": "roles",
        "topic": "Roles",
        "question": "Who can do what?",
        "answer": (
            "Owner: everything, including setup, placing or rejecting orders and Settings. Manager: plan purchases, "
            "edit and submit orders, mark deliveries received, update stock, calendar, import sales and see Activity. "
            "Staff: view stock and update quantities only. A button that is greyed out tells you which role you need."
        ),
    },
    {
        "id": "buffer",
        "topic": "Planning",
        "question": "What does the safety buffer % mean?",
        "answer": (
            "It is the extra we add on top of the forecast so you rarely run out. It is not a fixed number: we replay "
            "your past sales to see how wrong the forecast was for each ingredient, then pick the extra that would "
            "have been enough most of the time. Items that spoil fast get a smaller buffer so you do not waste food. "
            "The owner can change how careful it is in Settings (lean, balanced or never run out)."
        ),
    },
    {
        "id": "covered",
        "topic": "Planning",
        "question": "Why is an item not on my buy list?",
        "answer": (
            "Because your stock already covers it. We count only stock that will still be good (not expired) and "
            "subtract what you will use before it runs out. If you think it is wrong, check the quantity and the "
            "bought date on the Inventory page, then generate the plan again."
        ),
    },
    {
        "id": "expiry",
        "topic": "Inventory",
        "question": "How does expiry work?",
        "answer": (
            "Each purchase of an item is its own batch with its own bought date and shelf life, so chicken bought on "
            "Monday and on Tuesday expire on different days. Expiry = bought date + shelf life. Expired batches turn "
            "red, are never counted as stock, and have a Remove expired button (or Remove all expired for the lot)."
        ),
    },
    {
        "id": "add-stock",
        "topic": "Inventory",
        "question": "How do I add stock I just bought?",
        "answer": (
            "On the Inventory page, press + Add stock on the item and enter the quantity, the date you bought it and "
            "(if different) its shelf life and price. Each purchase date is kept as its own batch. For an item that is "
            "not in your list yet, press + Add item. When a delivery arrives for an order, Mark received adds it for you."
        ),
    },
    {
        "id": "add-item",
        "topic": "Inventory",
        "question": "How do I add a new item?",
        "answer": (
            "Press + Add item on the Inventory page (or in the setup step for your stock). Type the name, choose where "
            "it is kept and which supplier it comes from, say how it is sold and its price, then write how many days it "
            "stays good. Add how much you have now and the date you bought it. You can change the bought date at any time."
        ),
    },
    {
        "id": "lists",
        "topic": "Inventory",
        "question": "How do I add, rename or remove a supplier or a storage place?",
        "answer": (
            "In the Add item form, next to Supplier and Where is it kept, press Add or rename. Type a new name and press "
            "Add, or change a name in the list and press Save. You can also open it with the Suppliers and places button "
            "on the Inventory page. Managers and the owner can add and rename. Only the owner can press Remove, and if "
            "items still use it you choose where to move them. A supplier with an order in progress cannot be removed yet."
        ),
    },
    {
        "id": "ai",
        "topic": "AI",
        "question": "What does the AI do in this app?",
        "answer": (
            "The only AI is this help chat, which explains how to use the app. It cannot see your stock or sales and it "
            "cannot change anything. Forecasts, safety buffers and quantities come from your own sales history using plain "
            "maths, not AI, and a person always approves orders."
        ),
    },
    {
        "id": "sales",
        "topic": "Sales",
        "question": "How do I get my sales into the app?",
        "answer": (
            "Export your daily sales from FeedMe as a CSV file, then on the Dashboard press Import sales and choose "
            "the file. You see a summary first (days, dishes, any dishes not on your menu), and nothing is saved "
            "until you press Import. A day that is already in the app is replaced by the file's version, so "
            "re-uploading a corrected export is safe. In this demo FeedMe is a simulated screen with made-up sales."
        ),
    },
    {
        "id": "accuracy",
        "topic": "Planning",
        "question": "How accurate is the forecast?",
        "answer": (
            "The Dashboard shows it. On the demo data our forecast is off by about 13% on a typical day, against about "
            "28% for a simple 4-week average. It is measured on your own past sales, so it improves as your history "
            "grows, and holidays or events you add to the Calendar help it."
        ),
    },
    {
        "id": "calendar",
        "topic": "Calendar",
        "question": "How do I tell it about holidays, busy or slow periods?",
        "answer": (
            "Open Calendar (managers and the owner) and press Add to calendar. Choose a period (such as school "
            "holidays or Ramadan), a public holiday or a local event, then the dates. The forecast learns how each "
            "kind of period changed your sales before, so one that repeats helps more each time. Malaysian public "
            "holidays are added when you choose Malaysia in setup."
        ),
    },
    {
        "id": "supplier-details",
        "topic": "Orders",
        "question": "How do I change a supplier's WhatsApp number or minimum order?",
        "answer": (
            "On Plan purchases, open the supplier under Supplier orders and use Supplier details. A valid phone "
            "number is needed for the WhatsApp and Call buttons when you place an order. To change the supplier's "
            "name, use Add or rename in the Add item form on the Inventory page."
        ),
    },
    {
        "id": "no-pay",
        "topic": "Orders",
        "question": "Does the app send orders or pay suppliers by itself?",
        "answer": (
            "No. RestockAI prepares the order and the message. The owner sends it through WhatsApp or by phone and "
            "then confirms it was placed. The app never pays or transfers money."
        ),
    },
    {
        "id": "today",
        "topic": "Settings",
        "question": "Why does the app show a different date from today?",
        "answer": (
            "The app treats 'today' as the day after your latest sales. Importing a new day of sales moves it "
            "forward. The owner can pin a fixed demo date in Settings, which is useful for a demo or recording."
        ),
    },
    {
        "id": "reset",
        "topic": "Settings",
        "question": "How do I start over with the demo data?",
        "answer": (
            "The owner can use Settings, Reset demo data. It reloads the made-up data and starts the first-time "
            "setup again. Everyone sharing the demo sees the change, so tell your team first."
        ),
    },
]

PAGES = (
    "Dashboard: forecast accuracy, latest plan, sales from your POS (Import sales), stock health. "
    "Plan purchases: pick days, Generate plan, Supplier orders, Supplier details. "
    "Inventory: stock by batch, Add item, Add stock, Manage suppliers and places, Remove expired. "
    "Order history: past orders. Calendar: holidays, periods, events. Activity: record of every action. "
    "Settings (owner): risk setting, demo date, reset."
)


def guide_text() -> str:
    """Everything the AI helper may rely on, built from the answers above."""
    lines = [f"Pages: {PAGES}", ""]
    lines += [f"Q: {f['question']}\nA: {f['answer']}" for f in FAQ]
    return "\n".join(lines)
