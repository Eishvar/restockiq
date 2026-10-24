"""The help centre's ready-made answers.

Every entry here is answered instantly with NO call to the AI (no cost). Answers are short bullet points on
purpose. The most relevant ones are also given to the AI helper for questions that are not on the list, together
with the longer guide.md, so there is one source of truth: if a screen changes, fix the answer here.
"""
from pathlib import Path

FAQ: list[dict[str, str]] = [
    {
        "id": "forecast",
        "topic": "Planning",
        "question": "How does the forecast work?",
        "answer": (
            "- It predicts dishes per day from your own sales history.\n"
            "- It uses the usual level for the kind of period (semester, break), your weekday pattern and how busy the last 2 weeks were.\n"
            "- Holidays and events it has seen before change the number.\n"
            "- Dishes become ingredients using your recipes, then a safety buffer is added.\n"
            "- Your usable stock is taken off and the rest is rounded up to whole packs.\n"
            "- There is no AI in it, only your own numbers."
        ),
    },
    {
        "id": "plan",
        "topic": "Planning",
        "question": "How do I plan what to buy?",
        "answer": (
            "1. Open Plan purchases.\n"
            "2. Choose how many days to buy for (1 to 7).\n"
            "3. Press Generate plan.\n"
            "4. Check the list for each supplier. Press Why? on a line to see its numbers.\n"
            "- Managers and the owner can generate plans."
        ),
    },
    {
        "id": "order-flow",
        "topic": "Orders",
        "question": "What happens after I generate a plan?",
        "answer": (
            "- Each supplier gets its own order, under Supplier orders on Plan purchases.\n"
            "- The manager checks the quantities and presses Finish & submit.\n"
            "- The owner presses Review & place order, sends the message by WhatsApp or phone, then presses I have placed the order.\n"
            "- The order moves to Approved. The owner can also Reject it with a reason.\n"
            "- When the delivery arrives, the manager presses Mark received and stock updates.\n"
            "- Every step is saved in Activity."
        ),
    },
    {
        "id": "roles",
        "topic": "Roles",
        "question": "Who can do what?",
        "answer": (
            "- Owner: everything, including setup, placing or rejecting orders, removing suppliers and Settings.\n"
            "- Manager: plan, edit and submit orders, mark received, update stock, recipes and calendar.\n"
            "- Staff: view stock and update quantities only.\n"
            "- A greyed-out button tells you which role you need."
        ),
    },
    {
        "id": "buffer",
        "topic": "Planning",
        "question": "What does the safety buffer % mean?",
        "answer": (
            "- It is extra stock added on top of the forecast, so you rarely run out.\n"
            "- We replay your past sales to see how wrong the forecast was for each ingredient.\n"
            "- Then we pick the extra that would have been enough most of the time.\n"
            "- Fast-spoiling items get less extra, so you waste less.\n"
            "- The owner can change how careful it is in Settings (lean, balanced, never run out)."
        ),
    },
    {
        "id": "covered",
        "topic": "Planning",
        "question": "Why is an item not on my buy list?",
        "answer": (
            "- Your stock already covers it.\n"
            "- Only stock that is still good (not expired) is counted.\n"
            "- If it looks wrong, check the quantity and bought date on Inventory, then generate the plan again."
        ),
    },
    {
        "id": "expiry",
        "topic": "Inventory",
        "question": "How does expiry work?",
        "answer": (
            "- Each purchase is its own batch, with its own bought date and shelf life.\n"
            "- Expiry = bought date + shelf life.\n"
            "- Expired batches turn red and are never counted as stock.\n"
            "- Use Remove expired (or Remove all expired) to clear them."
        ),
    },
    {
        "id": "add-stock",
        "topic": "Inventory",
        "question": "How do I add stock I just bought?",
        "answer": (
            "- On Inventory, press + Add stock on the item.\n"
            "- Enter the quantity and the date you bought it. Shelf life and price can be changed.\n"
            "- Each purchase date is kept as its own batch.\n"
            "- For an item that is not in your list, use + Add item / supplier / place.\n"
            "- Mark received on an order also adds stock for you."
        ),
    },
    {
        "id": "add-item",
        "topic": "Inventory",
        "question": "How do I add a new item?",
        "answer": (
            "1. On Inventory, press + Add item / supplier / place.\n"
            "2. Type the name. Choose where it is kept and the supplier.\n"
            "3. Say how it is sold, its price and how many days it stays good.\n"
            "4. Enter how much you have and the date you bought it.\n"
            "5. Press Add item."
        ),
    },
    {
        "id": "recipes",
        "topic": "Inventory",
        "question": "How do I set or change what goes into a dish?",
        "answer": (
            "1. Open Recipes and find the dish (use the search box).\n"
            "2. Press Edit. Choose each ingredient and type the amount in one serving (g, ml or pcs).\n"
            "3. Press Save recipe. The next plan you generate uses it.\n"
            "- + Add a dish creates a new dish with its recipe. Use the name your till prints.\n"
            "- Every dish needs a recipe. Managers and the owner can edit."
        ),
    },
    {
        "id": "lists",
        "topic": "Inventory",
        "question": "How do I add, rename or remove a supplier or a storage place?",
        "answer": (
            "- Press + Add item / supplier / place, then use the link next to Supplier or Where is it kept.\n"
            "- Type a new name and press Add, or change a name and press Save.\n"
            "- Managers and the owner can add and rename. Only the owner can Remove.\n"
            "- If items still use it, you choose where to move them.\n"
            "- A supplier with an order in progress cannot be removed yet."
        ),
    },
    {
        "id": "ai",
        "topic": "AI",
        "question": "What does the AI do in this app?",
        "answer": (
            "- The only AI is this help chat. It explains how to use the app.\n"
            "- It cannot see your stock or sales, and it cannot change anything.\n"
            "- Forecasts, buffers and quantities come from your own sales and plain maths.\n"
            "- A person always approves orders."
        ),
    },
    {
        "id": "sales",
        "topic": "Sales",
        "question": "Where do the sales used for forecasts come from?",
        "answer": (
            "- Forecasts use the sales history already stored in the app.\n"
            "- This demo includes made-up sales for the sample menu.\n"
            "- There is no sales-system connection or sales upload feature."
        ),
    },
    {
        "id": "accuracy",
        "topic": "Planning",
        "question": "How accurate is the forecast?",
        "answer": (
            "- Plan purchases shows it, on the forecast card.\n"
            "- On the demo data we are off by about 13% on a typical day, against about 28% for a simple 4-week average.\n"
            "- It is checked on your own past sales, so it improves as your history grows.\n"
            "- Holidays and events you add to the Calendar help."
        ),
    },
    {
        "id": "calendar",
        "topic": "Calendar",
        "question": "How do I tell it about holidays, busy or slow periods?",
        "answer": (
            "- Open Calendar (managers and the owner) and press Add to calendar.\n"
            "- Choose a period (like school holidays), a public holiday or a local event, then the dates.\n"
            "- The forecast learns how that kind of period changed your sales before.\n"
            "- Malaysian public holidays are added when you choose Malaysia in setup."
        ),
    },
    {
        "id": "supplier-details",
        "topic": "Orders",
        "question": "How do I change a supplier's WhatsApp number or minimum order?",
        "answer": (
            "- On Plan purchases, open the supplier under Supplier orders and use Supplier details.\n"
            "- A valid phone number is needed for the WhatsApp and Call buttons.\n"
            "- To change the supplier's name, use + Add item / supplier / place on Inventory."
        ),
    },
    {
        "id": "no-pay",
        "topic": "Orders",
        "question": "Does the app send orders or pay suppliers by itself?",
        "answer": (
            "- No. RestockAI prepares the order and the message.\n"
            "- The owner sends it by WhatsApp or phone, then confirms it was placed.\n"
            "- The app never pays or transfers money."
        ),
    },
    {
        "id": "today",
        "topic": "Settings",
        "question": "Why does the app show a different date from today?",
        "answer": (
            "- The app treats 'today' as the day after your latest sales.\n"
            "- Importing a new day of sales moves it forward.\n"
            "- The owner can pin a fixed demo date in Settings."
        ),
    },
    {
        "id": "reset",
        "topic": "Settings",
        "question": "How do I start over with the demo data?",
        "answer": (
            "- The owner can use Settings, Reset demo data.\n"
            "- It reloads the made-up data and restarts the first-time setup.\n"
            "- Everyone sharing the demo sees the change, so tell your team first."
        ),
    },
]

PAGES = (
    "Plan purchases: pick days, Generate plan, forecast accuracy, stock health, biggest spend, Supplier orders, Supplier details. "
    "Inventory: stock by batch, + Add item / supplier / place, + Add stock, Remove expired. "
    "Recipes: what goes into one serving of each dish, + Add a dish. "
    "Order history: past orders. Calendar: holidays, periods, events. Activity: record of every action. "
    "Settings (owner): risk setting, demo date, reset."
)

GUIDE_FILE = Path(__file__).with_name("guide.md")


def guide_text() -> str:
    """The whole guide: the longer guide file, then every ready-made answer (used when nothing matches a question)."""
    lines = [GUIDE_FILE.read_text(encoding="utf-8"), "", f"Pages: {PAGES}", "", "READY-MADE ANSWERS"]
    lines += [f"Q: {f['question']}\nA: {f['answer']}" for f in FAQ]
    return "\n".join(lines)
