import time
import os
import sys
import platform
import urllib
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
import argparse
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost
import openai

openai.api_key = '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'
driver = None

def setup_driver():
    if platform.system() == "linux" or platform == "linux2":
        print('Not Supported')
        exit(1)
    # linux
    elif platform.system() == "Darwin":
        if platform.processor() == "arm":
            driver_path = os.path.join(os.getcwd(), 'lib', 'chromedriver-mac-arm64', 'chromedriver')
            binary_path = os.path.join(os.getcwd(), 'lib', 'chrome-mac-arm64', 'Google Chrome for Testing.app', 'Contents', 'MacOS', 'Google Chrome for Testing')
        else:
            driver_path = os.path.join(os.getcwd(), 'lib', 'chromedriver-mac-x64', 'chromedriver')
            binary_path = os.path.join(os.getcwd(), 'lib', 'chrome-mac-x64', 'Google Chrome for Testing.app', 'Contents', 'MacOS', 'Google Chrome for Testing')
    elif platform == "win32":
        if platform.machine().endswith('64'):
            driver_path = os.path.join(os.getcwd(), 'lib', 'chromedriver-win64', 'chromedriver.exe')
            binary_path = os.path.join(os.getcwd(), 'lib', 'chrome-win64', 'chrome.exe')
        else:
            driver_path = os.path.join(os.getcwd(), 'lib', 'chromedriver-win32', 'chromedriver.exe')
            binary_path = os.path.join(os.getcwd(), 'lib', 'chrome-win64', 'chrome.exe')

    service = Service(executable_path=driver_path)

    options = webdriver.ChromeOptions()
    options.binary_location = binary_path
    # options.add_argument("--headless")

    return webdriver.Chrome(service=service, options=options)

def scrape_quora_topics(driver, keyword):
    topics = []

    # browsers downloaded from https://googlechromelabs.github.io/chrome-for-testing/
    # signin_automation = True
    signin_automation = False
    no_results = True
    try:
        if signin_automation:
            driver.get("https://www.quora.com/")

            user_name = driver.find_element(By.CSS_SELECTOR, "input[type='email']")
            user_name.send_keys('ashjonasashjonas@gmail.com')

            user_name = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            user_name.send_keys('Automate123')

            time.sleep(1)

            enter = driver.find_element(By.CSS_SELECTOR, "button[type='button']")
            enter.click()

            time.sleep(5)

            search_box = driver.find_element(By.CSS_SELECTOR, "input[type='text']")
            search_box.send_keys(keyword)

            time.sleep(1)
            search_box.send_keys(Keys.RETURN)

            types = driver.find_elements(By.CSS_SELECTOR, "div[class='q-text qu-dynamicFontSize--small']")

            topics_element = None
            for type in types:
                if type.text == 'Topics':
                    topics_element = type
                    break

            topics_element.click()

        else:
            driver.get("https://www.quora.com/search?q="+urllib.parse.quote(keyword)+"&type=topic")

        time.sleep(5)

        topics_list = driver.find_elements(By.CSS_SELECTOR, "span[class='q-text qu-wordBreak--break-word']")
        if len(topics_list)>0:
            no_results = False

        tries = 2

        while tries>=0 and no_results:
            tries-=1
            driver.refresh()
            time.sleep(5)
            # driver.find_element("We couldn't find any results for 'business'.")
            topics_list = driver.find_elements(By.CSS_SELECTOR, "div[class='q-box qu-borderBottom qu-p--medium']")
            if len(topics_list)>0:
                no_results = False

        if no_results:
            print('Cannot find topics')
            return

        topics = [element.text for element in topics_list]

    except Exception as e:
        print("An error occurred:", e)
    finally:
        driver.quit()

    return topics

# Generate article using ChatGPT
def generate_article(length, prompt):
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=length  # Adjust length as needed
    )

    return response.choices[0].text.strip()

def create_wordpress_draft(title, content):
    wp = Client('https://your-wordpress-site.com/xmlrpc.php', 'your_username', 'your_password')

    post = WordPressPost()
    post.title = title
    post.content = content
    post.post_status = 'draft'

    wp.call(NewPost(post))
    return post.id


def main():
    # total arguments
    n = len(sys.argv)
    print("Total arguments passed:", n)

    try:
        keyword = None
        own_prompt = None
        num_articles = None
        word_count = None

        if n>0:
            parser = argparse.ArgumentParser()
            parser.add_argument('--keyword', type=str)
            parser.add_argument('--prompt', type=str)
            parser.add_argument('--n', type=str)
            parser.add_argument('--size', type=str)

            args = parser.parse_args()

            keyword = args.keyword
            own_prompt = args.prompt
            num_articles = args.n
            if args.size.lower() == 'small':
                word_count = 250
            elif args.size.lower() == 'medium':
                word_count = 500
            elif args.size.lower() == 'large':
                word_count = 700
        else:
            # User input
            keyword = input("Enter a keyword (e.g., 'business'): ")
            own_prompt = input("Enter the prompt text: ")
            num_articles = int(input("Enter the number of articles to generate: "))
            print("Enter option for length of articles: ")
            print("1. Small")
            print("2. Medium")
            print("3. Large")
            length_option = int(input(""))

            if length_option <1 or length_option >3:
                print("Wrong option")
                return

            options = {
                1: 250,  #Small
                2: 500,  #Medium
                3: 700   #Large
            }
            word_count = options[length_option];

        driver = setup_driver()
        topics = scrape_quora_topics(driver, keyword)

        for i in range(min(num_articles, len(topics))):
            topic = topics[i]
            # own_prompt = "Write an article in english of "+str(word_count)+" words about:"

            print('Generating Article no: '+ str(i+1))
            prompt = f"{own_prompt} {topic} in english of {str(word_count)} words"
            generated_article = generate_article(word_count, prompt)

            title = f"{topic} - Article"
            draft_content = generated_article

            print('Creating Wordpresss Draft: '+ str(i+1))
            post_id = create_wordpress_draft(title, draft_content)

            print(f"Draft created with ID: {post_id}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()