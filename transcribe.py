#!/usr/bin/env python3
"""
Audio Transcription Tool
Automated audio downloading and transcription using yt-dlp and Whisper
Supports multiprocessing, auto cleanup, clipboard functionality, and local file processing
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
    source: str  # URL or file path
    job_id: str
    is_local_file: bool = False
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
    
    def _is_url(self, source: str) -> bool:
        """Check if source is a URL"""
        return source.startswith(('http://', 'https://'))
    
    def _is_local_file(self, source: str) -> bool:
        """Check if source is a local file"""
        return os.path.isfile(source)
    
    def _is_supported_audio_video_file(self, file_path: str) -> bool:
        """Check if file has a supported audio/video extension"""
        supported_extensions = {
            '.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.wma',
            '.mp4', '.mkv', '.avi', '.mov', '.webm', '.3gp', '.flv'
        }
        return Path(file_path).suffix.lower() in supported_extensions
            
    def get_available_formats(self, url: str) -> List[Dict]:
        """Get available audio formats for a URL"""
        if not self._is_url(url):
            return []
            
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
    
    def _extract_audio_from_video(self, video_path: str, output_path: str) -> bool:
        """Extract audio from video file using ffmpeg"""
        try:
            # Check if ffmpeg is available
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.error("ffmpeg is required for video processing but not found")
            return False
        
        try:
            # Extract audio using ffmpeg
            cmd = [
                'ffmpeg', '-i', video_path,
                '-vn',  # No video
                '-acodec', 'libmp3lame',  # MP3 codec
                '-ab', '192k',  # Audio bitrate
                '-ar', '44100',  # Sample rate
                '-y',  # Overwrite output file
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.info(f"Audio extracted to: {output_path}")
                return True
            else:
                self.logger.error(f"ffmpeg error: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error extracting audio: {e}")
            return False
    
    def _prepare_local_file(self, job: TranscriptionJob) -> bool:
        """Prepare local file for transcription"""
        try:
            source_path = job.source
            
            # Check if file exists
            if not os.path.exists(source_path):
                raise FileNotFoundError(f"File not found: {source_path}")
            
            # Get file extension
            file_ext = Path(source_path).suffix.lower()
            
            # Audio files can be used directly
            audio_extensions = {'.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.wma'}
            if file_ext in audio_extensions:
                job.audio_file = source_path
                self.logger.info(f"Using audio file directly: {source_path}")
                return True
            
            # Video files need audio extraction
            video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.3gp', '.flv'}
            if file_ext in video_extensions:
                # Create temporary audio file
                safe_id = "".join(c for c in job.job_id if c.isalnum() or c in ('-', '_'))
                audio_file = os.path.join(self.temp_dir, f"extracted_audio_{safe_id}.mp3")
                
                if self._extract_audio_from_video(source_path, audio_file):
                    job.audio_file = audio_file
                    return True
                else:
                    # Fallback: try to use video file directly with Whisper
                    self.logger.warning("Audio extraction failed, trying to use video file directly")
                    job.audio_file = source_path
                    return True
            
            # Unsupported file type, but let's try anyway
            self.logger.warning(f"Unsupported file type {file_ext}, attempting transcription anyway")
            job.audio_file = source_path
            return True
            
        except Exception as e:
            job.error = f"File preparation error: {str(e)}"
            job.status = "failed"
            self.logger.error(f"File preparation failed for job {job.job_id}: {e}")
            return False
    
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
                ydl.download([job.source])
                
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
                # Log detected language info if available
                if hasattr(info, 'language'):
                    self.logger.info(f"Detected language: {info.language} (confidence: {getattr(info, 'language_probability', 'N/A')})")
            else:
                result = self.model.transcribe(job.audio_file, **transcribe_options)
                job.transcript = result['text'].strip()
                # Log detected language if available
                if 'language' in result:
                    self.logger.info(f"Detected language: {result['language']}")
                    
            job.status = "completed"
            
            self.logger.info(f"Transcription completed for job {job.job_id}")
            return True
            
        except Exception as e:
            job.error = f"Transcription error: {str(e)}"
            job.status = "failed"
            self.logger.error(f"Transcription failed for job {job.job_id}: {e}")
            return False
    
    def _cleanup_audio_file(self, job: TranscriptionJob):
        """Clean up downloaded/extracted audio file"""
        if self.auto_cleanup and job.audio_file:
            # Only delete if it's not the original local file
            if job.is_local_file and job.audio_file == job.source:
                # Don't delete the original local file
                return
            
            if os.path.exists(job.audio_file):
                try:
                    os.remove(job.audio_file)
                    self.logger.info(f"Cleaned up audio file: {job.audio_file}")
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup {job.audio_file}: {e}")
    
    def _process_job(self, job: TranscriptionJob):
        """Process a single transcription job"""
        try:
            # Handle local files vs URLs
            if job.is_local_file:
                # Prepare local file
                if not self._prepare_local_file(job):
                    return
            else:
                # Download audio from URL
                if not self._download_audio(job):
                    return
                
            # Transcribe audio
            if not self._transcribe_audio(job):
                return
                
        finally:
            # Cleanup
            self._cleanup_audio_file(job)
    
    def add_job(self, source: str, audio_format: Optional[str] = None, 
                language: Optional[str] = None) -> str:
        """Add a new transcription job"""
        job_id = f"job_{int(time.time() * 1000)}_{len(self.jobs)}"
        
        # Determine if source is a local file or URL
        is_local_file = self._is_local_file(source)
        
        # Validate input
        if not is_local_file and not self._is_url(source):
            raise ValueError(f"Source must be either a valid URL or existing file: {source}")
        
        job = TranscriptionJob(
            source=source,
            job_id=job_id,
            is_local_file=is_local_file,
            audio_format=audio_format if not is_local_file else None,  # Format only applies to URLs
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
        """Copy transcript to clipboard with source prefix"""
        job = self.jobs.get(job_id)
        if job and job.transcript:
            try:
                # Include source at the beginning for easy reference
                source_label = "File" if job.is_local_file else "URL"
                clipboard_content = f"Source ({source_label}): {job.source}\n\n{job.transcript}"
                pyperclip.copy(clipboard_content)
                self.logger.info(f"Transcript with source copied to clipboard for job {job_id}")
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
                    source_label = "File" if job.is_local_file else "URL"
                    f.write(f"Source ({source_label}): {job.source}\n")
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
    parser = argparse.ArgumentParser(description="Audio Transcription Tool - Supports URLs and local files")
    parser.add_argument("sources", nargs="*", help="URLs or file paths to process")
    parser.add_argument("--workers", "-w", type=int, default=4, help="Number of worker threads")
    parser.add_argument("--model", "-m", default="base", help="Whisper model to use")
    parser.add_argument("--language", "-l", help="Language code (e.g., 'en', 'zh')")
    parser.add_argument("--format", "-f", help="Audio format ID to download (URLs only)")
    parser.add_argument("--no-cleanup", action="store_true", help="Don't delete temporary audio files after transcription")
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
    
    if not args.sources:
        parser.print_help()
        return
    
    # List formats mode (only for URLs)
    if args.list_formats:
        for source in args.sources:
            if transcriber._is_url(source):
                print(f"\nAvailable formats for {source}:")
                formats = transcriber.get_available_formats(source)
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
                print(f"\n{source}: Local file - format listing not applicable")
        return
    
    # Add jobs
    job_ids = []
    for source in args.sources:
        try:
            job_id = transcriber.add_job(source, args.format, args.language)
            job_ids.append(job_id)
            source_type = "file" if transcriber._is_local_file(source) else "URL"
            print(f"Added job {job_id} for {source_type}: {source}")
        except ValueError as e:
            print(f"Error: {e}")
            continue
    
    if not job_ids:
        print("No valid sources to process")
        return
    
    # Process jobs
    print(f"\nProcessing {len(job_ids)} jobs...")
    results = transcriber.process_jobs()
    
    # Display results
    print("\n" + "="*60)
    print("TRANSCRIPTION RESULTS")
    print("="*60)
    
    for job_id in job_ids:
        job = results[job_id]
        source_type = "File" if job.is_local_file else "URL"
        print(f"\nJob ID: {job_id}")
        print(f"Source ({source_type}): {job.source}")
        print(f"Status: {job.status}")
        
        if job.status == "completed":
            print(f"Transcript:\n{job.transcript}")
            
            # Automatically copy to clipboard for single source processing
            if len(job_ids) == 1:
                if transcriber.copy_transcript_to_clipboard(job_id):
                    print("✓ Transcript (with source) copied to clipboard")
            else:
                # For multiple sources, still copy but mention it's automatic
                if transcriber.copy_transcript_to_clipboard(job_id):
                    print("✓ Transcript (with source) copied to clipboard")
            
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
    print("Supports both URLs and local files")
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
                    print("Usage: add <url|file_path> [format_id] [language]")
                    continue
                source = cmd[1]
                format_id = cmd[2] if len(cmd) > 2 else None
                language = cmd[3] if len(cmd) > 3 else None
                try:
                    job_id = transcriber.add_job(source, format_id, language)
                    source_type = "file" if transcriber._is_local_file(source) else "URL"
                    print(f"Added job {job_id} for {source_type}: {source}")
                except ValueError as e:
                    print(f"Error: {e}")
                
            elif action == "list":
                jobs = transcriber.get_all_jobs()
                if not jobs:
                    print("No jobs")
                    continue
                print(f"{'Job ID':<15} {'Type':<5} {'Status':<12} {'Source'}")
                print("-" * 70)
                for job in jobs.values():
                    source_type = "File" if job.is_local_file else "URL"
                    source_display = job.source[:40] + "..." if len(job.source) > 40 else job.source
                    print(f"{job.job_id:<15} {source_type:<5} {job.status:<12} {source_display}")
                    
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
                source = cmd[1]
                if transcriber._is_url(source):
                    formats = transcriber.get_available_formats(source)
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
                    print("Format listing is only available for URLs, not local files")
                    
            else:
                print("Unknown command. Available: add, list, process, copy, save, formats, quit")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
    
    print("Goodbye!")


if __name__ == "__main__":
    main()