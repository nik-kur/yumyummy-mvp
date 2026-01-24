"""
Agent workflow runner for YumYummy Telegram bridge.
This module exposes run_yumyummy_workflow() which calls the Agent Builder workflow.
"""
import logging
import os
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class WorkflowNotInstalledError(Exception):
    """Raised when the workflow code is not installed in app/agent_workflow/"""
    pass


async def run_yumyummy_workflow(user_text: str, telegram_id: str) -> dict:
    """
    Run the YumYummy Agent Builder workflow.
    
    Args:
        user_text: User input text
        telegram_id: Telegram user ID (string)
    
    Returns:
        Dict with the workflow result containing:
        - intent: str
        - message_text: str
        - confidence: str | None (e.g., "HIGH", "ESTIMATE", or null)
        - totals: dict with calories_kcal, protein_g, fat_g, carbs_g
        - items: list of dicts with name, grams, calories_kcal, protein_g, fat_g, carbs_g
        - source_url: str | None
    
    Raises:
        WorkflowNotInstalledError: If workflow code is not installed
    """
    # Check OPENAI_API_KEY before running workflow
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logger.error("[WORKFLOW] OPENAI_API_KEY missing. Put it into .env as OPENAI_API_KEY=...")
        raise WorkflowNotInstalledError(
            "OPENAI_API_KEY is not set. Put it into .env file as OPENAI_API_KEY=..."
        )
    
    # Check if workflow folder exists
    workflow_dir = Path(__file__).parent / "agent_workflow"
    
    if not workflow_dir.exists() or not workflow_dir.is_dir():
        raise WorkflowNotInstalledError(
            "Workflow not installed: put exported code into app/agent_workflow/"
        )
    
    # Check if there's an __init__.py or main module file
    init_file = workflow_dir / "__init__.py"
    main_file = workflow_dir / "main.py"
    workflow_file = workflow_dir / "workflow.py"
    
    if not any(f.exists() for f in [init_file, main_file, workflow_file]):
        raise WorkflowNotInstalledError(
            "Workflow not installed: put exported code into app/agent_workflow/"
        )
    
    # Try to import and call the workflow
    try:
        # Try importing from agent_workflow module
        import sys
        workflow_path = str(workflow_dir.parent)
        if workflow_path not in sys.path:
            sys.path.insert(0, workflow_path)
        
        # Try to import the workflow function
        # The exact import depends on how the workflow is structured
        # We'll try common patterns
        try:
            from app.agent_workflow.workflow import run_text
            # Try to pass telegram_id if function supports it
            try:
                result = await run_text(text=user_text, telegram_id=telegram_id)
            except TypeError:
                # Fallback if function doesn't accept telegram_id
                result = await run_text(text=user_text)
            return result
        except ImportError:
            try:
                from app.agent_workflow import run_text
                try:
                    result = await run_text(text=user_text, telegram_id=telegram_id)
                except TypeError:
                    result = await run_text(text=user_text)
                return result
            except ImportError:
                try:
                    from app.agent_workflow.main import run_text
                    try:
                        result = await run_text(text=user_text, telegram_id=telegram_id)
                    except TypeError:
                        result = await run_text(text=user_text)
                    return result
                except ImportError:
                    # If none of the imports work, raise the error
                    raise WorkflowNotInstalledError(
                        "Workflow not installed: put exported code into app/agent_workflow/ "
                        "and ensure it exports a run_text() function"
                    )
    except WorkflowNotInstalledError:
        raise
    except Exception as e:
        logger.error(f"[WORKFLOW] Error running workflow: {e}", exc_info=True)
        raise WorkflowNotInstalledError(
            f"Workflow execution failed: {str(e)}. "
            "Ensure workflow code is properly installed in app/agent_workflow/"
        )

