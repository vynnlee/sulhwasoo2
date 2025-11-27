import time
import random
import json
import os
import shutil
import glob
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from src.core.base_crawler import BaseCrawler
from src.core.config import INPUT_FILE, NAVER_CONFIG
import pandas as pd

# 스텔스 스크립트 - 봇 감지 우회
STEALTH_JS = """
// 1. webdriver 속성 숨기기
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 2. Chrome 런타임 위장
window.navigator.chrome = { 
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {}
};

// 3. 플러그인 위장 (빈 배열이면 봇으로 감지됨)
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
        { name: 'Native Client', filename: 'internal-nacl-plugin' }
    ]
});

// 4. 언어 설정
Object.defineProperty(navigator, 'languages', {
    get: () => ['ko-KR', 'ko', 'en-US', 'en']
});

// 5. 권한 API 위장
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);

// 6. 자동화 관련 속성 제거
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;

// 7. WebGL 렌더러 정보 위장 (선택적)
const getParameterProxyHandler = {
    apply: function(target, thisArg, argumentsList) {
        const param = argumentsList[0];
        const gl = thisArg;
        if (param === 37445) {
            return 'Google Inc. (Apple)';
        }
        if (param === 37446) {
            return 'ANGLE (Apple, Apple M1 Pro, OpenGL 4.1)';
        }
        return Reflect.apply(target, thisArg, argumentsList);
    }
};

try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    if (gl) {
        gl.getParameter = new Proxy(gl.getParameter.bind(gl), getParameterProxyHandler);
    }
} catch(e) {}
"""


class CrawlStats:
    """크롤링 통계 및 진행 상황 추적"""

    def __init__(self):
        self.reset()

    def reset(self):
        self.start_time = None
        self.total_pages = 0
        self.total_reviews = 0
        self.current_page = 0
        self.errors = []
        self.warnings = []
        self.pages_per_second = 0
        self.reviews_per_second = 0
        self.skipped_reviews = 0  # 이미 수집된 리뷰 (스킵)

    def start(self, total_pages=0, total_reviews=0):
        self.start_time = time.time()
        self.total_pages = total_pages
        self.total_reviews = total_reviews

    def update(self, current_page, collected_reviews):
        self.current_page = current_page
        elapsed = time.time() - self.start_time if self.start_time else 1
        self.pages_per_second = current_page / elapsed if elapsed > 0 else 0
        self.reviews_per_second = collected_reviews / elapsed if elapsed > 0 else 0

    def add_error(self, error_msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.errors.append(f"[{timestamp}] {error_msg}")

    def add_warning(self, warning_msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.warnings.append(f"[{timestamp}] {warning_msg}")

    def get_progress_str(self, collected_reviews):
        elapsed = time.time() - self.start_time if self.start_time else 0
        elapsed_str = time.strftime("%H:%M:%S", time.gmtime(elapsed))

        if self.total_pages > 0:
            progress_pct = (self.current_page / self.total_pages) * 100
            remaining_pages = self.total_pages - self.current_page
            eta_seconds = (
                remaining_pages / self.pages_per_second
                if self.pages_per_second > 0
                else 0
            )
            eta_str = time.strftime("%H:%M:%S", time.gmtime(eta_seconds))
        else:
            progress_pct = 0
            eta_str = "계산중..."

        skip_str = (
            f" (Skip: {self.skipped_reviews})" if self.skipped_reviews > 0 else ""
        )

        return (
            f"[{progress_pct:5.1f}%] "
            f"Page {self.current_page:,}/{self.total_pages:,} | "
            f"Reviews: {collected_reviews:,}{skip_str} | "
            f"Speed: {self.pages_per_second:.1f}p/s | "
            f"Elapsed: {elapsed_str} | ETA: {eta_str}"
        )

    def get_summary(self, collected_reviews):
        elapsed = time.time() - self.start_time if self.start_time else 0
        elapsed_str = time.strftime("%H:%M:%S", time.gmtime(elapsed))

        summary = [
            "",
            "=" * 60,
            "📊 크롤링 완료 요약",
            "=" * 60,
            f"  ✅ 총 페이지: {self.current_page:,}페이지",
            f"  ✅ 신규 리뷰: {collected_reviews:,}개",
        ]

        if self.skipped_reviews > 0:
            summary.append(f"  ⏭️  스킵 리뷰: {self.skipped_reviews:,}개 (이미 수집됨)")

        summary.extend(
            [
                f"  ⏱️  소요 시간: {elapsed_str}",
                f"  🚀 평균 속도: {self.pages_per_second:.2f}페이지/초",
            ]
        )

        if self.errors:
            summary.append(f"  ❌ 오류: {len(self.errors)}건")
            for err in self.errors[-5:]:
                summary.append(f"     - {err}")

        if self.warnings:
            summary.append(f"  ⚠️  경고: {len(self.warnings)}건")

        summary.append("=" * 60)
        return "\n".join(summary)


class NaverCrawler(BaseCrawler):
    def __init__(self):
        super().__init__(site_name="naver")
        self.collected_reviews = []
        self.saved_ids = set()
        self.current_file_path = None
        self.unsaved_reviews = []
        self.save_batch_size = NAVER_CONFIG.get("save_batch_size", 100)
        self.stats = CrawlStats()

        # 오류 대응 설정 강화
        self.max_retries = 5  # 재시도 횟수 증가
        self.retry_delay = 10
        self.pagination_retry_max = 3  # 페이지네이션 재시도 횟수
        self.block_detection_keywords = [
            "접근이 차단",
            "비정상적인 접근",
            "자동화된 접근",
            "captcha",
            "blocked",
            "denied",
        ]

    def _load_existing_reviews(self, prod_id):
        """기존에 수집된 리뷰 ID 로드 (이어서 크롤링용)"""
        # 가장 최근 폴더에서 해당 상품의 JSON 파일 찾기
        base_dir = os.path.join("data", "raw", "naver")
        if not os.path.exists(base_dir):
            return set(), []

        # 날짜순으로 정렬된 폴더 목록
        folders = sorted(
            [
                f
                for f in os.listdir(base_dir)
                if os.path.isdir(os.path.join(base_dir, f))
            ],
            reverse=True,
        )

        for folder in folders:
            file_path = os.path.join(base_dir, folder, f"naver_reviews_{prod_id}.json")
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        existing_reviews = json.load(f)

                    existing_ids = {
                        r.get("id") for r in existing_reviews if r.get("id")
                    }
                    print(f"   📂 기존 데이터 발견: {file_path}")
                    print(f"   📊 기존 리뷰: {len(existing_ids):,}개")
                    return existing_ids, existing_reviews
                except Exception as e:
                    print(f"   ⚠️  기존 파일 로드 실패: {e}")

        return set(), []

    def handle_response(self, response):
        """API 응답을 가로채서 리뷰 데이터를 수집"""
        try:
            url = response.url

            if "/contents/reviews/query-pages" not in url:
                return

            if response.status != 200:
                self.stats.add_warning(f"API returned status {response.status}")
                return

            try:
                data = response.json()
            except:
                return

            total_elements = data.get("totalElements", 0)
            total_pages = data.get("totalPages", 0)
            current_page = data.get("page", 0)

            if current_page == 1 and total_elements > 0:
                self.stats.start(total_pages, total_elements)
                print(
                    f"\n   📋 전체 리뷰: {total_elements:,}개 ({total_pages:,}페이지)"
                )

            contents = data.get("contents", [])
            if not contents:
                return

            new_reviews = []
            skipped = 0
            for review in contents:
                review_id = review.get("id")

                if not review_id:
                    continue

                if review_id in self.saved_ids:
                    skipped += 1
                    continue

                labels = review.get("labels", [])
                if "BEST" in labels:
                    continue

                new_reviews.append(review)
                self.saved_ids.add(review_id)

            self.stats.skipped_reviews += skipped

            if new_reviews:
                self.collected_reviews.extend(new_reviews)
                self.unsaved_reviews.extend(new_reviews)

                self.stats.update(current_page, len(self.collected_reviews))

                if len(self.unsaved_reviews) >= self.save_batch_size:
                    self._save_reviews_batch()

                print(
                    f"\r   {self.stats.get_progress_str(len(self.collected_reviews))}",
                    end="",
                    flush=True,
                )

        except Exception as e:
            self.stats.add_error(f"handle_response: {type(e).__name__}: {str(e)[:50]}")

    def _check_blocked(self, page):
        """차단 여부 확인"""
        try:
            page_content = page.content().lower()
            page_title = page.title().lower()

            for keyword in self.block_detection_keywords:
                if keyword in page_content or keyword in page_title:
                    return True, keyword

            if "에러" in page_title or "error" in page_title:
                return True, "error page"

            return False, None
        except:
            return False, None

    def _handle_block(self, page, reason):
        """차단 감지 시 대응"""
        self.stats.add_error(f"🚫 차단 감지: {reason}")
        print(f"\n\n   ⚠️  차단 감지됨: {reason}")
        print(f"   ⏳ {self.retry_delay}초 후 재시도...")

        if self.unsaved_reviews:
            self._save_reviews_batch()
            print(f"   💾 현재까지 수집된 데이터 저장 완료")

        time.sleep(self.retry_delay)

        try:
            page.reload(wait_until="domcontentloaded")
            time.sleep(3)

            is_blocked, _ = self._check_blocked(page)
            if is_blocked:
                print(f"   ❌ 여전히 차단됨. 더 긴 대기 시간 적용...")
                time.sleep(self.retry_delay * 3)
                return False
            return True
        except:
            return False

    def _click_next_group(self, page):
        """'다음' 버튼 클릭하여 10페이지 그룹 건너뛰기

        Returns:
            (success, new_page_num): 성공 여부와 새 페이지 번호
        """
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.3)

        # "다음" 버튼 찾기
        next_btn_selectors = [
            "a[data-shp-area='revlist.pgn']:has-text('다음'):not([aria-hidden='true'])",
            "a:has-text('다음'):visible",
        ]

        for selector in next_btn_selectors:
            try:
                next_btn = page.locator(selector).first
                if next_btn.count() > 0 and next_btn.is_visible():
                    aria_hidden = next_btn.get_attribute("aria-hidden")
                    if aria_hidden == "true":
                        continue

                    # 클릭 전 현재 페이지 그룹 확인
                    try:
                        with page.expect_response(
                            lambda r: "reviews" in r.url, timeout=5000
                        ):
                            next_btn.click(force=True)
                        time.sleep(0.3)
                        return True
                    except:
                        pass
            except:
                continue

        return False

    def _skip_to_page(self, page, target_page):
        """'다음' 버튼을 반복 클릭하여 목표 페이지 근처까지 빠르게 스킵

        Args:
            page: Playwright 페이지 객체
            target_page: 목표 페이지 번호

        Returns:
            실제 도달한 페이지 번호
        """
        # 10페이지 그룹 수 계산 (예: 157페이지 -> 15번 "다음" 클릭)
        groups_to_skip = (target_page - 1) // 10

        if groups_to_skip <= 0:
            return 1

        print(f"\n   ⏩ 빠른 스킵: '다음' 버튼 {groups_to_skip}번 클릭 예정")

        current_group = 0
        for i in range(groups_to_skip):
            success = self._click_next_group(page)

            if success:
                current_group += 1
                # 진행 상황 표시
                if (i + 1) % 5 == 0 or i == groups_to_skip - 1:
                    estimated_page = (current_group * 10) + 1
                    print(
                        f"   ⏩ 스킵 진행: {current_group}/{groups_to_skip} ({estimated_page}페이지 근처)"
                    )
            else:
                print(
                    f"\n   ⚠️ 스킵 중단: {current_group}번째 그룹에서 '다음' 버튼 없음"
                )
                break

            # 10번마다 잠시 쿨다운 (차단 방지)
            if (i + 1) % 10 == 0:
                time.sleep(random.uniform(1.0, 2.0))

        # 도달한 페이지 번호 계산 (그룹 * 10 + 1)
        reached_page = (current_group * 10) + 1
        print(f"   ✅ 스킵 완료: 약 {reached_page}페이지 도달")

        return reached_page

    def _cooldown(self, seconds, reason="차단 감지"):
        """쿨다운 대기

        Args:
            seconds: 대기 시간 (초)
            reason: 쿨다운 이유
        """
        print(f"\n   ❄️  쿨다운: {reason}")
        for remaining in range(seconds, 0, -10):
            print(f"   ⏳ {remaining}초 남음...", end="\r", flush=True)
            time.sleep(min(10, remaining))
        print(f"   ✅ 쿨다운 완료, 재시도합니다...")

    def _click_next_page(self, page, current_page):
        """다음 페이지 클릭 - 강화된 재시도 로직

        Args:
            page: Playwright 페이지 객체
            current_page: 현재 페이지 번호
        """
        next_page_num = current_page + 1
        delay_min = NAVER_CONFIG.get("page_delay_min", 0.8)
        delay_max = NAVER_CONFIG.get("page_delay_max", 1.5)

        for attempt in range(self.pagination_retry_max):
            # 스크롤을 내려서 페이지네이션 영역 확실히 로딩
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.5)

            # 방법 1: 정확한 페이지 번호 버튼
            next_num_selector = f"a[data-shp-area='revlist.pgn'][data-shp-contents-id='{next_page_num}']"
            next_num_btn = page.locator(next_num_selector).first

            if next_num_btn.count() > 0 and next_num_btn.is_visible():
                try:
                    with page.expect_response(
                        lambda r: "reviews" in r.url, timeout=10000
                    ):
                        next_num_btn.click(force=True)
                    time.sleep(random.uniform(delay_min, delay_max))
                    return True, None
                except Exception as e:
                    self.stats.add_warning(
                        f"Page {current_page}: 버튼 클릭 실패 ({attempt+1})"
                    )

            # 방법 2: "다음" 버튼 찾기 (10페이지 그룹 넘어갈 때)
            next_btn_selectors = [
                "a[data-shp-area='revlist.pgn']:has-text('다음'):not([aria-hidden='true'])",
                "a:has-text('다음'):visible",
            ]

            for selector in next_btn_selectors:
                try:
                    next_btn = page.locator(selector).first
                    if next_btn.count() > 0 and next_btn.is_visible():
                        aria_hidden = next_btn.get_attribute("aria-hidden")
                        if aria_hidden == "true":
                            continue

                        try:
                            with page.expect_response(
                                lambda r: "reviews" in r.url, timeout=10000
                            ):
                                next_btn.click(force=True)
                            time.sleep(random.uniform(delay_min, delay_max))
                            return True, None
                        except:
                            pass
                except:
                    continue

            # 방법 3: 모든 페이지네이션 버튼 순회
            try:
                all_pgn_btns = page.locator("a[data-shp-area='revlist.pgn']").all()
                for btn in all_pgn_btns:
                    try:
                        text = btn.text_content().strip()
                        aria_hidden = btn.get_attribute("aria-hidden")
                        contents_id = btn.get_attribute("data-shp-contents-id")

                        if (
                            text == "다음" and aria_hidden != "true"
                        ) or contents_id == str(next_page_num):
                            try:
                                with page.expect_response(
                                    lambda r: "reviews" in r.url, timeout=10000
                                ):
                                    btn.click(force=True)
                                time.sleep(random.uniform(delay_min, delay_max))
                                return True, None
                            except:
                                pass
                    except:
                        continue
            except:
                pass

            # 재시도 전 대기
            if attempt < self.pagination_retry_max - 1:
                print(
                    f"\n   🔄 페이지네이션 재시도 ({attempt + 2}/{self.pagination_retry_max})..."
                )
                time.sleep(2)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight - 500)")
                time.sleep(1)

        return False, "다음 페이지 버튼을 찾을 수 없음"

    def get_targets(self):
        print(f"📂 타겟 파일 로딩: {INPUT_FILE}")
        try:
            df = pd.read_excel(INPUT_FILE)
            p_col = [c for c in df.columns if "플랫폼" in str(c)][0]
            naver_df = df[
                df[p_col]
                .astype(str)
                .str.contains("네이버|스마트스토어", case=False, na=False)
            ]
            print(f"   ✅ 네이버 상품 {len(naver_df)}개 발견")
            return naver_df
        except Exception as e:
            self.stats.add_error(f"타겟 파일 로딩 실패: {e}")
            print(f"   ❌ 오류: {e}")
            return pd.DataFrame()

    def crawl_product(self, page, url, product_index=0, total_products=0):
        """단일 상품 크롤링 - 이어서 크롤링 지원"""
        print(f"\n{'='*60}")
        print(f"🛒 상품 [{product_index}/{total_products}]: {url}")
        print(f"{'='*60}")

        self.collected_reviews = []
        self.unsaved_reviews = []
        self.stats.reset()

        # 상품 ID 추출
        try:
            prod_id = (
                url.split("/products/")[-1].split("?")[0].split("#")[0]
                if "/products/" in url
                else "unknown"
            )
        except:
            prod_id = "unknown"

        # 기존 데이터 로드 (이어서 크롤링)
        existing_ids, existing_reviews = self._load_existing_reviews(prod_id)
        self.saved_ids = existing_ids.copy()

        # 스킵할 페이지 수 계산 (기존 리뷰 수 / 페이지당 20개)
        self.skip_to_page = len(existing_ids) // 20 if existing_ids else 0

        # 파일 경로 설정
        filename = f"naver_reviews_{prod_id}.json"
        self._ensure_directory()
        self.current_file_path = os.path.join(self.current_output_dir, filename)

        # 기존 데이터가 있으면 현재 파일에 복사
        if existing_reviews:
            with open(self.current_file_path, "w", encoding="utf-8") as f:
                json.dump(existing_reviews, f, ensure_ascii=False, indent=2)
            print(f"   📋 기존 {len(existing_reviews):,}개 리뷰 로드됨")
            if self.skip_to_page > 0:
                print(f"   ⏩ 약 {self.skip_to_page}페이지까지 빠르게 스킵 예정")

        print(f"   💾 저장 경로: {self.current_file_path}")

        retry_count = 0

        while retry_count < self.max_retries:
            try:
                # 1. 페이지 이동
                target_url = url if "#REVIEW" in url else f"{url}#REVIEW"
                print(f"   🌐 페이지 로딩 중...")
                page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(3)

                # 차단 확인
                is_blocked, reason = self._check_blocked(page)
                if is_blocked:
                    if not self._handle_block(page, reason):
                        retry_count += 1
                        continue

                # 2. 리뷰 탭 활성화
                print(f"   📑 리뷰 탭 활성화 중...")
                review_tab_selector = "a[data-name='REVIEW']"

                try:
                    review_btn = page.locator(review_tab_selector).first
                    if review_btn.is_visible():
                        is_active = (
                            review_btn.get_attribute("aria-current") == "true"
                            or review_btn.get_attribute("aria-selected") == "true"
                        )
                        if not is_active:
                            review_btn.click()
                            time.sleep(3)
                    else:
                        page.locator("a:has-text('리뷰')").first.click()
                        time.sleep(3)
                except Exception as e:
                    self.stats.add_warning(f"리뷰 탭 클릭 실패: {e}")

                # 3. 최신순 정렬
                print(f"   🔄 최신순 정렬 중...")
                page.mouse.wheel(0, 500)
                time.sleep(1)

                sort_btn = page.locator("a:has-text('최신순')").first
                if sort_btn.is_visible():
                    try:
                        with page.expect_response(
                            lambda r: "reviews" in r.url, timeout=5000
                        ):
                            sort_btn.click(force=True)
                    except:
                        self.stats.add_warning("최신순 정렬 응답 타임아웃")
                    time.sleep(2)

                # 4. 페이지네이션
                print(f"   📄 리뷰 수집 시작...")
                max_pages = 99999
                consecutive_failures = 0
                max_consecutive_failures = 5
                cooldown_count = 0
                max_cooldowns = 3  # 최대 쿨다운 횟수

                # 빠른 스킵: '다음' 버튼으로 10페이지씩 건너뛰기
                skip_target = getattr(self, "skip_to_page", 0)
                if skip_target > 10:
                    current_page = self._skip_to_page(page, skip_target)
                else:
                    current_page = 1

                while current_page < max_pages:
                    # 다음 페이지 클릭
                    success, error = self._click_next_page(page, current_page)

                    if success:
                        current_page += 1
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1

                        # 리뷰가 로딩되지 않음 = 차단 가능성
                        if consecutive_failures >= max_consecutive_failures:
                            # 현재까지 저장
                            if self.unsaved_reviews:
                                self._save_reviews_batch()

                            # 마지막 페이지인지 먼저 확인
                            if (
                                self.stats.total_pages > 0
                                and current_page >= self.stats.total_pages
                            ):
                                print(
                                    f"\n   ✅ 마지막 페이지 도달 ({current_page}/{self.stats.total_pages})"
                                )
                                break

                            # 쿨다운 시도
                            if cooldown_count < max_cooldowns:
                                cooldown_count += 1
                                cooldown_seconds = (
                                    30 * cooldown_count
                                )  # 30초, 60초, 90초
                                self._cooldown(
                                    cooldown_seconds,
                                    f"연속 {consecutive_failures}회 실패 (쿨다운 {cooldown_count}/{max_cooldowns})",
                                )

                                # 페이지 새로고침 후 재시도
                                try:
                                    page.reload(wait_until="domcontentloaded")
                                    time.sleep(3)

                                    # 리뷰 탭 다시 활성화
                                    review_btn = page.locator(
                                        "a[data-name='REVIEW']"
                                    ).first
                                    if review_btn.is_visible():
                                        review_btn.click()
                                        time.sleep(2)

                                    # 최신순 정렬 다시
                                    sort_btn = page.locator(
                                        "a:has-text('최신순')"
                                    ).first
                                    if sort_btn.is_visible():
                                        sort_btn.click(force=True)
                                        time.sleep(2)

                                    # 현재 페이지로 다시 이동
                                    if current_page > 10:
                                        print(
                                            f"   🔄 {current_page}페이지로 복귀 중..."
                                        )
                                        reached = self._skip_to_page(page, current_page)
                                        current_page = reached

                                    consecutive_failures = 0
                                    continue
                                except Exception as e:
                                    self.stats.add_error(f"복구 실패: {e}")
                            else:
                                self.stats.add_error(
                                    f"최대 쿨다운 횟수 초과 (page {current_page})"
                                )
                                break

                        # 마지막 페이지인지 확인
                        if (
                            self.stats.total_pages > 0
                            and current_page >= self.stats.total_pages
                        ):
                            print(
                                f"\n   ✅ 마지막 페이지 도달 ({current_page}/{self.stats.total_pages})"
                            )
                            break

                    # 주기적 차단 확인 (100페이지마다)
                    if current_page % 100 == 0:
                        is_blocked, reason = self._check_blocked(page)
                        if is_blocked:
                            if cooldown_count < max_cooldowns:
                                cooldown_count += 1
                                self._cooldown(60, f"차단 감지: {reason}")
                                if not self._handle_block(page, reason):
                                    break
                            else:
                                break

                # 성공적으로 완료
                break

            except PlaywrightTimeout as e:
                retry_count += 1
                self.stats.add_error(
                    f"타임아웃 (시도 {retry_count}/{self.max_retries})"
                )
                print(
                    f"\n   ⏰ 타임아웃 발생. 재시도 {retry_count}/{self.max_retries}..."
                )
                time.sleep(self.retry_delay)

            except Exception as e:
                retry_count += 1
                self.stats.add_error(f"{type(e).__name__}: {str(e)[:50]}")
                print(f"\n   ❌ 오류: {e}")
                print(f"   🔄 재시도 {retry_count}/{self.max_retries}...")
                time.sleep(self.retry_delay)

        # 남은 리뷰 저장
        if self.unsaved_reviews:
            self._save_reviews_batch()

        # 최종 요약 출력
        print(self.stats.get_summary(len(self.collected_reviews)))

    def _save_reviews_batch(self):
        """배치로 리뷰를 파일에 저장"""
        if not self.current_file_path or not self.unsaved_reviews:
            return

        try:
            if os.path.exists(self.current_file_path):
                with open(self.current_file_path, "r", encoding="utf-8") as f:
                    existing_reviews = json.load(f)
            else:
                existing_reviews = []

            existing_reviews.extend(self.unsaved_reviews)
            existing_reviews.sort(key=lambda x: x.get("createDate", ""), reverse=True)

            with open(self.current_file_path, "w", encoding="utf-8") as f:
                json.dump(existing_reviews, f, ensure_ascii=False, indent=2)

            saved_count = len(self.unsaved_reviews)
            self.unsaved_reviews = []
            print(f"\n   💾 배치 저장: {saved_count}개 리뷰")

        except Exception as e:
            self.stats.add_error(f"저장 실패: {e}")

    def run(self):
        """메인 실행"""
        print("\n" + "=" * 60)
        print("🚀 네이버 스마트스토어 리뷰 크롤러 시작")
        print("=" * 60)

        targets = self.get_targets()
        if targets.empty:
            print("❌ 크롤링 대상 없음")
            return

        total_products = len(targets)
        print(f"\n📊 총 {total_products}개 상품 크롤링 예정")
        print(f"💡 기존 데이터가 있으면 이어서 크롤링합니다.")

        user_data_dir = os.path.join(os.getcwd(), "browser_profile")
        if os.path.exists(user_data_dir):
            try:
                shutil.rmtree(user_data_dir)
            except:
                pass

        overall_start = time.time()
        completed_products = 0
        total_reviews_all = 0

        with sync_playwright() as p:
            print("\n🌐 Chrome 브라우저 실행 중...")
            try:
                browser = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    channel=NAVER_CONFIG.get("channel", "chrome"),
                    headless=NAVER_CONFIG.get("headless", False),
                    viewport=NAVER_CONFIG.get(
                        "viewport", {"width": 1600, "height": 900}
                    ),
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                )
            except Exception as e:
                print(f"❌ 브라우저 실행 실패: {e}")
                return

            page = browser.pages[0]
            page.add_init_script(STEALTH_JS)
            page.on("response", self.handle_response)

            product_delay = NAVER_CONFIG.get("product_delay", 5)

            for index, row in targets.iterrows():
                try:
                    addr_col = [c for c in targets.columns if "주소" in str(c)][0]
                    url = row[addr_col]
                except:
                    continue

                completed_products += 1
                self.crawl_product(page, url, completed_products, total_products)
                total_reviews_all += len(self.collected_reviews)

                if completed_products < total_products:
                    print(f"\n⏳ 다음 상품까지 {product_delay}초 대기...")
                    time.sleep(product_delay)

            browser.close()

        overall_elapsed = time.time() - overall_start
        elapsed_str = time.strftime("%H:%M:%S", time.gmtime(overall_elapsed))

        print("\n" + "=" * 60)
        print("🎉 전체 크롤링 완료!")
        print("=" * 60)
        print(f"  📦 완료 상품: {completed_products}/{total_products}")
        print(f"  📝 신규 리뷰: {total_reviews_all:,}개")
        print(f"  ⏱️  총 소요 시간: {elapsed_str}")
        print(f"  📁 저장 위치: {self.current_output_dir}")
        print("=" * 60)
