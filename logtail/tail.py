import glob
import os
import time
import threading
from typing import List, Dict, Callable, Any


class LogTailer:
    def __init__(self, patterns: List[str], callback: Callable[[Dict[str, Any]], None] = None):
        self.patterns = patterns
        self.callback = callback
        self.files: Dict[str, int] = {}
        self.running = False
        self.thread: threading.Thread = None
        
    def get_matching_files(self) -> List[str]:
        matched_files = set()
        for pattern in self.patterns:
            matched_files.update(glob.glob(pattern, recursive=True))
        return list(matched_files)
    
    def tail_file(self, file_path: str):
        if file_path not in self.files:
            try:
                with open(file_path, 'r') as f:
                    f.seek(0, 2)
                    self.files[file_path] = f.tell()
            except (IOError, OSError):
                return
        
        try:
            with open(file_path, 'r') as f:
                f.seek(self.files[file_path])
                lines = f.readlines()
                self.files[file_path] = f.tell()
                
                for line in lines:
                    line = line.rstrip('\n')
                    if line and self.callback:
                        self.callback({
                            'file': file_path,
                            'line': line,
                            'timestamp': time.time()
                        })
        except (IOError, OSError):
            pass
    
    def check_new_files(self):
        current_files = set(self.files.keys())
        matched_files = set(self.get_matching_files())
        
        new_files = matched_files - current_files
        for file_path in new_files:
            try:
                with open(file_path, 'r') as f:
                    f.seek(0, 2)
                    self.files[file_path] = f.tell()
            except (IOError, OSError):
                pass
        
        removed_files = current_files - matched_files
        for file_path in removed_files:
            if file_path in self.files:
                del self.files[file_path]
    
    def start(self, poll_interval: float = 0.1):
        self.running = True
        self.check_new_files()
        
        def tail_loop():
            while self.running:
                self.check_new_files()
                for file_path in list(self.files.keys()):
                    self.tail_file(file_path)
                time.sleep(poll_interval)
        
        self.thread = threading.Thread(target=tail_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
