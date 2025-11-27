import sys
import os
import argparse

# Ensure src is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    parser = argparse.ArgumentParser(description="Sulhwasoo Review Crawler")
    parser.add_argument("--site", type=str, default="apmall", help="Target site to crawl (default: apmall)")
    args = parser.parse_args()

    if args.site == "apmall":
        # Import lazily to avoid errors if module is missing
        try:
            from src.sites.apmall.crawler import APMallCrawler
            print("Initializing AP Mall Crawler...")
            crawler = APMallCrawler()
            crawler.run()
        except ImportError as e:
            print(f"Error loading APMallCrawler: {e}")
            
    elif args.site == "naver":
        try:
            from src.sites.naver.crawler import NaverCrawler
            print("Initializing Naver Crawler...")
            crawler = NaverCrawler()
            crawler.run()
        except ImportError as e:
            print(f"Error loading NaverCrawler: {e}")
            
    else:
        print(f"Error: Unknown site '{args.site}'")
        sys.exit(1)

    print("\nCrawling completed.")

if __name__ == "__main__":
    main()
