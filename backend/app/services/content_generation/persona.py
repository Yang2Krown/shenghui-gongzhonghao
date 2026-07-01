"""Helpers for applying the user's author persona to generation inputs."""

from typing import Optional


def normalize_persona(persona: Optional[str]) -> Optional[str]:
    """Trim and cap persona text before sending it into prompts."""
    if not persona:
        return None
    normalized = persona.strip()
    if not normalized:
        return None
    return normalized[:2000]


async def get_user_persona(db_session, user_id: Optional[int]) -> Optional[str]:
    """Load the current user's saved persona from either async or sync sessions."""
    if not user_id or not db_session:
        return None

    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.user import UserProfile

    if isinstance(db_session, AsyncSession):
        from sqlalchemy import select

        result = await db_session.execute(
            select(UserProfile.persona).where(UserProfile.user_id == user_id)
        )
        return normalize_persona(result.scalar_one_or_none())

    profile = (
        db_session.query(UserProfile.persona)
        .filter(UserProfile.user_id == user_id)
        .first()
    )
    return normalize_persona(profile[0] if profile else None)


async def apply_user_persona(inp, db_session=None):
    """Return a copy of the generation input with the saved persona filled in."""
    if inp.persona:
        return inp
    persona = await get_user_persona(db_session, inp.user_id)
    if not persona:
        return inp
    return inp.model_copy(update={"persona": persona})
