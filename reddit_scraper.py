import asyncio
import csv
import re
from playwright.async_api import async_playwright
from urllib.parse import urlparse
import random
from datetime import datetime
import signal
import sys

class RedditScraper:
    def __init__(self, cookies_file='cookies.txt', proxies_file='proxies.txt'):
        self.cookies_file = cookies_file
        self.proxies_file = proxies_file
        self.proxies = []
        self.users_data = []
        self.csv_filename = None
        self.browser = None
        self.total_scraped = 0
        self.max_total_users = 100  # Default max users
        
    def load_proxies(self):
        """Load proxies from proxies.txt in IP:PORT:USERNAME:PASSWORD format"""
        try:
            with open(self.proxies_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        parts = line.split(':')
                        if len(parts) == 4:
                            proxy = {
                                'server': f'http://{parts[0]}:{parts[1]}',
                                'username': parts[2],
                                'password': parts[3]
                            }
                            self.proxies.append(proxy)
            print(f"✓ Loaded {len(self.proxies)} proxies")
        except FileNotFoundError:
            print("⚠ No proxies.txt found, continuing without proxies")
    
    def load_cookies(self, context):
        """Load cookies from Netscape format cookies.txt"""
        try:
            cookies = []
            with open(self.cookies_file, 'r') as f:
                for line in f:
                    if line.startswith('#') or not line.strip():
                        continue
                    parts = line.strip().split('\t')
                    if len(parts) >= 7:
                        cookies.append({
                            'name': parts[5],
                            'value': parts[6],
                            'domain': parts[0],
                            'path': parts[2],
                            'secure': parts[3] == 'TRUE',
                            'httpOnly': False
                        })
            if cookies:
                asyncio.create_task(context.add_cookies(cookies))
                print(f"✓ Loaded {len(cookies)} cookies")
        except FileNotFoundError:
            print("⚠ No cookies.txt found, continuing without cookies")
    
    async def find_subreddits(self, page, keyword, max_subreddits=5):
        """Find relevant subreddits for the keyword"""
        print(f"\n🔍 Searching for subreddits related to '{keyword}'...")
        subreddits = []
        
        search_url = f'https://www.reddit.com/search/?q={keyword}&type=sr'
        try:
            await page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(3)
        except Exception as e:
            print(f"  ✗ Error loading search page: {str(e)[:50]}")
            return []
        
        # Handle mature content warning
        try:
            continue_btn = page.locator('button:has-text("Continue")')
            if await continue_btn.count() > 0:
                await continue_btn.first.click()
                await asyncio.sleep(2)
        except:
            pass
        
        # Scroll to load more results
        for _ in range(3):
            await page.evaluate('window.scrollBy(0, 1000)')
            await asyncio.sleep(1)
        
        # Extract subreddit links
        links = await page.locator('a[href*="/r/"]').all()
        seen = set()
        
        for link in links:
            try:
                href = await link.get_attribute('href')
                if href and '/r/' in href:
                    match = re.search(r'/r/([^/\?]+)', href)
                    if match:
                        subreddit = match.group(1)
                        # Filter out irrelevant subreddits
                        if subreddit.lower() not in seen and len(subreddit) > 2:
                            # Check if keyword is somewhat related
                            if keyword.lower() in subreddit.lower() or len(subreddits) < max_subreddits:
                                subreddits.append(subreddit)
                                seen.add(subreddit.lower())
                                print(f"  ✓ Found: r/{subreddit}")
                                if len(subreddits) >= max_subreddits:
                                    break
            except:
                continue
        
        if not subreddits:
            print(f"  ⚠️  No subreddits found, trying direct subreddit...")
            # Fallback: try the keyword as a direct subreddit
            subreddits = [keyword]
        
        return subreddits[:max_subreddits]

    async def get_active_users(self, page, subreddit, max_users=5):
        """Collect active users from a subreddit"""
        print(f"\n👥 Collecting users from r/{subreddit}...")
        users = set()
        
        subreddit_url = f'https://www.reddit.com/r/{subreddit}/hot/'
        try:
            await page.goto(subreddit_url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(3)
            
            # Handle mature content warning
            try:
                continue_btn = page.locator('button:has-text("Continue")')
                if await continue_btn.count() > 0:
                    await continue_btn.first.click()
                    await asyncio.sleep(2)
            except:
                pass
            
            # Scroll to load more posts
            for _ in range(5):
                await page.evaluate('window.scrollBy(0, 1500)')
                await asyncio.sleep(1.5)
            
            # Extract usernames from posts and comments
            user_links = await page.locator('a[href*="/user/"], a[href*="/u/"]').all()
            
            for link in user_links:
                try:
                    href = await link.get_attribute('href')
                    if href:
                        match = re.search(r'/u(?:ser)?/([^/\?]+)', href)
                        if match:
                            username = match.group(1)
                            if username not in ['[deleted]', 'AutoModerator']:
                                users.add(username)
                                if len(users) >= max_users:
                                    break
                except:
                    continue
            
            user_list = list(users)[:max_users]
            print(f"  ✓ Found {len(user_list)} active users")
            
            if not user_list:
                print(f"  ⚠️  No users found in r/{subreddit}")
            
            return user_list
        except Exception as e:
            print(f"  ✗ Error accessing r/{subreddit}: {str(e)[:100]}")
            return []
    
    async def scrape_user_profile(self, page, username):
        """Scrape detailed user profile information"""
        print(f"  📊 u/{username}...", end=' ', flush=True)
        
        profile_url = f'https://www.reddit.com/user/{username}/'
        user_data = {
            'reddit_username': username,
            'reddit_profile_url': profile_url,
            'total_karma': 'N/A',
            'contributions': 'N/A',
            'reddit_age': 'N/A',
            'bio_text': '',
            'social_links': '',
            'email': ''
        }
        
        try:
            await page.goto(profile_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(3)
            
            # Check if suspended
            page_html = await page.content()
            if 'suspended' in page_html.lower() and 'has been suspended' in page_html.lower():
                print("⚠️ Suspended")
                return user_data
            
            # Get all text from page for easier extraction
            page_text = await page.inner_text('body')
            
            # Debug: print first 500 chars to see what we're getting
            # print(f"\n[DEBUG] Page text sample: {page_text[:500]}\n")
            
            # Extract karma - look for the main karma number only (not post/comment breakdown)
            # First try to find the total karma (usually shown as "X Karma" at top of profile)
            karma_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*Karma', page_text, re.IGNORECASE)
            if karma_match:
                user_data['total_karma'] = karma_match.group(1).replace(',', '')
            else:
                # Fallback: try to find post + comment karma separately and sum them
                post_karma = re.search(r'Post Karma\s*(\d{1,3}(?:,\d{3})*)', page_text, re.IGNORECASE)
                comment_karma = re.search(r'Comment Karma\s*(\d{1,3}(?:,\d{3})*)', page_text, re.IGNORECASE)
                
                if post_karma and comment_karma:
                    total = int(post_karma.group(1).replace(',', '')) + int(comment_karma.group(1).replace(',', ''))
                    user_data['total_karma'] = str(total)
                elif post_karma:
                    user_data['total_karma'] = post_karma.group(1).replace(',', '')
                elif comment_karma:
                    user_data['total_karma'] = comment_karma.group(1).replace(',', '')
            
            # Extract contributions
            contrib_patterns = [
                r'(\d{1,3}(?:,\d{3})*)\s*Contribution',
                r'Contribution[s]?\s*(\d{1,3}(?:,\d{3})*)'
            ]
            
            for pattern in contrib_patterns:
                contrib_match = re.search(pattern, page_text, re.IGNORECASE)
                if contrib_match:
                    user_data['contributions'] = contrib_match.group(1).replace(',', '')
                    break
            
            # Extract reddit age - Reddit shows it as "6 y" or "3 mo" or "15 d"
            # Look for age pattern near "Reddit Age" text for accuracy
            age_section = re.search(r'Reddit\s*Age[:\s]*(.*?)(?:Social|Trophies|Moderator|$)', page_text, re.IGNORECASE | re.DOTALL)
            
            if age_section:
                age_text = age_section.group(1)[:50]  # Limit to 50 chars after "Reddit Age"
                
                # Try years
                year_match = re.search(r'(\d+)\s*y\b', age_text, re.IGNORECASE)
                if year_match:
                    years = year_match.group(1)
                    if 1 <= int(years) <= 20:
                        user_data['reddit_age'] = f"{years} years"
                
                # Try months
                if user_data['reddit_age'] == 'N/A':
                    month_match = re.search(r'(\d+)\s*mo\b', age_text, re.IGNORECASE)
                    if month_match:
                        months = month_match.group(1)
                        if 1 <= int(months) <= 24:
                            user_data['reddit_age'] = f"{months} months"
                
                # Try days
                if user_data['reddit_age'] == 'N/A':
                    day_match = re.search(r'(\d+)\s*d\b', age_text, re.IGNORECASE)
                    if day_match:
                        days = day_match.group(1)
                        if 1 <= int(days) <= 365:
                            user_data['reddit_age'] = f"{days} days"
            
            # Fallback: Full date format
            if user_data['reddit_age'] == 'N/A':
                cake_match = re.search(r'((?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})', page_text, re.IGNORECASE)
                if cake_match:
                    user_data['reddit_age'] = cake_match.group(1).strip()
            
            # Extract bio text - use DOM selector for accuracy
            try:
                # Try to find bio using specific selectors
                bio_selectors = [
                    'div[id*="profile"] p',
                    'div[class*="about"] p',
                    'shreddit-user-profile-header p',
                    '[slot="profile-bio"]'
                ]
                
                bio = ''
                for selector in bio_selectors:
                    try:
                        bio_elem = await page.locator(selector).first
                        if await bio_elem.count() > 0:
                            bio = await bio_elem.inner_text(timeout=2000)
                            if bio:
                                break
                    except:
                        continue
                
                # Clean bio
                if bio:
                    bio = bio.strip()
                    bio = re.sub(r'\s+', ' ', bio)
                    
                    # Remove UI elements
                    ui_junk = ['Follow', 'Start Chat', 'them.', 'Digdeepresearch', 'Reddit', 'Advertise', 
                              'Developer', 'Platform', 'Privacy', 'Policy', 'User Agreement', 'reserved']
                    
                    for junk in ui_junk:
                        bio = bio.replace(junk, '')
                    
                    bio = bio.strip()
                    
                    # Valid bio check
                    if 10 < len(bio) < 500:
                        user_data['bio_text'] = bio[:300]
                    else:
                        user_data['bio_text'] = 'Empty'
                else:
                    user_data['bio_text'] = 'Empty'
            except:
                user_data['bio_text'] = 'Empty'
            
            # Extract social links - find text "Social Links" then get links after it
            social_links = []
            try:
                # Method 1: Find "Social Links" text and extract URLs after it
                social_section_match = re.search(r'Social\s*Links\s*(.*?)(?:Trophies|Moderator|$)', page_text, re.IGNORECASE | re.DOTALL)
                if social_section_match:
                    social_text = social_section_match.group(1)
                    # Extract URLs from this section
                    url_pattern = r'https?://(?:www\.)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?'
                    found_urls = re.findall(url_pattern, social_text)
                    
                    for url_match in found_urls:
                        # Reconstruct full URL
                        url = 'https://' + url_match[0] + url_match[1]
                        if self.is_social_link(url):
                            social_links.append(url)
                
                # Method 2: Try DOM selectors
                if not social_links:
                    social_section_selectors = [
                        'div[class*="social"] a[href^="http"]',
                        'div[id*="social"] a[href^="http"]',
                        'shreddit-user-profile-header a[href^="http"]'
                    ]
                    
                    for selector in social_section_selectors:
                        try:
                            links = await page.locator(selector).all()
                            for link in links[:10]:
                                try:
                                    href = await link.get_attribute('href')
                                    if href and self.is_social_link(href):
                                        social_links.append(href)
                                except:
                                    continue
                        except:
                            continue
                
                # Remove duplicates
                if social_links:
                    unique_links = list(set(social_links))[:5]
                    user_data['social_links'] = ' | '.join(unique_links)
                else:
                    user_data['social_links'] = 'None'
            except:
                user_data['social_links'] = 'None'
            
            # Extract email
            emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', page_text)
            if emails:
                user_data['email'] = emails[0]
            
            print("✅")
            return user_data
            
        except asyncio.TimeoutError:
            print("⏱️ Timeout")
            return user_data
        except Exception as e:
            error_msg = str(e)[:40]
            print(f"❌ {error_msg}")
            return user_data

    def is_social_link(self, url):
        """Check if URL is a valid social media link"""
        if not url or url.startswith('#'):
            return False
        
        # Filter out Reddit and invalid links
        invalid_patterns = ['reddit.com', 'redd.it', 'reddithelp.com', 'ogp.me', 'schema.org', 
                           'javascript:', 'mailto:', 'tel:', 'redditstatic.com', 'reddit.app.link']
        if any(pattern in url.lower() for pattern in invalid_patterns):
            return False
        
        # Known social media domains
        social_domains = [
            'twitter.com', 'x.com', 'instagram.com', 'tiktok.com',
            'youtube.com', 'youtu.be', 'github.com', 'linkedin.com',
            'facebook.com', 'fb.com', 'twitch.tv', 'discord.gg', 
            'patreon.com', 'ko-fi.com', 'onlyfans.com', 'snapchat.com',
            'telegram.me', 't.me', 'pinterest.com', 'tumblr.com'
        ]
        
        try:
            parsed = urlparse(url)
            # Must be http/https
            if parsed.scheme not in ['http', 'https']:
                return False
            
            # Check if it's a known social domain
            return any(domain in parsed.netloc.lower() for domain in social_domains)
        except:
            return False
    
    def create_csv_filename(self, keyword):
        """Create timestamped CSV filename in output folder"""
        import os
        
        # Create output folder if it doesn't exist
        if not os.path.exists('output'):
            os.makedirs('output')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_keyword = re.sub(r'[^\w\s-]', '', keyword).strip().replace(' ', '_')
        return f"output/{timestamp}_{safe_keyword}.csv"
    
    def save_user_to_csv(self, user_data):
        """Save single user to CSV incrementally"""
        import os
        file_exists = os.path.isfile(self.csv_filename)
        
        # Clean data before saving
        cleaned_data = {}
        for key, value in user_data.items():
            if isinstance(value, str):
                # Remove problematic characters and normalize whitespace
                value = value.replace('\n', ' ').replace('\r', ' ')
                value = re.sub(r'\s+', ' ', value).strip()
            cleaned_data[key] = value
        
        with open(self.csv_filename, 'a', newline='', encoding='utf-8-sig') as f:
            fieldnames = ['reddit_username', 'reddit_profile_url', 'total_karma', 
                         'contributions', 'reddit_age', 'bio_text', 'social_links', 'email']
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerow(cleaned_data)
    
    async def cleanup(self):
        """Cleanup browser on exit"""
        if self.browser:
            try:
                await self.browser.close()
            except:
                pass
        
        if self.total_scraped > 0:
            print(f"\n✅ Saved {self.total_scraped} users to {self.csv_filename}")
    
    async def run(self, keyword):
        """Main scraping workflow"""
        self.load_proxies()
        self.csv_filename = self.create_csv_filename(keyword)
        
        print(f"📄 Output file: {self.csv_filename}\n")
        
        try:
            async with async_playwright() as p:
                # Setup browser with proxy if available
                launch_options = {'headless': False}
                
                if self.proxies:
                    proxy = random.choice(self.proxies)
                    launch_options['proxy'] = proxy
                    print(f"🌐 Using proxy: {proxy['server']}")
                
                self.browser = await p.chromium.launch(**launch_options)
                context = await self.browser.new_context()
                
                # Load cookies
                self.load_cookies(context)
                
                page = await context.new_page()
                
                # Step 1: Find subreddits (limit to 5)
                subreddits = await self.find_subreddits(page, keyword, max_subreddits=5)
                
                if not subreddits:
                    print("❌ No subreddits found")
                    await self.browser.close()
                    return
                
                print(f"\n📋 Found {len(subreddits)} subreddits")
                print(f"🎯 Will scrape 5 users from each subreddit (max 25 total)\n")
                
                # Step 2 & 3: Collect users and scrape profiles
                subreddit_count = 0
                for subreddit in subreddits:
                    subreddit_count += 1
                    print(f"\n[{subreddit_count}/{len(subreddits)}] Processing r/{subreddit}")
                    
                    # Get only 5 users per subreddit
                    users = await self.get_active_users(page, subreddit, max_users=5)
                    
                    if not users:
                        print(f"  ⚠️  No users found, skipping...")
                        continue
                    
                    user_count = 0
                    for user in users[:5]:  # Limit to exactly 5 users
                        user_count += 1
                        # Throttle to avoid bans
                        await asyncio.sleep(random.uniform(1, 2))
                        
                        user_data = await self.scrape_user_profile(page, user)
                        self.users_data.append(user_data)
                        
                        # Save immediately to CSV
                        self.save_user_to_csv(user_data)
                        self.total_scraped += 1
                    
                    print(f"  ✅ Completed r/{subreddit}: {user_count} users scraped")
                
                await self.browser.close()
                print(f"\n{'='*60}")
                print(f"✅ SCRAPING COMPLETE!")
                print(f"📊 Total users scraped: {self.total_scraped}")
                print(f"📁 Saved to: {self.csv_filename}")
                print(f"{'='*60}")
                
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user!")
            await self.cleanup()
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            await self.cleanup()

def main():
    print("=" * 60)
    print("🔍 Reddit OSINT Scraper")
    print("=" * 60)
    
    keyword = input("\n🔑 Enter keyword to search: ").strip()
    
    if not keyword:
        print("❌ Keyword cannot be empty")
        return
    
    scraper = RedditScraper()
    
    try:
        asyncio.run(scraper.run(keyword))
    except KeyboardInterrupt:
        print("\n\n⚠️  Stopped by user. Data saved!")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
    
    print("\n" + "=" * 60)

if __name__ == '__main__':
    main()
