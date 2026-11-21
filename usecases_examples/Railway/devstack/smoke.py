"""
Smoke check of the dev stack: post one event and one context through the gateway, then read the
event back as an OperatorFabric card and the context back from the Context Service.

Usage: python smoke.py [gateway URL, default http://localhost:3200]; exit code 0 when all pass.
"""

import sys

import seed


def main():
    token = seed.login()
    event = seed.seed_event(token, title="Smoke check")
    event_id = event["id_event"]
    card = seed.request("GET", f"/cards/cards/cabProcess.{event_id}", token=token)["card"]
    assert card["titleTranslated"] == "Smoke check", card
    assert card["entityRecipients"] == ["Railway"], card
    posted = seed.seed_context(token)
    latest = seed.request("GET", "/cabcontext/api/v1/contexts", token=token)
    assert latest and latest[0]["use_case"] == "Railway", latest
    assert latest[0]["data"] == posted["data"], (latest[0], posted)
    print(f"smoke check passed: event {event_id} is a card, the context reads back")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                       # noqa: BLE001 - report any failure as a fail
        print(f"smoke check FAILED: {e!r}", file=sys.stderr)
        sys.exit(1)
