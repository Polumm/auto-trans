#!/usr/bin/env python3
"""
Audio Transcription Tool
Automated audio downloading and transcription using yt-dlp and Whisper
Supports multiprocessing, auto cleanup, and clipboard functionality
"""

import os
import sys
import json
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import argparse
import logging

try:
    import whisper
except ImportError:
    try:
        import faster_whisper as whisper
        USING_FASTER_WHISPER = True
    except ImportError:
        print("Missing Whisper package. Install one of:")
        print("pip install openai-whisper  # Original Whisper")
        print("pip install faster-whisper  # Faster alternative")
        sys.exit(1)
else:
    USING_FASTER_WHISPER = False

try:
    import pyperclip
    import yt_dlp
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Please install required packages:")
    print("pip install pyperclip yt-dlp")
    sys.exit(1)


@dataclass
class TranscriptionJob:
    """Represents a single transcription job"""
    url: str
    job_id: str
    audio_format: Optional[str] = None
    language: Optional[str] = None
    status: str = "pending"
    audio_file: Optional[str] = None
    transcript: Optional[str] = None
    error: Optional[str] = None


class AudioTranscriber:
    """Main class for handling audio download and transcription"""
    
    def __init__(self, max_workers: int = 4, temp_dir: Optional[str] = None, 
                 whisper_model: str = "medium", auto_cleanup: bool = True):
        self.max_workers = max_workers
        self.temp_dir = temp_dir or tempfile.gettempdir()
        self.whisper_model = whisper_model
        self.auto_cleanup = auto_cleanup
        self.jobs: Dict[str, TranscriptionJob] = {}
        self.model = None
        self._setup_logging()
        
    def _setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('transcription.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def _load_whisper_model(self):
        """Load Whisper model (lazy loading)"""
        if self.model is None:
            self.logger.info(f"Loading Whisper model: {self.whisper_model}")
            if USING_FASTER_WHISPER:
                from faster_whisper import WhisperModel
                self.model = WhisperModel(self.whisper_model)
            else:
                self.model = whisper.load_model(self.whisper_model)
            
    def get_available_formats(self, url: str) -> List[Dict]:
        """Get available audio formats for a URL"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = info.get('formats', [])
                
                # Filter audio-only formats
                audio_formats = []
                for fmt in formats:
                    if fmt.get('vcodec') == 'none' or 'audio only' in str(fmt.get('format_note', '')):
                        audio_formats.append({
                            'format_id': fmt.get('format_id'),
                            'ext': fmt.get('ext'),
                            'abr': fmt.get('abr'),
                            'filesize': fmt.get('filesize'),
                            'format_note': fmt.get('format_note', ''),
                        })
                
                return sorted(audio_formats, key=lambda x: x.get('abr', 0), reverse=True)
                
        except Exception as e:
            self.logger.error(f"Error getting formats for {url}: {e}")
            return []
    
    def _download_audio(self, job: TranscriptionJob) -> bool:
        """Download audio from URL"""
        try:
            job.status = "downloading"
            self.logger.info(f"Downloading audio for job {job.job_id}")
            
            # Create unique filename
            safe_id = "".join(c for c in job.job_id if c.isalnum() or c in ('-', '_'))
            audio_file = os.path.join(self.temp_dir, f"audio_{safe_id}.%(ext)s")
            
            ydl_opts = {
                'format': job.audio_format or 'bestaudio/best',
                'outtmpl': audio_file,
                'quiet': True,
                'no_warnings': True,
                'extractaudio': True,
                'audioformat': 'mp3',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([job.url])
                
            # Find the downloaded file
            base_path = audio_file.replace('.%(ext)s', '')
            possible_extensions = ['.mp3', '.m4a', '.wav', '.webm', '.ogg']
            
            for ext in possible_extensions:
                potential_file = base_path + ext
                if os.path.exists(potential_file):
                    job.audio_file = potential_file
                    self.logger.info(f"Audio downloaded: {job.audio_file}")
                    return True
                    
            raise FileNotFoundError("Downloaded audio file not found")
            
        except Exception as e:
            job.error = f"Download error: {str(e)}"
            job.status = "failed"
            self.logger.error(f"Download failed for job {job.job_id}: {e}")
            return False
    
    def _transcribe_audio(self, job: TranscriptionJob) -> bool:
        """Transcribe audio file using Whisper"""
        try:
            job.status = "transcribing"
            self.logger.info(f"Transcribing audio for job {job.job_id}")
            
            self._load_whisper_model()
            
            # Transcribe with language detection or specified language
            transcribe_options = {}
            if job.language:
                transcribe_options['language'] = job.language
            
            if USING_FASTER_WHISPER:
                segments, info = self.model.transcribe(job.audio_file, **transcribe_options)
                job.transcript = " ".join([segment.text for segment in segments]).strip()
            else:
                result = self.model.transcribe(job.audio_file, **transcribe_options)
                job.transcript = result['text'].strip()
            job.status = "completed"
            
            self.logger.info(f"Transcription completed for job {job.job_id}")
            return True
            
        except Exception as e:
            job.error = f"Transcription error: {str(e)}"
            job.status = "failed"
            self.logger.error(f"Transcription failed for job {job.job_id}: {e}")
            return False
    
    def _cleanup_audio_file(self, job: TranscriptionJob):
        """Clean up downloaded audio file"""
        if self.auto_cleanup and job.audio_file and os.path.exists(job.audio_file):
            try:
                os.remove(job.audio_file)
                self.logger.info(f"Cleaned up audio file: {job.audio_file}")
            except Exception as e:
                self.logger.warning(f"Failed to cleanup {job.audio_file}: {e}")
    
    def _process_job(self, job: TranscriptionJob):
        """Process a single transcription job"""
        try:
            # Download audio
            if not self._download_audio(job):
                return
                
            # Transcribe audio
            if not self._transcribe_audio(job):
                return
                
        finally:
            # Cleanup
            self._cleanup_audio_file(job)
    
    def add_job(self, url: str, audio_format: Optional[str] = None, 
                language: Optional[str] = None) -> str:
        """Add a new transcription job"""
        job_id = f"job_{int(time.time() * 1000)}_{len(self.jobs)}"
        job = TranscriptionJob(
            url=url,
            job_id=job_id,
            audio_format=audio_format,
            language=language
        )
        self.jobs[job_id] = job
        return job_id
    
    def process_jobs(self) -> Dict[str, TranscriptionJob]:
        """Process all pending jobs using multiprocessing"""
        pending_jobs = [job for job in self.jobs.values() if job.status == "pending"]
        
        if not pending_jobs:
            self.logger.info("No pending jobs to process")
            return self.jobs
            
        self.logger.info(f"Processing {len(pending_jobs)} jobs with {self.max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_job = {executor.submit(self._process_job, job): job for job in pending_jobs}
            
            for future in as_completed(future_to_job):
                job = future_to_job[future]
                try:
                    future.result()
                except Exception as e:
                    job.error = f"Processing error: {str(e)}"
                    job.status = "failed"
                    self.logger.error(f"Job {job.job_id} failed: {e}")
        
        return self.jobs
    
    def get_job_status(self, job_id: str) -> Optional[TranscriptionJob]:
        """Get status of a specific job"""
        return self.jobs.get(job_id)
    
    def get_all_jobs(self) -> Dict[str, TranscriptionJob]:
        """Get all jobs"""
        return self.jobs
    
    def copy_transcript_to_clipboard(self, job_id: str) -> bool:
        """Copy transcript to clipboard with URL prefix"""
        job = self.jobs.get(job_id)
        if job and job.transcript:
            try:
                # Include URL at the beginning for easy reference
                clipboard_content = f"Source: {job.url}\n\n{job.transcript}"
                pyperclip.copy(clipboard_content)
                self.logger.info(f"Transcript with URL copied to clipboard for job {job_id}")
                return True
            except Exception as e:
                self.logger.error(f"Failed to copy to clipboard: {e}")
                return False
        return False
    
    def save_transcript(self, job_id: str, filename: str) -> bool:
        """Save transcript to file"""
        job = self.jobs.get(job_id)
        if job and job.transcript:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"URL: {job.url}\n")
                    f.write(f"Job ID: {job.job_id}\n")
                    f.write(f"Language: {job.language or 'auto-detected'}\n")
                    f.write("=" * 50 + "\n")
                    f.write(job.transcript)
                self.logger.info(f"Transcript saved to {filename}")
                return True
            except Exception as e:
                self.logger.error(f"Failed to save transcript: {e}")
                return False
        return False


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description="Audio Transcription Tool")
    parser.add_argument("urls", nargs="*", help="URLs to process")
    parser.add_argument("--workers", "-w", type=int, default=4, help="Number of worker threads")
    parser.add_argument("--model", "-m", default="base", help="Whisper model to use")
    parser.add_argument("--language", "-l", help="Language code (e.g., 'en', 'zh')")
    parser.add_argument("--format", "-f", help="Audio format ID to download")
    parser.add_argument("--no-cleanup", action="store_true", help="Don't delete audio files after transcription")
    parser.add_argument("--list-formats", action="store_true", help="List available formats for URLs")
    parser.add_argument("--output", "-o", help="Save transcripts to file")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    
    args = parser.parse_args()
    
    transcriber = AudioTranscriber(
        max_workers=args.workers,
        whisper_model=args.model,
        auto_cleanup=not args.no_cleanup
    )
    
    if args.interactive:
        interactive_mode(transcriber)
        return
    
    if not args.urls:
        parser.print_help()
        return
    
    # List formats mode
    if args.list_formats:
        for url in args.urls:
            print(f"\nAvailable formats for {url}:")
            formats = transcriber.get_available_formats(url)
            if formats:
                print(f"{'ID':<10} {'EXT':<5} {'ABR':<6} {'SIZE':<10} {'NOTE'}")
                print("-" * 50)
                for fmt in formats:
                    size = fmt.get('filesize')
                    size_str = f"{size//1024//1024:.1f}MB" if size else "N/A"
                    print(f"{fmt['format_id']:<10} {fmt['ext']:<5} {fmt.get('abr', 'N/A'):<6} {size_str:<10} {fmt['format_note']}")
            else:
                print("No audio formats found")
        return
    
    # Add jobs
    job_ids = []
    for url in args.urls:
        job_id = transcriber.add_job(url, args.format, args.language)
        job_ids.append(job_id)
        print(f"Added job {job_id} for {url}")
    
    # Process jobs
    print(f"\nProcessing {len(job_ids)} jobs...")
    results = transcriber.process_jobs()
    
    # Display results
    print("\n" + "="*60)
    print("TRANSCRIPTION RESULTS")
    print("="*60)
    
    for job_id in job_ids:
        job = results[job_id]
        print(f"\nJob ID: {job_id}")
        print(f"URL: {job.url}")
        print(f"Status: {job.status}")
        
        if job.status == "completed":
            print(f"Transcript:\n{job.transcript}")
            
            # Automatically copy to clipboard for single URL processing
            if len(job_ids) == 1:
                if transcriber.copy_transcript_to_clipboard(job_id):
                    print("✓ Transcript (with URL) copied to clipboard")
            else:
                # For multiple URLs, still copy but mention it's automatic
                if transcriber.copy_transcript_to_clipboard(job_id):
                    print("✓ Transcript (with URL) copied to clipboard")
            
            # Save to file if requested
            if args.output:
                filename = f"{args.output}_{job_id}.txt"
                if transcriber.save_transcript(job_id, filename):
                    print(f"✓ Transcript saved to {filename}")
                    
        elif job.status == "failed":
            print(f"Error: {job.error}")
        
        print("-" * 40)


def interactive_mode(transcriber: AudioTranscriber):
    """Interactive CLI mode"""
    print("=== Audio Transcription Tool - Interactive Mode ===")
    print("Commands: add, list, process, copy, save, formats, quit")
    
    while True:
        try:
            cmd = input("\n> ").strip().split()
            if not cmd:
                continue
                
            action = cmd[0].lower()
            
            if action == "quit" or action == "q":
                break
                
            elif action == "add":
                if len(cmd) < 2:
                    print("Usage: add <url> [format_id] [language]")
                    continue
                url = cmd[1]
                format_id = cmd[2] if len(cmd) > 2 else None
                language = cmd[3] if len(cmd) > 3 else None
                job_id = transcriber.add_job(url, format_id, language)
                print(f"Added job {job_id}")
                
            elif action == "list":
                jobs = transcriber.get_all_jobs()
                if not jobs:
                    print("No jobs")
                    continue
                print(f"{'Job ID':<15} {'Status':<12} {'URL'}")
                print("-" * 60)
                for job in jobs.values():
                    print(f"{job.job_id:<15} {job.status:<12} {job.url[:30]}...")
                    
            elif action == "process":
                print("Processing jobs...")
                transcriber.process_jobs()
                print("Processing completed")
                
            elif action == "copy":
                if len(cmd) < 2:
                    print("Usage: copy <job_id>")
                    continue
                job_id = cmd[1]
                if transcriber.copy_transcript_to_clipboard(job_id):
                    print("Transcript copied to clipboard")
                else:
                    print("Failed to copy transcript")
                    
            elif action == "save":
                if len(cmd) < 3:
                    print("Usage: save <job_id> <filename>")
                    continue
                job_id = cmd[1]
                filename = cmd[2]
                if transcriber.save_transcript(job_id, filename):
                    print(f"Transcript saved to {filename}")
                else:
                    print("Failed to save transcript")
                    
            elif action == "formats":
                if len(cmd) < 2:
                    print("Usage: formats <url>")
                    continue
                url = cmd[1]
                formats = transcriber.get_available_formats(url)
                if formats:
                    print(f"{'ID':<10} {'EXT':<5} {'ABR':<6} {'SIZE':<10} {'NOTE'}")
                    print("-" * 50)
                    for fmt in formats:
                        size = fmt.get('filesize')
                        size_str = f"{size//1024//1024:.1f}MB" if size else "N/A"
                        print(f"{fmt['format_id']:<10} {fmt['ext']:<5} {fmt.get('abr', 'N/A'):<6} {size_str:<10} {fmt['format_note']}")
                else:
                    print("No audio formats found")
                    
            else:
                print("Unknown command. Available: add, list, process, copy, save, formats, quit")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
    
    print("Goodbye!")


if __name__ == "__main__":
    main()