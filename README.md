# auto-trans

>Transform video URLs into clean, readable transcripts **with one command**.

auto-trans is an AI-powered command-line tool that automatically downloads audio, transcribes it using Whisper, and copies the text (with source URL) to your clipboard — ready for pasting, organizing, or prompting your favorite LLM.

🚀 Just imagine: with a single command, you can extract accurate transcripts from most online video platforms — YouTube, Bilibili, Twitter, TikTok, and more — instantly, and start using them for notes, summaries, idea generation, or research.

🧠 From there, plug your transcripts into ChatGPT, Claude, or any LLM to summarize, translate, annotate, or brainstorm. Build your own automated information capture and organization workflow, turbocharged by AI.

Whether you're a content creator, student, researcher, or curious mind, auto-trans empowers you to go from video ➡️ insight in seconds.

## ✨ Key Features

- 🚀 **One-command operation**: `auto-trans <url>` - that's it!
- 🌐 **Universal platform support**: YouTube, Bilibili, Twitter, TikTok, and 1000+ sites via yt-dlp
- 🧠 **AI-powered transcription**: OpenAI Whisper with multilingual support
- ⚡ **Parallel processing**: Download and transcribe multiple videos simultaneously
- 📋 **Smart clipboard integration**: Auto-copy transcripts with source URL for easy reference
- 🧹 **Auto cleanup**: Temporary files deleted automatically to save disk space
- 🎯 **Format optimization**: Automatically selects best audio quality or use custom formats
- 🌍 **Language detection**: Supports Chinese, English, and 90+ languages
- 📊 **Progress tracking**: Real-time status updates and detailed logging
- 🔧 **Highly configurable**: Customize workers, models, formats, and more

## 🎯 Core Benefits

| Traditional Workflow | auto-trans Workflow |
|---------------------|-------------------|
| 1. Find video URL | 1. Copy video URL |
| 2. Check available formats | 2. Run `auto-trans <url>` |
| 3. Download audio manually | 3. ✅ Done! Text in clipboard |
| 4. Convert audio format | |
| 5. Run transcription tool | |
| 6. Clean up files | |
| 7. Copy/paste results | |

**Time saved: 5-10 minutes per video → 30 seconds**

## 🔧 Installation

### Prerequisites

- **Linux/WSL** (Ubuntu/Debian recommended)
- **Python 3.8+**
- **FFmpeg** for audio processing

### Step 1: Install System Dependencies

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install python3 python3-pip python3-venv ffmpeg git

# CentOS/RHEL
sudo yum install python3 python3-pip ffmpeg git

# Arch Linux
sudo pacman -S python python-pip ffmpeg git
```

### Step 2: Clone and Setup

```bash
# Clone the repository
git clone https://github.com/Polumm/auto-trans.git
cd auto-trans

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### Step 3: Install System-wide Command

```bash
# Make the wrapper script executable and install it
sudo cp auto-trans /usr/local/bin/
sudo chmod +x /usr/local/bin/auto-trans

# Update the script paths (replace with your actual paths)
sudo nano /usr/local/bin/auto-trans
# Edit SCRIPT_DIR and VENV_PATH to match your installation
```

### Step 4: Configure Defaults

Edit `/usr/local/bin/auto-trans` to set your preferred defaults:

```bash
DEFAULT_WORKERS=4           # Number of parallel jobs
DEFAULT_MODEL="base"        # Whisper model (tiny/base/small/medium/large)
DEFAULT_LANGUAGE="zh"       # Default language (zh/en/auto)
DEFAULT_FORMAT=""           # Audio format (leave empty for auto)
```

### Step 5: Verify Installation

```bash
auto-trans --help
```

If you see the help message, you're ready to go! 🎉

## 🚀 Quick Start

### Basic Usage

```bash
# Transcribe any video with one command
auto-trans https://www.youtube.com/watch?v=dQw4w9WgXcQ
auto-trans https://www.bilibili.com/video/BV1ZMNQziEJn
auto-trans https://twitter.com/user/status/123456789
```

**What happens:**
1. 📥 Downloads best quality audio
2. 🧠 Transcribes with AI (Whisper)
3. 📋 Copies transcript + URL to clipboard
4. 🧹 Cleans up temporary files
5. ✅ Ready to paste anywhere!

### Language-Specific Transcription

```bash
# Chinese content
auto-trans https://www.bilibili.com/video/BV1ZMNQziEJn -l zh

# English content
auto-trans https://www.youtube.com/watch?v=dQw4w9WgXcQ -l en

# Auto-detect language
auto-trans https://example.com/video -l auto
```

### Batch Processing

```bash
# Process multiple videos simultaneously
auto-trans \
  https://www.youtube.com/watch?v=video1 \
  https://www.youtube.com/watch?v=video2 \
  https://www.bilibili.com/video/BV1234567890
```

## 📖 Advanced Usage

### Check Available Formats

```bash
# List all available audio/video formats
auto-trans --list-formats https://www.bilibili.com/video/BV1ZMNQziEJn
```

Output:
```
Available formats for https://www.bilibili.com/video/BV1ZMNQziEJn:
ID         EXT   ABR    SIZE       NOTE
30216      m4a   42k    7.96MB     audio only
30232      m4a   89k    16.68MB    audio only
30032      mp4   282k   52.99MB    video + audio
```

### Use Specific Audio Format

```bash
# Use high-quality audio format
auto-trans https://www.bilibili.com/video/BV1ZMNQziEJn -f 30232

# Use format ID from --list-formats output
auto-trans https://www.youtube.com/watch?v=dQw4w9WgXcQ -f 140
```

### Performance Tuning

```bash
# Use more CPU cores for faster processing
auto-trans https://example.com/video -w 8

# Use different Whisper models
auto-trans https://example.com/video -m tiny    # Fastest, least accurate
auto-trans https://example.com/video -m base    # Good balance (default)
auto-trans https://example.com/video -m large   # Most accurate, slowest

# Combine options
auto-trans https://example.com/video -w 8 -m large -l zh -f 30232
```

### Save Transcripts to Files

```bash
# Save to file instead of just clipboard
auto-trans https://example.com/video -o transcript

# This creates: transcript_job_123456789_0.txt
```

### Interactive Mode

```bash
# Launch interactive mode for batch operations
auto-trans -i
```

Interactive commands:
```
> add https://www.bilibili.com/video/BV1ZMNQziEJn 30232 zh
> add https://www.youtube.com/watch?v=dQw4w9WgXcQ
> list                    # Show all jobs
> process                 # Start transcription
> copy job_123456789_0    # Copy specific transcript
> save job_123456789_0 output.txt
> quit
```

## 🔧 Configuration Options

### Whisper Models

| Model | Speed | Accuracy | Memory | Best For |
|-------|-------|----------|--------|----------|
| `tiny` | ⚡⚡⚡⚡⚡ | ⭐⭐ | 39MB | Quick drafts, real-time |
| `base` | ⚡⚡⚡⚡ | ⭐⭐⭐ | 74MB | General use (default) |
| `small` | ⚡⚡⚡ | ⭐⭐⭐⭐ | 244MB | Good quality |
| `medium` | ⚡⚡ | ⭐⭐⭐⭐⭐ | 769MB | High quality |
| `large` | ⚡ | ⭐⭐⭐⭐⭐ | 1550MB | Best quality |

### Language Codes

| Language | Code | Example |
|----------|------|---------|
| Auto-detect | `auto` | `auto-trans <url> -l auto` |
| Chinese | `zh` | `auto-trans <url> -l zh` |
| English | `en` | `auto-trans <url> -l en` |
| Japanese | `ja` | `auto-trans <url> -l ja` |
| Korean | `ko` | `auto-trans <url> -l ko` |
| Spanish | `es` | `auto-trans <url> -l es` |
| French | `fr` | `auto-trans <url> -l fr` |
| German | `de` | `auto-trans <url> -l de` |

[See full list of supported languages](https://github.com/openai/whisper#available-models-and-languages)

### Worker Configuration

```bash
# Adjust based on your system
auto-trans <url> -w 2   # Low-end systems
auto-trans <url> -w 4   # Default (quad-core)
auto-trans <url> -w 8   # High-end systems
auto-trans <url> -w 16  # Server environments
```

## 📁 Project Structure

```
auto-trans/
├── transcribe.py          # Main Python script
├── auto-trans            # System wrapper script
├── requirements.txt      # Python dependencies
├── README.md            # This file
├── LICENSE
└── .gitignore
```

## 🔍 Supported Platforms

Thanks to yt-dlp, auto-trans supports **1000+ platforms** including:

### Popular Video Platforms
- **YouTube** - All video types, playlists, live streams
- **Bilibili** - Chinese video platform
- **Twitter/X** - Video tweets
- **TikTok** - Short videos
- **Instagram** - Video posts, stories, reels
- **Facebook** - Video posts, live streams
- **Twitch** - VODs, clips
- **Vimeo** - Professional videos

### Educational & Professional
- **Coursera** - Course videos
- **edX** - Educational content
- **Khan Academy** - Learning videos
- **LinkedIn Learning** - Professional courses
- **Udemy** - Course materials

### International Platforms
- **Youku** (China)
- **Niconico** (Japan)
- **VK** (Russia)
- **Dailymotion** (France)
- **And many more...**

[Full list of supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)

## 🚨 Troubleshooting

### Common Issues

#### 1. Command Not Found
```bash
which auto-trans
# If empty, reinstall:
sudo cp auto-trans /usr/local/bin/
sudo chmod +x /usr/local/bin/auto-trans
```

#### 2. Python Module Errors
```bash
# Reinstall dependencies
cd /path/to/auto-trans
source .venv/bin/activate
pip install -r requirements.txt
```

#### 3. FFmpeg Not Found
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# Check installation
ffmpeg -version
```

#### 4. Whisper Model Download Issues
```bash
# First run downloads models (may take time)
# Check internet connection and disk space
df -h  # Check disk space
```

#### 5. Video Platform Errors
```bash
# Update yt-dlp to latest version
pip install --upgrade yt-dlp

# Some platforms may require specific extractors
```

#### 6. Memory Issues
```bash
# Use smaller Whisper model
auto-trans <url> -m tiny

# Reduce worker count
auto-trans <url> -w 2
```

### Performance Tips

1. **SSD Storage**: Store temp files on SSD for faster processing
2. **RAM**: 8GB+ recommended for `large` model
3. **CPU**: More cores = faster parallel processing
4. **Network**: Stable connection for reliable downloads

### Logs and Debugging

```bash
# Check logs for detailed error information
tail -f ~/auto-trans/transcription.log

# Enable verbose output
auto-trans <url> --verbose
```

## 🤝 Contributing

We welcome contributions! Here's how you can help:

### 🐛 Bug Reports
- Use GitHub Issues
- Include system info, error logs, and reproduction steps

### 💡 Feature Requests
- Suggest new platforms, languages, or features
- Provide use cases and examples

### 🔧 Development
```bash
# Fork the repository
git clone https://github.com/Polumm/auto-trans.git
cd auto-trans

# Create feature branch
git checkout -b feature/your-feature-name

# Make changes and test
python transcribe.py --help

# Submit pull request
```

### 📚 Documentation
- Improve README.md
- Add usage examples
- Translate to other languages


## 🙏 Acknowledgments

- **[OpenAI Whisper](https://github.com/openai/whisper)** - State-of-the-art speech recognition
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** - Universal video downloader
- **[pyperclip](https://github.com/asweigart/pyperclip)** - Cross-platform clipboard functionality

## 📞 Support

- 📖 **Documentation**: Check this README and examples/
- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/Polumm/auto-trans/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/Polumm/auto-trans/discussions)

---

## ⭐ Star History

If auto-trans saves you time, please consider giving it a star! ⭐

<a href="https://github.com/Polumm/auto-trans/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=Polumm/auto-trans" />
</a>

[![Star History Chart](https://api.star-history.com/svg?repos=Polumm/auto-trans&type=Date)](https://www.star-history.com/#Polumm/auto-trans&Date)

---

**Made with ❤️ for content creators, researchers, and productivity enthusiasts worldwide.**