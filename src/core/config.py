# src/config.py

# ============================================================
# 공통 설정
# ============================================================
INPUT_FILE = "data/input/targets.xlsx"
DATA_RAW_DIR = "data/raw"

# ============================================================
# 아모레몰 (APMall) 설정
# ============================================================
APMALL_HEADERS = {
    "Host": "api-gw.amoremall.com",
    "Connection": "keep-alive",
    "X-G1ECP-Channel": "PCWeb",
    "sec-ch-ua-platform": '"macOS"',
    "Accept-Language": "ko",
    "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "X-G1ECP-CartNonmemberKey": "2f7437f0-0675-4bb8-95c0-1d6cc7982801",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.amoremall.com",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Accept-Encoding": "gzip, deflate, br, zstd",
}

APMALL_API_URL = "https://api-gw.amoremall.com/commune/v2/M01/apcp/reviews"

# 기존 호환성 유지
HEADERS = APMALL_HEADERS
API_URL = APMALL_API_URL

# 아모레몰 크롤링 딜레이 (초)
APMALL_MIN_DELAY = 1.0
APMALL_MAX_DELAY = 3.0

# 기존 호환성 유지
MIN_DELAY = APMALL_MIN_DELAY
MAX_DELAY = APMALL_MAX_DELAY

# ============================================================
# 네이버 스마트스토어 설정
# ============================================================
NAVER_CONFIG = {
    # 브라우저 설정
    "headless": False,  # Headed 모드 (봇 감지 우회)
    "channel": "chrome",  # 시스템 Chrome 사용
    "viewport": {"width": 1600, "height": 900},
    # 크롤링 딜레이 (초)
    "page_delay_min": 0.8,  # 페이지 전환 최소 딜레이
    "page_delay_max": 1.5,  # 페이지 전환 최대 딜레이
    "product_delay": 5,  # 상품 간 딜레이
    # 저장 설정
    "save_batch_size": 100,  # N개마다 디스크에 저장
    # API 엔드포인트
    "review_api_pattern": "/contents/reviews/query-pages",
}
