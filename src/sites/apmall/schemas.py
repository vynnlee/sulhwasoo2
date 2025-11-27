from typing import List, Optional, Any
from pydantic import BaseModel, Field


class ReviewImage(BaseModel):
    prodReviewImgSn: int = Field(..., description="이미지 고유 번호")
    imageFileUrl: str = Field(..., description="이미지 URL")
    sortOrder: Optional[int] = None


class ReviewSurvey(BaseModel):
    questionHeader: str = Field(..., description="질문 내용 (예: 보습감, 향)")
    responseBodyText: str = Field(..., description="응답 내용")
    memberAttrTgtYn: str = Field(..., description="회원 속성 타겟 여부 (Y/N)")


class UserProfile(BaseModel):
    nickName: Optional[str] = None
    gradeName: Optional[str] = None
    badgeName: Optional[str] = None
    imageUrl: Optional[str] = None


class ApmallReview(BaseModel):
    # --- 식별자 ---
    prodReviewSn: int = Field(..., description="리뷰 고유 번호")
    prodName: str = Field(..., description="상품명")

    # --- 리뷰 내용 ---
    prodReviewBodyText: str = Field(..., description="리뷰 본문")
    prodReviewTitle: Optional[str] = Field(None, description="리뷰 제목")
    scope: int = Field(..., description="평점 (1~5)")
    prodReviewTypeCode: str = Field(..., description="리뷰 유형 (Pur, OneMonth 등)")
    prodReviewRegistDt: str = Field(..., description="작성 일시")

    # --- 작성자 정보 ---
    memberSn: int = Field(..., description="회원 번호")
    memberId: Optional[str] = Field(None, description="회원 ID")
    memberStatus: Optional[str] = None
    profile: UserProfile = Field(default_factory=UserProfile)
    userAddAttrInfo: str = Field(
        ..., description="작성자 속성 요약 (연령/성별/피부타입/고민)"
    )

    # --- 상세 데이터 ---
    surveys: List[ReviewSurvey] = Field(
        default_factory=list, description="상세 설문 응답"
    )
    imgList: List[ReviewImage] = Field(
        default_factory=list, description="첨부 이미지 목록"
    )

    # --- 메타 데이터 ---
    recommendCnt: int = 0
    recommendYn: str = "N"
    reportCnt: int = 0
    rvAnalyticsScore: int = 0

    # --- 기타 Nullable 필드 (중요도 낮음) ---
    naverId: Optional[str] = None
    oneLineDesc: Optional[str] = None
    tipDoc: Optional[str] = None
    giftServiceLimitedYn: str = "N"
    isBlock: bool = False
