import os
import sys
import pandas as pd
from scraper.progress import Progress
from scraper.scroller import Scroller
from scraper.tweet import Tweet

from datetime import datetime
from fake_headers import Headers
from time import sleep

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService

from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

from openai import OpenAI
import schedule
import time

TWITTER_LOGIN_URL = "https://twitter.com/i/flow/login"

class Twitter_Scraper:
    def __init__(
        self,
        mail,
        username,
        password,
        openai_key,
        max_tweets=50,
        scrape_username=None,
        scrape_hashtag=None,
        scrape_query=None,
        scrape_poster_details=False,
        scrape_latest=True,
        scrape_top=False,
        proxy=None,
    ):
        print("Initializing Twitter Scraper...")
        self.mail = mail
        self.username = username
        self.password = password
        self.interrupted = False
        self.tweet_ids = set()
        self.data = []
        self.tweet_cards = []
        self.scraper_details = {
            "type": None,
            "username": None,
            "hashtag": None,
            "query": None,
            "tab": None,
            "poster_details": False,
        }
        self.max_tweets = max_tweets
        self.progress = Progress(0, max_tweets)
        self.router = self.go_to_home
        self.driver = self._get_driver(proxy)
        self.actions = ActionChains(self.driver)
        self.scroller = Scroller(self.driver)
        self._config_scraper(
            max_tweets,
            scrape_username,
            scrape_hashtag,
            scrape_query,
            scrape_latest,
            scrape_top,
            scrape_poster_details,
        )
        self.openai_client = OpenAI(api_key=openai_key)
        self.replied_tweets = set()

    def _config_scraper(
        self,
        max_tweets=50,
        scrape_username=None,
        scrape_hashtag=None,
        scrape_query=None,
        scrape_latest=True,
        scrape_top=False,
        scrape_poster_details=False,
    ):
        self.tweet_ids = set()
        self.data = []
        self.tweet_cards = []
        self.max_tweets = max_tweets
        self.progress = Progress(0, max_tweets)
        self.scraper_details = {
            "type": None,
            "username": scrape_username,
            "hashtag": str(scrape_hashtag).replace("#", "")
            if scrape_hashtag is not None
            else None,
            "query": scrape_query,
            "tab": "Latest" if scrape_latest else "Top" if scrape_top else "Latest",
            "poster_details": scrape_poster_details,
        }
        self.router = self.go_to_home
        self.scroller = Scroller(self.driver)

        if scrape_username is not None:
            self.scraper_details["type"] = "Username"
            self.router = self.go_to_profile
        elif scrape_hashtag is not None:
            self.scraper_details["type"] = "Hashtag"
            self.router = self.go_to_hashtag
        elif scrape_query is not None:
            self.scraper_details["type"] = "Query"
            self.router = self.go_to_search
        else:
            self.scraper_details["type"] = "Home"
            self.router = self.go_to_home
        pass

    def _get_driver(
        self,
        proxy=None,
    ):
        print("Setup WebDriver...")
        header = Headers().generate()["User-Agent"]

        # browser_option = ChromeOptions()
        browser_option = FirefoxOptions()
        browser_option.add_argument("--no-sandbox")
        browser_option.add_argument("--disable-dev-shm-usage")
        browser_option.add_argument("--ignore-certificate-errors")
        browser_option.add_argument("--disable-gpu")
        browser_option.add_argument("--log-level=3")
        browser_option.add_argument("--disable-notifications")
        browser_option.add_argument("--disable-popup-blocking")
        browser_option.add_argument("--user-agent={}".format(header))
        if proxy is not None:
            browser_option.add_argument("--proxy-server=%s" % proxy)

        # For Hiding Browser
        browser_option.add_argument("--headless")

        try:
            # print("Initializing ChromeDriver...")
            # driver = webdriver.Chrome(
            #     options=browser_option,
            # )

            print("Initializing FirefoxDriver...")
            driver = webdriver.Firefox(
                options=browser_option,
            )

            print("WebDriver Setup Complete")
            return driver
        except WebDriverException:
            try:
                # print("Downloading ChromeDriver...")
                # chromedriver_path = ChromeDriverManager().install()
                # chrome_service = ChromeService(executable_path=chromedriver_path)

                print("Downloading FirefoxDriver...")
                firefoxdriver_path = GeckoDriverManager().install()
                firefox_service = FirefoxService(executable_path=firefoxdriver_path)

                # print("Initializing ChromeDriver...")
                # driver = webdriver.Chrome(
                #     service=chrome_service,
                #     options=browser_option,
                # )

                print("Initializing FirefoxDriver...")
                driver = webdriver.Firefox(
                    service=firefox_service,
                    options=browser_option,
                )

                print("WebDriver Setup Complete")
                return driver
            except Exception as e:
                print(f"Error setting up WebDriver: {e}")
                sys.exit(1)
        pass

    def login(self):
        print()
        print("Logging in to Twitter...")

        try:
            self.driver.maximize_window()
            self.driver.get(TWITTER_LOGIN_URL)
            sleep(3)

            self._input_username()
            self._input_unusual_activity()
            self._input_password()

            cookies = self.driver.get_cookies()

            auth_token = None

            for cookie in cookies:
                if cookie["name"] == "auth_token":
                    auth_token = cookie["value"]
                    break

            if auth_token is None:
                raise ValueError(
                    """This may be due to the following:

- Internet connection is unstable
- Username is incorrect
- Password is incorrect
"""
                )

            print()
            print("Login Successful")
            print()
        except Exception as e:
            print()
            print(f"Login Failed: {e}")
            sys.exit(1)

        pass

    def _input_username(self):
        input_attempt = 0

        while True:
            try:
                username = self.driver.find_element(
                    "xpath", "//input[@autocomplete='username']"
                )

                username.send_keys(self.username)
                username.send_keys(Keys.RETURN)
                sleep(3)
                break
            except NoSuchElementException:
                input_attempt += 1
                if input_attempt >= 3:
                    print()
                    print(
                        """There was an error inputting the username.

It may be due to the following:
- Internet connection is unstable
- Username is incorrect
- Twitter is experiencing unusual activity"""
                    )
                    self.driver.quit()
                    sys.exit(1)
                else:
                    print("Re-attempting to input username...")
                    sleep(2)

    def _input_unusual_activity(self):
        input_attempt = 0

        while True:
            try:
                unusual_activity = self.driver.find_element(
                    "xpath", "//input[@data-testid='ocfEnterTextTextInput']"
                )
                unusual_activity.send_keys(self.username)
                unusual_activity.send_keys(Keys.RETURN)
                sleep(3)
                break
            except NoSuchElementException:
                input_attempt += 1
                if input_attempt >= 3:
                    break

    def _input_password(self):
        input_attempt = 0

        while True:
            try:
                password = self.driver.find_element(
                    "xpath", "//input[@autocomplete='current-password']"
                )

                password.send_keys(self.password)
                password.send_keys(Keys.RETURN)
                sleep(3)
                break
            except NoSuchElementException:
                input_attempt += 1
                if input_attempt >= 3:
                    print()
                    print(
                        """There was an error inputting the password.

It may be due to the following:
- Internet connection is unstable
- Password is incorrect
- Twitter is experiencing unusual activity"""
                    )
                    self.driver.quit()
                    sys.exit(1)
                else:
                    print("Re-attempting to input password...")
                    sleep(2)

    def post_tweet(self, tweet_text):
        """
        Posts a tweet with the given text
        Args:
            tweet_text (str): The text content of the tweet
        """
        print(f"Posting tweet: {tweet_text}")
        try:
            # # Wait for login to complete and navigate to home page
            # WebDriverWait(self.driver, 10).until(
            #     EC.presence_of_element_located((By.XPATH, "//a[@href='/home']"))
            # )
            
            # Navigate to the home page to ensure the tweet box is available
            self.go_to_home()

            # Create a WebDriverWait object
            wait = WebDriverWait(self.driver, 20)

            # Find and click the tweet composition box (updated selector)
            tweet_box = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='tweetTextarea_0']"))
            )
            tweet_box.send_keys(tweet_text)

            # Find and click the tweet button (updated selector)
            tweet_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='tweetButtonInline']"))
            )
            tweet_button.click()

            # Wait for a short period to ensure the tweet is posted
            sleep(5)

            print("Tweet posted successfully")
            
        except Exception as e:
            print(f"Error posting tweet: {e}")

    def go_to_home(self):
        self.driver.get("https://twitter.com/home")
        sleep(3)
        pass

    def go_to_profile(self):
        if (
            self.scraper_details["username"] is None
            or self.scraper_details["username"] == ""
        ):
            print("Username is not set.")
            sys.exit(1)
        else:
            self.driver.get(f"https://twitter.com/{self.scraper_details['username']}")
            sleep(3)
        pass

    def go_to_hashtag(self):
        if (
            self.scraper_details["hashtag"] is None
            or self.scraper_details["hashtag"] == ""
        ):
            print("Hashtag is not set.")
            sys.exit(1)
        else:
            url = f"https://twitter.com/hashtag/{self.scraper_details['hashtag']}?src=hashtag_click"
            if self.scraper_details["tab"] == "Latest":
                url += "&f=live"

            self.driver.get(url)
            sleep(3)
        pass

    def go_to_search(self):
        if self.scraper_details["query"] is None or self.scraper_details["query"] == "":
            print("Query is not set.")
            sys.exit(1)
        else:
            url = f"https://twitter.com/search?q={self.scraper_details['query']}&src=typed_query"
            if self.scraper_details["tab"] == "Latest":
                url += "&f=live"

            self.driver.get(url)
            sleep(3)
        pass

    def get_tweet_cards(self):
        self.tweet_cards = self.driver.find_elements(
            "xpath", '//article[@data-testid="tweet" and not(@disabled)]'
        )
        pass

    def remove_hidden_cards(self):
        try:
            hidden_cards = self.driver.find_elements(
                "xpath", '//article[@data-testid="tweet" and @disabled]'
            )

            for card in hidden_cards[1:-2]:
                self.driver.execute_script(
                    "arguments[0].parentNode.parentNode.parentNode.remove();", card
                )
        except Exception as e:
            return
        pass

    def scrape_tweets(
        self,
        max_tweets=50,
        no_tweets_limit=False,
        scrape_username=None,
        scrape_hashtag=None,
        scrape_query=None,
        scrape_latest=True,
        scrape_top=False,
        scrape_poster_details=False,
        router=None,
    ):
        self._config_scraper(
            max_tweets,
            scrape_username,
            scrape_hashtag,
            scrape_query,
            scrape_latest,
            scrape_top,
            scrape_poster_details,
        )

        if router is None:
            router = self.router

        router()

        if self.scraper_details["type"] == "Username":
            print(
                "Scraping Tweets from @{}...".format(self.scraper_details["username"])
            )
        elif self.scraper_details["type"] == "Hashtag":
            print(
                "Scraping {} Tweets from #{}...".format(
                    self.scraper_details["tab"], self.scraper_details["hashtag"]
                )
            )
        elif self.scraper_details["type"] == "Query":
            print(
                "Scraping {} Tweets from {} search...".format(
                    self.scraper_details["tab"], self.scraper_details["query"]
                )
            )
        elif self.scraper_details["type"] == "Home":
            print("Scraping Tweets from Home...")

        # Accept cookies to make the banner disappear
        try:
            accept_cookies_btn = self.driver.find_element(
            "xpath", "//span[text()='Refuse non-essential cookies']/../../..")
            accept_cookies_btn.click()
        except NoSuchElementException:
            pass

        self.progress.print_progress(0, False, 0, no_tweets_limit)

        refresh_count = 0
        added_tweets = 0
        empty_count = 0
        retry_cnt = 0

        while self.scroller.scrolling:
            try:
                self.get_tweet_cards()
                added_tweets = 0

                for card in self.tweet_cards[-15:]:
                    try:
                        tweet_id = str(card)

                        if tweet_id not in self.tweet_ids:
                            self.tweet_ids.add(tweet_id)

                            if not self.scraper_details["poster_details"]:
                                self.driver.execute_script(
                                    "arguments[0].scrollIntoView();", card
                                )

                            tweet = Tweet(
                                card=card,
                                driver=self.driver,
                                actions=self.actions,
                                scrape_poster_details=self.scraper_details[
                                    "poster_details"
                                ],
                            )

                            if tweet:
                                if not tweet.error and tweet.tweet is not None:
                                    if not tweet.is_ad:
                                        self.data.append(tweet.tweet)
                                        added_tweets += 1
                                        self.progress.print_progress(len(self.data), False, 0, no_tweets_limit)

                                        if len(self.data) >= self.max_tweets and not no_tweets_limit:
                                            self.scroller.scrolling = False
                                            break
                                    else:
                                        continue
                                else:
                                    continue
                            else:
                                continue
                        else:
                            continue
                    except NoSuchElementException:
                        continue

                if len(self.data) >= self.max_tweets and not no_tweets_limit:
                    break

                if added_tweets == 0:
                    # Check if there is a button "Retry" and click on it with a regular basis until a certain amount of tries
                    try:
                        while retry_cnt < 15:
                            retry_button = self.driver.find_element(
                            "xpath", "//span[text()='Retry']/../../..")
                            self.progress.print_progress(len(self.data), True, retry_cnt, no_tweets_limit)
                            sleep(58)
                            retry_button.click()
                            retry_cnt += 1
                            sleep(2)
                    # There is no Retry button so the counter is reseted
                    except NoSuchElementException:
                        retry_cnt = 0
                        self.progress.print_progress(len(self.data), False, 0, no_tweets_limit)

                    if empty_count >= 5:
                        if refresh_count >= 3:
                            print()
                            print("No more tweets to scrape")
                            break
                        refresh_count += 1
                    empty_count += 1
                    sleep(1)
                else:
                    empty_count = 0
                    refresh_count = 0
            except StaleElementReferenceException:
                sleep(2)
                continue
            except KeyboardInterrupt:
                print("\n")
                print("Keyboard Interrupt")
                self.interrupted = True
                break
            except Exception as e:
                print("\n")
                print(f"Error scraping tweets: {e}")
                break

        print("")

        if len(self.data) >= self.max_tweets or no_tweets_limit:
            print("Scraping Complete")
        else:
            print("Scraping Incomplete")

        if not no_tweets_limit:
            print("Tweets: {} out of {}\n".format(len(self.data), self.max_tweets))

        pass

    def save_to_csv(self):
        print("Saving Tweets to CSV...")
        
        if not self.data:
            print("No tweets to save!")
            return
        
        now = datetime.now()
        print(f"Current working directory: {os.getcwd()}")
        folder_path = os.path.join(os.getcwd(), "tweets")

        try:
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
                print(f"Created folder: {folder_path}")

            data = {
                "Name": [tweet[0] for tweet in self.data],
                "Handle": [tweet[1] for tweet in self.data],
                "Timestamp": [tweet[2] for tweet in self.data],
                "Verified": [tweet[3] for tweet in self.data],
                "Content": [tweet[4] for tweet in self.data],
                "Comments": [tweet[5] for tweet in self.data],
                "Retweets": [tweet[6] for tweet in self.data],
                "Likes": [tweet[7] for tweet in self.data],
                "Analytics": [tweet[8] for tweet in self.data],
                "Tags": [tweet[9] for tweet in self.data],
                "Mentions": [tweet[10] for tweet in self.data],
                "Emojis": [tweet[11] for tweet in self.data],
                "Profile Image": [tweet[12] for tweet in self.data],
                "Tweet Link": [tweet[13] for tweet in self.data],
                "Tweet ID": [f"tweet_id:{tweet[14]}" for tweet in self.data],
            }

            if self.scraper_details["poster_details"]:
                data["Tweeter ID"] = [f"user_id:{tweet[15]}" for tweet in self.data]
                data["Following"] = [tweet[16] for tweet in self.data]
                data["Followers"] = [tweet[17] for tweet in self.data]

            df = pd.DataFrame(data)
            current_time = now.strftime("%Y-%m-%d_%H-%M-%S")
            file_path = os.path.join(folder_path, f"{current_time}_tweets_1-{len(self.data)}.csv")
            
            pd.set_option("display.max_colwidth", None)
            df.to_csv(file_path, index=False, encoding="utf-8")

            print(f"CSV Saved: {file_path}")
            
        except Exception as e:
            print(f"Error saving CSV: {e}")
            print(f"Attempted to save to: {folder_path}")
            print(f"Data length: {len(self.data)}")
            print(f"First tweet data: {self.data[0] if self.data else 'No data'}")
            raise

    def get_tweets(self):
        return self.data

    def get_session(self):
        """Get current session cookies"""
        return self.driver.get_cookies()

    def load_session(self, cookies):
        """Load saved session cookies"""
        # First navigate to twitter.com
        self.driver.get('https://twitter.com')
        
        # Then add the cookies
        for cookie in cookies:
            self.driver.add_cookie(cookie)
        
        # Refresh the page
        self.driver.refresh()

    def _get_ai_response(self, tweet_content):
        """Get response from OpenAI API"""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are GreyBotAI, a helpful and friendly AI assistant. Keep responses concise and under 280 characters."},
                    {"role": "user", "content": f"Please respond to this tweet: {tweet_content}"}
                ],
                max_tokens=100,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error getting AI response: {e}")
            return None

    def _process_mentions(self, tweets_df):
        """Process and respond to mentions from dataframe"""
        try:
            if tweets_df.empty:
                print("No tweets to process")
                return False

            for _, row in tweets_df.iterrows():
                tweet_id = row['Tweet ID'].replace('tweet_id:', '')
                
                if tweet_id in self.replied_tweets:
                    continue

                tweet_content = row['Content']
                tweet_author = row['Handle']
                
                if tweet_author == self.username:
                    continue

                ai_response = self._get_ai_response(tweet_content)
                if ai_response:
                    reply = f"@{tweet_author} {ai_response}"
                    self.post_tweet(reply)
                    print(f"Replied to tweet {tweet_id}: {reply}")
                    self.replied_tweets.add(tweet_id)
                    time.sleep(2)  # Rate limiting

            return True

        except Exception as e:
            print(f"Error processing mentions: {e}")
            return False

    def _scrape_and_reply(self):
        """Scrape mentions and reply to them"""
        try:
            # Clear previous data
            self.data = []
            
            # Scrape new mentions
            self.scrape_tweets(
                max_tweets=10,
                scrape_latest=True,
                scrape_top=False,
                scrape_query=f"(@{self.username})"
            )
            
            # Convert scraped data to DataFrame
            tweets_df = pd.DataFrame({
                'Tweet ID': [f"tweet_id:{tweet[14]}" for tweet in self.data],
                'Content': [tweet[4] for tweet in self.data],
                'Handle': [tweet[1] for tweet in self.data]
            })
            
            print(f"Number of tweets collected: {len(tweets_df)}")
            self._process_mentions(tweets_df)
            
            return True

        except Exception as e:
            print(f"Error in scrape and reply: {e}")
            return False

    def start_monitoring_mentions(self):
        """Start monitoring mentions and replying"""
        # First run immediately
        self._scrape_and_reply()
        
        # Schedule runs every 1 minute
        schedule.every(1).minutes.do(self._scrape_and_reply)
