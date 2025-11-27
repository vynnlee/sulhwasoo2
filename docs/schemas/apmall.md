# APMall 리뷰 데이터 스키마 명세서

## 1. 개요
이 문서는 APMall에서 크롤링한 화장품 리뷰 데이터(`*.json`)의 구조와 각 필드의 의미를 정의합니다.
데이터는 JSON 배열 형태이며, 각 요소는 하나의 리뷰 객체를 나타냅니다.

## 2. 데이터 구조 (Schema)

### 2.1. 최상위 필드 (Top Level Fields)

| 필드명 (Field Name) | 데이터 타입 | 필수 여부 | 설명 (Description) | 비고 |
| :--- | :--- | :--- | :--- | :--- |
| **`prodReviewSn`** | `Integer` | **Required** | 리뷰 고유 식별자 (Primary Key) | 예: `5884165` |
| **`prodName`** | `String` | **Required** | 리뷰 대상 상품명 | 예: `"자음생세럼 브라이트닝 50ML"` |
| **`prodReviewBodyText`**| `String` | **Required** | 리뷰 본문 텍스트 | 핵심 분석 대상 |
| `prodReviewTitle` | `String` | Nullable | 리뷰 제목 | 대부분 `null`인 경우가 많음 |
| `scope` | `Integer` | **Required** | 평점 (1 ~ 5점) | |
| `prodReviewTypeCode` | `String` | **Required** | 리뷰 작성 유형 코드 | `Pur`: 일반 구매<br>`OneMonth`: 한 달 사용 |
| `prodReviewRegistDt` | `String` | **Required** | 리뷰 작성 일시 (ISO 8601) | 예: `"2025-11-21T10:02:25..."` |
| `recommendYn` | `String` | **Required** | 추천 여부 | `Y` / `N` |
| `recommendCnt` | `Integer` | **Required** | '도움이 돼요' 받은 횟수 | |
| `userAddAttrInfo` | `String` | **Required** | 작성자 피부/연령 속성 요약 문자열 | 구분자 `/` 사용<br>예: `"50대 이상/여성/복합성/탄력없음"` |

### 2.2. 작성자 정보 (User Profile)

| 필드명 | 데이터 타입 | 필수 여부 | 설명 |
| :--- | :--- | :--- | :--- |
| **`memberSn`** | `Integer` | **Required** | 회원 고유 번호 |
| `memberId` | `String` | Nullable | 회원 ID (마스킹 처리됨) |
| `profile` | `Object` | **Required** | 프로필 상세 객체 |
| └ `nickName` | `String` | Optional | 닉네임 (마스킹 처리됨) |
| └ `gradeName` | `String` | Optional | 회원 등급 (예: `BEGINNER`, `VIP`) |
| └ `badgeName` | `String` | Optional | 뱃지 이름 (예: `친절한 리뷰어`) |

### 2.3. 상세 설문 (`surveys`)

리뷰 작성 시 선택한 상세 평가 항목 리스트입니다. 보통 5개의 고정된 질문 세트로 구성됩니다.

| 필드명 | 데이터 타입 | 설명 |
| :--- | :--- | :--- |
| `questionHeader` | `String` | 질문 항목 (Key) |
| `responseBodyText` | `String` | 사용자의 응답 (Value) |

**주요 설문 항목 예시:**
1. **보습감**: "촉촉해요", "보통이에요"
2. **향**: "향이 좋아요", "보통이에요"
3. **민감성**: "순해서 좋아요", "반응이 있어요"
4. **피부타입**: "건성", "지성", "복합성", "중성"
5. **피부고민**: "주름", "탄력없음", "칙칙함", "트러블" 등

### 2.4. 이미지 (`imgList`)

| 필드명 | 데이터 타입 | 설명 |
| :--- | :--- | :--- |
| `prodReviewImgSn` | `Integer` | 이미지 고유 번호 |
| `imageFileUrl` | `String` | 이미지 원본 URL (CDN) |
| `sortOrder` | `Integer` | 이미지 정렬 순서 |

---

## 3. 데이터 예시 (Example)

```json
{
  "prodReviewSn": 5878311,
  "prodName": "자음생앰플 브라이트닝 20G",
  "prodReviewBodyText": "기미가 올라온곳이 있어서 집중케어 하는중 입니다...",
  "scope": 5,
  "prodReviewTypeCode": "Pur",
  "prodReviewRegistDt": "2025-11-18T10:23:49.2768+0900",
  "userAddAttrInfo": "40대/여성/중성/칙칙함",
  "surveys": [
    {
      "questionHeader": "보습감",
      "responseBodyText": "촉촉해요"
    },
    {
      "questionHeader": "피부고민(절대 수정/삭제 금지)",
      "responseBodyText": "칙칙함"
    }
  ],
  "memberSn": 8346734,
  "memberId": "eunj******",
  "profile": {
    "nickName": "eunj******",
    "gradeName": "BEGINNER"
  }
}
```

## 4. 참고 사항 (Notes)
*   **`userAddAttrInfo` 활용**: 연령대, 성별, 피부타입이 하나의 문자열로 합쳐져 있으므로, 분석 시 이를 파싱(`split('/')`)하여 사용하는 것이 좋습니다.
*   **`surveys` 활용**: 정형화된 감성 분석이 필요할 때 텍스트 리뷰(`prodReviewBodyText`)보다 `surveys`의 값을 우선적으로 참조할 수 있습니다.

