"""Helpers for migrations that edit packs.

Ownership is split by `packs.origin` (see 0062): migrations own `migration`
rows, the admin owns `admin` rows, and a pack edited by hand moves across. The
rule only works if the skip is loud — a migration that quietly passes over a
hand-edited pack ships a fix that never arrives, and the deploy reports success.

Usage inside a migration:

    from migrations.pack_ownership import editable_slugs, report_skipped

    mine, theirs = editable_slugs(bind, ["colors", "food", "crypto"])
    # ... update only `mine` ...
    report_skipped(theirs)
"""

from __future__ import annotations

import sqlalchemy as sa

ORIGIN_MIGRATION = "migration"
ORIGIN_ADMIN = "admin"


def editable_slugs(bind, slugs: list[str]) -> tuple[list[str], list[str]]:
    """Split the slugs into (migrations may edit, admin now owns).

    A slug that does not exist yet counts as editable: creating it is not a
    conflict with anybody.
    """
    if not slugs:
        return [], []
    rows = bind.execute(
        sa.text("SELECT slug, origin FROM packs WHERE slug = ANY(:slugs)"),
        {"slugs": slugs},
    ).all()
    owned_by_admin = {r[0] for r in rows if r[1] == ORIGIN_ADMIN}
    mine = [s for s in slugs if s not in owned_by_admin]
    theirs = [s for s in slugs if s in owned_by_admin]
    return mine, theirs


def report_skipped(skipped: list[str]) -> None:
    """Say out loud which packs the migration did not touch.

    Printed rather than logged: alembic runs before the app's logging is set up,
    and this has to land in the deploy output where somebody reads it.
    """
    if not skipped:
        return
    print(
        "ВНИМАНИЕ: пропущены паки, которыми теперь владеет админка — "
        f"{', '.join(sorted(skipped))}. "
        "Изменения миграции на них НЕ применены. "
        "Если правка нужна, внесите её через админку или смените origin вручную."
    )
