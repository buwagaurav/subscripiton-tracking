from datetime import date, timedelta

from langchain_core.tools import tool

from subtrack.database.db import fetch_subscriptions


def make_tools(user_id: int) -> list:
    """Return a list of LangChain tools scoped to the given user."""

    @tool
    def list_subscriptions() -> str:
        """List all subscriptions with name, cost, billing cycle, category, and next renewal date."""
        subs = fetch_subscriptions(user_id)
        if not subs:
            return "No subscriptions tracked yet."
        lines = [f"You have {len(subs)} subscription(s):"]
        for s in subs:
            lines.append(
                f"- **{s.name}** ({s.category.name}): "
                f"${s.cost:.2f}/{s.billing_cycle}, "
                f"renews {s.renewal_date.strftime('%b %d, %Y')}"
            )
        return "\n".join(lines)

    @tool
    def spending_summary() -> str:
        """Get total monthly spend, annual spend, and a breakdown by category."""
        subs = fetch_subscriptions(user_id)
        if not subs:
            return "No subscriptions to summarize."

        def mo(s):
            return s.cost if s.billing_cycle == "Monthly" else s.cost / 12

        total_mo = sum(mo(s) for s in subs)
        total_yr = sum(s.cost * 12 if s.billing_cycle == "Monthly" else s.cost for s in subs)

        by_cat: dict[str, float] = {}
        for s in subs:
            by_cat[s.category.name] = by_cat.get(s.category.name, 0) + mo(s)

        lines = [
            f"**Monthly spend:** ${total_mo:.2f}",
            f"**Annual spend:** ${total_yr:.2f}",
            f"**Subscriptions tracked:** {len(subs)}",
            "",
            "**Category breakdown (monthly):**",
        ]
        for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1]):
            pct = amt / total_mo * 100 if total_mo else 0
            lines.append(f"- {cat}: ${amt:.2f}/mo ({pct:.0f}%)")
        return "\n".join(lines)

    @tool
    def upcoming_renewals(days: int = 30) -> str:
        """Find subscriptions renewing within the next N days (default: 30)."""
        subs = fetch_subscriptions(user_id)
        today = date.today()
        cutoff = today + timedelta(days=max(1, min(days, 365)))
        due = sorted(
            [s for s in subs if today <= s.renewal_date <= cutoff],
            key=lambda s: s.renewal_date,
        )
        if not due:
            return f"No renewals in the next {days} days."
        lines = [f"**{len(due)} renewal(s) in the next {days} days:**"]
        for s in due:
            diff = (s.renewal_date - today).days
            if diff == 0:
                when = "**today**"
            elif diff == 1:
                when = "**tomorrow**"
            else:
                when = f"in {diff} days ({s.renewal_date.strftime('%b %d')})"
            lines.append(f"- **{s.name}**: ${s.cost:.2f} {s.billing_cycle} — renews {when}")
        return "\n".join(lines)

    @tool
    def find_subscription(name: str) -> str:
        """Look up a specific subscription by name (case-insensitive partial match)."""
        subs = fetch_subscriptions(user_id)
        hits = [s for s in subs if name.lower() in s.name.lower()]
        if not hits:
            return f"No subscription matching '{name}' found."
        out = []
        for s in hits:
            out.append(
                f"**{s.name}**\n"
                f"- Category: {s.category.name}\n"
                f"- Cost: ${s.cost:.2f} ({s.billing_cycle})\n"
                f"- Next renewal: {s.renewal_date.strftime('%B %d, %Y')}\n"
                f"- Notes: {s.notes or '—'}"
            )
        return "\n\n".join(out)

    @tool
    def most_expensive(top_n: int = 5) -> str:
        """Return the N most expensive subscriptions ranked by monthly cost (default top 5)."""
        subs = fetch_subscriptions(user_id)
        if not subs:
            return "No subscriptions tracked yet."
        ranked = sorted(
            subs,
            key=lambda s: s.cost if s.billing_cycle == "Monthly" else s.cost / 12,
            reverse=True,
        )[:max(1, top_n)]
        lines = [f"**Top {len(ranked)} most expensive (by monthly cost):**"]
        for i, s in enumerate(ranked, 1):
            m = s.cost if s.billing_cycle == "Monthly" else s.cost / 12
            lines.append(f"{i}. **{s.name}**: ${m:.2f}/mo")
        return "\n".join(lines)

    return [list_subscriptions, spending_summary, upcoming_renewals, find_subscription, most_expensive]
