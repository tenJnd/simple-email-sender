from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Union

try:  # optional import to allow test collection without SQLAlchemy installed
    from sqlalchemy import (
        DateTime,
        Integer,
        String,
        UniqueConstraint,
        create_engine,
        func,
        select,
        and_,
        ForeignKey,
    )
    from sqlalchemy.engine import Engine
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import declarative_base, Session, Mapped, mapped_column
    SA_AVAILABLE = True
except Exception:  # pragma: no cover - allow module import without SQLAlchemy
    SA_AVAILABLE = False


@dataclass
class Recipient:
    email: str
    flags: List[str]
    status: str = "active"  # active | opt_out | disabled
    notes: str = ""


Base = declarative_base()


class RecipientModel(Base):
    __tablename__ = "recipients"

    email: Mapped[str] = mapped_column(String, primary_key=True)
    flags: Mapped[str] = mapped_column(String, nullable=True)  # JSON stored as TEXT
    status: Mapped[str] = mapped_column(String, default="active")
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[Optional[str]] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[Optional[str]] = mapped_column(DateTime, nullable=True)


class CampaignModel(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[Optional[str]] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )


class SendLogModel(Base):
    __tablename__ = "send_log"
    __table_args__ = (
        UniqueConstraint("campaign_id", "recipient_email", name="uq_send_once"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id"), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String, ForeignKey("recipients.email"), nullable=False)
    template_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sent_at: Mapped[Optional[str]] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )


class Store:
    def __init__(self, db_path: Union[Path, str]):
        """
        Initialize storage.

        Accepts either a filesystem Path (SQLite file) or a SQLAlchemy URL.
        Examples:
          - Path("state.sqlite")
          - "sqlite:///state.sqlite"
          - "postgresql+psycopg2://user:pass@host:5432/dbname"
        """
        if isinstance(db_path, Path):
            url = f"sqlite:///{db_path}"
        else:
            # Treat string without scheme as SQLite file path too
            url = db_path if "://" in db_path else f"sqlite:///{db_path}"

        self.engine: Engine = create_engine(url, future=True)
        Base.metadata.create_all(self.engine)
        self._Session = Session

    def upsert_recipients(self, recips: Iterable[Recipient]) -> int:
        count = 0
        with Session(self.engine) as session:
            for r in recips:
                flags_json = json.dumps(r.flags or [])
                existing = session.get(RecipientModel, r.email)
                if existing is None:
                    obj = RecipientModel(
                        email=r.email,
                        flags=flags_json,
                        status=r.status,
                        notes=r.notes or None,
                    )
                    session.add(obj)
                else:
                    existing.flags = flags_json
                    existing.status = r.status
                    existing.notes = r.notes or None
                    existing.updated_at = func.current_timestamp()
                count += 1
            session.commit()
        return count

    def create_campaign(self, name: str) -> int:
        with Session(self.engine) as session:
            # First try to insert; if unique violation, fetch existing
            obj = CampaignModel(name=name)
            session.add(obj)
            try:
                session.commit()
                return int(obj.id)
            except IntegrityError:
                session.rollback()
                row = session.execute(select(CampaignModel.id).where(CampaignModel.name == name)).scalar_one_or_none()
                if row is None:
                    raise
                return int(row)

    def get_or_create_campaign(self, name: str) -> int:
        with Session(self.engine) as session:
            row = session.execute(select(CampaignModel.id).where(CampaignModel.name == name)).scalar_one_or_none()
            if row is not None:
                return int(row)
            # Not found: create new
            obj = CampaignModel(name=name)
            session.add(obj)
            session.commit()
            return int(obj.id)

    def list_campaigns(self) -> List[Dict]:
        with Session(self.engine) as session:
            rows = session.execute(
                select(CampaignModel.id, CampaignModel.name, CampaignModel.created_at).order_by(CampaignModel.created_at.desc())
            ).all()
            return [
                {"id": int(r[0]), "name": r[1], "created_at": r[2]}
                for r in rows
            ]

    def get_pending_recipients(self, campaign_id: int, limit: Optional[int] = None) -> List[Recipient]:
        with Session(self.engine) as session:
            subq = (
                select(SendLogModel.id)
                .where(and_(SendLogModel.campaign_id == campaign_id, SendLogModel.recipient_email == RecipientModel.email))
                .exists()
            )
            q = (
                select(RecipientModel.email, RecipientModel.flags, RecipientModel.status, RecipientModel.notes)
                .where(and_(RecipientModel.status == "active", ~subq))
                .order_by(RecipientModel.email)
            )
            if limit is not None:
                q = q.limit(limit)
            rows = session.execute(q).all()
            result: List[Recipient] = []
            for email, flags_txt, status, notes in rows:
                flags: List[str] = []
                try:
                    if flags_txt:
                        flags = json.loads(flags_txt)
                except Exception:
                    flags = []
                result.append(Recipient(email=email, flags=flags, status=status, notes=notes or ""))
            return result

    def log_send(self, campaign_id: int, email: str, template_key: str | None) -> None:
        with Session(self.engine) as session:
            obj = SendLogModel(campaign_id=campaign_id, recipient_email=email, template_key=template_key)
            session.add(obj)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                # already logged; idempotent skip
                return

    def set_opt_out(self, email: str) -> bool:
        with Session(self.engine) as session:
            existing = session.get(RecipientModel, email)
            if existing is not None:
                existing.status = "opt_out"
                existing.updated_at = func.current_timestamp()
                session.commit()
                return True
            # else insert new as opt_out
            obj = RecipientModel(email=email, flags=json.dumps([]), status="opt_out")
            session.add(obj)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
            return False

    def stats_campaign(self, campaign_id: int) -> Dict[str, int]:
        with Session(self.engine) as session:
            total_active = session.execute(
                select(func.count()).select_from(RecipientModel).where(RecipientModel.status == "active")
            ).scalar_one()

            sent = session.execute(
                select(func.count()).select_from(SendLogModel).where(SendLogModel.campaign_id == campaign_id)
            ).scalar_one()

            subq = (
                select(SendLogModel.id)
                .where(and_(SendLogModel.campaign_id == campaign_id, SendLogModel.recipient_email == RecipientModel.email))
                .exists()
            )
            pending = session.execute(
                select(func.count()).select_from(RecipientModel).where(and_(RecipientModel.status == "active", ~subq))
            ).scalar_one()

            return {
                "total_active": int(total_active or 0),
                "sent": int(sent or 0),
                "pending": int(pending or 0),
            }
