import os
import csv
import datetime
from typing import List, Dict, Optional


class ConversationManager:
    def __init__(self, timeout_minutes: int = 5) -> None:
        self.timeout_minutes = timeout_minutes
        self.conversation_history: List[Dict[str, str]] = []
        self.conversation_start_time: Optional[datetime.datetime] = None
        self.last_interaction_time: Optional[datetime.datetime] = None
        self.csv_file_path: Optional[str] = None
    
    def start_new_conversation(self) -> None:
        self.conversation_start_time = datetime.datetime.now()
        self.last_interaction_time = self.conversation_start_time
        self.conversation_history = []
        
        filename = self.conversation_start_time.strftime("%Y-%m-%d_%H-%M-%S.csv")
        self.csv_file_path = os.path.join("conversations", filename)
        
        with open(self.csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['timestamp', 'speaker', 'message'])
        
        print(f"📝 New conversation started: {filename}")
    
    def log_interaction(self, speaker: str, message: str) -> None:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        self.conversation_history.append({
            "role": "user" if speaker == "user" else "assistant",
            "content": message
        })
        
        if self.csv_file_path:
            with open(self.csv_file_path, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([timestamp, speaker, message])
        
        self.last_interaction_time = datetime.datetime.now()
    
    def is_conversation_expired(self) -> bool:
        if self.last_interaction_time is None:
            return True
        
        time_since_last = datetime.datetime.now() - self.last_interaction_time
        return time_since_last.total_seconds() > (self.timeout_minutes * 60)
    
    def get_conversation_for_openai(self, system_prompt: str) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.conversation_history)
        return messages