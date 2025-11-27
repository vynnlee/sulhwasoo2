from abc import ABC, abstractmethod
import os
import json
from datetime import datetime
from typing import List, Dict, Any

from src.core.config import DATA_RAW_DIR

class BaseCrawler(ABC):
    def __init__(self, site_name: str):
        self.site_name = site_name
        self.base_output_dir = os.path.join(DATA_RAW_DIR, self.site_name)
        self.timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.current_output_dir = os.path.join(self.base_output_dir, self.timestamp)

    def _ensure_directory(self):
        """출력 디렉토리가 존재하는지 확인하고 생성합니다."""
        os.makedirs(self.current_output_dir, exist_ok=True)

    def save_json(self, data: List[Dict[str, Any]], filename: str):
        """데이터를 JSON 파일로 저장합니다."""
        self._ensure_directory()
        
        # 파일명에 .json이 없으면 추가
        if not filename.endswith('.json'):
            filename += '.json'
            
        file_path = os.path.join(self.current_output_dir, filename)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[{self.site_name}] Saved {len(data)} records to {file_path}")
        except Exception as e:
            print(f"[{self.site_name}] Error saving file {filename}: {e}")

    @abstractmethod
    def run(self):
        """
        실제 크롤링 로직을 구현해야 하는 메서드입니다.
        """
        pass

