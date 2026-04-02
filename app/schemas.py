from pydantic import BaseModel
from typing import Optional


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

    class Config:
        from_attributes = True


class HearingDateBase(BaseModel):
    hearing_date: str
    hearing_type: Optional[str] = None
    notes: Optional[str] = None


class HearingDateCreate(HearingDateBase):
    pass


class HearingDateResponse(HearingDateBase):
    id: int
    case_id: int

    class Config:
        from_attributes = True


class PartyBase(BaseModel):
    role: Optional[str] = None
    name: str
    is_public: int = 1


class PartyCreate(PartyBase):
    pass


class PartyResponse(PartyBase):
    id: int
    case_id: int

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


class RequestUpdate(BaseModel):
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    status: Optional[str] = None
    response_due_date: Optional[str] = None
    response_summary: Optional[str] = None


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

    class Config:
        from_attributes = True


class CaseDetailResponse(CaseResponse):
    hearing_dates: list[HearingDateResponse] = []
    parties: list[PartyResponse] = []
    requests: list[RequestResponse] = []