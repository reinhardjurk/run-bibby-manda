"""Area: Statistik (Moderation, Anreise) und SEPA-Export."""

from __future__ import annotations

import csv
import io

import pytest

from tools.e2e.api import VALID_IBAN, registration_payload


@pytest.fixture(scope="module")
def sepa_regs(admin, cfg, event, comps) -> list[dict]:
    out = []
    for i, plz in enumerate(("20095", "01067", "80331")):
        r = admin.post(
            f"/api/{cfg.slug}/team/registrations",
            json=registration_payload(
                event["id"],
                comps["5 km"]["id"],
                first_name=f"Sepa{i}",
                last_name="E2E-Lastschrift",
                payment_method="sepa_debit",
                iban=VALID_IBAN,
                account_holder=f"E2E Inhaber {i}",
                postal_code=plz,
                heard_about="poster",
                tshirt_size="S",
                team_name="E2E Statistik",
            ),
        )
        assert r.status_code == 201, r.text
        out.append(r.json())
    return out


def test_statistics_structure(admin, cfg, event, sepa_regs):
    st = admin.get(f"/api/{cfg.slug}/team/stats", params={"event_id": event["id"]}).json()
    assert st["event"]["id"] == event["id"] and st["event"]["venue_postal_code"] == "82194"
    ov = st["overview"]
    assert ov["participants"] >= 3 and ov["average_age"] and ov["youngest"] and ov["oldest"]
    assert "E2E Statistik" in st["team_names"]
    assert st["heard_about"].get("poster", 0) >= 3 and st["tshirt_sizes"].get("S", 0) >= 3
    comps_by_title = {c["competition"]["title_de"]: c for c in st["competitions"]}
    assert comps_by_title["5 km"]["total"] >= 3 and "by_gender" in comps_by_title["5 km"]
    assert st["regulars"]["count"] >= 0
    assert (
        admin.get(
            f"/api/{cfg.slug}/team/stats",
            params={"event_id": "00000000-0000-0000-0000-000000000000"},
        ).status_code
        == 404
    )


def test_travel_estimate(admin, cfg, event, sepa_regs):
    tr = admin.get(f"/api/{cfg.slug}/team/stats", params={"event_id": event["id"]}).json()["travel"]
    assert tr["available"] is True and tr["counted"] >= 3
    assert tr["farthest_km"] and tr["farthest_km"] > 400  # Hamburg or Dresden from Munich area
    assert tr["average_km"] is not None and tr["top_regions"] and isinstance(tr["buckets"], dict)
    assert sum(tr["buckets"].values()) == tr["counted"]


def test_sepa_summary_and_export(admin, cfg, event, sepa_regs):
    base = f"/api/{cfg.slug}/team/sepa"
    before = admin.get(f"{base}/summary", params={"event_id": event["id"]}).json()
    assert before["open"]["count"] >= 3 and before["open"]["amount_cents"] >= 3000
    assert "creditor_name" in before and "creditor_id" in before
    r = admin.post(f"{base}/export.csv", params={"event_id": event["id"]})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert int(r.headers["X-Row-Count"]) == before["open"]["count"]
    text = r.content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    assert rows[0] == [
        "Name",
        "Kontoinhaber",
        "IBAN",
        "Mandatsreferenz",
        "Betrag",
        "Verwendungszweck",
        "Startnummer",
        "E-Mail",
    ]
    ours = [row for row in rows[1:] if "E2E-Lastschrift" in row[0]]
    assert len(ours) == 3
    assert all(
        row[2] == VALID_IBAN.replace(" ", "") for row in ours
    )  # full IBAN decrypted for the bank
    assert all(row[4] == "10,00" and row[3] and row[6] for row in ours)
    # exported payments are not exported twice unless asked for
    again = admin.post(f"{base}/export.csv", params={"event_id": event["id"]})
    assert again.headers["X-Row-Count"] == "0"
    after = admin.get(f"{base}/summary", params={"event_id": event["id"]}).json()
    assert (
        after["open"]["count"] == 0
        and after["exported"]["count"] == before["open"]["count"] + before["exported"]["count"]
    )
    full = admin.post(
        f"{base}/export.csv", params={"event_id": event["id"], "include_exported": "true"}
    )
    assert int(full.headers["X-Row-Count"]) >= 3
    detail = admin.get(
        f"/api/{cfg.slug}/team/registrations/{sepa_regs[0]['registration_id']}"
    ).json()
    assert detail["payment"]["sepa_exported_at"]
