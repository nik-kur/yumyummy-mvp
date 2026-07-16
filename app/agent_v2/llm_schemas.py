"""
Hand-written JSON Schemas for LLM structured output.

Deliberately flat (no $ref/$defs, no null unions) so the exact same dict is
accepted by Gemini responseJsonSchema, Perplexity json_schema and OpenAI
Responses json_schema. Absent optionals are empty strings / zeros.
"""

_PARSED_ITEM = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "grams": {"type": "number"},
        "explicit_grams": {"type": "boolean"},
        "fdc_query": {"type": "string"},
        "is_branded": {"type": "boolean"},
        "brand": {"type": "string"},
        # Photo only: where est_* numbers came from.
        #   label         — printed values fully readable (label/menu/screenshot)
        #   label_partial — some printed values visible but incomplete
        #   estimate      — visual estimate (or plain text parse)
        "nutrition_source": {
            "type": "string",
            "enum": ["label", "label_partial", "estimate"],
        },
        "est_calories_kcal": {"type": "number"},
        "est_protein_g": {"type": "number"},
        "est_fat_g": {"type": "number"},
        "est_carbs_g": {"type": "number"},
    },
    "required": [
        "name",
        "grams",
        "fdc_query",
        "est_calories_kcal",
        "est_protein_g",
        "est_fat_g",
        "est_carbs_g",
    ],
}

PARSE_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["log_meal", "eatout", "product", "help", "unknown"],
        },
        "items": {"type": "array", "items": _PARSED_ITEM},
        "language": {"type": "string"},
        "note": {"type": "string"},
    },
    "required": ["intent", "items"],
}

_BRANDED_ITEM = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "grams": {"type": "number"},
        "calories_kcal": {"type": "number"},
        "protein_g": {"type": "number"},
        "fat_g": {"type": "number"},
        "carbs_g": {"type": "number"},
        "source_url": {"type": "string"},
    },
    "required": ["name", "calories_kcal", "protein_g", "fat_g", "carbs_g"],
}

BRANDED_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": _BRANDED_ITEM},
        "confidence": {"type": "string", "enum": ["HIGH", "ESTIMATE"]},
        "source_url": {"type": "string"},
        "official_domain": {"type": "string"},
        "note": {"type": "string"},
    },
    "required": ["items", "confidence"],
}

_ADVISOR_OPTION = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "calories_kcal": {"type": "number"},
        "protein_g": {"type": "number"},
        "fat_g": {"type": "number"},
        "carbs_g": {"type": "number"},
        "source_url": {"type": "string"},
    },
    "required": ["name", "calories_kcal", "protein_g", "fat_g", "carbs_g"],
}

ADVISOR_SCHEMA = {
    "type": "object",
    "properties": {
        # What the model decided the question is:
        #   recommendation — "what should I eat/order" (fills 3 options)
        #   analysis       — a question about the user's own intake/history
        #   offtopic       — anything outside food & nutrition
        "answer_kind": {
            "type": "string",
            "enum": ["recommendation", "analysis", "offtopic"],
        },
        "message_text": {"type": "string"},
        "items": {"type": "array", "items": _ADVISOR_OPTION},
        "source_url": {"type": "string"},
    },
    "required": ["answer_kind", "message_text", "items"],
}
