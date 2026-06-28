"""
Stripe webhook server for Secret Thrower premium subscriptions.

Set up in Stripe Dashboard:
  1. Create a Product: "Secret Thrower Premium" at $4/month
  2. In Checkout Session creation, pass:
       metadata={"guild_id": str(guild_id)}
       subscription_data={"metadata": {"guild_id": str(guild_id)}}
  3. Point the webhook to: https://your-domain.com/stripe/webhook
     Events to listen for:
       - checkout.session.completed
       - customer.subscription.deleted
       - customer.subscription.paused
       - invoice.payment_failed

Run locally: uvicorn api:app --host 0.0.0.0 --port 8000
"""

import asyncio
import logging
import os
from datetime import datetime, timezone

import stripe
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from sqlalchemy import select

from database import AsyncSessionLocal
from models import Subscription, SubscriptionType

load_dotenv()


log = logging.getLogger("api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

app = FastAPI(title="Secret Thrower API")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
) -> dict:
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, WEBHOOK_SECRET)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payload") from e
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid signature") from e

    event_type: str = event["type"]
    log.info("Stripe event received: %s", event_type)

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(event["data"]["object"])

    elif event_type in ("customer.subscription.deleted", "customer.subscription.paused"):
        await _handle_subscription_ended(event["data"]["object"])

    elif event_type == "invoice.payment_failed":
        log.warning("Payment failed — invoice %s", event["data"]["object"].get("id"))

    return {"status": "ok"}


async def _handle_checkout_completed(session: dict) -> None:
    guild_id = session.get("metadata", {}).get("guild_id")
    if not guild_id:
        log.warning("checkout.session.completed missing guild_id in metadata — skipping")
        return

    guild_id = int(guild_id)
    expires_at = None

    stripe_sub_id = session.get("subscription")
    if stripe_sub_id:
        sub = await asyncio.to_thread(stripe.Subscription.retrieve, stripe_sub_id)
        expires_at = datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Subscription).where(Subscription.target_id == guild_id))
        row = result.scalar_one_or_none()
        if row:
            row.is_active = True
            row.expires_at = expires_at
        else:
            db.add(
                Subscription(
                    target_id=guild_id,
                    type=SubscriptionType.GUILD,
                    is_active=True,
                    expires_at=expires_at,
                )
            )
        await db.commit()

    log.info("Activated premium for guild %d (expires %s)", guild_id, expires_at)


async def _handle_subscription_ended(stripe_sub: dict) -> None:
    # guild_id is stored in subscription metadata at checkout creation time
    guild_id = stripe_sub.get("metadata", {}).get("guild_id")
    if not guild_id:
        log.warning("Subscription ended but no guild_id in metadata — cannot deactivate")
        return

    guild_id = int(guild_id)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Subscription).where(Subscription.target_id == guild_id))
        row = result.scalar_one_or_none()
        if row:
            row.is_active = False
            await db.commit()

    log.info("Deactivated premium for guild %d", guild_id)
