"""Authentication and event hooks for the local proposal workflow demo."""

import hmac
import os

from flask import session


DEMO_USERS = {
    "insp.ops": {"name": "Insp. Operations", "role": "initiator"},
    "insp.traffic": {"name": "Insp. Traffic", "role": "initiator"},
    "dsp.review": {"name": "DSP Review", "role": "reviewer"},
    "sp.approve": {"name": "SP Approver", "role": "approver"},
}

_listeners = []


def demo_password():
    return os.environ.get("IPMPRS_DEMO_PASSWORD", "demo123")


def authenticate(username, password):
    user = DEMO_USERS.get(username)
    if not user or not hmac.compare_digest(str(password or ""), demo_password()):
        return None
    return {"username": username, **user}


def current_user():
    return session.get("workflow_user")


def can_view_proposal(proposal, user):
    return proposal.get("status") != "Draft" or proposal.get("created_by") == user["name"]


def register_listener(listener):
    if listener not in _listeners:
        _listeners.append(listener)


def notify_listeners(event, proposal):
    for listener in tuple(_listeners):
        listener(event, proposal)