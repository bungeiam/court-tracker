from typing import Optional

from pydantic import BaseModel, ConfigDict


class CourtBase(BaseModel):
    name: str
    court_level: str
    city: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None


class CourtCreate(CourtBase):
    pass


class CourtResponse(CourtBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class InquiryBatchBase(BaseModel):
    name: str
    start_date: str
    end_date: str
    notes: Optional[str] = None
    status: str = "draft"


class InquiryBatchCreate(InquiryBatchBase):
    pass


class InquiryBatchUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class InquiryBatchResponse(InquiryBatchBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class InquiryBase(BaseModel):
    batch_id: int
    court_id: int
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    subject: str
    body: str
    status: str = "draft"
    sent_at: Optional[str] = None
    acknowledged_at: Optional[str] = None
    responded_at: Optional[str] = None
    notes: Optional[str] = None


class InquiryCreate(InquiryBase):
    pass


class InquiryUpdate(BaseModel):
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    status: Optional[str] = None
    sent_at: Optional[str] = None
    acknowledged_at: Optional[str] = None
    responded_at: Optional[str] = None
    notes: Optional[str] = None


class InquiryResponse(InquiryBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class InquiryMessageBase(BaseModel):
    message_type: str
    sender: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    received_at: Optional[str] = None
    file_path: Optional[str] = None
    mime_type: Optional[str] = None
    notes: Optional[str] = None


class InquiryMessageCreate(InquiryMessageBase):
    pass


class InquiryMessageResponse(InquiryMessageBase):
    id: int
    inquiry_id: int

    model_config = ConfigDict(from_attributes=True)


class InquiryBatchGeneratePayload(BaseModel):
    court_ids: list[int]


class HearingDateBase(BaseModel):
    hearing_date: str
    hearing_type: Optional[str] = None
    notes: Optional[str] = None


class HearingDateCreate(HearingDateBase):
    pass


class HearingDateResponse(HearingDateBase):
    id: int
    case_id: int

    model_config = ConfigDict(from_attributes=True)


class PartyBase(BaseModel):
    role: Optional[str] = None
    name: str
    is_public: int = 1


class PartyCreate(PartyBase):
    pass


class PartyResponse(PartyBase):
    id: int
    case_id: int

    model_config = ConfigDict(from_attributes=True)


class RequestBase(BaseModel):
    request_type: str
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    subject: str
    body: str
    status: str = "draft"
    sent_at: Optional[str] = None
    response_due_date: Optional[str] = None
    response_summary: Optional[str] = None


class RequestResponse(RequestBase):
    id: int
    case_id: int

    model_config = ConfigDict(from_attributes=True)


class RequestUpdate(BaseModel):
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    status: Optional[str] = None
    response_due_date: Optional[str] = None
    response_summary: Optional[str] = None


class DocumentBase(BaseModel):
    document_type: str
    title: str
    description: Optional[str] = None
    request_id: Optional[int] = None
    source: Optional[str] = None
    sender: Optional[str] = None
    file_path: Optional[str] = None
    mime_type: Optional[str] = None
    public_status: Optional[str] = None
    received_date: Optional[str] = None
    notes: Optional[str] = None


class DocumentCreate(DocumentBase):
    pass


class DocumentResponse(DocumentBase):
    id: int
    case_id: int

    model_config = ConfigDict(from_attributes=True)


class DocumentUpdate(BaseModel):
    document_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    request_id: Optional[int] = None
    source: Optional[str] = None
    sender: Optional[str] = None
    file_path: Optional[str] = None
    mime_type: Optional[str] = None
    public_status: Optional[str] = None
    received_date: Optional[str] = None
    notes: Optional[str] = None


class CaseBase(BaseModel):
    court_id: int
    external_case_id: Optional[str] = None
    case_type: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    public_status: Optional[str] = None
    source_method: Optional[str] = None
    source_reference: Optional[str] = None
    raw_text: Optional[str] = None
    interest_score: Optional[int] = None
    interest_notes: Optional[str] = None
    selected_for_followup: int = 0
    status: str = "new"


class CaseCreate(CaseBase):
    pass


class CaseResponse(CaseBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class CaseDetailResponse(CaseResponse):
    hearing_dates: list[HearingDateResponse] = []
    parties: list[PartyResponse] = []
    requests: list[RequestResponse] = []