"""Coverage over the whole e2e run. Its own file, named to sort last: pytest
runs files in name order, and a check that every button and handler was reached
is only true once every other file has run."""
from __future__ import annotations

from tests.e2e.harness import HANDLERS_RUN, TAPPED, all_handlers

# ---- coverage --------------------------------------------------------------- #


def test_zz_every_push_button_action_was_tapped():
    """A button added later without a scenario here is a button nobody pressed
    before a learner did."""
    import re
    from pathlib import Path

    src = Path("app/bot/handlers/push.py").read_text(encoding="utf-8")
    actions = set(re.findall(r'F\.action == "([a-z_]+)"', src))
    assert actions - TAPPED == set()


# Handlers no scenario here can reach, each with the reason. Revisit when one of
# these flows changes — or delete the handler.
NOT_REACHED_BY_DESIGN: set[str] = set()  # conditional flows: test_dormant_flows.py


def test_zz_every_handler_ran():
    """A handler no scenario reached is code no one ran before a learner did."""
    from types import SimpleNamespace

    from app.main import build_dispatcher

    dp = build_dispatcher(SimpleNamespace(rate_limit_per_second=5, access_password=""), None, None)
    try:
        missing = sorted(all_handlers(dp) - HANDLERS_RUN - NOT_REACHED_BY_DESIGN)
    finally:
        for router in list(dp.sub_routers):
            router._parent_router = None
    assert missing == [], "\n".join(missing)
