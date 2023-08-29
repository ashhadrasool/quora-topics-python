import time
import os
import sys
import platform
import urllib
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import argparse
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost
import openai

openai.api_key = 'xyz'
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
    elif platform.system() == "Windows":
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

        tries = 1
        total_tries=3

        delay=5
        while tries<=total_tries and no_results:
            print("Scrap try: "+str(tries))
            tries+=1

            by = By.CSS_SELECTOR
            selector = "div[class='q-box qu-borderBottom qu-p--medium']"

            #wait of maximum delay time
            WebDriverWait(driver, delay).until(EC.presence_of_all_elements_located((by, selector)))
            time.sleep(3)
            topics_list = driver.find_elements(by, selector)
            if len(topics_list)==0:
                driver.refresh()
            if len(topics_list)==1 and topics_list[0].text.startswith("We couldn't find any results for"):
                print("Couldn't find")
                driver.refresh()
            if len(topics_list)==1 and topics_list[0].text.startswith("We couldn't find any more results for"):
                selector_new = "div[class='q-flex qu-alignItems--center qu-py--small qu-flex--auto qu-overflow--hidden']"
                WebDriverWait(driver, delay).until(EC.presence_of_all_elements_located((by, selector_new)))
                time.sleep(2)
                topics_list = driver.find_elements(by, selector_new)
                if len(topics_list)>1:
                    no_results = False
                else:
                    driver.refresh()
            elif len(topics_list)>0:
                no_results = False

        if no_results:
            print('Cannot find topics')
            exit(1)
        else:
            print("Found Total "+str(len(topics_list))+" Topics on Quora")

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
    # print("Total arguments passed:", n)

    try:
        keyword = None
        own_prompt = None
        num_articles = None
        word_count = None

        arg_mode = True

        if n>0:
            parser = argparse.ArgumentParser()
            parser.add_argument('--keyword', type=str)
            parser.add_argument('--prompt', type=str)
            parser.add_argument('--n', type=int)
            parser.add_argument('--size', type=str)

            args = parser.parse_args()

            if args.keyword != None and args.prompt != None and args.n != None:
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
                arg_mode = False

        if arg_mode == False:
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

        articles_to_generate = min(num_articles, len(topics))
        print('Articles to generate: '+str(articles_to_generate))
        for i in range(articles_to_generate):
            topic = topics[i]
            # own_prompt = "Write an article in english of "+str(word_count)+" words about:"

            print('\nGenerating Article no: '+ str(i+1))
            prompt = f"{own_prompt} {topic} in english of {str(word_count)} words"
            generated_article = generate_article(word_count, prompt)

            title = f"{topic} - Article"
            draft_content = generated_article

            try:
                print('Creating Wordpresss Draft: '+ str(i+1))
                post_id = create_wordpress_draft(title, draft_content)
                print(f"Draft created with ID: {post_id}")
            except:
                print('Error Creating Wordpresss Draft: '+ str(i+1))


    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()