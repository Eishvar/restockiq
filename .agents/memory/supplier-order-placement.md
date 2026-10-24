---
name: Supplier order placement
description: User-confirmed order placement versus external WhatsApp and phone actions.
---
Orders stay in Draft while users contact a supplier. Move to Approved only after the user confirms they have placed the order.

**Why:** The user explicitly requested that the WhatsApp popup appear before approval and that approval happen only after placing the order. Opening WhatsApp or a dialler cannot establish whether a message was sent or an order accepted.

**How to apply:** Do not change order status merely on a contact-link click or message preview. Keep click-to-chat separate from authenticated WhatsApp Business delivery; only claim direct sending when a provider actually accepts the send.

After a confirmed placement or receipt, keep the changed order visible by selecting its destination tab within that supplier.

**Why:** Leaving users on an empty Draft tab after placement makes a successful action look like the order disappeared.

**How to apply:** Follow an actual status transition; do not override a user's chosen tab just because background data refreshes.
