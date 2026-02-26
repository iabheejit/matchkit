"""Chat service — business logic for chat rooms and messages."""
import logging
from typing import Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.entities import ChatRoom, ChatMessage, ChatRoomStatus, Match
from ai.icebreaker import icebreaker_generator

logger = logging.getLogger(__name__)


class ChatService:
    """Business logic for chat rooms and messaging."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_room(self, match_id: int) -> Optional[ChatRoom]:
        """Get existing chat room for a match, or create one with an AI icebreaker."""
        # Check for existing room
        result = await self.session.execute(
            select(ChatRoom).where(ChatRoom.match_id == match_id)
        )
        room = result.scalar_one_or_none()
        if room:
            return room

        # Load the match with orgs
        match_result = await self.session.execute(
            select(Match)
            .where(Match.id == match_id)
            .options(selectinload(Match.source_org), selectinload(Match.target_org))
        )
        match = match_result.scalar_one_or_none()
        if not match:
            return None

        # Generate AI icebreaker
        icebreaker = icebreaker_generator.generate_for_match(
            match, match.source_org, match.target_org
        )

        # Create room
        room = ChatRoom(
            match_id=match_id,
            org_a_id=match.source_org_id,
            org_b_id=match.target_org_id,
            icebreaker=icebreaker,
        )
        self.session.add(room)
        await self.session.flush()

        # Add icebreaker as first system message
        if icebreaker:
            msg = ChatMessage(
                room_id=room.id,
                sender_org_id=None,
                content=icebreaker,
                message_type="ai_icebreaker",
            )
            self.session.add(msg)
            await self.session.flush()

        logger.info(f"Created chat room {room.id} for match {match_id}")
        return room

    async def send_message(
        self,
        room_id: int,
        sender_org_id: int,
        content: str,
        message_type: str = "user",
    ) -> Optional[ChatMessage]:
        """Save a new message to a chat room."""
        msg = ChatMessage(
            room_id=room_id,
            sender_org_id=sender_org_id,
            content=content,
            message_type=message_type,
        )
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def get_messages(
        self,
        room_id: int,
        limit: int = 50,
        before_id: Optional[int] = None,
    ) -> Sequence[ChatMessage]:
        """Get messages for a room with pagination."""
        query = (
            select(ChatMessage)
            .where(ChatMessage.room_id == room_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        if before_id:
            query = query.where(ChatMessage.id < before_id)

        result = await self.session.execute(query)
        messages = list(result.scalars().all())
        messages.reverse()  # Return in chronological order
        return messages

    async def get_rooms_for_org(self, org_id: int) -> Sequence[ChatRoom]:
        """Get all chat rooms for an organization."""
        result = await self.session.execute(
            select(ChatRoom)
            .where(
                (ChatRoom.org_a_id == org_id) | (ChatRoom.org_b_id == org_id)
            )
            .where(ChatRoom.status == ChatRoomStatus.ACTIVE.value)
            .options(
                selectinload(ChatRoom.match),
                selectinload(ChatRoom.org_a),
                selectinload(ChatRoom.org_b),
            )
            .order_by(ChatRoom.updated_at.desc())
        )
        return result.scalars().all()

    async def get_room_by_id(self, room_id: int) -> Optional[ChatRoom]:
        """Get a chat room by ID with relationships loaded."""
        result = await self.session.execute(
            select(ChatRoom)
            .where(ChatRoom.id == room_id)
            .options(
                selectinload(ChatRoom.org_a),
                selectinload(ChatRoom.org_b),
                selectinload(ChatRoom.match),
            )
        )
        return result.scalar_one_or_none()

    async def mark_messages_read(self, room_id: int, reader_org_id: int):
        """Mark all messages in a room as read by a specific org."""
        from datetime import datetime
        result = await self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.room_id == room_id)
            .where(ChatMessage.sender_org_id != reader_org_id)
            .where(ChatMessage.read_at.is_(None))
        )
        messages = result.scalars().all()
        now = datetime.utcnow()
        for msg in messages:
            msg.read_at = now
        await self.session.flush()
        return len(messages)

    async def get_unread_count(self, room_id: int, org_id: int) -> int:
        """Get count of unread messages for an org in a room."""
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.count(ChatMessage.id))
            .where(ChatMessage.room_id == room_id)
            .where(ChatMessage.sender_org_id != org_id)
            .where(ChatMessage.read_at.is_(None))
        )
        return result.scalar_one()
