from sqlalchemy import Boolean, Column, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Court(Base):
    __tablename__ = "courts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)
    court_level = Column(Text, nullable=False)
    city = Column(Text, nullable=True)
    email = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)

    cases = relationship("Case", back_populates="court")
    inquiries = relationship("Inquiry", back_populates="court")


class InquiryBatch(Base):
    __tablename__ = "inquiry_batches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)
    start_date = Column(Text, nullable=False)
    end_date = Column(Text, nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(Text, default="draft")

    inquiries = relationship(
        "Inquiry",
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class Inquiry(Base):
    __tablename__ = "inquiries"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("inquiry_batches.id"), nullable=False)
    court_id = Column(Integer, ForeignKey("courts.id"), nullable=False)
    recipient_name = Column(Text, nullable=True)
    recipient_email = Column(Text, nullable=True)
    subject = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    status = Column(Text, default="draft")
    sent_at = Column(Text, nullable=True)
    acknowledged_at = Column(Text, nullable=True)
    responded_at = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    batch = relationship("InquiryBatch", back_populates="inquiries")
    court = relationship("Court", back_populates="inquiries")
    messages = relationship(
        "InquiryMessage",
        back_populates="inquiry",
        cascade="all, delete-orphan",
    )


class InquiryMessage(Base):
    __tablename__ = "inquiry_messages"

    id = Column(Integer, primary_key=True, index=True)
    inquiry_id = Column(Integer, ForeignKey("inquiries.id"), nullable=False)
    message_type = Column(Text, nullable=False)
    sender = Column(Text, nullable=True)
    subject = Column(Text, nullable=True)
    body = Column(Text, nullable=True)
    received_at = Column(Text, nullable=True)
    file_path = Column(Text, nullable=True)
    mime_type = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    inquiry = relationship("Inquiry", back_populates="messages")


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    court_id = Column(Integer, ForeignKey("courts.id"), nullable=False)
    external_case_id = Column(Text, nullable=True)
    case_type = Column(Text, nullable=True)
    title = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    public_status = Column(Text, nullable=True)
    source_method = Column(Text, nullable=True)
    source_reference = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)
    interest_score = Column(Integer, nullable=True)
    interest_notes = Column(Text, nullable=True)
    selected_for_followup = Column(Integer, default=0)
    status = Column(Text, default="new")

    court = relationship("Court", back_populates="cases")
    hearing_dates = relationship(
        "HearingDate",
        back_populates="case",
        cascade="all, delete-orphan",
    )
    parties = relationship(
        "Party",
        back_populates="case",
        cascade="all, delete-orphan",
    )
    requests = relationship(
        "Request",
        back_populates="case",
        cascade="all, delete-orphan",
    )
    documents = relationship(
        "Document",
        back_populates="case",
        cascade="all, delete-orphan",
    )


class HearingDate(Base):
    __tablename__ = "hearing_dates"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    hearing_date = Column(Text, nullable=False)
    hearing_type = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    case = relationship("Case", back_populates="hearing_dates")


class Party(Base):
    __tablename__ = "parties"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    role = Column(Text, nullable=True)
    name = Column(Text, nullable=False)
    is_public = Column(Integer, default=1)

    case = relationship("Case", back_populates="parties")


class Request(Base):
    __tablename__ = "requests"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    request_type = Column(Text, nullable=False)
    recipient_name = Column(Text, nullable=True)
    recipient_email = Column(Text, nullable=True)
    subject = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    status = Column(Text, default="draft")
    sent_at = Column(Text, nullable=True)
    response_due_date = Column(Text, nullable=True)
    response_summary = Column(Text, nullable=True)

    case = relationship("Case", back_populates="requests")
    documents = relationship("Document", back_populates="request")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    request_id = Column(Integer, ForeignKey("requests.id"), nullable=True)
    document_type = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    source = Column(Text, nullable=True)
    sender = Column(Text, nullable=True)
    file_path = Column(Text, nullable=True)
    mime_type = Column(Text, nullable=True)
    public_status = Column(Text, nullable=True)
    received_date = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    case = relationship("Case", back_populates="documents")
    request = relationship("Request", back_populates="documents")