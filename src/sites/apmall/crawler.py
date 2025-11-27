# src/crawlers/apmall.py
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import os
import time
import random
import pandas as pd
from datetime import datetime
from src.core.config import HEADERS, API_URL, INPUT_FILE, MIN_DELAY, MAX_DELAY
from src.core.base_crawler import BaseCrawler
from src.utils import extract_prod_sn

class APMallCrawler(BaseCrawler):
    def __init__(self):
        super().__init__(site_name="apmall")
        self.headers = HEADERS.copy()
        self.session = self._init_session()
        
    def _init_session(self):
        session = requests.Session()
        session.headers.update(self.headers)
        
        # Retry strategy: 3 retries with exponential backoff
        # Status codes: 429 (Too Many Requests), 500, 502, 503, 504
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        return session

    def get_targets(self):
        print(f"Reading targets from {INPUT_FILE}...")
        try:
            df = pd.read_excel(INPUT_FILE)
            
            # Column matching
            platform_col = [c for c in df.columns if "플랫폼" in str(c)]
            address_col = [c for c in df.columns if "주소" in str(c)]
            
            if not platform_col or not address_col:
                print("Could not find '플랫폼' or '주소' columns in targets file.")
                return pd.DataFrame()

            # Filter for AP Mall
            return df[df[platform_col[0]] == "AP몰"]
            
        except Exception as e:
            print(f"Error reading targets file: {e}")
            return pd.DataFrame()

    def fetch_reviews(self, prod_sn, referer_url):
        # Update Referer for current product
        self.session.headers.update({"Referer": referer_url})
        
        all_reviews = []
        offset = 0
        limit = 10
        total_count = None
        
        print(f"\nStarting crawl for product {prod_sn}...")
        
        while True:
            params = {
                "onlineProdSn": prod_sn,
                "offset": offset,
                "prodReviewUnit": "OnlineProd",
                "prodReviewType": "All",
                "prodReviewSort": "Last",  # Latest reviews
                "scope": "All",
                "opinion": "",
                "filterMemberAttrYn": "N",
                "limit": limit,
                "imageOnlyYn": "N",
            }
            
            try:
                # Use session instead of direct requests.get
                response = self.session.get(API_URL, params=params, timeout=10)
                
                if response.status_code != 200:
                    print(f"Request failed with status {response.status_code}")
                    break
                    
                data = response.json()
                
                if total_count is None:
                    total_count = data.get("totalCount", 0)
                    print(f"Total reviews available: {total_count}")
                
                reviews = data.get("prodReviewList", [])
                if not reviews:
                    print("No more reviews returned.")
                    break
                    
                all_reviews.extend(reviews)
                print(f"Fetched {len(reviews)} reviews. Progress: {len(all_reviews)}/{total_count}")
                
                offset += limit
                if offset >= total_count:
                    break
                
                # Randomized polite delay between pages
                delay = random.uniform(MIN_DELAY, MAX_DELAY)
                time.sleep(delay)
                
            except Exception as e:
                print(f"Error during request: {e}")
                break
                
        return all_reviews

    def save_reviews(self, prod_sn, reviews):
        if not reviews:
            print(f"No reviews to save for product {prod_sn}")
            return

        filename = f"apmall_reviews_{prod_sn}.json"
        self.save_json(reviews, filename)

    def run(self):
        targets = self.get_targets()
        print(f"Found {len(targets)} AP Mall targets.")
        
        # Iterate through all targets
        for index, row in targets.iterrows():
            # Re-find address column for safety inside loop or assume standard
            address_col = [c for c in targets.columns if "주소" in str(c)][0]
            url = row[address_col]
            prod_sn = extract_prod_sn(url)
            
            if not prod_sn:
                print(f"Could not extract onlineProdSn from {url}")
                continue
                
            reviews = self.fetch_reviews(prod_sn, url)
            self.save_reviews(prod_sn, reviews)
            
            # Long pause between products
            product_pause = random.uniform(5.0, 10.0)
            print(f"Pausing for {product_pause:.1f}s before next product...")
            time.sleep(product_pause)
