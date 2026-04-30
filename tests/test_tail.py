import pytest
import tempfile
import os
import time
import threading
from unittest.mock import Mock, patch

from logtail.tail import LogTailer


class TestLogTailer:
    def test_get_matching_files_single_file(self, tmp_path):
        log_file = tmp_path / 'test.log'
        log_file.write_text('line1\nline2\n')
        
        tailer = LogTailer(patterns=[str(log_file)])
        files = tailer.get_matching_files()
        
        assert len(files) == 1
        assert str(log_file) in files
    
    def test_get_matching_files_glob(self, tmp_path):
        (tmp_path / 'app1.log').write_text('log1\n')
        (tmp_path / 'app2.log').write_text('log2\n')
        (tmp_path / 'other.txt').write_text('text\n')
        
        tailer = LogTailer(patterns=[str(tmp_path / '*.log')])
        files = tailer.get_matching_files()
        
        assert len(files) == 2
        assert any('app1.log' in f for f in files)
        assert any('app2.log' in f for f in files)
    
    def test_get_matching_files_multiple_patterns(self, tmp_path):
        (tmp_path / 'access.log').write_text('access\n')
        (tmp_path / 'error.log').write_text('error\n')
        (tmp_path / 'debug.log').write_text('debug\n')
        
        tailer = LogTailer(patterns=[
            str(tmp_path / 'access.log'),
            str(tmp_path / 'error.log')
        ])
        files = tailer.get_matching_files()
        
        assert len(files) == 2
    
    def test_get_matching_files_recursive(self, tmp_path):
        subdir = tmp_path / 'subdir'
        subdir.mkdir()
        (subdir / 'deep.log').write_text('deep\n')
        
        tailer = LogTailer(patterns=[str(tmp_path / '**' / '*.log')])
        files = tailer.get_matching_files()
        
        assert len(files) == 1
        assert any('deep.log' in f for f in files)
    
    def test_get_matching_files_nonexistent(self, tmp_path):
        tailer = LogTailer(patterns=[str(tmp_path / 'nonexistent.log')])
        files = tailer.get_matching_files()
        
        assert len(files) == 0
    
    def test_tail_file_new_content(self, tmp_path):
        log_file = tmp_path / 'test.log'
        log_file.write_text('initial line\n')
        
        callback = Mock()
        tailer = LogTailer(patterns=[str(log_file)], callback=callback)
        tailer.check_new_files()
        
        initial_pos = log_file.stat().st_size
        with open(str(log_file), 'a') as f:
            f.write('new line1\n')
            f.write('new line2\n')
        
        tailer.tail_file(str(log_file))
        
        assert callback.call_count == 2
        calls = callback.call_args_list
        
        assert calls[0][0][0]['line'] == 'new line1'
        assert calls[1][0][0]['line'] == 'new line2'
    
    def test_tail_file_no_new_content(self, tmp_path):
        log_file = tmp_path / 'test.log'
        log_file.write_text('line1\nline2\n')
        
        callback = Mock()
        tailer = LogTailer(patterns=[str(log_file)], callback=callback)
        tailer.files[str(log_file)] = log_file.stat().st_size
        
        tailer.tail_file(str(log_file))
        
        callback.assert_not_called()
    
    def test_tail_file_nonexistent(self):
        callback = Mock()
        tailer = LogTailer(patterns=['nonexistent.log'], callback=callback)
        
        tailer.tail_file('nonexistent.log')
        
        callback.assert_not_called()
    
    def test_check_new_files(self, tmp_path):
        log1 = tmp_path / 'log1.log'
        log1.write_text('line1\n')
        
        tailer = LogTailer(patterns=[str(tmp_path / '*.log')])
        tailer.check_new_files()
        
        assert len(tailer.files) == 1
        assert str(log1) in tailer.files
        
        log2 = tmp_path / 'log2.log'
        log2.write_text('line2\n')
        
        tailer.check_new_files()
        
        assert len(tailer.files) == 2
        assert str(log2) in tailer.files
    
    def test_check_removed_files(self, tmp_path):
        log1 = tmp_path / 'log1.log'
        log1.write_text('line1\n')
        log2 = tmp_path / 'log2.log'
        log2.write_text('line2\n')
        
        tailer = LogTailer(patterns=[str(tmp_path / '*.log')])
        tailer.check_new_files()
        
        assert len(tailer.files) == 2
        
        os.remove(str(log2))
        
        tailer.check_new_files()
        
        assert len(tailer.files) == 1
        assert str(log2) not in tailer.files
    
    def test_start_and_stop(self, tmp_path):
        log_file = tmp_path / 'test.log'
        log_file.write_text('initial\n')
        
        callback = Mock()
        tailer = LogTailer(patterns=[str(log_file)], callback=callback)
        
        tailer.start(poll_interval=0.01)
        
        time.sleep(0.05)
        
        log_file.write_text('initial\nnew line\n')
        
        time.sleep(0.05)
        
        tailer.stop()
        
        assert callback.call_count >= 1
        assert any('new line' in call[0][0]['line'] for call in callback.call_args_list)
    
    def test_callback_receives_correct_data(self, tmp_path):
        log_file = tmp_path / 'test.log'
        log_file.write_text('initial\n')
        
        callback = Mock()
        tailer = LogTailer(patterns=[str(log_file)], callback=callback)
        tailer.check_new_files()
        
        with open(str(log_file), 'a') as f:
            f.write('test message\n')
        
        tailer.tail_file(str(log_file))
        
        callback.assert_called_once()
        data = callback.call_args[0][0]
        
        assert data['file'] == str(log_file)
        assert data['line'] == 'test message'
        assert 'timestamp' in data
        assert isinstance(data['timestamp'], float)
    
    def test_empty_line_ignored(self, tmp_path):
        log_file = tmp_path / 'test.log'
        log_file.write_text('line1\n\nline2\n')
        
        callback = Mock()
        tailer = LogTailer(patterns=[str(log_file)], callback=callback)
        tailer.files[str(log_file)] = 0
        
        tailer.tail_file(str(log_file))
        
        assert callback.call_count == 2
