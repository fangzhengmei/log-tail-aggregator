import glob
import os
import time
import threading
import sys
from typing import List, Dict, Callable, Any


DEFAULT_ENCODINGS = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1']


def read_lines_with_fallback(file_path: str, offset: int = 0, 
                              encodings: List[str] = None) -> tuple:
    """
    读取文件行，支持多编码回退机制
    
    返回: (lines, new_offset, used_encoding)
    """
    if encodings is None:
        encodings = DEFAULT_ENCODINGS
    
    last_error = None
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                f.seek(offset)
                lines = f.readlines()
                new_offset = f.tell()
                return lines, new_offset, encoding
        except UnicodeDecodeError as e:
            last_error = e
            continue
        except (IOError, OSError) as e:
            raise e
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            f.seek(offset)
            lines = f.readlines()
            new_offset = f.tell()
            print(f"警告: 文件 '{file_path}' 包含非 UTF-8 编码字符，已使用替换模式读取", file=sys.stderr)
            return lines, new_offset, 'utf-8 (replace)'
    except Exception as e:
        raise UnicodeDecodeError(
            'utf-8', b'', 0, 0,
            f"无法解码文件 '{file_path}': 所有编码尝试均失败，最后错误: {last_error}"
        ) from last_error


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
                with open(file_path, 'rb') as f:
                    f.seek(0, 2)
                    self.files[file_path] = f.tell()
            except (IOError, OSError):
                return
        
        try:
            lines, new_offset, _ = read_lines_with_fallback(
                file_path, 
                offset=self.files[file_path]
            )
            self.files[file_path] = new_offset
            
            for line in lines:
                line = line.rstrip('\n')
                if line and self.callback:
                    self.callback({
                        'file': file_path,
                        'line': line,
                        'timestamp': time.time()
                    })
        except UnicodeDecodeError:
            pass
        except (IOError, OSError):
            pass
    
    def check_new_files(self):
        current_files = set(self.files.keys())
        matched_files = set(self.get_matching_files())
        
        new_files = matched_files - current_files
        for file_path in new_files:
            try:
                with open(file_path, 'rb') as f:
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
