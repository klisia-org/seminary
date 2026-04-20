# Pricing Strategy

SeminaryERP charges students by creating invoices from **Fee Categories**, each linked to an ERPNext **Item** with a price on a **Price List**. How granular you make those items is a strategic decision that affects reporting, forecasting, and how much work it is to change prices later.

## Bundled vs. granular pricing

Both of the following approaches produce the same invoice total. They are not equivalent for the seminary.

| Approach A — *bundled*       | Approach B — *granular*         |
| ---------------------------- | ------------------------------- |
| 1h course: 250               | Credit-hour: 200                |
| 2h course: 450               | Course registration: 50         |

**Approach A** is faster to set up. Prices are baked into each course-level item.

**Approach B** separates *what varies with credit load* (per-credit teaching cost) from *what is fixed per enrollment* (administrative cost). This lets you:

- Project revenue against enrollment scenarios (e.g. "what if average load drops from 12 to 9 credits?")
- Raise per-credit rates without touching every course item
- Apply scholarships or discounts to the credit portion only
- Report on administrative vs. academic revenue cleanly

For anything beyond a very small seminary, **prefer Approach B**. The upfront modeling effort pays off the first time you need to adjust pricing or justify a budget.

## Practical guidelines

- **One Item per cost driver**, not per course. Credit hours, registration, technology fee, library access, housing — each is its own Item.
- **Keep the number of Price Lists small.** Each additional list multiplies the maintenance surface. Only add a list when the *entire* price structure genuinely differs (e.g. international students pay different rates across the board), not for one-off discounts — use scholarships or Pricing Rules for those.
- **Map each chargeable event to a Fee Category.** This is what makes billing automatic: when the student enrolls, the term opens, or the per-credit trigger fires, SeminaryERP creates the right invoice lines from the Fee Category.
- **Re-evaluate before your first term, not after.** Changing the pricing model once invoices exist is painful; getting it right before go-live is cheap.

## Related

- [Initial Setup](initial-setup.md) — the full setup sequence
- [ERPNext Item](https://docs.frappe.io/erpnext/item) · [Price List](https://docs.frappe.io/erpnext/price-lists) · [Item Price](https://docs.frappe.io/erpnext/item-price)
