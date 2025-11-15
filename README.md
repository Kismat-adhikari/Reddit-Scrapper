# Reddit OSINT Scraper

A powerful Python-based Reddit scraper for OSINT (Open Source Intelligence) that collects detailed user profiles based on keyword searches. Scrapes user data including karma, contributions, account age, bio, social links, and emails.

## Features

✅ **Automated Subreddit Discovery** - Finds relevant subreddits for any keyword  
✅ **User Profile Scraping** - Extracts comprehensive user data  
✅ **Proxy Support** - Rotate proxies with authentication to avoid bans  
✅ **Cookie Authentication** - Handle age-gated/mature content  
✅ **Real-time CSV Export** - Data saved incrementally as it scrapes  
✅ **Headful Browser** - Monitor scraping progress visually  
✅ **Smart Throttling** - Automatic delays to prevent rate limiting  
✅ **Clean Data Extraction** - Filters out junk and validates social links  

## Installation

1. **Clone the repository**
```bash
git clone https://github.com/Kismat-adhikari/Reddit-Scrapper.git
cd Reddit-Scrapper
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
playwright install chromium
```

3. **Set up required files** (see Configuration below)

## Configuration

### Required Files

#### 1. `cookies.txt` (Required for age-gated content)
Export your Reddit cookies in Netscape format to access mature/restricted subreddits.

**How to get cookies:**
- Use browser extension like "Get cookies.txt LOCALLY" (Chrome/Firefox)
- Login to Reddit in your browser
- Export cookies and save as `cookies.txt` in the project root

**Format:**
```
# Netscape HTTP Cookie File
.reddit.com	TRUE	/	TRUE	1234567890	cookie_name	cookie_value
```

#### 2. `proxies.txt` (Optional but recommended)
Add proxies to avoid IP bans and rate limiting.

**Format:** One proxy per line as `IP:PORT:USERNAME:PASSWORD`
```
123.45.67.89:8080:user1:pass1
98.76.54.32:3128:user2:pass2
```

**Where to get proxies:**
- Paid proxy services (recommended): Bright Data, Smartproxy, Oxylabs
- Free proxies (less reliable): Free-Proxy-List, ProxyScrape

> **Note:** Both files are gitignored for security. Never commit credentials to GitHub!

## Usage

Run the scraper:
```bash
python reddit_scraper.py
```

Enter a keyword when prompted:
```
🔑 Enter keyword to search: Python
```

The scraper will:
1. Find 5 relevant subreddits
2. Collect 5 active users from each subreddit
3. Scrape detailed profile data for each user
4. Save results to `output/TIMESTAMP_KEYWORD.csv`

## Output

CSV file with the following columns:

| Column | Description |
|--------|-------------|
| `reddit_username` | Reddit username |
| `reddit_profile_url` | Full profile URL |
| `total_karma` | Total karma (post + comment) |
| `contributions` | Number of posts/comments |
| `reddit_age` | Account age (e.g., "4 years", "6 months") |
| `bio_text` | User bio/about section |
| `social_links` | External social media links (Twitter, Instagram, etc.) |
| `email` | Email address if publicly available |

**Output location:** `output/YYYYMMDD_HHMMSS_KEYWORD.csv`

## Customization

Edit these values in `reddit_scraper.py`:

```python
# Line 66: Max subreddits to search
max_subreddits=5

# Line 123: Max users per subreddit  
max_users=5

# Line 430: Throttle delay (seconds)
await asyncio.sleep(random.uniform(1, 2))
```

## Limitations

- Scrapes public data only
- Respects Reddit's rate limits with throttling
- Some profiles may be private or suspended
- Social links only captured if listed in profile

## Legal & Ethics

⚠️ **Important:** This tool is for educational and research purposes only.

- Only scrapes publicly available data
- Respect Reddit's Terms of Service
- Use responsibly and ethically
- Don't use for spam, harassment, or malicious purposes
- Consider rate limits and server load

## Troubleshooting

**"No subreddits found"**
- Check your internet connection
- Verify cookies.txt is valid
- Try a different keyword

**"Timeout errors"**
- Add proxies to `proxies.txt`
- Increase timeout values in code
- Check if Reddit is accessible

**"All data shows N/A"**
- Update cookies.txt (may be expired)
- Check if profile pages load in browser
- Verify selectors haven't changed (Reddit updates)

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License - See LICENSE file for details

## Disclaimer

This tool is provided as-is. The author is not responsible for misuse or any violations of Reddit's Terms of Service. Use at your own risk.
