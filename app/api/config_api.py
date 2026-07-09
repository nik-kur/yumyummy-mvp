"""
Unauthenticated configuration endpoints for the mobile app.

These return JSON configs that the app needs before the user is signed in
(onboarding flow, activation journey ladder). No JWT required.
"""

import logging
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/app/config", tags=["config"])

ONBOARDING_CONFIG: dict[str, Any] = {
    "version": 1,
    "screens": [
        {"id": "S1_welcome", "enabled": True},
        {"id": "S2_goal", "enabled": True},
        {"id": "S3_pain_points", "enabled": True},
        {"id": "S4_gender", "enabled": True},
        {"id": "S5_age", "enabled": True},
        {"id": "S6_body", "enabled": True},
        {"id": "S7_activity", "enabled": True},
        {"id": "S9_S10_cico_arc", "enabled": True},
        {"id": "S11_try_it", "enabled": True},
        {"id": "N1_target_pace", "enabled": True, "goals": ["lose", "gain"]},
        {"id": "N2_loader", "enabled": True},
        {"id": "N3_plan_reveal", "enabled": True},
    ],
    "copy": {
        "rating": "4.8",
        "users_count": "12,000+",
        "cico_headline_1": "So what's the answer?",
        "cico_headline_2": "Prove it to me",
    },
}

JOURNEY_CONFIG: dict[str, Any] = {
    "version": 1,
    "ladder": [
        {"day": 1, "quest": "log_first_meal", "label": "Log your first meal", "desc": "Text, voice, or photo — any way you like.", "enabled": True},
        {"day": 2, "quest": "log_3_meals", "label": "Log 3 meals", "desc": "Build the habit with breakfast, lunch, and dinner.", "enabled": True},
        {"day": 3, "quest": "check_insight", "label": "Check your first insight", "desc": "See what the data says about Day 1.", "enabled": True},
        {"day": 4, "quest": "try_photo", "label": "Try a photo log", "desc": "Snap a pic — we'll do the rest.", "enabled": True},
        {"day": 5, "quest": "save_meal", "label": "Save a meal to My Menu", "desc": "One-tap re-logging for your favorites.", "enabled": True},
        {"day": 6, "quest": "add_widget", "label": "Add the home widget", "desc": "Track at a glance without opening the app.", "enabled": True},
        {"day": 7, "quest": "complete_week", "label": "Complete your first week!", "desc": "Review your Week 1 Report.", "enabled": True},
    ],
    "popup_copy": {
        "why_headline": "Why {QUEST}?",
        "default_why": "Small steps build lasting habits. This quest is designed to help you get the most out of YumYummy.",
    },
}


@router.get("/onboarding")
def get_onboarding_config():
    return ONBOARDING_CONFIG


@router.get("/journey")
def get_journey_config():
    return JOURNEY_CONFIG
